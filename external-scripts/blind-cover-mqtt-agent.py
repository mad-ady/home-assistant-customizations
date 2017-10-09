#!/usr/bin/python
import paho.mqtt.client as mqtt
import wiringpi2 as wpi
import yaml
import sys
import threading
import time

# Prerequisites:
# * pip: sudo apt-get install python-pip 
# * wiringPi: http://odroid.com/dokuwiki/doku.php?id=en:c1_tinkering#python_example
# * paho-mqtt: pip install paho-mqtt
# * python-yaml: sudo apt-get install python-yaml

# Configuration file goes in /etc/blind-cover-mqtt-agent.yaml and should contain your mqtt broker details

# For startup copy blind-cover-mqtt-agent.service to /etc/systemd/system/
# Startup is done via systemd with
# sudo systemctl enable blind-cover-mqtt-agent
# sudo systemctl start blind-cover-mqtt-agent


""" Parse and load the configuration file to get MQTT credentials """

conf={}

def parseConfig():
    global conf
    with open("/etc/blind-cover-mqtt-agent.yaml", 'r') as stream:
        try:
           conf = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            print("Unable to parse configuration file /etc/blind-cover-mqtt-agent.yaml")
            sys.exit(1)

#initialize wiringPi
wpi.wiringPiSetup()

coverModePin = 4 #GPIO 104 on Odroid C1, Pin 16
coverDirectionPin = 5 #GPIO #102 on Odroid C1, Pin 18

#FAKE GPIOs for offline testing
#coverModePin = 6 #GPIO 104 on Odroid C1, Pin 16
#coverDirectionPin = 10 #GPIO #102 on Odroid C1, Pin 18

#define some constants
coverModeAutomatic = 0  #the cover is controlled by the Odroid
coverModeManual = 1 #the cover is controlled by the physical switch

coverDirectionUp = 1 #the cover should raise
coverDirectionDown = 0 #the cover should lower

coverOperationTime = 17 #maximum time in seconds for the motor to raise or lower the cover from start to finish

activeTimer = None #reference to an active timer
currentposition = 100 # assume the default state of the blinds to be open. 0 is closed
lastDirection = 0 # remeber the direction you're going (up = 1, down = 0)
startTime = 0 #remember when starting the motor

#initialize the pins - output, with manual control by default
wpi.pinMode(coverModePin, 1)
wpi.digitalWrite(coverModePin, coverModeManual)
print("Set coverModePin to manual mode")
sys.stdout.flush()
wpi.pinMode(coverDirectionPin, 1)
wpi.digitalWrite(coverDirectionPin, coverDirectionUp) #has no effect as long as the cover is in manual mode
print("Set coverDirectionPin to up")
sys.stdout.flush()

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    sys.stdout.flush()

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    for topic in conf['mqttTopics']:
        (result, mid) = client.subscribe(topic)
        
        print("Got subscription result for "+topic+":"+str(result))
        sys.stdout.flush()

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print("Received command:"+msg.topic+" "+str(msg.payload))
    sys.stdout.flush()

    #listen to requests, process themm
    #set the replies over mqtt

    if msg.topic == 'ha/blind_cover/set':
        if msg.payload == 'OPEN' or msg.payload == 'CLOSE' or msg.payload == 'STOP':
            processCommand(msg.payload)

    if msg.topic == 'ha/blind_cover/position':
        if int(msg.payload) <= 100 and int(msg.payload) >= 0:
            # see in which direction and for how long we need to run the motor
            (direction, runtime) = position2runtime(msg.payload)
            runMotor(runtime, direction)

def position2runtime(newposition):
    # calculate running time and direction based on position and current position
    if int(newposition) > currentposition:
        # the blind needs to go up
        direction = coverDirectionUp
    else:
        # the blind needs to go down
        direction = coverDirectionDown

    runtime = abs(int(newposition) - currentposition) * coverOperationTime / 100
    if runtime > coverOperationTime:
        runtime = coverOperationTime
    if runtime < 0:
        runtime = 0

    return (direction, runtime)

def runtime2position(runtime):
    # calculate blind position based on a runtime, the current position and the direction
    if lastDirection == coverDirectionUp:
        newposition = int(currentposition + int(runtime) * 100 / coverOperationTime)
    else:
        newposition = int(currentposition - int(runtime) * 100 / coverOperationTime)
    print("Debug: newposition is %d" % (newposition))
    if newposition > 100:
        newposition = 100
    if newposition < 0:
        newposition = 0

    return newposition

def runMotor(duration, direction):
    global activeTimer, startTime, lastDirection
    print("Running the motor for " + str(duration) + " seconds in direction " + str(direction))
    sys.stdout.flush()
    # turn off any active timers
    if activeTimer:
        activeTimer.cancel()
    # set direction first.
    wpi.digitalWrite(coverDirectionPin, direction)
    # set the cover to be controlled by the Odroid
    wpi.digitalWrite(coverModePin, coverModeAutomatic)
    startTime = int(round(time.time() * 1000)) #time in ms
    print("Starting motor")
    sys.stdout.flush()
    # tell the caller we're opening/closing
    if direction:
        client.publish('ha/blind_cover/get', "opening", 0, False)
    else:
        client.publish('ha/blind_cover/get', "closing", 0, False)

    # start a thread to wait for the operation to complete and schedule a timer to finish it.
    lastDirection = direction
    if duration == coverOperationTime:
        # full run up or down
        if direction:
            activeTimer = threading.Timer(duration, stopBlinds, ["open"])
        else:
            activeTimer = threading.Timer(duration, stopBlinds, ["closed"])
    else:
        # partial control - we don't know the final position of the blinds
        activeTimer = threading.Timer(duration, stopBlinds, ["unknown"])
    activeTimer.start()

def processCommand(state):
    global activeTimer, startTime, lastDirection
    print("Setting cover "+str(state))
    sys.stdout.flush()

    if state == 'OPEN':
        # run the motor for the whole coverOperationTime in the direction Up to open it.
        runMotor(coverOperationTime, coverDirectionUp)

    elif state == 'CLOSE':
        # run the motor for the whole coverOperationTime in the direction Down to close it.
        runMotor(coverOperationTime, coverDirectionDown)

    elif state == 'STOP':
        # we need to close - turn off any active timers
        if activeTimer:
            activeTimer.cancel()
        # call stopBlinds immediately
        stopBlinds("unknown")

    else:
        # other states are not understood
        print("State "+str(state)+" is not supported")
        sys.stdout.flush()

def stopBlinds(action):
    global activeTimer, startTime, currentposition
    # we need to put the cover back in manual mode for the physical switch to work
    wpi.digitalWrite(coverModePin, coverModeManual)
    stopTime = int(round(time.time() * 1000))  # time in ms
    print("Switching back to manual mode (from action %s)" % (action))
    # report back the expected state of the cover
    client.publish('ha/blind_cover/get', action, 0, False)
    sys.stdout.flush()
    activeTimer = None
    if action != "open" and action != "closed":
        #calculate how much time the blind has worked
        runtime = int((stopTime - startTime)/1000)
        print("Runtime is %d" % (runtime))
        #calculate and update the current position
        currentposition = runtime2position(runtime)
    else:
        startTime = 0
        if action == "open":
            currentposition = 100
        if action == "closed":
            currentposition = 0
    print("currentposition is "+str(currentposition))


parseConfig()
conf['mqttTopics'] = ['ha/blind_cover/set', 'ha/blind_cover/position']
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("Starting blind-cover-mqtt-agent.py")
if conf['mqttUser'] and conf['mqttPass']:
    client.username_pw_set(username=conf['mqttUser'], password=conf['mqttPass'])

client.connect(conf['mqttServer'], conf['mqttPort'], 60)
print("Listen to MQTT messages...")
sys.stdout.flush()
client.loop_forever()
