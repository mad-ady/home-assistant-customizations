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

filename = '/sys/devices/w1_bus_master1/28-05168661eaff/w1_slave'
valid = False
oldValue = 0

"""
Parse and load the configuration file to get MQTT credentials
"""

conf=[]
with open("/etc/temperature-mqtt-agent.yaml", 'r') as stream:
    try:
       conf = yaml.load(stream)
    except yaml.YAMLError as exc:
       print(exc)
       print("Unable to parse configuration file /etc/temperature-mqtt-agent.yaml")
       sys.exit(1)

mqttServer = conf['mqttServer']
mqttPort = conf['mqttPort']
mqttUser = conf['mqttUser']
mqttPass = conf['mqttPass']
mqttTopic = conf['mqttTopic']
mqttPersistent = conf['mqttPersistent']
sleep = conf['sleep']

"""
Initialize the MQTT object and connect to the server
"""

client = mqtt.Client()
if mqttUser and mqttPass:
    client.username_pw_set(username=mqttUser, password=mqttPass)
client.connect(mqttServer, mqttPort, 60)

"""
Do an infinite loop reading temperatures and sending them via MQTT
"""

while(True):
    # execute the command and parse each line of output
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
                # publish the output value via MQTT if the value has changed
                if oldValue != output:
                    print("Temperature changed from %f to %f" % (float(oldValue), float(output)))
                    client.publish(mqttTopic, output, 0, mqttPersistent)
                    oldValue = output
    # sleep for a while
#    print("Sleeping "+str(sleep))
    time.sleep(sleep)
