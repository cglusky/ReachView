#!venv/bin/python
from gevent import monkey
monkey.patch_all()

import time
import json
from RtkController import RtkController
from ConfigManager import ConfigManager
from port import changeBaudrateTo230400

from threading import Thread
from flask import Flask, render_template, session, request
from flask.ext.socketio import SocketIO, emit, disconnect

app = Flask(__name__)
app.template_folder = "."
app.debug = False
app.config["SECRET_KEY"] = "secret!"

socketio = SocketIO(app)
server_not_interrupted = 1

rtk_location = "/home/reach/RTKLIB/app/rtkrcv/gcc"

# configure Ublox for 230400 baudrate!
changeBaudrateTo230400()

# prepare RtkController, run RTKLIB
print("prepare rtk")
rtkc = RtkController(rtk_location)
rtkc.start("reach_rover_default.conf")

# prepare ConfigManager
conm = ConfigManager(socketio, rtk_location[:-3])

satellite_thread = None
coordinate_thread = None

def broadcastSatellites():
    count = 0
    sat_number = 10
    json_data = {}

    while server_not_interrupted:

        # update satellite levels
        rtkc.getObs()

        # add new obs data to the message
        json_data.update(rtkc.obs)

        if count % 10 == 0:
            print("Sending sat levels:\n" + str(json_data))

        socketio.emit("satellite broadcast", json_data, namespace = "/test")
        count += 1
        time.sleep(1)

def broadcastCoordinates():
    count = 0
    json_data = {}

    while server_not_interrupted:

        # update RTKLIB status
        rtkc.getStatus()

        json_data.update(rtkc.info)

        if count % 10 == 0:
            print("Sending RTKLIB status select information:\n" + str(json_data))

        socketio.emit("coordinate broadcast", json_data, namespace = "/test")
        count += 1
        time.sleep(1)

@app.route("/")
def index():
    global satellite_thread
    global coordinate_thread

    if satellite_thread is None:
        satellite_thread = Thread(target = broadcastSatellites)
        satellite_thread.start()

    if coordinate_thread is None:
        coordinate_thread = Thread(target = broadcastCoordinates)
        coordinate_thread.start()

    return render_template("index.html")

@socketio.on("connect", namespace="/test")
def test_connect():
    emit("my response", {"data": "Connected", "count": 0})
    print("Browser client connected")

@socketio.on("disconnect", namespace="/test")
def test_disconnect():
    print("Browser client disconnected")

@socketio.on("read config", namespace="/test")
def readCurrentConfig():
    print("Got signal to read the current config")

    conm.readConfig(conm.default_base_config)
    emit("current config", conm.buff_dict, namespace="/test")

@socketio.on("read default base config", namespace="/test")
def readDefaultBaseConfig():
    print("Got signal to read the default base config")

@socketio.on("temp config modified", namespace="/test")
def writeConfig(json):
    print("Received temp config to write!!!")
    print(str(json))
    conm.writeConfig("temp.conf", json)
    print("reloading config result: " + str(rtkc.loadConfig("../temp.conf")))

# @socketio.on("my event", namespace="/test")
# def printEvent():
#     print("Connected socketio message received")

if __name__ == "__main__":
    try:
        socketio.run(app, host = "0.0.0.0", port = 5000)
    except KeyboardInterrupt:
        print("Server interrupted by user!!")
        server_not_interrupted = 0

