#!/usr/bin/python

intervals=96
duration = 24*60.0/intervals
current = 0

group = []

print("Interval duration is "+str(duration)+" minutes")
print("======== Cut here and paste to input_boolean: section  =====")

for i in range(0, intervals, 1):
    # calculate time interval
    if i > 0:
        current = current + duration
    # format current as an hour
    timestamp = '{:02d}_{:02d}'.format(*divmod(int(current), 60))
    readableTimestamp = '{:02d}:{:02d}'.format(*divmod(int(current), 60))
    #print the config subsection
    print("""  heater_timer_%s:
    name: Heater timer %s 
    initial: off
    icon: mdi:fire"""%(timestamp, readableTimestamp))
    (hours, minutes) = divmod(int(current), 60)
    groupid = hours//4
    #calculate a reasonable name for the timer group
    # eg. timer group 0 has entries from 00:00 to 03:45
    startGroupTime = (groupid*4, 0)
    endGroupTime = ((groupid+1)*4, 0)

    startTime = '{:02d}:{:02d}'.format(*startGroupTime)
    endTime = '{:02d}:{:02d}'.format(*endGroupTime)
    #print("start/end time: %s-%s"%(startTime, endTime))
    try:
        group[groupid]
    except IndexError:
        group.append("""  heater_timer_group_%d:
    name: Timer group %s - %s
    control: hidden
    entities:"""%(groupid, startTime, endTime))

    group[groupid]+="""\n     - input_boolean.heater_timer_%s"""%(timestamp)

print("============== Cut here and paste to group section ============")
for item in group:
    print(item)

print("""  heater_timer_group:
    name: Heater timer
    control: hidden
    entities:""")
for i in range(0, len(group), 1):
    print("    - group.heater_timer_group_%d"%(i))