# Device Template Documentation

This document explains the structure and configuration options for Modbus Manager device templates.

## Table of Contents

1. [Template Header](#template-header)
2. [Dynamic Configuration](#dynamic-configuration)
3. [Sensors](#sensors)
4. [Controls](#controls)
5. [Binary Sensors](#binary-sensors)
6. [Calculated Sensors](#calculated-sensors)
7. [Value Processing](#value-processing)
8. [Examples](#examples)

---

## Template Header

Every template file must start with header information that identifies the device:

```yaml
name: "Device Name"                    # Required: Display name
version: 1                             # Required: Template version number
description: "Device description"      # Optional: Detailed description
manufacturer: "Manufacturer Name"      # Optional: Device manufacturer
model: "Model Series"                  # Optional: Device model/series
type: "device_type"                    # Optional: Device type (e.g., "PV_Hybrid_Inverter", "ev_charger")
default_prefix: "device_prefix"        # Optional: Default prefix for entity IDs
default_slave_id: 1                    # Optional: Default Modbus slave ID
firmware_version: "1.0.0"             # Optional: Default firmware version

# Available firmware versions for user selection during setup
available_firmware_versions:
  - "1.0.0"
  - "1.1.18"
  - "2.0.0"
  - "Latest"
```

### Header Field Descriptions

- **`name`**: The display name shown in the Home Assistant configuration UI
- **`version`**: Template version number (incremented when template is updated)
- **`description`**: Extended description of the device and its capabilities
- **`manufacturer`**: Company that produces the device
- **`model`**: Specific model or model series
- **`type`**: Device category (used for grouping and organization)
- **`default_prefix`**: Prefix used for entity IDs (e.g., "SG" creates `sensor.sg1_temperature`)
- **`default_slave_id`**: Default Modbus slave/unit ID
- **`firmware_version`**: Default firmware version if none specified
- **`available_firmware_versions`**: List of firmware versions available for user selection during setup

---

## Dynamic Configuration

Dynamic configuration allows templates to adapt based on user-selected parameters. This enables one template to support multiple device variants.

```yaml
dynamic_config:
  # Simple option selection
  phases:
    description: "Number of phases"
    options: [1, 3]
    default: 3

  # Numeric option selection
  max_current:
    description: "Maximum current per phase"
    options: [6, 10, 16, 20, 32]
    default: 16

  # String option selection
  connection_type:
    description: "Connection type"
    options: ["LAN", "WiFi"]
    default: "LAN"

  # Firmware-based sensor replacements
  firmware_version:
    description: "Firmware version string"
    default: "1.0.0"
    sensor_replacements:
      battery_power_raw:
        "2.0.0":
          data_type: "int16"
          scale: 1
          description: "Battery power signed in firmware v2+"

  # Connection-based sensor availability
  connection_type:
    description: "Connection type"
    options: ["LAN", "WINET"]
    default: "LAN"
    sensor_availability:
      lan_only_sensors:
        - "monthly_pv_generation_01_january"
        - "yearly_pv_generation_2023"
      winet_only_sensors:
        - "some_winet_sensor"
```

### Dynamic Config Features

1. **Option Selection**: User chooses from predefined options during setup
2. **Sensor Filtering**: Sensors can be conditionally included/excluded based on configuration
3. **Sensor Replacements**: Sensor parameters can change based on firmware version
4. **Sensor Availability**: Sensors can be marked as available only for specific connection types

---

## Sensors

Sensors read data from Modbus registers and expose them as Home Assistant sensor entities.

### Basic Sensor Configuration

```yaml
sensors:
  - name: "Temperature"
    unique_id: "temperature"
    address: 5007
    input_type: "input"
    data_type: "int16"
    scan_interval: 10
    unit_of_measurement: "°C"
    device_class: "temperature"
    state_class: "measurement"
    scale: 0.1
    group: "PV_status"
    icon: "mdi:thermometer"
```

### Required Fields

- **`name`**: Display name for the sensor (shown in Home Assistant)
- **`address`**: Modbus register address (0-based, matches Modbus protocol)

### Optional Fields

#### Modbus Configuration

- **`unique_id`**: Unique identifier for the sensor (used for entity ID generation)
- **`device_address`**: Optional different slave ID for this sensor (default: uses template default)
- **`input_type`**: Register type - `"input"` (read-only) or `"holding"` (read/write)
- **`data_type`**: Data type - `"uint16"`, `"int16"`, `"uint32"`, `"int32"`, `"float32"`, `"float64"`, `"string"`, `"boolean"`
- **`count`**: Number of registers to read (default: 1, required for strings and 32/64-bit values)
- **`scan_interval`**: Update interval in seconds (default: 30)

#### Value Processing

- **`scale`**: Multiplier for numeric values (default: 1.0)
- **`offset`**: Offset value added after scaling (default: 0.0)
- **`precision`**: Decimal places for display (default: 1 for floats, 0 for integers)
- **`multiplier`**: Alternative to scale (default: 1.0)
- **`sum_scale`**: Sum multiple registers with scaling (advanced)

#### Bit Operations

- **`bitmask`**: Apply AND mask (e.g., `0xFF` for lower 8 bits)
- **`bit_position`**: Extract single bit (0-31)
- **`bit_range`**: Extract bit range `[start, end]`
- **`bit_shift`**: Shift bits left (positive) or right (negative)
- **`bit_rotate`**: Rotate bits left (positive) or right (negative)
- **`bits`**: Legacy bit position field

#### Byte Order (32/64-bit values)

- **`byte_order`**: `"big"` (default) or `"little"` endian
- **`swap`**: Swap bytes within words (default: false)

#### String Configuration

- **`encoding`**: String encoding - `"utf-8"` (default), `"ascii"`, `"latin1"`
- **`max_length`**: Maximum string length (None = unlimited)

#### Home Assistant Metadata

- **`unit_of_measurement`**: Unit string (e.g., "°C", "W", "V")
- **`device_class`**: Home Assistant device class (e.g., `"temperature"`, `"power"`, `"voltage"`)
- **`state_class`**: State class - `"measurement"`, `"total"`, `"total_increasing"`
- **`icon`**: Material Design Icon name (e.g., `"mdi:thermometer"`)
- **`group`**: Group identifier for organizing entities
- **`entity_category`**: Category - `"diagnostic"`, `"config"` (optional)

#### Value Mapping (see [Value Processing](#value-processing))

- **`map`**: Direct value-to-text mapping
- **`flags`**: Bit-flag to text mapping (multiple can be active)
- **`options`**: Dropdown options (for select entities)

---

## Controls

Controls are read/write entities that allow interaction with Modbus holding registers.

### Control Types

#### Number Control

```yaml
controls:
  - type: "number"
    name: "Max Current"
    unique_id: "max_current"
    address: 1012
    input_type: "holding"
    data_type: "float32"
    scan_interval: 30
    unit_of_measurement: "A"
    device_class: "current"
    state_class: "measurement"
    min_value: 0
    max_value: 32
    step: 1
    group: "EV_settings"
    icon: "mdi:gauge"
```

#### Select Control

```yaml
controls:
  - type: "select"
    name: "Charging Mode"
    unique_id: "charging_mode"
    address: 2000
    input_type: "holding"
    data_type: "uint16"
    scan_interval: 30
    options:
      0: "Disabled"
      1: "Slow"
      2: "Normal"
      3: "Fast"
    group: "EV_settings"
```

#### Switch Control

```yaml
controls:
  - type: "switch"
    name: "Charging Enabled"
    unique_id: "charging_enabled"
    address: 2001
    input_type: "holding"
    data_type: "uint16"
    scan_interval: 30
    write_value: 1      # Value written when turning switch ON
    write_value_off: 0  # Value written when turning switch OFF
    on_value: 1         # Optional: Value that represents ON state (defaults to write_value)
    off_value: 0        # Optional: Value that represents OFF state (defaults to write_value_off)
    group: "EV_settings"
```

**Switch Configuration Options:**
- **`write_value`**: Value written to register when switch is turned ON (default: 1)
- **`write_value_off`**: Value written to register when switch is turned OFF (default: 0)
- **`on_value`**: (Optional) Value that represents ON state when reading register. If not specified, uses `write_value` as fallback
- **`off_value`**: (Optional) Value that represents OFF state when reading register. If not specified, uses `write_value_off` as fallback

**Example with custom values (0xAA/0x55):**
```yaml
controls:
  - type: "switch"
    name: "Forced Startup Under Low SoC Standby"
    unique_id: "forced_startup_under_low_soc_standby"
    address: 13016
    input_type: "holding"
    data_type: "uint16"
    scan_interval: 30
    write_value: 0xAA      # 170 - Enable
    write_value_off: 0x55  # 85 - Disable
    # on_value and off_value automatically use write_value/write_value_off
    group: "PV_control"
```

**Note:** If `on_value` and `off_value` are not specified, they automatically default to `write_value` and `write_value_off` respectively. This simplifies configuration for most use cases where the written and read values are the same.

#### Button Control

```yaml
controls:
  - type: "button"
    name: "Reset Error"
    unique_id: "reset_error"
    address: 2002
    input_type: "holding"
    data_type: "uint16"
    write_value: 1234
    group: "EV_maintenance"
    icon: "mdi:refresh"
```

#### Text Control

```yaml
controls:
  - type: "text"
    name: "Device Name"
    unique_id: "device_name"
    address: 3000
    input_type: "holding"
    data_type: "string"
    count: 10
    scan_interval: 600
    encoding: "utf-8"
    max_length: 20
    group: "EV_settings"
```

### Control-Specific Fields

- **Number**: `min_value`, `max_value`, `step`
- **Select**: `options` (dictionary mapping values to labels)
- **Switch**: `on_value`, `off_value` (values written when switching)
- **Button**: `write_value` (value written when button pressed)
- **Text**: `encoding`, `max_length`

---

## Binary Sensors

Binary sensors can be defined in templates using calculated templates. They evaluate to `true`/`false` (or `on`/`off`).

```yaml
binary_sensors:
  - name: "Cable Connected"
    unique_id: "cable_connected"
    type: "binary_sensor"
    availability: >-
      {{ not is_state('sensor.{PREFIX}_cable_status', 'unavailable') }}
    state: >-
      {{ states('sensor.{PREFIX}_cable_status') not in ['unavailable', 'unknown', 'no cable'] }}
    device_class: "connectivity"
    group: "EV_charging_status"
    icon: "mdi:cable-data"
```

### Binary Sensor Fields

- **`name`**: Display name
- **`unique_id`**: Unique identifier
- **`type`**: Must be `"binary_sensor"`
- **`state`**: Jinja2 template expression that evaluates to boolean
- **`availability`**: Optional Jinja2 template for entity availability
- **`device_class`**: Home Assistant device class (e.g., `"connectivity"`, `"power"`, `"battery"`)
- **`icon`**: Material Design Icon name
- **`group`**: Group identifier

### Boolean Evaluation

The template expression should evaluate to:
- **`true`/`"on"`/`"true"`/`1`/`"yes"`**: Entity is ON
- **`false`/`"off"`/`"false"`/`0`/`"no"`**: Entity is OFF
- **`"unknown"`/`"unavailable"`/`"none"`/`""`**: Entity is unavailable

---

## Calculated Sensors

Calculated sensors use Jinja2 templates to derive values from other entities.

```yaml
calculated:
  - name: "Total Power"
    unique_id: "total_power"
    type: "sensor"
    state: "{{ (states('sensor.{PREFIX}_power_1') | default(0) | float) + (states('sensor.{PREFIX}_power_2') | default(0) | float) }}"
    unit_of_measurement: "W"
    device_class: "power"
    state_class: "measurement"
    group: "PV_calculated"
```

### Calculated Binary Sensors

```yaml
calculated:
  - name: "Charging Active"
    unique_id: "charging_active"
    type: "binary_sensor"
    state: "{{ states('sensor.{PREFIX}_status') == 'Charging' }}"
    device_class: "power"
    group: "EV_status"
```

### Field Descriptions

- **`name`**: Display name
- **`unique_id`**: Unique identifier
- **`type`**: `"sensor"` or `"binary_sensor"`
- **`state`**: Jinja2 template expression (use `{PREFIX}` placeholder)
- **`unit_of_measurement`**: Unit for sensor type
- **`device_class`**: Home Assistant device class
- **`state_class`**: State class for sensor type
- **`icon`**: Material Design Icon name
- **`group`**: Group identifier

### Template Placeholders

- **`{PREFIX}`**: Replaced with device prefix (e.g., "SG1", "eBox1")

### Example Expressions

```jinja2
# Conditional value
{{ 1 if states('sensor.{PREFIX}_voltage') | float > 230 else 0 }}

# Bitwise operation (for flags-based sensors)
{{ (states('sensor.{PREFIX}_running_state') | int) | bitwise_and(1) == 1 }}

# String comparison
{{ states('sensor.{PREFIX}_status') not in ['unavailable', 'unknown', 'no cable'] }}

# Mathematical calculation
{{ (states('sensor.{PREFIX}_voltage') | default(0) | float) * (states('sensor.{PREFIX}_current') | default(0) | float) }}
```

---

## Value Processing

The Modbus Manager supports three types of value processing that convert raw numeric register values to human-readable text.

### Processing Order

1. **Map** (highest priority) - Direct 1:1 mapping
2. **Flags** (medium priority) - Bit-based evaluation
3. **Options** (lowest priority) - Dropdown options

### 1. Map (Direct Value Mapping)

Direct 1:1 mapping of numeric values to text strings. Used for status codes, error codes, and operating modes.

```yaml
sensors:
  - name: "Status"
    unique_id: "status"
    address: 275
    input_type: "input"
    data_type: "string"
    map:
      A: "not connected"
      B1: "Connected but not ready for charging"
      B2: "Connected ready for charging"
      C1: "Charging without ventilation - not ready"
      C2: "Charging without ventilation - ready"
      D1: "Charging with ventilation - not ready"
      D2: "Charging with ventilation - ready"
      E: "Error"
      F: "EVSE not available"
```

**Result**: If register contains "B2", the sensor state becomes "Connected ready for charging".

### 2. Flags (Bit-Based Evaluation)

Bit-based evaluation where multiple flags can be active simultaneously. Used for status registers with multiple bits or alarm flags.

```yaml
sensors:
  - name: "Running State"
    unique_id: "running_state"
    address: 5001
    input_type: "input"
    data_type: "uint16"
    flags:
      0: "PV Generating"
      1: "Battery Charging"
      2: "Battery Discharging"
      3: "Grid Connected"
      4: "System OK"
```

**Result**: If register value = 5 (binary: `101`), the result would be: "PV Generating, Battery Discharging"

**Note**: For bitwise operations in calculated sensors, the sensor stores both the numeric value (for bitwise operations) and the formatted string (for display). Use `numeric_value` attribute to access the raw numeric value.

### 3. Options (Dropdown Options)

Dropdown options for Select controls. Used for configuration options and selection menus.

```yaml
controls:
  - type: "select"
    name: "Charging Mode"
    unique_id: "charging_mode"
    address: 2000
    input_type: "holding"
    data_type: "uint16"
    options:
      0: "Disabled"
      1: "Slow"
      2: "Normal"
      3: "Fast"
```

---

## Examples

### Complete Example: Simple Temperature Sensor

```yaml
name: "Simple Temperature Sensor"
version: 1
description: "Basic temperature monitoring"
manufacturer: "Generic"
model: "TempSensor"

sensors:
  - name: "Temperature"
    unique_id: "temperature"
    address: 5007
    input_type: "input"
    data_type: "int16"
    scale: 0.1
    scan_interval: 10
    unit_of_measurement: "°C"
    device_class: "temperature"
    state_class: "measurement"
    group: "environment"
    icon: "mdi:thermometer"
```

### Complete Example: EV Charger with Controls

```yaml
name: "EV Charger"
version: 1
description: "EV Charger with control capabilities"
manufacturer: "Generic"
model: "EVCharger"
default_prefix: "EV"
default_slave_id: 1

sensors:
  - name: "Current Phase 1"
    unique_id: "current_phase_1"
    address: 1006
    input_type: "input"
    data_type: "float32"
    scan_interval: 10
    unit_of_measurement: "A"
    device_class: "current"
    state_class: "measurement"
    group: "EV_current"

  - name: "Status"
    unique_id: "status"
    address: 275
    input_type: "input"
    data_type: "string"
    scan_interval: 120
    group: "EV_status"
    map:
      A: "not connected"
      B2: "Connected ready for charging"
      C2: "Charging"

controls:
  - type: "number"
    name: "Max Current"
    unique_id: "max_current"
    address: 1012
    input_type: "holding"
    data_type: "float32"
    scan_interval: 30
    unit_of_measurement: "A"
    device_class: "current"
    min_value: 0
    max_value: 32
    step: 1
    group: "EV_settings"

  - type: "switch"
    name: "Charging Enabled"
    unique_id: "charging_enabled"
    address: 2001
    input_type: "holding"
    data_type: "uint16"
    scan_interval: 30
    on_value: 1
    off_value: 0
    group: "EV_settings"

calculated:
  - name: "Total Power"
    unique_id: "total_power"
    type: "sensor"
    state: "{{ (states('sensor.{PREFIX}_current_phase_1') | default(0) | float) * 230 }}"
    unit_of_measurement: "W"
    device_class: "power"
    state_class: "measurement"
    group: "EV_calculated"
```

### Example: Dynamic Configuration Template

```yaml
name: "Dynamic Device"
version: 1
description: "Device with dynamic configuration"
manufacturer: "Generic"
model: "Dynamic"

dynamic_config:
  phases:
    description: "Number of phases"
    options: [1, 3]
    default: 3

  max_power:
    description: "Maximum power"
    options: [3000, 5000, 7000]
    default: 5000

sensors:
  - name: "Power Phase 1"
    unique_id: "power_phase_1"
    address: 1000
    input_type: "input"
    data_type: "uint16"
    scale: 1
    scan_interval: 10
    unit_of_measurement: "W"
    device_class: "power"
    # This sensor only appears if phases >= 1
    condition: "phases >= 1"
    group: "PV_power"
```

---

## Best Practices

1. **Use Groups**: Organize entities with meaningful group names (e.g., `PV_power`, `EV_status`)
2. **Meaningful Names**: Use descriptive, clear names for sensors and controls
3. **Unique IDs**: Always provide `unique_id` for predictable entity IDs
4. **Appropriate Scan Intervals**: Use longer intervals (600s) for rarely-changing data, shorter (10s) for real-time values
5. **Home Assistant Metadata**: Always include `device_class`, `state_class`, and `unit_of_measurement` where applicable
6. **Icons**: Use Material Design Icons for visual consistency
7. **Documentation**: Add comments in YAML for complex configurations
8. **Version Control**: Increment template version when making changes

---

## Additional Resources

- [Home Assistant Sensor Device Classes](https://developers.home-assistant.io/docs/core/entity/sensor#available-device-classes)
- [Home Assistant State Classes](https://developers.home-assistant.io/docs/core/entity/sensor#available-state-classes)
- [Material Design Icons](https://materialdesignicons.com/)
- [Jinja2 Template Documentation](https://jinja.palletsprojects.com/)

---

**Last Updated**: January 2025
