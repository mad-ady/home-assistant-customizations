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
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOSTS

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

CONF_KISMET_SERVER = 'host'
CONF_KISMET_PORT = 'port'
CONF_SSIDS = 'ssids'
CONF_CLIENTS = 'clients'
CONF_SCAN_INTERVAL = 'interval_seconds'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_KISMET_SERVER, default='127.0.0.1'): cv.string,
    vol.Required(CONF_KISMET_PORT, default=2501): cv.positive_int,
    vol.Optional(CONF_SSIDS, default=[]): cv.ensure_list,
    vol.Optional(CONF_CLIENTS, default=[]): cv.ensure_list,
    vol.Optional(CONF_SCAN_INTERVAL): cv.positive_timedelta
})


def get_scanner(hass, config):
    """Validate the configuration and return a Nmap scanner."""
    _LOGGER.debug("Called get_scanner")
    return KismetDeviceScanner(config[DOMAIN])


Device = namedtuple('Device', ['mac', 'last_ssid', 'last_update'])

class KismetDeviceScanner(DeviceScanner):
    """This class scans for devices using kismet."""

    exclude = []

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []

        self.server = config[CONF_KISMET_SERVER]
        self.port = config[CONF_KISMET_PORT]
        self.scan_interval = config[CONF_SCAN_INTERVAL]
        self.ssids = config[CONF_SSIDS]
        self.clients = config[CONF_CLIENTS]

        _LOGGER.debug("scan_interval (type "+str(type(self.scan_interval))+")")
        _LOGGER.debug("Params:"+"server: "+self.server+", port: "+str(self.port)+", scan_interval (type "+str(type(self.scan_interval))+"): "+str(self.scan_interval))

        #check that either clients or ssids has at least an entry
        if len(self.ssids) or len(self.clients):
            _LOGGER.info("Scanner initialized for "+str(len(self.ssids))+" SSIDs and "+str(len(self.clients))+" clients")
        else:
            _LOGGER.error("Kismet device_tracker requires at least a SSID or a client in the configuration")

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
        parameters = {}
        parameters['regex'] = []
        for ssid in self.ssids:
            _LOGGER.debug("Adding SSID "+ssid+"...")
            parameters['regex'].append(['dot11.device/dot11.device.last_beaconed_ssid', str(ssid)])

        for client in self.clients:
            _LOGGER.debug("Adding client " + client + "...")
            parameters['regex'].append(['kismet.device.base.macaddr', str(client).upper()])

        parameters['fields'] = ('kismet.device.base.macaddr', 'kismet.device.base.name')

        payload = "json="+urllib.parse.quote_plus(json.dumps(parameters))
        _LOGGER.debug("Making request with this payload:"+payload)

        try:
            r = requests.post("http://"+self.server+":"+str(self.port)+"/devices/last-time/"+"-"+str(int(self.scan_interval.total_seconds()))+"/devices.json",
                          headers={ 'Content-Type': 'application/x-www-form-urlencoded'},
                          data=payload)

            now = dt_util.now()

            if r.json():
                # we got a valid reply
                for pair in r.json():
                    _LOGGER.debug("Found device "+str(pair['kismet.device.base.macaddr']))
                    last_results.append(Device(pair['kismet.device.base.macaddr'].upper(), pair['kismet.device.base.name'], now))
            else:
                _LOGGER.error("Got an error in the kismet reply: "+r.text)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Error connecting to kismet instance")

        self.last_results = last_results

        _LOGGER.info("Kismet scan finished")
        return True
