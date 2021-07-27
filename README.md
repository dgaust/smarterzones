# smarterzones
An appdaemon app to automatically control climate zones (on/off) only depending on localised temperatures. Supports multiple conditions being set before action is taken (ALL conditions must be met), and manual override with an input_boolean

Here is what every option means:

### Minimum Configuration

| Name                |   Type       | Default      | Description                                                             |
| ------------------- | :----------: | ------------ | ----------------------------------------------------------------------- |
| `climatedevice`     | `string`     | **Required** | An entity_id within the `climate` domain.                               |
| `exteriortempsensor`| `string`     | **Required** | An entity_id with a temperature value as state                          |
| `common_zone_switch`| `string`     | Optional     | If your AC requires a common zone, specify the switch here, and the zone will always be on. This is an alternate approach to leaving the zone out of the list                         |
| `force_auto_fan`    | `bool`       | False        | Whether the fan should be set to an auto mode.                          |
| `zone`              | `object`     | **Required** | Zone objects that will be controlled                                    |

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
| `upperbound`   | `float`   | **Required**     | Value above setpoint that local_tempsensor can reach. Required if coolingoffset or heatingoffset is specified.                |
| `lowerbound`   | `float`   | **Required**     | Value below setpoint that local_tempsensor can reach. Required if coolingoffset or heatingoffset is specified.                |                 
 
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
  exteriortempsensor: sensor.bellambi_temp
  force_auto_fan: true
  zones:
    - name: "Alex Smart Zone"
      zone_switch: switch.daikin_ac_alex
      local_tempsensor: sensor.alex_temp_sensor_sonoff
      manual_override: input_boolean.alexsmartzone
      target_temp: input_number.alex_temp_setting
      coolingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      heatingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      conditions:
        - entity: binary_sensor.alex_window_sensor_2
          targetstate: "off"
    - name: "Bridgets Smart Zone"
      zone_switch: switch.daikin_ac_bridget
      local_tempsensor: sensor.bridgets_temperature_sensor
      manual_override: input_boolean.bridgetsmartzone
      target_temp: input_number.bridget_temp_setting
      coolingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      heatingoffset:
        upperbound: 0.3
        lowerbound: 0.3
      conditions:
        - entity: binary_sensor.bridget_window_sensor_2
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
