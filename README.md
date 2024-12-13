# Modbus Manager for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

A Home Assistant integration for managing Modbus devices with preconfigured device definitions and translations.

## ⚠️ Disclaimer

This integration is provided "AS IS" without warranty of any kind. By using this integration, you agree that:

1. The use of this integration is at your own risk
2. The author(s) will not be liable for any damages, direct or indirect, that may arise from the use of this integration
3. The integration may interact with electrical devices and systems. Incorrect configuration or usage could potentially damage your devices
4. You are responsible for ensuring compliance with your device manufacturer's warranty terms and conditions
5. Always verify the correct operation of your system after making any changes

## Supported Devices

### Sungrow SHRT Series (Hybrid Inverters)
- Sungrow SH-RT (3-phase with battery)
- Sungrow SH-RT (3-phase)
- Sungrow SH-RT (1-phase with battery)
- Sungrow SH-RT (1-phase)

### Sungrow SGRT Series (Grid Inverters)
- Sungrow SG-RT (Base)
- Sungrow SG-RT (1-phase)
- Sungrow SG-RT (3-phase)

### Sungrow Battery System
- Battery status and control
- Energy and power measurement
- Health and diagnostic data

### Compleo Charging Station
- eBox Professional
- Charging status and control
- Energy and power measurement

### Additional Modules
- Common Entities (Base information for all devices)
- Load Management System

## Installation

1. Add this repository to HACS as a "Custom Repository":
   ```
   https://github.com/TCzerny/modbus_manager
   ```

2. Install the integration through HACS

3. Restart Home Assistant

## Configuration

1. Go to Settings -> Devices & Services
2. Click "Add Integration"
3. Search for "Modbus Manager"
4. Select the desired device type from the list
5. Enter the required connection parameters:
   - Name: A unique name for the device
   - Host: IP address or hostname of the device
   - Port: Modbus TCP port (default: 502)
   - Slave ID: Modbus slave ID (default: 1)
   - Scan Interval: Update interval in seconds (default: 30)
   - System Size (PV systems only): Size in kW (1-30)

## Features

### Automatic Device Detection
- Preconfigured device definitions
- Automatic setup of all relevant entities
- Optimized polling intervals

### Intelligent Load Management
- Consumer prioritization
- Dynamic power adjustment
- Energy flow optimization

### Advanced Monitoring
- Detailed status displays
- Power and energy measurement
- Error and diagnostic reports

### Automation Capabilities
- Predefined automations
- Event-based notifications
- Adjustable thresholds

## Troubleshooting

### Connection Issues
1. Check the network connection to the device
2. Ensure the Modbus TCP port (default: 502) is accessible
3. Verify the device's slave ID

### Data Errors
1. Check the scan interval
2. Verify Modbus register addresses
3. Validate device configuration

## Contributing

Contributions are welcome! Please create a Pull Request or Issue in the GitHub repository.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Translations

The integration supports multiple languages through Home Assistant's translation system:
- English (en)
- German (de)

All entity names, sensors, and UI elements are defined in English and translated through the translation files. 