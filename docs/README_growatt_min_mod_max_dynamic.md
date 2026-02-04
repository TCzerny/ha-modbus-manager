## Growatt MIN/MOD/MAX Dynamic Template

This document describes the Modbus registers for the Growatt MIN/MOD/MAX dynamic template: `growatt_min_mod_max_dynamic.yaml`.

### Template Overview

- **Name**: Growatt MIN/MOD/MAX Series Inverter
- **Type**: `PV_Hybrid_Inverter`
- **Default prefix**: `Growatt`
- **Default slave ID**: `1`
- **Firmware**: `1.0.0`
- **Protocol**: Growatt Modbus RTU Protocol V1.05 (2018-04-19) / V1.13 (2019-01-16 for MAX)

### ⚠️ BETA STATUS

**This template is in BETA status - use at your own risk.**

The template has been created based on community documentation and may need verification with actual devices. MAX series support is preliminary and may need verification/adjustment.

### Dynamic Configuration

- `valid_models`: Model list based on series and power rating
  - **MIN Series** (Single Phase Hybrid, 2.5-6kW):
    - `MIN-2500TL-X`, `MIN-2500TL-XE`, `MIN-3000TL-X`, `MIN-5000TL-X`, `MIN-5000TL-XH`, `MIN-6000TL-X`, `MIN-6000TL-XH`
    - 2 MPPTs, battery support enabled
  - **MOD Series** (Three Phase Hybrid, 3-10kW):
    - `MOD-3000TL3-X`, `MOD-3000TL3-XH`, `MOD-4000TL3-X`, `MOD-4000TL3-XH`, `MOD-5000TL3-X`, `MOD-5000TL3-XH`, `MOD-6000TL-X`, `MOD-6000TL3-X`, `MOD-6000TL3-XH`, `MOD-7000TL3-X`, `MOD-7000TL3-XH`, `MOD-8000TL3-X`, `MOD-8000TL3-XH`, `MOD-9000TL3-X`, `MOD-9000TL3-XH`, `MOD-10KTL3-XH`
    - 2 MPPTs, battery support enabled
  - **MAX Series** (Three Phase Commercial, 50-253kW) - **PRELIMINARY**:
    - `MAX-50KTL3-LV`, `MAX-50KTL3-MV`, `MAX-60KTL3-LV`, `MAX-60KTL3-MV`, `MAX-80KTL3-LV`, `MAX-80KTL3-MV`, `MAX-100KTL3-LV`, `MAX-100KTL3-X`, `MAX-125KTL3-X`, `MAX-185KTL3-X`, `MAX-200KTL3-X`, `MAX-253KTL3-X`
    - 6-15 MPPTs, battery support enabled
    - **WARNING**: MAX series uses DIFFERENT register addresses (0-52 Input, 0-42 Holding) vs MIN/MOD (3000-3180+)
- `phases`: Options [1, 3] (default: 1)
- `mppt_count`: Options [1, 2, 6, 7, 9, 10, 12, 15] (default: 2)
- `battery_config`: Options ["none", "standard_battery"] (default: "standard_battery")
- `firmware_version`: Options ["1.0.0", "Latest"] (default: "1.0.0")

### Register Address Structure

#### MIN/MOD Series (Primary Support)
- **Input Registers**: 3000-3180+
  - PV data: 3001-3009
  - Grid data: 3023-3040
  - Battery data: 3125-3180
- **Holding Registers**: 0-15, 3036-3049, 3085
  - Controls: On/Off, Power Limits, Battery Settings

#### MAX Series (Preliminary Support)
- **Input Registers**: 0-52
- **Holding Registers**: 0-42
- **WARNING**: MAX series uses completely different register addresses than MIN/MOD series. This template currently supports MIN/MOD register structure. MAX series may need separate template or conditional handling.

### Key Features

- **PV Data**: Voltage, current, power for up to 2 MPPTs (MIN/MOD) or 6-15 MPPTs (MAX)
- **Grid Data**: Voltage, current, power, frequency (single phase for MIN, three phase for MOD/MAX)
- **Battery Data**: Voltage, current, power, SOC, temperature (for hybrid models)
- **Energy Data**: Daily and total PV energy, grid energy
- **Controls**: On/Off, Export limit, Battery charge/discharge limits, SOC settings

### Register Notes

- MIN and MOD series use **identical register addresses** (3000-3180+)
- Same structure for PV, Grid, Battery data across MIN/MOD
- MAX series uses **different register addresses** (0-52 vs 3000-3180+) - documented but not fully implemented
- MAX series support is preliminary and may need verification
- MOD series corrected to three-phase (was incorrectly listed as single-phase in earlier versions)

### Sensor Registers (MIN/MOD Series)

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| PV Voltage 1 | pv_voltage_1 | 3001 | input | uint16 | V | 0.1 | |
| PV Current 1 | pv_current_1 | 3002 | input | uint16 | A | 0.1 | |
| PV Power 1 | pv_power_1 | 3003 | input | uint16 | W | 1 | |
| PV Voltage 2 | pv_voltage_2 | 3004 | input | uint16 | V | 0.1 | mppt_count >= 2 |
| PV Current 2 | pv_current_2 | 3005 | input | uint16 | A | 0.1 | mppt_count >= 2 |
| PV Power 2 | pv_power_2 | 3006 | input | uint16 | W | 1 | mppt_count >= 2 |
| Grid Voltage | grid_voltage | 3023 | input | uint16 | V | 0.1 | |
| Grid Current | grid_current | 3024 | input | int16 | A | 0.1 | |
| Grid Power | grid_power | 3025 | input | int16 | W | 1 | |
| Grid Frequency | grid_frequency | 3026 | input | uint16 | Hz | 0.01 | |
| Battery Voltage | battery_voltage | 3125 | input | uint16 | V | 0.1 | battery_enabled == true |
| Battery Current | battery_current | 3126 | input | int16 | A | 0.1 | battery_enabled == true |
| Battery Power | battery_power | 3127 | input | int16 | W | 1 | battery_enabled == true |
| Battery SOC | battery_soc | 3128 | input | uint16 | % | 0.1 | battery_enabled == true |
| Battery Temperature | battery_temperature | 3129 | input | int16 | °C | 0.1 | battery_enabled == true |
| PV Energy Today | pv_energy_today | 3013 | input | uint32 | kWh | 0.1 | |
| PV Energy Total | pv_energy_total | 3015 | input | uint32 | kWh | 0.1 | |

### Controls (Holding Registers - MIN/MOD Series)

| Name | Unique ID | Address | Input | Data | Unit | Min | Max | Step | Condition |
|---|---|---|---|---|---|---|---|---|---|
| Inverter On/Off | inverter_on_off | 0 | holding | uint16 |  | 0 | 1 | 1 | |
| Export Power Limit | export_power_limit | 3036 | holding | uint16 | W | 0 | 10000 | 100 | |
| Battery Charge Power Limit | battery_charge_power_limit | 3037 | holding | uint16 | W | 0 | 5000 | 100 | battery_enabled == true |
| Battery Discharge Power Limit | battery_discharge_power_limit | 3038 | holding | uint16 | W | 0 | 5000 | 100 | battery_enabled == true |
| Battery SOC Min | battery_soc_min | 3039 | holding | uint16 | % | 0 | 100 | 1 | battery_enabled == true |

### MAX Series Notes

The MAX series (50-253kW commercial inverters) uses a different register map:

- **Input Registers**: 0-52 (vs 3000-3180+ for MIN/MOD)
- **Holding Registers**: 0-42 (vs 0-15, 3036-3049, 3085 for MIN/MOD)
- **Protocol**: MAX Series Modbus RTU Protocol V1.13 (2019-01-16)
- **Support Status**: Preliminary - register addresses documented but not fully verified

**Recommendation**: MAX series may need a separate template or conditional register address handling based on selected model.

### Calculated Sensors

- **PV Power Total**: Sum of PV Power 1 and PV Power 2
- **Battery Power**: Battery power (for hybrid models)
- **Grid Power**: Grid power (positive = export, negative = import)

### Binary Sensors

- **PV Generating**: True when PV power > 0
- **Battery Charging**: True when battery power > 0 (for hybrid models)
- **Battery Discharging**: True when battery power < 0 (for hybrid models)
- **Grid Importing**: True when grid power < 0
- **Grid Exporting**: True when grid power > 0

### References

- Repository: https://github.com/timlaing/modbus_local_gateway/tree/main/custom_components/modbus_local_gateway/device_configs
- Source Files Analyzed: MIN-6000TL-XH.yaml, MOD-6000TL-X.yaml, MOD-10KTL3-XH.yaml
- Official MAX Protocol: MAX Series Modbus RTU Protocol V1.13 (2019-01-16)
- Protocol Versions:
  - MIN/MOD: Growatt Modbus RTU Protocol V1.05 (2018-04-19)
  - MAX: MAX Series Modbus RTU Protocol V1.13 (2019-01-16)
