# Sungrow SHx Dynamic Template

## 📋 Overview

The **Sungrow SHx Dynamic Template** is a complete, dynamically configurable template for all Sungrow SHx inverter models. Based on the mkaiser implementation, it contains all available registers and supports automatic filtering based on device configuration.

## 🏭 Supported Inverter Models

The template supports **all 36** following Sungrow SHx models:

### 🔋 Hybrid-Inverters (with Battery Support)
- **SH5.0RT, SH6.0RT, SH8.0RT, SH10RT** - Standard Hybrid Models
- **SH5.0RT-20, SH6.0RT-20, SH8.0RT-20, SH10RT-20** - 20kW Hybrid Models
- **SH5.0RT-V112, SH6.0RT-V112, SH8.0RT-V112, SH10RT-V112** - V112 Versions
- **SH5.0RT-V122, SH6.0RT-V122, SH8.0RT-V122, SH10RT-V122** - V122 Versions

### ⚡ String-Inverters (without Battery)
- **SH3K6, SH4K6, SH5K-20, SH5K-V13** - Standard String Models
- **SH3K6-30, SH4K6-30, SH5K-30** - 30kW String Models
- **SH3.0RS, SH3.6RS, SH4.0RS, SH5.0RS, SH6.0RS, SH8.0RS, SH10RS** - RS Series

### 🏠 Residential Models
- **SH5T, SH6T, SH8T, SH10T, SH12T, SH15T, SH20T, SH25T** - T Series

### 🏢 Commercial Models
- **MG5RL, MG6RL** - Commercial Series

## ⚙️ Dynamic Configuration

### 📊 Configurable Parameters

| Parameter | Options | Default | Description |
|-----------|----------|---------|-------------|
| **Model** | See list above | Required | Inverter model selection |
| **Phases** | 1, 3 | Auto | Number of phases (auto-detected from model) |
| **MPPT** | 1, 2, 3 | Auto | Number of MPPT trackers (auto-detected from model) |
| **Battery** | none, standard_battery, sbr_battery | none | Battery configuration |
| **Meter Type** | DTSU666, DTSU666-20 | DTSU666 | Meter type connected to inverter |
| **Firmware** | String | "03011.95.01" | Firmware version (e.g. "03011.95.01") |
| **Strings** | 1-24 | Auto | Number of PV strings (auto-detected from model) |
| **Connection** | LAN, WINET | LAN | Connection type |

### 🔄 Automatic Filtering

#### **Phase Filtering**
- **1-phase:** Only Phase A registers are loaded
- **3-phase:** All Phase A, B, C registers are loaded

#### **MPPT Filtering**
- **MPPT 1:** Only MPPT1 registers
- **MPPT 2:** MPPT1 + MPPT2 registers
- **MPPT 3:** All MPPT1, MPPT2, MPPT3 registers

#### **Battery Filtering**
- **Battery none:** No battery registers
- **Battery standard_battery:** Inverter battery registers only
- **Battery sbr_battery:** Inverter battery registers + SBR battery template entities

#### **Meter Type Filtering**
- **DTSU666:** Standard single-channel meter (registers 5600-5606)
- **DTSU666-20:** Dual-channel meter with Channel 2 support (registers 5600-5606 + 13199-13205)
- **Note:** iHomeManager is now a separate template (`sungrow_ihomemanager.yaml`) and should not be selected here

#### **Connection Filtering**
- **LAN:** All registers available
- **WINET:** Some statistical registers not available

#### **Firmware Adaptation**
- Automatic sensor parameter adjustment based on firmware version
- Support for different data formats between firmware versions

## 📡 Available Sensors

### 🔧 Basic Inverter Data
- **Inverter Serial** - Serial number
- **Device Type Code** - Automatic model detection
- **Inverter Temperature** - Inverter temperature
- **System State** - System status with flags

### 🔗 Master/Slave Mode (Multi-Inverter / Cascade)
Undocumented holding registers for Master/Slave cascade configuration. Available as **sensors** (read) and **controls** (read/write). Values may vary by model/firmware.

| Register | Address | Type | Description | Mapped Values |
|----------|---------|------|-------------|---------------|
| **Master Slave Mode** | 33499 | U16 | Master/Slave mode enabled/disabled | 0xAA (170) = Enabled, 0x55 (85) = Disabled |
| **Master Slave Role** | 33500 | U16 | Role in cascade (Master or Slave 1-4) | 0xA0=Master, 0xA1=Slave 1, 0xA2=Slave 2, 0xA3=Slave 3, 0xA4=Slave 4 |
| **Slave Count** | 33501 | U16 | Number of slaves in cascade | 0-4 valid; 65535 (0xFFFF) = Invalid/Not supported |

- **Note:** On single-inverter setups (e.g. SH10RT + SBR battery), Slave Count may return 65535 (not implemented). Master/Slave registers are primarily for multi-inverter cascade systems.

### ⚡ MPPT Data (1-3 Trackers)
- **MPPT Voltage/Current** - Voltage and current per tracker
- **MPPT Power** - Calculated power per tracker
- **Total DC Power** - Total DC power

### 🔌 Phase Data (1 or 3 Phases)
- **Phase Voltage/Current** - Voltage and current per phase
- **Phase Power** - Calculated power per phase
- **Total Active Power** - Total AC power

### 🔋 Battery Data (only with Battery Support)
- **Battery Voltage/Current** - Battery voltage and current
- **Battery Power** - Battery power (charging/discharging)
- **Battery Level** - Battery state of charge (SoC)
- **Battery Temperature** - Battery temperature
- **Battery State of Health** - Battery health
- **Backup Power** - Backup power per phase

### 📊 Energy Data
- **Daily/Total PV Generation** - Daily/Total PV generation
- **Daily/Total Export** - Daily/Total export
- **Daily/Total Import** - Daily/Total import
- **Daily/Total Battery Charge/Discharge** - Battery charge cycles

### 🎛️ Meter Data (Grid Monitoring)
- **Meter Active Power** - Grid active power (DTSU666/DTSU666-20)
- **Meter Phase Power** - Phase-specific power (DTSU666/DTSU666-20, 3-phase only)
- **Meter Voltage/Current** - Grid voltage and current
- **Grid Frequency** - Grid frequency
- **Meter Channel 2** - Channel 2 power data (DTSU666-20 dual-channel meter only)
  - **Note:** iHomeManager meter support is now provided by the separate `sungrow_ihomemanager.yaml` template

### 📈 Statistical Data (LAN only)
- **Monthly PV Generation** - Monthly PV generation (12 months)
- **Yearly PV Generation** - Yearly PV generation (2019-2029)
- **Monthly Export** - Monthly export (12 months)
- **Yearly Export** - Yearly export (2019-2029)

## 🎛️ Controls (Write Access)

### 🔧 System Modes
- **EMS Mode Selection** - Energy management mode
- **Load Adjustment Mode** - Load adjustment mode
- **Backup Mode** - Enable/disable backup mode

### ⚡ Power Control
- **Export Power Limit** - Export power limitation
- **Export Power Limit Mode** - Enable/disable export limitation

### 🔋 Battery Control
- **Max SoC** - Maximum battery state of charge
- **Min SoC** - Minimum battery state of charge
- **Reserved SoC for Backup** - Reserved SoC for backup
- **Battery Max Charge Power** - Maximum battery charge power
- **Battery Max Discharge Power** - Maximum battery discharge power
- **Battery Charging Start Power** - Power threshold to start battery charging
- **Battery Discharging Start Power** - Power threshold to start battery discharging

### 🔄 System Control
- **Forced Startup Under Low SoC Standby** - Enable/disable forced startup when battery is in low SoC standby mode
  - **Address:** 13016 (register 13017)
  - **Values:** 0xAA (Enabled) / 0x55 (Disabled)
  - **Purpose:** Allows the inverter to start even when battery is in low SoC standby mode
  - **Note:** This control addresses issue #444 from mkaiser's implementation (SH10RT no standby mode after latest firmware update)

### 🔗 Master/Slave Mode (Multi-Inverter / Cascade)
Holding registers for Master/Slave cascade configuration. Available as select (Mode, Role) and number (Slave Count) controls.

| Control | Address | Type | Options / Range |
|---------|---------|------|-----------------|
| **Master Slave Mode** | 33499 | Select | 0xAA (Enabled), 0x55 (Disabled) |
| **Master Slave Role** | 33500 | Select | 0xA0 (Master), 0xA1 (Slave 1), 0xA2 (Slave 2), 0xA3 (Slave 3), 0xA4 (Slave 4) |
| **Slave Count** | 33501 | Number | 0-4 |

## 🧮 Calculated Sensors

### ⚡ Power Calculations
- **MPPT Power** - Calculated power per MPPT (MPPT1-4)
- **Total MPPT Power** - Total MPPT power (sum of all MPPT trackers)
- **Phase Power** - Calculated power per phase (A, B, C)
- **Total Phase Power** - Total phase power

### 🔄 Grid Power Calculations
- **Grid Import Power** - Grid import (positive)
- **Grid Export Power** - Grid export (negative)
- **Net Grid Power** - Net grid power

### 🔋 Battery Power Calculations
- **Battery Charging Power** - Battery charging power
- **Battery Discharging Power** - Battery discharging power
- **Signed Battery Power** - Signed battery power

### 📊 Efficiency Calculations
- **Solar to Grid Efficiency** - PV to grid efficiency
- **Battery to Load Efficiency** - Battery to load efficiency
- **DC to AC Efficiency** - Inverter efficiency (AC output / DC input)
- **Power Balance** - System power balance

### 🛡️ Meter Power Handling
- **Meter Active Power** - With 0x7FFFFFFF error handling
- **Meter Phase Power** - Phase-specific with error handling

### 🏠 Home Assistant Energy Dashboard Compatible Sensors
These sensors follow the HA Energy Dashboard convention: **positive values for consumption/discharging/import, negative values for generation/charging/export**.

- **Battery Charging Power Signed** - Positive when charging (for display purposes)
- **Battery Discharging Power Signed** - Positive when discharging (matches HA convention)
- **Grid Power Signed** - Negative when exporting (generation), positive when importing (consumption)
- **Grid Export Power Signed** - Only export power as negative values
- **Grid Import Power Signed** - Only import power as positive values

**Usage:** Use `sensor.{PREFIX}_battery_power` directly for HA Energy Dashboard battery sensor (already has correct sign). Use `sensor.{PREFIX}_grid_power_signed` for grid power in Energy Dashboard.

### 📈 PV Analysis & Performance Metrics

#### Self-Consumption & Autarky
- **Self-Consumption Rate** - Percentage of PV generation consumed directly (not exported to grid)
- **Autarky Rate** - Percentage of load supplied by PV/Battery (self-sufficiency)
- **Grid Dependency** - Percentage of load that depends on grid (inverse of autarky)

#### Energy Flow Analysis
- **PV to Load Direct** - PV power going directly to load (without battery)
- **PV to Battery** - PV power going to battery (charging)
- **Battery to Load** - Battery power going to load (discharging)
- **Grid to Load** - Grid power going to load (importing)
- **Net Consumption** - Net consumption after PV and battery supply

#### MPPT Performance Analysis
- **MPPT Power Deviation** - Maximum deviation from average MPPT power (indicates imbalance)
- **MPPT Utilization** - How much of total DC power comes from MPPT trackers (should be close to 100%)

#### PV System Performance
- **PV Capacity Factor** - Current PV power as percentage of inverter rated capacity
- **PV Generation Hours Today** - Equivalent generation hours at current power level (approximation)

## 📋 Complete Entity Reference

This section contains all entities that will be created by this template, including Modbus register addresses and unique IDs. Entities are automatically filtered based on your device configuration (phases, MPPT count, battery enabled, connection type).

### Sensors (Read-only)

| Address | Name | Unique ID |
|---------|------|-----------|
| 5035 | Grid frequency 0.1 Hz *(commented out)* | grid_frequency_alt |
| 4951 | Protocol version raw | protocol_version_raw |
| 4953 | Certification version of ARM Software | certification_version_arm_software |
| 4968 | Certification version of DSP Software | certification_version_dsp_software |
| 4989 | Sungrow inverter serial | inverter_serial |
| 4999 | Sungrow device type code | sungrow_device_type_code |
| 5000 | Nominal output power | nominal_output_power |
| 5001 | Output type | output_type |
| 5002 | Daily PV generation & battery discharge | daily_pv_gen_battery_discharge |
| 5003 | Total PV generation & battery discharge | total_pv_gen_battery_discharge |
| 5007 | Inverter temperature | inverter_temperature |
| 5010 | MPPT1 voltage | mppt1_voltage |
| 5011 | MPPT1 current | mppt1_current |
| 5012 | MPPT2 voltage | mppt2_voltage |
| 5013 | MPPT2 current | mppt2_current |
| 5014 | MPPT3 voltage | mppt3_voltage |
| 5015 | MPPT3 current | mppt3_current |
| 5016 | Total DC power | total_dc_power |
| 5018 | Phase A voltage | phase_a_voltage |
| 5019 | Phase B voltage | phase_b_voltage |
| 5020 | Phase C voltage | phase_c_voltage |
| 5032 | Reactive power | reactive_power |
| 5034 | Power factor | power_factor |
| 5213 | Battery power | battery_power |
| 5241 | Grid frequency | grid_frequency |
| 5600 | Meter active power raw | meter_active_power_raw |
| 5602 | Meter phase A active power raw | meter_phase_a_active_power_raw |
| 5604 | Meter phase B active power raw | meter_phase_b_active_power_raw |
| 5606 | Meter phase C active power raw | meter_phase_c_active_power_raw |
| 5621 | Min Export Power Limit Value | min_export_power_limit_value |
| 5622 | Max Export Power Limit Value | max_export_power_limit_value |
| 5627 | BDC rated power | bdc_rated_power |
| 5630 | Battery current | battery_current |
| 5634 | BMS max. charging current | bms_max_charging_current |
| 5635 | BMS max. discharging current | bms_max_discharging_current |
| 5638 | Battery capacity | battery_capacity |
| 5722 | Backup phase A power | backup_phase_a_power |
| 5723 | Backup phase B power | backup_phase_b_power |
| 5724 | Backup phase C power | backup_phase_c_power |
| 5725 | Total backup power | total_backup_power |
| 5740 | Meter phase A voltage | meter_phase_a_voltage |
| 5741 | Meter phase B voltage | meter_phase_b_voltage |
| 5742 | Meter phase C voltage | meter_phase_c_voltage |
| 5743 | Meter phase A current | meter_phase_a_current |
| 5744 | Meter phase B current | meter_phase_b_current |
| 5745 | Meter phase C current | meter_phase_c_current |
| 6226 | Monthly PV generation (01 January) | monthly_pv_generation_01_january |
| 6227 | Monthly PV generation (02 February) | monthly_pv_generation_02_february |
| 6228 | Monthly PV generation (03 March) | monthly_pv_generation_03_march |
| 6229 | Monthly PV generation (04 April) | monthly_pv_generation_04_april |
| 6230 | Monthly PV generation (05 May) | monthly_pv_generation_05_may |
| 6231 | Monthly PV generation (06 June) | monthly_pv_generation_06_june |
| 6232 | Monthly PV generation (07 July) | monthly_pv_generation_07_july |
| 6233 | Monthly PV generation (08 August) | monthly_pv_generation_08_august |
| 6234 | Monthly PV generation (09 September) | monthly_pv_generation_09_september |
| 6235 | Monthly PV generation (10 October) | monthly_pv_generation_10_october |
| 6236 | Monthly PV generation (11 November) | monthly_pv_generation_11_november |
| 6237 | Monthly PV generation (12 December) | monthly_pv_generation_12_december |
| 6257 | Yearly PV generation (2019) | yearly_pv_generation_2019 |
| 6259 | Yearly PV generation (2020) | yearly_pv_generation_2020 |
| 6261 | Yearly PV generation (2021) | yearly_pv_generation_2021 |
| 6263 | Yearly PV generation (2022) | yearly_pv_generation_2022 |
| 6265 | Yearly PV generation (2023) | yearly_pv_generation_2023 |
| 6267 | Yearly PV generation (2024) | yearly_pv_generation_2024 |
| 6269 | Yearly PV generation (2025) | yearly_pv_generation_2025 |
| 6271 | Yearly PV generation (2026) | yearly_pv_generation_2026 |
| 6273 | Yearly PV generation (2027) | yearly_pv_generation_2027 |
| 6275 | Yearly PV generation (2028) | yearly_pv_generation_2028 |
| 6277 | Yearly PV generation (2029) | yearly_pv_generation_2029e |
| 6595 | Monthly export (01 January) | monthly_export_01_january |
| 6596 | Monthly export (02 February) | monthly_export_02_february |
| 6597 | Monthly export (03 March) | monthly_export_03_march |
| 6598 | Monthly export (04 April) | monthly_export_04_april |
| 6599 | Monthly export (05 May) | monthly_export_05_may |
| 6600 | Monthly export (06 June) | monthly_export_06_june |
| 6601 | Monthly export (07 July) | monthly_export_07_july |
| 6602 | Monthly export (08 August) | monthly_export_08_august |
| 6603 | Monthly export (09 September) | monthly_export_09_september |
| 6604 | Monthly export (10 October) | monthly_export_10_october |
| 6605 | Monthly export (11 November) | monthly_export_11_november |
| 6606 | Monthly export (12 December) | monthly_export_12_december |
| 6615 | Yearly Export (2019) | yearly_export_2019 |
| 6617 | Yearly Export (2020) | yearly_export_2020 |
| 6619 | Yearly Export (2021) | yearly_export_2021 |
| 6621 | Yearly Export (2022) | yearly_export_2022 |
| 6623 | Yearly Export (2023) | yearly_export_2023 |
| 6625 | Yearly Export (2024) | yearly_export_2024 |
| 6627 | Yearly Export (2025) | yearly_export_2025 |
| 6629 | Yearly Export (2026) | yearly_export_2026 |
| 6631 | Yearly Export (2027) | yearly_export_2027 |
| 6633 | Yearly Export (2028) | yearly_export_2028 |
| 12999 | System state | system_state |
| 13000 | Running state | running_state |
| 13001 | Load Adjustment Mode Raw | load_adjustment_mode_selection_raw |
| 13001 | Daily PV generation | daily_pv_generation |
| 13002 | Total PV generation | total_pv_generation |
| 13004 | Daily exported energy from PV | daily_exported_energy_from_PV |
| 13005 | Total exported energy from PV | total_exported_energy_from_pv |
| 13007 | Load power | load_power |
| 13009 | Export power raw | export_power_raw |
| 13010 | Load Adjustment Mode ON/OFF Selection raw | load_adjustment_mode_on_off_selection_raw |
| 13011 | Daily battery charge from PV | daily_battery_charge_from_pv |
| 13012 | Total battery charge from PV | total_battery_charge_from_pv |
| 13016 | Daily direct energy consumption | daily_direct_energy_consumption |
| 13016 | Forced Startup Under Low SoC Standby raw | forced_startup_under_low_soc_standby_raw |
| 13017 | Total direct energy consumption | total_direct_energy_consumption |
| 13019 | Battery voltage | battery_voltage |
| 13020 | Battery current *(we use 5630 instead)* | - |
| 13021 | Battery power *(we use 5213 instead)* | - |
| 13022 | Battery level | battery_level |
| 13023 | Battery state of health | battery_state_of_health |
| 13024 | Battery temperature | battery_temperature |
| 13025 | Daily battery discharge | daily_battery_discharge |
| 13026 | Total battery discharge | total_battery_discharge |
| 13030 | Phase A current | phase_a_current |
| 13031 | Phase B current | phase_b_current |
| 13032 | Phase C current | phase_c_current |
| 13033 | Total active power | total_active_power |
| 13035 | Daily imported energy | daily_imported_energy |
| 13036 | Total imported energy | total_imported_energy |
| 13039 | Daily battery charge | daily_battery_charge |
| 13040 | Total battery charge | total_battery_charge |
| 13044 | Daily exported energy | daily_exported_energy |
| 13045 | Total exported energy | total_exported_energy |
| 13199 | Meter Channel 2 Total Active Power raw (DTSU666-20 only) | meter_channel_2_total_active_power_raw |
| 13201 | Meter Channel 2 Phase A Active Power raw (DTSU666-20 only) | meter_channel_2_phase_a_active_power_raw |
| 13203 | Meter Channel 2 Phase B Active Power raw (DTSU666-20 only) | meter_channel_2_phase_b_active_power_raw |
| 13205 | Meter Channel 2 Phase C Active Power raw (DTSU666-20 only) | meter_channel_2_phase_c_active_power_raw |
| 13249 | Inverter Firmware Information (RT/T/K6 only) | inverter_firmware_info |
| 13264 | Communication Module Firmware Information (RT/T/K6 only) | communication_module_firmware_info |
| 13279 | Battery Firmware Information (RT/T/K6 only) | battery_firmware_info |
| 30229 | Global mpp scan manual raw | global_mpp_scan_manual_raw |
| 13042 | DRM State *(commented out)* | drm_state |
| 13049 | Inverter alarm raw *(commented out)* | inverter_alarm_raw |
| 13051 | Grid-side fault raw *(commented out)* | grid_side_fault_raw |
| 13053 | System fault 1 raw *(commented out)* | system_fault_1_raw |
| 13055 | System fault 2 raw *(commented out)* | system_fault_2_raw |
| 13057 | DC-side fault raw *(commented out)* | dc_side_fault_raw |
| 13059 | Permanent fault raw *(commented out)* | permanent_fault_raw |
| 13061 | BDC-side fault raw *(commented out)* | bdc_side_fault_raw |
| 13063 | BDC-side permanent fault raw *(commented out)* | bdc_side_permanent_fault_raw |
| 13065 | Battery fault raw *(commented out)* | battery_fault_raw |
| 13067 | Battery alarm raw *(commented out)* | battery_alarm_raw |
| 13071 | BMS fault 2 raw *(commented out)* | bms_fault_2_raw |
| 13077 | BMS alarm 2 raw *(commented out)* | bms_alarm_2_raw |
| 13079 | External EMS heartbeat raw *(commented out)* | external_ems_heartbeat_raw |

**Note:**
- **Grid frequency 0.1 Hz (5035)** is commented out: template uses reg 5242 (address 5241) for higher precision 0.01 Hz
- **Fault/alarm registers** (13049–13067): commented out; fault codes per Appendix 4; uncomment for diagnostics
- **DRM State (13042)**, **BMS fault 2/alarm 2 (13075, 13077)**, **External EMS heartbeat (13079)** are commented out
- **Battery current (5630)** and **Battery power (5213)** are used instead of 13020/13021 per Protocol V1.1.11 documentation recommendation
- **Firmware Information** (13249, 13264, 13279) and **Protocol version raw** (4951) are only available on RT/T/K6 models, not on RS/MG models
- Monthly and yearly statistical sensors are only available with LAN connection
- Battery-related sensors are only available when battery is enabled
- Meter Channel 2 sensors (13199-13205) are only available when meter_type is set to "DTSU666-20"
- **iHomeManager is now a separate template** (`sungrow_ihomemanager.yaml`) - do not use meter_type "iHomeManager" with this template

### Controls (Read/Write)

| Address | Name | Unique ID |
|---------|------|-----------|
| 13001 | Load Adjustment Mode | load_adjustment_mode_selection |
| 13010 | Load Adjustment Mode ON/OFF | load_adjustment_mode_on_off_selection |
| 13016 | Forced Startup Under Low SoC Standby | forced_startup_under_low_soc_standby |
| 13049 | EMS Mode Selection | ems_mode_selection |
| 13050 | Battery forced charge discharge cmd raw | battery_forced_charge_discharge_cmd_raw |
| 13051 | Battery forced charge discharge power | battery_forced_charge_discharge_power |
| 13057 | Max SoC | max_soc |
| 13058 | Min SoC | min_soc |
| 13073 | Export Power Limit | export_power_limit |
| 13074 | Backup Mode | backup_mode |
| 13086 | Export Power Limit Mode | export_power_limit_mode |
| 13087 | Export Power Limit Ratio | export_power_limit_ratio |
| 13088 | Active Power Limitation (SHT only) | active_power_limitation |
| 13089 | Active Power Limit Ratio | active_power_limit_ratio |
| 13099 | Reserved SoC for Backup | reserved_soc_for_backup |
| 31221 | Export Power Limit Value Wide Range | export_power_limit_value_wide_range |
| 33046 | Battery Max Charge Power | battery_max_charge_power |
| 33047 | Battery Max Discharge Power | battery_max_discharge_power |
| 33148 | Battery Charging Start Power | battery_charging_start_power |
| 33149 | Battery Discharging Start Power | battery_discharging_start_power |
| 13017 | PV Power Limitation (SHT only) | pv_power_limitation |
| 4999 | System clock: Year *(commented out)* | system_clock_year |
| 5000 | System clock: Month *(commented out)* | system_clock_month |
| 5001 | System clock: Day *(commented out)* | system_clock_day |
| 5002 | System clock: Hour *(commented out)* | system_clock_hour |
| 5003 | System clock: Minute *(commented out)* | system_clock_minute |
| 5004 | System clock: Second *(commented out)* | system_clock_second |
| 13000 | DO Configuration raw *(commented out)* | do_configuration_raw |
| 13002 | Load timing period 1 start hour *(commented out)* | load_timing_period_1_start_hour |
| 13015 | Optimized power of load *(commented out)* | optimized_power_of_load |
| 33041 | Charge Cutoff Voltage raw *(commented out)* | charge_cutoff_voltage_raw |
| 33207 | Forced Charging raw *(commented out)* | forced_charging_raw |
| 33273 | Load Rated Power raw *(commented out)* | load_rated_power_raw |

**Note (Controls):**
- **Active Power Limitation** (13088) and **PV Power Limitation** (13017) are only available on SHT models (SH5T–SH25T), not on RT/RS models
- **System clock (4999–5004)**, **DO Configuration (13000)**, **Load timing (13002–13015)**, **Charge Cutoff Voltage (33041)**, **Forced Charging (33207–33218)**, **Load Rated Power (33273)** are commented out in template; uncomment to enable

### Calculated Sensors

#### Power Calculations
| Address | Name | Unique ID |
|---------|------|-----------|
| - | MPPT1 Power | mppt1_power |
| - | MPPT2 Power | mppt2_power |
| - | MPPT3 Power | mppt3_power |
| - | MPPT4 Power | mppt4_power |
| - | Total MPPT Power | total_mppt_power |
| - | Phase A Power | phase_a_power |
| - | Phase B Power | phase_b_power |
| - | Phase C Power | phase_c_power |
| - | Total Phase Power | total_phase_power |

#### Grid Power Calculations
| Address | Name | Unique ID |
|---------|------|-----------|
| - | Net Grid Power | net_grid_power |
| - | Import Power | import_power |
| - | Export Power | export_power |
| - | Total Load Power | total_load_power |
| - | Meter Active Power | meter_active_power |
| - | Meter Phase A Active Power | meter_phase_a_active_power |
| - | Meter Phase B Active Power | meter_phase_b_active_power |
| - | Meter Phase C Active Power | meter_phase_c_active_power |
| - | Meter Channel 2 Total Active Power (DTSU666-20 only) | meter_channel_2_total_active_power |
| - | Meter Channel 2 Phase A Active Power (DTSU666-20 only) | meter_channel_2_phase_a_active_power |
| - | Meter Channel 2 Phase B Active Power (DTSU666-20 only) | meter_channel_2_phase_b_active_power |
| - | Meter Channel 2 Phase C Active Power (DTSU666-20 only) | meter_channel_2_phase_c_active_power |

#### Battery Power Calculations
| Address | Name | Unique ID |
|---------|------|-----------|
| - | Signed battery power | signed_battery_power |
| - | Battery charging power | battery_charging_power |
| - | Battery discharging power | battery_discharging_power |
| - | Battery level (nominal) | battery_level_nom |
| - | Battery charge (nominal) | battery_charge_nom |
| - | Battery charge | battery_charge |
| - | Battery charge (health-rated) | battery_charge_health_rated |

#### Home Assistant Energy Dashboard Compatible
| Address | Name | Unique ID | Description |
|---------|------|-----------|-------------|
| - | Battery charging power signed | battery_charging_power_signed | Positive when charging (display) |
| - | Battery discharging power signed | battery_discharging_power_signed | Positive when discharging (HA convention) |
| - | Grid power signed | grid_power_signed | Negative=export, Positive=import (HA convention) |
| - | Grid export power signed | grid_export_power_signed | Only export as negative values |
| - | Grid import power signed | grid_import_power_signed | Only import as positive values |

#### PV Analysis & Performance Metrics
| Address | Name | Unique ID | Description |
|---------|------|-----------|-------------|
| - | Self-Consumption Rate | self_consumption_rate | % of PV consumed directly |
| - | Autarky Rate | autarky_rate | % of load supplied by PV/Battery |
| - | Grid Dependency | grid_dependency | % of load depending on grid |
| - | DC to AC Efficiency | dc_to_ac_efficiency | Inverter efficiency (%) |
| - | PV Capacity Factor | pv_capacity_factor | Current power as % of rated capacity |
| - | PV Generation Hours Today | pv_generation_hours_today | Equivalent generation hours |

#### Energy Flow Analysis
| Address | Name | Unique ID | Description |
|---------|------|-----------|-------------|
| - | PV to Load Direct | pv_to_load_direct | PV power directly to load |
| - | PV to Battery | pv_to_battery | PV power charging battery |
| - | Battery to Load | battery_to_load | Battery power to load |
| - | Grid to Load | grid_to_load | Grid power to load |
| - | Net Consumption | net_consumption | Net consumption after PV/Battery |

#### MPPT Performance Analysis
| Address | Name | Unique ID | Description |
|---------|------|-----------|-------------|
| - | MPPT Power Deviation | mppt_power_deviation | Max deviation from average (imbalance indicator) |
| - | MPPT Utilization | mppt_utilization | % of DC power from MPPT trackers |

#### Efficiency Calculations
| Address | Name | Unique ID |
|---------|------|-----------|
| - | Solar to Grid Efficiency | solar_to_grid_efficiency |
| - | Battery to Load Efficiency | battery_to_load_efficiency |
| - | Power Balance | power_balance |

#### Energy Statistics
| Address | Name | Unique ID |
|---------|------|-----------|
| - | Daily consumed energy | daily_consumed_energy |
| - | Total consumed energy | total_consumed_energy |
| - | Monthly PV generation (current) | monthly_pv_generation_current |
| - | Yearly PV generation (current) | yearly_pv_generation_current |
| - | Monthly export (current) | monthly_export_current |
| - | Yearly export (current) | yearly_export_current |

#### Device Information
| Address | Name | Unique ID | Description |
|---------|------|-----------|-------------|
| - | Protocol Version | protocol_version | Formatted from protocol_version_raw (e.g. V1.1.11) |

#### Status Displays
| Address | Name | Unique ID |
|---------|------|-----------|
| - | Inverter Status Display | inverter_status_display |
| - | Grid Status | grid_status |
| - | Battery Status Indicator | battery_status_indicator |
| - | Battery Health Status | battery_health_status |

### Binary Sensors

| Address | Name | Unique ID |
|---------|------|-----------|
| - | PV generating | pv_generating |
| - | PV generating (delay) | pv_generating_delay |
| - | Battery charging | battery_charging |
| - | Battery charging (delay) | battery_charging_delay |
| - | Battery discharging | battery_discharging |
| - | Battery discharging (delay) | battery_discharging_delay |
| - | Exporting power | exporting_power |
| - | Exporting power (delay) | exporting_power_delay |
| - | Importing power | importing_power |
| - | Importing power (delay) | importing_power_delay |
| - | Positive load power | positive_load_power |
| - | Negative load power | negative_load_power |

**Note:** Address "-" indicates that the entity is calculated or derived from other entities and does not have a direct Modbus register address.

## 🚀 Example Configurations

### 🔋 3-phase Hybrid Inverter (SH10RT)
```yaml
phases: 3
mppt_count: 2
battery_enabled: true
firmware_version: "SAPPHIRE-H_03011.95.01"
string_count: 8
connection_type: "LAN"
```

### ⚡ 1-phase String Inverter (SH5K-20)
```yaml
phases: 1
mppt_count: 1
battery_enabled: false
firmware_version: "SAPPHIRE-H_03011.95.01"
string_count: 4
connection_type: "LAN"
```

### 🏠 Residential Inverter (SH6T)
```yaml
phases: 1
mppt_count: 3
battery_enabled: false
firmware_version: "SAPPHIRE-H_03011.95.01"
string_count: 6
connection_type: "WINET"
```

## 🔗 Based on

- **mkaiser Implementation:** https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant
- **100% Register Compatibility:** All registers exactly taken over
- **Extended Functionality:** Dynamic configuration added

## 🙏 Acknowledgments

### 🏆 mkaiser - The Original Pioneer
This template is built upon the **outstanding work of mkaiser** and their comprehensive Sungrow SHx Modbus implementation. Their dedication to reverse-engineering and documenting the Sungrow Modbus protocol has made this integration possible.

**Key Contributions:**
- **Complete Register Mapping:** All 36 Sungrow SHx models documented
- **Reverse Engineering:** Extensive work to understand undocumented registers
- **Community Support:** Ongoing maintenance and support for the Home Assistant community
- **Documentation:** Detailed comments and explanations for each register

### 🌟 Community Contributions
Special thanks to the **photovoltaikforum.com** and **forum.iobroker.net** communities for their collaborative reverse-engineering efforts, particularly for:
- **Undocumented Sensors:** Battery charging/discharging start power registers
- **Firmware Compatibility:** Understanding differences between firmware versions
- **Error Handling:** 0x7FFFFFFF meter error handling
- **Real-world Testing:** Validation across different inverter models

### 🔗 Original Repository
- **GitHub:** https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant
- **License:** Please check the original repository for licensing information
- **Support:** For issues specific to the original implementation, please refer to mkaiser's repository
