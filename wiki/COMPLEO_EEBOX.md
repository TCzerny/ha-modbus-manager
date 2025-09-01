# Compleo eBox Professional Template

## 📋 Overview

The Compleo eBox Professional template provides comprehensive support for the Compleo eBox Professional EV charger (also known as Innogy eBox). This template includes all sensors, controls, and calculated values needed for monitoring and controlling EV charging.

## 🚗 Device Information

- **Manufacturer**: Compleo
- **Model**: eBox Professional
- **Type**: EV Charger
- **Protocol**: Modbus TCP
- **Features**: 3-phase charging, current control, fallback settings

## 🔧 Template Features

### 📊 Sensors

#### Device Information
- **eBox ID**: Device identification string
- **eBox Serial Number**: Device serial number
- **eBox Active Protocol**: Active communication protocol
- **eBox Manufacturer**: Manufacturer information
- **eBox Firmware**: Firmware version

#### Charging Status
- **eBox Status**: Current charging status
- **eBox Cable Status**: Cable connection status
- **eBox Charging Active**: Binary sensor for active charging
- **eBox Cable Connected**: Binary sensor for cable connection

#### Current Measurements
- **eBox Current Phase 1/2/3**: Real-time current per phase
- **eBox Total Current**: Calculated total current across all phases
- **eBox Actual Max Current Phase 1/2/3**: Current maximum current settings

#### Power Calculations
- **eBox Charging Power**: Calculated charging power (W)
- **eBox Max Charging Power**: Maximum possible charging power
- **eBox Charging Efficiency**: Current efficiency percentage

### 🎛️ Controls

#### Current Settings
- **eBox Max Current Phase 1/2/3**: Set maximum current per phase (0-16A)
- **eBox Fallback Max Current Phase 1/2/3**: Set fallback current per phase
- **eBox Remaining Time Before Fallback**: Time until fallback activation

#### Number Controls
- **eBox Set Max Current**: Unified control for setting current on all phases

## 📋 Register Mapping

### Input Registers (Read-Only)

| Register | Name | Data Type | Description |
|----------|------|-----------|-------------|
| 0 | eBox ID | String(25) | Device identification |
| 25 | eBox Serial Number | String(25) | Serial number |
| 50 | eBox Active Protocol | String(25) | Active protocol |
| 100 | eBox Manufacturer | String(25) | Manufacturer info |
| 200 | eBox Firmware | String(25) | Firmware version |
| 275 | eBox Status | String(25) | Charging status |
| 300 | eBox Cable Status | uint16 | Cable connection status |
| 1000 | Actual Max Current Phase 1 | float32 | Current max current setting |
| 1002 | Actual Max Current Phase 2 | float32 | Current max current setting |
| 1004 | Actual Max Current Phase 3 | float32 | Current max current setting |
| 1006 | Current Phase 1 | float32 | Real-time current |
| 1008 | Current Phase 2 | float32 | Real-time current |
| 1010 | Current Phase 3 | float32 | Real-time current |

### Holding Registers (Read/Write)

| Register | Name | Data Type | Description |
|----------|------|-----------|-------------|
| 1012 | Max Current Phase 1 | float32 | Set maximum current |
| 1014 | Max Current Phase 2 | float32 | Set maximum current |
| 1016 | Max Current Phase 3 | float32 | Set maximum current |
| 1018 | Fallback Max Current Phase 1 | float32 | Set fallback current |
| 1020 | Fallback Max Current Phase 2 | float32 | Set fallback current |
| 1022 | Fallback Max Current Phase 3 | float32 | Set fallback current |
| 1024 | Remaining Time Before Fallback | uint16 | Fallback timer (minutes) |

## 🏗️ Setup Instructions

### 1. Add the Template

1. **Open Home Assistant** → Configuration → Integrations
2. **Click "Add Integration"** → "Modbus Manager"
3. **Select "Compleo eBox Professional"** template
4. **Enter device details**:
   - **Host**: IP address of the eBox
   - **Port**: Modbus TCP port (usually 502)
   - **Slave ID**: Modbus slave address
   - **Prefix**: Unique prefix for this device (e.g., "ebox1")

### 2. Configure Modbus Connection

```yaml
# configuration.yaml
modbus:
  - name: eBox
    type: tcp
    host: 192.168.1.100  # eBox IP address
    port: 502
    slave: 1  # Modbus slave ID
```

### 3. Verify Sensors

After setup, you should see these sensors:
- `sensor.ebox1_charging_power`
- `sensor.ebox1_total_current`
- `sensor.ebox1_charging_active`
- `sensor.ebox1_cable_connected`

## 📊 Usage Examples

### Dashboard Integration

```yaml
# Lovelace Dashboard
type: entities
title: "EV Charger Status"
entities:
  - sensor.ebox1_charging_power
  - sensor.ebox1_total_current
  - sensor.ebox1_charging_efficiency
  - binary_sensor.ebox1_charging_active
  - binary_sensor.ebox1_cable_connected
```

### Current Control

```yaml
# Control current via number entity
type: number
entity: number.ebox1_set_max_current
min: 0
max: 16
step: 1
unit_of_measurement: "A"
```

### Automations

```yaml
# automation.yaml
- alias: "EV Charging Started"
  trigger:
    platform: state
    entity_id: binary_sensor.ebox1_charging_active
    to: "on"
  action:
    service: notify.mobile_app_phone
    data:
      message: "EV charging started: {{ states('sensor.ebox1_charging_power') }} W"

- alias: "High Charging Power"
  trigger:
    platform: numeric_state
    entity_id: sensor.ebox1_charging_power
    above: 10000  # 10 kW
  action:
    service: notify.mobile_app_phone
    data:
      message: "High charging power: {{ states('sensor.ebox1_charging_power') }} W"
```

## 🔧 Advanced Configuration

### Multiple Chargers

For multiple eBox chargers, use different prefixes:

```yaml
# First charger
prefix: "ebox1"
host: 192.168.1.100

# Second charger  
prefix: "ebox2"
host: 192.168.1.101
```

### Aggregate Integration

Add EV charger aggregates to your aggregate hub:

```yaml
# In aggregates hub configuration
selected_aggregates:
  - "Total EV Charging Power"
  - "Total EV Current"
  - "Average EV Charging Efficiency"
  - "Active EV Chargers"
```

### Custom Calculations

The template includes several calculated sensors:

- **Total Current**: Sum of all three phases
- **Charging Power**: Calculated using the formula: `((I1 + I2 + I3) - 0.27) * 220`
- **Charging Efficiency**: Current power / max power * 100

## ⚠️ Important Notes

### Current Control

- **Maximum Current**: 16A per phase
- **Minimum Current**: 0A (charging disabled)
- **Cable Status**: Current can only be set when cable status = 3 (connected)
- **Fallback**: Automatic fallback to lower current settings

### Power Calculation

The charging power calculation includes a correction factor:
- **Formula**: `((I1 + I2 + I3) - 0.27) * 220`
- **Correction**: 0.27A is subtracted to account for measurement offset
- **Voltage**: Assumes 220V per phase

### Safety Features

- **Cable Detection**: Only allows current control when cable is connected
- **Range Limits**: Current is limited to 0-16A range
- **Fallback Timer**: Automatic fallback to lower current after timeout

## 🔍 Troubleshooting

### Common Issues

#### Sensors Show "Unknown"
- **Check Modbus connection**: Verify IP address and port
- **Check slave ID**: Ensure correct Modbus slave address
- **Check network**: Ensure eBox is reachable

#### Current Control Not Working
- **Check cable status**: Must be connected (status = 3)
- **Check range**: Current must be between 0-16A
- **Check permissions**: Ensure Modbus write access

#### Power Calculation Wrong
- **Check current sensors**: Verify all three phases are reading
- **Check formula**: Power = ((I1 + I2 + I3) - 0.27) * 220
- **Check voltage**: Assumes 220V per phase

### Debug Logging

Enable debug logging for troubleshooting:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.modbus_manager: debug
```

## 📞 Support

For issues with the Compleo eBox template:

1. **Check logs** for Modbus communication errors
2. **Verify register mapping** matches your device
3. **Test Modbus connection** with external tools
4. **Create GitHub issue** with debug information

---

**Template Version**: 1.0  
**Last Updated**: January 2025  
**Compatible Devices**: Compleo eBox Professional, Innogy eBox
