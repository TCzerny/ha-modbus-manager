# Modbus Manager Services

> **Context:** For using the integration end-to-end, see the [User Guide (Wiki)](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide). This file lists **service** definitions only.

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

### 3. `modbus_manager.add_entity_prefix`

**Description:** Renames **entity IDs** so they include the device prefix, for devices that were added with **Entity IDs without prefix** set to **yes** (`entity_ids_without_prefix`), or with **`entity_id_strategy: legacy_unprefixed`** (same intent). This is the follow-up step after a migration where you matched another integration’s unprefixed `entity_id` values (see [Migration from mkaiser (Wiki)](https://github.com/TCzerny/ha-modbus-manager/wiki/Migration-from-mkaiser)).

**Behavior:**

- Only affects entities belonging to the given Modbus Manager **config entry** that are tied to a **device** still configured with `entity_ids_without_prefix: yes` / **`legacy_unprefixed`** (see [Entity ID strategy](ENTITY_ID_STRATEGY.md)).
- For each matching entity, if the `entity_id` **does not** already start with `{prefix}_`, it is renamed from `domain.object_id` to `domain.{prefix}_object_id` (prefix lowercased), e.g. `sensor.battery_level` → `sensor.sg_battery_level`.
- **`unique_id` in the registry is unchanged**; only **`entity_id`** is updated. Home Assistant **migrates history** when an `entity_id` is renamed.
- Entities that **already** have the prefix in `entity_id` are skipped.
- If the target `entity_id` already exists, that rename is **skipped** (logged as a conflict).

**Service call:**

```yaml
service: modbus_manager.add_entity_prefix
data:
  entry_id: "<modbus_manager_config_entry_id>"  # required
  # device_entry_id: "<device_subentry_unique_id>"  # optional: only this device on a multi-device hub
```

**Parameters:**

| Field | Required | Description |
|--------|----------|-------------|
| `entry_id` | **Yes** | Modbus Manager integration config entry ID. In **Developer tools → Services**, pick `modbus_manager.add_entity_prefix` and use the **config entry** selector. |
| `device_entry_id` | No | Device **subentry** `unique_id` (logical device id). Use when the hub has **multiple** devices and you only want to rename entities for **one** of them. Omit to process every device on that entry that still has `entity_ids_without_prefix: yes`. |

**History:** Renaming via this service updates only **`entity_id`** in the registry; **`unique_id` is unchanged**. Home Assistant **migrates recorder history** to the new `entity_id` when the rename succeeds. This is the recommended way to move from **unprefixed** (mkaiser-style) to **prefixed** ids without losing history. See [Entity ID strategy](ENTITY_ID_STRATEGY.md) (history preservation).

**After running the service:**

1. Set **Entity IDs without prefix** to **no** (or **`entity_id_strategy`** to **`legacy_prefixed`**) for that device (**Configure** on the device in **Settings → Devices & services**).
2. **Important:** Future reloads/reconfigures only **keep** prefixed `entity_id` values if the registry **already** has those prefixed names (or you run this service first). Changing strategy to **`legacy_prefixed`** alone on an install that still has unprefixed registry rows does **not** rename them automatically.
3. Update automations, dashboards, and scripts to use the **new** `entity_id` values if anything still pointed at the old unprefixed names.

**If nothing is renamed:** Check the logs. Common causes:

- No device on that entry has `entity_ids_without_prefix: yes` / **`legacy_unprefixed`**.
- Wrong `entry_id` or `device_entry_id`.
- `entity_id` **already** includes the prefix (skipped).
- Target `entity_id` **already exists** (conflict — rename skipped; resolve duplicate registry row first).

---

### Removing prefix from entity IDs (no dedicated service)

There is **no** `modbus_manager.remove_entity_prefix` (or similar) service. To work with **unprefixed** `entity_id` values again:

- Prefer **device reconfiguration**: set **`entity_id_strategy`** to **`legacy_unprefixed`** (or legacy **Entity IDs without prefix: yes**) where the template supports it, then reload — **only affects new registry rows**; existing prefixed `entity_id` values are not auto-stripped. For a clean mkaiser-style setup, follow [Migration from mkaiser](https://github.com/TCzerny/ha-modbus-manager/wiki/Migration-from-mkaiser) (remove old YAML → restart → add device unprefixed).
- Or **manually** rename entities under **Settings → Devices & services → Entities** (be aware of history and automation references per Home Assistant behavior).

---

### 4. `modbus_manager.reload_templates`

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

### 5. Device removal via subentry delete

**Description:** Per-device removal is now handled directly in Home Assistant UI by deleting the device subentry.

**How to use:**
- Open the Modbus Manager entry
- Select the device subentry
- Use delete/remove in the subentry menu

This updates the underlying `devices[]` data and the removed device does not return after restart.

---

## Removed Services

The following services have been removed as they were duplicates, unnecessary, or not useful for end users:

- **`modbus_manager.get_devices`** - Removed (devices are visible in Settings → Devices & Services)
- **`modbus_manager.get_performance`** - Removed (use `performance_monitor` instead)
- **`modbus_manager.reset_performance`** - Removed (use `performance_reset` instead)
- **`modbus_manager.register_optimize`** - Removed (register optimization is automatic)
- **`modbus_manager.remove_device`** - Removed (use subentry delete in UI)

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

  # After SHx migration with entity_ids_without_prefix: add prefix to entity_ids once
  - alias: "Add Modbus Manager entity prefix after migration"
    trigger: []
    action:
      - service: modbus_manager.add_entity_prefix
        data:
          entry_id: "<your_modbus_manager_config_entry_id>"
          # device_entry_id: "<optional_subentry_unique_id>"
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

### `add_entity_prefix` renames nothing

1. Confirm at least one device on that config entry still has **Entity IDs without prefix** set to **yes**.
2. Confirm `entry_id` is the Modbus Manager **hub** entry, not another integration.
3. If you passed `device_entry_id`, it must match the device subentry’s **unique_id** exactly.
4. Check logs for “Skipping rename due to conflict” (target `entity_id` already taken).

---

## Additional Notes

- All services log their results to the Home Assistant logs
- Performance metrics are stored in memory and reset on Home Assistant restart
- Use `performance_reset` to clear metrics without restarting
- Template reload updates entity attributes but does not change entity availability or state
