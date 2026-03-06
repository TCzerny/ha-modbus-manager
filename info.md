# HA-Modbus-Manager

A comprehensive Modbus integration for Home Assistant with support for multiple device types and advanced features. This integration provides a template-based, UI-configurable platform that replaces manual maintenance of `configuration.yaml` and offers a scalable solution for managing multiple Modbus-TCP devices.

## ⚠️ Disclaimer

This integration is provided "AS IS" without warranty of any kind. By using this integration, you agree that:

1. The use of this integration is at your own risk
2. The author(s) will not be liable for any damages, direct or indirect, that may arise from the use of this integration
3. The integration may interact with electrical devices and systems. Incorrect configuration or usage could potentially damage your devices
4. You are responsible for ensuring compliance with your device manufacturer's warranty terms and conditions
5. Always verify the correct operation of your system after making any changes

## 🔧 Current Features

### Core Functionality
- 🔌 **Multi-Device Support**: Manage multiple Modbus devices simultaneously
- 📊 **Template-Based Configuration**: YAML templates for easy device setup
- 🛠 **UI-Driven Setup**: Complete configuration through Home Assistant UI
- 🔄 **Automatic Entity Generation**: Sensors, switches, numbers, and more created automatically
- 🆔 **Deterministic Entity IDs**: Optional `default_entity_id` enforces stable entity IDs

### Advanced Data Processing
- ⚡ **Bit Operations**: Shift bits, bit masking, and bit field extraction
- 🗺️ **Enum Mapping**: Convert numeric values to human-readable text
- 🏁 **Bit Flags**: Extract individual bit status as separate attributes
- 🔢 **Mathematical Operations**: Offset, multiplier, and sum_scale support
- 📏 **Data Type Support**: uint16, int16, uint32, int32, string, float32, float64, boolean
- 🌊 **Float Conversion**: Complete IEEE 754 32-bit and 64-bit floating-point support

### Entity Types
- 📊 **Sensors**: Comprehensive sensor support with all data types
- 🔘 **Binary Sensors**: Boolean sensors with configurable true/false values
- 🔢 **Numbers**: Read/write numeric entities with min/max/step validation
- 📋 **Selects**: Dropdown selection with predefined options
- 🔌 **Switches**: On/off control with custom on/off values
- 🔘 **Buttons**: Action triggers for device control
- 📝 **Text**: String input/output entities

### Monitoring & Optimization
- 📊 **Performance Monitoring**: Comprehensive metrics and operation tracking
- 🔧 **Register Optimization**: Intelligent grouping and batch reading
- 🛠️ **Template Reload**: Update templates without restart
- 📈 **Services**: Built-in services for optimization and monitoring

### Device Templates
- ☀️ **Sungrow SHx Dynamic**: Complete support for all 36 SHx models with dynamic configuration
  - **Automatic Filtering**: Based on phases (1/3), MPPT count (1-4), battery options, strings, firmware
  - **Firmware Compatibility**: Automatic sensor parameter adjustment
  - **Connection Types**: LAN/WINET support with register filtering
  - **Meter Support**: DTSU666, DTSU666-20 (dual-channel)
- ☀️ **Sungrow SG Dynamic**: Model selection for SG series inverters
- ☀️ **Sungrow iHomeManager**: New EMS template added - *needs testing*
- 🔋 **Compleo EBox Professional**: EV charger wallbox integration template
- 🔋 **Sungrow SBR Battery**: Battery system template
- 🔌 **Sungrow AC011E Wallbox**: EV wallbox (AC007-00, AC011E-01, AC22E-01), RS485 via inverter – *needs testing*
- 🔌 **Heidelberg Energy Control**: EV charger (Modbus RTU via proxy) – *needs testing*

**New / BETA templates**
The following templates were added recently and **have not been tested on real hardware**. If you use them, please report any issues or feedback so we can fix register maps and behaviour: **Sungrow AC011E-01 Wallbox**, **Heidelberg Energy Control**, **Fronius GEN24**, **Growatt MIN/MOD/MAX**, **SMA Sunny Tripower/Boy**, **SolaX Inverter Series**, **BYD Battery Box**. See [Documentation](https://github.com/TCzerny/ha-modbus-manager/wiki) and `docs/` for per-template docs.


## 📋 Configuration

### Quick Setup
1. **Add Integration**: Go to Configuration → Devices & Services → + Add Integration
2. **Select Template**: Choose from available device templates
3. **Configure Device**: Enter IP, port, slave ID, and prefix
4. **Enjoy**: Entities are automatically created and ready to use

### Advanced Configuration
- **Custom Templates**: Create your own device definitions
- **Performance Tuning**: Adjust batch sizes and polling intervals
- **Error Handling**: Configure retry mechanisms and timeouts

## 🔍 Device Support

### Currently Supported
- **Sungrow SHx Inverters**: Complete dynamic template supporting all 36 SHx models with automatic filtering
- **Sungrow SG Inverters**: Dynamic template with model selection (SG3.0RS, SG4.0RS, SG5.0RS, SG6.0RS, SG8.0RS, SG10RS, SG3.0RT, SG4.0RT, SG5.0RT, SG6.0RT)
- **Compleo EBox Professional**: Wallbox charging station integration
- **Sungrow SBR Battery**: Battery system template
- **Sungrow AC011E Wallbox**: EV wallbox (AC007-00, AC011E-01, AC22E-01) – *needs testing*
- **Heidelberg Energy Control**: EV charger (Modbus RTU via proxy) – *needs testing*


### Template Development
- **YAML-Based**: Simple and readable template format
- **Extensible**: Add new devices easily with template system
- **Documented**: Comprehensive examples and documentation
- **Community**: Share and contribute templates

## 📚 Documentation & Support

### Contributing
- [🤝 Contributing](https://github.com/TCzerny/ha-modbus-manager/blob/main/CONTRIBUTING.md): How to contribute to the project

### Community Support
- [🐛 Bug Reports](https://github.com/TCzerny/ha-modbus-manager/issues): Report issues and request features
- [💬 Discussions](https://github.com/TCzerny/ha-modbus-manager/discussions): Community discussions and help
- [📚 Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki): Extended documentation and examples

## 🎯 Current Status

### Version 1.0.1 (Current - March 2026)
- ✅ Core Modbus integration with template system
- ✅ Advanced data processing and entity types
- ✅ Performance monitoring and register optimization
- ✅ Comprehensive device templates with dynamic configuration
- ✅ Multi-step configuration flow
- ✅ Template reload functionality
- ✅ Calculated sensors with Jinja2
- ✅ Full float conversion support (IEEE 754)
- ✅ iHomeManager EMS support (BETA - requires end-user testing)
- ✅ Home Assistant Entity guidelines compliance (has_entity_name, EntityCategory, etc.)

## 🤝 Contributing

We welcome contributions! Whether you're a developer, tester, or documentation writer:

- **🐛 Report Bugs**: Help improve reliability
- **💡 Suggest Features**: Share your ideas for improvement
- **🔧 Code Contributions**: Implement new features or fix bugs
- **📖 Documentation**: Improve guides and examples
- **🧪 Testing**: Test with different devices and configurations

## ⭐ Support the Project

If you find this integration useful, please consider:

- ⭐ **Star the repository** to show your support
- 🐛 **Report issues** to help improve reliability
- 💡 **Contribute code** to add new features
- 📖 **Improve documentation** to help other users
- 🔗 **Share with the community** to help others discover it

---

**Made with ❤️ for the Home Assistant community**

*This integration is designed to be a modern, scalable alternative to traditional Modbus configurations, providing the power and flexibility needed for complex home automation setups.*

---

**Version**: 1.0.1
**Status**: Stable - Active Development
**Home Assistant**: 2025.4.0+
**Last Updated**: March 2026
