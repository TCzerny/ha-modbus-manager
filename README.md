# Modbus Manager for Home Assistant

A custom integration for Home Assistant that manages Modbus devices through a template-based, UI-configurable platform. The goal is to replace manual maintenance of `configuration.yaml` and provide a scalable solution for managing multiple Modbus-TCP devices.

## 🔧 Main Features

- **Device Templates**: YAML-based definitions of Modbus devices with register mapping, scaling, units, device_class, state_class and group tags
- **UI Setup**: Users select a template, enter IP, port, slave-ID and a prefix – entities are automatically generated
- **Entity Generation**: Sensors are dynamically created from templates, with prefix for distinction and group tags for later aggregation
- **Modbus Hub Management**: Each device is registered as its own virtual Modbus hub, communication runs through the standard Home Assistant Modbus API
- **Aggregation Module**: Automatic generation of sum, average, max/min and count sensors over entities with the same group tag
- **Live Refresh**: Aggregation sensors update immediately when related entities change via `async_track_state_change`
- **Group Discovery**: All existing groups are detected and offered in the UI for aggregation configuration
- **Advanced Data Processing**: Support for bit operations, enum mapping, bit flags, offset, multiplier, and sum_scale
- **Complete Entity Types**: Sensors, binary sensors, numbers, selects, switches, buttons, text entities
- **Robust Modbus Integration**: Fully integrated with the standard Home Assistant Modbus API, comprehensive error handling and validation
- **Performance Monitoring**: Comprehensive metrics, operation tracking, and register optimization

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
- **Description**: Demonstrates advanced features
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
    
    # Advanced data processing features (IMPLEMENTED)
    offset: 0.0           # Add offset
    multiplier: 1.0       # Apply multiplier
    sum_scale: [0.1, 0.01]  # Scale factors for sum operations
    shift_bits: 0         # Bit shift operations
    bits: [0, 1, 2]      # Specific bit selection
    float: false          # Float conversion
    string: false         # String conversion
    
    # Control entities (IMPLEMENTED)
    control: "none"       # Control type (none, number, select, switch, text)
    min_value: 0.0       # Minimum value for number entities
    max_value: 100.0     # Maximum value for number entities
    step: 1.0            # Step size for number entities
    options: {}           # Options for select entities
    
    # Data mapping (IMPLEMENTED)
    map: {}              # Value mapping
    flags: {}            # Bit flags
    never_resets: false  # Never resets flag
    
    # Boolean sensor configuration (IMPLEMENTED)
    true_value: 1        # Value for true state
    false_value: 0       # Value for false state
    bit_position: 0      # Bit position for boolean sensors
```

## 🔧 Implemented Advanced Features

### Bit Operations
```yaml
- name: "Status Register"
  data_type: "uint16"
  shift_bits: 4  # Shift 4 bits to the right
  bits: 8        # Use only lower 8 bits
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

### Bit Flags
```yaml
- name: "System Status"
  data_type: "uint16"
  flags:
    0: "Power On"
    1: "Fan Active"
    2: "Pump Active"
```

### Sum Operations
```yaml
- name: "Total Energy"
  data_type: "uint32"
  count: 2
  sum_scale: [1, 10000]  # r1*1 + r2*10000
```

### Control Entities
```yaml
# Number entity (read/write)
- name: "Set Temperature"
  control: "number"
  min_value: 10.0
  max_value: 50.0
  step: 0.5

# Select entity (read/write)
- name: "Fan Speed"
  control: "select"
  options:
    0: "Off"
    1: "Low"
    2: "Medium"

# Switch entity (read/write)
- name: "Power Switch"
  control: "switch"
  switch:
    "on": 1
    "off": 0
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

### Real-time Updates
Aggregation sensors update immediately when any related entity changes, providing real-time insights.

## 🚧 TODO: Planned Features

### Advanced Data Processing
- [ ] **Float Conversion**: Automatic 32-bit IEEE 754 float conversion
- [ ] **String Processing**: Enhanced string handling and validation
- [ ] **Advanced Bit Operations**: More complex bit manipulation functions
- [ ] **Data Validation**: Input validation and error checking

### Entity Enhancements
- [ ] **Custom Icons**: Template-based icon configuration
- [ ] **Entity Categories**: Support for entity_category parameter
- [ ] **Advanced Control**: More sophisticated control entity types
- [ ] **Conditional Logic**: Template-based conditional entity creation

### Aggregation Improvements
- [ ] **Status Aggregation**: Combined status from multiple entities
- [ ] **Custom Aggregation Methods**: User-defined aggregation functions
- [ ] **Aggregation Scheduling**: Configurable update intervals
- [ ] **Historical Aggregation**: Time-based aggregation data

### Performance & Monitoring
- [ ] **Advanced Metrics**: More detailed performance analytics
- [ ] **Alerting**: Performance threshold alerts
- [ ] **Optimization Suggestions**: AI-powered optimization recommendations
- [ ] **Batch Processing**: Enhanced register reading optimization

### Template System
- [ ] **Template Inheritance**: Base templates with overrides
- [ ] **Template Validation**: Enhanced YAML validation
- [ ] **Dynamic Templates**: Runtime template generation
- [ ] **Template Versioning**: Version control for templates

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

### Contributing to TODO Features
If you'd like to contribute to implementing the planned features:
1. Check the TODO list above
2. Create an issue to discuss the implementation
3. Implement the feature with proper tests
4. Update documentation accordingly

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the Home Assistant community's need for better Modbus device management
- Special thanks to all contributors and testers

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/TCzerny/ha-modbus-manager/issues)
- **Discussions**: [Join the community](https://github.com/TCzerny/ha-modbus-manager/discussions)
- **Documentation**: [Full documentation](https://github.com/TCzerny/ha-modbus-manager/wiki)

---

**Made with ❤️ for the Home Assistant community** 