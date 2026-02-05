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
type: "device_type"                    # Device type (e.g., "PV_Hybrid_Inverter", "EV_charger")
default_prefix: "device_prefix"        # Default prefix for entity IDs
default_slave_id: 1                    # Default Modbus slave ID
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
- **`default_prefix`**: Prefix used for entity IDs (e.g., "SG" creates `sensor.sg_temperature`)
- **`default_slave_id`**: Default Modbus slave/unit ID
- **`firmware_version`**: Default firmware version if none specified
- **`available_firmware_versions`**: List of firmware versions available for user selection during setup

---

## Dynamic Configuration

Dynamic configuration allows templates to adapt based on user-selected parameters. This enables one template to support multiple device variants.

```yaml
dynamic_config:
  # RECOMMENDED: Model-specific configuration using valid_models
  # This is the preferred approach for device variants with different specifications
  # When a model is selected, all values from that model are automatically added to dynamic_config
  # and can be used throughout the template (e.g., in conditions, max_value placeholders, etc.)
  valid_models:
    "Model-A":
      phases: 1
      mppt_count: 2
      string_count: 2
      max_ac_output_power: 5000
      max_current: 23
      battery_enabled: false
    "Model-B":
      phases: 3
      mppt_count: 2
      string_count: 2
      max_ac_output_power: 10000
      max_current: 45
      battery_enabled: true
      max_charge_power: 6600
      max_discharge_power: 6600

  # Other configuration options (can be combined with valid_models)
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

  firmware_version:
    description: "Firmware version string"
    default: "1.0.0"
    sensor_replacements:
      battery_power_raw:
        "2.0.0":
          data_type: "int16"
          scale: 1
          description: "Battery power signed in firmware v2+"

  battery_config:
    description: "Battery configuration"
    options: ["none", "sungrow_sbr_battery", "other"]
    default: "none"
```

**How `valid_models` Works:**

1. **Model Selection**: When `valid_models` is defined, users select a model during setup instead of configuring individual parameters
2. **Automatic Value Injection**: All values from the selected model are automatically added to `dynamic_config` and available throughout the template
3. **Template Usage**: Values can be used in:
   - **Conditions**: `condition: "phases >= 3"` or `condition: "selected_model == 'Model-B'"`
   - **Placeholders**: `max_value: "{{max_ac_output_power}}"` or `max_value: "{{max_charge_power * 0.5}}"`
   - **Calculations**: Supports Jinja2 expressions like `{{max(max_charge_power, max_discharge_power)}}`
4. **Value Replacement**: Placeholders like `{{max_ac_output_power}}` are replaced at runtime with the actual value from the selected model
5. **No Duplication**: When using `valid_models`, you don't need to define `phases`, `mppt_count`, etc. separately - they come from the model configuration

**Example Template Usage:**

```yaml
controls:
  - type: "number"
    name: "Export Power Limit"
    unique_id: "export_power_limit"
    address: 5010
    input_type: "holding"
    data_type: "uint16"
    min_value: 0
    max_value: "{{max_ac_output_power}}"  # Replaced with 5000 for Model-A, 10000 for Model-B
    unit_of_measurement: "W"
    group: "PV_control"

sensors:
  - name: "Power Phase 1"
    unique_id: "power_phase_1"
    address: 1000
    condition: "phases >= 1"  # Uses phases value from selected model
    # ... more config
```

### Dynamic Config Features

1. **Model Selection (Recommended)**: Use `valid_models` for device variants with different specifications
   - Users select a model during setup instead of configuring individual parameters
   - All model values are automatically injected into `dynamic_config` and available throughout the template
   - Values can be used in conditions, placeholders (e.g., `{{max_ac_output_power}}`), and calculations
   - This is the **preferred approach** for templates supporting multiple device models
2. **Option Selection**: User chooses from predefined options during setup (alternative to `valid_models` for simple configurations)
3. **Sensor Filtering**: Sensors can be conditionally included/excluded based on configuration
4. **Sensor Replacements**: Sensor parameters can change based on firmware version
5. **Sensor Availability**: Sensors can be marked as available only for specific connection types
6. **Battery Setup Step**: A dedicated battery flow is shown in the config flow
   only when `dynamic_config.battery_config` is defined in the template. The UI
   captures battery availability and selection (template or "other"). The
   resulting `battery_config` value is stored as `none`, `other`, or the battery
   template name (e.g., `sungrow_sbr_battery`).

### Condition Filtering

Use the `condition` field on sensors/controls/calculated/binary entities to include or skip them based on dynamic configuration.

**Supported operators:**
- `==`, `!=`, `>=`
- `in`, `not in` for list checks
- `and`, `or` for combining conditions

**Examples:**
```yaml
# Model-specific control
condition: "selected_model in [SG33CX, SG40CX, SG50CX]"

# Exclude a meter type
condition: "meter_type != 'iHomeManager'"

# Combined logic
condition: "phases >= 3 and connection_type == 'LAN'"
```

**Notes:**
- Conditions can use any field from `dynamic_config`.
- `selected_model` is required when `valid_models` exist.
- `battery_config` can be `none`, `other`, or a battery template name.

### Unique IDs and Entity ID Handling

- **`unique_id`**: Required field that uniquely identifies the entity
  - Should not include a device prefix in the template
  - The integration automatically adds the configured prefix (e.g., `SG`) to entity IDs
  - Format: `prefix_unique_id` (e.g., `sg_average_voltage`)

- **`default_entity_id`**: Optional field to force a specific entity_id
  - If not set, it is automatically derived from `unique_id`
  - If set, the entity will be created with that exact `entity_id`
  - Useful for maintaining consistent entity IDs across template updates

**Note**: When existing entities have different IDs, Home Assistant may keep the old IDs until the entity registry is manually cleaned up.

### Example: Battery Flow Trigger

```yaml
dynamic_config:
  battery_config:
    description: "Battery configuration"
    options: ["none", "sbr_battery"]
    default: "none"
```

This enables the battery flow. The final `battery_config` value is set by the
UI to `none`, `other`, or a template name, regardless of the options list.

### Example: Model Selection

```yaml
dynamic_config:
  valid_models:
    "SG10RT": {phases: 3, mppt_count: 2, string_count: 2}
    "SG12RT": {phases: 3, mppt_count: 2, string_count: 2}
```

When `valid_models` exists, `selected_model` is required and can be used in
`condition` expressions.

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
- **`unique_id`**: Unique identifier for the sensor (used for entity ID generation)
- **`address`**: Modbus register address (0-based, matches Modbus protocol)

### Optional Fields

#### Modbus Configuration
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
    state: "{{ (states('sensor.{PREFIX}_power_1') | float(0)) + (states('sensor.{PREFIX}_power_2') | float(0)) }}"
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
- **`state_class`**: State class for sensor type (should not be used for string values)
- **`precision`**: Decimal places for display (optional, only for numeric values)
- **`icon`**: Material Design Icon name
- **`group`**: Group identifier
- **`availability`**: Optional Jinja2 template for entity availability

### Important Notes

- **String Values**: If a calculated sensor returns a string value (e.g., "Cell Position 520 (3.3500 V)"), do NOT use `state_class: measurement` as this will cause validation errors. The system automatically removes `suggested_display_precision` for string values.
- **Numeric Values**: For numeric calculated sensors, you can optionally specify `precision` to control decimal places. If not specified, defaults to 5 decimal places for calculated sensors.
- **Availability**: Use the `availability` template to control when the sensor is available based on other sensor states.

### Template Placeholders

- **`{PREFIX}`**: Replaced with device prefix (e.g., "SG", "eBox")

### Example Expressions

```jinja2
# Conditional value
{{ if states('sensor.{PREFIX}_voltage') | float > 230 else 0 }}

# Bitwise operation (for flags-based sensors)
{{ (states('sensor.{PREFIX}_running_state') | int) | bitwise_and(1) == 1 }}

# String comparison
{{ states('sensor.{PREFIX}_status') not in ['unavailable', 'unknown', 'no cable'] }}

# Mathematical calculation
{{ (states('sensor.{PREFIX}_voltage') | float(0)) * (states('sensor.{PREFIX}_current') | float(0)) }}
```

---

## Value Processing

The Modbus Manager supports three types of value processing that convert raw numeric register values to human-readable text.

### Processing Order

All entity types (Sensors, Select, Number, Switch, Binary Sensor) process values in this order:

1. **Map** (highest priority) - Direct 1:1 mapping
2. **Flags** (medium priority) - Bit-based evaluation (if no map defined)
3. **Options** (lowest priority) - Dropdown options (if no map or flags defined)

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

The best way to learn how to create templates is to study the existing device templates in this project. Each template demonstrates real-world usage of all features described in this documentation.

### Available Device Templates

All templates are located in `custom_components/modbus_manager/device_templates/`:

#### PV Inverters
- **[Sungrow SHx Dynamic](README_sungrow_shx_dynamic.md)** (`sungrow_shx_dynamic.yaml`) - Comprehensive hybrid inverter template with `valid_models`, dynamic configuration, battery support, and extensive calculated sensors
- **[Sungrow SG Dynamic](README_sungrow_sg_dynamic.md)** (`sungrow_sg_dynamic.yaml`) - PV inverter template with model selection and power limit controls
- **[Fronius Dynamic](README_fronius_dynamic.md)** (`fronius_dynamic.yaml`) - SunSpec-based inverter with model selection
- **[SMA Dynamic](README_sma_dynamic.md)** (`sma_dynamic.yaml`) - Sunny Tripower/Boy series with model selection
- **[SolaX Dynamic](README_solax_dynamic.md)** (`solax_dynamic.yaml`) - GEN2/GEN3/GEN6 series with dynamic configuration
- **[Growatt MIN/MOD/MAX Dynamic](README_growatt_min_mod_max_dynamic.md)** (`growatt_min_mod_max_dynamic.yaml`) - Hybrid inverter series with battery support

#### Battery Systems
- **[Sungrow SBR Battery](README_sungrow_sbr_battery.md)** (`sungrow_sbr_battery.yaml`) - Battery system with module-level monitoring and balancing analysis
- **[BYD Battery Box](README_byd_battery_box.md)** (`byd_battery_box.yaml`) - Battery system template

#### Other Devices
- **[Compleo eBox Professional](README_compleo_ebox_professional.md)** (`compleo_ebox_professional.yaml`) - EV charger with 3-phase control, status mapping, and calculated sensors
- **[Solvis SC3](README_solvis_sc3.md)** (`solvis_sc3.yaml`) - Heating controller with temperature sensors and pump controls
- **[Sungrow iHomeManager](README_iHomeManager.md)** (`sungrow_ihomemanager.yaml`) - Energy management system

### Template Examples by Feature

#### Using `valid_models` (Recommended Approach)
- **Sungrow SHx Dynamic**: Demonstrates comprehensive model selection with power limits, phases, MPPT counts
- **Sungrow SG Dynamic**: Shows model-specific AC output power limits and current limits
- **Sungrow SBR Battery**: Model selection for different battery capacities and module counts

#### Dynamic Configuration
- **Fronius Dynamic**: Connection type-based sensor availability
- **SolaX Dynamic**: Battery configuration and firmware version handling
- **Growatt Dynamic**: Phases, MPPT, and battery configuration

#### Value Processing (Map, Flags, Options)
- **Compleo eBox Professional**: Extensive use of `map` for status codes and charging states
- **Sungrow SHx Dynamic**: `flags` for status registers and `options` for select controls

#### Calculated Sensors
- **Sungrow SHx Dynamic**: Complex battery power calculations, efficiency metrics, energy flow analysis
- **Sungrow SBR Battery**: Balancing analysis, voltage spread calculations, module comparisons
- **Compleo eBox Professional**: Power calculations from current and voltage

#### Controls (Number, Switch, Select, Button, Text)
- **Sungrow SHx Dynamic**: Power limits with model-specific `max_value` placeholders, battery control switches
- **Compleo eBox Professional**: Current limits, charging control switches, mode selection

#### Binary Sensors
- **Sungrow SHx Dynamic**: Battery charging/discharging states, grid connection status
- **Compleo eBox Professional**: Cable connection status, charging active state

### Quick Reference Examples

For quick reference, here are minimal examples of common patterns:

#### Basic Sensor with Map
```yaml
sensors:
  - name: "Status"
    unique_id: "status"
    address: 275
    input_type: "input"
    data_type: "string"
    map:
      A: "not connected"
      B2: "Connected ready"
      C2: "Charging"
```

#### Control with Model-Specific Max Value
```yaml
controls:
  - type: "number"
    name: "Export Power Limit"
    unique_id: "export_power_limit"
    address: 5010
    input_type: "holding"
    data_type: "uint16"
    min_value: 0
    max_value: "{{max_ac_output_power}}"  # Replaced from valid_models
    unit_of_measurement: "W"
```

#### Calculated Sensor with Condition
```yaml
calculated:
  - name: "Battery Charging Power"
    unique_id: "battery_charging_power"
    type: "sensor"
    state: "{{ states('sensor.{PREFIX}_battery_power_raw') | float(0) if states('sensor.{PREFIX}_battery_power_raw') | float(0) > 0 else 0 }}"
    unit_of_measurement: "W"
    device_class: "power"
    condition: "battery_enabled == true"
```

**For complete, production-ready examples, refer to the templates listed above.**

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
