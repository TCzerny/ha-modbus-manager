# Modbus Manager for Home Assistant

A custom integration for Home Assistant that manages Modbus devices through a template-based, UI-configurable platform. The goal is to replace manual maintenance of `configuration.yaml` and provide a scalable solution for managing multiple Modbus-TCP devices.

## 🔧 Main Features

- **Device Templates**: YAML-based definitions of Modbus devices with register mapping, scaling, units, device_class, state_class and group tags
- **UI Setup**: Users select a template, enter IP, port, slave-ID and a prefix – entities are automatically generated
- **Entity Generation**: Sensors are dynamically created from templates, with prefix for distinction and group tags for later aggregation
- **Modbus Hub Management**: Each device is registered as its own virtual Modbus hub, communication runs through the standard Home Assistant Modbus API
- **Aggregation Module**: Automatic generation of sum, average, max/min and status sensors over entities with the same group tag
- **Live Refresh**: Aggregation sensors update immediately when related entities change via `async_track_state_change`
- **Group Discovery**: All existing groups are detected and offered in the UI for aggregation configuration
- **Advanced Data Processing**: Support for bit operations, enum mapping, bit flags and more (based on [modbus_connect](https://github.com/dmatscheko/modbus_connect))
- **Complete Entity Types**: Sensors, switches, numbers, select entities, binary sensors
- **Robust Modbus Integration**: Fully integrated with the standard Home Assistant Modbus API, comprehensive error handling and validation

## 📋 Supported Devices

### Sungrow SHx Inverter
- **Template**: `sungrow_shx.yaml`
- **Description**: Complete support for Sungrow SHx inverters
- **Registers**: Temperature, MPPT data, grid parameters, energy statistics
- **Groups**: identification, energy_daily, energy_total, mppt1, mppt2, grid_l1, power_total, system

### Compleo EBox Professional Wallbox
- **Template**: `compleo_ebox.yaml`
- **Description**: Template for Compleo EBox Professional wallbox
- **Registers**: Charging status, current/voltage/power, energy statistics, temperature
- **Groups**: identification, status, charging, energy_session, energy_total, time_session, system

### Advanced Example Device
- **Template**: `advanced_example.yaml`
- **Description**: Demonstrates all advanced features
- **Features**: Bit operations, enum mapping, bit flags, float conversion, control entities

## 🚀 Installation

### HACS Installation (Recommended)
1. Add the repository to HACS
2. Install the integration via HACS
3. Restart Home Assistant

### Manual Installation
1. Download the code
2. Copy the `custom_components/modbus_manager` folder to your `custom_components` folder
3. Restart Home Assistant

## ⚙️ Configuration

### 1. Select Template
- Go to **Configuration** → **Devices & Services**
- Click **+ Add Integration**
- Select **Modbus Manager**
- Choose an available template

### 2. Device Configuration
- **Prefix**: Unique name for the device (e.g., `sungrow_1`)
- **Host**: IP address of the Modbus device
- **Port**: Modbus port (default: 502)
- **Slave ID**: Modbus slave ID (default: 1)
- **Timeout**: Connection timeout in seconds (default: 3)
- **Retries**: Number of retry attempts (default: 3)

### 3. Aggregation Configuration
- Go to the **Options** of the integration
- Select **Configure Aggregations**
- Choose the desired groups
- Select the aggregation methods (sum, average, max/min, count)

## 📊 Template Format

Templates use the following YAML format:

```yaml
name: "Device Name"
description: "Device description"
manufacturer: "Manufacturer"
model: "Model"

sensors:
  - name: "Sensor Name"
    unique_id: "unique_id"
    device_address: 1
    address: 1000
    input_type: "input"  # input or holding
    data_type: "uint16"  # uint16, int16, uint32, int32, string, float, boolean
    count: 1
    scan_interval: 600
    precision: 2
    unit_of_measurement: "kWh"
    device_class: "energy"
    state_class: "total_increasing"
    scale: 0.01
    swap: false  # for 32-bit values
    group: "energy_total"
    
    # Advanced data processing (modbus_connect features)
    offset: 0.0           # Add offset
    multiplier: 1.0       # Apply multiplier
    sum_scale: [0.1, 0.01]  # Scale factors for sum operations
    shift_bits: 0         # Bit shift operations
    bits: [0, 1, 2]      # Specific bit selection
    float: false          # Float conversion
    string: false         # String conversion
    control: "none"       # Control type (none, number, select, switch, text)
    min_value: 0.0       # Minimum value for number entities
    max_value: 100.0     # Maximum value for number entities
    step: 1.0            # Step size for number entities
    options: {}           # Options for select entities
    map: {}              # Value mapping
    flags: {}            # Bit flags
    never_resets: false  # Never resets flag
    entity_category: null # Entity category
    icon: null           # Custom icon
```

## 🔧 Advanced Features

### Bit Operations
```yaml
- name: "Status Flags"
  data_type: "uint16"
  bits: [0, 1, 2, 3]  # Read specific bits
  flags:
    0: "Error"
    1: "Warning"
    2: "Running"
    3: "Connected"
```

### Enum Mapping
```yaml
- name: "Operating Mode"
  data_type: "uint16"
  map:
    0: "Off"
    1: "Standby"
    2: "Running"
    3: "Error"
```

### Sum Operations
```yaml
- name: "Total Energy"
  data_type: "uint32"
  count: 2
  sum_scale: [0.1, 0.01]  # Scale factors for each register
```

## 📈 Aggregation Features

### Automatic Group Detection
The integration automatically detects all groups from templates and offers them for aggregation configuration.

### Supported Aggregation Types
- **Sum**: Sum of all values in a group
- **Average**: Average of all values in a group
- **Maximum**: Highest value in a group
- **Minimum**: Lowest value in a group
- **Count**: Number of entities in a group
- **Status**: Combined status from multiple entities

### Real-time Updates
Aggregation sensors update immediately when any related entity changes, providing real-time insights.

## 🐛 Troubleshooting

### Common Issues
1. **Connection Errors**: Check IP address, port, and slave ID
2. **No Data**: Verify register addresses and data types
3. **Wrong Values**: Check scale, precision, and swap settings
4. **Missing Entities**: Ensure template is properly formatted

### Debug Mode
Enable debug logging in `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.modbus_manager: debug
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Based on the excellent work of [modbus_connect](https://github.com/dmatscheko/modbus_connect)
- Inspired by the Home Assistant community's need for better Modbus device management
- Special thanks to all contributors and testers

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/TCzerny/ha-modbus-manager/issues)
- **Discussions**: [Join the community](https://github.com/TCzerny/ha-modbus-manager/discussions)
- **Documentation**: [Full documentation](https://github.com/TCzerny/ha-modbus-manager/wiki)

---

**Made with ❤️ for the Home Assistant community** 