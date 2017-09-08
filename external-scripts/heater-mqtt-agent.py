#!/usr/bin/python
import paho.mqtt.client as mqtt
import re
import time
import sys
import yaml
import wiringpi2 as wpi

# Prerequisites:
# * pip: sudo apt-get install python-pip
# * paho-mqtt: pip install paho-mqtt
# * wiringPi: http://odroid.com/dokuwiki/doku.php?id=en:c1_tinkering#python_example
# * python-yaml: sudo apt-get install python-yaml

# Configuration file goes in /etc/heater-mqtt-agent.yaml and should contain your mqtt broker details

# For startup copy heater-mqtt-agent.service to /etc/systemd/system/
# Startup is done via systemd with
#  sudo systemctl enable heater-mqtt-agent
#  sudo systemctl start heater-mqtt-agent

""" Parse and load the configuration file to get MQTT credentials """

conf = {}

def parseConfig():
    global conf
    with open("/etc/heater-mqtt-agent.yaml", 'r') as stream:
        try:
            conf = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            print("Unable to parse configuration file /etc/heater-mqtt-agent.yaml")
            sys.exit(1)

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
            wpi.digitalWrite(heaterRelay, heaterOn)
            # we can now say that the heater is on
            client.publish(conf['state_topic'], "ON", 0, False)

        if msg.payload == 'OFF':
            # turn off the heater
            wpi.digitalWrite(heaterRelay, heaterOff)
            # we can now say that the heater is off
            client.publish(conf['state_topic'], "OFF", 0, False)

# initialize wiringPi to use /sys/class/gpio numbers
wpi.wiringPiSetupSys()

#initialize the relay pin
heaterRelay = 131  # GPIO 131 on Odroid C2, J7 connector, pin 6.
heaterOff = 0
heaterOn = 1

wpi.pinMode(heaterRelay, 1) # output mode
wpi.digitalWrite(heaterRelay, heaterOff) # set the heater to off by default

""" Initialize the MQTT object and connect to the server """
parseConfig()
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
if conf['mqttUser'] and conf['mqttPass']:
    client.username_pw_set(username=conf['mqttUser'], password=conf['mqttPass'])
client.connect(conf['mqttServer'], conf['mqttPort'], 60)
#listen for messages and call on_message when needed
client.loop_forever()
