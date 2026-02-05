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
- **Sungrow SHx Series** - Complete template with dynamic configuration for all 36 SHx models
  - Automatic filtering: MPPT (1-3), strings (0-4), phases, battery options
  - Meter support: DTSU666, DTSU666-20 (dual-channel)
  - Connection types: LAN and WINET with register filtering
- **Sungrow SG Series** - Dynamic template with model selection (SG3.0RS–SG10RS, SG3.0RT–SG6.0RT)
- **Sungrow iHomeManager EMS** - Energy management system template ⚠️ **BETA – needs testing**

#### Battery Systems
- **Sungrow SBR / SBH Battery** - Dedicated battery template (SBR096–SBR256, SBH100–SBH400)
  - ⚠️ **SBH needs testing** - Based on protocol documentation, not verified on hardware
- **BYD Battery Box** - Template for HVS/HVM/HVL/LVS series ⚠️ **BETA – needs testing**

#### Other Inverters ⚠️ **BETA – need testing**
- **Fronius GEN24 Series** - SunSpec-capable dynamic template
- **Growatt MIN/MOD/MAX Series** - MIN/MOD/MAX inverter template
- **SMA Sunny Tripower/Boy Series** - SMA inverter template
- **SolaX Inverter Series** - SolaX GEN2–GEN6 dynamic template

#### Other Devices
- **Solvis SC2/SC3** - Heating controller with temperature sensors and pump controls
- **Compleo eBox Professional** - EV charger with 3-phase charging control and monitoring

### 🔮 Future Support
- **Kostal** (Piko, Plenticore), **Victron** (MultiPlus, Quattro)

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


## 🧪 Usage

### 1. Add Device Template

1. **Open Home Assistant** → Configuration → Integrations
2. **Click "Add Integration"** → "Modbus Manager"
3. **Select your device template** → Choose the device template you like to add
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

Dashboard examples are available in the [Dashboard Examples](Dashboard-Examples/README.md) folder:

- **Battery Dashboards**: Comprehensive battery monitoring with balancing analysis, module details, and advanced metrics
- **PV Dashboards**: PV inverter monitoring with MPPT analysis, energy flow, and statistics

All examples are available in multiple versions:
- **Standard**: Uses built-in Home Assistant cards (no custom cards required)
- **Mushroom**: Enhanced UI with Mushroom Cards (requires HACS installation)
- **Simple**: Minimal version with only essential cards

See the [Dashboard Examples README](Dashboard-Examples/README.md) for installation instructions and customization options.

## 📊 Available Templates

The full, up-to-date list of templates is maintained in the project wiki:
https://github.com/TCzerny/ha-modbus-manager/wiki

## 🚧 Known Issues

### Offline Devices
- If the Modbus host is unreachable, entities show as **unavailable** (standard HA behavior).
- Home Assistant’s Modbus hub retries the TCP connection every 60 seconds (Core behavior).

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
- **[Sungrow SG Dynamic](docs/README_sungrow_sg_dynamic.md)** - Dynamic SG template documentation
- **[Sungrow iHomeManager](docs/README_iHomeManager.md)** - iHomeManager register documentation
- **[Sungrow SBR Battery](docs/README_sungrow_sbr_battery.md)** - SBR battery template
- **[Solvis SC3](docs/README_solvis_sc3.md)** - Solvis SC2/SC3 template
- **[Compleo eBox Professional](docs/README_compleo_ebox_professional.md)** - EV charger template
- **[BYD Battery Box](docs/README_byd_battery_box.md)** - BYD Battery-Box template (BETA)
- **[Fronius GEN24 Dynamic](docs/README_fronius_dynamic.md)** - Fronius GEN24 template (BETA)
- **[Growatt MIN/MOD/MAX Dynamic](docs/README_growatt_min_mod_max_dynamic.md)** - Growatt template (BETA)
- **[SMA Dynamic](docs/README_sma_dynamic.md)** - SMA Sunny Tripower/Boy template (BETA)
- **[SolaX Dynamic](docs/README_solax_dynamic.md)** - SolaX inverter template (BETA)

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
