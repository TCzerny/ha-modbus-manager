# Aggregate Sensors Documentation

## 📊 Overview

Aggregate sensors allow you to combine values from multiple Modbus Manager devices and create higher-level statistics. This is particularly useful for solar installations with multiple inverters, battery storage systems, or other energy devices.

## 🎯 What are Aggregate Sensors?

Aggregate sensors collect data from all sensors with the same `group` property and calculate:
- **Sum**: Addition of all values
- **Average**: Arithmetic mean
- **Maximum**: Highest value
- **Minimum**: Lowest value
- **Count**: Number of devices/sensors

## 🏗️ Setup and Configuration

### 1. Create Aggregate Hub

1. **Open Home Assistant** → Configuration → Integrations
2. **Click "Add Integration"** → "Modbus Manager"
3. **Select "Modbus Manager Aggregates"** template
4. **Enter prefix** (e.g., "SG" for Sungrow)
5. **Select aggregate sensors** (see available options below)

### 2. Available Aggregate Groups

#### 🔋 Battery Aggregates
- **`battery_power`**: Total battery power (charging + discharging)
- **`battery_charging`**: Charging power only
- **`battery_discharging`**: Discharging power only

#### ⚡ Solar Aggregates
- **`mppt_power`**: MPPT power (Solar Power)
- **`total_dc_power`**: Total DC power

#### 🔌 Grid Aggregates
- **`grid_power`**: Net grid power
- **`grid_import`**: Grid import (consumption)
- **`grid_export`**: Grid export (feed-in)

#### 🏠 Load Aggregates
- **`load_power`**: Load power
- **`power_measurement`**: Power measurement
- **`power_balance`**: Power balance
- **`phase_power`**: Phase power
- **`meter_power`**: Meter power

#### 📊 Efficiency Aggregates
- **`efficiency`**: Average efficiency

#### 🔢 Device Aggregates
- **`device_count`**: Number of devices

### 3. Post-Configuration

Aggregate hubs can be reconfigured later via the Options Flow:

1. **Integrations** → **Modbus Manager** → **Aggregates Hub** → **Options**
2. **Select/deselect aggregate sensors**
3. **Save changes**

## 📋 Example Configuration

### Sungrow Inverter Setup

```yaml
# Example for two SG1 and SG2 inverters
# SG1: Prefix "sg1"
# SG2: Prefix "sg2"

# Aggregate Hub: Prefix "total"
# Selected aggregates:
- Total Battery Power Sum
- Total Solar Power Sum  
- Total Grid Export Power Sum
- Total Load Power Sum
- Average Efficiency
- Device Count Count
```

### Resulting Sensors

After configuration, the following sensors are created:

```
sensor.total_battery_power_sum          # SG1 + SG2 battery power
sensor.total_solar_power_sum            # SG1 + SG2 solar power
sensor.total_grid_export_power_sum      # SG1 + SG2 grid export
sensor.total_load_power_sum             # SG1 + SG2 load power
sensor.efficiency_average               # Average efficiency
sensor.device_count_count               # Number of devices (2)
```

## 🔧 Template Configuration

### Define Sensor Groups

In device templates, sensors are assigned to groups:

```yaml
# custom_components/modbus_manager/device_templates/sungrow_shx.yaml
sensors:
  - name: "Battery Charging Power"
    unique_id: "battery_charging_power"
    group: "battery_charging"  # ← Group for aggregation
    # ... additional configuration

  - name: "Total MPPT Power"
    unique_id: "total_mppt_power"
    group: "mppt_power"        # ← Group for aggregation
    # ... additional configuration
```

### Define Aggregate Sensors

```yaml
# custom_components/modbus_manager/device_templates/aggregates_hub.yaml
aggregates:
  - name: "Total Battery Charging Power"
    group: "battery_charging"
    method: "sum"
    unit_of_measurement: "W"
    device_class: "power"
    state_class: "measurement"
    icon: "mdi:battery-plus"
```

## 📊 Usage Examples

### Dashboard Integration

```yaml
# configuration.yaml
homeassistant:
  customize:
    sensor.total_battery_power_sum:
      friendly_name: "Total Battery Power"
      icon: mdi:battery
    sensor.total_solar_power_sum:
      friendly_name: "Total Solar Power"
      icon: mdi:solar-power
    sensor.efficiency_average:
      friendly_name: "Average Efficiency"
      icon: mdi:gauge
```

### Lovelace Cards

```yaml
# Lovelace Dashboard
type: entities
title: "Energy Overview"
entities:
  - sensor.total_solar_power_sum
  - sensor.total_battery_power_sum
  - sensor.total_grid_export_power_sum
  - sensor.efficiency_average
  - sensor.device_count_count
```

### Automations

```yaml
# automation.yaml
- alias: "High Solar Power"
  trigger:
    platform: numeric_state
    entity_id: sensor.total_solar_power_sum
    above: 10000  # 10 kW
  action:
    service: notify.mobile_app_phone
    data:
      message: "High solar power: {{ states('sensor.total_solar_power_sum') }} W"
```

## ⚠️ Important Notes

### Avoid Double Counting

**Problem**: Sensors can be double-counted if:
- Calculated sensors and raw data sensors are in the same group
- Multiple sensors represent the same value

**Solution**: Use separate groups for different sensor types:

```yaml
# ❌ Wrong - Double counting
- name: "Battery Power Raw"
  group: "battery_power"
- name: "Battery Power Calculated"  
  group: "battery_power"  # Same group = double counting

# ✅ Correct - Separate groups
- name: "Battery Power Raw"
  group: "battery_power_raw"
- name: "Battery Power Calculated"
  group: "battery_power_calculated"
```

### Prevent Self-Referencing

Aggregate sensors automatically exclude themselves from calculations:

```yaml
# These sensors are automatically excluded:
sensor.sg1_battery_power_sum      # Contains "_sum"
sensor.sg1_battery_power_max      # Contains "_max"
sensor.sg1_battery_power_average  # Contains "_average"
```

### Performance Optimization

- Use **debug logging** for better performance
- Adjust **scan intervals** (default: 10 seconds)
- **Only activate needed aggregates**

## 🔍 Troubleshooting

### Aggregate shows "unknown"

**Cause**: No sensors found with the corresponding group

**Solution**:
1. Check if sensors have the correct `group` property
2. Enable debug logging: `logger: custom_components.modbus_manager: debug`
3. Restart Home Assistant

### Double values

**Cause**: Multiple sensors in the same group

**Solution**:
1. Review groups in templates
2. Separate calculated and raw data sensors
3. Enable debug logging for `tracked_entities`

### Slow updates

**Cause**: Too many aggregate sensors or short scan intervals

**Solution**:
1. Only activate needed aggregates
2. Increase scan intervals
3. Disable debug logging

## 📚 Advanced Configuration

### Custom Aggregate Methods

```yaml
# Add new aggregate method
aggregates:
  - name: "Total Power Peak"
    group: "mppt_power"
    method: "max"  # Highest value
    unit_of_measurement: "W"
    device_class: "power"
```

### Multiple Aggregate Hubs

```yaml
# Different aggregate hubs for different purposes
# Hub 1: Solar overview
prefix: "solar"
aggregates: ["mppt_power", "efficiency"]

# Hub 2: Battery overview  
prefix: "battery"
aggregates: ["battery_charging", "battery_discharging"]
```

### Conditional Aggregates

```yaml
# Aggregates only under certain conditions
aggregates:
  - name: "Active Solar Power"
    group: "mppt_power"
    method: "sum"
    condition: "{{ states('sensor.weather_sun') == 'above_horizon' }}"
```

## 🎯 Best Practices

1. **Meaningful Groups**: Use semantically meaningful group names
2. **Consistent Prefixes**: Use uniform prefixes for all devices
3. **Minimal Aggregates**: Only activate needed aggregates
4. **Debug Logging**: Use debug logging for development, INFO for production
5. **Template Validation**: Test templates before production use

## 📞 Support

For problems with aggregate sensors:

1. **Enable debug logging**:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.modbus_manager: debug
   ```

2. **Check logs** for:
   - `tracked_entities`: Which sensors are being tracked
   - `Self-Reference`: Whether aggregate sensors exclude themselves
   - `Group Assignment`: Whether sensors have correct groups

3. **Create GitHub Issues** with:
   - Home Assistant version
   - Modbus Manager version
   - Debug logs
   - Template configuration

---

**Last Updated**: January 2025  
**Version**: 2.1.0  
**Author**: Modbus Manager Team