## SolaX Dynamic Template

This document describes the Modbus registers for the SolaX dynamic template: `solax_dynamic.yaml`.

### Template Overview

- **Name**: SolaX Inverter Series
- **Type**: `PV_Hybrid_Inverter`
- **Default prefix**: `SolaX`
- **Default slave ID**: `1`
- **Firmware**: `1.0.0`
- **Protocol**: SolaX Modbus RTU/TCP

### ⚠️ BETA STATUS

**This template is in BETA status - use at your own risk.**

The template has been created based on community documentation and may need verification with actual devices. Register addresses may vary by generation (GEN2-GEN6).

### Dynamic Configuration

- `valid_models`: Model list based on generation, phase, and battery support
  - GEN2 Series: X1 Single Phase (3.0-5.0kW, AC/HYBRID)
  - GEN3 Series: X1 Single Phase (3.0-5.0kW, AC/HYBRID)
  - GEN4 Series: X1/X3 Single/Three Phase (3.0-10.0kW, AC/HYBRID)
  - GEN5 Series: X1/X3 Single/Three Phase (3.0-10.0kW, AC/HYBRID)
  - GEN6 Series: X1/X3 Single/Three Phase (3.0-10.0kW, AC/HYBRID)
- `phases`: Options [1, 3] (default: 1)
- `mppt_count`: Options [1, 2, 3, 4, 5, 6, 8, 10] (default: 2)
- `battery_config`: Options ["none", "solax_battery"] (default: "none")
- `firmware_version`: Options ["1.0.0", "Latest"] (default: "1.0.0")

### Key Features

- **PV Data**: Voltage, current, power for up to 2 MPPTs
- **Grid Data**: Voltage, current, power, frequency
- **Inverter Data**: Power, temperature
- **Battery Data**: Voltage, current, power, SOC (for HYBRID models)
- **Energy Data**: Daily and total PV energy
- **Controls**: Export limit, battery charge/discharge limits, SOC settings

### Register Notes

- Register addresses are typical for GEN4/GEN5 - may vary by generation
- Supports multiple inverter types: AC, HYBRID, PV, MIC, MAX
- Battery support with per-pack entities (not fully implemented in this template)
- Parallel mode support (PM registers) - not implemented in this template
- EPS (Emergency Power Supply) support - not implemented in this template

### Sensor Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| PV Voltage 1 | pv_voltage_1 | 0 | input | uint16 | V | 0.1 | |
| PV Current 1 | pv_current_1 | 1 | input | uint16 | A | 0.1 | |
| PV Power 1 | pv_power_1 | 2 | input | uint16 | W | 1 | |
| PV Voltage 2 | pv_voltage_2 | 3 | input | uint16 | V | 0.1 | mppt_count >= 2 |
| PV Current 2 | pv_current_2 | 4 | input | uint16 | A | 0.1 | mppt_count >= 2 |
| PV Power 2 | pv_power_2 | 5 | input | uint16 | W | 1 | mppt_count >= 2 |
| Grid Voltage | grid_voltage | 21 | input | uint16 | V | 0.1 | |
| Grid Current | grid_current | 22 | input | int16 | A | 0.1 | |
| Grid Power | grid_power | 23 | input | int16 | W | 1 | |
| Grid Frequency | grid_frequency | 24 | input | uint16 | Hz | 0.01 | |
| Inverter Power | inverter_power | 41 | input | uint16 | W | 1 | |
| Inverter Temperature | inverter_temperature | 42 | input | int16 | °C | 0.1 | |
| Battery Voltage | battery_voltage | 61 | input | uint16 | V | 0.1 | battery_enabled == true |
| Battery Current | battery_current | 62 | input | int16 | A | 0.1 | battery_enabled == true |
| Battery Power | battery_power | 63 | input | int16 | W | 1 | battery_enabled == true |
| Battery SOC | battery_soc | 64 | input | uint16 | % | 0.1 | battery_enabled == true |
| PV Energy Today | pv_energy_today | 81 | input | uint32 | kWh | 0.1 | |
| PV Energy Total | pv_energy_total | 83 | input | uint32 | kWh | 0.1 | |

### Controls (Holding Registers)

| Name | Unique ID | Address | Input | Data | Unit | Min | Max | Step | Condition |
|---|---|---|---|---|---|---|---|---|---|
| Export Power Limit | export_power_limit | 0 | holding | uint16 | W | 0 | 10000 | 100 | |
| Battery Charge Power Limit | battery_charge_power_limit | 1 | holding | uint16 | W | 0 | 5000 | 100 | battery_enabled == true |
| Battery Discharge Power Limit | battery_discharge_power_limit | 2 | holding | uint16 | W | 0 | 5000 | 100 | battery_enabled == true |
| Battery SOC Min | battery_soc_min | 3 | holding | uint16 | % | 0 | 100 | 1 | battery_enabled == true |

### Calculated Sensors

- **PV Power Total**: Sum of PV Power 1 and PV Power 2
- **Battery Power**: Battery power (for HYBRID models)
- **Inverter Power**: Inverter output power

### Binary Sensors

- **PV Generating**: True when PV power > 0
- **Battery Charging**: True when battery power > 0 (for HYBRID models)
- **Battery Discharging**: True when battery power < 0 (for HYBRID models)

### Remaining Work

This template is a basic implementation. Future enhancements may include:

- More sensors from plugin_solax.py (energy meters, temperature, status)
- More controls (remote control modes, time schedules, generator control)
- More calculated sensors (house load, grid import/export)
- More binary sensors (system status, alarms)
- Select entities (charger use mode, lock state, etc.)
- Button entities (sync RTC, system on/off, etc.)
- Multiple MPPT support (MPPT3, MPPT4, MPPT5, MPPT6, MPPT8, MPPT10)
- EPS (Emergency Power Supply) support
- Dry Contact Box (DCB) support
- Generator control support
- PeakShaving mode
- Parallel mode support (PM registers)

### References

- Repository: https://github.com/wills106/homeassistant-solax-modbus
- Documentation: https://homeassistant-solax-modbus.readthedocs.io/
- Plugin file: custom_components/solax_modbus/plugin_solax.py (7000+ lines)
