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
- **Phase A Voltage**: Voltage on phase A (V)
- **Phase B Voltage**: Voltage on phase B (V)
- **Phase C Voltage**: Voltage on phase C (V)
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

**Version:** 1.0.0
**Last Update:** 2024
**Status:** Stable
**Compatibility:** Compleo eBox Professional Series

## 🔗 Related Documentation

- **[Main README](../../README.md)** - Project overview
- **[GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)** - Additional documentation

## 🙏 Acknowledgments

- **Compleo** for providing Modbus documentation
- **Home Assistant Community** for integration support
- **EV Charging Community** for testing and feedback
