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

class SmarterZones(hass.Hass):
    """
    SmarterZones is an AppDaemon app to manage climate zones using Home Assistant.
    """

    COOLING_OFFSET_DEFAULT = [0.3, 0.3]
    HEATING_OFFSET_DEFAULT = [0.3, 0.3]
    TriggerTemperatureUpper = 0
    TriggerTemperatureLower = 0

    def initialize(self):
        """Initialize the SmarterZones app."""
        try:
            self.Common_Zone_Flag = False
            self.climatedevice = self.args.get('climatedevice')
            self.exterior_temperature = self.args.get('exteriortempsensor')
            self.forceautofan = self.args.get('force_auto_fan', False)

            self.listen_state(self.climate_device_change, self.climatedevice)
            self.listen_state(self.outside_climate_change, self.exterior_temperature)
            if self.forceautofan:
                self.listen_state(self.climate_fan_change, self.climatedevice, attribute="fan_mode")

            self.setup_zones()
        except Exception as ex:
            self.log_error(ex)

    def setup_zones(self):
        """Setup the zones and their listeners."""
        try:
            self.zones = self.args.get('zones', [])

            self.setup_common_zone()
            self.setup_trigger_sensor()

            for zone in self.zones:
                self.setup_zone_listeners(zone)
                self.automatically_manage_zone(zone)
        except Exception as ex:
            self.log_error(ex)

    def setup_common_zone(self):
        """Setup the common zone if available."""
        try:
            self.common_zone = self.args['common_zone_switch']
            self.Common_Zone_Flag = True
        except KeyError:
            self.log_info("No common zone found")
            self.Common_Zone_Flag = False

    def setup_trigger_sensor(self):
        """Setup the trigger temperature sensor if available."""
        try:
            self.trigger_temp_sensor = self.args['trigger_temp_sensor']
            self.TriggerTemperatureUpper = self.args['trigger_temp_upper']
            self.TriggerTemperatureLower = self.args['trigger_temp_lower']
            self.listen_state(self.trigger_temp_sensor_changed, self.trigger_temp_sensor)
            self.log_info(f"Trigger sensor detected, will automatically turn on airconditioner when temp exceeds: {self.TriggerTemperatureUpper}")
        except KeyError:
            self.log_info("No trigger threshold entity available")

    def setup_zone_listeners(self, zone):
        """Setup listeners for a zone."""
        self.listen_state(self.target_temp_change, zone['target_temp'])
        self.listen_state(self.in_room_temp_change, zone['local_tempsensor'])

        for condition in zone.get("conditions", []):
            entity = condition["entity"]
            self.listen_state(self.condition_changed, entity)

        if 'manual_override' in zone:
            self.listen_state(self.manual_override_change, zone['manual_override'])

        if self.Common_Zone_Flag and self.common_zone == zone["zone_switch"]:
            self.listen_state(self.common_zone_manager, self.common_zone)

    def trigger_temp_sensor_changed(self, entity, attribute, old, new, kwargs):
        """Handle changes in the trigger temperature sensor."""
        current_temp = float(new)
        self.log_info(f"Upper trigger temp is {self.TriggerTemperatureUpper}")
        self.log_info(f"Lower trigger temp is {self.TriggerTemperatureLower}")
        self.log_info("Trigger temperature exceeded, turning on airconditioner auto mode")

        device_state = self.get_state(self.climatedevice)
        self.climate_entity = self.get_entity(self.climatedevice)

        if device_state == 'off' and self.climate_entity:
            if current_temp >= self.TriggerTemperatureUpper:
                self.climate_entity.call_service("set_hvac_mode", hvac_mode="cool")
            elif current_temp <= self.TriggerTemperatureLower:
                self.climate_entity.call_service("set_hvac_mode", hvac_mode="heat")

    def condition_changed(self, entity, attribute, old, new, kwargs):
        """Handle changes in zone conditions."""
        self.log_info("A condition in one of the zones changed")
        for zone in self.zones:
            self.automatically_manage_zone(zone)

    def climate_fan_change(self, entity, attribute, old, new, kwargs):
        """Handle changes in the climate device's fan mode."""
        is_on = self.get_state(entity)
        if is_on != "off" and "auto" not in self.get_state(entity, attribute="fan_modes").lower():
            self.call_service("climate/set_fan_mode", entity_id=self.climatedevice, fan_mode=f"{new}/Auto")

    def climate_device_change(self, entity, attribute, old, new, kwargs):
        """Handle changes in the climate device's state."""
        self.log_info("Climate device change state. Setting up zones appropriately.")
        for zone in self.zones:
            self.automatically_manage_zone(zone)

        if self.Common_Zone_Flag:
            self.log_info("Common zone enabled, better set it up")
            self.common_zone_manager(entity=self.common_zone, attribute=self.common_zone, old=self.common_zone, new=self.common_zone, kwargs=self.Common_Zone_Flag)

    def target_temp_change(self, entity, attribute, old, new, kwargs):
        """Handle changes in the target temperature."""
        for zone in self.zones:
            if zone["target_temp"] == entity:
                self.log_info(f"{zone['name']}: Wanted temperature in zone changed from {old} to {new}")
                self.automatically_manage_zone(zone)

    def in_room_temp_change(self, entity, attribute, old, new, kwargs):
        """Handle changes in the in-room temperature sensor."""
        self.log_info(f"Got an in-zone temp change from: {entity}")
        for zone in self.zones:
            if zone["local_tempsensor"] == entity:
                self.log_info(f"{zone['name']}: Current temperature in zone changed from {old} to {new}")
                self.automatically_manage_zone(zone)

    def manual_override_change(self, entity, attribute, old, new, kwargs):
        """Handle changes in the manual override switch."""
        for zone in self.zones:
            if zone["manual_override"] == entity:
                self.log_info(f"{zone['name']}: manual override switch changed from {old} to {new}")
                self.automatically_manage_zone(zone)

    def common_zone_manager(self, entity, attribute, old, new, kwargs):
        """Manage the common zone based on the state of other zones."""
        self.log_info(f"Checking to see if common zone required to be open: {entity}")

        zone_open = any(self.get_state(zone["zone_switch"]) == "on" for zone in self.zones if self.common_zone != zone["zone_switch"])
        common_zone_open = self.get_state(self.common_zone) == "on"

        if not zone_open and not common_zone_open:
            self.log_info("All zones including common are closed, so opening the common zone")
            self.common_zone_open(entity)
        elif not zone_open and common_zone_open:
            self.log_info("Zones are closed, but common is open, so it's good")
        else:
            self.log_info("At least one zone is open, so the Common Zone will be controlled automatically")

    def automatically_manage_zone(self, zone):
        """Automatically manage a zone based on its conditions and temperatures."""
        zonename = zone["name"]
        self.log_info(f"Auto-managing: {zonename}")

        climate_device_state = self.get_state(self.climatedevice)
        cooling_mode = self.heating_or_cooling(climate_device_state, zone)
        time.sleep(0.25)

        if climate_device_state == "off":
            self.switch_off(zone)
            return
        
        if self.override_enabled(zone):
            return

        manage = cooling_mode in {ACMODE.HEATING, ACMODE.COOLING}
        
        self.log_info(f"{zonename}: auto control condition is {self.is_condition_met(zone)}")

        if not self.is_condition_met(zone) and manage:
            self.switch_off(zone)
            return    

        temperature_offsets = self.get_temperature_offsets(zone, climate_device_state)
        wanted_zone_temperature = float(self.get_state(zone["target_temp"]))

        try:
            current_zone_temperature = float(self.get_state(zone["local_tempsensor"]))
            self.log_info(f"{zonename}: current zone temperature is {current_zone_temperature} and wanted temperature is {wanted_zone_temperature}")
        except:
            current_zone_temperature = wanted_zone_temperature + 5
            self.log_info(f"Error getting current temperature in {zone['name']} zone. Check the temperature sensor.")
            self.log_info(f"Setting current zone temperature to {wanted_zone_temperature} due to local temp sensor failure")
        
        max_temp = wanted_zone_temperature + temperature_offsets[0]
        min_temp = wanted_zone_temperature - temperature_offsets[1]
        
        self.log_info(f"{zonename}: Desired temperature range is: {min_temp} to {max_temp}")

        if cooling_mode == ACMODE.OFF:
            self.switch_off(zone)
        elif cooling_mode == ACMODE.COOLING:
            if current_zone_temperature >= max_temp:
                self.switch_on(zone)
            elif current_zone_temperature <= min_temp:
                self.switch_off(zone)
        elif cooling_mode == ACMODE.HEATING:
            if current_zone_temperature <= min_temp:
                self.switch_on(zone)
            elif current_zone_temperature >= max_temp:
                self.switch_off(zone)

    def switch_off(self, zone):
        """Switch off a zone."""
        if self.get_state(zone["zone_switch"]) != "off":
            self.turn_off(zone["zone_switch"])
            self.log_info(f"Switching {zone['name']} off")

    def switch_on(self, zone):
        """Switch on a zone."""
        if self.get_state(zone["zone_switch"]) != "on":
            self.turn_on(zone["zone_switch"])
            self.log_info(f"Switching {zone['name']} on")
        
    def log_info(self, message):
        """Log an info message."""
        self.log(f"Smarter Zones: {message}")

    def log_error(self, error):
        """Log an error message."""
        self.error(f"Smarter Zones Error: {error}")

    def override_enabled(self, zone):
        """Check if manual override is enabled for a zone."""
        try:
            state = self.get_state(zone["manual_override"])
            if state == "on":
                self.log_info(f"Manual override is enabled for: {zone['name']}")
                return True
        except KeyError:
            return False

    def get_temperature_offsets(self, zone, climate_device_state):
        """Get the temperature offsets for a zone."""
        cooling_offset = zone.get("cooling_offset", self.COOLING_OFFSET_DEFAULT)
        heating_offset = zone.get("heating_offset", self.HEATING_OFFSET_DEFAULT)

        if "cool" in climate_device_state.lower():
            return cooling_offset
        elif "heat" in climate_device_state.lower():
            return heating_offset
        else:
            return self.COOLING_OFFSET_DEFAULT

    def is_condition_met(self, zone):
        """Check if the conditions for a zone are met."""
        for condition in zone.get("conditions", []):
            entity = condition["entity"]
            entity_state = str(self.get_state(entity)).lower()
            condition_state = str(condition["state"]).lower()
            if entity_state != condition_state:
                self.log_info(f"Condition not met: {entity}. Current state: {entity_state}, required state: {condition_state}")
                return False
        return True

    def heating_or_cooling(self, climate_device_state, zone):
        """Determine if the system is in heating or cooling mode."""
        if "cool" in climate_device_state.lower():
            return ACMODE.COOLING
        elif "heat" in climate_device_state.lower():
            return ACMODE.HEATING
        elif climate_device_state.lower() == "off":
            return ACMODE.OFF
        else:
            return ACMODE.OTHER

    def common_zone_open(self, entity):
        """Open the common zone."""
        self.log_info("Opening Common Zone")
        if self.get_state(entity) == "off":
            self.turn_on(entity)
