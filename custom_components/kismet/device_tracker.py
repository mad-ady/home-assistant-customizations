"""
Support for tracking wifi-enabled devices through Kismet.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.kismet/
"""
from datetime import timedelta
import logging
import re
import urllib
import requests
import json
from collections import namedtuple

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import (
    CONF_SCAN_INTERVAL, DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import ( CONF_HOSTS, CONF_LATITUDE, CONF_LONGITUDE, ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE)

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

CONF_KISMET_SERVER = 'host'
CONF_KISMET_PORT = 'port'
CONF_KISMET_USER = 'user'
CONF_KISMET_PASS = 'pass'
CONF_SSIDS = 'ssids'
CONF_CLIENTS = 'clients'
CONF_LOCAL_LATITUDE = 'latitude'
CONF_LOCAL_LONGITUDE = 'longitude'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_KISMET_SERVER, default='127.0.0.1'): cv.string,
    vol.Required(CONF_KISMET_PORT, default=2501): cv.positive_int,
    vol.Required(CONF_KISMET_USER, default='kismet'): cv.string,
    vol.Required(CONF_KISMET_PASS, default='changeme'): cv.string,
    vol.Optional(CONF_SSIDS, default=[]): cv.ensure_list,
    vol.Optional(CONF_CLIENTS, default=[]): cv.ensure_list,
    vol.Optional(CONF_LOCAL_LATITUDE, default=0.0): cv.latitude,
    vol.Optional(CONF_LOCAL_LONGITUDE, default=0.0): cv.longitude,
    #vol.Required(CONF_SCAN_INTERVAL): cv.time_period_seconds
    #vol.Required(CONF_SCAN_INTERVAL): cv.positive_int
    #vol.Required(CONF_SCAN_INTERVAL): cv.timedelta
})


def get_scanner(hass, config):
    """Validate the configuration and return a Nmap scanner."""
    _LOGGER.debug("Called get_scanner")
    return KismetDeviceScanner(hass, config[DOMAIN])


DeviceGPS = namedtuple('Device', ['mac', 'last_ssid', 'gps', 'last_update'])
Device = namedtuple('Device', ['mac', 'last_ssid', 'last_update'])

class KismetDeviceScanner(DeviceScanner):
    """This class scans for devices using kismet."""

    exclude = []

    def __init__(self, hass, config):
        """Initialize the scanner."""
        self.last_results = []

        self.server = config[CONF_KISMET_SERVER]
        self.port = config[CONF_KISMET_PORT]
        self.user = config[CONF_KISMET_USER]
        self.password = config[CONF_KISMET_PASS]
        self.scan_interval = config[CONF_SCAN_INTERVAL]
        #self.scan_interval = 35
        self.ssids = config[CONF_SSIDS]
        self.clients = config[CONF_CLIENTS]

#        self.longitude = config[CONF_LOCAL_LONGITUDE]
#        if self.longitude == 0:
#            # no local setting, try setting the one from Home Assistant instance
#            self.longitude = hass.config.longitude
#        self.latitude = config[CONF_LOCAL_LATITUDE]
#        if self.latitude == 0:
#            # no local setting, try setting the one from Home Assistant instance
#            self.latitude = hass.config.latitude
        

        _LOGGER.debug("Params:"+"server: "+self.server+", port: "+str(self.port)+", scan_interval (type "+str(type(self.scan_interval))+"): "+str(self.scan_interval))

        #check that either clients or ssids has at least an entry
        if len(self.ssids) or len(self.clients):
            _LOGGER.info("Scanner initialized for "+str(len(self.ssids))+" SSIDs and "+str(len(self.clients))+" clients")
        else:
            _LOGGER.error("Kismet device_tracker requires at least a SSID or a client in the configuration")

#    @property
#    def latitude(self):
#        """Return latitude value of the tracker."""
#        # Check with "get" instead of "in" because value can be None
#        if self.latitude:
#           return self.latitude
#        return None
#
#    @property
#    def longitude(self):
#        """Return longitude value of the tracker."""
#        # Check with "get" instead of "in" because value can be None
#        if self.longitude:
#           return self.longitude
#        return None
    
    def scan_devices(self):
        """Scan for new devices and return a list with found MACs."""
        self._update_info()

        _LOGGER.debug("Kismet last results %s", self.last_results)

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        _LOGGER.debug("Called get_device_name with device = "+str(device))
        filter_named = [result.last_ssid for result in self.last_results
                        if result.mac == device]

        if filter_named:
            _LOGGER.debug("Returning name " + str(filter_named[0]) + " for client "+ str(device) )
            return filter_named[0]
        return None

    def _update_info(self):
        """Scan the network for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Preparing kismet query...")
        last_results = []
        #prepare the query

        # two different records for client/ssid
        ssid_gps_prefix = "dot11.device/dot11.device.last_beaconed_ssid_record/dot11.advertisedssid.location"
        client_gps_prefix = "dot11.device/dot11.device.last_probed_ssid_record/dot11.probedssid.location"
        
        parameters = {"regex": [], "fields": ["kismet.device.base.name", "kismet.device.base.macaddr"] }

        if len(self.ssids):
            parameters["fields"].append(ssid_gps_prefix)
        
        if len(self.clients):
            parameters["fields"].append(client_gps_prefix)

        for ssid in self.ssids:
            _LOGGER.debug("Adding SSID " + ssid + "...")
            parameters["regex"].append(["kismet.device.base.name", str(ssid)])
        
        for client in self.clients:
            _LOGGER.debug("Adding client " + client + "...")
            parameters["regex"].append(["kismet.device.base.macaddr", str(client).upper()])
        

        #payload = "json="+urllib.parse.quote_plus(json.dumps(parameters))
        payload = "json="+json.dumps(parameters)
        _LOGGER.debug("Making request with this payload:"+payload)

        try:
            r = requests.post("http://"+self.server+":"+str(self.port)+"/devices/last-time/"+"-"+str(self.scan_interval.total_seconds())+"/devices.json",
                headers={ 'Content-Type': 'application/x-www-form-urlencoded'},
                data=payload,
                auth=(self.user, self.password))
            
            now = dt_util.now()
            
            if r.ok:
                if r.json():
                    # we got a valid reply. Should look like this:
                    #[{'kismet.device.base.macaddr': 'AA:BB:CC:DD:EE:FF', 'kismet.device.base.name': 'My Device Name',
                    #  'dot11.[probed/advertised]ssid.location': { ... } }]

                    _LOGGER.info(r.json())
                    for pair in r.json():
                        _LOGGER.debug("Found device "+str(pair['kismet.device.base.macaddr']))

                        if "dot11.probedssid.location" in pair and pair["dot11.probedssid.location"] != 0:
                            location = pair["dot11.probedssid.location"]
                        
                        elif "dot11.advertisedssid.location" in pair and pair["dot11.advertisedssid.location"] != 0:
                            location = pair["dot11.advertisedssid.location"]
                         
                        if location and "kismet.common.location.loc_valid" in location and location["kismet.common.location.loc_valid"] == 1:
                            # instead of delving further into the structure, we use the integer coordinates
                            lat = location["kismet.common.location.avg_lat"] * .000001
                            lon = location["kismet.common.location.avg_lon"] * .000001
                            last_results.append(DeviceGPS(pair["kismet.device.base.macaddr"].upper(), pair["kismet.device.base.name"], (lat,lon), now))
                        else:
                            _LOGGER.debug("Couldn't find GPS Coordinates in result..")
                            last_results.append(Device(pair["kismet.device.base.macaddr"].upper(), pair["kismet.device.base.name"], now))
                else:
                    _LOGGER.error(f"Got an error in the kismet reply: {r.text}")
                    pass
            else:
                _LOGGER.error(f"Got an error in the kismet query. Error code {r.status_code}, reply text {r.text}")

        except requests.exceptions.ConnectionError:
            _LOGGER.error("Error connecting to kismet instance")

        self.last_results = last_results

        _LOGGER.debug("Kismet scan finished")
        return True
