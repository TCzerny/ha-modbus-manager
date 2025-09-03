# Home Assistant Modbus Manager

A modular, template-based Modbus Manager for Home Assistant with predefined device templates for popular energy devices.

## 🚀 Features

- **Predefined Device Templates**: Ready-to-use templates for popular devices
- **Template-based Configuration**: Devices are defined via YAML templates
- **Aggregate Sensors**: Automatic aggregation of sensors across multiple devices
- **Calculated Sensors**: Template-based calculations with Jinja2
- **Options Flow**: Post-configuration of aggregate hubs via the UI
- **Modular Architecture**: Easily extensible for new device types
- **Home Assistant Integration**: Fully integrated into the HA UI

## 🔌 Supported Devices

### ✅ Currently Supported

#### Solar Inverters
- **Sungrow SHx Series** - Complete template with all sensors and controls
  - **Dynamic Configuration**: Supports all 36 SHx models with automatic filtering
  - **Battery management**: SOC, charging/discharging, temperature monitoring
  - **MPPT tracking**: 1-3 MPPT trackers with power calculations
  - **Grid interaction**: Import/export, phase monitoring, frequency
  - **Calculated sensors**: Efficiency, power balance, signed battery power
  - **Full Modbus register mapping**: Based on mkaiser's comprehensive implementation
  - **Firmware compatibility**: Automatic sensor parameter adjustment
  - **Connection types**: LAN and WINET support with register filtering
  - **Float conversion**: Full IEEE 754 32-bit and 64-bit floating-point support

#### EV Chargers
- **Compleo eBox Professional** - Complete EV charger template
  - 3-phase charging control
  - Current and power monitoring
  - Fallback current settings
  - Cable status and charging control

### 🔮 Future Support

#### SunSpec Standard (Planned/To be tested)
- **SMA** - Sunny Boy, Tripower, Home Storage
- **Fronius** - GEN24, Tauro
- **Huawei** - Luna, FusionSolar
- **SolarEdge** - HD Wave, StorEdge

#### Other Manufacturers (Planned)
- **Kostal** - Piko, Plenticore
- **Growatt** - MIN, MAX series
- **Victron** - MultiPlus, Quattro

## 🏗️ Template Structure

### Device Templates
Each device template includes:

```yaml
# Example: Sungrow SHx Template
name: "Sungrow SHx Inverter"
version: 1
description: "Sungrow SHx Series Solar Inverter"
manufacturer: "Sungrow"
model: "SHx Series"

# Raw Modbus sensors
sensors:
  - name: "Battery Level"
    unique_id: "battery_level"
    address: 5000
    input_type: "holding"
    data_type: "uint16"
    group: "PV_battery_power"
    # ... more configuration

# Calculated sensors
calculated_sensors:
  - name: "Battery Charging Power"
    type: "sensor"
    state: >-
      {% if states('sensor.{PREFIX}_battery_power_raw') | default(0) | float > 0 %}
        {{ states('sensor.{PREFIX}_battery_power_raw') | default(0) | float }}
      {% else %}
        0
      {% endif %}
    group: "PV_battery_charging"

# Controls
controls:
  - name: "Max SOC"
    unique_id: "max_soc"
    address: 5001
    input_type: "holding"
    data_type: "uint16"
    min_value: 0
    max_value: 100
```

### Aggregate Integration
All templates support automatic aggregation:

```yaml
# Aggregate groups with device-specific prefixes
groups:
  - "PV_battery_power"      # Solar battery power
  - "PV_solar_power"        # Solar generation
  - "PV_grid_power"         # Grid interaction
  - "EV_charging_power"     # EV charging power
  - "EV_current_measurement" # EV current monitoring
```

## 🔧 Installation

1. **Clone Repository**:
   ```bash
   git clone https://github.com/TCzerny/ha-modbus-manager.git
   cd ha-modbus-manager
   ```

2. **Copy to Home Assistant**:
   ```bash
   cp -r custom_components/modbus_manager /path/to/homeassistant/config/custom_components/
   ```

3. **Restart Home Assistant**

4. **Add Integration**: Configuration → Integrations → Add "Modbus Manager"

## 📁 Directory Structure

```
custom_components/modbus_manager/
├── __init__.py
├── template_loader.py          # Template loader
├── sensor.py                   # Sensor entities
├── calculated.py               # Calculated sensors
├── aggregates.py               # Aggregate sensors
├── config_flow.py             # Configuration UI
├── device_templates/
│   ├── sungrow_shx.yaml           # Sungrow SHx template
│   ├── compleo_ebox_professional.yaml  # Compleo eBox template
│   ├── aggregates_hub.yaml       # Aggregate sensors template
│   └── base_templates/           # Future SunSpec templates
└── translations/               # UI translations
    ├── de.json
    └── en.json
```

## 🧪 Usage

### 1. Add Device Template

1. **Open Home Assistant** → Configuration → Integrations
2. **Click "Add Integration"** → "Modbus Manager"
3. **Select your device template**:
   - **Sungrow SHx Inverter** for solar inverters
   - **Compleo eBox Professional** for EV chargers
4. **Configure connection**:
   - **Host**: Device IP address
   - **Port**: Modbus port (usually 502)
   - **Slave ID**: Modbus slave address
   - **Prefix**: Unique prefix for this device

### 2. Add Aggregate Hub

1. **Add another integration** → "Modbus Manager"
2. **Select "Modbus Manager Aggregates"**
3. **Choose aggregate sensors** to create
4. **Configure prefix** (e.g., "total" for overall aggregates)

### 3. Configure Dashboard

```yaml
# Lovelace Dashboard Example
type: entities
title: "Energy Overview"
entities:
  # Individual devices
  - sensor.sg1_battery_level
  - sensor.ebox1_charging_power
  
  # Aggregates
  - sensor.total_pv_battery_power_sum
  - sensor.total_ev_charging_power_sum
  - sensor.efficiency_average
```

## 📊 Available Templates

### Sungrow SHx Series
- **File**: `sungrow_shx_dynamic.yaml`
- **Devices**: All 36 SHx models (SHxK6, SHxK-20/V13, SHxK-30, SHx.0RS, SHx.0RT/RT-20/RT-V112/RT-V122, SHxT, MGxRL)
- **Features**:
  - **Dynamic Configuration**: 6 configurable parameters (phases, MPPT, battery, firmware, strings, connection)
  - **Automatic Filtering**: Register filtering based on device configuration
  - **Battery management**: SOC, charging/discharging, temperature, health monitoring
  - **MPPT tracking**: 1-3 MPPT trackers with individual power calculations
  - **Grid interaction**: Import/export, phase monitoring, frequency, meter data
  - **Load management**: Load power, backup power, direct consumption
  - **Calculated sensors**: Efficiency, power balance, signed battery power, phase power
  - **Firmware compatibility**: Automatic sensor parameter adjustment for different firmware versions
  - **Connection support**: LAN (full access) and WINET (limited access) with register filtering

### Compleo eBox Professional
- **File**: `compleo_ebox_professional.yaml`
- **Devices**: Compleo eBox Professional, Innogy eBox
- **Features**:
  - 3-phase charging control
  - Current monitoring per phase
  - Power calculations
  - Fallback current settings
  - Cable status monitoring

## 🔍 Aggregate Sensors

### Available Aggregates

#### Solar (PV) Aggregates
- **Total PV Battery Power**: Sum of all battery power
- **Total PV Solar Power**: Sum of all solar generation
- **Total PV Grid Power**: Sum of all grid interaction
- **Average PV Efficiency**: Average efficiency across inverters

#### EV Charger Aggregates
- **Total EV Charging Power**: Sum of all charging power
- **Total EV Current**: Sum of all charging current
- **Active EV Chargers**: Count of active chargers
- **Average EV Efficiency**: Average charging efficiency

#### Combined Aggregates
- **Total Energy System Power**: All devices combined
- **Device Count**: Total number of devices
- **System Efficiency**: Overall system efficiency

## 🚧 Known Issues

- Aggregate sensors show double counting with multiple devices (expected behavior)

## ✅ Recent Fixes

- **Dynamic Configuration**: Fully functional with automatic sensor filtering
- **Float Conversion**: Complete IEEE 754 32-bit and 64-bit floating-point support
- **Services & Diagnostics**: Performance monitoring and register optimization
- **Template Filtering**: Automatic exclusion of irrelevant sensors based on device configuration
- **Firmware Compatibility**: Automatic sensor parameter adjustment for different firmware versions
- **Connection Type Filtering**: LAN/WINET register availability filtering
- **Performance Optimization**: Register grouping and operation monitoring
- **Deprecation Warnings** for Home Assistant 2025.12 fixed
- **Asyncio Blocking Warnings** fixed through task optimization

## 🤝 Contributing

### Adding New Device Templates

1. **Fork** the repository
2. **Create device template** in `device_templates/`
3. **Add documentation** in the [GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)
4. **Test with real device**
5. **Create Pull Request**

### Template Guidelines

- Use device-specific group prefixes (`PV_`, `EV_`, `BAT_`, etc.)
- Include all relevant sensors and controls
- Add calculated sensors for derived values
- Document register mapping
- Test with real hardware

## 📚 Documentation

- **[GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)** - Complete documentation
- **[📚 Template Documentation](docs/README.md)** - Complete template documentation overview
- **[Sungrow SHx Dynamic](docs/README_sungrow_shx_dynamic.md)** - Complete dynamic template documentation
- **[Sungrow SHx (Legacy)](docs/README_sungrow_shx.md)** - Legacy template documentation
- **[SunSpec Standard Config](docs/README_sunspec_standard_config.md)** - Universal SunSpec template
- **[Compleo eBox Professional](docs/README_compleo_ebox_professional.md)** - EV charger template

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Home Assistant Community** for the great platform
- **Device Manufacturers** for Modbus documentation
- **Community Contributors** for device testing
- **[mkaiser](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant)** for the outstanding Sungrow SHx Modbus implementation
- **photovoltaikforum.com** and **forum.iobroker.net** communities for reverse-engineering efforts

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/TCzerny/ha-modbus-manager/issues)
- **Discussions**: [GitHub Discussions](https://github.com/TCzerny/ha-modbus-manager/discussions)
- **Wiki**: [GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)

---

**Last Updated**: January 2025  
**Version**: 3.0.0  
**Status**: Stable (Sungrow SHx Dynamic, Compleo templates implemented)