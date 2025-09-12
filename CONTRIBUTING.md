# Contributing to HA-Modbus-Manager

Thank you for your interest in contributing to HA-Modbus-Manager! This document focuses on creating new device templates, which is our primary need for contributions.

## 🎯 Primary Contribution Need: New Device Templates

We are actively seeking **new device templates** for various Modbus-compatible devices. Templates are the core of this integration and help users integrate their devices quickly and easily.

## 🏭 What We Need

### High Priority Templates
- **Solar Inverters**: SMA, Fronius, Huawei, SolarEdge, Kostal, Growatt
- **Heat Pumps**: Vaillant, Viessmann, Buderus, Bosch
- **EV Chargers**: Wallbox, ABB, Schneider Electric, Tesla
- **Battery Systems**: BYD, LG Chem, Tesla Powerwall, Sonnen
- **Smart Meters**: Landis+Gyr, Kamstrup, Itron
- **Industrial Equipment**: PLCs, HMIs, SCADA systems

### Template Features to Include
- **Dynamic Configuration**: Automatic filtering based on device parameters
- **Float Conversion**: Support for IEEE 754 32-bit and 64-bit floating-point
- **Firmware Compatibility**: Sensor parameter adjustment for different firmware versions
- **Connection Types**: LAN/WINET support with register filtering

### Template Types
1. **Dynamic Templates**: Like Sungrow SHx Dynamic (preferred)
2. **Static Templates**: Simple device-specific templates
3. **SunSpec Templates**: For SunSpec-compliant devices

## 📋 Template Creation Guidelines

### 1. Template Structure

#### Basic Template Structure
```yaml
name: "Device Name"
description: "Brief description of the device and its capabilities"
manufacturer: "Manufacturer Name"
model: "Model Series"
version: 1.0.0

# Dynamic configuration (optional)
dynamic_config:
  parameter_name:
    description: "Parameter description"
    options: [option1, option2, option3]
    default: option1

sensors:
  - name: "Sensor Name"
    unique_id: "sensor_identifier"
    address: 40001
    input_type: input
    data_type: uint16
    unit_of_measurement: "W"
    device_class: power
    state_class: measurement
    scale: 1
    scan_interval: 10

controls:
  - type: "number"
    name: "Control Name"
    address: 40002
    input_type: holding
    data_type: uint16
    unit_of_measurement: "W"
    min_value: 0
    max_value: 10000
    step: 100

calculated:
  - name: "Calculated Sensor"
    unique_id: "calculated_sensor"
    type: "sensor"
    state: "{{ states('sensor.{PREFIX}_base_sensor') | default(0) | float * 2 }}"
    unit_of_measurement: "W"
    device_class: power
```

#### Dynamic Template Example
```yaml
dynamic_config:
  phases:
    description: "Number of phases"
    options: [1, 3]
    default: 1

  battery_enabled:
    description: "Battery support enabled"
    default: false

  firmware_version:
    description: "Firmware version string"
    default: "1.0.0"
    sensor_replacements:
      battery_current:
        "2.0.0":
          data_type: "int16"
          scale: 0.1
```

### 2. Required Fields

#### Every Sensor Must Have
- `name`: Human-readable name
- `unique_id`: Unique identifier (no spaces, use underscores)
- `address`: Modbus register address
- `input_type`: `input` or `holding`
- `data_type`: `uint16`, `int16`, `uint32`, `int32`, `float32`, `string`
- `scan_interval`: Update frequency in seconds

#### Optional Fields
- `unit_of_measurement`: Unit (W, A, V, °C, etc.)
- `device_class`: Home Assistant device class
- `state_class`: `measurement`, `total`, `total_increasing`
- `scale`: Scaling factor for raw values
- `precision`: Decimal places for display
- `group`: Logical grouping for organization

### 3. Data Types and Scaling

#### Common Data Types
```yaml
# 16-bit unsigned integer
data_type: uint16
scale: 1

# 16-bit signed integer
data_type: int16
scale: 0.1

# 32-bit unsigned integer (requires count: 2)
data_type: uint32
count: 2
swap: word
scale: 1

# 32-bit signed integer (requires count: 2)
data_type: int32
count: 2
swap: word
scale: 1

# 32-bit float (requires count: 2)
data_type: float32
count: 2
swap: word

# String (requires count for character length)
data_type: string
count: 10
```

#### Scaling Examples
```yaml
# Raw value 1000, display as 100.0
scale: 0.1
precision: 1

# Raw value 5000, display as 5.0 kW
scale: 0.001
unit_of_measurement: "kW"

# Raw value 1234, display as 12.34%
scale: 0.01
unit_of_measurement: "%"
```

### 4. Device Classes and State Classes

#### Power and Energy
```yaml
device_class: power
state_class: measurement
unit_of_measurement: "W"

device_class: energy
state_class: total_increasing
unit_of_measurement: "kWh"
```

#### Electrical Parameters
```yaml
device_class: voltage
state_class: measurement
unit_of_measurement: "V"

device_class: current
state_class: measurement
unit_of_measurement: "A"

device_class: frequency
state_class: measurement
unit_of_measurement: "Hz"
```

#### Temperature and Battery
```yaml
device_class: temperature
state_class: measurement
unit_of_measurement: "°C"

device_class: battery
state_class: measurement
unit_of_measurement: "%"
```

### 5. Controls (Read/Write)

#### Number Controls
```yaml
- type: "number"
  name: "Max Power"
  address: 40002
  input_type: holding
  data_type: uint16
  unit_of_measurement: "W"
  min_value: 0
  max_value: 10000
  step: 100
  scan_interval: 30
```

#### Select Controls
```yaml
- type: "select"
  name: "Operating Mode"
  address: 40003
  input_type: holding
  data_type: uint16
  options:
    0: "Auto"
    1: "Manual"
    2: "Scheduled"
  scan_interval: 30
```

#### Switch Controls
```yaml
- type: "switch"
  name: "Enable Feature"
  address: 40004
  input_type: holding
  data_type: uint16
  scan_interval: 30
```

### 6. Calculated Sensors

#### Basic Calculation
```yaml
calculated:
  - name: "Total Power"
    unique_id: "total_power"
    type: "sensor"
    state: "{{ states('sensor.{PREFIX}_power_1') | default(0) | float + states('sensor.{PREFIX}_power_2') | default(0) | float }}"
    unit_of_measurement: "W"
    device_class: power
```

#### Conditional Logic
```yaml
calculated:
  - name: "Grid Import Power"
    unique_id: "grid_import_power"
    type: "sensor"
    state: >-
      {% if states('sensor.{PREFIX}_grid_power') | default(0) | float > 0 %}
        {{ states('sensor.{PREFIX}_grid_power') | default(0) | float }}
      {% else %}
        0
      {% endif %}
    unit_of_measurement: "W"
    device_class: power
```

## 🔧 Template Development Process

### 1. Research Phase
1. **Find Device Manual**: Locate Modbus documentation
2. **Identify Registers**: List all relevant registers
3. **Understand Data Types**: Note scaling and units
4. **Test Communication**: Verify Modbus connectivity

### 2. Template Creation
1. **Create Basic Template**: Start with essential sensors
2. **Add Controls**: Include read/write capabilities
3. **Implement Calculations**: Add calculated sensors
4. **Test Thoroughly**: Verify all functionality

### 3. Documentation
1. **Create README**: Document template features
2. **Add Examples**: Provide configuration examples
3. **Include Troubleshooting**: Common issues and solutions
4. **Update Main Docs**: Add to docs/README.md

### 4. Submission
1. **Create Pull Request**: Submit template for review
2. **Include Testing**: Provide test results
3. **Documentation**: Include README and examples
4. **Follow Guidelines**: Ensure compliance with standards

## 📚 Template Examples

### Simple Static Template
```yaml
name: "Simple Device"
description: "Basic device with essential sensors"
manufacturer: "Manufacturer"
model: "Model Series"
version: 1.0.0

sensors:
  - name: "Device Temperature"
    unique_id: "device_temperature"
    address: 40001
    input_type: input
    data_type: int16
    unit_of_measurement: "°C"
    device_class: temperature
    state_class: measurement
    scale: 0.1
    scan_interval: 30

  - name: "Power Output"
    unique_id: "power_output"
    address: 40002
    input_type: input
    data_type: uint16
    unit_of_measurement: "W"
    device_class: power
    state_class: measurement
    scale: 1
    scan_interval: 10

controls:
  - type: "number"
    name: "Power Limit"
    address: 40003
    input_type: holding
    data_type: uint16
    unit_of_measurement: "W"
    min_value: 0
    max_value: 10000
    step: 100
    scan_interval: 30
```

### Dynamic Template Example
```yaml
name: "Advanced Device"
description: "Device with dynamic configuration"
manufacturer: "Manufacturer"
model: "Advanced Series"
version: 1.0.0

dynamic_config:
  phases:
    description: "Number of phases"
    options: [1, 3]
    default: 1

  battery_enabled:
    description: "Battery support enabled"
    default: false

  firmware_version:
    description: "Firmware version"
    default: "1.0.0"
    sensor_replacements:
      battery_current:
        "2.0.0":
          data_type: "int16"
          scale: 0.1

sensors:
  - name: "Phase A Current"
    unique_id: "phase_a_current"
    address: 40001
    input_type: input
    data_type: uint16
    unit_of_measurement: "A"
    device_class: current
    state_class: measurement
    scale: 0.01
    scan_interval: 10

  - name: "Phase B Current"
    unique_id: "phase_b_current"
    address: 40002
    input_type: input
    data_type: uint16
    unit_of_measurement: "A"
    device_class: current
    state_class: measurement
    scale: 0.01
    scan_interval: 10

  - name: "Phase C Current"
    unique_id: "phase_c_current"
    address: 40003
    input_type: input
    data_type: uint16
    unit_of_measurement: "A"
    device_class: current
    state_class: measurement
    scale: 0.01
    scan_interval: 10

  - name: "Battery Current"
    unique_id: "battery_current"
    address: 40004
    input_type: input
    data_type: int16
    unit_of_measurement: "A"
    device_class: current
    state_class: measurement
    scale: 0.1
    scan_interval: 10
```

## 🧪 Testing Your Template

### Manual Testing Checklist
- [ ] **Modbus Connection**: Verify device communication
- [ ] **Sensor Values**: Check data accuracy and scaling
- [ ] **Control Functions**: Test read/write operations
- [ ] **Calculated Sensors**: Verify calculations
- [ ] **Dynamic Features**: Test parameter filtering
- [ ] **Error Handling**: Test with invalid data

### Test Configuration
```yaml
# Enable debug logging
logger:
  default: info
    custom_components.modbus_manager: debug

# Test template
modbus_manager:
  - name: "Test Device"
    template: "your_template.yaml"
    prefix: "test"
    # Add dynamic parameters if applicable
    phases: 3
    battery_enabled: true
    firmware_version: "1.0.0"
```

## 📝 Documentation Requirements

### Template README Structure
```markdown
# Device Name Template

## Overview
Brief description of the device and template capabilities.

## Supported Models
List of supported device models.

## Configuration
Required and optional parameters.

## Features
Available sensors, controls, and calculated sensors.

## Installation
Step-by-step installation guide.

## Troubleshooting
Common issues and solutions.

## Version
Template version and compatibility information.
```

## 🚀 Getting Started

### Quick Start
1. **Choose a Device**: Pick a device you want to support
2. **Find Documentation**: Locate Modbus register documentation
3. **Create Template**: Follow the structure guidelines above
4. **Test Thoroughly**: Verify all functionality works
5. **Submit PR**: Create pull request with template and documentation

### Resources
- **[Template Examples](custom_components/modbus_manager/device_templates/)** - Existing templates
- **[Documentation](docs/)** - Template documentation
- **[Issues](https://github.com/TCzerny/ha-modbus-manager/issues)** - Request specific devices

## 🤝 Community Guidelines

### Before Contributing
- **Check Existing Templates**: Avoid duplicates
- **Test with Real Device**: Ensure functionality
- **Follow Standards**: Use consistent formatting
- **Document Everything**: Include comprehensive documentation

### Code of Conduct
- Be respectful and constructive
- Help other contributors
- Share knowledge and experiences
- Report issues promptly

## 📞 Getting Help

### Questions and Discussion
- **GitHub Issues**: For template-specific questions
- **GitHub Discussions**: For general discussion
- **Home Assistant Community**: For integration help

### Template Review
- **Request Review**: Ask for feedback on complex templates
- **Testing Help**: Get assistance with device testing
- **Documentation**: Help with template documentation

---

**Thank you for contributing to HA-Modbus-Manager!** Your device templates help make this integration more useful for the entire Home Assistant community.

**Priority**: We especially need templates for popular solar inverters, heat pumps, and EV chargers!
