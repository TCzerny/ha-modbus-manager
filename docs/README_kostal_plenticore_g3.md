# KOSTAL PLENTICORE G3 template

## Overview

This template covers the Modbus TCP register map of **KOSTAL PLENTICORE G3** hybrid inverters: device information, inverter state, PV inputs, AC side, battery, the connected power meter and the energy counters. It reads holding registers (FC03) and, only if you enable the optional battery control, writes registers 1038/1040/1042 (FC16).

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

## Battery control (optional)

The template has three number controls for external battery management (spec section 3.4). They are **disabled by default**; enable them in the entity settings.

| Control | Register | Range | Notes |
|---|---|---|---|
| Battery Charge Limit | 1038 | 0 … BMS max charge power (1076; 30000 W while that sensor is disabled) | Reads back the effective limit |
| Battery Discharge Limit | 1040 | 0 … BMS max discharge power (1078; 30000 W while that sensor is disabled) | `0` still lets the inverter's own consumption (about 260 W on a G3 M, FW 3.07.03) come from the battery |
| Battery Minimum SoC | 1042 | 5 … 100 | Written as at most the current SoC; reads back the effective value (the web UI minimum after a fallback) |

**Requirements**

- In the web UI, set *Battery management* to external control via Modbus (register 1080 = 2). Otherwise the controls are unavailable (checked with the medium scan group, every 30 s by default; keep the *Battery Management Mode* sensor enabled, without it the check is skipped). Keep *Battery SoC* enabled as well; without it every write of the minimum SoC is refused.
- After upgrading from the read-only template, enable the *Battery Max Charge Power (BMS)* and *Battery Max Discharge Power (BMS)* sensors. They set the limits' maximum; new installs have them enabled.
- The inverter follows these registers only while it keeps receiving writes within the timeout set in the web UI (default 30 s). The timeout is shared by all registers 1024–1044, and any write to one of them resets it. Keep it at 30 s or more: the group writes every 15 s, so 30 s leaves room for one missed round.

**How it works** (see [cyclic writes](KEEPALIVE.md))

- Setting a control writes it once. The value is also stored for the keepalive group **Battery control**.
- The group switch (`Battery control`, starts off after every restart) rewrites all stored values every 15 s, 1 s apart.
- Turning the switch off stops the writes. The inverter returns to its own control after the timeout. Nothing is written on switch-off, unload or shutdown.
- The minimum SoC is written as at most the latest SoC reading, on the first write from the entity and on every cyclic write. A target above the current SoC is accepted: the SoC is written, the target is stored, and the cyclic writes follow the SoC up to the target. A minimum SoC equal to the SoC holds the battery (the same value `kostal_modbus_control`'s Block Discharge writes; stable on the test unit). A minimum SoC above the current SoC disconnects the battery while *Use sleep mode* is enabled in the battery settings (on the test unit twice followed by a battery FAULT that needed an inverter restart); with sleep mode disabled the test unit only ran the 10-minute FeedIn/GridPreCheck cycle. The BMS can correct the SoC down by a whole step without any current (15 → 14 % on the test unit); the minimum then stays above the SoC until the next round, up to 15 s plus the poll delay. If the SoC reading is older than 30 s, unavailable, or the result would be below 5 %, the write is refused, and a cyclic round stops the whole group including the limits (at a SoC below 5 % with a minimum SoC set).
- The limits read back the effective value. A value above the inverter's own limit reads back lower, which is accepted, also on the first write (for example 29000 W reads back about 15.3 kW on a G3 M). Any lower read-back is accepted, so a write the inverter ignores while it still reads a lower value is not detected. After a fallback the register reads the inverter's own limit again (about 15.3–15.9 kW on the test unit); three rounds in a row with that reading stop the group, but only if the requested limit is more than 100 W below the inverter's own limit.

**Run only one writer.** Another integration or automation that writes any of 1024–1044 keeps this template's values alive, and the other way round. Disable the other writer before turning the group on.

Not included: AC setpoints 1024/1026/1030 (BI/MP only according to the spec; 1026 has no effect on the G3 M), the DC setpoint 1034, the maximum SoC 1044, and the section 3.5 limits 1280–1288.

## References

- KOSTAL: *Interface description MODBUS (TCP) & SunSpec with control information*, revision 2.9 (17.07.2026)
- KOSTAL PLENTICORE G3 operating manual, chapter 15 (external battery control)
