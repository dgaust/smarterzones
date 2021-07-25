# smarterzones
An appdaemon app to automatically control climate zones (on/off) only depending on localised temperatures. Supports multiple conditions being set before action is taken (ALL conditions must be met), and manual override with an input_boolean

Here is what every option means:

### Minimum Configuration

| Name               |   Type       | Default      | Description                                                             |
| ------------------ | :----------: | ------------ | ----------------------------------------------------------------------- |
| `climatedevice`    | `string`     | **Required** | An entity_id within the `climate` domain.                               |
| `zoneswitch`       | `string`     | **Required** | An entity_id within the `switch` domain.                                |
| `localtempsensor`  | `string`     | **Required** | An entity_id that has a temperature as its state.                       |
| `localtargettemp`  | `string`     | **Required** | An entity_id that has a temperature or number as its state.             |
| `manualoverride`   | `string`     | Optional     | Entity_id of an input_boolean                                           |
| `autofanoverride`  | `bool`       | Optional     | Set fan to matching Auto mode (Low/Auto, Mid/Auto, High/Auto) on change |
| `coolingoffset`    | `object`     | Optional     | Temperature offset object. If no object provided defaults to 1.0        |
| `heatingoffset`    | `object`     | Optional     | Temperature offset object. If no object provided defaults to 1.0        |
| `conditions`       | `object`     | Optional     | Condition object. Multiple conditions can be specified                  |


### Temperature Offset Object                                                                                    
| Name           |   Type    | Default          | Description                                                             |
| -------------- | :-------: | ---------------- | ----------------------------------------------------------------------- |
| `upperbound`   | `float`   | **Required**     | Value above setpoint that localtempsensor can reach. Required if coolingoffset or heatingoffset is specified.                |
| `lowerbound`   | `float`   | **Required**     | Value below setpoint that localtempsensor can reach. Required if coolingoffset or heatingoffset is specified.                |                 
 
### Condition Object                                                                                               
| Name           |   Type    | Default          | Description                                                             |
| -------------- | :-------: | ---------------- | ----------------------------------------------------------------------- |
| `entity`       | `string`  | **Required**     | Entity_id of the entity to match. Required if conditions is specified.  |
| `targetstate`  | `string`  | **Required**     | The state the entity must be in for the automtic control to work. Required if conditions is specified.       |

A typical example of the configuration in the apps.yaml file will look like

```
guestroomsmartzone:
  module: smartzone
  class: smartzone
  entities:
    climatedevice: climate.daikin_ac
    zoneswitch: switch.daikin_ac_guest
    localtempsensor: sensor.temperature_18
    manualoverride: input_boolean.guestairconzone
    autofanoverride: True
    coolingoffset:
      upperbound: 1.5
      lowerbound: 0.5
    heatingoffset:
      upperbound: 0.5
      lowerbound: 0.5
    conditions:
      - entity: binary_sensor.spare_bedroom_window
        targetstate: "off"
      - entity: input_boolean.guest_mode
        targetstate: "on"
```
