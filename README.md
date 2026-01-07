# Home Assistant Modbus Manager

> **⚠️ BETA - Use at your own risk!**
> This integration is currently in beta testing. Some features may not work as expected. Please report any issues you encounter.

A modular, template-based Modbus Manager for Home Assistant with predefined device templates for popular energy devices.

## 📦 Installation

### Using HACS (Recommended)

1. **Install HACS** (if not already installed):
   - Go to [HACS](https://hacs.xyz/) and follow the installation instructions
   - Restart Home Assistant after installation

2. **Add this repository to HACS**:
   - Open HACS in your Home Assistant sidebar
   - Go to **Integrations**
   - Click the three dots menu (⋮) in the top right
   - Select **Custom repositories**
   - Add repository URL: `https://github.com/TCzerny/ha-modbus-manager`
   - Set category to **Integration**
   - Click **Add**

3. **Install the integration**:
   - Search for "Modbus Manager" in HACS Integrations
   - Click **Install**
   - Restart Home Assistant

4. **Add the integration**:
   - Go to **Settings** → **Devices & Services**
   - Click **Add Integration**
   - Search for "Modbus Manager"
   - Follow the configuration wizard

### Manual Installation

1. **Download the latest release** from the [Releases page](https://github.com/TCzerny/ha-modbus-manager/releases)

2. **Copy the integration**:
   - Extract the downloaded file
   - Copy the `modbus_manager` folder to your `custom_components` directory
   - Your structure should look like: `config/custom_components/modbus_manager/`

3. **Restart Home Assistant**

4. **Add the integration**:
   - Go to **Settings** → **Devices & Services**
   - Click **Add Integration**
   - Search for "Modbus Manager"
   - Follow the configuration wizard

## 🚀 Features

- **Predefined Device Templates**: Ready-to-use templates for popular devices
- **Template-based Configuration**: Devices are defined via YAML templates
- **Multi-Step Configuration Flow**: Intuitive step-by-step device setup
- **Dynamic Template Configuration**: Automatic sensor filtering based on device parameters
- **Model Selection**: Automatic configuration based on device model selection
- **Calculated Sensors**: Template-based calculations with Jinja2
- **Options Flow**: Post-configuration via the UI
- **Template Reload**: Update templates without losing configuration
- **Modular Architecture**: Easily extensible for new device types
- **Home Assistant Integration**: Fully integrated into the HA UI

## 🔌 Supported Devices

### ✅ Currently Supported

#### Solar Inverters
- **Sungrow SHx Series** - Complete template with all sensors and controls
  - **Dynamic Configuration**: Supports all 36 SHx models with automatic filtering
  - **Multi-Step Setup**: Connection parameters → Dynamic configuration
  - **Battery Options**: None, Standard Battery, SBR Battery
  - **Battery management**: SOC, charging/discharging, temperature monitoring
  - **MPPT tracking**: 1-3 MPPT trackers with power calculations
  - **String tracking**: 0-4 strings with individual monitoring
  - **Grid interaction**: Import/export, phase monitoring, frequency
  - **Calculated sensors**: Efficiency, power balance, signed battery power
  - **Full Modbus register mapping**: Based on mkaiser's comprehensive implementation
  - **Firmware compatibility**: Automatic sensor parameter adjustment
  - **Connection types**: LAN and WINET support with register filtering
  - **Float conversion**: Full IEEE 754 32-bit and 64-bit floating-point support

- **Sungrow SG Series** - Dynamic template with model selection
  - **2-Step Configuration**: Connection parameters → Model selection
  - **Model Selection**: Automatic configuration based on selected model
  - **Supported Models**: SG3.0RS, SG4.0RS, SG5.0RS, SG6.0RS, SG8.0RS, SG10RS, SG3.0RT, SG4.0RT, SG5.0RT, SG6.0RT
  - **Automatic Filtering**: Phases, MPPT, Strings configured automatically
  - **Firmware Support**: SAPPHIRE-H firmware compatibility
  - **Connection Types**: LAN and WINET support

#### EV Chargers
- **Compleo eBox Professional** - Complete EV charger template
  - 3-phase charging control
  - Current and power monitoring
  - Fallback current settings
  - Cable status and charging control

### 🔮 Future Support

#### Other Manufacturers (Planned)
- **Kostal** - Piko, Plenticore
- **Growatt** - MIN, MAX series
- **Victron** - MultiPlus, Quattro

## 🏗️ Template Structure

### Value Processing (Map, Flags, Options)

The Modbus Manager supports three types of value processing for converting raw register values to human-readable text:

#### 1. **Map** (Highest Priority)
Direct 1:1 mapping of numeric values to text strings. Used for status codes, error codes, and operating modes.

```yaml
# Example: Operating mode mapping
map:
  0: "Off"
  1: "On"
  2: "Standby"
  3: "Error"
  64: "Running (normal operation)"
```

#### 2. **Flags** (Medium Priority)
Bit-based evaluation where multiple flags can be active simultaneously. Used for status registers with multiple bits or alarm flags.

```yaml
# Example: Status register with multiple flags
flags:
  0: "Alarm 1"
  1: "Alarm 2"
  2: "Warning"
  3: "Maintenance"
  4: "System OK"
```

**Result**: If register value = 5 (binary: 101), the result would be: "Alarm 1, Warning"

#### 3. **Options** (Lowest Priority)
Dropdown options for Select controls. Used for configuration options and selection menus.

```yaml
# Example: Configuration options
options:
  0: "Auto"
  1: "Manual"
  2: "Schedule"
  3: "Emergency"
```

#### Processing Order
All entity types (Sensors, Select, Number, Switch, Binary Sensor) process values in this order:
1. **Map** (if defined)
2. **Flags** (if no map defined)
3. **Options** (if no map or flags defined)

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
    type: "number"
    unique_id: "max_soc"
    address: 5001
    input_type: "holding"
    data_type: "uint16"
    min_value: 0
    max_value: 100
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
├── config_flow.py             # Configuration UI
├── device_templates/
│   ├── sungrow_shx.yaml           # Sungrow SHx template
│   ├── compleo_ebox_professional.yaml  # Compleo eBox template
│   └── base_templates/           # Base templates (if needed)
└── translations/               # UI translations
    ├── de.json
    └── en.json
```

## 🧪 Usage

### 1. Add Device Template

1. **Open Home Assistant** → Configuration → Integrations
2. **Click "Add Integration"** → "Modbus Manager"
3. **Select your device template**:
   - **Sungrow SHx Dynamic Inverter** for SHx series solar inverters
   - **Sungrow SG Dynamic Inverter** for SG series solar inverters
   - **Compleo eBox Professional** for EV chargers
4. **Configure connection** (Step 1):
   - **Host**: Device IP address
   - **Port**: Modbus port (usually 502)
   - **Slave ID**: Modbus slave address
   - **Timeout**: Connection timeout (default: 5s)
   - **Delay**: Delay between operations (default: 0ms)
   - **Message Wait**: Wait time between requests (default: 100ms)
5. **Configure device parameters** (Step 2):
   - **Dynamic Templates**: Configure phases, MPPT, strings, battery, firmware, connection type
   - **Model Selection**: Select device model for automatic configuration
   - **Battery Configuration**: Choose battery type and slave ID if applicable

### 2. Configure Dashboard

```yaml
# Lovelace Dashboard Example
type: entities
title: "Energy Overview"
entities:
  # Individual devices
  - sensor.sg_battery_level
  - sensor.ebox_charging_power
```

## 📊 Available Templates

### Sungrow SHx Series
- **File**: `sungrow_shx_dynamic.yaml`
- **Devices**: All 36 SHx models (SHxK6, SHxK-20/V13, SHxK-30, SHx.0RS, SHx.0RT/RT-20/RT-V112/RT-V122, SHxT, MGxRL)
- **Features**:
  - **Multi-Step Configuration**: Connection parameters → Dynamic configuration
  - **Dynamic Configuration**: 6 configurable parameters (phases, MPPT, battery, firmware, strings, connection)
  - **Battery Options**: None, Standard Battery, SBR Battery
  - **Automatic Filtering**: Register filtering based on device configuration
  - **Battery management**: SOC, charging/discharging, temperature, health monitoring
  - **MPPT tracking**: 1-3 MPPT trackers with individual power calculations
  - **String tracking**: 0-4 strings with individual monitoring
  - **Grid interaction**: Import/export, phase monitoring, frequency, meter data
  - **Load management**: Load power, backup power, direct consumption
  - **Calculated sensors**: Efficiency, power balance, signed battery power, phase power
  - **Firmware compatibility**: Automatic sensor parameter adjustment for different firmware versions
  - **Connection support**: LAN (full access) and WINET (limited access) with register filtering

### Sungrow SG Series
- **File**: `sungrow_sg_dynamic.yaml`
- **Devices**: SG3.0RS, SG4.0RS, SG5.0RS, SG6.0RS, SG8.0RS, SG10RS, SG3.0RT, SG4.0RT, SG5.0RT, SG6.0RT
- **Features**:
  - **2-Step Configuration**: Connection parameters → Model selection
  - **Model Selection**: Automatic configuration based on selected model
  - **Automatic Filtering**: Phases, MPPT, Strings configured automatically
  - **Firmware Support**: SAPPHIRE-H firmware compatibility
  - **Connection Types**: LAN and WINET support
  - **MPPT tracking**: 2-3 MPPT trackers based on model
  - **Phase support**: 1-phase (RS) and 3-phase (RT) models
  - **String tracking**: 1 string per model

### Compleo eBox Professional
- **File**: `compleo_ebox_professional.yaml`
- **Devices**: Compleo eBox Professional, Innogy eBox
- **Features**:
  - 3-phase charging control
  - Current monitoring per phase
  - Power calculations
  - Fallback current settings
  - Cable status monitoring

## 🚧 Known Issues


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
- **[Sungrow SHx Dynamic](docs/README_sungrow_shx_dynamic.md)** - Complete dynamic template documentation
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

**Last Updated**: October 2025
**Version**: 0.1.0
**Status**: Initial Release
