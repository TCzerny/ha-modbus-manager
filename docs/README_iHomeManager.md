## Sungrow iHomeManager Template

This document lists the Modbus registers for the standalone iHomeManager EMS
template: `sungrow_ihomemanager.yaml`.

### Template Overview

- **Name**: Sungrow iHomeManager
- **Type**: `energy_manager`
- **Default prefix**: `IHM`
- **Default slave ID**: `247`
- **Firmware**: `iHomeManager`

### Dynamic Configuration

- `battery_enabled` (true/false): Enables battery-related registers.
- `channel_2_enabled` (true/false): Enables meter channel 2 registers.

### Sensor Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Meter Active Power Raw | meter_active_power_raw | 8156 | input | int32 | W | 10 |  |
| Meter Phase A Active Power Raw | meter_phase_a_active_power_raw | 8558 | input | int32 | W | 1 |  |
| Meter Phase B Active Power Raw | meter_phase_b_active_power_raw | 8560 | input | int32 | W | 1 |  |
| Meter Phase C Active Power Raw | meter_phase_c_active_power_raw | 8562 | input | int32 | W | 1 |  |
| Device Type Code | device_type_code | 7999 | input | uint16 |  |  |  |
| Protocol Number | protocol_number | 8000 | input | uint32 |  |  |  |
| Protocol Version | protocol_version | 8002 | input | uint32 |  |  |  |
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
| Load Power | load_power | 8158 | input | int32 | W | 10 |  |
| Battery Power | battery_power | 8160 | input | int32 | W | 10 | battery_enabled == true |
| Battery Level | battery_level | 8162 | input | uint16 | % | 0.1 | battery_enabled == true |
| Grid Import Energy | grid_import_energy | 8175 | input | uint32 | kWh | 0.1 |  |
| Grid Export Energy | grid_export_energy | 8177 | input | uint32 | kWh | 0.1 |  |
| Output Type Raw | output_type_raw | 8553 | input | uint16 |  |  |  |
| Phase A Voltage | phase_a_voltage | 8554 | input | uint16 | V | 0.1 |  |
| Phase B Voltage | phase_b_voltage | 8555 | input | uint16 | V | 0.1 |  |
| Phase C Voltage | phase_c_voltage | 8556 | input | uint16 | V | 0.1 |  |
| Grid Frequency | grid_frequency | 8557 | input | uint16 | Hz | 0.1 |  |
| Phase A Voltage Ch2 | phase_a_voltage_ch2 | 8564 | input | uint16 | V | 0.1 | channel_2_enabled == true |
| Phase B Voltage Ch2 | phase_b_voltage_ch2 | 8565 | input | uint16 | V | 0.1 | channel_2_enabled == true |
| Phase C Voltage Ch2 | phase_c_voltage_ch2 | 8566 | input | uint16 | V | 0.1 | channel_2_enabled == true |
| Grid Frequency Ch2 | grid_frequency_ch2 | 8567 | input | uint16 | Hz | 0.1 | channel_2_enabled == true |
| Phase A Active Power Ch2 | phase_a_active_power_ch2 | 8568 | input | int32 | W |  | channel_2_enabled == true |
| Phase B Active Power Ch2 | phase_b_active_power_ch2 | 8570 | input | int32 | W |  | channel_2_enabled == true |
| Phase C Active Power Ch2 | phase_c_active_power_ch2 | 8572 | input | int32 | W |  | channel_2_enabled == true |
| Charger Status Raw | charger_status_raw | 8551 | input | uint16 |  |  |  |

### Control Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| EMS Mode Selection | ems_mode_selection | 8023 | holding | uint16 |  |  |  |
| Charging/Discharging Command | charging_discharging_command | 8024 | holding | uint16 |  |  | battery_enabled == true |
| Charging/Discharging Power | charging_discharging_power | 8025 | holding | uint32 | kW | 0.1 | battery_enabled == true |
| Feed-in Power Limit Mode | feed_in_power_limit_mode | 8027 | holding | uint16 |  |  |  |
| Feed-in Power Limit | feed_in_power_limit | 8028 | holding | uint32 | kW | 0.1 |  |
| Export Power Limit Ratio | export_power_limit_ratio | 8030 | holding | int32 | % | 0.1 |  |
| External VPP Heartbeat | external_vpp_heartbeat | 8032 | holding | uint16 | s |  |  |
| Power-on/off | power_on_off | 8046 | holding | uint16 |  |  |  |
| Charger Charging Modes | charger_charging_modes | 8047 | holding | uint16 |  |  |  |
| Charger Enable | charger_enable | 8048 | holding | uint16 |  |  |  |
| Charger Grid Power Draw | charger_grid_power_draw | 8049 | holding | uint16 |  |  |  |
| Charger Power Limitation Enable | charger_power_limitation_enable | 8050 | holding | uint16 |  |  |  |
| Charger Power Limit Percentage | charger_power_limit_percentage | 8051 | holding | uint16 | % | 0.1 |  |

### Notes

- Addresses are the base register offsets used by the integration.
- Conditions reflect template logic and are evaluated in the dynamic config.
