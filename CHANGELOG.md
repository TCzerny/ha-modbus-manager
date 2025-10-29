# Changelog

All notable changes to the HA-Modbus-Manager project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-29

### 🎉 Initial Release

#### ✨ Core Features

- **Template-Based Configuration System**
  - YAML-based device templates for easy setup
  - Support for multiple device templates
  - Template versioning and validation
  - Dynamic template configuration support

- **Multi-Step Configuration Flow**
  - Intuitive UI-driven setup process
  - Connection parameters configuration
  - Dynamic device parameter configuration
  - Firmware version selection
  - Device prefix customization

- **Modbus Coordinator**
  - Central coordinator for all Modbus data updates
  - Intelligent register grouping and batch reading
  - Individual scan intervals per register
  - Automatic register optimization
  - Connection pooling and error recovery

#### 📊 Entity Types

- **Sensors**
  - Full data type support: uint16, int16, uint32, int32, float32, float64, string, boolean
  - IEEE 754 32-bit and 64-bit floating-point conversion
  - Configurable scan intervals
  - Home Assistant device classes and state classes
  - Material Design Icons support

- **Binary Sensors**
  - Template-based binary sensors via Jinja2
  - Availability templates
  - Device class support

- **Controls (Read/Write Entities)**
  - **Number**: Numeric input with min/max/step validation
  - **Select**: Dropdown selection with predefined options
  - **Switch**: On/off control with custom on/off values
  - **Button**: Action triggers for device control
  - **Text**: String input/output entities

- **Calculated Sensors**
  - Jinja2 template-based calculations
  - Derive values from other entities
  - Support for complex mathematical operations
  - Conditional expressions
  - Template placeholder support (`{PREFIX}`)

#### 🔧 Advanced Data Processing

- **Value Processing**
  - **Map**: Direct 1:1 value-to-text mapping
  - **Flags**: Bit-based evaluation with multiple active flags
  - **Options**: Dropdown options for select controls
  - Processing priority: Map → Flags → Options

- **Bit Operations**
  - Bit masking (`bitmask`)
  - Single bit extraction (`bit_position`)
  - Bit range extraction (`bit_range`)
  - Bit shifting (`bit_shift`)
  - Bit rotation (`bit_rotate`)

- **Mathematical Operations**
  - Scale multiplier
  - Offset addition
  - Precision control
  - Sum with scaling (`sum_scale`)

- **Byte Order Support**
  - Big-endian (default) and little-endian
  - Byte swapping for 32/64-bit values
  - String encoding support (UTF-8, ASCII, Latin1)

#### 🏭 Device Templates

- **Sungrow SHx Dynamic Inverter**
  - Complete support for all 36 SHx models
  - Dynamic configuration: phases, MPPT count, battery options, firmware, strings, connection type
  - Multi-step setup: Connection → Dynamic configuration
  - Battery management: SOC, charging/discharging, temperature monitoring
  - MPPT tracking: 1-3 MPPT trackers with power calculations
  - String tracking: 0-4 strings with individual monitoring
  - Grid interaction: Import/export, phase monitoring, frequency
  - Calculated sensors: Efficiency, power balance, signed battery power
  - Firmware compatibility: Automatic sensor parameter adjustment
  - Connection types: LAN and WINET support with register filtering

- **Sungrow SG Dynamic Inverter**
  - 2-step configuration: Connection → Model selection
  - Model selection: Automatic configuration based on selected model
  - Supported models: SG3.0RS, SG4.0RS, SG5.0RS, SG6.0RS, SG8.0RS, SG10RS, SG3.0RT, SG4.0RT, SG5.0RT, SG6.0RT
  - Automatic filtering: Phases, MPPT, Strings configured automatically
  - Firmware support: SAPPHIRE-H firmware compatibility
  - MPPT tracking: 2-3 MPPT trackers based on model
  - Phase support: 1-phase (RS) and 3-phase (RT) models

- **Compleo eBox Professional EV Charger**
  - Complete EV charger template
  - 3-phase charging control
  - Current and power monitoring per phase
  - Cable status and charging status sensors
  - Calculated sensors: Total current, charging power, efficiency
  - Binary sensors: Charging active, cable connected
  - Dynamic configuration: Phases, max current, connectors, connection type

- **Sungrow SBR Battery**
  - Battery system template for Sungrow SBR batteries
  - SOC and capacity monitoring
  - Charging/discharging status
  - Temperature monitoring

#### 🔄 Dynamic Configuration

- **Parameter Selection**
  - User-selectable options during setup
  - Default values support
  - Description text for each parameter

- **Automatic Sensor Filtering**
  - Filter sensors based on device configuration
  - Phase-based filtering (1/3 phases)
  - MPPT-based filtering
  - Battery-based filtering
  - Firmware version compatibility
  - Connection type filtering (LAN/WINET)

- **Firmware Compatibility**
  - Sensor replacements based on firmware version
  - Automatic parameter adjustment
  - Multiple firmware version support

#### 📈 Performance & Monitoring

- **Performance Monitor**
  - Track operation times and success rates
  - Device-specific metrics
  - Global performance metrics
  - Operation history tracking
  - Throughput calculations

- **Register Optimizer**
  - Intelligent grouping of consecutive registers
  - Batch reading for efficiency
  - Minimal Modbus calls
  - Statistics and analysis

#### 🛠️ Services

- **Template Management**
  - `modbus_manager.reload_templates`: Reload device templates without restart
  - Update templates while preserving configuration

- **Performance Monitoring**
  - `modbus_manager.get_performance`: Get performance metrics for device or globally
  - `modbus_manager.reset_performance`: Reset performance metrics

- **Register Optimization**
  - `modbus_manager.optimize_registers`: Get register optimization statistics

- **Device Information**
  - `modbus_manager.get_devices`: Get all configured devices

#### 📚 Documentation

- **Comprehensive Template Documentation** (`docs/README_Template.md`)
  - Complete template structure guide
  - All configuration options explained
  - Examples for all entity types
  - Value processing documentation
  - Best practices

- **Device-Specific Documentation**
  - Sungrow SHx Dynamic template documentation
  - Compleo eBox Professional template documentation

- **Project Documentation**
  - PROJECT_OVERVIEW.md: Architecture and features overview
  - README.md: User installation and usage guide
  - CONTRIBUTING.md: Template creation guidelines

#### 🧹 Code Quality

- **Clean Architecture**
  - Removed legacy SunSpec template support
  - Removed aggregates functionality
  - Removed EMS and Panel functionality
  - Removed diagnostics module
  - Removed unused error_handling module

- **Core Modules**
  - `coordinator.py`: Central data coordinator
  - `template_loader.py`: Template loading and validation
  - `config_flow.py`: UI configuration flow
  - `sensor.py`: Sensor entity implementation
  - `calculated.py`: Calculated sensors with Jinja2
  - `binary_sensor.py`: Binary sensor implementation
  - `number.py`, `select.py`, `switch.py`, `button.py`, `text.py`: Control entities
  - `register_optimizer.py`: Register grouping and optimization
  - `performance_monitor.py`: Performance tracking
  - `value_processor.py`: Central value processing
  - `logger.py`: Custom logging system

#### 🌐 Internationalization

- **Translations**
  - English (en.json)
  - German (de.json)

#### 🏗️ Technical Details

- **Home Assistant Integration**
  - Config flow with dynamic steps
  - Options flow support
  - Device registry integration
  - Entity registry support
  - Service registry

- **Modbus Support**
  - Full Modbus TCP support
  - Input and holding registers
  - Configurable slave IDs
  - Connection timeout and delay settings
  - Message wait time configuration

- **Requirements**
  - pymodbus >= 3.5.2
  - Home Assistant 2025.1.0+
  - Python 3.11+

---

## Future Releases

Future versions will follow semantic versioning:
- **MAJOR** version for breaking changes
- **MINOR** version for new features (backward compatible)
- **PATCH** version for bug fixes (backward compatible)

---

## Contributing

When contributing to this project, please update this changelog with a new entry describing your changes.
