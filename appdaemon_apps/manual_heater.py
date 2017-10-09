import appdaemon.appapi as appapi
import re
import datetime

class ManualHeater(appapi.AppDaemon):
    # load data from the configuration section
    interval_length = 15
    climate = "climate.heater_thermostat"
    heater = "switch.heater"

    # called automatically by AppDaemon when starting the App
    def initialize(self):
        self.log("__function__@__line__: Initializing...")
        # set globals based on the configuration apps.yaml
        self.interval_length = self.args["interval_length"]
        self.climate = self.args["climate"]
        self.heater = self.args["heater"]

        # register a recurrent timer callback every interval_length minutes (runs every 5th second of the minute
        self.minutely = self.run_minutely(self.checkManualHeater, datetime.time(0, 0, 5))
        # register callbacks to all the input_boolean.heater_timer_*_* entities
        pattern = re.compile(r"^heater_timer_([0-9]{2})_([0-9]{2})$")
        for item in self.entities.input_boolean:
            result = pattern.search(str(item))
            if result:
                self.log("__function__@__line__: Looking at input_boolean " + str(item))
                # register a callback for this one. Send the hour/minute already parsed
                self.listen_state(self.inputBoolean, "input_boolean." + str(item), hour=result.group(1),
                                  minute=result.group(2))

    # called when the user toggles a input_boolean switch in order to adjust manual schedule
    def inputBoolean(self, entity, attribute, old, new, kwargs):
        self.log("__function__@__line__: Hour is " + kwargs["hour"] + ", minute is " + kwargs[
            "minute"] + ", state is " + new)
        # get the current time, according to AppDaemon (see TimeTravel in the documentation)
        currentHour = int(self.time().strftime("%H"))
        currentMinute = int(self.time().strftime("%M"))
        # see if we are in the same time period as this toggled boolean.
        # e.g. if the input_boolean for 04:30 was activated, and it's now 04:35 (less than interval_length)
        # ignore the date part, we're just comparing times
        booleanTime = datetime.datetime(year=2000, month=1, day=1, hour=int(kwargs["hour"]),
                                        minute=int(kwargs["minute"]))
        currentTime = datetime.datetime(year=2000, month=1, day=1, hour=currentHour, minute=currentMinute)
        difference = currentTime - booleanTime
        # self.log("booleanTime = " + str(booleanTime) + ", currentTime = " + str(currentTime) + ", difference is "+str(difference.total_seconds()))
        if difference.total_seconds() >= 0 and difference.total_seconds() <= self.interval_length * 60:
            # somebody toggled this interval and we're in it!
            self.log("__function__@__line__: Interval was toggled and we're currently in it.")
            self.controlHeater(new)
        else:
            self.log("__function__@__line__: Not my interval. Ignoring it for now")

    # called every minute to check if we need to do a manual intervention
    def checkManualHeater(self, kwargs):
        currentMinute = int(self.time().strftime("%M"))
        if currentMinute % self.interval_length == 0:
            # we're on an interval_length boundry
            self.log("__function__@__line__: Checking if we need to touch climate")
            currentHour = int(self.time().strftime("%H"))
            # get the state of the input_boolean
            booleanName = "heater_timer_%02d_%02d" % (currentHour, currentMinute)
            currentState = eval("self.entities.input_boolean." + booleanName + ".state")
            self.log("__function__@__line__: %s is %s" % (booleanName, currentState))
            self.controlHeater(currentState)

    # take over the heater controls
    def controlHeater(self, newstate):
        if newstate == "on":
            # set climate off
            if eval("self.entities." + self.climate + ".attributes.operation_mode") != "off":
                self.log("__function__@__line__: Turning off climate control")
                self.call_service("climate/set_operation_mode", entity_id=self.climate, operation_mode="off")
            # set heater on
            if eval("self.entities." + self.heater + ".state") != "on":
                self.log("__function__@__line__: Turning on heater switch")
                self.call_service("switch/turn_on", entity_id=self.heater)
        else:
            # set climate on
            if eval("self.entities." + self.climate + ".attributes.operation_mode") != "auto":
                self.log("__function__@__line__: Turning on climate control")
                self.call_service("climate/set_operation_mode", entity_id=self.climate, operation_mode="auto")
            # set heater off
            if eval("self.entities." + self.heater + ".state") != "off":
                self.log("__function__@__line__: Turning off heater switch")
                self.call_service("switch/turn_off", entity_id=self.heater)