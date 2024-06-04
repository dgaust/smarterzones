import queue
from typing import List
import appdaemon.plugins.hass.hassapi as hass
import time
from enum import Enum

class ACMODE(Enum):
    COOLING = 1
    HEATING = 2
    OTHER = 3
    OFF = 4

class smarterzones(hass.Hass): 
    COOLING_OFFSET_DEFAULT = [0.3, 0.3]
    HEATING_OFFSET_DEFAULT = [0.3, 0.3]
    TriggerTemperatureUpper = 0
    TriggerTemperatureLower = 0

    def initialize(self):   
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
            except KeyError:
                self.queuedlogger("No common zone found")
                self.Common_Zone_Flag = False

            try:
                self.trigger_temp_sensor = self.args['trigger_temp_sensor']
                self.TriggerTemperatureUpper = self.args['trigger_temp_upper']
                self.TriggerTemperatureLower = self.args['trigger_temp_lower']
                self.listen_state(self.trigger_temp_sensor_changed,  self.trigger_temp_sensor)
                self.queuedlogger("Trigger sensor detected, will automatically turn on airconditioner when temp exceeds: " + str(self.TriggerTemperatureUpper))
            except KeyError:
                self.queuedlogger("No trigger threshold entity available")

            for zone in self.zones:
                self.listen_state(self.target_temp_change, zone['target_temp'])
                self.listen_state(self.inroomtempchange, zone['local_tempsensor'])

                try:
                    for item in zone["conditions"]:
                        entity = item["entity"]
                        self.listen_state(self.conditionchanged, entity)
                except KeyError as ex:
                    self.queuedlogger("Trouble setting condition listener: " + str(ex))

                try:
                    self.listen_state(self.manual_override_change, zone['manual_override'])
                except KeyError:
                    pass

                if self.Common_Zone_Flag and self.common_zone == zone["zone_switch"]:
                    self.listen_state(self.common_zone_manager, self.common_zone)

                self.automatically_manage_zone(zone)

        except Exception as ex:
            self.queuedlogger(ex)

    def trigger_temp_sensor_changed(self, entity, attribute, old, new, kwargs):
        currenttemp = float(new)
        self.queuedlogger("Upper trigger temp is " + str(self.TriggerTemperatureUpper))
        self.queuedlogger("Lower trigger temp is " + str(self.TriggerTemperatureLower))
        self.queuedlogger("Trigger temperature exceeded, turning on airconditioner auto mode")
        devicestate = self.get_state(self.climatedevice)
        self.climate_entity = self.get_entity(self.climatedevice)
        if devicestate == 'off' and self.climate_entity:
            if currenttemp >= self.TriggerTemperatureUpper:
                self.climate_entity.call_service("set_hvac_mode", hvac_mode="cool")
            elif currenttemp <= self.TriggerTemperatureLower:
                self.climate_entity.call_service("set_hvac_mode", hvac_mode="heat")

    def conditionchanged(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("A condition in one of the zones changed")
        for zone in self.zones:
            self.automatically_manage_zone(zone)

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
            self.common_zone_manager(entity=self.common_zone, attribute=self.common_zone, old=self.common_zone, new=self.common_zone, kwargs=self.Common_Zone_Flag)

    def target_temp_change(self, entity, attribute, old, new, kwargs):
        for zone in self.zones:
            if zone["target_temp"] == entity:
                self.queuedlogger(zone["name"] + ": Wanted temperature in zone changed from " + str(old) + " to " + str(new))
                self.automatically_manage_zone(zone)

    def inroomtempchange(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("Got an inzone temp change from: " + entity)
        for zone in self.zones:
            if zone["local_tempsensor"] == str(entity):
                self.queuedlogger(zone["name"] + ": Current temperature in zone changed from " + str(old) + " to " + str(new))
                newint = float(new)
                oldint = float(old)
                diff = round(newint - oldint, 2)
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

    def common_zone_manager(self, entity, attribute, old, new, kwargs):
        self.queuedlogger("Checking to see if common zone required to be open: " + entity)

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
        if not AZoneOpen and not CommonZoneOpen:
            self.queuedlogger("All zones including common are closed so opening the common zone")
            self.common_zone_open(entity)
        elif not AZoneOpen and CommonZoneOpen:
            self.queuedlogger("Zones are closed, but common is open, so it's good")
        else:
            self.queuedlogger("At least one zone is open so the Common Zone will be controlled automatically")

    def automatically_manage_zone(self, zone):     
        zonename = zone["name"]
        self.queuedlogger("Auto-managing: " + zonename)

        climate_device_state = self.get_state(self.climatedevice)
        coolingmode = self.heatingorcooling(climate_device_state, zone)
        time.sleep(0.25)

        if climate_device_state == "off":
            self.switchoff(zone)
            return
        
        if self.override_enabled(zone):
            return

        manage = coolingmode in (ACMODE.HEATING, ACMODE.COOLING)
        
        self.queuedlogger(zonename + ": auto control condition is " + str(self.IsConditionMet(zone)))

        if not self.IsConditionMet(zone) and manage:
            self.switchoff(zone)
            return    

        temperature_offsets = self.get_temperature_offsets(zone, climate_device_state)
        wanted_zone_temperature = float(self.get_state(zone["target_temp"]))

        try:
            current_zone_temperature = float(self.get_state(zone["local_tempsensor"]))
            self.queuedlogger(zonename + ": current zone temperature is " + str(current_zone_temperature) + " and wanted temperature is " + str(wanted_zone_temperature)) 
        except:
            current_zone_temperature = wanted_zone_temperature + 5
            self.queuedlogger("Error getting current temperature in " + zone["name"] + " zone. Check the temperature sensor.")
            self.queuedlogger("Setting current zone temperature to " + str(wanted_zone_temperature) + " due to local temp sensor failure")      
        
        maxtemp = wanted_zone_temperature + temperature_offsets[0]
        mintemp = wanted_zone_temperature - temperature_offsets[1]
        
        self.queuedlogger(zonename + ": Desired temperature range is: " + str(mintemp) + " to " + str(maxtemp))

        if coolingmode == ACMODE.OFF:
            self.switchoff(zone)
        elif coolingmode == ACMODE.COOLING:
            if current_zone_temperature >= maxtemp:
                self.switchon(zone)
            elif current_zone_temperature <= mintemp:
                self.switchoff(zone)
        elif coolingmode == ACMODE.HEATING:
            if current_zone_temperature <= mintemp:
                self.switchon(zone)
            elif current_zone_temperature >= maxtemp:
                self.switchoff(zone)

    def switchoff(self, zone):
        if self.get_state(zone["zone_switch"]) != "off":
            self.turn_off(zone["zone_switch"])
            self.queuedlogger("Switching " + zone["name"] + " off")

    def switchon(self, zone):
        if self.get_state(zone["zone_switch"]) != "on":
            self.turn_on(zone["zone_switch"])
            self.queuedlogger("Switching " + zone["name"] + " on")
        
    def queuedlogger(self, message):
        try:
            self.log("Smarter Zones: " + message)
        except Exception as ex:
            self.error("Error writing to log: " + str(ex))

    def override_enabled(self, zone):
        try:
            state = self.get_state(zone["manual_override"])
            if state == "on":
                self.queuedlogger("Manual override is enabled for: " + zone["name"])
                return True
        except KeyError:
            return False

    def get_temperature_offsets(self, zone, climate_device_state):
        try:
            cooling_offset = zone.get("cooling_offset", self.COOLING_OFFSET_DEFAULT)
            heating_offset = zone.get("heating_offset", self.HEATING_OFFSET_DEFAULT)
        except KeyError:
            cooling_offset = self.COOLING_OFFSET_DEFAULT
            heating_offset = self.HEATING_OFFSET_DEFAULT

        if "cool" in climate_device_state.lower():
            return cooling_offset
        elif "heat" in climate_device_state.lower():
            return heating_offset
        else:
            return self.COOLING_OFFSET_DEFAULT

    def IsConditionMet(self, zone):
        try:
            for item in zone["conditions"]:
                entity = item["entity"]
                entity_state = str(self.get_state(entity)).lower()
                condstate = str(item["state"]).lower()
                if entity_state != condstate:
                    self.queuedlogger("Condition not met: " + entity + ". Current state: " + entity_state + ", required state: " + condstate)
                    return False
        except KeyError:
            return True
        return True

    def heatingorcooling(self, climate_device_state, zone):
        if "cool" in climate_device_state.lower():
            return ACMODE.COOLING
        elif "heat" in climate_device_state.lower():
            return ACMODE.HEATING
        elif climate_device_state.lower() == "off":
            return ACMODE.OFF
        else:
            return ACMODE.OTHER

    def common_zone_open(self, entity):
        self.queuedlogger("Opening Common Zone")
        if self.get_state(entity) == "off":
            self.turn_on(entity)
