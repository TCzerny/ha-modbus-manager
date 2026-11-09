# KOSTAL PLENTICORE G3 template (read-only)

## Overview

This read-only template covers the Modbus TCP register map of **KOSTAL PLENTICORE G3** hybrid inverters: device information, inverter state, PV inputs, AC side, battery, the connected power meter and the energy counters. It uses holding-register reads (FC03) only and writes nothing.

Default connection: TCP port **1502**, unit ID **71**. Modbus must be enabled in the inverter's web UI under *Settings > Modbus/SunSpec (TCP)*.

Field validation (read only, 08.11.2026): PLENTICORE G3 M, UI/FW 3.07.03.27599, BYD Battery-Box Premium HVS, KOSTAL Smart Energy Meter. Every read range the optimizer can build from this template was read successfully on that unit, and the decoded values were checked against each other (phase sum vs. total AC power, battery current × voltage vs. battery power, generation energy vs. total yield). The template was then run in Modbus Manager 1.3.12 on Home Assistant 2026.11 against the same inverter, alongside two other Modbus clients: all 61 default entities came up with values, and they match the KOSTAL REST integration (`kostal_plenticore`) within rounding (AC power, SoC, battery power, home consumption from PV, inverter state). Other G3 sizes, MP G3, BI, PLENTICORE plus G2 and PIKO are not validated.

## Encoding

- The template assumes the inverter's default byte order **little-endian (CDAB)** (register 5 = 0, exposed as *Modbus Byte Order*). Float32 values use `swap: word`.
- **U32 values are not consistent.** The U32 values at 0x24, 0x38 and 0x68 are word-swapped like the floats. The U32 values from 0x200 on (512, 527, 529, 577, 586, 1288, 40346, 40354) arrive high word first, even in CDAB mode. Both were confirmed with known values: inverter state 6 = FeedIn, gross capacity 48 Ah, generation energy equal to total yield.
- Strings are big-endian bytes, padded with NUL; the battery manufacturer is padded with spaces.
- Register 588 (battery type) became U32 in G3 FW 3.07.03.27419. The template reads it as U16, which KOSTAL keeps for backwards compatibility. M-TEC (0x10000) therefore does not appear.

## Read boundaries

The inverter answers with exception 2 (illegal data address) when a read starts inside a field (for example in the middle of a string) or covers the undocumented ranges 71–97, 300–319 or 592–607. The register optimizer only merges strictly adjacent registers, so the template never requests those ranges and needs no `read_group`.

## Entities

71 entities are enabled by default (power, energy, battery, battery bank state, temperatures, meter totals, state). Per-phase currents, reactive/apparent power, per-string energy and the battery-management read-backs (1034–1044, 1076/1078, 1280–1288) are present but disabled by default.

Sign conventions from the spec: battery current and power are negative while charging. Meter values at the grid connection are positive for import and negative for feed-in.

## Temperatures and inverter events (SunSpec model 113)

The KOSTAL register map only has the controller board temperature (98). From the SunSpec inverter model 113 (float, at 40122) the template adds cabinet, heat sink and transformer temperature (40162/40164/40166) and the event bitfields `Evt1` (40172, GROUND_FAULT, GRID_DISCONNECT, OVER_TEMP …) and `EvtVnd1` (40176). The floats in this model follow the CDAB setting. Both event fields read 0 on the tested unit, so their word order is assumed to match the floats and is not verified; the raw value stays in the `numeric_value` attribute.

## Battery bank state (SunSpec model 802)

The inverter's SunSpec chain is 1, 103, 113, 120, 123, 160, 203, 802 (at 40415), 65535. From the battery base model 802 the template reads the bank state (`State`, 40437: DISCONNECTED / INITIALIZING / CONNECTED / STANDBY / SOC PROTECTION / SUSPENDING / FAULT), the event bitfield `Evt1` (40441, shown as active flags such as COMMUNICATION_ERROR or OTHER_ALARM, raw value in the `numeric_value` attribute), max/min cell voltage (40452/40455, `CellV_SF` = −3 on the tested unit) and the battery's inverter state request (`ReqInvState`, 40463). Vendor state, vendor events and `SetOp` are present but disabled by default. Enum and bitfield points need no scale factor; 32-bit points arrive high word first like the other U32 values from 0x200 on. On the tested unit the bank state shows STANDBY while a BYD battery idles at its minimum SoC (event 1033 in the inverter log) and FAULT after a failed reconnect from battery sleep mode.

## Why there are no controls

External battery management (registers 1024–1044) falls back to internal control after the timeout set in the web UI unless *some* battery register is written again within that time; any write resets one shared timer. A write-once `number` would silently revert. Section 3.5 (1280–1288) explicitly requires cyclic writes. Battery controls are left out until the integration can rewrite a value periodically.

## References

- KOSTAL: *Interface description MODBUS (TCP) & SunSpec with control information*, revision 2.9 (17.07.2026)
- KOSTAL PLENTICORE G3 operating manual, chapter 15 (external battery control)
