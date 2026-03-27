# Victron EV Charging Station Template

## Overview

Template for **Victron EV Charging Station** (with LCD) and **EV Charging Station NS** (rounded design, no screen). Both units expose the **same Modbus TCP registers** and behave the same from Modbus Manager’s perspective.

- **Register reference:** Victron *EVCS Modbus TCP register list* **v3.8** ([spreadsheet on Victron Energy](https://www.victronenergy.com/upload/documents/EVCS-Modbus-TCP-register-list-v3.8.xlsx); link also in the YAML template).
- **Tested:** Firmware **v2.05**, **single-phase** supply. **Per-phase power** sensors (**Power Phase 1/2/3**) are created only when you set **Number of phases** to **3** in the integration; with **1** phase they are omitted (total **Power** remains available).

Contributed by **Sean Lano** ([@seanlano](https://github.com/seanlano)) in [PR #45](https://github.com/TCzerny/ha-modbus-manager/pull/45).

## Configuration

| Parameter | Description |
|-----------|-------------|
| **Number of phases** | `1` or `3`. **`Power Phase 1`**, **`Power Phase 2`**, **`Power Phase 3`** are only registered when **`3`** is selected; with **`1`**, use the aggregate **Power** sensor instead. |
| **Charging Station has a screen?** | `Yes` / `No`. Enables display-related controls (backlight, timeout, control via display) when `Yes`. |
| **Firmware version** | Currently **2.05** (aligned with register list v3.8). |

Default Modbus **slave ID** is **1** (adjust if your installation differs). The YAML **`version`** field for this template is **0.1** (template revision inside the integration, not the Home Assistant integration release).

## Holding registers (FC3)

Victron’s TCP map is accessed with **function code 3** (read/write holding) in Home Assistant. Read-only values from the spreadsheet are still exposed as **`input_type: holding`** reads—this matches pymodbus / HA Modbus, not an error in the template.

## Features (summary)

- **Diagnostics:** product ID, serial, raw firmware, device name, temperatures, reboot info.
- **Measurements:** total energy, session energy/time, current, total power, per-phase power (all three phase sensors only if **3 phases** is configured).
- **Status:** mapped charging state + raw code; binary sensors for EV connected and error band.
- **Controls:** charging current setpoint, enable, auto-start, mode (manual/auto/scheduled), light ring brightness, min current, calibration, restart; display options when a screen is present.

## Safety

Do not raise the **maximum installation current** beyond the electrical rating of the installation. The template exposes **maximum current** as read-only in Home Assistant; change limits via Victron’s local UI or app where required.
