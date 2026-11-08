# KOSTAL Smart Energy Meter template (read-only)

## Overview

This read-only template covers the Modbus TCP interface of the **KOSTAL Smart Energy Meter (KSEM G1/G2)**: device information, total and per-phase instantaneous values, energy counters, and the KOSTAL energy flow block. It uses holding-register reads (FC03) only.

Default connection: TCP port **502**, unit ID **1**. The Modbus TCP slave must be enabled in the KSEM web UI. With TLS enabled the KSEM listens on port 802.

Field validation (08.11.2026): KSEM G2 (HWv3), firmware 2.7.2. Every field was first read with raw FC03 requests. The template then ran in Modbus Manager 1.3.12 on Home Assistant 2026.11: all 31 default entities came up with values, and the energy counters match an existing core Modbus YAML configuration and the KOSTAL inverter's own meter registers exactly. KSEM G1 is not validated.

## Encoding

- All multi-register values are big-endian, most significant word first (`byte_order: big`, `swap: none`).
- The internal registers use fixed scaling: 0.1 W / var / VA, 0.001 A / V / Hz, power factor 0.001, energy 0.1 Wh. Import (+) and export (−) are separate unsigned values.
- The SunSpec meter model (40000+) uses dynamic scale factors (`*_SF`), so the template does not use it.

## Energy counters (uint64)

The KSEM energy counters (0x0200–0x0317) are `uint64` in 0.1 Wh. Modbus Manager has no `uint64` data type, so the template reads the **lower 32 bits** at address + 2 as `uint32`. That is exact up to 429.4 MWh per counter, which a household meter will not reach. The KSEM accepted these reads that start inside a 64-bit field. If `uint64` support is added later, the counters can switch to the full width without changing their `unique_id`.

## Energy flow block

The static block at 40960 (KSEM SW ≥ 2.6.0) holds the KOSTAL system as the KSEM sees it: grid, inverter AC, PV DC, home consumption, battery (negative while charging), system SoC, wallbox, and a curtailment flag. Generators outside the KOSTAL system (for example a second inverter brand) are not part of it.

## Entities

31 entities are enabled by default: grid power and frequency, per-phase active power, current and voltage, import/export energy, the energy flow block, and device info. Reactive and apparent values, power factors, per-phase energy and wallbox values are present but disabled by default.

## References

- KOSTAL: *KSEM G1/G2 Interface Beschreibung MODBUS*, 13.03.2025, valid for SW 2.6.0
