#!/usr/bin/python
import re

filename = '/sys/devices/w1_bus_master1/28-05168661eaff/w1_slave'
valid = False

print "Content-Type: text/plain"
print ""

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
            output = "%.1f" % (float(temperature.group(1))/1000.0)
            print output
