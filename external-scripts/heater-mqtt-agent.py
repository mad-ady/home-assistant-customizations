#!/usr/bin/python
from __future__ import print_function  # Only needed for Python 2
import paho.mqtt.client as mqtt
import sys
import yaml
import os

# Prerequisites:
# * pip: sudo apt-get install python-pip
# * paho-mqtt: pip install paho-mqtt
# * python-yaml: sudo apt-get install python-yaml

# Configuration file goes in /etc/heater-mqtt-agent.yaml and should contain your mqtt broker details

# For startup copy heater-mqtt-agent.service to /etc/systemd/system/
# Startup is done via systemd with
#  sudo systemctl enable heater-mqtt-agent
#  sudo systemctl start heater-mqtt-agent

""" Parse and load the configuration file to get MQTT credentials """

conf = {}
heaterRelay = 131  # GPIO 131 on Odroid C2, J7 connector, pin 6.
heaterOff = 1
heaterOn = 0

def parseConfig():
    global conf
    with open("/etc/heater-mqtt-agent.yaml", 'r') as stream:
        try:
            conf = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            print("Unable to parse configuration file /etc/heater-mqtt-agent.yaml")
            sys.exit(1)

# Export the pin and set direction
def pinMode(pinNumber, value):
    if not os.path.isdir("/sys/class/gpio/gpio" + str(pinNumber)):
        with open("/sys/class/gpio/export", 'w') as export:
            print(pinNumber, file=export)
    with open("/sys/class/gpio/gpio" + str(pinNumber) + "/direction", 'w') as direction:
        print(value, file=direction)

# Write a 1 or a 0 to the pin
def digitalWrite(pinNumber, value):
    with open("/sys/class/gpio/gpio" + str(pinNumber) + "/value", 'w') as val:
        print(value, file=val)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    (result, mid) = client.subscribe(conf['command_topic'])
    print("Got subscription result for " + conf['command_topic'] + ":" + str(result))


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print("Received command:" + msg.topic + " " + str(msg.payload))

    # listen to requests, process themm
    # set the replies over mqtt

    if msg.topic == conf['command_topic']:
        if msg.payload == 'ON':
            # turn on the heater
            digitalWrite(heaterRelay, heaterOn)
            print("Turned heater ON")
            sys.stdout.flush()
            # we can now say that the heater is on
            client.publish(conf['state_topic'], "ON", 0, conf['mqttPersistent'])

        if msg.payload == 'OFF':
            # turn off the heater
            digitalWrite(heaterRelay, heaterOff)
            print("Turned heater OFF")
            # we can now say that the heater is off
            client.publish(conf['state_topic'], "OFF", 0, conf['mqttPersistent'])

#initialize the relay pin
pinMode(heaterRelay, 'out') # output mode
digitalWrite(heaterRelay, heaterOff) # set the heater to off by default
print("Set GPIO "+str(heaterRelay)+" as out")
print("Set heater OFF by default")
sys.stdout.flush()
""" Initialize the MQTT object and connect to the server """
parseConfig()
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
if conf['mqttUser'] and conf['mqttPass']:
    client.username_pw_set(username=conf['mqttUser'], password=conf['mqttPass'])
client.connect(conf['mqttServer'], conf['mqttPort'], 60)
#listen for messages and call on_message when needed
print("Listen to MQTT messages...")
sys.stdout.flush()
client.loop_forever()
