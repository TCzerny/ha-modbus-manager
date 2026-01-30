# Sungrow SG Dynamic Template

## 📋 Overview

The **Sungrow SG Dynamic Template** is a complete, dynamically configurable template for Sungrow SG series residential and commercial PV grid-connected inverters. Based on Communication Protocol V1.1.53, it supports RS, RT, HX, KTL, KTL-MT, HV/BF, and CX series inverters.

## 🏭 Supported Inverter Models

The template supports the following Sungrow SG series models:

### ⚡ RS Series (Single Phase)
- **SG3.0RS, SG4.0RS, SG5.0RS, SG6.0RS, SG8.0RS, SG10RS** - Residential Single Phase Models

### 🔌 RT Series (Three Phase)
- **SG3.0RT, SG4.0RT, SG5.0RT, SG6.0RT, SG7.0RT, SG8.0RT, SG10RT, SG12RT, SG15RT, SG20RT** - Residential Three Phase Models

### 🏢 KTL Series (Commercial)
- **SG10KTL, SG12KTL, SG15KTL, SG20KTL, SG30KTL, SG36KTL, SG40KTL, SG60KTL, SG80KTL** - Commercial Models

### 🔧 KTL-M Series (Modular Commercial)
- **SG30KTL-M, SG40KTL-M, SG50KTL-M, SG60KTL-M** - Modular Commercial Models

### ⚡ CX Series (Commercial)
- **SG30CX, SG33CX, SG40CX, SG50CX, SG75CX, SG100CX, SG110CX** - Commercial CX Series

### 🚀 HX Series (High Power)
- **SG250HX, SG320HX, SG350HX** - High Power Commercial Models

## ⚙️ Dynamic Configuration

### 📊 Configurable Parameters

| Parameter | Options | Default | Description |
|-----------|----------|---------|-------------|
| **Model** | See list above | Required | Inverter model selection |
| **Phases** | 1, 3 | Auto | Number of phases (auto-detected from model) |
| **MPPT** | 1-12 | Auto | Number of MPPT trackers (auto-detected from model) |
| **Strings** | 1-24 | Auto | Number of PV strings (auto-detected from model) |
| **Firmware** | String | "SAPPHIRE-H_xxx" | Firmware version |
| **Connection** | LAN, WINET | LAN | Connection type |

### 🔄 Automatic Filtering

#### **Phase Filtering**
- **1-phase:** Only Phase A registers are loaded
- **3-phase:** All Phase A, B, C registers are loaded

#### **MPPT Filtering**
- Automatically filters based on model configuration
- Supports 1-12 MPPT trackers depending on model

#### **String Filtering**
- Automatically filters string current sensors based on model

#### **Connection Filtering**
- **LAN:** Full access to all registers
- **WINET:** Limited access (some registers not available)

#### **Model-Specific Register Filtering**
Some registers are only available on specific model families. The template now
filters these entities automatically using `selected_model` (limited to the
models listed in `valid_models`).

- **RT/CX/HX only:** `work_status_1`, `work_status_2`, `active_power_overload`,
  `night_svg_switch`, `pid_recovery`
- **HX only:** `anti_pid`, `full_day_pid_suppression`
- **HX (SG320HX/SG350HX):** `quick_grid_dispatch_mode`,
  `swift_grid_dispatch_mode`
- **KTL/KTL-M/RT/CX/HX only:** `total_apparent_power`

## 📡 Available Sensors

### 🔧 Basic Inverter Data
- **Inverter Serial** - Serial number
- **Device Type Code** - Automatic model detection
- **Inverter Temperature** - Inverter temperature
- **Work State** - System work state
- **Running State** - System running state

### ⚡ MPPT Data (1-12 Trackers)
- **MPPT Voltage/Current** - Voltage and current per tracker
- **MPPT Power** - Calculated power per tracker
- **Total DC Power** - Total DC power

### 🔌 Phase Data (1 or 3 Phases)
- **Phase Voltage/Current** - Voltage and current per phase
- **Phase Power** - Calculated power per phase
- **Total Active Power** - Total AC power

### 📊 Energy Data
- **Daily/Total PV Generation** - Daily/Total PV generation
- **Daily/Total Export** - Daily/Total export
- **Daily/Total Import** - Daily/Total import
- **Monthly PV Generation** - Monthly generation

### 🎛️ Meter Data (Grid Monitoring)
- **Meter Active Power** - Grid active power
- **Grid Frequency** - Grid frequency

### 📈 String Current Data
- **String Current (1-8)** - Individual string currents

## 🎛️ Controls (Write Access)

### 🔧 System Control
- **Start/Stop Control** - Start or stop inverter
- **Power Limitation** - Power limitation settings
- **Export Power Limitation** - Export power limit

### ⚡ Grid Control
- **Reactive Power Adjustment** - Reactive power control
- **Power Factor Setting** - Power factor control
- **Grid Dispatch Mode** - Grid dispatch settings

### 🔋 Battery Control (if supported)
- Battery control features depend on model

## 🧮 Calculated Sensors

### ⚡ Power Calculations
- **MPPT Power** - Calculated power per MPPT
- **Total MPPT Power** - Total MPPT power
- **Phase Power** - Calculated power per phase

### 🔄 Grid Power Calculations
- **Grid Import Power** - Grid import (positive)
- **Grid Export Power** - Grid export (negative)

### 📊 Efficiency Calculations
- **Solar to Grid Efficiency** - PV to grid efficiency
- **Power Balance** - System power balance

## 📋 Complete Entity Reference

This section contains all entities that will be created by this template, including Modbus register addresses and unique IDs. Entities are automatically filtered based on your device configuration (model, phases, MPPT count, connection type).

### Sensors (Read-only)

| Address | Name | Unique ID |
|---------|------|-----------|
| 4989 | Sungrow inverter serial | inverter_serial |
| 4999 | Sungrow device type code | sungrow_device_type_code |
| 5001 | Output type | output_type |
| 5002 | Daily PV generation | daily_pv_generation |
| 5003 | Total PV generation | total_pv_generation |
| 5005 | Total running time | total_running_time |
| 5007 | Inverter temperature | inverter_temperature |
| 5008 | Total apparent power | total_apparent_power |
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
| 5021 | Phase A current | phase_a_current |
| 5022 | Phase B current | phase_b_current |
| 5023 | Phase C current | phase_c_current |
| 5030 | Total active power | total_active_power |
| 5032 | Reactive power | reactive_power |
| 5034 | Load Adjustment Mode | load_adjustment_mode_selection_raw |
| 5035 | Grid frequency | grid_frequency |
| 5037 | Work state | work_state |
| 5080 | Running State | running_state |
| 5082 | Meter active power raw | meter_active_power_raw |
| 5090 | Load Power | load_power |
| 5092 | Daily exported energy | daily_exported_energy |
| 5094 | Total exported energy | total_exported_energy |
| 5096 | Daily Imported Energy | daily_imported_energy |
| 5098 | Total Imported Energy | total_imported_energy |
| 5100 | Daily Direct Energy Consumption | daily_direct_energy_consumption |
| 5102 | Total Direct Energy Consumption | total_direct_energy_consumption |
| 5112 | Daily running time | daily_running_time |
| 5114 | MPPT4 voltage | mppt4_voltage |
| 5115 | MPPT4 current | mppt4_current |
| 5116 | MPPT5 voltage | mppt5_voltage |
| 5117 | MPPT5 current | mppt5_current |
| 5118 | MPPT6 voltage | mppt6_voltage |
| 5119 | MPPT6 current | mppt6_current |
| 5127 | Monthly PV generation | monthly_pv_generation |
| 5120 | MPPT7 voltage | mppt7_voltage |
| 5121 | MPPT7 current | mppt7_current |
| 5122 | MPPT8 voltage | mppt8_voltage |
| 5123 | MPPT8 current | mppt8_current |
| 5129 | MPPT9 voltage | mppt9_voltage |
| 5130 | MPPT9 current | mppt9_current |
| 5131 | MPPT10 voltage | mppt10_voltage |
| 5132 | MPPT10 current | mppt10_current |
| 5133 | MPPT11 voltage | mppt11_voltage |
| 5134 | MPPT11 current | mppt11_current |
| 5135 | MPPT12 voltage | mppt12_voltage |
| 5136 | MPPT12 current | mppt12_current |
| 5139 | Work status 1 | work_status_1 |
| 5140 | Work status 2 | work_status_2 |
| 5142 | Heart beat | heart_beat |
| 5143 | Total PV Generation (high precision) | total_pv_generation_high_precision |
| 5145 | Negative voltage to ground | negative_voltage_ground |
| 5146 | Bus voltage | bus_voltage |
| 5147 | Grid frequency (high precision) | grid_frequency_hp |
| 5149 | PID work state | pid_work_state |
| 5150 | PID alarm code | pid_alarm_code |
| 7012 | String 1 current | string_1_current |
| 7013 | String 2 current | string_2_current |
| 7014 | String 3 current | string_3_current |
| 7015 | String 4 current | string_4_current |
| 7016 | String 5 current | string_5_current |
| 7017 | String 6 current | string_6_current |
| 7018 | String 7 current | string_7_current |
| 7019 | String 8 current | string_8_current |

**Note:** MPPT and phase sensors are automatically filtered based on model configuration.

### Controls (Read/Write)

| Address | Name | Unique ID |
|---------|------|-----------|
| 5005 | Start/Stop Control | start_stop_control |
| 5006 | Power Limitation Switch | power_limitation_switch |
| 5007 | Power Limitation Setting | power_limitation_setting |
| 5009 | Export Power Limitation | export_power_limitation |
| 5010 | Export Power Limitation Value | export_power_limitation_value |
| 5011 | Current Transformer Output Current | ct_output_current |
| 5012 | Current Transformer Range | ct_range |
| 5013 | Current Transformer Type | ct_type |
| 5014 | Export Power Limitation Percentage | export_power_limitation_percentage |
| 5018 | Power Factor Setting | power_factor_setting |
| 5019 | Active Power Overload | active_power_overload |
| 5034 | Night SVG Switch | night_svg_switch |
| 5035 | Reactive power adjustment mode | reactive_power_adjustment_mode |
| 5036 | Reactive power percentage setting | reactive_power_percentage_setting |
| 5038 | Power limitation adjustment | power_limitation_adjustment |
| 5039 | Reactive power adjustment | reactive_power_adjustment |
| 5040 | PID Recovery | pid_recovery |
| 5041 | Anti-PID | anti_pid |
| 5042 | Full-Day PID Suppression | full_day_pid_suppression |
| 32568 | Quick grid dispatch mode | quick_grid_dispatch_mode |
| 32569 | Swift grid dispatch mode | swift_grid_dispatch_mode |

### Calculated Sensors

| Address | Name | Unique ID |
|---------|------|-----------|
| - | MPPT1 Power | mppt1_power |
| - | MPPT2 Power | mppt2_power |
| - | MPPT3 Power | mppt3_power |
| - | MPPT4 Power | mppt4_power |
| - | MPPT5 Power | mppt5_power |
| - | MPPT6 Power | mppt6_power |
| - | MPPT7 Power | mppt7_power |
| - | MPPT8 Power | mppt8_power |
| - | MPPT9 Power | mppt9_power |
| - | MPPT10 Power | mppt10_power |
| - | MPPT11 Power | mppt11_power |
| - | MPPT12 Power | mppt12_power |
| - | Total MPPT Power | total_mppt_power |
| - | Import Power | import_power |
| - | Export Power | export_power |
| - | Total Load Power | total_load_power |
| - | Solar to Grid Efficiency | solar_to_grid_efficiency |
| - | Battery to Load Efficiency | battery_to_load_efficiency |
| - | Power Balance | power_balance |
| - | Phase A Power | phase_a_power |
| - | Phase B Power | phase_b_power |
| - | Phase C Power | phase_c_power |
| - | Meter Active Power | meter_active_power |
| - | Daily consumed energy | daily_consumed_energy |
| - | Total consumed energy | total_consumed_energy |
| - | Inverter Status Display | inverter_status_display |
| - | Grid Status | grid_status |

### Binary Sensors

| Address | Name | Unique ID |
|---------|------|-----------|
| - | PV generating | pv_generating |
| - | PV generating (delay) | pv_generating_delay |
| - | Exporting power | exporting_power |
| - | Exporting power (delay) | exporting_power_delay |
| - | Importing power | importing_power |
| - | Importing power (delay) | importing_power_delay |
| - | Positive load power | positive_load_power |
| - | Negative load power | negative_load_power |

**Note:** Address "-" indicates that the entity is calculated or derived from other entities and does not have a direct Modbus register address.

## 🚀 Example Configurations

### ⚡ Single Phase Residential (SG5.0RS)
```yaml
model: "SG5.0RS"
phases: 1
mppt_count: 2
connection_type: "LAN"
```

### 🔌 Three Phase Commercial (SG30KTL)
```yaml
model: "SG30KTL"
phases: 3
mppt_count: 2
string_count: 4
connection_type: "LAN"
```

## 📝 Special Features

### 🔄 Automatic Model Detection
The template automatically detects the inverter model and adjusts available registers accordingly.

### 🔌 Connection Type Support
- **LAN:** Full access to all registers
- **WINET:** Limited access (some registers not available)

### 📊 Error Handling
- **0x7FFFFFFF Handling:** Automatic handling of meter errors
- **Unavailable State:** Graceful handling of unavailable sensors

## 🔗 Based on

- **Sungrow Communication Protocol V1.1.53** - Official Sungrow Modbus protocol documentation
- **Complete Register Mapping** - All registers from protocol documentation

## 📋 Version

**Version:** 1.0.0
**Last Update:** 2025
**Compatibility:** All Sungrow SG Series Models
