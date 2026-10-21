# AEFA EVSE

> **General documentation (Wiki):** [User Guide](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide) · [Template reference](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference) · [Capabilities and limits](https://github.com/TCzerny/ha-modbus-manager/wiki/Capabilities-and-Limits) · [Local customization](https://github.com/TCzerny/ha-modbus-manager/wiki/Local-Customization)

## Overview

**Needs testing.** The register map is in the integration, with limited field checks. Please report issues before treating it as fully supported.

Modbus TCP template for AEFA EVSE hardware sold under EM2GO, Greenlight GNLT, evpartner e-Vision, IGLU Kallik, Voltant AMPHAWK, and ANS/Honors. Other faceplates may use the same map.

Tested with **Greenlight EVB07** and **EVE03**. Other models in the family are not validated.

- **Register reference:** [EM2GO Home Wallbox Modbus register map](https://wallboxcenter.de/wp-content/uploads/2024/06/EM2GO-Home-Wallbox-11kw-Modbus-Register.pdf)
- **Default slave ID:** 255
- **Default prefix:** `AEFA`

## Configuration

Setup asks for a power rating. That choice sets the phase count and the current-limit range:

| Model | Phases | Current |
| --- | ---: | --- |
| 22 kW, three phases | 3 | 6–32 A |
| 16 kW, three phases | 3 | 6–25 A |
| 11 kW, three phases | 3 | 6–16 A |
| 7 kW, single phase | 1 | 6–32 A |
| 3.5 kW, single phase | 1 | 6–16 A |

L2 entities are created when the selected model has at least two phases. L3 entities are created for three-phase models.

## What it exposes

Sensors cover EVSE state, cable state, error code, charge current, voltage, active power, session and total energy, and the EVSE, cable, and minimum current limits. Controls cover the Modbus current limit, fallback current, communication timeout, plug-and-charge, start, stop, and phase count. Binary sensors cover vehicle connected, charging active, and fault.
