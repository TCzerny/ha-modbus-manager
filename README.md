# Modbus Manager for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release][releases-shield]][releases]
![Project Maintenance][maintenance-shield]
[![License][license-shield]](LICENSE)

A flexible and powerful Modbus integration for Home Assistant that supports multiple device types and offers advanced features like:

- Dynamic device configuration through YAML definitions
- Optimized batch reading of registers
- Automatic register grouping for better performance
- Built-in error handling and retry mechanisms
- Extensive monitoring and diagnostics
- Support for multiple devices and manufacturers
- Smart request proxy with caching and batching

## ⚠️ Disclaimer

This integration is provided "AS IS" without warranty of any kind. By using this integration, you agree that:

1. The use of this integration is at your own risk
2. The author(s) will not be liable for any damages, direct or indirect, that may arise from the use of this integration
3. The integration may interact with electrical devices and systems. Incorrect configuration or usage could potentially damage your devices
4. You are responsible for ensuring compliance with your device manufacturer's warranty terms and conditions
5. Always verify the correct operation of your system after making any changes

## Features

### Advanced Request Handling
- **Smart Request Proxy**: Automatically combines multiple register reads into optimized batches
- **Intelligent Caching**: Caches register values to reduce device load
- **Request Merging**: Combines adjacent or overlapping register requests
- **Automatic Retry**: Handles communication errors with configurable retry logic

### Performance Optimization
- **Request Batching**: Groups multiple register reads into single Modbus transactions
- **Register Grouping**: Automatically groups adjacent registers for efficient reading
- **Cache Management**: Time-based cache with configurable timeout
- **Request Queuing**: Smart queuing system for optimal request handling

### Monitoring and Diagnostics
- **Performance Metrics**: Track response times, success rates, and error rates
- **Detailed Logging**: Comprehensive logging of all Modbus operations
- **Error Tracking**: Detailed error tracking and categorization
- **Health Monitoring**: Monitor device and connection health

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the "+" button
4. Search for "Modbus Manager"
5. Click "Download"
6. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/modbus_manager` folder to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

### Basic Setup
1. Go to Settings -> Devices & Services
2. Click "Add Integration"
3. Search for "Modbus Manager"
4. Follow the configuration steps

### Advanced Configuration Options

## Supported Devices

Currently supported device types:
- Sungrow SH-RT Hybrid Inverter
- Sungrow Battery System
- Generic Modbus devices (through custom device definitions)

## Device Definitions

You can add support for new devices by creating YAML device definitions. See the [Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki) for more information.

## Contributing

Feel free to contribute to this project! Please read our [Contributing Guidelines](CONTRIBUTING.md).

## Support

- Report bugs and feature requests on [GitHub Issues](https://github.com/TCzerny/ha-modbus-manager/issues)
- Join the discussion in our [Discord Community](https://discord.gg/your-discord)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

[releases-shield]: https://img.shields.io/github/release/TCzerny/ha-modbus-manager.svg?style=for-the-badge
[releases]: https://github.com/TCzerny/ha-modbus-manager/releases
[maintenance-shield]: https://img.shields.io/maintenance/yes/2024.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/TCzerny/ha-modbus-manager.svg?style=for-the-badge 