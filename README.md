# smarterzones
An appdaemon app to automatically control climate zones (on/off) only depending on localised temperatures. Supports multiple conditions being set before action is taken (ALL conditions must be met), and manual override with an input_boolean

Here is what every option means:

### Minimum Configuration

| Name                  |   Type       | Default      | Description                                                             |
| --------------------- | :----------: | ------------ | ----------------------------------------------------------------------- |
| `climatedevice`       | `string`     | **Required** | An entity_id within the `climate` domain.                               |
| `exteriortempsensor`  | `string`     | **Required** | An entity_id with a temperature value as state                          |
| `common_zone_switch`  | `string`     | Optional     | If your AC requires a common zone, specify the switch entity here, and the zone will always be on. This is an alternate approach to leaving the zone out of the list                         |
| `force_auto_fan`      | `bool`       | False        | Whether the fan should be set to an auto mode.                          |
| `auto_control_on_sensor_temperature` | `bool`     | False        | Whether the climate device could be turned on if a specific temperature is passed by the tigger sensor                           |
| `trigger_temp_sensor` | `string`     | False        | An entity_id with a temperature value as state                           |
| `trigger_temp_upper`  | `float`      | False        | Temperature which if trigger sensor goes *above* will turn the air-con on                          |
| `trigger_temp_lower`  | `float`      | False        | Temperature which if trigger sensor goes *below* will turn the air-con on                          |
| `zone`                | `object`     | **Required** | Zone objects that will be controlled                                    |

### Zone Object

| Name                |   Type       | Default      | Description                                                              |
| ------------------- | :----------: | ------------ | ------------------------------------------------------------------------ |
| `name`     | `string`     | **Required** | Name of the zone                                                         |
| `zone_switch`       | `string`     | **Required** | An entity_id within the `switch` domain.                                 |
| `local_tempsensor`  | `string`     | **Required** | An entity_id that has a temperature as its state.                        |
| `target_temp`       | `string`     | **Required** | An entity_id that has a temperature or number as its state.              |
| `manual_override`   | `string`     | Optional     | Entity_id of an input_boolean                                            |
| `coolingoffset`     | `object`     | Optional     | Temperature offset object. If no object provided defaults to 0.3         |
| `heatingoffset`     | `object`     | Optional     | Temperature offset object. If no object provided defaults to 0.3         |
| `conditions`        | `object`     | Optional     | Condition object. Multiple conditions can be specified                   |


### Temperature Offset Object                                                                                    
| Name           |   Type    | Default          | Description                                                             |
| -------------- | :-------: | ---------------- | ----------------------------------------------------------------------- |
| `upperbound`   | `float`   | **Required**     | Value above setpoint that local_tempsensor can reach. Required if coolingoffset or heatingoffset is specified. This will be the amount over the preferred temperature (ie. 20 degrees + upperbound)                |
| `lowerbound`   | `float`   | **Required**     | Value below setpoint that local_tempsensor can reach. Required if coolingoffset or heatingoffset is specified. This will be the amount below the preferred temperature (ie. 20 degrees - lowerbound)                      |                 
 
### Condition Object                                                                                               
| Name           |   Type    | Default          | Description                                                             |
| -------------- | :-------: | ---------------- | ----------------------------------------------------------------------- |
| `entity`       | `string`  | **Required**     | Entity_id of the entity to match. Required if conditions is specified.  |
| `targetstate`  | `string`  | **Required**     | The state the entity must be in for the automtic control to work. Required if conditions is specified.       |

A typical example of the configuration in the apps.yaml file will look like

```
smarterzones:
  module: smarterzones
  class: smarterzones
  climatedevice: climate.daikin_ac
  common_zone_switch: switch.daikin_living
  exteriortempsensor: sensor.bellambi_temp
  force_auto_fan: true
  trigger_temp_sensor: sensor.living_room_temperature
  trigger_temp_upper: 27
  trigger_temp_lower: 18
  zones:
    - name: "A Smart Zone"
      zone_switch: switch.daikin_ac_a
      local_tempsensor: sensor.a_temp_sensor_sonoff
      manual_override: input_boolean.alexsmartzone
      target_temp: input_number.a_temp_setting
      coolingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      heatingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      conditions:
        - entity: binary_sensor.a_window_sensor_2
          targetstate: "off"
    - name: "B Smart Zone"
      zone_switch: switch.daikin_ac_b
      local_tempsensor: sensor.b_temperature_sensor
      manual_override: input_boolean.bridgetsmartzone
      target_temp: input_number.b_temp_setting
      coolingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      heatingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      conditions:
        - entity: binary_sensor.b_window_sensor_2
          targetstate: "off"
    - name: "Lounge Smart Zone"
      zone_switch: switch.daikin_ac_living
      local_tempsensor: sensor.lounge_average_temperature
      manual_override: input_boolean.loungesmartzone
      target_temp: input_number.lounge_room_temp
      coolingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      heatingoffset:
        upperbound: 0.3
        lowerbound: 0.3
    - name: "Guest Bedroom"
      zone_switch: switch.daikin_ac_guest
      local_tempsensor: sensor.spare_bedroom_temperature_sensor
      manual_override: input_boolean.guestsmartzone
      target_temp: input_number.guest_room_temp
      coolingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      heatingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      conditions:
        - entity: binary_sensor.spare_room_window_sensor
          targetstate: "off"
        - entity: input_boolean.guest_mode
          targetstate: "on"
    - name: "Master Bedroom"
      zone_switch: switch.daikin_ac_master
      local_tempsensor: sensor.master_bedroom_temperature_2
      manual_override: input_boolean.mastersmartzone
      target_temp: input_number.master_bedroom
      coolingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      heatingoffset:
        upperbound: 0.3
        lowerbound: 0.3
    - name: "Media Room"
      zone_switch: switch.daikin_ac_media
      local_tempsensor: sensor.media_room_temperature_sensor
      manual_override: input_boolean.mediasmartzone
      target_temp: input_number.media_room_temp
      coolingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      heatingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      conditions:
        - entity: remote.media_room
          targetstate: "on"
```
