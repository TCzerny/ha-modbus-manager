## Sungrow iHomeManager Template

> **General documentation (Wiki):** [User Guide](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide) · [Template reference](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference) · [Capabilities and limits](https://github.com/TCzerny/ha-modbus-manager/wiki/Capabilities-and-Limits) · [Local customization](https://github.com/TCzerny/ha-modbus-manager/wiki/Local-Customization)

This document lists the Modbus registers for the standalone iHomeManager EMS
template: `sungrow_ihomemanager.yaml`.

### Template Overview

- **Name**: Sungrow iHomeManager
- **Type**: `energy_manager`
- **Default prefix**: `IHM`
- **Default slave ID**: `247`
- **Firmware**: `iHomeManager`
- **Template version**: 1.0.7

### Dynamic Configuration

- `battery_enabled` (true/false): Enables battery-related registers.
- `channel_2_enabled` (true/false): Enables PROD.CT channel 2 registers.
- `charger_enabled` (true/false): Enables charger-related registers.
- `charger_region` (`EU` / `AU`): EV charger mode map (EU modes 160–163, AU modes 164–167). Default: `EU`.

Config-flow labels are translated in `en.json` / `de.json` under `config.step.dynamic_config.data`.

### Combined Device with a Sungrow inverter

From **integration 1.0.11**, you can add a **[Cross-hub Combined Device](README_Combined_Device.md)** that links an inverter hub and an iHomeManager hub. It provides:

- iHM grid sensors (`grid_import_energy`, `grid_export_energy`, import/export power) at the **GRID.CT**
- **`combined_daily_consumed_energy`** / **`combined_total_consumed_energy`** using WR PV/battery and iHM grid data (see [#50](https://github.com/TCzerny/ha-modbus-manager/issues/50))

Single-template **`daily_consumed_energy`** on the inverter alone does **not** include iHM grid data.

### Sensor Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Device Type Code | device_type_code | 7999 | input | uint16 |  |  |  |
| Protocol Number | protocol_number | 8000 | input | string |  |  |  |
| Protocol Version Raw | protocol_version_raw | 8002 | input | uint32 |  |  |  |
| Total Devices Connected | total_devices_connected | 8004 | input | uint16 |  |  |  |
| Devices in Fault | devices_in_fault | 8005 | input | uint16 |  |  |  |
| Total Nominal Active Power | total_nominal_active_power | 8144 | input | uint32 | kW | 0.1 |  |
| Total Battery Rated Capacity | total_battery_rated_capacity | 8146 | input | uint32 | kWh | 0.1 | battery_enabled == true |
| Battery Charge/Discharge Limit | battery_charge_discharge_limit | 8148 | input | uint32 | kW | 0.1 | battery_enabled == true |
| Battery Max Charge Power | battery_max_charge_power | 8150 | input | uint16 | kW | 0.1 | battery_enabled == true |
| Battery Min Charge Power | battery_min_charge_power | 8151 | input | uint16 | kW | 0.1 | battery_enabled == true |
| Battery Max Discharge Power | battery_max_discharge_power | 8152 | input | uint16 | kW | 0.1 | battery_enabled == true |
| Battery Min Discharge Power | battery_min_discharge_power | 8153 | input | uint16 | kW | 0.1 | battery_enabled == true |
| Total Active Power | total_active_power | 8154 | input | int32 | W | 10 |  |
| Meter Active Power Raw | meter_active_power_raw | 8156 | input | int32 | W | 10 |  |
| Load Power | load_power | 8158 | input | int32 | W | 10 |  |
| Battery Power | battery_power | 8160 | input | int32 | W | 10 | battery_enabled == true |
| Battery Level SOC | battery_level | 8162 | input | uint16 | % | 0.1 | battery_enabled == true |
| Grid Import Energy | grid_import_energy | 8175 | input | uint32 | kWh | 0.1 |  |
| Grid Export Energy | grid_export_energy | 8177 | input | uint32 | kWh | 0.1 |  |
| Application Software Version | application_software_version | 8317 | input | string |  |  |  |
| Charger Status Raw | charger_status_raw | 8551 | input | uint16 |  |  | charger_enabled == true |
| Output Type Raw | output_type_raw | 8553 | input | uint16 | V | 0.1 |  |
| Phase A Voltage | phase_a_voltage | 8554 | input | uint16 | V | 0.1 |  |
| Phase B Voltage | phase_b_voltage | 8555 | input | uint16 | V | 0.1 |  |
| Phase C Voltage | phase_c_voltage | 8556 | input | uint16 | V | 0.1 |  |
| Grid Frequency | grid_frequency | 8557 | input | uint16 | Hz | 0.1 |  |
| Meter Phase A Active Power Raw | meter_phase_a_active_power_raw | 8558 | input | int32 | W | 1 |  |
| Meter Phase B Active Power Raw | meter_phase_b_active_power_raw | 8560 | input | int32 | W | 1 |  |
| Meter Phase C Active Power Raw | meter_phase_c_active_power_raw | 8562 | input | int32 | W | 1 |  |
| Phase A Voltage Ch2 | phase_a_voltage_ch2 | 8564 | input | uint16 | V | 0.1 | channel_2_enabled == true |
| Phase B Voltage Ch2 | phase_b_voltage_ch2 | 8565 | input | uint16 | V | 0.1 | channel_2_enabled == true |
| Phase C Voltage Ch2 | phase_c_voltage_ch2 | 8566 | input | uint16 | V | 0.1 | channel_2_enabled == true |
| Grid Frequency Ch2 | grid_frequency_ch2 | 8567 | input | uint16 | Hz | 0.1 | channel_2_enabled == true |
| Phase A Active Power Ch2 | phase_a_active_power_ch2 | 8568 | input | int32 | W |  | channel_2_enabled == true |
| Phase B Active Power Ch2 | phase_b_active_power_ch2 | 8570 | input | int32 | W |  | channel_2_enabled == true |
| Phase C Active Power Ch2 | phase_c_active_power_ch2 | 8572 | input | int32 | W |  | channel_2_enabled == true |

### Control Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| EMS Mode Selection | ems_mode_selection | 8023 | holding | uint16 |  |  |  |
| Charging/Discharging Command | charging_discharging_command | 8024 | holding | uint16 |  |  | battery_enabled == true |
| Charging/Discharging Power | charging_discharging_power | 8025 | holding | uint32 | kW | 0.1 | battery_enabled == true |
| Feed-in Power Limitation | feed_in_power_limitation | 8027 | holding | uint16 |  |  |  |
| Feed-in Power Limit Value | feed_in_power_limit_value | 8028 | holding | uint32 | kW | 0.1 |  |
| Feed-in Power Limit Ratio | feed_in_power_limit_ratio | 8030 | holding | int16 | % | 0.1 |  |
| Power-on/off | power_on_off | 8046 | holding | uint16 |  |  |  |
| Charger Charging Modes (EU) | charger_charging_modes | 8047 | holding | uint16 |  |  | charger_enabled == true and charger_region == 'EU' |
| Charger Charging Modes (AU) | charger_charging_modes_au | 8047 | holding | uint16 |  |  | charger_enabled == true and charger_region == 'AU' |
| Charger Enable | charger_enable | 8048 | holding | uint16 |  |  | charger_enabled == true |
| Charger Grid Power Draw | charger_grid_power_draw | 8049 | holding | uint16 |  |  | charger_enabled == true |
| Active Power Limitation | active_power_limitation | 8050 | holding | uint16 |  |  |  |
| Active Power Limit Ratio | active_power_limit_ratio | 8051 | holding | uint16 | % | 0.1 |  |

EMS mode values: `0` AI Mode, `1` Self-consumption, `2` Time plan, `4` VPP, `5` Compulsory mode.

Charger mode values: EU `160`–`163`, AU `164`–`167` (same register 8047).

Register **8032** (External VPP Heartbeat) is documented in the protocol but **not** exposed in the template yet.

### Calculated Sensors

| Name | Unique ID | Condition |
|---|---|---|
| Protocol Version | protocol_version |  |
| Net Grid Power | net_grid_power |  |
| Import Power | import_power |  |
| Export Power | export_power |  |
| Total Phase Power | total_phase_power |  |
| Phase A Power | phase_a_power |  |
| Phase B Power | phase_b_power |  |
| Phase C Power | phase_c_power |  |
| Total Phase Power Ch2 | total_phase_power_ch2 | channel_2_enabled == true |

Grid import/export power is derived from `meter_active_power_raw` (positive = import, negative = export).

### Notes

- Addresses are the base register offsets used by the integration (Modbus address = register number − 1).
- Conditions reflect template logic and are evaluated from dynamic config.
- **Feed-in** controls (8027–8030) limit export to the grid.
- **Active power** controls (8050–8051) limit inverter AC output — not the same as feed-in limitation.
