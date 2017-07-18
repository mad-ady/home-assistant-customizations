#!/usr/bin/python
import paho.mqtt.client as mqtt
import syslog
import time
from subprocess import call
import yaml
import sys

#Prerequisites:
# * pip: sudo apt-get install python-pip 
# * lirc + irsend configured
# * paho-mqtt: pip install paho-mqtt
# * python-yaml: sudo apt-get install python-yaml

#Configuration file goes in /etc/ir-ac-mqtt-agent.yaml and should contain your mqtt broker details

#For startup copy ir-ac-mqtt-agent.service to /etc/systemd/system/
#Startup is done via systemd with
# sudo systemctl enable ir-ac-mqtt-agent
# sudo systemctl start ir-ac-mqtt-agent


conf=[]
with open("/etc/ir-ac-mqtt-agent.yaml", 'r') as stream:
    try:
       conf = yaml.load(stream)
    except yaml.YAMLError as exc:
       print(exc)
       print("Unable to parse configuration file /etc/ir-ac-mqtt-agent.yaml")
       sys.exit(1)

mqttServer = conf['mqttServer']
mqttPort = conf['mqttPort']
mqttTopics = ['ha/lg_ac/power/set', 'ha/lg_ac/jet/set', 'ha/lg_ac/ionizer/set', 'ha/lg_ac/swing/set', 'ha/lg_ac/temperature/set', 'ha/lg_ac/fan/set' ]
mqttUser = conf['mqttUser']
mqttPass = conf['mqttPass']

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

    #listen to requests, process them and call the IR message
    #set the replies over mqtt

    if msg.topic == 'ha/lg_ac/power/set':
        if msg.payload == 'ON' or msg.payload == 'OFF':
            processCommand('power', msg.payload)
            if msg.payload == 'OFF':
                #on power off, disable jet, ionizer and swing
                for item in ['jet', 'ionizer', 'swing']:
                    currentState[item] = False
                    client.publish('ha/lg_ac/'+item+'/get', 'OFF', 0, False)
    if msg.topic == 'ha/lg_ac/jet/set':
        if currentState['power'] == True:
            if msg.payload == 'ON' or msg.payload == 'OFF':
                processCommand('jet', msg.payload)
                if msg.payload == 'ON':
                    #jet ON means temperature = 18 and fan = high
                    currentState['temperature'] = 18
                    client.publish('ha/lg_ac/temperature/get', 18, 0, False)
                    currentState['fan'] = 'high'
                    client.publish('ha/lg_ac/fan/get', 'high', 0, False)
        #don't set the jet if the AC is off
    if msg.topic == 'ha/lg_ac/ionizer/set':
        if currentState['power'] == True:
            if msg.payload == 'ON' or msg.payload == 'OFF':
                processCommand('ionizer', msg.payload)
        #don't set the ionizer if the AC is off
    if msg.topic == 'ha/lg_ac/swing/set':
        if currentState['power'] == True:
            if msg.payload == 'ON' or msg.payload == 'OFF':
                processCommand('swing', msg.payload)
        #don't set the swing if the AC is off
    if msg.topic == 'ha/lg_ac/temperature/set':
        if currentState['power'] == True:
            #The payload should be a temperature
            temperature = int(float(msg.payload))
            if temperature >= 18 and temperature <= 30:
                #if the temperature is the same as the internal state, don't set it. 
                #it avoids an annoying extra beep when setting Jet=ON
                if temperature != currentState['temperature']:
                    processCommand('temperature', temperature)
    if msg.topic == 'ha/lg_ac/fan/set':
        if currentState['power'] == True:
            fan = str(msg.payload).lower()
            if fan == 'low' or fan == 'med' or fan == 'high' or fan == 'cycle':
                #if the fan is the same as the current state, don't set it
                if fan != currentState['fan']:
                    processCommand('fan', fan)


def processCommand(item, state):
    print("Setting "+item+" "+str(state))
    success = sendir(item+"-"+str(state).lower())
    if success:
        print("Injected IR command successfully. Updating state")
        if isinstance( state, int ):
            #save numeric states as they are
            currentState[item] = state
        elif state == 'low' or state == 'med' or state == 'high' or state == 'cycle':
            #save these states as they are
            currentState[item] = state
        else:
            currentState[item]= True if state == 'ON' else False
        client.publish('ha/lg_ac/'+item+'/get', state, 0, False)
    else:
        #IR didn't work. Don't change the internal state, but publish it for feedback
        print("IR injection failed!")
        client.publish('ha/lg_ac/'+item+'/get', state, 0, False)


# Actually send IR codes
# Returns True if there was no problem reported by lirc, False otherwise
def sendir(code):
    success = False
    syslog.syslog('Sending IR code '+code)
    ret = call(['/usr/bin/irsend', 'SEND_ONCE', 'lgirplus.conf', code])
    if ret:
        #there was a problem sending the command.
        success = False
    else:
        success = True

    #due to a bug in lirc/ir module,  we need to restart lirc after every code
    ret = call(['/usr/sbin/service', 'lirc', 'restart'])
    #sometimes lirc fails to restart if restarted too fast (e.g. on multiple commands)
    if ret:
        #try again after a delay
        time.sleep(3)
        ret = call(['/usr/sbin/service', 'lirc', 'restart'])

    return success

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

syslog.syslog('Starting ir-ac-mqtt-agent.py')
client.username_pw_set(username=mqttUser, password=mqttPass)

client.connect(mqttServer, mqttPort, 60)
client.loop_forever()
