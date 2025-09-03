# 🔧 Project Description: HA-Modbus-Manager

## 👤 Author: TCzerny  
## 📦 Repository: [github.com/TCzerny/ha-modbus-manager](https://github.com/TCzerny/ha-modbus-manager)  
## 📅 Status: January 2025  
## 🧠 Goal: A universal, template-driven Modbus integration for Home Assistant

---

## 🧱 Project Goal

The HA-Modbus-Manager aims to provide a modular, scalable and maintainable platform for managing Modbus devices in Home Assistant. The goal is to integrate any devices such as PV inverters, heat pumps, wallboxes, HVAC systems or heating systems through a unified template system — without manual YAML configuration or automations.

**Key Features:**
- **Template-Based**: All device configurations defined in YAML templates
- **Dynamic Configuration**: Automatic filtering based on device parameters
- **Universal Compatibility**: Support for any Modbus-compatible device
- **UI-Driven**: Complete configuration through Home Assistant UI
- **Performance Optimized**: Intelligent register reading and aggregation

---

## 🔧 Architecture Overview

### 📁 Template Structure

Templates are located under `custom_components/modbus_manager/device_templates/*.yaml` and contain:

- `sensors:` → Modbus sensors with full data type support
- `controls:` → Direct Modbus control (`number`, `select`, `switch`, `button`)
- `calculated:` → Calculated sensors via Jinja2 templates
- `dynamic_config:` → Dynamic configuration parameters (optional)
- `version:` → Template versioning for update detection
- `manufacturer:` → Device manufacturer information
- `model:` → Device model series

### 🧩 Core Modules

| File                   | Function                                           |
|------------------------|----------------------------------------------------|
| `template_loader.py`   | Loads and validates YAML templates                 |
| `config_flow.py`       | UI setup and dynamic configuration                 |
| `sensor.py`            | Sensor entity implementation                       |
| `number.py`            | Number entity implementation (read/write)          |
| `select.py`            | Select entity implementation (read/write)         |
| `switch.py`            | Switch entity implementation (read/write)         |
| `binary_sensor.py`     | Binary sensor implementation                       |
| `button.py`            | Button entity implementation                       |
| `text.py`              | Text entity implementation (read/write)            |
| `calculated.py`        | Calculated sensors with Jinja2                    |
| `aggregates.py`        | Real-time aggregation and group management        |
| `register_optimizer.py`| Register reading optimization                      |
| `performance_monitor.py`| Performance monitoring and metrics                |

### 🔄 Dynamic Configuration System

The integration supports dynamic templates that automatically filter sensors based on device configuration:

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

---

## ✅ Current Features

### 🔌 Core Functionality
- **Multi-Device Support**: Manage multiple Modbus devices simultaneously
- **Template-Based Configuration**: YAML templates for easy device setup
- **UI-Driven Setup**: Complete configuration through Home Assistant UI
- **Automatic Entity Generation**: Sensors, switches, numbers, and more created automatically

### 📊 Advanced Data Processing
- **Bit Operations**: Shift bits, bit masking, and bit field extraction
- **Enum Mapping**: Convert numeric values to human-readable text
- **Bit Flags**: Extract individual bit status as separate attributes
- **Mathematical Operations**: Offset, multiplier, and sum_scale support
- **Data Type Support**: uint16, int16, uint32, int32, float32, string, boolean

### 🎛️ Entity Types
- **Sensors**: Comprehensive sensor support with all data types
- **Binary Sensors**: Boolean sensors with configurable true/false values
- **Numbers**: Read/write numeric entities with min/max/step validation
- **Selects**: Dropdown selection with predefined options
- **Switches**: On/off control with custom on/off values
- **Buttons**: Action triggers for device control
- **Text**: String input/output entities

### 📈 Aggregation & Monitoring
- **Real-time Aggregation**: Sum, average, max, min, and count sensors
- **Group Discovery**: Automatic detection of entity groups from templates
- **Performance Monitoring**: Comprehensive metrics and operation tracking
- **Register Optimization**: Intelligent grouping and batch reading

### 🏭 Device Templates

#### 🔋 Solar Inverters
- **Sungrow SHx Dynamic** (v1.0.0): Complete support for all 36 SHx models with dynamic configuration
- **SunSpec Standard Config**: Universal template for all SunSpec-compliant devices

#### 🔌 EV Chargers
- **Compleo EBox Professional**: Wallbox integration template

#### 🧪 Development
- **Advanced Example**: Demonstrates all advanced features

---

## 📋 Example Template: `sungrow_shx_dynamic.yaml`

```yaml
name: "Sungrow SHx Dynamic Inverter"
description: "Dynamic template for Sungrow SHx inverters"
manufacturer: "Sungrow"
model: "SHx Series Dynamic"
version: 1.0.0

dynamic_config:
  phases:
    description: "Number of phases"
    options: [1, 3]
    default: 1
  
  mppt_count:
    description: "Number of MPPT trackers"
    options: [1, 2, 3]
    default: 1
  
  battery_enabled:
    description: "Battery support enabled"
    default: false

sensors:
  - name: "Inverter Temperature"
    unique_id: "inverter_temperature"
    address: 5007
    input_type: input
    data_type: int16
    unit_of_measurement: "°C"
    device_class: temperature
    state_class: measurement
    scale: 0.1
    scan_interval: 10

  - name: "MPPT1 Voltage"
    unique_id: "mppt1_voltage"
    address: 5010
    input_type: input
    data_type: uint16
    unit_of_measurement: "V"
    device_class: voltage
    state_class: measurement
    scale: 0.1
    scan_interval: 10

controls:
  - type: "number"
    name: "Export Power Limit"
    address: 13073
    input_type: holding
    data_type: uint16
    unit_of_measurement: "W"
    min_value: 0
    max_value: 10000
    step: 100
    scan_interval: 30

calculated:
  - name: "MPPT1 Power"
    unique_id: "mppt1_power"
    type: "sensor"
    state: "{{ (states('sensor.{PREFIX}_mppt1_voltage') | default(0) | float) * (states('sensor.{PREFIX}_mppt1_current') | default(0) | float) }}"
    unit_of_measurement: "W"
    device_class: power
    state_class: measurement
```

---

## 🚀 Planned Features

### High Priority
- **Additional Device Templates**: SMA, Fronius, Huawei, SolarEdge, heat pumps, EV chargers
- **Enhanced Dynamic Configuration**: More parameter types and filtering options
- **Template Validation**: Advanced YAML validation and error reporting
- **Performance Optimization**: Further register reading optimizations

### Medium Priority
- **Template Inheritance**: Base templates with overrides
- **Advanced Aggregation**: More complex aggregation functions
- **Custom Icons**: Template-based icon configuration
- **Automation Templates**: Predefined automation support

### Low Priority
- **AI Optimization**: Performance improvement suggestions
- **Advanced Metrics**: Detailed performance analytics
- **Script Execution**: Built-in script capabilities
- **Cloud Integration**: Remote monitoring capabilities

---

## 🔍 Device Support

### Currently Supported
- **Sungrow SHx Inverters**: Complete dynamic template supporting all 36 SHx models
- **Compleo EBox Professional**: Wallbox charging station integration
- **SunSpec Devices**: Universal template for all SunSpec-compliant devices
- **Generic Devices**: Advanced example template for custom implementations

### Template Development
- **YAML-Based**: Simple and readable template format
- **Extensible**: Add new devices easily with template system
- **Documented**: Comprehensive examples and documentation
- **Dynamic**: Automatic filtering based on device configuration

---

## 📊 Performance Features

### Register Optimization
- **Batch Reading**: Group registers for efficient reading
- **Intelligent Polling**: Adjust scan intervals based on data type
- **Error Recovery**: Automatic retry mechanisms
- **Connection Pooling**: Efficient Modbus connection management

### Monitoring & Metrics
- **Performance Tracking**: Monitor read times and success rates
- **Error Reporting**: Detailed error logging and reporting
- **Resource Usage**: Track memory and CPU usage
- **Health Monitoring**: Device connection health status

---

## 🤝 Contributing

We actively seek **new device templates** for various Modbus-compatible devices:

### High Priority Templates
- **Solar Inverters**: SMA, Fronius, Huawei, SolarEdge, Kostal, Growatt
- **Heat Pumps**: Vaillant, Viessmann, Buderus, Bosch
- **EV Chargers**: Wallbox, ABB, Schneider Electric, Tesla
- **Battery Systems**: BYD, LG Chem, Tesla Powerwall, Sonnen

### Template Types
1. **Dynamic Templates**: Like Sungrow SHx Dynamic (preferred)
2. **Static Templates**: Simple device-specific templates
3. **SunSpec Templates**: For SunSpec-compliant devices

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📞 Support & Community

- **GitHub Issues**: [Bug reports and feature requests](https://github.com/TCzerny/ha-modbus-manager/issues)
- **GitHub Discussions**: [Questions and general discussion](https://github.com/TCzerny/ha-modbus-manager/discussions)
- **Documentation**: [Complete template documentation](docs/README.md)
- **Home Assistant Community**: [Integration-specific help](https://community.home-assistant.io/)

---

**Version**: 3.0.0  
**Status**: Stable (Sungrow SHx Dynamic, Compleo templates implemented)  
**Home Assistant**: 2025.1.0+  
**Last Updated**: January 2025
