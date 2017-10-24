#!/usr/bin/python
import paho.mqtt.client as mqtt
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


"""
Parse and load the configuration file to get MQTT credentials
"""

conf={}
def parseConfig():
    global conf
    with open("/etc/ir-ac-mqtt-agent.yaml", 'r') as stream:
        try:
           conf = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            print("Unable to parse configuration file /etc/ir-ac-mqtt-agent.yaml")
            sys.exit(1)


"""
Define a state object to preserve an internal AC state so that we can have more complex decisions later
"""

currentState = { 'power': False, 'jet': False, 'ionizer': False, 'swing': False, 'temperature': 22, 'fan': 'low' }

def on_connect(client, userdata, flags, rc):
    """
    The callback for when the client receives a CONNACK response from the MQTT server.
    """
    print("Connected with result code "+str(rc))
    sys.stdout.flush()

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    for topic in conf['mqttTopics']:
        (result, mid) = client.subscribe(topic)
        
        print("Got subscription result for "+topic+":"+str(result))
        sys.stdout.flush()

def on_message(client, userdata, msg):
    """
    The callback for when a PUBLISH message is received from the MQTT server.
    """
    print("Received command:"+msg.topic+" "+str(msg.payload))
    sys.stdout.flush()

    """
    Handle AC power on/off
    """
    if msg.topic == 'ha/lg_ac/power/set':
        if msg.payload == 'ON' or msg.payload == 'OFF':
            processCommand('power', msg.payload)
            if msg.payload == 'OFF':
                #on power off, disable jet, ionizer
                for item in ['jet', 'ionizer']:
                    currentState[item] = False
                    client.publish('ha/lg_ac/'+item+'/get', 'OFF', 0, False)
            else:
                #power on sets temperature to 21C, fan to high
                currentState['temperature'] = 21
                client.publish('ha/lg_ac/temperature/get', '21', 0, False)
                currentState['fan'] = 'high'
                client.publish('ha/lg_ac/fan/get', 'high', 0, False)


    """
    Handle the pressing of the Jet (or Turbo) button
    """
    if msg.topic == 'ha/lg_ac/jet/set':
        if currentState['power'] == True:
            if msg.payload == 'ON' or msg.payload == 'OFF':
                newstate = True if msg.payload == 'ON' else False
                if currentState['jet'] != newstate:
                    #execute the Jet command only if we need to
                    processCommand('jet', msg.payload)
                    if msg.payload == 'ON':
                        #jet ON means temperature = 18 and fan = high
                        currentState['temperature'] = 18
                        client.publish('ha/lg_ac/temperature/get', 18, 0, False)
                        currentState['fan'] = 'high'
                        client.publish('ha/lg_ac/fan/get', 'high', 0, False)
        #don't set the jet if the AC is off

    """
    Handle the pressing of the Ionizer button
    """
    if msg.topic == 'ha/lg_ac/ionizer/set':
        if currentState['power'] == True:
            if msg.payload == 'ON' or msg.payload == 'OFF':
                processCommand('ionizer', msg.payload)
        #don't set the ionizer if the AC is off

    """
    Handle the pressing of the Swing button
    """
    if msg.topic == 'ha/lg_ac/swing/set':
        if currentState['power'] == True:
            if msg.payload == 'ON' or msg.payload == 'OFF':
                processCommand('swing', msg.payload)
        #don't set the swing if the AC is off

    """
    Handle the changing of the temperature
    """
    if msg.topic == 'ha/lg_ac/temperature/set':
        if currentState['power'] == True:
            #The payload should be a temperature
            temperature = int(float(msg.payload))
            if temperature >= 18 and temperature <= 30:
                #if the temperature is the same as the internal state, don't set it. 
                #it avoids an annoying extra beep when setting Jet=ON
                if temperature != currentState['temperature']:
                    processCommand('temperature', temperature)
                    #when temperature changes, Jet mode turns off
                    if currentState['jet']:
                        currentState['jet'] = False
                        client.publish('ha/lg_ac/jet/get', 'OFF', 0, False)

    """
    Handle changing fan speed
    """
    if msg.topic == 'ha/lg_ac/fan/set':
        if currentState['power'] == True:
            fan = str(msg.payload).lower()
            if fan == 'low' or fan == 'med' or fan == 'high' or fan == 'cycle':
                #if the fan is the same as the current state, don't set it
                if fan != currentState['fan']:
                    processCommand('fan', fan)
                    #when fan speed changes, Jet mode turns off
                    if currentState['jet']:
                        currentState['jet'] = False
                        client.publish('ha/lg_ac/jet/get', 'OFF', 0, False)

def processCommand(item, state):
    """
    Call the sendir function, update internal state and publish the state change as an MQTT message
    """
    print("Setting "+item+" "+str(state))
    sys.stdout.flush()
    success = sendir(item+"-"+str(state).lower())
    if success:
        print("Injected IR command successfully. Updating state")
        sys.stdout.flush()
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
        #IR didn't work. Don't change the internal state, but publish it for feedback (e.g. the slider moves back)
        print("IR injection failed!")
        sys.stdout.flush()
        client.publish('ha/lg_ac/'+item+'/get', state, 0, False)

# Actually send IR codes
# Returns True if there was no problem reported by lirc, False otherwise
def sendir(code):
    """
    Send IR codes with the help of irsend (lirc). The code names are derived from the item name and lowercase state.
    E.g.: temperature-22, fan-high, power-on, jet-off.
    Returns True on success and False otherwise
    """
    success = False
    
    #due to a bug in lirc/ir module,  we need to restart lirc before/after every code
    ret = call(['/usr/sbin/service', 'lirc', 'restart'])
    #sometimes lirc fails to restart if restarted too fast (e.g. on multiple commands)
    if ret:
        #try again after a delay
        time.sleep(5)
        ret = call(['/usr/sbin/service', 'lirc', 'restart'])

    print('Sending IR code '+code)
    sys.stdout.flush()
    ret = call(['/usr/bin/irsend', 'SEND_ONCE', 'lgirplus.conf', code])
    #ret is the program return code - 0 for success.
    if ret:
        #there was a problem sending the command.
        success = False
    else:
        success = True

    return success

"""
Initialize the MQTT object and connect to the server, looping forever waiting for messages
"""
parseConfig()

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print ('Starting ir-ac-mqtt-agent.py')
sys.stdout.flush()
if conf['mqttUser'] and conf['mqttPass']:
    client.username_pw_set(username=conf['mqttUser'], password=conf['mqttPass'])

client.connect(conf['mqttServer'], conf['mqttPort'], 60)
client.loop_forever()
