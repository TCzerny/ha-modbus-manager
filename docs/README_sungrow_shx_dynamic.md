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
| **Phases** | 1, 3 | 1 | Number of phases (1-phase or 3-phase) |
| **MPPT** | 1, 2, 3 | 1 | Number of MPPT trackers |
| **Battery** | true, false | false | Battery support enabled |
| **Firmware** | String | "SAPPHIRE-H_03011.95.01" | Firmware version (e.g. "SAPPHIRE-H_03011.95.01") |
| **Strings** | 1-24 | 1 | Number of PV strings |
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
- **Battery disabled:** No battery registers
- **Battery enabled:** All battery registers + backup power

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
- **Meter Active Power** - Grid active power
- **Meter Phase Power** - Phase-specific power
- **Meter Voltage/Current** - Grid voltage and current
- **Grid Frequency** - Grid frequency

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

## 🧮 Calculated Sensors

### ⚡ Power Calculations
- **MPPT Power** - Calculated power per MPPT
- **Total MPPT Power** - Total MPPT power
- **Phase Power** - Calculated power per phase
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
- **Power Balance** - System power balance

### 🛡️ Meter Power Handling
- **Meter Active Power** - With 0x7FFFFFFF error handling
- **Meter Phase Power** - Phase-specific with error handling

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

## 📝 Special Features

### 🔄 Automatic Model Detection
The template automatically detects the inverter model via `dev_code` and adjusts available registers accordingly.

### 🛡️ Firmware Compatibility
- **Firmware v1.x:** Standard data formats
- **Firmware v2.x:** Signed values for battery current/power
- **Firmware v2.1+:** Higher precision for certain sensors

### 🔌 Connection Type Support
- **LAN:** Full access to all registers
- **WINET:** Limited access (no statistical data)

### 📊 Error Handling
- **0x7FFFFFFF Handling:** Automatic handling of meter errors
- **Unavailable State:** Graceful handling of unavailable sensors

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

## 📋 Version

**Version:** 1.0.0  
**Last Update:** 2025  
**Compatibility:** All 36 Sungrow SHx Models
