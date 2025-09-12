# HA-Modbus-Manager Documentation

## 📚 Template Documentation

This directory contains comprehensive documentation for all available device templates in the HA-Modbus-Manager project.

## 🏭 Available Templates

### 🔋 Solar Inverters

#### [Sungrow SHx Dynamic](README_sungrow_shx_dynamic.md)
- **Status**: ✅ Recommended (v1.0.0)
- **Models**: All 36 SHx models with dynamic configuration
- **Features**: Automatic filtering, firmware compatibility, LAN/WINET support
- **Firmware**: SAPPHIRE-H_03011.95.01

#### [Sungrow SHx (Legacy)](README_sungrow_shx.md)
- **Status**: ⚠️ Legacy (Use Dynamic Template Instead)
- **Models**: All 36 SHx models with manual configuration
- **Features**: Complete register mapping, manual filtering required

#### [SunSpec Standard Config](README_sunspec_standard_config.md)
- **Status**: ✅ Universal Template
- **Compatibility**: All SunSpec-compliant devices
- **Manufacturers**: SMA, Fronius, Huawei, SolarEdge, and more
- **Features**: Automatic sensor generation, universal compatibility

### 🔌 EV Chargers

#### [Compleo eBox Professional](README_compleo_ebox_professional.md)
- **Status**: ✅ Stable (v1.0.0)
- **Models**: Compleo eBox Professional series
- **Features**: 3-phase charging control, current monitoring, comprehensive status

## 📋 Template Comparison

| Template | Type | Dynamic Config | Firmware Support | Connection Filtering | Status |
|----------|------|----------------|-------------------|---------------------|---------|
| **Sungrow SHx Dynamic** | Solar | ✅ Yes | ✅ Yes | ✅ Yes | 🟢 Recommended |
| **Sungrow SHx (Legacy)** | Solar | ❌ No | ❌ No | ❌ No | 🟡 Legacy |
| **SunSpec Standard Config** | Universal | ✅ Yes | ✅ Yes | ❌ No | 🟢 Universal |
| **Compleo eBox Professional** | EV Charger | ❌ No | ❌ No | ❌ No | 🟢 Stable |

## 🔧 Quick Start Guide

### 1. Choose Your Template

#### For Sungrow Inverters
- **New Installations**: Use [Sungrow SHx Dynamic](README_sungrow_shx_dynamic.md)
- **Existing Installations**: Consider migrating to dynamic template

#### For SunSpec Devices
- **Any SunSpec Device**: Use [SunSpec Standard Config](README_sunspec_standard_config.md)
- **Universal Compatibility**: Works with all SunSpec-compliant manufacturers

#### For EV Chargers
- **Compleo eBox**: Use [Compleo eBox Professional](README_compleo_ebox_professional.md)

### 2. Installation Steps

1. **Select Template**: Choose appropriate template from list above
2. **Read Documentation**: Review template-specific documentation
3. **Configure Parameters**: Set required parameters (prefix, addresses, etc.)
4. **Test Integration**: Verify all sensors and controls work correctly

### 3. Configuration Examples

#### Sungrow SHx Dynamic
```yaml
prefix: "sungrow_inverter"
phases: 3
mppt_count: 2
battery_enabled: true
firmware_version: "SAPPHIRE-H_03011.95.01"
string_count: 8
connection_type: "LAN"
```

#### SunSpec Standard Config
```yaml
prefix: "sma_inverter"
common_model_address: 40001
inverter_model_address: 40069
storage_model_address: 40187
meter_model_address: 40277
```

#### Compleo eBox Professional
```yaml
prefix: "compleo_ebox"
name: "Compleo eBox Professional"
```

## 🚨 Troubleshooting

### Common Issues

#### No Data from Sensors
1. **Check Modbus Connection**: Verify network connectivity
2. **Verify Addresses**: Confirm register addresses are correct
3. **Check Device Manual**: Ensure addresses match device documentation

#### Wrong Values
1. **Data Type**: Verify data type configuration
2. **Scaling**: Check scale and precision settings
3. **Byte Order**: Confirm byte order (big/little endian)

#### Missing Sensors
1. **Template Support**: Ensure device is supported by template
2. **Configuration**: Check if optional features are enabled
3. **Firmware**: Verify firmware version compatibility

### Debug Steps

1. **Enable Debug Logging**:
   ```yaml
   logger:
     default: info
     custom_components.modbus_manager: debug
   ```

2. **Test Modbus Connection**:
   ```bash
   telnet [DEVICE_IP] 502
   ```

3. **Check Home Assistant Logs**:
   ```bash
   tail -f /config/home-assistant.log
   ```

## 📊 Features Overview

### Dynamic Configuration
- **Parameter Selection**: UI-driven configuration
- **Automatic Filtering**: Register filtering based on device type
- **Firmware Compatibility**: Automatic sensor parameter adjustment
- **Connection Support**: LAN/WINET automatic filtering

### Universal Templates
- **SunSpec Standard**: Works with any SunSpec-compliant device
- **Automatic Generation**: Sensors generated from standard definition
- **Flexible Addressing**: User-provided model addresses

### Comprehensive Monitoring
- **Real-time Data**: Live sensor updates
- **Calculated Sensors**: Efficiency and power calculations
- **Control Integration**: Full device control capabilities
- **Status Monitoring**: Device status and error reporting

## 🔗 Related Resources

- **[Main Project README](../README.md)** - Project overview and features
- **[GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)** - Additional documentation
- **[GitHub Issues](https://github.com/TCzerny/ha-modbus-manager/issues)** - Bug reports and feature requests
- **[GitHub Discussions](https://github.com/TCzerny/ha-modbus-manager/discussions)** - Community support

## 🙏 Acknowledgments

- **[mkaiser](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant)** for Sungrow SHx implementation
- **photovoltaikforum.com** and **forum.iobroker.net** communities for reverse-engineering
- **SunSpec Alliance** for the Modbus standard
- **Device Manufacturers** for Modbus documentation
- **Home Assistant Community** for platform and integration support

---

**Last Updated**: January 2025
**Documentation Version**: 1.0.0
