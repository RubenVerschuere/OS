import math
import cmath
import time

from opsoro.console_msg import *
from opsoro.expression import Expression
from opsoro.hardware import Hardware
# from opsoro.stoppable_thread import StoppableThread

from flask import Blueprint, render_template, request

constrain = lambda n, minn, maxn: max(min(maxn, n), minn)

config = {"full_name": "Circumplex", "icon": "fa-meh-o", 'color': '#15e678'}


def setup_pages(opsoroapp):
    circumplex_bp = Blueprint(
        config['full_name'].lower(),
        __name__,
        template_folder="templates",
        static_folder="static")

    @circumplex_bp.route("/")
    @opsoroapp.app_view
    def index():
        data = {}
        return opsoroapp.render_template(config['full_name'].lower() + ".html",
                                         **data)

    opsoroapp.register_app_blueprint(circumplex_bp)


def setup(opsoroapp):
    pass


def start(opsoroapp):
    pass


def stop(opsoroapp):
    pass
