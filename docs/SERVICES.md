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

**mkaiser migration note:** Some entities still need manual automation updates after migration — e.g. battery max power numbers renamed to `battery_max_charging_power` / `battery_max_discharging_power` and scaled to **kW** ([#70](https://github.com/TCzerny/ha-modbus-manager/issues/70)). See [Entity ID strategy — known mkaiser exceptions](ENTITY_ID_STRATEGY.md#known-mkaiser-exceptions-issue-70).

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

### 5. `modbus_manager.read_device_identification`

**Description:** Standalone diagnostic for **Modbus FC43** (function code **0x2B**, MEI *Read Device Identification*). The service opens a **short-lived connection** (Modbus **TCP**, **RTU over TCP**, or **serial RTU**), asks the device for identification strings (vendor, product code, firmware version, and more), then closes the connection.

**You do not need a Modbus Manager hub or device configured** — only access to the device (IP/port for TCP, or serial port + baud/parity for RTU). This matches the use case in [Discussion #56](https://github.com/TCzerny/ha-modbus-manager/discussions/56): read the same kind of text you would see in vendor tools (e.g. Schneider BMS) without extra software.

---

#### What you get back

| Output | Where to find it |
|--------|------------------|
| **Plain-text summary** | Persistent notification (if `notify: true`, default) |
| **Same text + details** | Home Assistant **log** (INFO level, logger `custom_components.modbus_manager.device_identification`) |
| **Structured data** | Service response in Developer tools (field `objects`, keys like `0x00`, `0x01`, …) |

Example notification / log text:

```text
Modbus device identification (FC43)
Target: 192.168.1.100:502
Slave ID: 1
Read code: basic

VendorName (0x00): Schneider Electric
ProductCode (0x01): PM5560
MajorMinorRevision (0x02): V2.1.0
```

Standard object IDs (when the device supports them):

| ID | Label | Typical content |
|----|--------|-----------------|
| `0x00` | VendorName | Manufacturer |
| `0x01` | ProductCode | Product / model code |
| `0x02` | MajorMinorRevision | Firmware / version string |
| `0x04` | ProductName | Product name |
| `0x05` | ModelName | Model name |

Use `read_code: regular` or `extended` if `basic` returns too little and your device supports more objects.

---

#### Step-by-step: run the service in the UI (beginner guide)

These steps assume Modbus Manager **1.0.19+** is installed (HACS or manual copy under `config/custom_components/modbus_manager`) and Home Assistant has been **restarted** after the update.

**1. Open Developer tools**

- In the sidebar, click **Settings** (gear icon).
- Scroll down and click **Developer tools**.
- Open the **Actions** tab (in older Home Assistant versions this tab may be named **Services**).

**2. Select the service**

- In **Action**, start typing `read_device_identification` or `modbus_manager`.
- Choose **`modbus_manager.read_device_identification`**
  *(label: “Read Device Identification (FC43)”)*.

**3. Fill in the fields**

For **TCP** (default), you only **must** set **Host**. For **serial RTU**, set **Connection type** to `serial` and **Serial port** (e.g. `/dev/ttyUSB0`).

| UI field | What to enter | Example |
|----------|----------------|---------|
| **Connection type** | `tcp` (default), `serial`, or `rtuovertcp` | `tcp` |
| **Host** | IP or hostname (**tcp** / **rtuovertcp**) | `192.168.1.100` |
| **Port** | Modbus TCP port (leave empty for default **502**) | `502` |
| **Serial port** | Device path (**serial** only) | `/dev/ttyUSB0` |
| **Baudrate** | Serial speed (**serial**, default **9600**) | `9600` |
| **Data bits** | Usually **8** (**serial**) | `8` |
| **Stop bits** | Usually **1** (**serial**) | `1` |
| **Parity** | `none`, `even`, or `odd` (**serial**) | `even` |
| **Slave ID** | Modbus unit/slave ID (leave empty for default **1**) | `1` |
| **Read code** | `basic`, `regular`, or `extended` | `basic` |
| **Timeout** | Seconds to wait for connect + read (default **3**) | `5` |
| **Show notification** | If on, creates a visible notification with the result text | `true` |

**Tip:** If you are unsure of the slave ID, try `1` first (common for inverters and gateways). Some batteries or meters use other IDs (e.g. `200`).

**4. Run the action**

- Click **Perform action** (or **Call service** on older UI).
- Wait a few seconds (timeout defaults to 3 s; increase if the device is slow or far on the network).

**5. Read the result — notification**

- Click the **bell icon** (notifications) in the sidebar (top area on phone app; left sidebar on desktop).
- Open the entry titled **“Modbus Manager — Device identification”**.
- The **message body** is the full plain-text report (vendor, product code, version, etc.).

Notifications stay until you dismiss them (X on each entry). Re-running the service updates the same notification ID for that host/port/slave combination.

**6. Read the result — logs (optional)**

If the notification is disabled (`notify: false`) or you need more detail for support:

- **Settings** → **System** → **Logs**
- Click **Load full log** (or **Show full log**), then search for `device_identification` or `Modbus device identification`
- Or open the log file on the host: `home-assistant.log` in your config directory

On failure, you still get a notification (if `notify: true`) with the error text, e.g. connection timeout or “device may not support FC43”.

**7. Read the result — Developer tools response (optional)**

After **Perform action**, expand **Response** (if shown). Useful fields:

- `message` — full text block (same as notification)
- `objects` — map of hex object IDs to string values
- `error` — present only if the call failed

---

#### YAML examples

**Minimal TCP (only IP required in practice):**

```yaml
service: modbus_manager.read_device_identification
data:
  host: 192.168.1.100
```

**Serial RTU (e.g. Schneider power meter on USB-RS485):**

```yaml
service: modbus_manager.read_device_identification
data:
  connection_type: serial
  serial_port: /dev/ttyUSB0
  baudrate: 9600
  parity: even
  data_bits: 8
  stop_bits: 1
  slave_id: 1
  notify: true
```

**RTU over TCP:**

```yaml
service: modbus_manager.read_device_identification
data:
  connection_type: rtuovertcp
  host: 192.168.1.50
  port: 502
  slave_id: 1
```

**Full TCP options:**

```yaml
service: modbus_manager.read_device_identification
data:
  host: 192.168.1.100
  port: 502
  slave_id: 1
  read_code: basic
  timeout: 5
  notify: true
```

**Log only, no notification:**

```yaml
service: modbus_manager.read_device_identification
data:
  host: 192.168.1.100
  slave_id: 1
  notify: false
```

**Try extended identification (if basic is empty or too short):**

```yaml
service: modbus_manager.read_device_identification
data:
  host: 192.168.1.100
  read_code: extended
  notify: true
```

**Different slave ID (e.g. meter on same gateway):**

```yaml
service: modbus_manager.read_device_identification
data:
  host: 10.40.0.30
  port: 502
  slave_id: 247
  read_code: basic
```

---

#### Automation example (manual button or schedule)

```yaml
automation:
  - alias: "Probe unknown Modbus device FC43"
    trigger:
      - platform: event
        event_type: test_fc43_probe
    action:
      - service: modbus_manager.read_device_identification
        data:
          host: 192.168.1.100
          port: 502
          slave_id: 1
          read_code: basic
          notify: true
```

You can fire the event from **Developer tools → Events** with event type `test_fc43_probe` to test without YAML reload.

---

#### Parameters (reference)

| Field | Required | Default | Description |
|--------|----------|---------|-------------|
| `connection_type` | No | `tcp` | `tcp`, `serial`, or `rtuovertcp`. |
| `host` | For tcp/rtuovertcp | — | IP address or hostname. |
| `port` | No | `502` | Modbus TCP port for tcp/rtuovertcp (1–65535). |
| `serial_port` | For serial | — | Serial device path (e.g. `/dev/ttyUSB0`). |
| `baudrate` | No | `9600` | Serial baudrate: 9600, 19200, 38400, 57600, or 115200. |
| `data_bits` | No | `8` | Serial data bits: `7` or `8`. |
| `stop_bits` | No | `1` | Serial stop bits: `1` or `2`. |
| `parity` | No | `none` | Serial parity: `none`, `even`, or `odd`. |
| `slave_id` | No | `1` | Modbus slave/unit ID (1–247). |
| `read_code` | No | `basic` | `basic`, `regular`, or `extended` (Modbus device identification access level). |
| `timeout` | No | `3` | Connection and read timeout in seconds (1–30). |
| `notify` | No | `true` | If `true`, creates a **persistent notification** with the full result text. |

---

#### When to use

- A **new device** is on the network or on **RS485** and you want vendor/product strings before choosing a Modbus Manager template.
- **Troubleshooting** whether a slave supports FC43 at all.
- **One-off check** from Developer tools (no polling, no new entities).

---

#### Limitations

- Not every Modbus device implements FC43; some only support **FC17 Report Slave ID** or no identification at all (common on some power meters).
- Does **not** create entities, does **not** run at hub startup, and does **not** auto-select a template.
- Opens a **separate short session** to the target (in addition to any existing Modbus connection on the same IP or serial port).
- For **serial RTU**, the USB/serial port must not be in use by another integration or hub at the same time.

---

#### Troubleshooting `read_device_identification`

| Symptom | What to try |
|---------|-------------|
| Service not in the list | Confirm Modbus Manager **1.0.19+** is installed; **restart Home Assistant**; check **Settings → Devices & services → Modbus Manager** is loaded without errors. |
| `host is required` | Set **Host** for tcp/rtuovertcp, or use **connection_type: serial** with **serial_port**. |
| Connection timeout | Ping the IP from the HA host; verify port **502** (or device-specific port); increase **timeout**; check firewall/VLAN. For serial, verify `/dev/ttyUSB0` exists and baud/parity match the device. |
| Serial port busy | Stop other integrations/hubs using the same USB-RS485 adapter; only one process can open the port. |
| No response / FC43 not supported | Try another **slave_id**; try `read_code: extended`; device may not implement FC43 — use vendor tools or register docs instead. |
| No notification | Ensure **Show notification** is `true`; check the **bell icon**; set `notify: true` in YAML. |
| Empty `objects` | Device answered but returned no strings — try `regular` / `extended`; check slave ID. |

For Schneider and similar BMS devices, **`basic`** is often enough; if the vendor tool shows more fields, try **`extended`**.

---

### 6. Device removal via subentry delete

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
