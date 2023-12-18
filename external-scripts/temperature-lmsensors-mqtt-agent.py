#!/usr/bin/python3
import paho.mqtt.client as mqtt
import re
import time
import sys
import yaml
import sensors

# Prerequisites:
# * pip: sudo apt-get install python-pip3
# * paho-mqtt: pip3 install paho-mqtt
# * pysensors: pip3 install pysensors
# * python-yaml: sudo apt-get install python3-yaml

# Configuration file goes in /etc/temperature-lmsensors-mqtt-agent.yaml and should contain your mqtt broker details

# For startup copy temperature-lmsensors-mqtt-agent.service to /etc/systemd/system/
# Startup is done via systemd with
#  sudo systemctl enable temperature-lmsensors-mqtt-agent
#  sudo systemctl start temperature-lmsensors-mqtt-agent

oldValue = {}

""" Parse and load the configuration file to get MQTT credentials """

conf = {}

sensors.init()

def parseConfig():
    global conf
    with open("/etc/temperature-lmsensors-mqtt-agent.yaml", 'r') as stream:
        try:
            conf = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            print("Unable to parse configuration file /etc/temperature-lmsensors-mqtt-agent.yaml")
            sys.exit(1)


""" Read temperature from sysfs and return it as a string """


def readSensor(chipName, sensorName):
    try:
        for chip in sensors.iter_detected_chips():
            #print ("%s" % (chip,))
            #print (f"Looking for {chipName}")
            if str(chip) == chipName:
                #print('%s at %s' % (chip, chip.adapter_name))
                for feature in chip:
                    if feature.label == sensorName:
                        # sensor values are rounded to the nearest 10th to prevent jitter
                        return round(feature.get_value(), 1)
    except Exception as err:
        print("Problem reading sensors")


""" Initialize the MQTT object and connect to the server """
parseConfig()
client = mqtt.Client()
if conf['mqttUser'] and conf['mqttPass']:
    client.username_pw_set(username=conf['mqttUser'], password=conf['mqttPass'])
client.connect(conf['mqttServer'], conf['mqttPort'], 60)
client.loop_start()

""" Do an infinite loop reading temperatures and sending them via MQTT """

while (True):
    for sensor in conf['sensors']:
        newValue = readSensor(sensor['chip'], sensor['sensor'])
        if newValue is None:
            print(f"Ignoring incorrect sensor reading for sensor['name'] - sensor['chip']: sensor['sensor']")
            time.sleep(conf['sleep'])
            continue
        # publish the output value via MQTT if the value has changed
        if sensor['chip']+"/"+sensor['sensor'] not in oldValue:
            oldValue[sensor['chip']+"/"+sensor['sensor']] = 0
        if oldValue[sensor['chip']+"/"+sensor['sensor']] != newValue:
            print(f"Sensor {sensor['chip']}/{sensor['sensor']} changed from %.5f to %.5f" % (float(oldValue[sensor['chip']+"/"+sensor['sensor']]), float(newValue)))
        sys.stdout.flush()
        client.publish(sensor['mqttTopic'], newValue, 0, conf['mqttPersistent'])
        oldValue[sensor['chip']+"/"+sensor['sensor']] = newValue
    
    # sleep for a while
#    print("Sleeping...")
    time.sleep(conf['sleep'])
