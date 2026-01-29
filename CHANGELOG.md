# Changelog

All notable changes to the HA-Modbus-Manager project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.7] - 2026-01-29

### ✨ Added
- **Condition Filtering**: Added `in` / `not in` list support for `condition` statements
  - Enables model-specific inclusion like `selected_model in [SG33CX, SG40CX]`
  - Works across config flow, options flow, and coordinator filtering

### 🐛 Fixed
- **Offline Setup**: Prevent setup from hanging when Modbus host is unreachable
  - Coordinator setup now proceeds in offline mode if connect fails or times out
  - Coordinator reconnect attempts now honor the configured timeout
- **Calculated Sensors**: Avoid template errors when source entities are unavailable
  - Added availability guards and `float(0)` conversions for SG calculated status sensors
- **HA Standard Offline Handling**: Mark entities unavailable on connection loss
  - Coordinator now raises `UpdateFailed` when hub is offline

### 📚 Documentation
- **Template Docs**: Documented condition syntax and model list usage in `docs/README_Template.md`
- **README**: Added note about offline entity availability and retry behavior

---

## [0.1.6] - 2026-01-15

### ✨ Added

#### iHomeManager EMS Support
- ⚠️ **BETA**: iHomeManager support is in beta testing and requires end-user testing. Please report any issues you encounter.
- **Meter Type Selection**: Added `meter_type` dynamic configuration option for Sungrow SHx template
  - Options: `DTSU666` (standard), `DTSU666-20` (dual-channel), `iHomeManager` (EMS)
  - Default: `DTSU666`
  - Conditional register loading ensures only compatible registers are loaded based on selected meter type

- **iHomeManager Input Registers**: Added comprehensive iHomeManager-specific input registers
  - **Device Information**: Device type code, protocol number/version, total devices connected, devices in fault
  - **System Capacity**: Total nominal active power, total battery rated capacity
  - **Battery Limits**: Charge/discharge limits, min/max charge/discharge power
  - **Real-Time Power**: Total active power, load power, battery power
  - **Battery State**: Battery level (SoC)
  - **Energy Totals**: Grid import/export energy
  - **Grid Meter Channel 1**: Output type, phase voltages (A/B/C), frequency, phase active power (A/B/C)
  - **Grid Meter Channel 2**: Phase voltages (A/B/C), frequency, phase active power (A/B/C)
  - **Charger Status**: Charger status raw value

- **iHomeManager Holding Registers (Controls)**: Added iHomeManager-specific controls
  - **EMS Mode Selection**: Select control for energy management mode (Self-consumption, Time-of-use, Fixed charge/discharge, External EMS, VPP)
  - **Battery Forced Charge/Discharge**: Select control (Auto, Charge, Discharge, Standby) and power setting (0-100 kW)
  - **Export Power Limit**: Export power limit mode (Disabled, Absolute, Percentage) and limit value (0-100 kW)
  - **Export Power Limit Ratio**: Percentage-based export limit (0-1000%)

- **Conditional Loading Enhancement**: Enhanced template_loader.py to support `AND` and `!=` operators in condition statements
  - Enables more complex filtering logic (e.g., `meter_type != 'iHomeManager'`, `meter_type == 'DTSU666' or meter_type == 'DTSU666-20'`)

- **Standardized Naming**: Standardized `unique_id` and `name` fields for functionally equivalent registers across meter types
  - Same `unique_id` used for equivalent registers (e.g., `meter_active_power_raw` for both DTSU666 and iHomeManager)
  - Filtering based on `meter_type` condition ensures correct register is loaded

### 🔧 Changed

#### Sungrow SHx Dynamic Template v1.2.6
- **Template Version**: Updated from v1.2.5 to v1.2.6
- **Meter Type Configuration**: Added `meter_type` to dynamic configuration with three options
- **Register Addresses**: iHomeManager uses different addresses than DTSU666:
  - Total power: 8156 (scale: 10) vs 5600 (scale: 1)
  - Phase power: 8558-8562 (scale: 1) vs 5602-5606 (scale: 1)
  - All iHomeManager power values use scale 10 (0.1W units)
- **Entity ID Handling**: Added `default_entity_id` support to enforce deterministic entity IDs
  - Default: `default_entity_id` is set from `unique_id` (with prefix)
  - If provided in the template, the entity is created with the exact `entity_id`

### 🐛 Fixed

#### Bug Fixes & Code Cleanup
- **Solvis SC3 Template**: Fixed Warmwasser Nachheizung register address (changed from 2328 to 2322)
- **Solvis SC3 Template**: Changed default prefix from "solvis" to "SC3" for consistency
- **Meter Type Handling**: Fixed `meter_type` handling and improved dynamic config processing
- **Entity Implementation**: Code cleanup and improvements to follow Home Assistant Entity guidelines:
  - Set `has_entity_name = True` in all entity classes (mandatory for new integrations)
  - Fixed `unique_id` bug in binary_sensor.py (removed incorrect `generate_entity_id` wrapper)
  - Added `EntityCategory.CONFIG` for switches, numbers, selects, buttons, text (configuration entities)
  - Added `EntityCategory.DIAGNOSTIC` for binary_sensors and diagnostic sensors
  - Reduced `extra_state_attributes` to minimize database size (removed frequently changing attributes)
  - Added `async_added_to_hass()` lifecycle hooks to sensor, number, select entities
  - Fixed device membership for proper `friendly_name` generation

### 📚 Documentation

- **README.md**: Updated with iHomeManager support information
- **Wiki**: Updated Sungrow SHx Dynamic documentation with complete iHomeManager register tables
- **CHANGELOG.md**: Added comprehensive changelog entry for iHomeManager support

## [0.1.5] - 2026-01-08

### ✨ Added
- **Template Placeholders for Model-Specific Values**: Added support for placeholders in control `max_value` fields
  - Use `{{max_charge_power}}`, `{{max_discharge_power}}`, `{{max_ac_output_power}}` in templates
  - Supports calculations: `{{max_charge_power * 0.5}}` for 50% limits, `{{max(max_charge_power, max_discharge_power)}}` for maximum values
  - Supports built-in functions: `max()`, `min()`, `abs()`, `round()`, `int()`, `float()`
  - Automatically converts W to kW when control unit is "kW"
  - Placeholders are replaced at runtime based on `selected_model` from `dynamic_config.valid_models`
  - Example: `max_value: "{{max_charge_power}}"` → `10.6` for SH10RT (10600 W / 1000)
  - Applied to: Battery Max Charging/Discharging Power, Export Power Limit, Battery Start Power, Battery Forced Charge Discharge Power

### 🔧 Fixed
- **Generic Model Config Extraction**: Fixed `_extract_config_from_model` to automatically extract ALL fields from model configuration
  - Now properly includes `max_charge_power`, `max_discharge_power`, `max_ac_output_power` in `dynamic_config`
  - Future-proof: Any new fields added to template `valid_models` will be automatically extracted
  - Makes template extensions work without requiring coordinator code changes

- **Template Reload with Model-Specific Limits**: Fixed config/options flow to apply model-specific power limits during template reload
  - Added global helper function `_adjust_control_limits_for_model()` for consistent limit adjustment
  - Config flow and options flow now both adjust control max/min values based on `selected_model`
  - Template reload now correctly updates power limits without requiring device deletion/re-adding
  - Added automatic migration: Legacy config format is automatically converted to devices array format on template reload
  - Preserves `selected_model` during migration to ensure power limits work correctly after upgrade

## [0.1.4] - 2026-01-07

### ✨ Added

#### Home Assistant Energy Dashboard Compatible Sensors
- **New Calculated Sensors for HA Energy Dashboard**: Added signed power sensors following HA Energy Dashboard convention
  - `battery_charging_power_signed` - Positive when charging (for display purposes)
  - `battery_discharging_power_signed` - Positive when discharging (matches HA convention)
  - `grid_power_signed` - Negative when exporting (generation), positive when importing (consumption)
  - `grid_export_power_signed` - Only export power as negative values
  - `grid_import_power_signed` - Only import power as positive values
  - Convention: Positive = consumption/discharging/import, Negative = generation/charging/export

#### PV Analysis & Performance Metrics
- **New Calculated Sensors for PV Inverter Analysis**:
  - `self_consumption_rate` - Percentage of PV generation consumed directly (not exported to grid)
  - `autarky_rate` - Percentage of load supplied by PV/Battery (self-sufficiency)
  - `grid_dependency` - Percentage of load that depends on grid (inverse of autarky)
  - `dc_to_ac_efficiency` - Inverter efficiency (AC output / DC input)
  - `pv_capacity_factor` - Current PV power as percentage of inverter rated capacity
  - `pv_generation_hours_today` - Equivalent generation hours at current power level

#### Energy Flow Analysis Sensors
- **New Energy Flow Breakdown Sensors**:
  - `pv_to_load_direct` - PV power going directly to load (without battery)
  - `pv_to_battery` - PV power charging battery
  - `battery_to_load` - Battery power going to load (discharging)
  - `grid_to_load` - Grid power going to load (importing)
  - `net_consumption` - Net consumption after PV and battery supply

#### MPPT Performance Analysis
- **New MPPT Analysis Sensors**:
  - `mppt_power_deviation` - Maximum deviation from average MPPT power (imbalance indicator)
  - `mppt_utilization` - Percentage of DC power from MPPT trackers (should be close to 100%)
  - `mppt4_power` - Power calculation for MPPT4 tracker

#### Battery Temperature Module Info Sensors
- **New Human-Readable Temperature Sensors** (Sungrow SBR Battery):
  - `Battery 1 Max Temperature Module Info` - Shows "Module Position X (YY.Y °C)"
  - `Battery 1 Min Temperature Module Info` - Shows "Module Position X (YY.Y °C)"
  - Similar format to existing voltage cell info sensors

#### Dashboard Examples
- **New PV Analysis Dashboards**:
  - `sungrow_pv_analysis_standard.yaml` - Standard HA cards with new Sections layout
  - `sungrow_pv_analysis_mushroom.yaml` - Mushroom cards with new Sections layout
  - `sungrow_pv_analysis_simple.yaml` - Simplified version with built-in HA cards only
  - All dashboards include new calculated sensors for PV analysis
  - Use new Home Assistant Sections layout (replaces HStack/VStack)

#### Dual-Channel Meter Support
- **New Dynamic Config Option**: `dual_channel_meter` for Sungrow SHx template
  - Allows users to enable/disable Meter Channel 2 sensors
  - Default: `false` (disabled)
  - Only registers Meter Channel 2 sensors when explicitly enabled
  - Prevents errors for users without dual-channel meters (e.g., DTSU666-20)

#### Condition Processing Enhancement
- **Extended Condition Support**: Added `==` operator support for conditions
  - Supports boolean comparisons (`dual_channel_meter == true`)
  - Supports integer comparisons (`phases == 3`)
  - Supports string comparisons
  - Works alongside existing `>=` operator

#### Firmware Version Filtering
- **Config Flow Filtering**: Added `firmware_min_version` filtering to `config_flow.py`
  - Sensors with `firmware_min_version` are now filtered during setup
  - Prevents registration of sensors that require newer firmware
  - Works in both initial setup and options flow

### 🔧 Changed

#### Sungrow SHx Dynamic Template v1.2.0
- **Battery Power Register Update**: Changed to recommended register (Protocol V1.1.11)
  - Old: Address 13021 (reg 13022, int16)
  - New: Address 5213 (reg 5214-5215, int32, swap: word)
  - More accurate battery power readings

- **Battery Current Register Update**: Updated to recommended register
  - Old: Address 13020 (reg 13021)
  - New: Address 5630 (reg 5631)

- **New Firmware Information Sensors**:
  - Inverter Firmware Info (Address 13250, String, 15 registers)
  - Communication Module Firmware Info (Address 13265, String, 15 registers)
  - Battery Firmware Info (Address 13280, String, 15 registers)

- **New Battery Capacity High Precision Sensor**:
  - Address 5638 (reg 5639, U16, 0.01 kWh)
  - More accurate battery capacity readings

- **Meter Channel 2 Data Sensors** (Conditional):
  - Total Active Power (Address 13199, int32)
  - Phase A/B/C Active Power (Addresses 13201/13203/13205, int32)
  - Only registered when `dual_channel_meter` is enabled

- **Dynamic Power Limits**:
  - Battery Max Charge/Discharge Power: Dynamically adjusted based on selected model
  - Export Power Limit: Dynamically adjusted based on `max_ac_output_power`
  - Battery Charging/Discharging Start Power: Set to 50% of respective max power
  - Limits based on inverter datasheet specifications

- **Safety Improvements**:
  - Runtime validation for battery power limits (0.5C/1C rate)
  - Warnings added to battery power controls
  - Max values set to lowest safe defaults

- **Register Updates for SHxRT Models**:
  - Updated various register addresses for improved compatibility with SHxRT series
  - Enhanced register mapping accuracy

#### Device Firmware Display
- **Firmware Priority**: Device firmware now shows register value if available, otherwise config value
  - Reads firmware from `inverter_firmware_info` register (13250)
  - Updates device registry automatically
  - Falls back to firmware version from config flow

### 🐛 Fixed

- **Calculated Sensors with String Values**: Fixed `ValueError` for calculated sensors returning string values
  - Removed `suggested_display_precision` automatically for string sensor values
  - Prevents validation errors when sensors return formatted strings (e.g., "Cell Position 520 (3.3500 V)")
  - System now dynamically removes precision attribute for non-numeric values
  - Fixes issue where sensors with `state_class: measurement` and string values caused errors

- **Cell Info Sensor Template Logic**: Fixed template logic for Cell Info sensors to handle sensor states correctly
  - Improved handling of `unknown` and `unavailable` states
  - Better fallback logic for missing values

- **Firmware Version Filtering**: Fixed missing firmware version filtering in config flow
  - Sensors with `firmware_min_version` are now properly excluded during setup
  - Prevents errors when reading registers that don't exist on older firmware

- **Calculated Sensor Availability**: Fixed calculated sensors not appearing in Home Assistant Helper UI
  - Added `should_poll = True` to `ModbusCalculatedSensor`
  - Sensors now available for Riemann Integral and other helpers

- **Battery Power Values**: Fixed incorrect battery power readings
  - Corrected Modbus address (5213 instead of 5214)
  - Proper handling of int32 with word swap

### 📚 Documentation

- **Updated Template Documentation**:
  - Updated `README_sungrow_shx_dynamic.md` with all new calculated sensors
  - Added sections for PV Analysis, Energy Flow Analysis, and HA Energy Dashboard compatibility
  - Updated `README_Template.md` with notes on string value handling and precision control
  - Added documentation for new dashboard examples

- **Dashboard Examples**:
  - Updated `Dashboard-Examples/README.md` with PV analysis dashboard documentation
  - Added comprehensive documentation for all dashboard examples (battery and PV)
  - Documented new HA Sections layout usage

- **General Documentation**:
  - Updated CHANGELOG.md with all changes since v0.1.3
  - Added documentation for dual-channel meter configuration
  - Updated Sungrow template documentation with new registers
  - Added `BATTERY_CELL_POSITION.md` documentation for battery cell position sensors

---

## [0.1.3] - 2025-11-24

### 🐛 Fixed

#### Critical Bug Fixes
- **Issue #3 - Config Flow Self Reference**: Fixed `AttributeError` when updating templates from options flow
  - Added missing `_process_dynamic_config` and helper methods to `ModbusManagerOptionsFlow`
  - Template updates now work correctly from device options menu
  - Fixes crash when trying to update template version from options

- **Issue #2 - Modbus Write Operations**: Fixed incorrect use of `CALL_TYPE_REGISTER_HOLDING` for write operations
  - Changed to `CALL_TYPE_WRITE_REGISTERS` in `select.py`, `number.py`, and `switch.py`
  - Write operations now use correct Modbus call type constant
  - Improves compatibility with Modbus protocol standards

- **Number Entity Scaling**: Fixed incorrect scaling when writing number values to Modbus registers
  - Now uses `scale` from config if available, falls back to `multiplier`, defaults to 1.0
  - Fixes issue where setting SOC Min to 7.0 resulted in 0.7 in inverter
  - Added debug logging for write operations to track scaling calculations

### 🔧 Changed

#### Logging Improvements
- **Reduced Log Noise**: Changed unnecessary info-level logs to debug level
  - "Successfully set" logs now at debug level (number, select entities)
  - "Created X entities" logs now at debug level (all entity types)
  - Setup-related logs moved to debug level
  - Only errors and important warnings remain at info/warning level
  - Reduces log noise during normal operation

### 📚 Documentation

- Updated changelog with all fixes and improvements since v0.1.2

---

## [0.1.2] - 2025-11-07

### 🔧 Changed

#### Compleo eBox Professional Template v3.0.0
- **Firmware Version Filtering**: Voltage sensors and energy meter reading now require firmware version 2.0.34 or higher
  - Voltage Phase 1, 2, 3 sensors: Only available with firmware 2.0.34+
  - Energy Meter Reading sensor: Only available with firmware 2.0.35+
  - Average Voltage calculated sensor: Only available with firmware 2.0.34+
  - Voltage Imbalance calculated sensor: Only available with firmware 2.0.35+
  - Sensors are automatically filtered based on selected firmware version during setup
  - Prevents errors when using older firmware versions that don't support these registers

- **Energy Meter Reading Sensor Correction**:
  - Corrected sensor name: "Current Meter Reading" → "Energy Meter Reading"
  - Corrected unit: "A" → "kWh"
  - Corrected device_class: "current" → "energy"
  - Corrected state_class: "measurement" → "total_increasing"
  - Added scale: 1 (register value is already in kWh)

- **Voltage Imbalance Calculated Sensor Fix**:
  - Removed incorrect device_class: "voltage" (unit is "%", not "V")
  - Corrected firmware_min_version: "2.0.35"

#### Config Flow Improvements
- **Dynamic Config Defaults**: Default values are now properly displayed in dynamic configuration form
  - All fields with `options` now use `vol.Optional()` with `default` parameter
  - Connection type and firmware version defaults are correctly set
  - Fixes issue where only firmware_version was pre-selected in dynamic config dialog

- **Device Addition Fix**: When adding a device to existing hub, all required fields are now properly saved
  - `firmware_version`, `template_version`, `selected_model`, and `type` are now included in device dict
  - Ensures firmware filtering works correctly for newly added devices

#### Coordinator Improvements
- **Unloading Handling**: Coordinator now properly stops updates when being unloaded
  - Added `_is_unloading` flag to prevent register reads during unload
  - Suppresses warnings for failed register reads during reload/unload operations
  - Cache is invalidated before unloading to prevent stale data

#### Template Structure Improvements
- **Firmware Version Configuration**: All templates now use `firmware_version` in `dynamic_config` with `options`
  - Removed dependency on `available_firmware_versions` at template level
  - Consistent structure across all templates (SHx, SG, eBox, SBR)
  - Firmware version selection works correctly in dynamic config dialog

### 📚 Documentation

- Updated `README_compleo_ebox_professional.md` with firmware version requirements
- Added firmware version selection information and entity reference tables
- Clarified which sensors require which firmware versions
- Updated GitHub Wiki documentation for Compleo eBox Professional template
- Corrected Energy Meter Reading documentation (kWh instead of A)

---

## [0.1.1] - 2025-11-07

### ✨ Added

#### Switch Controls Enhancement
- **Enhanced Switch State Interpretation**: Switches now support `on_value` and `off_value` for custom state interpretation
  - Allows switches to correctly interpret non-standard ON/OFF values (e.g., 0xAA/0x55)
  - Automatic fallback: If `on_value`/`off_value` not specified, uses `write_value`/`write_value_off` as defaults
  - Supports devices that use custom values instead of standard 0/1 or 1/0

#### Sungrow SHx Dynamic Template v1.1.0
- **New Control**: "Forced Startup Under Low SoC Standby" (Address 13016)
  - Resolves issue with SH10RT inverters not entering standby mode after firmware update (mkaiser issue #444)
  - Allows forced startup when battery is in low SoC standby mode
  - Values: 0xAA (Enabled) / 0x55 (Disabled)
  - Implemented as Select control for reliable state interpretation

- **New Sensor**: "Forced Startup Under Low SoC Standby raw" (Address 13016)
  - Read-only sensor for monitoring the current state of the forced startup setting
  - Useful for automation and status monitoring

### 🔧 Changed

- **Switch Implementation**: Improved switch state interpretation logic
  - Better handling of custom ON/OFF values
  - Automatic value mapping from write values to read values
  - Warning logging for unexpected register values

### 📚 Documentation

- Updated `README_sungrow_shx_dynamic.md` with new control and sensor documentation
- Enhanced `README_Template.md` with detailed Switch control configuration examples
- Added examples for custom value switches (0xAA/0x55 pattern)

---

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
