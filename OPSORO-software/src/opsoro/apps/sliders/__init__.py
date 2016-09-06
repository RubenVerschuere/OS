from __future__ import with_statement

from opsoro.console_msg import *
from opsoro.expression import Expression
from opsoro.hardware import Hardware

from flask import Blueprint, render_template, request, redirect, url_for, flash

constrain = lambda n, minn, maxn: max(min(maxn, n), minn)

config = {"full_name": "Sliders", "icon": "fa-sliders"}

clientconn = None
# dof_positions = {}

import os
from functools import partial
get_path = partial(os.path.join, os.path.abspath(os.path.dirname(__file__)))

import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


def setup_pages(opsoroapp):
    sliders_bp = Blueprint(
        "sliders",
        __name__,
        template_folder="templates",
        static_folder="static")

    global clientconn

    @sliders_bp.route("/")
    @opsoroapp.app_view
    def index():
        data = {
            # "dofs":				[]
        }

        # global dof_positions
        #
        # for servo in Expression.servos:
        # 	if servo.pin >= 0 and servo.pin < 16:
        # 		# Pin is valid, add to the page
        # 		data["dofs"].append({
        # 			"name":		servo.dofname,
        # 			"pin":		servo.pin,
        # 			"min":		servo.min_range,
        # 			"mid":		servo.mid_pos,
        # 			"max":		servo.max_range,
        # 			"current":	dof_positions[servo.dofname]
        # 		})

        with open(get_path("../../config/modules_configs/ono.yaml")) as f:
            data["config"] = yaml.load(f, Loader=Loader)

        return opsoroapp.render_template("sliders.html", **data)

    @opsoroapp.app_socket_connected
    def s_connected(conn):
        global clientconn
        clientconn = conn

    @opsoroapp.app_socket_disconnected
    def s_disconnected(conn):
        global clientconn
        clientconn = None

    @opsoroapp.app_socket_message("servosEnable")
    def s_servosenable(conn, data):
        print_info("Servos enabled")
        with Hardware.lock:
            Hardware.servo_enable()

    @opsoroapp.app_socket_message("servosDisable")
    def s_servosdisable(conn, data):
        print_info("Servos disabled")
        with Hardware.lock:
            Hardware.servo_disable()

    @opsoroapp.app_socket_message("setDofPos")
    def s_setdofpos(conn, data):
        modulename = str(data.pop("module_name", None))
        dofname = str(data.pop("dof_name", None))
        pos = float(data.pop("pos", 0.0))

        if modulename is None or dofname is None:
            conn.send_data("error", {"message": "No valid dof name given."})

            # global dof_positions
            # if dofname not in dof_positions:
            # conn.send_data("error", {"message": "Unknown DOF name."})
            # else:
            pos = constrain(pos, -1.0, 1.0)
            dof_positions[dofname] = pos

            with Expression.lock:
                Expression.update()

    opsoroapp.register_app_blueprint(sliders_bp)


def overlay_fn(dof_pos, dof):
    # Overwrite all DOFs to use the ones from the slider app
    global dof_positions

    if dof.name in dof_positions:
        return dof_positions[dof.name]
    else:
        return dof_pos


def setup(opsoroapp):
    pass


def start(opsoroapp):
    global dof_positions
    dof_positions = {}

    # Apply overlay function
    for servo in Expression.servos:
        if servo.pin < 0 or servo.pin > 15:
            continue  # Skip invalid pins
        dof_positions[servo.dofname] = 0.0
        if servo.dofname in Expression.dofs:
            Expression.dofs[servo.dofname].overlays.append(overlay_fn)

    # Turn servo power off, init servos, update expression
    with Hardware.lock:
        Hardware.servo_disable()
        Hardware.servo_init()
        Hardware.servo_neutral()

    with Expression.lock:
        Expression.update()


def stop(opsoroapp):
    with Hardware.lock:
        Hardware.servo_disable()

    # Remove all overlay functions
    for dofname, dof in Expression.dofs.iteritems():
        if overlay_fn in dof.overlays:
            dof.overlays.remove(overlay_fn)
