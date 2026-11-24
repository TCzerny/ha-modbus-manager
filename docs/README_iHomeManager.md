# Sungrow iHomeManager

> **General documentation (Wiki):** [User Guide](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide) · [Template reference](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference) · [Capabilities and limits](https://github.com/TCzerny/ha-modbus-manager/wiki/Capabilities-and-Limits) · [Local customization](https://github.com/TCzerny/ha-modbus-manager/wiki/Local-Customization)

## Template Overview

- **Name**: Sungrow iHomeManager
- **Manufacturer**: Sungrow
- **Model**: iHomeManager
- **Type**: energy_manager
- **Default prefix**: IHM
- **Default slave ID**: 247
- **Firmware**: iHomeManager
- **Template version**: 1.0.17
- **Description**: Template for Sungrow iHomeManager EMS device (Modbus TCP). Includes iHomeManager meter, EMS, and charger registers.

## Dynamic Configuration

| Option | Description | Choices | Default |
| --- | --- | --- | --- |
| battery_config | Battery configuration | none (No battery), battery (Battery connected) | none |
| channel_2_enabled | Enable PROD.CT channel 2 registers | true, false | false |
| charger_enabled | Enable charger-related registers | true, false | false |
| charger_phases | EV charger phase count (hides phase B/C power sensors when single-phase) | 1, 3 | 3 |
| charger_region | EV charger regional mode map (EU/DE vs Australia) | EU (Europe (modes 160-163)), AU (Australia (modes 164-167)) | EU |
| protocol_version | iHomeManager Modbus protocol map (not app firmware). Match the device protocol version sensor. | 1.0.0 (V1.0.0 — initial map), 1.0.1 (V1.0.1 — meter channel 2, app software version, active power limit; feed-in ratio S32), 1.0.2 (V1.0.2 — feed-in limitation enable (8028); feed-in ratio is S16) | 1.0.2 |

<!-- mm-info:sungrow_ihomemanager.yaml start -->
`charger_enabled` is the supported path for the EV charger on iHomeManager. Do not add the AC011E `21xxx` template while iHomeManager holds charger TLS `:516`. Wiring: [Sungrow AC wallbox connection topologies](README_sungrow_wallbox_connection.md).

`protocol_version` is the iHomeManager Modbus protocol map, not app firmware. Match `protocol_version` / `protocol_version_raw` on the device.

- **V1.0.1+**: meter channel 2, application software version, active power limit (registers 8051–8052); feed-in **ratio** (8031) as **S32**; undocumented feed-in **value** (8029–8030 U32).
- **V1.0.2+**: feed-in limitation **enable** (8028); ratio (8031) **S16**.

Feed-in **value** uses `depends_on` enable **8028 = On** when the enable entity exists (V1.0.2). On V1.0.1 the enable entity is not created, so the value stays visible. The ratio is not gated on enable. Active power limit ratio still requires Active Power Limitation **On**.

Feed-in Power Limitation, Charger Enable, and Active Power Limitation use `0x55` Off and `0xAA` On. EMS mode values: `0` AI Mode, `1` Self-consumption, `2` Time plan, `4` VPP, `5` Compulsory mode.

Charger mode values: EU `160`–`163`, AU `164`–`167` (protocol address 8047). Protocol V1.0.2 only lists Fast/ECO (`160`/`161`); extra modes come from field maps. **Grid power draw** (protocol address 8049) is writable only in Eco.

Config-flow labels are translated under `config.step.dynamic_config.data`.

### EV charger on iHM vs wallbox `21xxx`

Poll **this** template (slave **247**, iHomeManager IP, port **502** or **503**, SSL off). The iHomeManager protocol documents charger **status 8552**, **modes 8048**, **enable 8049**, and **grid draw 8050**. Live power **8594–8601** is not in the PDF; it is in the template ([#86](https://github.com/TCzerny/ha-modbus-manager/issues/86)).

Not on iHomeManager (charger `21xxx` only, and not used while iHomeManager holds TLS `:516`): setpoint current, phase-count write, remote start/stop, session and lifetime energy, per-phase voltage and current. A scan of 8574–8773 during charging found **no energy counter**. Use a Riemann sum or `utility_meter` on `charger_active_power` for kWh, or keep the Sungrow EMS as the source of truth.

GRID.CT **8554–8564** is the iHomeManager meter, not the wallbox. Forum maps that put charger load on **8553** / **8558–8562** are the meter and output-type block. Live charger watts are **8593–8599** ([photovoltaikforum 248099](https://www.photovoltaikforum.com/thread/248099-ihomemanager-modbus-register/?pageNo=10), [#86](https://github.com/TCzerny/ha-modbus-manager/issues/86)).
<!-- mm-info:sungrow_ihomemanager.yaml end -->

## Registers

Address is the protocol address stored in the template.

### Sensors

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
| --- | --- | --- | --- | --- | --- | --- | --- |
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
| Charger Active Power | charger_active_power | 8593 | input | int32 | W |  | charger_enabled == true |
| Charger Phase A Active Power | charger_phase_a_active_power | 8595 | input | int32 | W |  | charger_enabled == true |
| Charger Phase B Active Power | charger_phase_b_active_power | 8597 | input | int32 | W |  | charger_enabled == true and charger_phases == 3 |
| Charger Phase C Active Power | charger_phase_c_active_power | 8599 | input | int32 | W |  | charger_enabled == true and charger_phases == 3 |
| Output Type Raw | output_type_raw | 8553 | input | uint16 |  |  |  |
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

### Controls

| Name | Unique ID | Type | Address | Input | Data | Unit | Scale | Condition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EMS Mode Selection | ems_mode_selection | select | 8023 | holding | uint16 |  |  |  |
| Charging/Discharging Command | charging_discharging_command | select | 8024 | holding | uint16 |  |  | battery_enabled == true |
| Charging/Discharging Power | charging_discharging_power | number | 8025 | holding | uint32 | kW | 0.1 | battery_enabled == true |
| Feed-in Power Limitation | feed_in_power_limitation | select | 8027 | holding | uint16 |  |  |  |
| Feed-in Power Limit Value | feed_in_power_limit_value | number | 8028 | holding | uint32 | kW | 0.1 |  |
| Feed-in Power Limit Ratio | feed_in_power_limit_ratio | number | 8030 | holding | int16 | % | 0.1 |  |
| Power-on/off | power_on_off | select | 8046 | holding | uint16 |  |  |  |
| Charger Charging Modes | charger_charging_modes | select | 8047 | holding | uint16 |  |  | charger_enabled == true and charger_region == 'EU' |
| Charger Charging Modes | charger_charging_modes_au | select | 8047 | holding | uint16 |  |  | charger_enabled == true and charger_region == 'AU' |
| Charger Enable | charger_enable | switch | 8048 | holding | uint16 |  |  | charger_enabled == true |
| Charger Grid Power Draw | charger_grid_power_draw | select | 8049 | holding | uint16 |  |  | charger_enabled == true |
| Active Power Limitation | active_power_limitation | switch | 8050 | holding | uint16 |  |  |  |
| Active Power Limit Ratio | active_power_limit_ratio | number | 8051 | holding | uint16 | % | 0.1 |  |

### Calculated sensors

| Name | Unique ID | Type | Unit | Condition |
| --- | --- | --- | --- | --- |
| Protocol Version | protocol_version | sensor |  |  |
| Net Grid Power | net_grid_power | sensor | W |  |
| Import Power | import_power | sensor | W |  |
| Export Power | export_power | sensor | W |  |
| Total Phase Power | total_phase_power | sensor | W |  |
| Phase A Power | phase_a_power | sensor | W |  |
| Phase B Power | phase_b_power | sensor | W |  |
| Phase C Power | phase_c_power | sensor | W |  |
| Total Phase Power Ch2 | total_phase_power_ch2 | sensor | W | channel_2_enabled == true |
| Charger Total Phase Power | charger_total_phase_power | sensor | W | charger_enabled == true and charger_phases == 3 |

## Additional information

<!-- mm-kept start -->
### Combined Device with a Sungrow inverter

A [Cross-hub Combined Device](README_Combined_Device.md) can link an inverter hub and an iHomeManager hub. It provides:

- iHomeManager grid sensors (`grid_import_energy`, `grid_export_energy`, import and export power) at the **GRID.CT**
- **`combined_daily_consumed_energy`** / **`combined_total_consumed_energy`** from inverter PV and battery plus iHomeManager grid data ([#50](https://github.com/TCzerny/ha-modbus-manager/issues/50))

`daily_consumed_energy` on the inverter template alone does not include iHomeManager grid data.

### Notes

- The Address column is the protocol address stored in the template. The Sungrow document register number is that address plus 1.
- Output Type (protocol address 8553) is an enum: `0` Single, `1` 3P4L, `2` 3P3L. It is not a voltage.
- **Feed-in** controls (protocol addresses 8027–8030) limit export to the grid.
- **Active power** controls (protocol addresses 8050–8051) limit inverter AC output. That is not feed-in limitation.
- Register **8032** (External VPP Heartbeat) is in the protocol and is not in this template.
- Grid import and export power are calculated from `meter_active_power_raw` (positive = import, negative = export).
<!-- mm-kept end -->
