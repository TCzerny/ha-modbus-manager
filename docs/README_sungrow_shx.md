# Sungrow SHx Template (Legacy)

## 📋 Overview

The **Sungrow SHx Template** is the original, static template for Sungrow SHx inverters. This template contains all available registers but requires manual configuration for different device types.

## 🏭 Supported Inverter Models

This template supports all 36 Sungrow SHx models:

### 🔋 Hybrid Inverters
- **SHxK6 Series**: SH3K6, SH4K6, SH5K6
- **SHxK-20/V13 Series**: SH5K-20, SH5K-V13
- **SHxK-30 Series**: SH3K6-30, SH4K6-30, SH5K-30
- **SHx.0RS Series**: SH3.0RS, SH3.6RS, SH4.0RS, SH5.0RS, SH6.0RS, SH8.0RS, SH10RS
- **SHx.0RT Series**: SH5.0RT, SH6.0RT, SH8.0RT, SH10RT
- **SHx.0RT-20 Series**: SH5.0RT-20, SH6.0RT-20, SH8.0RT-20, SH10RT-20
- **SHx.0RT-V112 Series**: SH5.0RT-V112, SH6.0RT-V112, SH8.0RT-V112, SH10RT-V112
- **SHx.0RT-V122 Series**: SH5.0RT-V122, SH6.0RT-V122, SH8.0RT-V122, SH10RT-V122

### ⚡ String Inverters
- **SHxT Series**: SH5T, SH6T, SH8T, SH10T, SH12T, SH15T, SH20T, SH25T

### 🏠 Residential Inverters
- **MGxRL Series**: MG5RL, MG6RL

## 🔧 Configuration

### Manual Configuration Required

Unlike the dynamic template, this template requires manual configuration:

1. **Phase Configuration**: Manually comment/uncomment phase B and C sensors
2. **MPPT Configuration**: Manually comment/uncomment MPPT3 sensors
3. **Battery Configuration**: Manually comment/uncomment battery sensors
4. **Connection Type**: No automatic filtering for LAN/WINET

### Example Manual Configuration

#### For 1-phase inverter without battery:
```yaml
# Comment out phase B and C sensors
# - name: Phase B voltage
#   unique_id: phase_b_voltage
#   ...

# Comment out battery sensors
# - name: Battery voltage
#   unique_id: battery_voltage
#   ...
```

#### For 3-phase hybrid inverter:
```yaml
# Keep all phase sensors active
- name: Phase A voltage
  unique_id: phase_a_voltage
  ...

- name: Phase B voltage
  unique_id: phase_b_voltage
  ...

- name: Phase C voltage
  unique_id: phase_c_voltage
  ...

# Keep all battery sensors active
- name: Battery voltage
  unique_id: battery_voltage
  ...
```

## 📊 Features

### ✅ Available Sensors
- **Device Information**: Serial number, device type code
- **PV Generation**: Daily/total generation, MPPT tracking
- **Grid Interaction**: Import/export power, phase monitoring
- **Battery Management**: SOC, charging/discharging, temperature
- **System Status**: Operating modes, error states
- **Energy Statistics**: Monthly/yearly generation and export

### 🔧 Controls
- **EMS Mode Selection**: Self-consumption, forced, backup, emergency
- **Load Adjustment Mode**: Timing, ON/OFF, power optimization
- **Export Power Limit**: Configurable export limits
- **Battery Settings**: Min/Max SOC, charging/discharging power
- **Backup Mode**: Enable/disable backup functionality

### 📈 Calculated Sensors
- **MPPT Power Calculations**: Individual and total MPPT power
- **Grid Power Calculations**: Import/export power separation
- **Battery Power Calculations**: Charging/discharging power
- **Efficiency Calculations**: Solar to grid, battery to load
- **Power Balance**: System power balance calculations

## 🚨 Limitations

### Manual Configuration Required
- No automatic filtering based on device type
- Manual commenting/uncommenting of sensors
- Risk of configuration errors
- Time-consuming setup process

### No Dynamic Features
- No firmware version compatibility
- No automatic connection type filtering
- No dynamic parameter adjustment
- Static template structure

## 🔄 Migration to Dynamic Template

### Recommended Migration Path

For new installations, use the **[Sungrow SHx Dynamic Template](README_sungrow_shx_dynamic.md)** instead:

1. **Automatic Configuration**: Dynamic parameter selection
2. **Firmware Compatibility**: Automatic sensor parameter adjustment
3. **Connection Filtering**: LAN/WINET automatic filtering
4. **Error Prevention**: No manual configuration required

### Migration Steps

1. **Backup Current Configuration**: Export current settings
2. **Install Dynamic Template**: Use `sungrow_shx_dynamic.yaml`
3. **Configure Parameters**: Select device parameters in UI
4. **Verify Functionality**: Test all sensors and controls
5. **Remove Legacy Template**: Delete old configuration

## 📋 Version

**Version:** 1.0.0  
**Last Update:** 2024  
**Status:** Legacy (Use Dynamic Template Instead)  
**Compatibility:** All 36 Sungrow SHx Models

## 🔗 Related Documentation

- **[Sungrow SHx Dynamic Template](README_sungrow_shx_dynamic.md)** - Recommended dynamic template
- **[Main README](../../README.md)** - Project overview
- **[GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)** - Additional documentation

## 🙏 Acknowledgments

- **[mkaiser](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant)** for the original Modbus implementation
- **photovoltaikforum.com** and **forum.iobroker.net** communities for reverse-engineering efforts
