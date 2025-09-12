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

### Aggregation & Monitoring
- 📈 **Real-time Aggregation**: Sum, average, max, min, and count sensors
- 🔍 **Group Discovery**: Automatic detection of entity groups from templates
- 📊 **Performance Monitoring**: Comprehensive metrics and operation tracking
- ⚡ **Register Optimization**: Intelligent grouping and batch reading
- 🔧 **Services & Diagnostics**: Built-in services for optimization and monitoring

### Device Templates
- ☀️ **Sungrow SHx Dynamic**: Complete support for all 36 SHx models with dynamic configuration
  - **Automatic Filtering**: Based on phases (1/3), MPPT count (1-3), battery support
  - **Firmware Compatibility**: Automatic sensor parameter adjustment
  - **Connection Types**: LAN/WINET support with register filtering
- 🔋 **Compleo EBox Professional**: Wallbox integration template
- 🧪 **Advanced Example**: Demonstrates all advanced features

## 🚀 Planned Features

### High Priority
- ✅ **Float Conversion**: Automatic 32-bit and 64-bit IEEE 754 float handling (fully implemented)
- ✅ **Dynamic Configuration**: Automatic sensor filtering based on device parameters (fully implemented)
- ✅ **Services & Diagnostics**: Performance monitoring and register optimization (fully implemented)
- 📝 **String Processing**: Enhanced string validation and encoding
- 🏷️ **Entity Categories**: Config, diagnostic, and system categories
- 📊 **Status Aggregation**: Combined status from multiple entities
- 🧮 **Template Sensors**: Mathematical calculations (MPPT Power, Phase Power)
- 🔍 **Advanced Binary Sensors**: Bit-based status with direct register operations

### Medium Priority
- 🎨 **Custom Icons**: Template-based icon configuration
- 🎛️ **Advanced Controls**: Sophisticated control entity types
- ⏰ **Aggregation Scheduling**: Configurable update intervals
- ✅ **Template Validation**: Enhanced YAML validation and error reporting
- 🔧 **Input Entity Integration**: Native input support for configuration
- 🧹 **Data Filtering**: Time-based filtering and data validation

### Low Priority
- 🤖 **AI Optimization**: Performance improvement suggestions
- 🧬 **Template Inheritance**: Base templates with overrides
- 🔄 **Dynamic Templates**: Runtime template generation
- 📊 **Advanced Metrics**: Detailed performance analytics
- 🤖 **Automation Templates**: Predefined automation support
- 📜 **Script Execution**: Built-in script capabilities

## 📋 Configuration

### Quick Setup
1. **Add Integration**: Go to Configuration → Devices & Services → + Add Integration
2. **Select Template**: Choose from available device templates
3. **Configure Device**: Enter IP, port, slave ID, and prefix
4. **Enjoy**: Entities are automatically created and ready to use

### Advanced Configuration
- **Custom Templates**: Create your own device definitions
- **Aggregation Setup**: Configure group-based aggregation sensors
- **Performance Tuning**: Adjust batch sizes and polling intervals
- **Error Handling**: Configure retry mechanisms and timeouts

## 🔍 Device Support

### Currently Supported
- **Sungrow SHx Inverters**: Complete dynamic template supporting all 36 SHx models with automatic filtering
- **Compleo EBox Professional**: Wallbox charging station integration
- **SunSpec Devices**: Universal template for all SunSpec-compliant devices
- **Generic Devices**: Advanced example template for custom implementations

### Template Development
- **YAML-Based**: Simple and readable template format
- **Extensible**: Add new devices easily with template system
- **Documented**: Comprehensive examples and documentation
- **Community**: Share and contribute templates

## 📚 Documentation & Support

### Getting Started
- [📖 README](https://github.com/TCzerny/ha-modbus-manager/blob/main/README.md): Complete feature overview and setup guide
- [📋 TODO](https://github.com/TCzerny/ha-modbus-manager/blob/main/TODO.md): Development roadmap and planned features
- [🤝 Contributing](https://github.com/TCzerny/ha-modbus-manager/blob/main/CONTRIBUTING.md): How to contribute to the project

### Community Support
- [🐛 Bug Reports](https://github.com/TCzerny/ha-modbus-manager/issues): Report issues and request features
- [💬 Discussions](https://github.com/TCzerny/ha-modbus-manager/discussions): Community discussions and help
- [📚 Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki): Extended documentation and examples

## 🎯 Roadmap

### Version 1.x (Current)
- ✅ Core Modbus integration with template system
- ✅ Advanced data processing and entity types
- ✅ Aggregation and performance monitoring
- ✅ Comprehensive device templates

### Version 2.x (Planned)
- 🚧 Template sensors and mathematical calculations
- 🚧 Advanced binary sensors with bit operations
- 🚧 Input entity integration and automation support
- 🚧 Enhanced data filtering and validation

### Version 3.x (Future)
- 🔮 AI-powered optimization suggestions
- 🔮 Template inheritance and dynamic generation
- 🔮 Advanced automation and script execution
- 🔮 Enterprise features and scalability

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

**Version**: 3.0.0
**Status**: Stable (Sungrow SHx Dynamic, Compleo templates implemented)
**Home Assistant**: 2025.1.0+
**Last Updated**: January 2025
