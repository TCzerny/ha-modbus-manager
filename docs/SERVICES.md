# Modbus Manager Services

This document describes all available services provided by the Modbus Manager integration.

## Available Services

### 1. `modbus_manager.performance_monitor`

**Description:** Get detailed performance metrics summary for Modbus Manager devices.

**Service Call:**
```yaml
service: modbus_manager.performance_monitor
data:
  device_id: "your_device_prefix"  # Optional: omit for global metrics
```

**Parameters:**
- `device_id` (optional): Device prefix to get metrics for a specific device. If omitted, returns global summary.

**Response:**
- Creates a persistent notification with detailed performance metrics
- Returns performance summary (also logged) including:
  - Total operations
  - Successful/failed operations
  - Success rate
  - Average duration
  - Average throughput
  - Last operation timestamp
  - **Optimization stats** (new in v0.1.2):
    - Average registers per batch read
    - Total batch reads
    - Total registers read
    - Efficiency percentage (how many reads were saved)

**Note:**
- The notification shows the device prefix (e.g., "SH10RT") which you can use as `device_id` for device-specific metrics
- Optimization stats show how efficiently registers are combined into batch reads
- If metrics show 0, wait a few minutes for the coordinator to perform operations and accumulate data

**Example:**
```yaml
# Monitor specific device
service: modbus_manager.performance_monitor
data:
  device_id: "SH10RT"

# Monitor all devices
service: modbus_manager.performance_monitor
```

---

### 2. `modbus_manager.performance_reset`

**Description:** Reset performance metrics for Modbus Manager devices.

**Service Call:**
```yaml
service: modbus_manager.performance_reset
data:
  device_id: "your_device_prefix"  # Optional: omit to reset all devices
```

**Parameters:**
- `device_id` (optional): Device prefix to reset metrics for a specific device. If omitted, resets metrics for all devices.

**When to use:**
- Before starting a performance test to get clean metrics
- If you want to reset accumulated metrics after a period of time
- For debugging performance issues

**Example:**
```yaml
# Reset metrics for specific device
service: modbus_manager.performance_reset
data:
  device_id: "SH10RT"

# Reset metrics for all devices
service: modbus_manager.performance_reset
```

---

### 3. `modbus_manager.reload_templates`

**Description:** Reload device templates and update entity attributes without restarting Home Assistant.

**Service Call:**
```yaml
service: modbus_manager.reload_templates
data:
  entry_id: "config_entry_id"  # Optional: omit to reload all templates
```

**Parameters:**
- `entry_id` (optional): Specific config entry ID to reload. If omitted, reloads all templates.

**Response:**
- Creates a persistent notification with reload results
- Logs the number of updated entries and entities

**What it does:**
- Reloads template files from disk
- Updates entity attributes (name, icon, etc.) without restart
- Maintains Modbus connection during reload
- Does NOT change entity states or values, only attributes

**When to use:**
- After updating a template file and wanting to apply changes without restart
- When developing templates and need to test changes quickly
- To refresh entity names/icons after template modifications

**Example:**
```yaml
# Reload all templates
service: modbus_manager.reload_templates

# Reload specific device template
service: modbus_manager.reload_templates
data:
  entry_id: "abc123def456"
```

---

## Removed Services

The following services have been removed as they were duplicates, unnecessary, or not useful for end users:

- **`modbus_manager.get_devices`** - Removed (devices are visible in Settings → Devices & Services)
- **`modbus_manager.get_performance`** - Removed (use `performance_monitor` instead)
- **`modbus_manager.reset_performance`** - Removed (use `performance_reset` instead)
- **`modbus_manager.register_optimize`** - Removed (register optimization is automatic)

---

## Performance Metrics Explained

### What are Performance Metrics?

The Modbus Manager tracks performance metrics to help you understand:
- **How many Modbus operations** are being performed
- **How long** each operation takes
- **Success rate** of operations
- **Network throughput** (bytes per second)

### Understanding the Metrics

- **Total Operations:** Number of Modbus read/write operations performed
- **Success Rate:** Percentage of successful operations (0-100%)
- **Average Duration:** Average time per operation in seconds
- **Average Throughput:** Average data transfer rate in bytes per second
- **Register Count:** Number of registers read per operation

### Performance Comparison

To compare performance with the standard HA Modbus integration:

1. **Count Modbus Requests:**
   - Modbus Manager: Check logs for "Reading X registers in Y optimized ranges"
   - Standard HA: Each register = 1 request

2. **Measure Total Time:**
   - Use `modbus_manager.performance_monitor` to see average duration
   - Compare with standard HA integration timing

3. **Network Efficiency:**
   - Modbus Manager batches consecutive registers into single requests
   - Standard HA makes separate requests for each register

---

## Using Services in Automations

You can use these services in Home Assistant automations:

```yaml
automation:
  - alias: "Check Modbus Performance Daily"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - service: modbus_manager.performance_monitor
      - service: notify.persistent_notification
        data:
          message: "Performance metrics logged. Check logs for details."
```

---

## Troubleshooting

### Service Not Found

If a service is not found:
1. Ensure the Modbus Manager integration is installed and configured
2. Restart Home Assistant
3. Check the logs for service registration errors

### Performance Metrics Not Available

If performance metrics are empty:
1. Ensure devices are actively reading registers
2. Wait a few minutes for metrics to accumulate
3. Check that the coordinator is running

### Template Reload Issues

If template reload doesn't work:
1. Check the logs for specific error messages
2. Ensure the template file is valid YAML
3. Verify the entry_id is correct (if specified)

---

## Additional Notes

- All services log their results to the Home Assistant logs
- Performance metrics are stored in memory and reset on Home Assistant restart
- Use `performance_reset` to clear metrics without restarting
- Template reload updates entity attributes but does not change entity availability or state
