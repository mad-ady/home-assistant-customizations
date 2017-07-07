#!/usr/bin/python
import paho.mqtt.client as mqtt
import syslog
import time
from subprocess import call
import wiringpi2 as wpi
import yaml
import sys

#Prerequisites:
# * pip: sudo apt-get install python-pip 
# * wiringPi: http://odroid.com/dokuwiki/doku.php?id=en:c1_tinkering#python_example
# * paho-mqtt: pip install paho-mqtt
# * python-yaml: sudo apt-get install python-yaml

#Configuration file goes in /etc/blind-cover-mqtt-agent.yaml and should contain your mqtt broker details

#For startup copy blind-cover-mqtt-agent.service to /etc/systemd/system/
#Startup is done via systemd with
# sudo systemctl enable blind-cover-mqtt-agent
# sudo systemctl start blind-cover-mqtt-agent

conf=[]
with open("/etc/blind-cover-mqtt-agent.yaml", 'r') as stream:
    try:
       conf = yaml.load(stream)
    except yaml.YAMLError as exc:
        print(exc)
        print("Unable to parse configuration file /etc/blind-cover-mqtt-agent.yaml")
        sys.exit(1)

mqttServer = conf['mqttServer']
mqttPort = conf['mqttPort']
mqttTopics = ['ha/blind_cover/set' ]
mqttUser = conf['mqttUser']
mqttPass = conf['mqttPass']

#initialize wiringPi
wpi.wiringPiSetup()

coverModePin = 4 #GPIO 104 on Odroid C1, Pin 16
coverDirectionPin = 5 #GPIO #102 on Odroid C1, Pin 18

#define some constants
coverModeAutomatic = 0  #the cover is controlled by the Odroid
coverModeManual = 1 #the cover is controlled by the physical switch

coverDirectionUp = 1 #the cover should raise
coverDirectionDown = 0 #the cover should lower

coverOperationTime = 17 #maximum time in seconds for the motor to raise or lower the cover

#initialize the pins - output, with manual control by default
wpi.pinMode(coverModePin, 1)
wpi.digitalWrite(coverModePin, coverModeManual)
print("Set coverModePin to manual mode")
wpi.pinMode(coverDirectionPin, 1)
wpi.digitalWrite(coverDirectionPin, coverDirectionUp) #has no effect as long as the cover is in manual mode
print("Set coverDirectionPin to up")

currentState = { 'power': False, 'jet': False, 'ionizer': False, 'swing': False, 'temperature': 22, 'fan': 'low' }

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    for topic in mqttTopics:
        (result, mid) = client.subscribe(topic)
        
        print("Got subscription result for "+topic+":"+str(result))

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print("Received command:"+msg.topic+" "+str(msg.payload))

    #listen to requests, process themm
    #set the replies over mqtt

    if msg.topic == 'ha/blind_cover/set':
        if msg.payload == 'OPEN' or msg.payload == 'CLOSE' or msg.payload == 'STOP':
            processCommand(msg.payload)

def processCommand(state):
    print("Setting cover "+str(state))
    #should implement threading to be able to process commands before the blind closes/opens
    #TODO
    if state == 'OPEN':
        #we need to open
        #set direction first. Open means up
        wpi.digitalWrite(coverDirectionPin, coverDirectionUp)
        #set the cover to be controlled by the Odroid
        wpi.digitalWrite(coverModePin, coverModeAutomatic)
        print("Opening blind")
        #tell the caller we're opening
        client.publish('ha/blind_cover/get', "opening", 0, False)
        #now we wait for the motor to do its thing
        time.sleep(coverOperationTime)

        #we can now say that the cover is open
        client.publish('ha/blind_cover/get', "open", 0, False)
        
        #we need to put the cover back in manual mode for the plysical switch to work
        wpi.digitalWrite(coverModePin, coverModeManual)
        print("Switching back to manual mode")

    elif state == 'CLOSE':
        #we need to close
        #set direction first. Close means down
        wpi.digitalWrite(coverDirectionPin, coverDirectionDown)
        #set the cover to be controlled by the Odroid
        wpi.digitalWrite(coverModePin, coverModeAutomatic)
        print("Closing blind")
        #tell the caller we're opening
        client.publish('ha/blind_cover/get', "closing", 0, False)
        #now we wait for the motor to do its thing
        time.sleep(coverOperationTime)

        #we can now say that the cover is open
        client.publish('ha/blind_cover/get', "closed", 0, False)
        
        #we need to put the cover back in manual mode for the plysical switch to work
        wpi.digitalWrite(coverModePin, coverModeManual)
        print("Switching back to manual mode")

    else:
        #STOP is not really processed at this point
	pass

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

syslog.syslog('Starting blind-cover-mqtt-agent.py')
client.username_pw_set(username=mqttUser, password=mqttPass)

client.connect(mqttServer, mqttPort, 60)
client.loop_forever()
