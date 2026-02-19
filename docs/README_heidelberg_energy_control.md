# Heidelberg Energy Control Wallbox Template

## Overview

The **Heidelberg Energy Control Template** integrates Amperfied's Heidelberg Energy Control Wallbox with Home Assistant via Modbus Manager. The wallbox uses **Modbus RTU** over RS-485 (e.g. via CH340 USB adapter).

**Manufacturer:** [Amperfied](https://www.amperfied.de/) (Heidelberg wallbox series)
**Protocol:** Modbus RTU (19200 baud, 8E1 typical)
**Documentation:** [EC_ModBus_register_table_20210222_LW.pdf](https://www.amperfied.de/wp-content/uploads/2023/03/EC_ModBus_register_table_20210222_LW.pdf)

## Connection Architecture

```
Home Assistant → Modbus Manager → Heidelberg template → TCP or RTU over TCP
                                                              ↓
                                              Modbus Proxy (TCzerny ha-modbusproxy)
                                                              ↓
                                              Serial (RS-485 / USB) → Wallbox
```

- **Modbus RTU only** – no native Modbus TCP. The wallbox speaks RTU over RS-485.
- **RTU over TCP** (required): Use [modbus-proxy](https://github.com/TCzerny/ha-modbusproxy) or similar gateway. Serial connection is not supported yet.
- Typical settings: 19200 baud, 8E1 (8 data bits, Even parity, 1 stop bit)

## Step-by-Step Setup Guide

### Prerequisites

- Home Assistant with Modbus Manager integration installed ([HACS](https://hacs.xyz/) or manual)
- [Modbus Proxy](https://github.com/TCzerny/ha-modbusproxy) add-on installed
- Heidelberg Energy Control Wallbox with RS-485 connection (e.g. USB-RS485 adapter like CH340)
- Physical connection: Wallbox RS-485 terminals → USB-RS485 adapter → Home Assistant host (or device running the proxy)

---

### Step 1: Install Modbus Proxy Add-on

1. Go to **Settings** → **Add-ons** → **Add-on Store**
2. Click the **⋮** menu (top right) → **Repositories**
3. Add repository: `https://github.com/TCzerny/ha-modbusproxy`
4. Find **Modbus Proxy** in the store → **Install**

---

### Step 2: Configure Modbus Proxy for the Wallbox

1. Go to **Settings** → **Add-ons** → **Modbus Proxy** → **Configuration**
2. Add a device entry for the Heidelberg wallbox. Example configuration:

```yaml
modbus_devices:
  - name: "Heidelberg Energy Control"
    device: "/dev/ttyUSB0"
    baudrate: 19200
    databits: 8
    stopbits: 1
    parity: "E"
    bind_port: 5502
    timeout: 5.0
```

**Parameters explained:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| `device` | `/dev/ttyUSB0` | Serial port (may be `ttyUSB1`, `ttyACM0`, etc. – check add-on logs at startup) |
| `baudrate` | `19200` | Per Amperfied documentation |
| `databits` | `8` | 8 data bits |
| `stopbits` | `1` | 1 stop bit |
| `parity` | `E` | Even parity (8E1) |
| `bind_port` | `5502` | Local port where proxy listens (use a free port, e.g. 5502, 5503) |

**Tip:** Enable `auto_detect_device: true` if you prefer automatic serial device detection instead of specifying `device`.

3. Click **Save**
4. Start the add-on: **Info** tab → **Start**
5. Check the logs to confirm the proxy is listening on your `bind_port`

---

### Step 3: Add Device in Modbus Manager

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration** → search for **Modbus Manager** (or configure existing instance)
3. Select template: **Heidelberg Energy Control**

---

### Step 4: Connection Parameters (Modbus Manager)

1. **Host:** IP address of the machine running Modbus Proxy
   - Same host as Home Assistant: `127.0.0.1` or `localhost`
   - Another host (e.g. Raspberry Pi): use that host’s IP
2. **Port:** The `bind_port` from Step 2 (e.g. `5502`)
3. **Modbus type:** Select **RTU over TCP**
4. **Prefix:** e.g. `hec` or `wallbox`
5. **Slave ID:** `1` (default for most wallboxes)

---

### Step 5: Dynamic Configuration

1. **Connection type:** RTU over TCP (only option for this template)
2. **selected_model:** Choose your model (Energy Control, Energy Control PLUS 11kW, or Energy Control Climate)
3. **Firmware version:** Select your wallbox firmware (1.0.7 or 1.0.8)

---

### Step 6: Verify Connection

1. After setup, entities should appear under your device
2. Check sensors like **Status** and **Charging Power** – they should update
3. If values stay `Unknown` or you see errors:
   - Verify Modbus Proxy is running and listening
   - Confirm host/port match the proxy config
   - Ensure **Modbus type** is **RTU over TCP**
   - Check serial connection (cables, adapter, correct `/dev/tty*` device)

## Dynamic configuration

| Parameter | Options | Description |
| **selected_model** | Energy Control, Energy Control PLUS 11kW, Energy Control Climate | Model (same register map for all) |
| **firmware_version** | 1.0.7, 1.0.8 | Modbus layout version (reg 4). Energy since Installation requires 1.0.7+ |

## Sensors

### Device Info
| Register | Name | Description |
|----------|------|-------------|
| 4 | Modbus Register Version | Protocol layout version (e.g. 0x100 = V1.0.0) |
| 200 | Hardware Variant | Hardware type |
| 203 | Application Software Version | Firmware/SVN revision |
| 100 | HW Max Current | Hardware max current (A) |
| 101 | HW Min Current | Hardware min current (A) |

### Charging Status
| Register | Name | Description |
|----------|------|-------------|
| 5 | Status | A1, A2, B1, B2, C1, C2, Derating, E, F, Error |
| 13 | External Lock State | Locked / Unlocked |

### Measurements
| Register | Name | Unit | Scale |
|----------|------|------|-------|
| 6–8 | Current Phase 1/2/3 | A | 0.1 |
| 9 | PCB Temperature | °C | 0.1 |
| 10–12 | Voltage Phase 1/2/3 | V | 1 |
| 14 | Charging Power | VA | 1 |
| 15–16 | Energy since PowerOn | VAh | - |
| 17–18 | Energy since Installation | VAh | - |

## Controls

| Register | Name | Range | Description |
|----------|------|-------|-------------|
| 261 | Max Current | 0–16 A | Charging current limit (0 = off, disables charging) |
| 262 | FailSafe Current | 0–16 A | Current when Modbus lost (0 = error) |
| 259 | Remote Lock | On/Off | Lock/unlock (if external lock open) |
| 258 | Standby Function | Enable/Disable | Power saving when no car plugged |
| 257 | Watchdog Timeout | 0–65535 ms | Modbus timeout (0 = off) **commented out for now**|

## Charging States (IEC 61851)

- **A1/A2**: No vehicle plugged
- **B1/B2**: Vehicle plugged, no charging request
- **C1/C2**: Charging
- **Derating**: Reduced power
- **E/F/Error**: Fault states
