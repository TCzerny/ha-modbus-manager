## Fronius GEN24 Dynamic Template

This document describes the Modbus registers for the Fronius GEN24 dynamic template: `fronius_dynamic.yaml`.

### Template Overview

- **Name**: Fronius GEN24 Series Inverter
- **Type**: `PV_Hybrid_Inverter`
- **Default prefix**: `Fronius`
- **Default slave ID**: `1`
- **Firmware**: `1.19.7-1`
- **Protocol**: Fronius Modbus RTU/TCP - Uses Holding Registers
- **SunSpec Support**: Yes (Models 103, 160, 124)

### ⚠️ BETA STATUS

**This template is in BETA status - use at your own risk.**

The template has been created based on community documentation and may need verification with actual devices.

### Dynamic Configuration

- `valid_models`: Model list based on power rating and battery support
  - `GEN24-6.0`: 6kW, single phase, no battery
  - `GEN24-8.0`: 8kW, single phase, no battery
  - `GEN24-10.0`: 10kW, single phase, no battery
  - `GEN24-12.0`: 12kW, single phase, no battery
  - `GEN24-6.0-Plus`: 6kW, single phase, with battery
  - `GEN24-8.0-Plus`: 8kW, single phase, with battery
  - `GEN24-10.0-Plus`: 10kW, single phase, with battery
  - `GEN24-12.0-Plus`: 12kW, single phase, with battery
  - `GEN24-10.0-3P`: 10kW, three phase, no battery
  - `GEN24-10.0-3P-Plus`: 10kW, three phase, with battery
- `phases`: Options [1, 3] (default: 1)
- `mppt_count`: Options [1, 2] (default: 1)
- `battery_config`: Options ["none", "fronius_battery"] (default: "none")
- `firmware_version`: Options ["1.19.7-1", "Latest"] (default: "1.19.7-1")

### SunSpec Protocol Support

This template supports SunSpec protocol for dynamic register address detection:

- **Model 103** (Single Phase Inverter): Start address 40070 (auto-detected or user-configurable)
- **Model 160** (Multiple MPPT Extension): Start address 40253 (auto-detected or user-configurable)
- **Model 124** (Battery Storage Control): Start address 40000 (auto-detected or user-configurable)

SunSpec model addresses can be:
1. Automatically detected by reading Model ID registers
2. Manually configured in the config flow
3. Fallback to template defaults if detection fails

### Key Features

- **Summary Measurements** (register 258-273): Grid voltage, current, power, frequency
- **Per-Phase Measurements** (register 286-327): All 3 phases (voltage, current, power, power factor)
- **Energy Measurements** (register 1024-1039): Consumed/Produced energy (kWh + Wh format)
- **PV Data** (SunSpec Model 103): DC voltage, current, power for single DC input
- **PV Data** (SunSpec Model 160): MPPT 1 & 2 voltage, current, power for multiple DC inputs
- **Battery Data** (SunSpec Model 124): Voltage, current, power, SOC for GEN24 Plus models

### Register Notes

- Fronius uses **Holding Registers** (not Input Registers) for both read and write
- All values are **32-bit signed integers** (2 registers combined)
- Low word stored at lower address
- Energy values stored in 4 registers (kWh + Wh)
- SunSpec registers use dynamic address calculation based on model start addresses

### Sensor Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Grid Voltage L1 | grid_voltage_l1 | 258 | holding | int32 | V | 0.1 | |
| Grid Voltage L2 | grid_voltage_l2 | 260 | holding | int32 | V | 0.1 | phases >= 2 |
| Grid Voltage L3 | grid_voltage_l3 | 262 | holding | int32 | V | 0.1 | phases >= 3 |
| Grid Current L1 | grid_current_l1 | 264 | holding | int32 | A | 0.01 | |
| Grid Current L2 | grid_current_l2 | 266 | holding | int32 | A | 0.01 | phases >= 2 |
| Grid Current L3 | grid_current_l3 | 268 | holding | int32 | A | 0.01 | phases >= 3 |
| Grid Power L1 | grid_power_l1 | 270 | holding | int32 | W | 1 | |
| Grid Power L2 | grid_power_l2 | 272 | holding | int32 | W | 1 | phases >= 2 |
| Grid Power L3 | grid_power_l3 | 274 | holding | int32 | W | 1 | phases >= 3 |
| Grid Frequency | grid_frequency | 276 | holding | int32 | Hz | 0.01 | |
| Energy Consumed Total | energy_consumed_total | 1024 | holding | int32 | kWh | 1 | |
| Energy Produced Total | energy_produced_total | 1028 | holding | int32 | kWh | 1 | |
| PV DC Voltage | pv_dc_voltage | SunSpec 103+25 | holding | uint16 | V | 1 | mppt_count == 1 |
| PV DC Current | pv_dc_current | SunSpec 103+26 | holding | int16 | A | 0.1 | mppt_count == 1 |
| PV DC Power | pv_dc_power | SunSpec 103+27 | holding | int32 | W | 1 | mppt_count == 1 |
| PV MPPT1 Voltage | pv_mppt1_voltage | SunSpec 160+0 | holding | uint16 | V | 1 | mppt_count >= 2 |
| PV MPPT1 Current | pv_mppt1_current | SunSpec 160+1 | holding | int16 | A | 0.1 | mppt_count >= 2 |
| PV MPPT1 Power | pv_mppt1_power | SunSpec 160+2 | holding | int32 | W | 1 | mppt_count >= 2 |
| PV MPPT2 Voltage | pv_mppt2_voltage | SunSpec 160+5 | holding | uint16 | V | 1 | mppt_count >= 2 |
| PV MPPT2 Current | pv_mppt2_current | SunSpec 160+6 | holding | int16 | A | 0.1 | mppt_count >= 2 |
| PV MPPT2 Power | pv_mppt2_power | SunSpec 160+7 | holding | int32 | W | 1 | mppt_count >= 2 |
| Battery Voltage | battery_voltage | SunSpec 124+0 | holding | uint16 | V | 0.1 | battery_enabled == true |
| Battery Current | battery_current | SunSpec 124+1 | holding | int16 | A | 0.1 | battery_enabled == true |
| Battery Power | battery_power | SunSpec 124+2 | holding | int32 | W | 1 | battery_enabled == true |
| Battery SOC | battery_soc | SunSpec 124+4 | holding | uint16 | % | 0.1 | battery_enabled == true |

### Calculated Sensors

- **PV Power Total**: Sum of all PV power inputs
- **Grid Power Total**: Sum of all phase powers (for three-phase models)

### Binary Sensors

- **PV Generating**: True when PV power > 0
- **Grid Importing**: True when grid power < 0
- **Grid Exporting**: True when grid power > 0

### References

- Repository: https://github.com/otti/FroniusModbusRtu
- Official Documentation: https://manuals.fronius.com/html/4204102649/en-US.html
- Tested with: Fronius Symo GEN24 10.0 Plus (SW: 1.19.7-1)
