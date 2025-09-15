# Changelog

All notable changes to the HA-Modbus-Manager project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2025-01-15

### 🚀 Early Beta Release: SG Dynamic Template

#### ⚠️ Beta Warning
- **SG Dynamic Template is now available as Early Beta for testing and fine-tuning**
- **Controls are NOT TESTED** - Use with caution in production environments
- **Please report any issues** encountered during testing

#### ✨ Added
- **Sungrow SG Dynamic Template** (`sungrow_sg_dynamic.yaml`)
  - **2-Step Configuration**: Connection parameters → Model selection
  - **Model Selection**: Automatic configuration based on selected model
  - **Supported Models**: SG3.0RS, SG4.0RS, SG5.0RS, SG6.0RS, SG8.0RS, SG10RS, SG3.0RT, SG4.0RT, SG5.0RT, SG6.0RT
  - **Automatic Filtering**: Phases, MPPT, Strings configured automatically
  - **Firmware Support**: SAPPHIRE-H firmware compatibility
  - **Connection Types**: LAN and WINET support
  - **MPPT tracking**: 2-3 MPPT trackers based on model
  - **Phase support**: 1-phase (RS) and 3-phase (RT) models
  - **String tracking**: 1 string per model

- **Multi-Step Configuration Flow**
  - Intuitive step-by-step device setup
  - Connection parameters configuration
  - Dynamic device parameter configuration

- **Template Reload Functionality**
  - Update templates without losing configuration
  - Correct sensor filtering during template reload
  - Preserve all current configuration values

#### 🔧 Technical Improvements
- **String Number Extraction**: Improved regex for string sensor filtering (`string[_\s]*(\d+)`)
- **Template Update Filtering**: Correct sensor filtering during template reload
- **NoneType Error Fixes**: Comprehensive error handling for all edge cases
- **Translation Keys**: Added support for `string_count` and `selected_model`
- **Code Quality**: Removed unnecessary debug logging

#### 🐛 Fixed
- **String Sensor Filtering**: Correctly filters string sensors based on `string_count`
- **Template Update**: Uses all current configuration values (phases, mppt_count, string_count, battery_config, etc.)
- **Model Selection**: Properly processes selected model and applies automatic configuration
- **Error Handling**: Comprehensive NoneType error prevention throughout the codebase

## [0.5.0] - 2025-01

### 🎉 Major Release: Dynamic Configuration & Float Conversion

#### ✨ Added
- **Dynamic Template Configuration (Fully Functional)**
  - Automatic sensor filtering based on device parameters
  - Phase filtering (1/3 phases) with automatic exclusion
  - MPPT filtering (1-3 trackers) with intelligent detection
  - Battery filtering with comprehensive keyword detection
  - Firmware version compatibility with sensor replacements
  - Connection type filtering (LAN/WINET register availability)
  - Debug logging for filtering decisions

- **Complete Float Conversion Support**
  - IEEE 754 32-bit (float32) floating-point conversion
  - IEEE 754 64-bit (float64) floating-point conversion
  - Automatic count=2 assignment for float32 data types
  - Byte order handling for different endianness
  - Error handling for invalid float values

- **Services & Diagnostics**
  - `modbus_manager_optimize_registers` service for register optimization
  - `modbus_manager_get_performance` service for performance metrics
  - `modbus_manager_reset_performance` service for metrics reset
  - Comprehensive diagnostics panel via Home Assistant UI
  - Performance monitoring with success rates and operation tracking
  - Register optimization statistics and batch reading analysis

#### 🔧 Enhanced
- **Template Processing**
  - Use filtered registers from config entry instead of reloading template
  - Process calculated sensors and controls with dynamic filtering
  - Improved firmware version handling for non-semantic versions
  - Enhanced debug logging for troubleshooting

- **Performance Optimization**
  - Register grouping for efficient batch reading
  - Performance monitoring with detailed metrics
  - Connection pooling and error recovery
  - Intelligent polling based on data type

#### 🧹 Refactored
- **String Count Parameter Removal**
  - Removed unnecessary string_count parameter from dynamic config
  - Eliminated string filtering logic (no string-specific sensors exist)
  - Simplified function signatures and reduced complexity
  - Updated template structure and documentation

#### 📚 Documentation
- Updated README.md: Marked as production ready
- Updated info.md: Added float conversion and services features
- Updated TODO.md: Marked major features as completed
- Updated PROJECT_OVERVIEW.md: Added diagnostics and float64 support
- Updated CONTRIBUTING.md: Added template feature requirements

#### 🏗️ Technical
- Fixed dynamic filtering to work with both sensor_name and unique_id
- Improved error handling for firmware version parsing
- Enhanced logging levels (INFO for important messages, DEBUG for details)
- Converted remaining German comments and messages to English

#### 🙏 Acknowledgments
- **mkaiser**: Outstanding Sungrow SHx Modbus implementation
- **Home Assistant Community**: Great platform and support
- **Community Contributors**: Device testing and feedback

## [0.4.0] - 2025-08

### 🎉 Major Release: Sungrow SHx Dynamic Template

#### ✨ Added
- **Sungrow SHx Dynamic Template v1.0.0**
  - Complete dynamic configuration for all 36 SHx models
  - Automatic register filtering based on device configuration
  - Firmware compatibility with SAPPHIRE-H_03011.95.01
  - Support for 1-3 phases, 1-3 MPPT trackers, battery options
  - LAN and WINET connection type support
  - Comprehensive calculated sensors and controls

#### 🔧 Enhanced
- **Dynamic Template Configuration**
  - ConfigFlow extended for dynamic parameters
  - Template filtering based on configuration
  - Firmware version compatibility system
  - Connection type filtering (LAN/WINET)

#### 📚 Documentation
- Complete English documentation for Sungrow SHx Dynamic Template
- Comprehensive README with all 36 supported models
- Acknowledgments section for mkaiser and community contributions
- Updated main README and info.md

#### 🏗️ Technical
- Template renamed from `sungrow_shx_dynamic_complete.yaml` to `sungrow_shx_dynamic.yaml`
- Version updated to 1.0.0 for the template
- Firmware version default changed to `SAPPHIRE-H_03011.95.01`
- All German comments and documentation converted to English

#### 🙏 Acknowledgments
- **mkaiser**: Outstanding Sungrow SHx Modbus implementation
- **photovoltaikforum.com**: Reverse-engineering efforts
- **forum.iobroker.net**: Community contributions

## [0.3.0] - 2024-12

### 🔧 Fixed
- **Home Assistant 2025.12.0 Compatibility**
  - Removed `via_device` references causing warnings
  - Updated device registry integration
  - Fixed deprecation warnings

### 🛠️ Improved
- **Modbus Parameter Management**
  - Removed unsupported Modbus parameters
  - Kept only `delay` and `timeout` parameters
  - Updated `__init__.py` to use user-configured values

### 📊 Enhanced
- **Template Validation**
  - Auto-count logic for `float32` data types
  - Improved validation for `scan_interval: 0`
  - Better error handling and warnings

## [0.2.0] - 2024-11

### ✨ Added
- **Compleo eBox Professional Template**
  - Complete EV charger integration
  - 3-phase charging control
  - Current and power monitoring
  - Fallback current settings

### 🔧 Enhanced
- **Aggregate Sensors**
  - Real-time aggregation across multiple devices
  - Group-based sensor aggregation
  - Performance monitoring and optimization

### 📚 Documentation
- Comprehensive GitHub Wiki
- Device-specific documentation
- Aggregate sensors guide

## [0.1.0] - 2024-10

### 🎉 Initial Release
- **Core Modbus Manager Integration**
  - Template-based configuration system
  - Multi-device support
  - UI-driven setup process
  - Automatic entity generation

### ✨ Features
- **Device Templates**
  - YAML-based template system
  - Extensible architecture
  - Comprehensive validation

- **Entity Types**
  - Sensors, binary sensors, numbers
  - Selects, switches, buttons, text
  - Full data type support

- **Advanced Processing**
  - Bit operations and masking
  - Enum mapping and flags
  - Mathematical operations

---

## Version History

- **v0.4.0**: Sungrow SHx Dynamic Template (Current)
- **v0.3.0**: Home Assistant 2025.12.0 compatibility
- **v0.2.0**: Compleo eBox Professional template
- **v0.1.0**: Initial release with core functionality

## Contributing

When contributing to this project, please update this changelog with a new entry describing your changes.
