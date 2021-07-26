import queue
from typing import List
import appdaemon.plugins.hass.hassapi as hass
import time
import json
from enum import Enum

class ACMODE(Enum):
    COOLING = 1
    HEATING = 2
    OTHER = 3
    OFF = 4

class smarterzones(hass.Hass): 
    
    def initialize(self):   
    
      # Get climate device, outside temperature and fan setting
      try:
        self.climatedevice = self.args.get('climatedevice')
        self.exterior_temperature = self.args.get('exteriortempsensor')
        self.forceautofan = self.args.get('force_auto_fan', False)    
        # Hook up a listener for the climate device
        self.listen_state(self.climatedevicechange, self.climatedevice)    
        # Hook up a listener for an exterior temperature change (maybe)
        self.listen_state(self.outside_climate_change, self.exterior_temperature)
        # Hook up a listener to force the fan to auto mode
        if self.forceautofan:
            self.listen_state(self.climatefanchange, self.climatedevice, attribute="fan_mode")
      except Exception as ex:
        self.queuedlogger(ex)

      # Get zones from config
      try: 
         self.zones = self.args.get('zones', []) 
      except Exception as ex:
          self.queuedlogger(ex)

      for zone in self.zones:
            self.queuedlogger("Monitoring new zone: " + zone['friendly_name'])
            self.listen_state(self.inroomtempchange, zone['local_tempsensor'])
            self.listen_state(self.target_temp_change, zone['target_temp'])
            try:
                self.listen_state(self.manual_override_change, zone['manual_override'])
            except:
                pass
            self.automatically_manage_zone(zone)

    # Climate Device Listeners
    def climatefanchange(self, entity, attribute, old, new, kwargs):
        ison = self.get_state(entity)
        if ison != "off" and new.lower().find("auto") == -1: 
            availablemodes = self.get_state(entity, attribute="fan_modes")
            if str(availablemodes).lower().find("auto") != -1:
                self.call_service("climate/set_fan_mode", entity_id = self.climatedevice, fan_mode = new + "/Auto")

    def climatedevicechange(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("Climate Device Changed: " + entity)

    # Zone Listeners           
    def target_temp_change(self, entity, attribute, old, new, kwargs):
        for zone in self.zones:
            self.queuedlogger(zone["friendly_name"]  + ": Wanted temperature in zone changed from " + str(old) + " to " + str(new))
            self.automatically_manage_zone(zone)

    def inroomtempchange(self, entity, attribute, old, new, kwargs):
       for zone in self.zones:
           if zone["local_tempsensor"] == str(entity):
                self.queuedlogger(zone["friendly_name"] + ": Current temperature in zone changed from " + str(old) + " to " + str(new))
                self.automatically_manage_zone(zone)

    def manual_override_change(self, entity, attribute, old, new, kwargs):
        for zone in self.zones:
            if zone["manual_override"] == str(entity):
                self.queuedlogger(zone["friendly_name"] + ": manual override switch changed from " + str(old) + " to " + str(new))
                self.automatically_manage_zone(zone)

    # Exterior temperature sensor monitor - for future use       
    def outside_climate_change(self, entity, attribute, old, new, kwargs):
       self.queuedlogger("Outside Temperature changed from " + str(old) + " to " + str(new))

    # Zone Management
    def automatically_manage_zone(self, zone):     
        zonename = zone["friendly_name"]
        # If manual override exists and is enabled stop processing.
        
        if self.override_enabled(zone) is True:            
            return

        # check if conditions for zone to be open are met and if not close it.
        if self.IsConditionMet(zone) is False:
            self.switchoff(zone)
            return    

        # Get current climate device state
        climate_device_state = self.get_state(self.climatedevice)
        temperature_offsets = self.get_temperature_offsets(zone, climate_device_state)
        coolingmode = self.heatingorcooling(climate_device_state, zone)

        # Get zones current and wanted temperatures
        wanted_zone_temperature = float(self.get_state(zone["target_temp"]))
        current_zone_temperature = float(self.get_state(zone["local_tempsensor"]))
        maxtemp = wanted_zone_temperature + temperature_offsets[0]
        mintemp = wanted_zone_temperature - temperature_offsets[1]
        if coolingmode == ACMODE.OFF:
            return
        elif coolingmode == ACMODE.COOLING:
            # Check if zone is above the wanted temperature and if so, open the zone to cool      
            if current_zone_temperature >= maxtemp:
                self.switchon(zone)
            elif current_zone_temperature <= mintemp:
                self.switchoff(zone)
        elif coolingmode == ACMODE.HEATING:
            if current_zone_temperature <= mintemp:
                self.switchon(zone)
            elif current_zone_temperature >= maxtemp:
                self.switchoff(zone)
        else:
            # what do we want to do with drying, I think turn all zones on
            self.queuedlogger("Other")

    def switchon(self, zone):
        zone_switch = zone["zone_switch"]
        state = self.get_state(zone_switch)
        if state != "on":
            self.queuedlogger(zone["friendly_name"] + ": zone is opening")
            self.call_service("switch/turn_on", zone_switch)
      
    def switchoff(self, zone):
        zone_switch = zone["zone_switch"]
        state = self.get_state(zone_switch)
        if state != "of":
            self.queuedlogger(zone["friendly_name"] + ": zone is closing")
            self.call_service("switch/turn_off", zone_switch)

    # Zone Checks
    def override_enabled(self, zone):       
        try:
            Override = zone["manual_override"]
        except:
            return False

        if self.get_state(zone["manual_override"]) == "on":
            return True
        else:
            return False
        
    def IsConditionMet(self, zone):
        try:
            checkconditions = zone["conditions"]
        except:
            return True       

        try:
         for item in zone["conditions"]:
            entity = item["entity"]
            targetstate = item["targetstate"]            
            state = self.get_state(entity)
            if str(state.lower()) != str(targetstate.lower()):
                return False
        except Exception as dex:
            return True
        return True
    
    def get_temperature_offsets(self, zone, mode):
        zonename = zone["friendly_name"]
        mode = self.heatingorcooling(mode, zone)
        if mode == ACMODE.COOLING or ACMODE.OTHER:
            try:
                boundaries = [float(zone["coolingoffset"]["upperbound"]), float(zone["coolingoffset"]["lowerbound"])]
            except:
                boundaries = [0.3, 0.3]
            return boundaries
        else:
            try:
                boundaries = [float(zone["heatingoffset"]["upperbound"]), float(zone["heatingoffset"]["lowerbound"])]
            except:
                boundaries = [0.3, 0.3]
            return boundaries

    def heatingorcooling(self, mode, zone):
        if mode == "off":
            return ACMODE.OFF
        elif mode == "cool":
            return ACMODE.COOLING
        elif mode == "heat":
            return ACMODE.HEATING
        elif mode == "fan_only" or mode == "dry": 
            return ACMODE.OTHER
        else:
            # Since we don't know if we're heating or cooling from the climate devices mode, we need to make our best guess
            # Use target temp compared to external temperature to guess if it's heating or cooling
            outside_temperature = self.get_state(self.exterior_temperature)
            target_temperature = self.get_state(zone["target_temp"])
            if outside_temperature > target_temperature:         
                return ACMODE.COOLING
            elif outside_temperature < target_temperature:
                return ACMODE.HEATING
 
    def queuedlogger(self, message):
        self.log(message)
        
