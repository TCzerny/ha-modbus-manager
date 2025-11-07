# Compleo eBox Professional Template

## 📋 Overview

The **Compleo eBox Professional Template** provides complete integration for Compleo eBox Professional EV charging stations. This template supports 3-phase charging control, current monitoring, and comprehensive status tracking.

## 🏭 Supported Models

- **Compleo eBox Professional** - 3-phase wallbox
- **Compleo eBox Professional Plus** - Enhanced version with additional features

## 🔧 Configuration

### Required Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| **Prefix** | String | Required | Unique prefix for all entities |
| **Name** | String | Required | Display name for the device |
| **Firmware Version** | String | 1.3.38 | Firmware version of your device |

### Available Firmware Versions

| Version | Description | Features |
|---------|-------------|----------|
| **1.3.38** | Basic functionality | All core features (current, status, controls) |
| **2.0.35** | Enhanced features | Includes voltage sensors and energy meter reading |

**Important:** Voltage sensors and energy meter reading are only available with firmware version **2.0.35** or higher. If you select firmware version 1.3.38, these sensors will be automatically filtered out.

### Example Configuration

```yaml
# Basic Configuration
prefix: "compleo_ebox"
name: "Compleo eBox Professional"

# Modbus Configuration
host: "192.168.1.100"
port: 502
unit_id: 1
```

## 📊 Features

### ✅ Available Sensors

#### 🔌 Charging Control
- **Charging Status**: Active, paused, stopped, error
- **Charging Current**: Real-time current draw (A)
- **Charging Power**: Active power consumption (W)
- **Charging Energy**: Total energy delivered (kWh)

#### ⚡ Electrical Parameters
- **Phase A Current**: Current on phase A (A)
- **Phase B Current**: Current on phase B (A)
- **Phase C Current**: Current on phase C (A)
- **Phase A Voltage**: Voltage on phase A (V) ⚠️ *Requires firmware 2.0.34+*
- **Phase B Voltage**: Voltage on phase B (V) ⚠️ *Requires firmware 2.0.34+*
- **Phase C Voltage**: Voltage on phase C (V) ⚠️ *Requires firmware 2.0.34+*
- **Energy Meter Reading**: Total energy meter reading (kWh) ⚠️ *Requires firmware 2.0.35+*
- **Grid Frequency**: AC frequency (Hz)

#### 🔋 Battery Information
- **Battery Level**: Connected vehicle battery level (%)
- **Battery Temperature**: Battery temperature (°C)
- **Remaining Time**: Estimated time to full charge (min)

#### 📊 Energy Statistics
- **Daily Energy**: Energy delivered today (kWh)
- **Total Energy**: Total energy delivered (kWh)
- **Session Energy**: Current session energy (kWh)

#### 🛡️ Safety & Status
- **Error Status**: Current error state
- **Temperature**: Wallbox temperature (°C)
- **Communication Status**: Modbus connection status

### 🔧 Controls

#### ⚡ Charging Control
- **Start Charging**: Initiate charging session
- **Stop Charging**: Stop current charging session
- **Pause Charging**: Pause charging temporarily

#### 🔌 Current Settings
- **Max Current**: Set maximum charging current (A)
- **Fallback Current**: Set fallback current limit (A)
- **Dynamic Current**: Enable/disable dynamic current adjustment

#### ⚙️ Operating Modes
- **Operating Mode**: Auto, manual, scheduled
- **Load Management**: Enable/disable load balancing
- **Grid Protection**: Enable/disable grid protection

### 📈 Calculated Sensors

#### ⚡ Power Calculations
- **Total Power**: Sum of all phase powers (W)
- **Power Factor**: Overall power factor
- **Efficiency**: Charging efficiency (%)

#### 🔋 Battery Calculations
- **Charging Rate**: Energy per hour (kWh/h)
- **Time to Full**: Estimated completion time
- **Cost Calculation**: Charging cost based on tariff

## 📋 Complete Entity Reference

This section contains all entities that will be created by this template, including Modbus register addresses and unique IDs.

### Sensors (Read-only)

| Address | Name | Unique ID | Firmware Requirement |
|---------|------|-----------|----------------------|
| 0 | ID | id | All versions |
| 25 | Serial Number | serial_number | All versions |
| 50 | Active Protocol | active_protocol | All versions |
| 100 | Manufacturer | manufacturer | All versions |
| 200 | Firmware | firmware | All versions |
| 275 | Status | status | All versions |
| 300 | Cable Status | cable_status | All versions |
| 301 | Voltage Phase 1 | voltage_phase_1 | **2.0.35+** |
| 303 | Voltage Phase 2 | voltage_phase_2 | **2.0.35+** |
| 305 | Voltage Phase 3 | voltage_phase_3 | **2.0.35+** |
| 307 | Energy Meter Reading | energy_meter_reading | **2.0.35+** |
| 1000 | Actual Max Current Phase 1 | actual_max_current_phase_1 | All versions |
| 1002 | Actual Max Current Phase 2 | actual_max_current_phase_2 | All versions |
| 1004 | Actual Max Current Phase 3 | actual_max_current_phase_3 | All versions |
| 1006 | Current Phase 1 | current_phase_1 | All versions |
| 1008 | Current Phase 2 | current_phase_2 | All versions |
| 1010 | Current Phase 3 | current_phase_3 | All versions |

### Controls (Read/Write)

| Address | Name | Unique ID |
|---------|------|-----------|
| 1012 | Max Current Phase 1 | max_current_phase_1 |
| 1014 | Max Current Phase 2 | max_current_phase_2 |
| 1016 | Max Current Phase 3 | max_current_phase_3 |

### Calculated Sensors

| Address | Name | Unique ID | Firmware Requirement |
|---------|------|-----------|----------------------|
| - | Total Current | total_current | All versions |
| - | Charging Power | charging_power | All versions |
| - | Max Total Current | max_total_current | All versions |
| - | Max Charging Power | max_charging_power | All versions |
| - | Charging Efficiency | charging_efficiency | All versions |
| - | Average Voltage | average_voltage | **2.0.34+** |
| - | Voltage Imbalance | voltage_imbalance | **2.0.34+** |

### Binary Sensors

| Address | Name | Unique ID |
|---------|------|-----------|
| - | Charging Active | charging_active |
| - | Cable Connected | cable_connected |

**Note:** Address "-" indicates that the entity is calculated or derived from other entities and does not have a direct Modbus register address.

## 🔧 Installation

### 1. Template Selection
1. Open Home Assistant
2. Go to **Settings** → **Devices & Services**
3. Click **Add Integration**
4. Search for **Modbus Manager**
5. Select **Compleo eBox Professional** template

### 2. Configuration
1. Enter device **prefix** (e.g., "compleo_ebox")
2. Enter device **name** (e.g., "Compleo eBox Professional")
3. Configure **Modbus connection**:
   - Host: IP address of wallbox
   - Port: 502 (default)
   - Unit ID: 1 (default)

### 3. Verification
1. Check all sensors are created
2. Verify charging control works
3. Test current limit adjustments

## 🚨 Troubleshooting

### Common Issues

#### Connection Problems
- **Modbus Timeout**: Check network connectivity
- **Wrong Unit ID**: Verify Modbus unit ID
- **Port Blocked**: Ensure port 502 is open

#### Sensor Issues
- **No Data**: Check Modbus register addresses
- **Wrong Values**: Verify data type and scaling
- **Missing Sensors**: Check template validation

### Debug Steps

1. **Check Modbus Connection**:
   ```bash
   # Test Modbus connectivity
   telnet [IP_ADDRESS] 502
   ```

2. **Verify Register Access**:
   ```bash
   # Test register reading
   modbus read [IP_ADDRESS] 502 1 40001 10
   ```

3. **Check Home Assistant Logs**:
   ```yaml
   # Enable debug logging
   logger:
     default: info
     custom_components.modbus_manager: debug
   ```

## 📋 Version

**Template Version:** 3.0.0
**Last Update:** 2025-11-07
**Status:** Stable
**Compatibility:** Compleo eBox Professional Series

## 📝 Changelog

### Version 3.0.0 (2025-11-07)

#### 🔧 Changed
- **Firmware Version Filtering**: Voltage sensors and current meter reading now require firmware version 2.0.34 or higher
  - Voltage Phase 1, 2, 3 sensors: Only available with firmware 2.0.34+
  - Energy Meter Reading sensor: Only available with firmware 2.0.35+
  - Average Voltage calculated sensor: Only available with firmware 2.0.34+
  - Voltage Imbalance calculated sensor: Only available with firmware 2.0.34+
  - Sensors are automatically filtered based on selected firmware version during setup

#### 📚 Documentation
- Updated entity reference tables with firmware requirements
- Added firmware version selection information
- Clarified which sensors require which firmware versions

## 🔗 Related Documentation

- **[Main README](../../README.md)** - Project overview
- **[GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)** - Additional documentation

## 🙏 Acknowledgments

- **Compleo** for providing Modbus documentation
- **Home Assistant Community** for integration support
- **EV Charging Community** for testing and feedback
