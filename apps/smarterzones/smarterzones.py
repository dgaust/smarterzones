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
    COOLING_OFFSET_DEFAULT = [0.3, 0.3]
    HEATING_OFFSET_DEFAULT = [0.3, 0.3]
    TriggerTemperature = 0

    def initialize(self):   
        # Get climate device, outside temperature and fan setting
        try:
            self.Common_Zone_Flag = False
            self.climatedevice = self.args.get('climatedevice')
            self.exterior_temperature = self.args.get('exteriortempsensor')
            self.forceautofan = self.args.get('force_auto_fan', False)    
            self.listen_state(self.climatedevicechange, self.climatedevice)    
            self.listen_state(self.outside_climate_change, self.exterior_temperature)
            if self.forceautofan:
                self.listen_state(self.climatefanchange, self.climatedevice, attribute="fan_mode")
        except Exception as ex:
            self.queuedlogger(ex)

        try: 
            self.zones = self.args.get('zones', []) 
            try:
                self.common_zone = self.args['common_zone_switch']
                self.Common_Zone_Flag = True
            except Exception as ex:
                self.queuedlogger("No common zone found")
                self.Common_Zone_Flag = False

            try:
                self.trigger_temp_sensor = self.args['trigger_temp_sensor']
                self.TriggerTemperature = self.args['trigger_temp']
                self.listen_state(self.trigger_temp_sensor_changed,  self.trigger_temp_sensor)
                self.queuedlogger("Trigger sensor detected, will automatically turn on airconditioner when temp exceeds: " + str(self.trigger_temp))
            except Exception as ex:
                self.queuedlogger("No trigger threshold entity available")

            for zone in self.zones:
                self.listen_state(self.target_temp_change, zone['target_temp'])
                self.listen_state(self.inroomtempchange, zone['local_tempsensor'])

                try:
                    for item in zone["conditions"]:
                        entity = item["entity"]
                        self.listen_state(self.conditionchanged, entity)
                except Exception as ex:
                    self.queuedlogger("Trouble setting condition listener: " + str(ex))
                    pass

                try:
                    self.listen_state(self.manual_override_change, zone['manual_override'])
                except Exception as ex:
                    pass

                if self.Common_Zone_Flag and self.common_zone == zone["zone_switch"]:
                    self.listen_state(self.common_zone_manager, self.common_zone)

                self.automatically_manage_zone(zone)

        except Exception as ex:
            self.queuedlogger(ex)

    def entity_creation():


    def trigger_temp_sensor_changed(self, entity, attribute, old, new, kwargs):
        if (float(new) >= self.TriggerTemperature):
            devicestate = self.get_state(self.climatedevice)
            if (devicestate == 'off'):
                self.queuedlogger("Trigger temperature exceeded, turning on airconditioner to cool")
                self.climate_entity = self.get_entity(self.climatedevice)
                self.climate_entity.call_service("set_hvac_mode", hvac_mode = "cool" )



    def conditionchanged(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("A condition in one of the zones changed")
        for zone in self.zones:
            self.automatically_manage_zone(zone)

    # Climate Device Listeners
    def climatefanchange(self, entity, attribute, old, new, kwargs):
        is_on = self.get_state(entity)
        if is_on != "off" and "auto" not in self.get_state(entity, attribute="fan_modes").lower():
            self.call_service("climate/set_fan_mode", entity_id=self.climatedevice, fan_mode=f"{new}/Auto")


    def climatedevicechange(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("Climate device change state. Setting up zones appropriately.")
        for zone in self.zones:
            self.automatically_manage_zone(zone)
        if self.Common_Zone_Flag:
            self.queuedlogger("Common zone enabled, better set it up")
            self.common_zone_manager(entity = self.common_zone, attribute = self.common_zone, old = self.common_zone, new = self.common_zone, kwargs = self.Common_Zone_Flag)

    # In room sensor or setting changes
    def target_temp_change(self, entity, attribute, old, new, kwargs):
        for zone in self.zones:
            if (zone["target_temp"] == entity):
                self.queuedlogger(zone["name"]  + ": Wanted temperature in zone changed from " + str(old) + " to " + str(new))
                self.automatically_manage_zone(zone)

    def inroomtempchange(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("Got an inzone temp change from: " + entity)
        for zone in self.zones:
            if zone["local_tempsensor"] == str(entity):
                self.queuedlogger(zone["name"] + ": Current temperature in zone changed from " + str(old) + " to " + str(new))
                newint = float(new)
                oldint = float(old)
                diff = round(newint - oldint,2)
                if diff > 0:
                  self.queuedlogger(zone["name"] + ": temperature increased by " + str(diff) + " degrees")
                else:
                  self.queuedlogger(zone["name"] + ": temperature decreased by " + str(diff * -1) + " degrees")
                self.automatically_manage_zone(zone)

    def manual_override_change(self, entity, attribute, old, new, kwargs):
        for zone in self.zones:
            if zone["manual_override"] == str(entity):
                self.queuedlogger(zone["name"] + ": manual override switch changed from " + str(old) + " to " + str(new))
                self.automatically_manage_zone(zone)

    # Zone Listeners       
    def common_zone_manager(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("Checking to see if common zone required to be open: " + entity)
        
        # what do these do
        AZoneOpen = False
        CommonZoneOpen = False      
        
        for zone in self.zones:
            zonestate = self.get_state(zone["zone_switch"])
            if zonestate == "on" and self.common_zone != zone["zone_switch"]:
                self.queuedlogger(zone["name"] + " is already open")
                AZoneOpen = True
            elif zonestate == "on" and self.common_zone == zone["zone_switch"]:
                self.queuedlogger("Common zone is already open")
                AZoneOpen = True
                CommonZoneOpen = True
        if AZoneOpen == False and CommonZoneOpen == False:
            self.queuedlogger("All zones including common are closed so opening the common zone")
            self.common_zone_open(entity)
        elif AZoneOpen == False and CommonZoneOpen == True:
            self.queuedlogger("Zones are closed, but common is open, so it's good")
        else:
            self.queuedlogger("At least one zone is open so the Common Zone will be controlled automatically")

    def automatically_manage_zone(self, zone):     
        zonename = zone["name"]
        # If manual override exists and is enabled stop processing.
        self.queuedlogger("Auto-managing: " + zonename)

        climate_device_state = self.get_state(self.climatedevice)
        coolingmode = self.heatingorcooling(climate_device_state, zone)
        time.sleep(0.25)
        
        # If the climate control device is off, close zones to prevent any undesired airflow
        if climate_device_state == "off":
           self.switchoff(zone)
           return
        
        if self.override_enabled(zone) is True:            
            return

        if coolingmode == ACMODE.HEATING or coolingmode == ACMODE.COOLING:
           manage = True
        else:
           manage = False
        
        self.queuedlogger(zonename + ": auto control conditon is " + str(self.IsConditionMet(zone)))

        # check if conditions for zone to be open are met and if not close it. 
        if self.IsConditionMet(zone) is False and manage:
            self.switchoff(zone)
            return    

        # Get current climate device state        
        temperature_offsets = self.get_temperature_offsets(zone, climate_device_state)
        
        # Get zones current and wanted temperatures
        wanted_zone_temperature = float(self.get_state(zone["target_temp"]))

        try:
            current_zone_temperature = float(self.get_state(zone["local_tempsensor"]))
            self.queuedlogger(zonename + ": current zone temperature is " + str(current_zone_temperature) + " and wanted temperature is " + str(wanted_zone_temperature)) 
        except:
            current_zone_temperature =  wanted_zone_temperature + 5
            self.queuedlogger("Error getting current temperature in " + zone["name"] + " zone. Check the temperature sensor.")
            self.queuedlogger("Setting current zone temperature to " + str(wanted_zone_temperature) + " due to local temp sensor failure")      
        
        maxtemp = wanted_zone_temperature + temperature_offsets[0]
        mintemp = wanted_zone_temperature - temperature_offsets[1]
        
        self.queuedlogger(zonename + ": Desired temperature range is: " + str(mintemp) + " to " + str(maxtemp))

        if coolingmode == ACMODE.OFF:
            self.switchoff(zone)
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
            # what do we want to do with drying, I think turn all zones on. 
            # this is never hit due to the IsConditionMet check above
            self.switchon(zone)
            self.queuedlogger(zonename + ": It's either fan or dry mode, so just open the zone")


    # Exterior temperature sensor monitor - for future use       
    def outside_climate_change(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("Outside Temperature changed from " + str(old) + " to " + str(new))   

    def switchon(self, zone):
        zone_switch = zone["zone_switch"]
        state = self.get_state(zone_switch)
        if state != "on":
            self.queuedlogger(zone["name"] + ": zone is opening")
            time.sleep(0.2)
            self.call_service("switch/turn_on", entity_id = zone_switch)
            if self.Common_Zone_Flag:
                self.common_zone_manager(entity = self.common_zone, attribute = self.common_zone, old = self.common_zone, new = self.common_zone, kwargs = self.Common_Zone_Flag)

    def switchoff(self, zone):
        zone_switch = zone["zone_switch"]
        state = self.get_state(zone_switch)
        if state != "off":
            self.queuedlogger(zone["name"] + ": zone is closing")
            time.sleep(0.2)
            self.call_service("switch/turn_off", entity_id = zone_switch)
            if self.Common_Zone_Flag:
                self.common_zone_manager(entity = self.common_zone, attribute = self.common_zone, old = self.common_zone, new = self.common_zone, kwargs = self.Common_Zone_Flag)

    def common_zone_open(self, entity):
        state = self.get_state(entity)
        if state != "on":
            self.queuedlogger("Ensuring common zone is open")
            time.sleep(0.2)
            self.call_service("switch/turn_on", entity_id = entity)

    def common_zone_closed(self, entity):
        state = self.get_state(entity)
        if state != "off":
            self.queuedlogger("Climate is off, so turning common zone off")
            time.sleep(0.2)
            self.call_service("switch/turn_off", entity_id = entity)

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
        zonename = zone["name"]
        mode = self.heatingorcooling(mode, zone)
        if mode == ACMODE.COOLING or mode == ACMODE.OTHER:
            try:
                boundaries = [float(zone["coolingoffset"]["upperbound"]), float(zone["coolingoffset"]["lowerbound"])]
            except Exception as e:
                boundaries = self.COOLING_OFFSET_DEFAULT
                self.queuedlogger(f"Error getting cooling offsets for {zonename}: {e}. Defaulting to {self.COOLING_OFFSET_DEFAULT} degrees either side of setpoint.")
            return boundaries
        else:
            try:
                boundaries = [float(zone["heatingoffset"]["upperbound"]), float(zone["heatingoffset"]["lowerbound"])]
            except Exception as e:
                boundaries = self.HEATING_OFFSET_DEFAULT
                self.queuedlogger(f"Error getting heating offsets for {zonename}: {e}. Defaulting to {self.HEATING_OFFSET_DEFAULT} degrees either side of setpoint.")
            return boundaries

    def heatingorcooling(self, mode, zone):
        self.queuedlogger("Mode: " + mode)
        if mode == "off":
            return ACMODE.OFF
        elif mode == "cool":
            return ACMODE.COOLING
        elif mode == "heat":
            return ACMODE.HEATING
        elif mode == "fan_only" or mode == "dry": 
            return ACMODE.OTHER
        else:
            outside_temperature = float(self.get_state(self.exterior_temperature))
            target_temperature = float(self.get_state(self.climatedevice, "temperature"))
            if outside_temperature > target_temperature:   
                self.queuedlogger("Estimated mode as cooling")      
                return ACMODE.COOLING
            elif outside_temperature < target_temperature:
                self.queuedlogger("Estimated mode as heating") 
                return ACMODE.HEATING
            else:
                return ACMODE.OTHER

    def queuedlogger(self, message):
        self.log(message) 
