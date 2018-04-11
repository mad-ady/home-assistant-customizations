#!/usr/bin/python
import paho.mqtt.client as mqtt
import wiringpi2 as wpi
import yaml
import sys
import threading
import time

# Prerequisites:
# * pip: sudo apt-get install python-pip 
# * wiringPi: http://odroid.com/dokuwiki/doku.php?id=en:c2_tinkering#python_example
# * paho-mqtt: pip install paho-mqtt
# * python-yaml: sudo apt-get install python-yaml

# Configuration file goes in /etc/pir-mqtt-agent.yaml and should contain your mqtt broker details

# For startup copy pir-mqtt-agent.service to /etc/systemd/system/
# Startup is done via systemd with
# sudo systemctl enable pir-mqtt-agent
# sudo systemctl start pir-mqtt-agent


""" Parse and load the configuration file to get MQTT credentials """

conf={}

def parseConfig():
    global conf
    with open("/etc/pir-mqtt-agent.yaml", 'r') as stream:
        try:
           conf = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            print("Unable to parse configuration file /etc/pir-mqtt-agent.yaml")
            sys.exit(1)

def processIRQ():
    global activeTimer
    print("Servicing IRQ (movement detected)")
    sys.stdout.flush()
    # if there's an active timer, extend it
    if activeTimer:
        print("Movement is persisting")
        activeTimer.cancel()
    else:
        # if no active timer, create one and send a MOVEMENT message
        print("New movement detected!")
        client.publish(conf['mqttTopic'], "MOVEMENT", 0, False)
    activeTimer = threading.Timer(int(conf['persistence']), stopMotion)
    activeTimer.start()
    sys.stdout.flush()
    return True

def stopMotion():
    global activeTimer
    client.publish(conf['mqttTopic'], "QUIET", 0, False)
    print("All is quiet again")
    activeTimer = None
    sys.stdout.flush()

#initialize wiringPi
wpi.wiringPiSetup()


parseConfig()
activeTimer = None #reference to an active timer

#initialize the pin - input
wpi.pinMode(conf["pin"], 0)
print("Set pin "+str(conf["pin"])+" as input")
sys.stdout.flush()

# wake up on interrupts on this pin on the rising edge
wpi.wiringPiISR(conf["pin"], 2, processIRQ)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    sys.stdout.flush()

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    (result, mid) = client.subscribe(conf['mqttTopic'])
        
    print("Got subscription result for "+conf['mqttTopic']+":"+str(result))
    sys.stdout.flush()


client = mqtt.Client()
#client.on_connect = on_connect
#client.on_message = on_message

print("Starting pir-mqtt-agent.py")
if conf['mqttUser'] and conf['mqttPass']:
    client.username_pw_set(username=conf['mqttUser'], password=conf['mqttPass'])

client.connect(conf['mqttServer'], conf['mqttPort'], 60)
print("Connected to server...")
sys.stdout.flush()
client.loop_forever()
