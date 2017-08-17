#!/bin/bash


filename='/sys/devices/w1_bus_master1/28-05168661eaff/w1_slave'
valid=0

echo "Content-Type: text/plain"
echo 

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
    echo "scale=1;$rawtemperature/1000" | bc
  fi
#read line by line from $filename
done < "$filename"