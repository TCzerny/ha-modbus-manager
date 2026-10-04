# inepro PRO380-Mod template

## Overview

This read-only template supports the **inepro PRO380-Mod** three-phase energy meter. It uses Modbus RTU holding-register reads (FC03), default slave ID `1`, and the V1.18 multi-register address area. Float values are IEEE-754 Float ABCD: big-endian bytes and words, with no word swap.

Hardware validation was performed on a Solar-Log branded PRO380-Mod matching the inepro PRO380-Mod register interface. This validates the implemented transactions on that unit; it does not claim compatibility with other variants or firmware.

## Included measurements

The template exposes phase voltage and current, grid frequency, total and per-phase active power, total and directional active energy, plus total and per-phase power factor. All implemented values are documented Float32 holding-register measurements; the energy counters use Home Assistant's `total_increasing` state class.

## Power-factor transaction boundary

The documentation describes the `0x5000`–`0x5030` multi-register area. During hardware validation, FC03 `0x502A` with count `8` timed out, while reads of `0x502A` count `2` and `0x502C` count `6` succeeded. The cause is unknown.

The template uses two `read_group` values to preserve the successful reads:

- `pro380_pf_total`: Total Power Factor at `0x502A`, count 2, every 300 seconds.
- `pro380_pf_phases`: L1/L2/L3 Power Factor at `0x502C`, count 6, every 60 seconds.

The separate groups prevent the optimizer from merging them into the known-failing count-8 request when both intervals are due.

## References

- [inepro PRO380-Mod product page](https://www.ineprometering.com/product/pro380-mod-electricity-meter)
- [PRO1-Mod & PRO380-Mod Modbus User Manual V1.18](https://zeben.pt/download/ditSZmxWUDEwT2MrSno5WGVRd3B6RjRpcmxuM3d1QTR1SS8xeVlJSDVKSzNrWXpua0FJYko0YmphekRlM0Ria1F0WWJIQU5HdmpERmNBV3R5V2FQTldtTWZKZ3ViVkJKeG1CTWNjN1VmYmZXejArS2U2SytGRXAzdVAweUxmYXY%3D)
