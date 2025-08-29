# TODO: Planned Features for Modbus Manager

This document tracks planned features that are described in the README but not yet implemented in the code.

## 🧠 Modbus Manager Refactor – Architecture & Feature Summary

### 👤 Developer: TCzerny  
### 📦 Project: [ha-modbus-manager](https://github.com/TCzerny/ha-modbus-manager)  
### 📅 Status: August 2025  

---

## 🧱 Architecture Overview

Goal: A modular, template-driven platform for managing Modbus devices in Home Assistant – scalable for PV inverters, heat pumps, wallboxes, HVAC systems, heating systems, and more.

### 🔧 Components
- `template_loader.py`: Parser for `registers`, `calculated`, `controls`
- `entity_factory.py`: Creates entities from template data
- `controls.py`: Direct Modbus control (`number`, `select`, `button`)
- `calculated.py`: Calculated sensors via Jinja2
- `async_setup_entry()`: Setup + version comparison + addition of new entities

### 📁 Template Structure

Templates are located under `device_definitions/*.yaml` and contain:

- `registers:` → Modbus sensors  
- `calculated:` → Calculated sensors via Jinja2  
- `controls:` → Direct Modbus control (`number`, `select`, `button`)  
- `version:` → Template versioning for update detection  
- `type:` → Device type (e.g. `inverter`, `heatpump`, `wallbox`)  

### 🧩 Modules

| File                   | Function                                           |
|------------------------|----------------------------------------------------|
| `template_loader.py`   | Loads and validates templates                      |
| `entity_factory.py`    | Creates entities from template data                |
| `controls.py`          | Direct Modbus control                              |
| `calculated.py`        | Calculated sensors with Jinja2                     |
| `modbus_device.py`     | Central device class                               |
| `config_flow.py`       | UI setup for devices                               |

---

## 📘 Modbus Standards & Mapping Architecture – Summary

## 🧱 Base Strategy

- Goal: Unified standardization of Modbus devices through base templates
- Approach:
  - One `*_base.yaml` per device type with complete register structure and advanced processing
  - Manufacturer/model mappings attach themselves via `extends:` to the appropriate base
  - All registers from source (e.g. mkaiser, own YAMLs) are fully adopted

---

## 📦 Available Base Standards

| Base File                  | Device Type / Industry                     |
|----------------------------|-----------------------------------------|
| `sunspec_base.yaml`        | PV inverters, storage, smart meters, wallboxes (SunSpec)  
| `dlms_base.yaml`           | Energy meters (DLMS/COSEM)  
| `vdma24247_base.yaml`      | Heat pumps / heating systems  
| `hvac_base.yaml`           | HVAC / refrigeration systems  
| `ocpp_evse_base.yaml`      | Wallboxes with OCPP mapping  
| `ups_base.yaml`            | UPS systems  
| `iec61131_base.yaml`       | PLC / I/O modules  
| `bhkw_base.yaml`           | Combined heat and power / generators  
| `bms_base.yaml`            | Battery management systems  
| `mbus_meter_base.yaml`     | Water, gas, heat meters via M-Bus  
| `pq_analyzer_base.yaml`    | Power quality analyzers  

---

## ⚙️ Advanced Data Processing Features (integrated in all bases)

```yaml
offset: 0.0
multiplier: 1.0
sum_scale: []
shift_bits: 0
bits: []
float: false
string: false
control: "none"
min_value: 0.0
max_value: 100.0
step: 1.0
options: {}
```

---

## 🏭 Manufacturer Mapping Examples

### 📋 Manufacturer-Map (Excerpt)

| Manufacturer / Model | Base File | Mapping File |
|----------------------|-----------|--------------|
| Fronius GEN24 | `sunspec_base.yaml` | `map_gen24.yaml` |
| SMA Sunny Boy | `sunspec_base.yaml` | `map_sunnyboy.yaml` |
| Sungrow SH10RT | `sunspec_base.yaml` | `map_sh10rt.yaml` |
| BYD BatteryBox | `sunspec_base.yaml` | `map_byd.yaml` |
| Pylontech US | `bms_base.yaml` | `map_pylontech.yaml` |
| Viessmann Vitocal | `vdma24247_base.yaml` | `map_vitocal.yaml` |
| Kamstrup Multical | `mbus_meter_base.yaml` | `map_multical.yaml` |
| APC Smart-UPS | `ups_base.yaml` | `map_smartups.yaml` |
| WAGO PFC | `iec61131_base.yaml` | `map_pfc.yaml` |

---

## 🧩 Missing / Optional Base Standards

| Suggestion | Description / Device Examples |
|------------|-------------------------------|
| `drive_base.yaml` | Frequency converters (ABB, Siemens, Danfoss) |
| `rtu_base.yaml` | Remote terminal units / SCADA-RTUs |
| `sensor_base.yaml` | Process sensors (pressure, flow, level) |
| `fire_base.yaml` | Fire alarm and safety systems |
| `dali_base.yaml` | Lighting control / DALI gateways |
| `tank_base.yaml` | Tank/silo management systems |
| `lab_base.yaml` | Laboratory/analysis devices (pH, conductivity) |

---

## 📌 Next Steps for Base Standards

- [ ] Generate mapping files for all mkaiser devices completely
- [ ] Add Solvis heating as mapping on `vdma24247_base.yaml`
- [ ] Create base standards for missing device types
- [ ] Update `manufacturer_map.md` regularly
- [ ] Optional: Import script for automatic mapping creation from external YAMLs

---

## ✅ ToDo List

### 🔧 Parsing & Structure
- [x] Modular template parser (`template_loader.py`)
- [x] Prefix placeholder `{prefix}` in `calculated.template`
- [x] Support for `data_type`, `length`, `bitmask`
- [ ] Template versioning (`version:`) + comparison

### 🧠 Entities
- [x] `ModbusRegisterSensor`
- [x] `CalculatedSensor`
- [x] `ModbusNumberEntity`, `ModbusSelectEntity`, `ModbusButtonEntity`

### 🚀 Setup & Update
- [x] Check Entity Registry → no duplicates
- [x] Add new entities on version jump
- [ ] Save `template_version` in `config_entry`

### 📁 Templates
- [x] `heatpump_generic.yaml`
- [ ] `wallbox_generic.yaml`
- [ ] `hvac_generic.yaml`

### 🧠 UI & Options
- [ ] Display template version in `config_flow.py`
- [ ] UI option "Update template"

---

## 🚧 Advanced Data Processing

### Float Conversion
- [ ] **Automatic 32-bit IEEE 754 float conversion**
  - Implement proper float register handling
  - Support for different byte orders
  - Validation of float values
  - Error handling for invalid floats

### String Processing
- [ ] **Enhanced string handling and validation**
  - Better string encoding support
  - String length validation
  - Null character handling
  - String truncation options

### Advanced Bit Operations
- [ ] **More complex bit manipulation functions**
  - Bit rotation operations
  - Bit field extraction
  - Bit pattern matching
  - Advanced bit masking

### Data Validation
- [ ] **Input validation and error checking**
  - Range validation for numeric values
  - Type checking and conversion
  - Error reporting and recovery
  - Data integrity checks

## 🎛️ Entity Enhancements

### Custom Icons
- [ ] **Template-based icon configuration**
  - Support for `icon` parameter in templates
  - Dynamic icon selection based on values
  - Icon inheritance from device types
  - Custom icon sets

### Entity Categories
- [ ] **Support for entity_category parameter**
  - `config` category for configuration entities
  - `diagnostic` category for diagnostic entities
  - `system` category for system entities
  - UI integration for categories

### Advanced Control
- [ ] **More sophisticated control entity types**
  - Advanced number controls with validation
  - Multi-select entities
  - Slider controls
  - Button groups

### Conditional Logic
- [ ] **Template-based conditional entity creation**
  - Conditional entity visibility
  - Dynamic entity properties
  - State-based entity creation
  - Template expressions

## 📊 Aggregation Improvements

### Status Aggregation
- [ ] **Combined status from multiple entities**
  - Status combination logic
  - Priority-based status selection
  - Status conflict resolution
  - Custom status aggregation rules

### Custom Aggregation Methods
- [ ] **User-defined aggregation functions**
  - Custom aggregation scripts
  - Mathematical expressions
  - Statistical functions
  - User-defined algorithms

### Aggregation Scheduling
- [ ] **Configurable update intervals**
  - Per-aggregation update schedules
  - Time-based aggregation
  - Event-driven updates
  - Performance optimization

### Historical Aggregation
- [ ] **Time-based aggregation data**
  - Historical data storage
  - Trend analysis
  - Statistical summaries
  - Data retention policies

## 📈 Performance & Monitoring

### Advanced Metrics
- [ ] **More detailed performance analytics**
  - Response time distribution
  - Error rate analysis
  - Throughput optimization
  - Resource usage monitoring

### Alerting
- [ ] **Performance threshold alerts**
  - Configurable thresholds
  - Alert notifications
  - Escalation rules
  - Alert history

### Optimization Suggestions
- [ ] **AI-powered optimization recommendations**
  - Register grouping suggestions
  - Polling interval optimization
  - Connection parameter tuning
  - Performance improvement tips

### Batch Processing
- [ ] **Enhanced register reading optimization**
  - Intelligent batch sizing
  - Register grouping algorithms
  - Priority-based reading
  - Adaptive optimization

## 📝 Template System

### Template Inheritance
- [ ] **Base templates with overrides**
  - Base device templates
  - Template extension system
  - Override mechanisms
  - Template composition

### Template Validation
- [ ] **Enhanced YAML validation**
  - Schema validation
  - Cross-reference checking
  - Dependency validation
  - Error reporting

### Dynamic Templates
- [ ] **Runtime template generation**
  - Dynamic sensor creation
  - Conditional templates
  - Template adaptation
  - Runtime customization

### Template Versioning
- [ ] **Version control for templates**
  - Template versioning
  - Migration support
  - Backward compatibility
  - Version management

## 🔧 Technical Improvements

### Error Handling
- [ ] **Enhanced error handling and recovery**
  - Graceful degradation
  - Automatic retry mechanisms
  - Error categorization
  - User-friendly error messages

### Configuration Management
- [ ] **Advanced configuration options**
  - Configuration profiles
  - Import/export functionality
  - Configuration validation
  - Migration tools

### Testing Framework
- [ ] **Comprehensive testing suite**
  - Unit tests for all components
  - Integration tests
  - Performance tests
  - Template validation tests

### Documentation
- [ ] **Complete documentation**
  - API documentation
  - Template examples
  - Troubleshooting guides
  - Video tutorials

## 🚀 Discussion-Inspired Features

### Template Sensors (Mathematical Calculations)
- [ ] **Automatic Power Calculations**
  - MPPT Power = Voltage × Current
  - Phase Power = Voltage × Current
  - Battery Power with direction detection
  - Energy consumption calculations
  - Real-time mathematical operations

### Advanced Binary Sensors
- [ ] **Bit-based Status Sensors**
  - Direct bit extraction from registers
  - PV generating, battery charging/discharging
  - Power flow detection (export/import)
  - Load powering status
  - Delay-based status updates

### Input Entity Integration
- [ ] **Native Input Support**
  - Input numbers for configuration values
  - Input selects for mode selection
  - Bidirectional synchronization
  - Real-time value updates
  - Validation and constraints

### Automation & Scripts
- [ ] **Built-in Automation Support**
  - Predefined automation templates
  - Script execution capabilities
  - State change triggers
  - Conditional logic support
  - Error handling in automations

### Data Filtering & Processing
- [ ] **Advanced Data Processing**
  - Time-based filtering (moving averages)
  - Data validation and error handling
  - Invalid value detection (0x7FFFFFFF)
  - Data smoothing algorithms
  - Quality indicators

### State Management
- [ ] **Enhanced State Handling**
  - Complex state calculations
  - State mapping and translation
  - Availability logic
  - State persistence
  - State synchronization

## 🎯 Priority Levels

### High Priority (Core Functionality)
- [ ] Float conversion support
- [ ] String processing improvements
- [ ] Entity category support
- [ ] Status aggregation
- [ ] Template sensors for calculations
- [ ] Advanced binary sensors

### Medium Priority (User Experience)
- [ ] Custom icons
- [ ] Advanced control entities
- [ ] Aggregation scheduling
- [ ] Template validation
- [ ] Input entity integration
- [ ] Data filtering

### Low Priority (Nice to Have)
- [ ] AI optimization suggestions
- [ ] Template inheritance
- [ ] Dynamic templates
- [ ] Advanced metrics
- [ ] Automation templates
- [ ] Script execution

## 🤝 Contributing

If you'd like to contribute to implementing any of these features:

1. **Check the priority level** - Focus on high-priority items first
2. **Create an issue** - Discuss the implementation approach
3. **Plan the implementation** - Consider impact on existing code
4. **Implement with tests** - Ensure proper test coverage
5. **Update documentation** - Keep README and other docs current

### Contributing to MKaiser Features
The MKaiser integration provides excellent examples of advanced Home Assistant features. When implementing these:

1. **Analyze the approach** - Understand why they use templates vs. native features
2. **Consider alternatives** - Can we implement this natively in our integration?
3. **Maintain compatibility** - Ensure our implementation works with existing setups
4. **Document decisions** - Explain why we chose our approach over MKaiser's

## 📋 Implementation Notes

- **Backward Compatibility**: All new features must maintain backward compatibility
- **Performance**: New features should not significantly impact performance
- **Testing**: All features require comprehensive testing
- **Documentation**: Features must be documented before merging
- **MKaiser Compatibility**: Consider how our features complement or replace MKaiser approaches

---

## 🔧 Missing Modbus Parameters (Home Assistant Standard)

Based on the [Home Assistant Modbus Integration](https://www.home-assistant.io/integrations/modbus/) documentation, the following parameters are missing from our template-based implementation:

### 📊 **Sensor & Entity Parameters**
- [ ] **`input_type`**: Specify register type (`input`, `holding`, `coil`, `discrete`)
- [ ] **`count`**: Number of registers to read (for multi-register values)
- [ ] **`slave_count`**: Alternative to `count` for 32/64-bit values
- [ ] **`virtual_count`**: Virtual register count for complex data types
- [ ] **`structure`**: Custom data structure for complex data types
- [ ] **`scan_interval`**: Custom update interval per entity (overrides global)
- [ ] **`verify`**: Verification after write operations
- [ ] **`command_on` / `command_off`**: Commands for switch entities
- [ ] **`state_on` / `state_off`**: State values for binary sensors

### 🔄 **Data Processing Parameters**
- [ ] **`swap: byte`**: Byte swapping for 16-bit values
- [ ] **`swap: word`**: Word swapping for 32/64-bit values  
- [ ] **`swap: word_byte`**: Combined word and byte swapping
- [ ] **`precision`**: Decimal precision for float values
- [ ] **`write_type`**: Specify write method (`coil`, `register`)

### 🎛️ **Control & Validation Parameters**
- [ ] **`verify`**: Verification configuration for write operations
- [ ] **`input_type`**: Input register type for verification
- [ ] **`state_on` / `state_off`**: Expected states after operations
- [ ] **`command_on` / `command_off`**: Commands for control operations

### 📈 **Advanced Parameters**
- [ ] **`message_wait_milliseconds`**: Delay between Modbus requests
- [ ] **`delay`**: Connection delay for device preparation
- [ ] **`timeout`**: Per-entity timeout settings
- [ ] **`retry_on_empty`**: Retry logic for empty responses
- [ ] **`retries`**: Number of retry attempts
- [ ] **`retry_delay`**: Delay between retries

### 🧩 **Template Structure Updates**
- [ ] **`registers` section**: Rename from `sensors` to match HA standard
- [ ] **`calculated` section**: Add support for complex Jinja2 expressions
- [ ] **`controls` section**: Add verification and command parameters
- [ ] **`binary_sensors` section**: Add dedicated binary sensor support
- [ ] **`climates` section**: Add climate entity support
- [ ] **`covers` section**: Add cover entity support
- [ ] **`fans` section**: Add fan entity support
- [ ] **`lights` section**: Add light entity support

### 🔗 **Home Assistant Modbus Actions**
- [ ] **`modbus.write_register`**: Generic register write action
- [ ] **`modbus.write_coil`**: Generic coil write action
- [ ] **`modbus.set_temperature`**: Temperature setting action
- [ ] **`modbus.set_hvac_mode`**: HVAC mode setting action

### 📋 **Implementation Strategy & Phases**

#### **Phase 1: Parameter Extension (Low Risk)**
- [ ] **`input_type`**: Add register type support (`input`, `holding`, `coil`, `discrete`)
- [ ] **`count`**: Add multi-register support for 32/64-bit values
- [ ] **`swap` options**: Add byte/word swapping support
- [ ] **`scan_interval`**: Add per-entity update intervals
- [ ] **`precision`**: Add decimal precision for float values

#### **Phase 2: Enhanced Parameters (Medium Risk)**
- [ ] **`verify`**: Add verification for write operations
- [ ] **`command_on/off`**: Add switch control commands
- [ ] **`state_on/off`**: Add binary sensor state values
- [ ] **`write_type`**: Specify write method (`coil`, `register`)
- [ ] **`retry_on_empty`**: Add retry logic for empty responses

#### **Phase 3: Advanced Parameters (Low Risk)**
- [ ] **`message_wait_milliseconds`**: Add delay between Modbus requests
- [ ] **`delay`**: Add connection delay for device preparation
- [ ] **`timeout`**: Add per-entity timeout settings
- [ ] **`retries`**: Add number of retry attempts
- [ ] **`retry_delay`**: Add delay between retries

### 🔧 **Implementation Approach**

#### **Backward Compatibility Strategy**
- **Keep Existing Structure**: No new sections, only parameter extensions
- **Optional Parameters**: All new parameters are optional
- **Default Values**: Sensible defaults for missing parameters
- **No Migration Needed**: Existing templates work unchanged

#### **Template Evolution Example**
```yaml
# Phase 1: Extended parameters (existing templates work unchanged)
sensors:  # ← Existing structure remains
  - name: "Temperature"
    address: 100
    scale: 0.1
    input_type: "holding"        # ← New optional parameter
    count: 1                     # ← New optional parameter

# Phase 2: Enhanced parameters (optional)
sensors:  # ← Same structure, more options
  - name: "Temperature"
    address: 100
    scale: 0.1
    input_type: "holding"
    count: 1
    verify:                       # ← New verification parameter
      input_type: "input"
      address: 101
    command_on: 1                # ← New control parameter
    command_off: 0               # ← New control parameter
```

#### **Risk Mitigation**
- **Parameter Validation**: Strict validation of new parameters
- **Graceful Degradation**: Fallback to defaults on invalid parameters
- **Comprehensive Testing**: Test each phase before proceeding
- **User Documentation**: Clear examples for new parameters
- **No Breaking Changes**: Existing templates work without modification

---

## 🧠 Decision Basis & Architecture Overview

### ✅ Decision Basis

- **Template-driven architecture**: Devices are described via YAML templates (`registers`, `calculated`, `controls`)
- **Direct Modbus control**: UI entities like `number`, `select`, `button` replace `input_*` + `automation`
- **Calculated sensors via Jinja2**: Template sensors with `{prefix}` placeholder enable multi-device support
- **Versioning in template**: `version:` field detects changes and enables semi-automatic updates
- **No YAML configuration needed**: All devices are set up via UI (`config_flow`)
- **Modular structure**: Each component is independently extensible (sensors, control, aggregation)
- **Statistics data preserved**: Existing entities are not deleted, only supplemented

---

## 🔗 Relevant Links

- 🔧 Project Repo: [github.com/TCzerny/ha-modbus-manager](https://github.com/TCzerny/ha-modbus-manager)
- 📚 Home Assistant Dev Docs: [developers.home-assistant.io](https://developers.home-assistant.io/)
- 🧪 Jinja2 Template Editor: [HA Developer Tools → Templates](http://homeassistant.local:8123/developer-tools/template)
- 🧠 MKaiser Comparison: [github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant)

---

## 🧩 Architecture Steps

### 🔧 Parsing & Structure
- `template_loader.py`: Loads `registers`, `calculated`, `controls`
- Placeholder `{prefix}` in template → dynamically replaced
- Support for `data_type`, `length`, `bitmask`

### 🧠 Entities
- `ModbusRegisterSensor`: Register with scaling & data type
- `CalculatedSensor`: Calculated sensors via Jinja2
- `ModbusNumberEntity`, `ModbusSelectEntity`, `ModbusButtonEntity`: direct control

### 🚀 Setup & Update
- `async_setup_entry()` checks `template_version`
- Adds new entities → no deletion
- Statistics data preserved

### 📁 Templates
- Example: `heatpump_generic.yaml`
- Further planned: `wallbox_generic.yaml`, `hvac_generic.yaml`

---

## 📋 Implementation Notes

- Templates should use `{prefix}` to access their own sensors
- Template version is saved in `config_entry`
- Entity Registry is checked → no duplicates
- UI hint possible on version jump ("Template updated")
- Aggregation possible via `group:` field (e.g. `pv_power`, `heat_energy`)

---

## 📦 Next Steps

- [ ] Create branch `feature/template_refactor`  
- [ ] Integrate all new files (`template_loader.py`, `controls.py`, `calculated.py`, etc.)  
- [ ] Extend README with template schema  
- [ ] Add UI function "Update template"  
- [ ] Write additional templates

---

**Last Updated**: August 2025
**Version**: 2.0.0


