# TODO: Planned Features for Modbus Manager

This document tracks planned features that are described in the README but not yet implemented in the code.

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

**Last Updated**: $(date)
**Version**: 1.1.0 



# 🧠 Modbus Manager Refactor – Architektur & Feature-Zusammenfassung

## 👤 Entwickler: TCzerny  
## 📦 Projekt: [ha-modbus-manager](https://github.com/TCzerny/ha-modbus-manager)  
## 📅 Stand: August 2025  

---

## 🧱 Architekturüberblick

Ziel: Eine modulare, template-gesteuerte Plattform zur Verwaltung von Modbus-Geräten in Home Assistant – skalierbar für PV-Wechselrichter, Wärmepumpen, Wallboxen, Klimageräte, Heizungen u.v.m.

### 🔧 Komponenten
- `template_loader.py`: Parser für `registers`, `calculated`, `controls`
- `entity_factory.py`: Erzeugt Entitäten aus Template-Daten
- `controls.py`: Direkte Modbus-Steuerung (`number`, `select`, `button`)
- `calculated.py`: Berechnete Sensoren via Jinja2
- `async_setup_entry()`: Setup + Versionsvergleich + Ergänzung neuer Entitäten

---

## ✅ ToDo-Liste

### 🔧 Parsing & Struktur
- [x] Modularer Template-Parser (`template_loader.py`)
- [x] Präfix-Platzhalter `{prefix}` in `calculated.template`
- [x] Unterstützung für `data_type`, `length`, `bitmask`
- [ ] Template-Versionierung (`version:`) + Vergleich

### 🧠 Entitäten
- [x] `ModbusRegisterSensor`
- [x] `CalculatedSensor`
- [x] `ModbusNumberEntity`, `ModbusSelectEntity`, `ModbusButtonEntity`

### 🚀 Setup & Update
- [x] Entity Registry prüfen → keine Duplikate
- [x] Ergänzung neuer Entitäten bei Versionssprung
- [ ] Speichern von `template_version` im `config_entry`

### 📁 Templates
- [x] `heatpump_generic.yaml`
- [ ] `wallbox_generic.yaml`
- [ ] `hvac_generic.yaml`

### 🧠 UI & Optionen
- [ ] Anzeige von Template-Version in `config_flow.py`
- [ ] UI-Option „Template aktualisieren“

---

## 📁 Beispiel-Template: `heatpump_generic.yaml`

```yaml
name: Generic Heatpump
type: heatpump
version: 2
slave_id: 1

registers:
  - name: "Flow Temperature"
    address: 30010
    unit: "°C"
    scale: 0.1
    device_class: temperature
    state_class: measurement
    group: heat_flow

  - name: "Return Temperature"
    address: 30012
    unit: "°C"
    scale: 0.1
    device_class: temperature
    state_class: measurement
    group: heat_return

  - name: "Compressor Status"
    address: 30020
    data_type: bitfield
    bitmask: 0x01
    device_class: running
    group: heat_status

  - name: "Total Heat Energy"
    address: 30030
    length: 2
    data_type: uint32
    unit: "kWh"
    scale: 0.01
    device_class: energy
    state_class: total
    group: heat_energy

calculated:
  - name: "Delta Temperature"
    type: sensor
    template: "{{ states('sensor.{prefix}_flow_temperature') | float - states('sensor.{prefix}_return_temperature') | float }}"
    unit: "°C"
    device_class: temperature
    state_class: measurement
    group: heat_delta

controls:
  - type: number
    name: "Target Temperature"
    address: 40010
    scale: 0.1
    unit: "°C"
    min: 30
    max: 60
    step: 0.5
    group: heat_control

  - type: select
    name: "Operation Mode"
    address: 40020
    options:
      Auto: 1
      Eco: 2
      Boost: 3
    group: heat_control

  - type: button
    name: "Restart Heatpump"
    address: 40030
    value: 1
    group: heat_control

# 🧠 Entscheidungsgrundlagen & Architekturübersicht – Modbus Manager

## ✅ Entscheidungsgrundlagen

- **Template-gesteuerte Architektur**: Geräte werden über YAML-Templates beschrieben (`registers`, `calculated`, `controls`)
- **Direkte Modbus-Steuerung**: UI-Entitäten wie `number`, `select`, `button` ersetzen `input_*` + `automation`
- **Berechnete Sensoren via Jinja2**: Template-Sensoren mit `{prefix}`-Platzhalter ermöglichen Mehrgeräte-Support
- **Versionierung im Template**: `version:`-Feld erkennt Änderungen und ermöglicht halbautomatische Updates
- **Keine YAML-Konfiguration nötig**: Alle Geräte werden über UI (`config_flow`) eingerichtet
- **Modularer Aufbau**: Jede Komponente ist unabhängig erweiterbar (Sensoren, Steuerung, Aggregation)
- **Statistikdaten bleiben erhalten**: Bestehende Entitäten werden nicht gelöscht, sondern nur ergänzt

---

## 🔗 Relevante Links

- 🔧 Projekt-Repo: [github.com/TCzerny/ha-modbus-manager](https://github.com/TCzerny/ha-modbus-manager)
- 📚 Home Assistant Dev Docs: [developers.home-assistant.io](https://developers.home-assistant.io/)
- 🧪 Jinja2 Template-Editor: [HA Entwicklerwerkzeuge → Vorlagen](http://homeassistant.local:8123/developer-tools/template)
- 🧠 MKaiser Vergleich: [github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant)

---

## 🧩 Architektur-Schritte

### 🔧 Parsing & Struktur
- `template_loader.py`: Lädt `registers`, `calculated`, `controls`
- Platzhalter `{prefix}` im Template → dynamisch ersetzt
- Unterstützung für `data_type`, `length`, `bitmask`

### 🧠 Entitäten
- `ModbusRegisterSensor`: Register mit Skalierung & Datentyp
- `CalculatedSensor`: Berechnete Sensoren via Jinja2
- `ModbusNumberEntity`, `ModbusSelectEntity`, `ModbusButtonEntity`: direkte Steuerung

### 🚀 Setup & Update
- `async_setup_entry()` prüft `template_version`
- Ergänzt neue Entitäten → keine Löschung
- Statistikdaten bleiben erhalten

### 📁 Templates
- Beispiel: `heatpump_generic.yaml`
- Weitere geplant: `wallbox_generic.yaml`, `hvac_generic.yaml`

---

## 📋 Hinweise zur Umsetzung

- Templates sollten `{prefix}` verwenden, um auf eigene Sensoren zuzugreifen
- Template-Version wird im `config_entry` gespeichert
- Entity Registry wird geprüft → keine Duplikate
- UI-Hinweis bei Versionssprung möglich („Template aktualisiert“)
- Aggregation über `group:`-Feld möglich (z. B. `pv_power`, `heat_energy`)

---

## 📦 Nächste Schritte

- [ ] Branch `feature/template_refactor` erstellen  
- [ ] Alle neuen Dateien integrieren (`template_loader.py`, `controls.py`, `calculated.py`, etc.)  
- [ ] README erweitern mit Template-Schema  
- [ ] UI-Funktion „Template aktualisieren“ ergänzen  
- [ ] Weitere Templates schreiben


