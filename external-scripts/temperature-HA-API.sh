#!/bin/bash

filename='/sys/devices/w1_bus_master1/28-05168661eaff/w1_slave'
homeassistantip='192.168.1.9'
haport=8123
api_password='odroid'
sensor_name='sensor.temperature_via_api'
valid=0

# read line by line, parse each line
while read -r line
do

  if [[ $line =~ crc=.*YES ]]; then
    # the CRC is valid. Continue processing
    valid=1
    continue
  fi
  if [[ "$valid" == "1" ]] && [[ $line =~ t=[0-9]+ ]]; then
    # extract the temperature value
    rawtemperature=`echo "$line" | cut -d "=" -f 2`
    # convert to degrees celsius and keep 1 digit of accuracy
    temperature=`echo "scale=1;$rawtemperature/1000" | bc`
    # push the data to the Home Assistant entity via the API
    curl -X POST -H "x-ha-access: $api_password" -H "Content-Type: application/json" \
    --data "{\"state\": \"$temperature\"}" http://$homeassistantip:$haport/api/states/$sensor_name
  fi
#read line by line from $filename
done < "$filename"