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
    """
    SmarterZones is an AppDaemon app to manage climate zones using Home Assistant.
    """

    COOLING_OFFSET_DEFAULT = [0.3, 0.3]
    HEATING_OFFSET_DEFAULT = [0.3, 0.3]
    TriggerTemperatureUpper = 31
    TriggerTemperatureLower = 17

    FAN_SPEEDS = {
        "high": 5,   # Temperature difference greater than or equal to 5°C
        "medium": 3, # Temperature difference between 3°C and 5°C
        "low": 1     # Temperature difference between 1°C and 3°C
    }

    def initialize(self):
        """Initialize the SmarterZones app."""
        """Test Copy"""
        try:
            self.log_info("Setting up")
            self.Common_Zone_Flag = False
            self.climatedevice = self.args.get('climatedevice')
            self.exterior_temperature = self.args.get('exteriortempsensor')
            self.climate_entity = self.get_entity(self.climatedevice)
            self.listen_state(self.climate_device_change, self.climatedevice)
            self.forceautofan = self.args.get('force_auto_fan', False)
            self.auto_on_from_sensor_temp = self.args.get('auto_control_on_sensor_temperature', False)
            if self.auto_on_from_sensor_temp:
                self.trigger_temperature_sensor = self.args.get('trigger_temp_sensor')
                self.TriggerTemperatureUpper = self.args.get('trigger_temp_upper', 31)
                self.TriggerTemperatureLower = self.args.get('trigger_temp_lower', 17)
                self.listen_state(self.trigger_climate_change, self.trigger_temperature_sensor)
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

        except KeyError:
            self.log_info("No trigger threshold entity available")

    def get_common_zone(self):
        """Find the zone that matches the common zone switch."""
        for zone in self.zones:
            if zone["zone_switch"] == self.common_zone:
                return zone
        return None

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

    def condition_changed(self, entity, attribute, old, new, kwargs):
        """Handle changes in zone conditions."""
        self.log_info("A condition in one of the zones changed")
        for zone in self.zones:
            self.automatically_manage_zone(zone)

    def climate_fan_change(self, entity, attribute, old, new, kwargs):
        """Handle changes in the climate device's fan mode."""
        is_on = self.get_state(entity)
        if is_on != "off" and "/auto" not in new.lower():
            fan_modes = self.get_state(entity, attribute="fan_modes")
            # if fan_modes and "auto" not in fan_modes.lower():
            try:
                self.log_info(f"Changing fan mode to {new}/Auto for {entity}")
                self.climate_entity.call_service("set_fan_mode", fan_mode=f"{new}/Auto")
            except Exception as e:
                self.log_error(f"Error changing fan mode: {e}")

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
    
        # Check if any zone other than the common zone is on
        zone_open = any(self.get_state(zone["zone_switch"]) == "on" for zone in self.zones if self.common_zone != zone["zone_switch"])
        common_zone_open = self.get_state(self.common_zone) == "on"

        common_zone = self.get_common_zone()
        if not common_zone:
            self.log_error("Common zone configuration not found")
            return


        try:
            common_zone_temperature = float(self.get_state(common_zone["local_tempsensor"]))
            common_zone_target_temp = float(self.get_state(common_zone["target_temp"]))
        except KeyError:
            self.log_error("Common zone temperature sensor or target temperature not specified")
            return

        # Calculate temperature offsets
        temperature_offsets = self.get_temperature_offsets(common_zone, self.get_state(self.climatedevice))
        max_temp = common_zone_target_temp + temperature_offsets[0]
        min_temp = common_zone_target_temp - temperature_offsets[1]
    
        self.log_info(f"Common zone current temperature: {common_zone_temperature}")
        self.log_info(f"Common zone desired temperature range: {min_temp} to {max_temp}")

        # If no other zones are open and the common zone is not open, open the common zone
        if not zone_open and not common_zone_open:
            self.log_info("All zones including common are closed, so opening the common zone")
            self.common_zone_open(entity)
        # If no other zones are open and the common zone is already open, log that it's good
        elif not zone_open and common_zone_open:
            self.log_info("Zones are closed, but common is open, so it's good")
        # If at least one other zone is open and the common zone is open, close the common zone
        elif zone_open and common_zone_open:
            if common_zone_temperature > max_temp or common_zone_temperature < min_temp:
                self.log_info("At least one zone is open and common zone temperature is outside the desired range, so closing the Common Zone")
                self.common_zone_close(entity)
            else:
                self.log_info("At least one zone is open, but common zone temperature is within the desired range, so keeping the Common Zone open")
        # If at least one other zone is open, log that the common zone will be controlled automatically
        else:
            self.log_info("At least one zone is open, so the Common Zone will be controlled automatically")


    def common_zone_close(self, entity):
        """Close the common zone."""
        self.log_info("Closing Common Zone")
        if self.get_state(entity) == "on":
            self.turn_off(entity)


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
        self.log(f"{message}", level ="INFO")

    def log_error(self, error):
        """Log an error message."""
        self.log(f"{error}", level = "ERROR")

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
            condition_state = str(condition["targetstate"]).lower()
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

    def trigger_climate_change(self, entity, attribute, old, new, kwargs):
        """Handle changes in the exterior temperature sensor."""
        current_trigger_temp = float(new)
        old_trigger_temp = float(old)
        self.climate_entity = self.get_entity(self.climatedevice)
        self.log_info(f"Monitored temperature changed from {old_trigger_temp} to {current_trigger_temp}")
        if self.auto_on_from_sensor_temp:
            if current_trigger_temp > self.TriggerTemperatureUpper:
                self.log_info("Temperature is very high, consider turning on cooling")
                self.climate_entity.call_service("turn_on")
                self.climate_entity.call_service("set_hvac_mode", hvac_mode="cool")
            elif current_trigger_temp < self.TriggerTemperatureLower:
                self.log_info("Temperature is very low, consider turning on heating")
                self.climate_entity.call_service("turn_on")
                self.climate_entity.call_service("set_hvac_mode", hvac_mode="heat")
            else:
                self.log_info("Temperature is moderate, no immediate action required")   
        else:
            self.log_info("We don't want to turn on the thermostat automatically based on temperature, so ignoring.")

    def adjust_fan_speed(self, climate_device, current_temp, desired_temp):
        """Adjust the fan speed of the climate device based on the temperature difference."""
        temp_diff = abs(desired_temp - current_temp)
    
        if temp_diff >= self.FAN_SPEEDS["high"]:
            fan_speed = "High"
        elif temp_diff >= self.FAN_SPEEDS["medium"]:
            fan_speed = "Medium"
        elif temp_diff >= self.FAN_SPEEDS["low"]:
            fan_speed = "Low"
        else:
            fan_speed = "Auto"  # Default to auto or lowest setting

        self.log_info(f"Adjusting fan speed to {fan_speed} based on temperature difference of {temp_diff} degrees")
    
        # Set the new fan speed
        self.climate_entity.call_service("set_fan_mode", fan_mode=fan_speed)

    def adjust_target_temperature(self, climate_device, current_temp, desired_temp):
        """Adjust the target temperature of the climate device to reach the desired temperature more quickly."""
        max_boost = 5  # Maximum temperature adjustment (degrees)
        min_boost = 1  # Minimum temperature adjustment (degrees)
        threshold = 0.5  # Acceptable range around the desired temperature

        # Calculate temperature difference
        temp_diff = desired_temp - current_temp

        # Determine the boost amount
        if abs(temp_diff) > threshold:
            boost_amount = max(min_boost, min(max_boost, abs(temp_diff)))
        else:
            boost_amount = 0

        # Adjust target temperature based on heating or cooling mode
        if temp_diff > 0:
            # Heating
            new_target_temp = desired_temp + boost_amount
        else:
            # Cooling
            new_target_temp = desired_temp - boost_amount

        new_target_temp = max(17, min(31, new_target_temp))

        # Apply limits to ensure comfort and safety
        new_target_temp = max(self.TriggerTemperatureLower, min(self.TriggerTemperatureUpper, new_target_temp))

        self.log_info(f"Adjusting target temperature from {desired_temp} to {new_target_temp} to reach {current_temp} quickly")
    
        # Set the new target temperature
        self.call_service("climate/set_temperature", entity_id=climate_device, temperature=new_target_temp)
