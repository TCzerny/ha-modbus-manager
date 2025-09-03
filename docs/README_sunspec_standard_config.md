# SunSpec Standard Config Template

## 📋 Overview

The **SunSpec Standard Config Template** is a universal template for all SunSpec-compliant devices. This template automatically generates sensors based on the SunSpec standard and user-provided model addresses.

## 🏭 Supported Manufacturers

### ✅ SunSpec-Compliant Devices
- **SMA** - Sunny Boy, Tripower, Home Storage
- **Fronius** - GEN24, Tauro
- **Huawei** - Luna, FusionSolar
- **SolarEdge** - HD Wave, StorEdge
- **Kostal** - Piko, Plenticore
- **Growatt** - MIN, MAX series
- **Victron** - MultiPlus, Quattro
- **And many more...**

### 🔧 Universal Compatibility
This template works with **any** device that follows the SunSpec standard, regardless of manufacturer.

## 🔧 Configuration

### Required Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| **Prefix** | String | Required | Unique prefix for all entities |
| **Name** | String | Optional | Display name for the device |
| **Common Model Address** | Number | Required | Base address for Common Model |
| **Inverter Model Address** | Number | Required | Base address for Inverter Model |
| **Storage Model Address** | Number | Optional | Base address for Storage Model |
| **Meter Model Address** | Number | Optional | Base address for Meter Model |

### Example Configuration

```yaml
# Basic Configuration
prefix: "sma_inverter"
name: "SMA Sunny Boy 5.0"

# SunSpec Model Addresses
common_model_address: 40001
inverter_model_address: 40069
storage_model_address: 40187
meter_model_address: 40277
```

## 📊 Features

### ✅ Automatic Sensor Generation

#### 🔧 Common Model (Device Information)
- **Manufacturer**: Device manufacturer
- **Model**: Model designation
- **Serial Number**: Device serial number
- **Firmware Version**: Current firmware version
- **Device Address**: Modbus device address

#### ⚡ Inverter Model (Inverter Data)
- **AC Power**: AC power output (W)
- **AC Current**: AC current (A) - all phases
- **AC Voltage**: AC voltage (V) - all phases
- **AC Frequency**: AC frequency (Hz)
- **DC Power**: DC power input (W)
- **DC Current**: DC current (A)
- **DC Voltage**: DC voltage (V)
- **Temperature**: Inverter temperature (°C)
- **Operating Status**: Current operating state

#### 🔋 Storage Model (Battery Data)
- **Battery Level**: State of charge (%)
- **Battery Voltage**: Battery voltage (V)
- **Battery Current**: Battery current (A)
- **Battery Temperature**: Battery temperature (°C)
- **Charging Status**: Charging/discharging state
- **Battery Power**: Battery power (W)

#### 📊 Meter Model (Grid Data)
- **Grid Power**: Grid power flow (W)
- **Grid Current**: Grid current (A) - all phases
- **Grid Voltage**: Grid voltage (V) - all phases
- **Grid Frequency**: Grid frequency (Hz)
- **Energy Import**: Total energy imported (kWh)
- **Energy Export**: Total energy exported (kWh)

### 📈 Calculated Sensors

#### ⚡ Efficiency Calculations
- **Inverter Efficiency**: DC to AC conversion efficiency (%)
- **MPPT Efficiency**: Maximum power point tracking efficiency (%)
- **Overall Efficiency**: System overall efficiency (%)

#### 🔋 Battery Calculations
- **Battery Capacity**: Available battery capacity (kWh)
- **Charging Rate**: Energy charging rate (kWh/h)
- **Discharging Rate**: Energy discharging rate (kWh/h)

#### 📊 Energy Calculations
- **Net Energy**: Net energy flow (kWh)
- **Self-Consumption**: Self-consumed energy (kWh)
- **Grid Feed-in**: Grid feed-in energy (kWh)

## 🔧 Installation

### 1. Template Selection
1. Open Home Assistant
2. Go to **Settings** → **Devices & Services**
3. Click **Add Integration**
4. Search for **Modbus Manager**
5. Select **SunSpec Standard Config** template

### 2. Configuration
1. Enter device **prefix** (e.g., "sma_inverter")
2. Enter device **name** (e.g., "SMA Sunny Boy 5.0")
3. Configure **SunSpec model addresses**:
   - Common Model: 40001 (default)
   - Inverter Model: 40069 (default)
   - Storage Model: 40187 (optional)
   - Meter Model: 40277 (optional)

### 3. Modbus Configuration
Ensure you have a Modbus integration configured:

```yaml
# configuration.yaml
modbus:
  - name: "sunspec_device"
    type: tcp
    host: 192.168.1.100  # Your device IP address
    port: 502
    timeout: 3
    retries: 3
```

## 📍 Standard Model Addresses

### Common Base Addresses

#### **SMA**
- Common Model: `40001`
- Inverter Model: `40069`
- Storage Model: `40187`
- Meter Model: `40277`

#### **Fronius**
- Common Model: `40001`
- Inverter Model: `40069`
- Storage Model: `40187`
- Meter Model: `40277`

#### **Huawei**
- Common Model: `40001`
- Inverter Model: `40069`
- Storage Model: `40187`
- Meter Model: `40277`

#### **SolarEdge**
- Common Model: `40001`
- Inverter Model: `40069`
- Storage Model: `40187`
- Meter Model: `40277`

## 🚨 Troubleshooting

### Common Issues

#### Address Problems
- **Wrong Model Address**: Verify base addresses from device manual
- **Missing Models**: Some devices don't support all SunSpec models
- **Register Access**: Check Modbus register accessibility

#### Sensor Issues
- **No Data**: Verify model addresses and Modbus connection
- **Wrong Values**: Check data type and scaling
- **Missing Sensors**: Ensure model is supported by device

### Debug Steps

1. **Check Modbus Connection**:
   ```bash
   # Test Modbus connectivity
   telnet [IP_ADDRESS] 502
   ```

2. **Verify Model Addresses**:
   ```bash
   # Test Common Model (40001)
   modbus read [IP_ADDRESS] 502 1 40001 10
   
   # Test Inverter Model (40069)
   modbus read [IP_ADDRESS] 502 1 40069 10
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
**Compatibility:** All SunSpec-Compliant Devices

## 🔗 Related Documentation

- **[Main README](../../README.md)** - Project overview
- **[SunSpec Standard](../../custom_components/modbus_manager/device_templates/base_templates/sunspec_standard.yaml)** - Base template definition
- **[GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)** - Additional documentation

## 🙏 Acknowledgments

- **SunSpec Alliance** for the Modbus standard
- **Device Manufacturers** for SunSpec compliance
- **Home Assistant Community** for integration support
