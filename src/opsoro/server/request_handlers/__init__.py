from flask import Flask, request, render_template, redirect, url_for, flash, session, send_from_directory
from flask_login import login_user, logout_user, current_user
from werkzeug.exceptions import default_exceptions

from functools import partial

from opsoro.expression import Expression
from opsoro.robot import Robot
from opsoro.console_msg import *
from opsoro.preferences import Preferences
from opsoro.server.request_handlers.opsoro_data_requests import *

import random
import os
import subprocess
import base64

import glob

try:
    import simplejson as json
except ImportError:
    import json

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


class RHandler(object):
    def __init__(self, server):
        # title
        self.title = "OPSORO play"
        self.robotName = "Ono"

        self.server = server

    def set_urls(self):

        protect = self.server.protected_view

        self.server.flaskapp.add_url_rule("/",
                                          "index",
                                          protect(self.page_index), )
        self.server.flaskapp.add_url_rule(
            "/login/",
            "login",
            self.page_login,
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule("/logout/",
                                          "logout",
                                          self.page_logout, )
        # self.server.flaskapp.add_url_rule(
        #     "/preferences",
        #     "preferences",
        #     protect(self.page_preferences),
        #     methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule("/sockjstoken/",
                                          "sockjstoken",
                                          self.page_sockjstoken, )
        self.server.flaskapp.add_url_rule("/shutdown/",
                                          "shutdown",
                                          protect(self.page_shutdown), )
        self.server.flaskapp.add_url_rule("/closeapp/",
                                          "closeapp",
                                          protect(self.page_closeapp), )
        self.server.flaskapp.add_url_rule("/openapp/<appname>/",
                                          "openapp",
                                          protect(self.page_openapp), )
        # self.server.flaskapp.add_url_rule(
        #     "/app/<appname>/files/<action>",
        #     "files",
        #     protect(self.page_files),
        #     methods=["GET", "POST"], )
        # ----------------------------------------------------------------------
        # DOCUMENTS
        # ----------------------------------------------------------------------
        self.server.flaskapp.add_url_rule(
            "/docs/data/<app_name>/",
            "file_data",
            protect(docs_file_data),
            methods=["GET"], )
        self.server.flaskapp.add_url_rule(
            "/docs/save/<app_name>/",
            "file_save",
            protect(docs_file_save),
            methods=["POST"], )
        self.server.flaskapp.add_url_rule(
            "/docs/delete/<app_name>/",
            "file_delete",
            protect(docs_file_delete),
            methods=["POST"], )
        self.server.flaskapp.add_url_rule(
            "/docs/list/",
            "file_list",
            protect(self.page_file_list),
            methods=["GET"], )

        # ----------------------------------------------------------------------
        # ROBOT
        # ----------------------------------------------------------------------
        self.server.flaskapp.add_url_rule(
            "/robot/",
            "robot",
            self.page_virtual,
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule(
            "/robot/config/",
            "robot_config",
            protect(robot_config_data),
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule(
            "/robot/emotion/",
            "robot_emotion",
            protect(robot_emotion),
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule(
            "/robot/dof/",
            "robot_dof",
            protect(robot_dof_data),
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule(
            "/robot/dofs/",
            "robot_dofs",
            protect(robot_dofs_data),
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule(
            "/robot/tts/",
            "robot_tts",
            protect(robot_tts),
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule(
            "/robot/sound/",
            "robot_sound",
            protect(robot_sound),
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule(
            "/robot/servo/",
            "robot_servo",
            protect(robot_servo),
            methods=["GET", "POST"], )
        self.server.flaskapp.add_url_rule(
            "/robot/stop/",
            "robot_stop",
            protect(robot_stop),
            methods=["GET", "POST"], )

        for _exc in default_exceptions:
            self.server.flaskapp.errorhandler(_exc)(self.show_errormessage)

        self.server.flaskapp.context_processor(self.inject_opsoro_vars)

    def render_template(self, template, **kwargs):
        kwargs["app"] = {}

        kwargs["title"] = self.title
        # Set app variables
        if self.server.activeapp in self.server.apps:
            kwargs["app"]["active"] = True
            kwargs["app"]["name"] = self.server.apps[
                self.server.activeapp].config["full_name"].title()
            kwargs["app"]["full_name"] = self.server.apps[
                self.server.activeapp].config["full_name"]
            kwargs["app"]["formatted_name"] = self.server.apps[
                self.server.activeapp].config["formatted_name"]
            kwargs["app"]["icon"] = self.server.apps[
                self.server.activeapp].config["icon"]
            kwargs["app"]["color"] = self.server.apps[
                self.server.activeapp].config["color"]
            kwargs["title"] += " - %s" % self.server.apps[
                self.server.activeapp].config["full_name"].title()
            kwargs["page_icon"] = self.server.apps[
                self.server.activeapp].config["icon"]
            kwargs["page_caption"] = self.server.apps[
                self.server.activeapp].config["full_name"]
        else:
            kwargs["app"]["active"] = False

        if 'actions' not in kwargs:
            kwargs['actions'] = {}
        kwargs['actions']['openfile'] = request.args.get("f", None)

        if "closebutton" not in kwargs:
            kwargs["closebutton"] = True

        kwargs["isuser"] = True

        return render_template(template, **kwargs)

    def page_index(self):
        data = {"title": self.title, "apps": []}

        if self.server.activeapp in self.server.apps:
            app = self.server.apps[self.server.activeapp]
            if app.config.has_key('allowed_background'):
                if not app.config['allowed_background']:
                    self.server.stop_current_app()
                else:
                    data["activeapp"] = {"name": self.server.activeapp,
                                         "full_name": app.config["full_name"],
                                         "formatted_name": app.config["formatted_name"],
                                         "icon": app.config["icon"],
                                         "color": app.config['color']}

        for appname in sorted(self.server.apps.keys()):
            app = self.server.apps[appname]
            data["apps"].append({"name": appname,
                                 "full_name": app.config["full_name"],
                                 "formatted_name": app.config["formatted_name"],
                                 "icon": app.config["icon"],
                                 "color": app.config['color'],
                                 "active": (appname == self.server.activeapp)})

        return self.render_template("apps.html", **data)

    def page_login(self):
        if request.method == "GET":
            kwargs = {}
            kwargs["title"] = self.title + " - Login"
            kwargs["isuser"] = False
            return render_template("login.html", **kwargs)

        password = request.form["password"]

        if password == Preferences.get(
                "general", "password", default="RobotOpsoro"):
            login_user(AdminUser())
            self.server.active_session_key = os.urandom(24)
            session["active_session_key"] = self.server.active_session_key
            return redirect(url_for("index"))
        else:
            flash("Wrong password.")
            return redirect(url_for("login"))

    def page_logout(self):
        logout_user()
        session.pop("active_session_key", None)
        flash("You have been logged out.")
        return redirect(url_for("login"))

    def page_sockjstoken(self):
        if current_user.is_authenticated:
            if current_user.is_admin():
                if session[
                        "active_session_key"] == self.server.active_session_key:
                    # Valid user, generate a token
                    self.server.sockjs_token = os.urandom(24)
                    return base64.b64encode(self.server.sockjs_token)
                else:
                    logout_user()
                    session.pop("active_session_key", None)
        return ""  # Not a valid user, return nothing!

    def page_shutdown(self):
        message = ""
        self.server.stop_current_app()

        # Run shutdown command with 5 second delay, returns immediately
        subprocess.Popen("sleep 5 && sudo halt", shell=True)
        self.server.shutdown()
        return message

    def page_closeapp(self):
        self.server.stop_current_app()
        return redirect(url_for("index"))

    def page_openapp(self, appname):
        # Check if another app is running, if so, run its stop function
        if self.server.activeapp == appname:
            return redirect("/apps/%s/" % appname)

        self.server.stop_current_app()

        if appname in self.server.apps:
            # robot_state:
            # 0: Manual start/stop
            # 1: Start robot automatically (alive feature according to preferences)
            # 2: Start robot automatically and enable alive feature
            # 3: Start robot automatically and disable alive feature
            if self.server.apps[appname].config.has_key('robot_state'):
                print_info(self.server.apps[appname].config['robot_state'])
                if self.server.apps[appname].config['robot_state'] > 0:
                    Robot.start()

            self.server.activeapp = appname

            try:
                print_appstarted(appname)
                self.server.apps[appname].start(self.server)
            except AttributeError:
                print_info("%s has no start function" % self.server.activeapp)

            return redirect("/apps/%s/" % appname)
        else:
            return redirect(url_for("index"))

    def page_file_list(self):
        data = docs_file_list()
        return self.render_template(
            "_filelist.html",
            title=self.title + " - Files",
            # page_caption=appSpecificFolderPath,
            page_icon="fa-folder",
            **data)

    def page_virtual(self):
        # clientconn = None

        # def send_stopped():
        #     global clientconn
        #     if clientconn:
        #         clientconn.send_data("soundStopped", {})

        # if request.method == "POST":
        #     dataOnly = request.form.get("getdata", type=int, default=0)
        #     if dataOnly == 1:
        #         tempDofs = Robot.dof_values()
        #         return json.dumps({'success': True, 'dofs': tempDofs})
        # # 		return Expression.dof_values
        #     frameOnly = request.form.get("frame", type=int, default=0)
        #     if frameOnly == 1:
        #         #return self.render_template("virtual.html", title="Virtual Model", page_caption="Virtual model", page_icon="fa-smile-o", modules=Modules.modules)
        #         pass

        file_location = get_path('../../config/')
        file_name = 'default.conf'
        config_data = ''
        if os.path.isfile(file_location + file_name):
            with open(get_path(file_location + file_name), "r") as f:
                config_data = f.read()
            # config_data = send_from_directory(file_location, file_name)
            # print_info("Default config loaded")

        return self.render_template(
            "virtual.html",
            title="Virtual Model",
            page_caption="Virtual model",
            page_icon="fa-smile-o",
            modules=Robot.modules,
            config=config_data)

    def show_errormessage(self, error):
        print_error(error)
        # return redirect("/")
        return ""

    def inject_opsoro_vars(self):
        opsoro = {"robot_name": Preferences.get("general", "robot_name",
                                                self.robotName)}
        return dict(opsoro=opsoro)
