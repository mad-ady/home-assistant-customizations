#!/usr/bin/python
import paho.mqtt.client as mqtt
import re
import time
import sys
import yaml

# Prerequisites:
# * pip: sudo apt-get install python-pip
# * paho-mqtt: pip install paho-mqtt
# * python-yaml: sudo apt-get install python-yaml

# Configuration file goes in /etc/temperature-mqtt-agent.yaml and should contain your mqtt broker details

# For startup copy temperature-mqtt-agent.service to /etc/systemd/system/
# Startup is done via systemd with
#  sudo systemctl enable temperature-mqtt-agent
#  sudo systemctl start temperature-mqtt-agent

#filename = '/sys/devices/w1_bus_master1/28-0516a1db5dff/w1_slave'
valid = False
oldValue = 0

""" Parse and load the configuration file to get MQTT credentials """

conf = {}


def parseConfig():
    global conf
    with open("/etc/temperature-mqtt-agent.yaml", 'r') as stream:
        try:
            conf = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            print("Unable to parse configuration file /etc/temperature-mqtt-agent.yaml")
            sys.exit(1)


""" Read temperature from sysfs and return it as a string """


def readTemperature():
    valid = False
    with open(filename) as f:
        for line in f:
            if re.search('crc=.*YES', line):
                # the CRC is valid. Continue processing
                valid = True
                continue
            if valid and re.search('t=[0-9]+', line):
                # extract the temperature value
                temperature = re.search('t=([0-9]+)', line)
                # convert to degrees celsius and keep 1 digit of accuracy
                output = "%.1f" % (float(temperature.group(1)) / 1000.0)
                # ignore extreme temperatures
                if float(output) < -10.0 or float(output) > 45.0:
                    print("Read %f" % float(output))
                    return None

#                print("Temperature is "+str(output))
                return output


""" Initialize the MQTT object and connect to the server """
parseConfig()
filename='/sys/devices/w1_bus_master1/'+conf['sensor']+'/w1_slave'
client = mqtt.Client()
if conf['mqttUser'] and conf['mqttPass']:
    client.username_pw_set(username=conf['mqttUser'], password=conf['mqttPass'])
client.connect(conf['mqttServer'], conf['mqttPort'], 60)
client.loop_start()

""" Do an infinite loop reading temperatures and sending them via MQTT """

while (True):
    newValue = readTemperature()
    if newValue is None:
        print("Ignoring incorrect temperature reading")
        continue
    # publish the output value via MQTT if the value has changed
    if oldValue != newValue:
        print("Temperature changed from %.1f to %.1f" % (float(oldValue), float(newValue)))
        sys.stdout.flush()
        client.publish(conf['mqttTopic'], newValue, 0, conf['mqttPersistent'])
        oldValue = newValue
    # sleep for a while
#    print("Sleeping...")
    time.sleep(conf['sleep'])
