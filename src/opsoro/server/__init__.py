from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_babel import Babel
from flask_login import LoginManager, logout_user, current_user, login_required

from tornado.wsgi import WSGIContainer
from tornado.ioloop import IOLoop
import tornado.web
import tornado.httpserver
from sockjs.tornado import SockJSRouter, SockJSConnection
from functools import wraps, partial

from opsoro.expression import Expression
from opsoro.robot import Robot
from opsoro.console_msg import *
from opsoro.preferences import Preferences
from opsoro.server.request_handlers import RHandler

import pluginbase
import os
import atexit
import threading
import base64
import logging

try:
    import simplejson as json
    print_info("Using simplejson")
except ImportError:
    import json
    print_info("Simplejson not available, falling back on json")

dof_positions = {}
# Helper function
get_path = partial(os.path.join, os.path.abspath(os.path.dirname(__file__)))


# Helper class to deal with login
class AdminUser(object):
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return "admin"

    def is_admin(self):
        return True


class Server(object):
    def __init__(self):
        self.request_handler = RHandler(self)

        # Create flask instance for webserver
        self.flaskapp = Flask(__name__)

        self.flaskapp.config.from_pyfile('settings.cfg')
        self.babel = Babel(self.flaskapp)

        # Setup key for sessions
        self.flaskapp.secret_key = "5\x075y\xfe$\x1aV\x1c<A\xf4\xc1\xcfst0\xa49\x9e@\x0b\xb2\x17"

        # Setup login manager
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.flaskapp)
        self.login_manager.login_view = "login"
        self.setup_user_loader()

        # Variable to keep track of the active user
        self.active_session_key = None

        # Token to authenticate socket connections
        # Client requests token via AJAX, server generates token if session is valid
        # Client then sends the token to the server via SockJS, validating the connection
        self.sockjs_token = None

        # Setup app system
        self.plugin_base = pluginbase.PluginBase(package="opsoro.server.apps")
        self.plugin_source = self.plugin_base.make_plugin_source(
            searchpath=[get_path("./../apps")])

        self.apps = {}
        self.activeapp = None
        self.apps_can_register_bp = True  # Make sure apps are only registered during setup
        self.current_bp_app = ""  # Keep track of current app for blueprint setup

        # Socket callback dicts
        self.sockjs_connect_cb = {}
        self.sockjs_disconnect_cb = {}
        self.sockjs_message_cb = {}

        # if Preferences.check_if_update():
        #     print_info("Update available")
        #     Preferences.update()

        for plugin_name in self.plugin_source.list_plugins():
            self.current_bp_app = plugin_name

            plugin = self.plugin_source.load_plugin(plugin_name)
            print_apploaded(plugin_name)

            if not hasattr(plugin, "config"):
                plugin.config = {"full_name": "No name",
                                 "icon": "fa-warning",
                                 'color': '#333'}

            if "full_name" not in plugin.config:
                plugin.config["full_name"] = "No name"

            if "icon" not in plugin.config:
                plugin.config["icon"] = "fa-warning"

            self.apps[plugin_name] = plugin
            try:
                plugin.setup(self)
            except AttributeError:
                print_info("%s has no setup function" % plugin_name)

            try:
                plugin.setup_pages(self)
            except AttributeError:
                print_info("%s has no setup_pages function" % plugin_name)

        self.current_bp_app = ""
        self.apps_can_register_bp = False

        # Initialize all URLs
        self.request_handler.set_urls()

        # Run stop function at exit
        atexit.register(self.at_exit)

    def at_exit(self):
        self.stop_current_app()

        if threading.activeCount() > 0:
            threads = threading.enumerate()
            for thread in threads:
                try:
                    thread.stop()
                    thread.join()
                except AttributeError:
                    pass

    def setup_user_loader(self):
        @self.login_manager.user_loader
        def load_user(id):
            if id == "admin":
                return AdminUser()
            else:
                return None

    def register_app_blueprint(self, bp):
        assert self.apps_can_register_bp, "Apps can only register blueprints at setup!"

        prefix = "/apps/" + self.current_bp_app
        self.flaskapp.register_blueprint(bp, url_prefix=prefix)

    def render_template(self, template, **kwargs):
        return self.request_handler.render_template(template, **kwargs)

    def run(self):
        # Setup SockJS
        class OpsoroSocketConnection(SockJSConnection):
            def __init__(conn, *args, **kwargs):
                super(OpsoroSocketConnection, conn).__init__(*args, **kwargs)
                conn._authenticated = False
                conn._activeapp = self.activeapp

            def on_message(conn, msg):
                # Attempt to decode JSON
                try:
                    message = json.loads(msg)
                except ValueError:
                    conn.send_error("Invalid JSON")
                    return

                if not conn._authenticated:
                    # Attempt to authenticate the socket
                    try:
                        if message["action"] == "authenticate":
                            token = base64.b64decode(message["token"])
                            if token == self.sockjs_token and self.sockjs_token is not None:
                                # Auth succeeded
                                conn._authenticated = True

                                # Trigger connect callback
                                if conn._activeapp in self.sockjs_connect_cb:
                                    self.sockjs_connect_cb[conn._activeapp](
                                        conn)

                                return

                        # Auth failed
                        return
                    except KeyError:
                        # Auth failed
                        return
                else:
                    # Decode action and trigger callback, if it exists.
                    action = message.pop("action", "")
                    if conn._activeapp in self.sockjs_message_cb:
                        if action in self.sockjs_message_cb[conn._activeapp]:
                            self.sockjs_message_cb[conn._activeapp][action](
                                conn, message)

            def on_open(conn, info):
                # Connect callback is triggered when socket is authenticated.
                pass

            def on_close(conn):
                if conn._authenticated:
                    if conn._activeapp in self.sockjs_disconnect_cb:
                        self.sockjs_disconnect_cb[conn._activeapp](conn)

            def send_error(conn, message):
                return conn.send(
                    json.dumps({
                        "action": "error",
                        "status": "error",
                        "message": message
                    }))

            def send_data(conn, action, data):
                msg = {"action": action, "status": "success"}
                msg.update(data)
                return conn.send(json.dumps(msg))

        flaskwsgi = WSGIContainer(self.flaskapp)
        socketrouter = SockJSRouter(OpsoroSocketConnection, "/sockjs")

        tornado_app = tornado.web.Application(socketrouter.urls + [(
            r".*", tornado.web.FallbackHandler, {"fallback": flaskwsgi})])
        tornado_app.listen(80)

        # http_server = tornado.httpserver.HTTPServer(tornado_app, ssl_options={
        # 	"certfile": "/etc/ssl/certs/server.crt",
        # 	"keyfile": "/etc/ssl/private/server.key",
        # 	})
        # http_server.listen(443)
        try:
            IOLoop.instance().start()
        except KeyboardInterrupt:
            self.stop_current_app()
            print "Goodbye!"

    def stop_current_app(self):
        Robot.stop()
        if self.activeapp in self.apps:
            print_appstopped(self.activeapp)
            try:
                self.apps[self.activeapp].stop(self)
            except AttributeError:
                print_info("%s has no stop function" % self.activeapp)
        self.activeapp = None

    def shutdown(self):
        logging.info("Stopping server")
        io_loop = IOLoop.instance()
        io_loop.stop()

    def protected_view(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_user.is_authenticated:
                if current_user.is_admin():
                    if session[
                            "active_session_key"] == self.active_session_key:
                        # the actual page
                        return f(*args, **kwargs)
                    else:
                        logout_user()
                        session.pop("active_session_key", None)
                        flash(
                            "You have been logged out because a more recent session is active.")
                        return redirect(url_for("login"))
                else:
                    flash(
                        "You do not have permission to access the requested page. Please log in below.")
                    return redirect(url_for("login"))
            else:
                flash(
                    "You do not have permission to access the requested page. Please log in below.")
                return redirect(url_for("login"))

        return wrapper

    def app_view(self, f):
        appname = f.__module__.split(".")[-1]

        @wraps(f)
        def wrapper(*args, **kwargs):
            # Protected page
            if current_user.is_authenticated:
                if current_user.is_admin():
                    if session[
                            "active_session_key"] != self.active_session_key:
                        logout_user()
                        session.pop("active_session_key", None)
                        flash(
                            "You have been logged out because a more recent session is active.")
                        return redirect(url_for("login"))
                else:
                    flash(
                        "You do not have permission to access the requested page. Please log in below.")
                    return redirect(url_for("login"))
            else:
                flash(
                    "You do not have permission to access the requested page. Please log in below.")
                return redirect(url_for("login"))

            # Check if app is active
            if appname == self.activeapp:
                # This app is active
                return f(*args, **kwargs)
            else:
                # Return app not active page
                assert appname in self.apps, "Could not find %s in list of loaded apps." % appname
                data = {
                    "app": {},
                    # "appname": appname,
                    "page_icon": self.apps[appname].config["icon"],
                    "page_caption": self.apps[appname].config["full_name"]
                }
                data["title"] = self.request_handler.title
                if self.activeapp in self.apps:
                    # Another app is active
                    data["app"]["active"] = True
                    data["app"]["name"] = self.apps[self.activeapp].config[
                        "full_name"]
                    data["app"]["icon"] = self.apps[self.activeapp].config[
                        "icon"]
                    data["title"] += " - %s" % self.apps[
                        self.activeapp].config["full_name"]
                else:
                    # No app is active
                    data["app"]["active"] = False

                return render_template("app_not_active.html", **data)

        return wrapper

    def app_api(self, f):
        appname = f.__module__.split(".")[-1]

        @wraps(f)
        def wrapper(*args, **kwargs):
            # Protected page
            if current_user.is_authenticated:
                if current_user.is_admin():
                    if session[
                            "active_session_key"] != self.active_session_key:
                        logout_user()
                        session.pop("active_session_key", None)
                        return jsonify(
                            status="error",
                            message="You have been logged out because a more recent session is active.")
                else:
                    return jsonify(
                        status="error",
                        message="You do not have permission to access the requested page.")
            else:
                return jsonify(
                    status="error",
                    message="You do not have permission to access the requested page.")

            # Check if app is active
            if appname == self.activeapp:
                # This app is active
                data = f(*args, **kwargs)
                if data is None:
                    data = {}
                if "status" not in data:
                    data["status"] = "success"

                return jsonify(data)
            else:
                # Return app not active page
                assert appname in self.apps, "Could not find %s in list of loaded apps." % appname

                return jsonify(
                    status="error", message="This app is not active.")

        return wrapper

    def app_socket_connected(self, f):
        appname = f.__module__.split(".")[-1]

        self.sockjs_connect_cb[appname] = f

        return f

    def app_socket_disconnected(self, f):
        appname = f.__module__.split(".")[-1]

        self.sockjs_disconnect_cb[appname] = f

        return f

    def app_socket_message(self, action=""):
        def inner(f):
            appname = f.__module__.split(".")[-1]

            # Create new dict for app if necessary
            if appname not in self.sockjs_message_cb:
                self.sockjs_message_cb[appname] = {}

            self.sockjs_message_cb[appname][action] = f

            return f

        return inner
