# Changelog

All notable changes to the HA-Modbus-Manager project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2025-01-XX

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

## [2.1.0] - 2024-12-XX

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

## [2.0.0] - 2024-11-XX

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

## [1.0.0] - 2024-10-XX

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

- **v3.0.0**: Sungrow SHx Dynamic Template (Current)
- **v2.1.0**: Home Assistant 2025.12.0 compatibility
- **v2.0.0**: Compleo eBox Professional template
- **v1.0.0**: Initial release with core functionality

## Contributing

When contributing to this project, please update this changelog with a new entry describing your changes.
