#!/usr/bin/python
import paho.mqtt.client as mqtt
import re
import time
import sys
import yaml
import os
import logging 
from logging.config import dictConfig

# Prerequisites:
# * pip: sudo apt-get install python-pip
# * paho-mqtt: pip install paho-mqtt
# * python-yaml: sudo apt-get install python-yaml

# Configuration file goes in /etc/pir-mqtt-agent-sysfs.yaml and should contain your mqtt broker details

# For startup copy pir-mqtt-agent-sysfs.service to /etc/systemd/system/
# Startup is done via systemd with
#  sudo systemctl enable pir-mqtt-agent-sysfs
#  sudo systemctl start pir-mqtt-agent-sysfs

logging_config = dict(
    version = 1,
    formatters = {
        'c': {'format':
              '%(levelname)-8s (%(threadName)-15s) [%(funcName)s:%(lineno)d] %(message)s'}
    },
    handlers = {
        'c': {'class': 'logging.StreamHandler',
              'formatter': 'c',
              'level': logging.DEBUG,
              'stream': "ext://sys.stdout" },
    },
    root = {
        'handlers': ['c'],
        'level': logging.INFO,
    },
)

dictConfig(logging_config)
logger = logging.getLogger(__name__)

oldValue = False
timer_start = 0
motion_detected = False

""" Parse and load the configuration file to get MQTT credentials """

conf = {}
config_file = '/etc/pir-mqtt-agent-sysfs.yaml'


def parseConfig():
    global conf
    logger.debug("Opening config file")
    with open(f"{config_file}", 'r') as stream:
        try:
            conf = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logger.fatal(exc)
            logger.fatal(f"Unable to parse configuration file {config_file}")
            sys.exit(1)

def getFilename(gpio):
    gpio = str(gpio)
    return f"/sys/class/gpio/gpio{gpio}/value"


""" Read sensor from sysfs and return it as a bool """
def readSensor(gpio):
    with open(getFilename(gpio)) as f:
         contents = f.read()
         return bool(int(contents))

""" Setup sensor, if needed """
def setupSensor(gpio):
   logger.debug(f"Setting up GPIO {gpio}")
   # Convert the input to string
   gpio = str(gpio)
   
   # Define the GPIO directory
   gpio_dir = f"/sys/class/gpio/gpio{gpio}"
   
   # Check if the directory exists
   if not os.path.isdir(gpio_dir):
       # If it doesn't exist, export the GPIO
       logger.debug(f"Exporting {gpio}")
       with open("/sys/class/gpio/export", "w") as f:
           f.write(gpio)
       
   # Define the direction file
   direction_file = f"{gpio_dir}/direction"
   
   # Write to the direction file
   with open(direction_file, "w") as f:
       f.write("in")

""" Initialize the MQTT object and connect to the server """
parseConfig()
setupSensor(conf['gpio'])

client = mqtt.Client()
if conf['mqttUser'] and conf['mqttPass']:
    client.username_pw_set(username=conf['mqttUser'], password=conf['mqttPass'])
logger.info("Connecting to MQTT broker")
client.connect(conf['mqttServer'], conf['mqttPort'], 60)
client.loop_start()

""" Do an infinite loop reading sensor values and sending them via MQTT """


while True:
   # Poll the motion sensor
   motion = readSensor(conf['gpio'])
   logger.debug(f"Sensor value {motion}")
   
   if motion and not motion_detected:
       # Motion detected and previously not detected
       logger.info('Motion detected')
       motion_detected = True
       timer_start = time.time()
       client.publish(conf['mqttTopic'], '1', 0, conf['mqttPersistent'])  
       
   elif not motion and motion_detected:
       # No motion detected but previously was
       if time.time() - timer_start < int(conf['persistence']):
           # Still within hysteresis time
           logger.debug('Motion detected (hysterezis period)')
       else:
           # Outside hysteresis time
           logger.debug('No motion detected')
           motion_detected = False
           client.publish(conf['mqttTopic'], '0', 0, conf['mqttPersistent'])  

   time.sleep(conf['sleep'])

