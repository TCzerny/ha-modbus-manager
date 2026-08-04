## Sungrow SBR / SBH Battery Template

> **General documentation (Wiki):** [User Guide](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide) · [Template reference](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference) · [Capabilities and limits](https://github.com/TCzerny/ha-modbus-manager/wiki/Capabilities-and-Limits) · [Local customization](https://github.com/TCzerny/ha-modbus-manager/wiki/Local-Customization)

This document lists the Modbus registers for the Sungrow SBR/SBH battery template: `sungrow_sbr_battery.yaml`.

### Template Overview

- **Name**: Sungrow SBR Battery (covers SBR and SBH series)
- **Type**: `battery`
- **Default prefix**: `SBR`
- **Default slave ID**: `200`
- **Firmware**: `22011.01.19`

### SBR vs SBH

- **SBR** (SBR064–SBR256): 3.2 kWh per module, 30 A, compatible with SH-RS (single-phase) and SH-RT/SH-T (three-phase).
- **SBH** (SBH100–SBH400): 5 kWh per module, up to 50 A. Reported on **SH-T** and **SH-RS** setups ([#77](https://github.com/TCzerny/ha-modbus-manager/issues/77)). Both series use the Residential Hybrid Inverter Modbus protocol; battery data is read on the **battery Modbus unit** (registers **10710+**), not on inverter slave 1.

### Modbus unit ID (slave ID) — not always 200

| Path | Typical TCP Unit ID | Notes |
|------|---------------------|--------|
| **Inverter LAN (RJ45)** on SH-RT / SH-T | **200** | Internal battery address on the inverter Modbus port |
| **WiNet-S** (Wi‑Fi or cable to dongle) | **Forwarded ID** from WiNet web UI | Internal address **200** is often forwarded as **2** (or another ID) — see below |
| **RS485 direct (A1/B1)** | Often **200** | Planned dedicated `RS485` connection type ([#82](https://github.com/TCzerny/ha-modbus-manager/issues/82)) |

**WiNet-S:** Open **Device maintenance → Device list** on the WiNet web page. The **forwarded Modbus ID** column is the Unit ID for Modbus TCP (e.g. inverter **1**, first SBH **2**). Using Unit ID **200** on WiNet-S usually times out even though the battery is reachable ([#77](https://github.com/TCzerny/ha-modbus-manager/issues/77)).

The battery **slave ID is configurable** during setup (`battery_slave_id`). Default **200** applies to direct LAN/RS485; WiNet-S users should enter the **forwarded ID** from the device list.

### Register map overview (do not confuse with inverter PV statistics)

This template uses the **SBR/SBH battery map** starting at **10710** on the battery unit:

| Range | Content |
|-------|---------|
| **10710** | Battery serial number (ASCII string) |
| **10720** | BCU firmware string (ASCII) |
| **10740–10747** | Base pack data: voltage, current, temperature, SOC, SOH, total charge/discharge energy |
| **10756–10788** | **SBR detailed cell/module diagnostics** (max/min cell voltage, module temps, cell types, DC switch) |
| **10821+** | Per-module serial numbers |

**Template filtering:** Registers **10756+**, module serials **10821+**, and related calculated sensors are created only when **`connection_type != 'WINET'`** (direct inverter LAN / RS485). **WiNet-S** setups keep base registers **10710–10747** only ([#77](https://github.com/TCzerny/ha-modbus-manager/issues/77)). **Note:** Some **SBH** firmware maps may still not implement **10756+** even on LAN — report if you see Modbus exception 2 on those addresses.

**SBH vs SBR diagnostics:** Base registers **10710–10747** work on tested **SBH150** over WiNet-S (Unit ID 2). Registers **10756+** return Modbus exception 2 on SBH150 — they match the **SBR** detailed map and are often only available on **direct inverter LAN** for SBR stacks ([#77](https://github.com/TCzerny/ha-modbus-manager/issues/77), [#74](https://github.com/TCzerny/ha-modbus-manager/issues/74)). On **WiNet-S**, detailed cell/module registers are generally **not** exposed even for SBR.

### Three ways to get battery data

| Setup | What you get |
|-------|----------------|
| **`standard_battery`** on inverter (slave **1**) | Summary battery sensors on the **inverter** template — works on **LAN and WiNet-S** |
| **Separate SBR/SBH device** (this template) | Pack serial, BCU firmware, **10740+** totals; SBR cell diagnostics when the path exposes them |
| **Inverter slave 1 only** | No module serials / no 10756+ cell detail |

When the inverter uses **WiNet-S**, the config flow currently limits **`battery_config`** to **`none`** or **`standard_battery`** on the inverter entry; adding this template still requires a path where **`sbr_battery`** is allowed (typically **LAN** on the inverter hub) or configuring the battery device with the correct **forwarded slave ID** if your setup supports it ([#77](https://github.com/TCzerny/ha-modbus-manager/issues/77)).

### Dynamic Configuration

- `valid_models`: model list based on module count and max_power (W)
  - **SBR**: SBR064 (2 mod), SBR096 (3 mod), SBR128 (4), SBR160 (5), SBR192 (6), SBR224 (7), SBR256 (8)
  - **SBH**: SBH100 (2 mod), SBH150 (3), SBH200 (4), SBH250 (5), SBH300 (6), SBH350 (7), SBH400 (8)
- `battery_config`: options=['sbr_battery'] (default: sbr_battery)
- `firmware_version`: options=['22011.01.19'] (default: 22011.01.19) — **register-map baseline: this release or higher**; a new option is added only when Sungrow changes specific registers between releases

### Sensor Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Battery 1 Serial Number | battery_1_serial_number | 10710 | input | string |  |  |  |
| Battery 1 BCU Firmware | battery_1_bcu_firmware | 10720 | input | string |  |  |  |
| Battery 1 Voltage | battery_1_voltage | 10740 | input | uint16 | V | 0.1 |  |
| Battery 1 Current | battery_1_current | 10741 | input | int16 | A | 0.1 |  |
| Battery 1 Temperature | battery_1_temperature | 10742 | input | uint16 | °C | 0.1 |  |
| Battery 1 SOC | battery_1_soc | 10743 | input | uint16 | % | 0.1 |  |
| Battery 1 SOH | battery_1_soh | 10744 | input | uint16 | % | 1 |  |
| Battery 1 Total Battery Charge | battery_1_total_battery_charge | 10745 | input | uint32 | kWh | 0.1 |  |
| Battery 1 Total Battery Discharge | battery_1_total_battery_discharge | 10747 | input | uint32 | kWh | 0.1 |  |
| Battery 1 Max Voltage of Cell | battery_1_max_voltage_of_cell | 10756 | input | uint16 | V | 0.0001 | not WINET |
| Battery 1 Position of Max Voltage Cell | battery_1_position_of_max_voltage_cell | 10757 | input | uint16 |  | 1 |  |
| Battery 1 Min Voltage of Cell | battery_1_min_voltage_of_cell | 10758 | input | uint16 | V | 0.0001 |  |
| Battery 1 Position of Min Voltage Cell | battery_1_position_of_min_voltage_cell | 10759 | input | uint16 |  | 1 |  |
| Battery 1 Max Temperature of Module | battery_1_max_temperature_of_module | 10760 | input | uint16 | °C | 0.1 |  |
| Battery 1 Position of Max Temperature of Module | battery_1_position_of_max_temperature_of_module | 10761 | input | uint16 |  | 1 |  |
| Battery 1 Min Temperature of Module | battery_1_min_temperature_of_module | 10762 | input | uint16 | °C | 0.1 |  |
| Battery 1 Position of Min Temperature of Module | battery_1_position_of_min_temperature_of_module | 10763 | input | uint16 |  | 1 |  |
| Battery 1 Max Cell Voltage of Module 1 | battery_1_max_cell_voltage_of_module_1 | 10764 | input | uint16 | V | 0.0001 |  |
| Battery 1 Max Cell Voltage of Module 2 | battery_1_max_cell_voltage_of_module_2 | 10765 | input | uint16 | V | 0.0001 |  |
| Battery 1 Max Cell Voltage of Module 3 | battery_1_max_cell_voltage_of_module_3 | 10766 | input | uint16 | V | 0.0001 |  |
| Battery 1 Max Cell Voltage of Module 4 | battery_1_max_cell_voltage_of_module_4 | 10767 | input | uint16 | V | 0.0001 |  |
| Battery 1 Max Cell Voltage of Module 5 | battery_1_max_cell_voltage_of_module_5 | 10768 | input | uint16 | V | 0.0001 |  |
| Battery 1 Max Cell Voltage of Module 6 | battery_1_max_cell_voltage_of_module_6 | 10769 | input | uint16 | V | 0.0001 |  |
| Battery 1 Max Cell Voltage of Module 7 | battery_1_max_cell_voltage_of_module_7 | 10770 | input | uint16 | V | 0.0001 |  |
| Battery 1 Max Cell Voltage of Module 8 | battery_1_max_cell_voltage_of_module_8 | 10771 | input | uint16 | V | 0.0001 |  |
| Battery 1 Min Cell Voltage of Module 1 | battery_1_min_cell_voltage_of_module_1 | 10772 | input | uint16 | V | 0.0001 |  |
| Battery 1 Min Cell Voltage of Module 2 | battery_1_min_cell_voltage_of_module_2 | 10773 | input | uint16 | V | 0.0001 |  |
| Battery 1 Min Cell Voltage of Module 3 | battery_1_min_cell_voltage_of_module_3 | 10774 | input | uint16 | V | 0.0001 |  |
| Battery 1 Min Cell Voltage of Module 4 | battery_1_min_cell_voltage_of_module_4 | 10775 | input | uint16 | V | 0.0001 |  |
| Battery 1 Min Cell Voltage of Module 5 | battery_1_min_cell_voltage_of_module_5 | 10776 | input | uint16 | V | 0.0001 |  |
| Battery 1 Min Cell Voltage of Module 6 | battery_1_min_cell_voltage_of_module_6 | 10777 | input | uint16 | V | 0.0001 |  |
| Battery 1 Min Cell Voltage of Module 7 | battery_1_min_cell_voltage_of_module_7 | 10778 | input | uint16 | V | 0.0001 |  |
| Battery 1 Min Cell Voltage of Module 8 | battery_1_min_cell_voltage_of_module_8 | 10779 | input | uint16 | V | 0.0001 |  |
| Battery 1 Cell Type of Module 1 | battery_1_cell_type_of_module_1 | 10780 | input | uint16 |  | 1 |  |
| Battery 1 Cell Type of Module 2 | battery_1_cell_type_of_module_2 | 10781 | input | uint16 |  | 1 |  |
| Battery 1 Cell Type of Module 3 | battery_1_cell_type_of_module_3 | 10782 | input | uint16 |  | 1 |  |
| Battery 1 Cell Type of Module 4 | battery_1_cell_type_of_module_4 | 10783 | input | uint16 |  | 1 |  |
| Battery 1 Cell Type of Module 5 | battery_1_cell_type_of_module_5 | 10784 | input | uint16 |  | 1 |  |
| Battery 1 Cell Type of Module 6 | battery_1_cell_type_of_module_6 | 10785 | input | uint16 |  | 1 |  |
| Battery 1 Cell Type of Module 7 | battery_1_cell_type_of_module_7 | 10786 | input | uint16 |  | 1 |  |
| Battery 1 Cell Type of Module 8 | battery_1_cell_type_of_module_8 | 10787 | input | uint16 |  | 1 |  |
| Battery 1 State of DC Switch | battery_1_state_of_dc_switch | 10788 | input | uint16 |  | 1 |  |
| Battery 1 module 1 serial number | battery_1_module_1_sn | 10821 | input | string |  |  | modules >= 1 |
| Battery 1 module 2 serial number | battery_1_module_2_sn | 10830 | input | string |  |  | modules >= 2 |
| Battery 1 module 3 serial number | battery_1_module_3_sn | 10839 | input | string |  |  | modules >= 3 |
| Battery 1 module 4 serial number | battery_1_module_4_sn | 10848 | input | string |  |  |  |
| Battery 1 module 5 serial number | battery_1_module_5_sn | 10857 | input | string |  |  |  |
| Battery 1 module 6 serial number | battery_1_module_6_sn | 10866 | input | string |  |  |  |
| Battery 1 module 7 serial number | battery_1_module_7_sn | 10875 | input | string |  |  |  |
| Battery 1 module 8 serial number | battery_1_module_8_sn | 10884 | input | string |  |  |  |

### Calculated Sensors

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Battery 1 Voltage Spread | battery_1_voltage_spread |  |  |  | V |  |  |
| Battery 1 Module 1 Deviation | battery_1_module_1_deviation |  |  |  | V |  | modules >= 1 |
| Battery 1 Module 2 Deviation | battery_1_module_2_deviation |  |  |  | V |  | modules >= 2 |
| Battery 1 Module 3 Deviation | battery_1_module_3_deviation |  |  |  | V |  | modules >= 3 |
| Battery 1 Module 4 Deviation | battery_1_module_4_deviation |  |  |  | V |  | modules >= 4 |
| Battery 1 Module 5 Deviation | battery_1_module_5_deviation |  |  |  | V |  | modules >= 5 |
| Battery 1 Module 6 Deviation | battery_1_module_6_deviation |  |  |  | V |  | modules >= 6 |
| Battery 1 Module 7 Deviation | battery_1_module_7_deviation |  |  |  | V |  | modules >= 7 |
| Battery 1 Module 8 Deviation | battery_1_module_8_deviation |  |  |  | V |  | modules >= 8 |
| Battery 1 Temperature Spread | battery_1_temperature_spread |  |  |  | °C |  |  |
| Battery 1 Average Module Voltage | battery_1_average_module_voltage |  |  |  | V |  |  |
| Battery 1 Max Module Deviation | battery_1_max_module_deviation |  |  |  | V |  |  |
| Battery 1 Voltage Imbalance Percentage | battery_1_voltage_imbalance_percentage |  |  |  | % |  |  |
| Battery 1 Module 1 Cell Voltage Range | battery_1_module_1_cell_voltage_range |  |  |  | V |  | modules >= 1 |
| Battery 1 Module 2 Cell Voltage Range | battery_1_module_2_cell_voltage_range |  |  |  | V |  | modules >= 2 |
| Battery 1 Module 3 Cell Voltage Range | battery_1_module_3_cell_voltage_range |  |  |  | V |  | modules >= 3 |
| Battery 1 Module 4 Cell Voltage Range | battery_1_module_4_cell_voltage_range |  |  |  | V |  | modules >= 4 |
| Battery 1 Module 5 Cell Voltage Range | battery_1_module_5_cell_voltage_range |  |  |  | V |  | modules >= 5 |
| Battery 1 Module 6 Cell Voltage Range | battery_1_module_6_cell_voltage_range |  |  |  | V |  | modules >= 6 |
| Battery 1 Module 7 Cell Voltage Range | battery_1_module_7_cell_voltage_range |  |  |  | V |  | modules >= 7 |
| Battery 1 Module 8 Cell Voltage Range | battery_1_module_8_cell_voltage_range |  |  |  | V |  | modules >= 8 |
| Battery 1 Max Module Cell Voltage Range | battery_1_max_module_cell_voltage_range |  |  |  | V |  |  |
| Battery 1 Max Voltage Cell Info | battery_1_max_voltage_cell_info |  |  |  |  |  |  |
| Battery 1 Min Voltage Cell Info | battery_1_min_voltage_cell_info |  |  |  |  |  |  |
| Battery 1 Max Temperature Module Info | battery_1_max_temperature_module_info |  |  |  |  |  |  |
| Battery 1 Min Temperature Module Info | battery_1_min_temperature_module_info |  |  |  |  |  |  |

### Notes

- Addresses are the base register offsets used by the integration.
- Conditions reflect template logic and are evaluated in the dynamic config.
- **10756+** = battery cell/module diagnostics (this template), not inverter monthly/yearly PV energy statistics (see `sungrow_shx_dynamic.yaml`, registers 6226+ on slave 1).
