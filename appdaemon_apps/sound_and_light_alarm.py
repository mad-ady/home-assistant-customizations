import appdaemon.appapi as appapi
import re
import time

""" Appdaemon App that simulates an alarm.
    Plays a preset playlist to a media player while flashing a light in a specific pattern (rhythm)

    Example configuration inside apps.yaml:
    sound_and_light_alarm:
      module: sound_and_light_alarm
      class: SoundAndLightAlarm
      media_player: "media_player.mpd_kids"
      light: "light.kids_light"
      music: "wakeupalarm"
      rhythm: "/home/homeassistant/.homeassistant/trumpet.txt"
      trigger: "input_boolean.wake_up"

"""

class SoundAndLightAlarm(appapi.AppDaemon):
    #load data from the configuration section
    media_player=None
    light=None
    music=None
    rhythm=None
    trigger=None

    # called automatically by AppDaemon when starting the App
    def initialize(self):
        self.log("__function__@__line__: Initializing...")
        #set globals based on the configuration apps.yaml
        self.media_player = self.args["media_player"]
        self.light = self.args["light"]
        self.music = self.args["music"]
        self.rhythm = self.args['rhythm']
        self.trigger = self.args['trigger']

        #register callback for an input_boolean trigger
        trigger_state = eval("self.entities."+self.trigger)
        if trigger_state is not None:
            self.log("__function__@__line__: Registering listener for "+self.trigger)
            self.listen_state(self.onTrigger, self.trigger)
        else:
            self.log("__function__@__line__: Unable to find entity trigger named "+str(self.trigger))

    def onTrigger(self, entity, attribute, old, new, kwargs):
        self.log("__function__@__line__: Processing trigger state change")
        if new == "on":
            self.log("__function__@__line__: trigger turned on, it's show time!")
            #prepare the media player
            self.call_service("homeassistant/turn_on", entity_id=self.media_player)
            self.call_service("media_player/volume_set", entity_id=self.media_player, volume_level=1)
            #play the media player
            self.call_service("media_player/play_media", entity_id=self.media_player, media_content_id=self.music, media_content_type="playlist")
            #save the current light state
            old_light_state = eval("self.entities."+self.light)
            self.log("__function__@__line__: Old light state is "+str(old_light_state))
            #prepare to parse the rhythm file
            #look for lines similar to this
            #Event: time 1525422849.036317, type 1 (EV_KEY), code 30 (KEY_A), value 1
            #1 means on, 0 means off. Sleep for the difference between on/off
            pattern = r"Event: time ([0-9\.]+), type 1 \(EV_KEY\), code 30 \(KEY_A\), value ([0-2])"
            last_value = 0
            last_time = 0
            try:
                for line in open(self.rhythm, "r"):
                    #"play" the light
                    m = re.search(pattern, line)
                    if m:
                        ctime = float(m.group(1))
                        value = int(m.group(2))
                        if value != last_value: #ignore repeated values
                            #sleep for whatever time we needed to sleep
                            if last_time > 0:
                                time_to_sleep = ctime-last_time
                                #due to limitations in the switching time for my light, reduce sleep periods from what is measured by 0.1s
                                time_to_sleep = time_to_sleep - 0.1
                                if time_to_sleep < 0:
                                    time_to_sleep = 0
                                time.sleep(time_to_sleep)
                                self.log("__function__@__line__: Slept for "+str(time_to_sleep))
                            if value == 1:
                                #we need to turn on the light
                                self.log("__function__@__line__: Turning on light")
                                self.call_service("homeassistant/turn_on", entity_id=self.light)
                            if value == 0:
                                #we need to turn off the light
                                self.log("__function__@__line__: Turning off light")
                                self.call_service("homeassistant/turn_off", entity_id=self.light)
                            last_time = ctime
                            last_value = value

                    
            except IOError: 
                 self.log("__function__@__line__: Unable to read rhythm file. Lights blinking skipped")
            #restore original light state
            if old_light_state.state == "on":
            	self.call_service("homeassistant/turn_on", entity_id=self.light)
            else:
            	self.call_service("homeassistant/turn_off", entity_id=self.light)

            #turn off the trigger
            self.call_service("homeassistant/turn_off", entity_id=self.trigger)
            self.call_service("homeassistant/turn_off", entity_id=self.media_player)
        
        else:
            self.log("__function__@__line__: trigger turned off, ignoring")
