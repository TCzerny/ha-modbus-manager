# Sungrow AC011E Wallbox Template

> **General documentation (Wiki):** [User Guide](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide) · [Template reference](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference) · [Capabilities and limits](https://github.com/TCzerny/ha-modbus-manager/wiki/Capabilities-and-Limits) · [Local customization](https://github.com/TCzerny/ha-modbus-manager/wiki/Local-Customization)

## 📋 Overview

The **Sungrow AC011E Wallbox Template** provides integration for Sungrow EV wallboxes. It is based on the [Sungrow-Wallbox-Modbus-HomeAssistant](https://github.com/Louisbertelsmann/Sungrow-Wallbox-Modbus-HomeAssistant) project by Louis Bertelsmann.

## 🏭 Supported Models

- **AC007-00** – Device type code 0x20ED
- **AC011E-01** – Device type code 0x20DA (primary model)
- **AC22E-01** – Device type code 0x3F80

## 🔌 Connection

Full wiring, ports, and slaves: **[Sungrow AC wallbox connection topologies](README_sungrow_wallbox_connection.md)**.

1. **RS485 to hybrid** — SHx on **inverter LAN** only sees proxy **`33540–33549`**. Full `21xxx` (this template): hub host = **WiNet-S IP**, slave = WiNet **Forwarding Modbus ID** (often **2** or **3**, not inverter LAN, not 248). [#127](https://github.com/TCzerny/ha-modbus-manager/issues/127).
2. **Direct LAN TLS** — charger Ethernet, no iHM. **Own** hub, charger IP, **TLS**, port **516**, slave **248** (HA 2026.9+).
3. **iHomeManager** — do **not** use this template. [iHomeManager](README_iHomeManager.md) hub, **`charger_enabled`**. iHM already holds charger `:516`.

## ⚙️ Configuration

### Required Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| **Model** | Select | AC011E-01 | Wallbox model (Output Current limits from datasheet) |
| **Prefix** | String | WB | Unique prefix for all entities |
| **Slave ID** | Integer | 3 | WiNet forwarding ID (confirm in dongle Device List; often 2 or 3) or **248** on TLS |

### Model Selection (config flow / options flow)

During setup you select your wallbox model. Min/max values for **Output Current** are taken from the datasheet:

| Model | Min | Max | Phases | Power |
|-------|-----|-----|--------|-------|
| AC007-00 | 6 A | 32 A | 1 | 7.4 kW |
| AC011E-01 | 6 A | 16 A | 3 | 11 kW |
| AC22E-01 | 6 A | 32 A | 3 | 22 kW |

### Example

Add as a Modbus Manager device with:

- **Template:** Sungrow AC011E Wallbox
- **Model:** AC011E-01 (or your model)
- **Host:** **WiNet-S IP** for forwarded `21xxx`, or **charger LAN IP** for TLS — not the inverter Ethernet jack
- **Port:** 502 (WiNet) or 516 (TLS)
- **Slave ID:** WiNet forwarding ID (**2** or **3**, confirm in the dongle list), or **248** on charger TLS / USB-RS485 (see [connection topologies](README_sungrow_wallbox_connection.md))

## 📊 Available Entities

### Sensors

| Entity | Description |
|--------|-------------|
| Device Type Code | Model identification (AC007-00, AC011E-01, AC22E-01) |
| Power Phases | Number of power phases |
| Rated Voltage | Rated voltage (V) |
| Phase Switching Status | Three phase / Single phase |
| Minimum / Maximum Charging Power | Power limits (W) |
| Total Energy | Lifetime energy delivered (Wh) |
| Phase A/B/C Voltage & Current | Per-phase measurements |
| Charging Power / Energy | Current session power (W) and energy (Wh) |
| Charging Status | Idle, Standby, Charging, Completed, etc. |
| Charging Start / End Time | Session timestamps |
| Start Mode | Stopped, EMS, Swipe |

### Controls

| Entity | Type | Description |
|--------|------|-------------|
| Output Current | Number | Max charging current (model-dependent: 6–16 A or 6–32 A) |
| Phase Mode | Select | Three phase / Single phase |
| Charger Enable | Switch | Enable / Disable wallbox |
| Mileage per kWh | Number | km/kWh for range calculation (1–500) |
| Working Mode | Select | Network, Plug and Play, EMS |
| Start Charging | Button | Remote start |
| Stop Charging | Button | Remote stop |

### Calculated Sensors

| Entity | Description |
|--------|-------------|
| Charging Start Time | Formatted timestamp (dd.mm.yyyy HH:mm) |
| Charging End Time | Formatted timestamp |
| Charging Duration | Session duration (H:MM) |
| Charged Range | Estimated km from energy × mileage/kWh |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| Charging Active | True when status is Charging |
