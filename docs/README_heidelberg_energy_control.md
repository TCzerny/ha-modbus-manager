# Heidelberg Energy Control Wallbox Template

## Overview

The **Heidelberg Energy Control Template** integrates Amperfied's Heidelberg Energy Control Wallbox with Home Assistant via Modbus Manager. The wallbox uses **Modbus RTU** over RS-485 (e.g. via CH340 USB adapter).

**Manufacturer:** [Amperfied](https://www.amperfied.de/) (Heidelberg wallbox series)
**Protocol:** Modbus RTU (19200 baud, 8E1 typical)
**Documentation:** [EC_ModBus_register_table_20210222_LW.pdf](https://www.amperfied.de/wp-content/uploads/2023/03/EC_ModBus_register_table_20210222_LW.pdf)

See also:
- [GitHub Discussion #18](https://github.com/TCzerny/ha-modbus-manager/discussions/18)
- [evcc heidelberg-ec.go](https://github.com/evcc-io/evcc/blob/master/charger/heidelberg-ec.go) – reference implementation

## Connection

- **Modbus RTU only** – no native Modbus TCP. The wallbox speaks RTU over RS-485.
- **RTU over TCP** (required): Use [modbus-proxy](https://github.com/TCzerny/ha-modbusproxy) or similar gateway. The template provides a **Connection type** option ("RTU over TCP") in the dynamic config step. Serial connection is not supported yet.
- Typical settings: 19200 baud, 8E1 (8 data bits, Even parity, 1 stop bit)

## Dynamic configuration

| Parameter | Options | Description |
| **connection_type** | RTU over TCP | Communication transport (required when using proxy/gateway) |
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
| 257 | Watchdog Timeout | 0–65535 ms | Modbus timeout (0 = off) |

## Charging States (IEC 61851)

- **A1/A2**: No vehicle plugged
- **B1/B2**: Vehicle plugged, no charging request
- **C1/C2**: Charging
- **Derating**: Reduced power
- **E/F/Error**: Fault states

## Entity Groups (aligned with eBox template)

- `EV_device_info` – Version, hardware, temperature, lock state
- `EV_charging_status` – Status, charging active, vehicle connected
- `EV_current_measurement` – Current Phase 1/2/3, Total Current
- `EV_voltage_measurement` – Voltage Phase 1/2/3, Average Voltage
- `EV_charging_power` – Charging Power
- `EV_meter_reading` – Energy counters
- `EV_max_current_actual` – Actual Max Current, FailSafe Current
- `EV_max_current_setting` – Max Current, FailSafe Current (controls)
- `EV_lock_control` – Remote lock
- `EV_power_control` – Standby
