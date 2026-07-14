# Sandi Solar SD-Pro — Modbus RTU Protocol V2.14

> **General documentation (Wiki):** [User Guide](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide) · [Template reference](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference)

> **Related:** [Issue #60](https://github.com/TCzerny/ha-modbus-manager/issues/60) · Product: [SD-Pro 6.5 kW Off-Grid Inverter](https://www.sandisolar.com/product/sd-pro-6-5-kw-off-grid-inverter-with-ai-assistant/)

> **Source document:** [Modbus RTU Protocol V2.14 (xlsx)](https://github.com/user-attachments/files/27947510/Modbus.RTU.Protocol.V2.14-1.xlsx) — register tables below are generated from that file.

## Overview

This document lists **all input and holding registers** from the manufacturer Modbus RTU protocol **V2.14** for Sandi Solar hybrid/off-grid inverters (including the **SD-Pro** series). It is intended as a reference for building a Modbus Manager device template and for integrators using Home Assistant.

**Modbus Manager template status:** **BETA** — [`sandisolar_sd_pro_dynamic.yaml`](../custom_components/modbus_manager/device_templates/sandisolar_sd_pro_dynamic.yaml) provides a minimal read-only set for field testing (Issue #60). This README lists the full protocol; the template implements a subset only.

### Setup (beta template)

1. Add a Modbus Manager device and select **Sandi Solar SD-Pro Off-Grid**.
2. Model: **SD-Pro-6.5** (more `valid_models` can be added later).
3. On the Home Assistant **Modbus** hub used by Modbus Manager: set **delay** or **message wait** to at least **850 ms** (see below).
4. Default **slave ID 1**, **9600 baud** (per protocol).

### Entities included in the beta template (read-only)

| Area | Entities |
|------|----------|
| Status | Inverter status, off-grid / grid-connected / fault binaries |
| Device | Device type code, PV channel count, main error/warning, system fault word 0 |
| Temperature | Inverter, ambient, battery |
| AC / EPS | Inverter V/I, grid frequency, EPS V/I/frequency/active power |
| PV | Total power, PV1–PV2 V/I (per `mppt_count`) |
| Battery | Voltage, SOC, current, temperature |
| Energy | PV energy today / total |

Contributions: copy register definitions from the tables below into the YAML, or open a PR referencing Issue #60.

## Communication parameters

| Parameter | Value |
|-----------|--------|
| Mode | Modbus RTU over RS-485 |
| Default baud rate | 9600 bps |
| Data format | 8 data bits, no parity, 1 stop bit |
| Slave address range | 1–254 (0 = broadcast) |
| Minimum command interval | **850 ms** between requests |
| Max registers per read/write | 125 registers |
| Standard read holding | Function code **0x03** |
| Standard read input | Function code **0x04** |
| Write single holding | Function code **0x06** |
| Write multiple holding | Function code **0x10** |

**Important for Home Assistant / Modbus Manager:**

- Set hub **delay** or **message wait** to at least **850 ms** to match the inverter.
- Register addresses in the tables use the **zero-based address** from the Excel **Register address** column. Verify on hardware before production use.
- Many power/energy values use **uint32/sint32** as **high word + low word** (two consecutive 16-bit registers).
- Notes containing **Single-phase not supported** refer to three-phase (S/T) quantities.

### Non-standard function codes (not normal register reads)

The protocol defines additional function codes for meter data, historical energy, and events. Standard Modbus read (0x03/0x04) integrations **cannot** use these as normal register addresses:

| FC | Purpose |
|----|---------|
| 0x17 | Remote firmware upgrade |
| 0x21 | Read meter data |
| 0x23 | Historical PV energy |
| 0x24 | Historical load energy |
| 0x25 | Historical grid import energy |
| 0x26 | Historical grid export (sell) energy |
| 0x29 | Historical events |

## Protocol change log (from manufacturer document)

| No. | Version | Date (serial) | Summary |
|-----|---------|---------------|---------|
| 1 | V1.00 | 45211 | first edition |
| 2 | V2.00 | 45280 | 1. Redefine the safety parameters of holding332~376 |
| 3 | V2.01 | 45371 | 1. Change the priority setting parameter information holding137~180<br>2. Redefine the calibration coefficient and parameter calibration register holding2000~2624<br>3. Add special parameter definitions for holding181~206 off-grid machines |
| 4 | V2.02 | 45384 | Holding changes:<br>Modification sequence of register numbers 5~19, low register address sends low sequence number<br>Register numbers 121~124 add fault reconnection and grid connection conditions<br>Correct the default value of register number 127~129<br>Register numbers 184 and 186 are now reserved<br>Input changes:<br>The data type of register numbers 14~20 is changed to signed 16-bit |
| 5 | V2.03 | 45394 | Holding changes:<br>Register No. 187 off-grid stop discharge recovery SOC value range is corrected to 10~100<br>Register number 189AC charging limit current value range is corrected to 10~1000<br>Register number 231 adds Bluetooth enable<br>Register number 193 lead-acid battery subtype option 7N16 changed to N13<br>Input changes:<br>Register number 63 adds the number of PV channels |
| 6 | V2.04 | 45410 | Holding changes:<br>Register number 4 baud rate remove 115200 option<br>Register number 72 increases the maximum power draw percentage of the inverter<br>Register number 70 increases the reactive power percentage response time<br>Register numbers 207~211 add buzzer switch, overload to bypass enable, off-grid output mode, balanced charging voltage and parallel mode in sequence.<br>Input changes:<br>The corresponding positions of the variable names of register numbers 145 and 146 are opposite. The positions are now swapped.<br>Register numbers 139 battery SOC and 140 battery voltage are now reserved. |
| 7 | V2.05 | 45437 | Holding changes:<br>Register No. 106 Off Grid Voltage Added Options 220V and 200V<br>Register numbers 112 and 113 add zero-ground relay control enable and fan detection instructions in sequence.<br>Register numbers 296, 297 and 298 add over-frequency and over-load reduction fast recovery enable, under-frequency load fast recovery enable and under-frequency load hysteresis mode enable in sequence.<br>Register numbers 312~314 add G100 safety over-power detection enable, G100 safety internal parameter clearing and under-frequency loading hysteresis mode enable in sequence.<br>Register number 345 adds Q(V) reactive bias percentage<br>Register numbers 346 and 347 modify description and unit<br>Register numbers 368 and 369 add QP function cut-in voltage and QP function cut-out voltage<br>Register numbers 381 and 382 add the Italian safety option enable bit and capacitive reactive power response time<br>Input changes:<br>Register numbers 96~102 add diesel generator voltage, current and frequency<br>Register number 106 adds fan speed<br>Register numbers 357~368 add the apparent power and active power of the diesel generator<br>Register number 536 adds CAN detection flag bit |
| 8 | V2.06 | 45490 | Holding changes:<br>Register number 77MPPT mode modification status 2 is described as parallel MPPT mode<br>Register number 383 adds CEI external instruction<br>Register number 212 adds the parallel CAN communication address<br>Register number 213 adds parallel device type<br>Register number 116 adds AFCI error clear command<br>Register number 232 adds wifi data update notification<br>Register number 233 Add wifi to restore factory settings<br>Register numbers 129, 130 and 131 modify the register description<br>Input changes:<br>Register 0 inverter operating status added 0x06: self-charging status |
| 9 | V2.07 | 45506 | Holding changes:<br>Register number 214 adds BMS communication method<br>Register number 215 adds grid power compensation<br>Register number 377 adds DCI injection enable<br>Register number 378 adds DCI injection value<br>Register number 201LCD setting enable bit adds bit 7 grid feed enable<br>Register number 125 battery type adds lithium battery without communication type (applicable to off-grid machines) |
| 10 | V2.08 | 45523 | Holding changes:<br>Scope modification:<br>Register number 90~92 modified value range<br>Register number 94~95 modified value range<br>Delete register numbers 96~97<br>Register number 101~104 modified value range<br>Register number 106 modified value range<br>Register number 121~124 modified value range<br>Register number 127 modified value range<br>Redefine safety parameter range |
| 11 | V2.09 | 45546 | Holding changes:<br>The modified value range of register numbers 139~141 is 10~100<br>Register number 2001 adds instruction 4: parallel CAN detection<br>Add collector status to register number 234~235<br>Register number 499 adds startup diagnostic function<br>Register numbers 3000~3052 add peak clipping function related registers<br>Input changes:<br>Register number 537 adds parallel CAN detection flag bit<br>Register numbers 3000~3015 add installation diagnosis related registers |
| 12 | V2.10 | 45623 | Holding changes:<br>Register number 100 adds a boot navigation flag<br>Register number 68 adds screen type<br>Register number 126 battery communication protocol modified definition<br>Modify register numbers 3000~3105, used for peak clipping function, new model time period and control mode related registers<br>Register numbers 5000~5008 add EMS control coefficients<br>Register number 384 adds QP function - response time<br>Added option 5 (No Bat mode) to register 125<br>Register 132 increases the high voltage battery voltage rating<br>Input changes:<br>Register number 170 modifies the definition of battery manufacturer information<br>Register numbers 419~430 add online electricity (selling electricity), purchased electricity (selling electricity) and self-sufficient electricity |
| 13 | V2.11 | 45628 | Holding changes:<br>Modify the register definitions of register numbers 3008, 3018, 3028, 3038, 3048, 3058, 3068, 3078, 3088, and 3098<br>Register number 3005 added to clear all time periods |
| 14 | V2.12 | 45645 | Holding changes:<br>Register number 126 modified definition<br><br>Input changes:<br>Register numbers 450~498 add parallel data<br>Register number 170 modified definition |
| 15 | V2.13 | 45645 | Input changes:<br>Register numbers 491~498 increase battery charging and discharging energy |
| 16 | V2.14 | 45665 | Input changes:<br>Register number 3014 modified definition<br>Register number 3016 adds meter wiring fault comparison table |

## UART protocol summary

| No. | Item | Description | Details |
|-----|------|-------------|---------|
| 1 | Data format |  | Valid slave address range is 0 - 254 decimal.<br>Each slave device is assigned an address in the range 1 - 254.<br>0 is the broadcast address<br>Each holding and input register is a 16-bit (two bytes) unsigned integer; |
| 2 | Command format | Function code 0x3<br>Read holding register |  |
| 3 |  | Function code 0x4<br>Read input register |  |
| 4 |  | Function code 0x6<br>Preset a single register |  |
| 5 |  | Function code 0x10<br>Preset multiple registers |  |
| 6 | Device transport mode and frame | RTU mode | When the controller is set up to communicate on a Modbus network using RTU (Remote Terminal Unit) mode, each 8-bit byte in the message contains two 4-digit hexadecimal characters. Each message must be transmitted in a continuous stream. |
| 7 |  | The format of each byte in RTU mode | Coding system: eight-digit binary, hexadecimal 0-9, A-F<br>Each contains two hexadecimal digits<br>eight-bit message field |
| 8 |  | Number of characters per | a start bit<br>8 data bits, least significant bit sent first<br>No parity<br>a stop bit<br>Error checking field: Cyclic Redundancy Check (CRC) |
| 9 |  | Transmission baud rate | Default baud rate: 9600 bps |
| 10 |  | Minimum CMD period (RS485 timeout) | 850ms<br>Wait at least 850ms after the last CMD to send a new CMD |
| 11 |  | Maximum data length definition | The maximum read data length is 125 words in the read command;<br>   The maximum update data length in the default command is 125 words. |
|  | Function code | 0x03 | Read holding registers |
|  |  | 0x04 | Read input registers |
|  |  | 0x06 | Write single holding register |
|  |  | 0x10 | Write multiple holding registers |
|  |  | 0x17 | Remote firmware upgrade |
|  |  | 0x21 | Read meter data |
|  |  | 0x23 | Read historical PV energy |
|  |  | 0x24 | Read historical load energy |
|  |  | 0x25 | Read historical grid import energy |
|  |  | 0x26 | Read historical grid export (sell) energy |
|  |  | 0x29 | Read historical events |

## Input registers (function code 0x04)

**Total:** 422 registers

| Address | Group | Variable name | Description | Data type | Unit / scale | Notes |
|---------|-------|---------------|-------------|-----------|--------------|-------|
| 0 | Group 1 — System operating parameters | Inverter Status | Inverter operating status | uint16 |  | 0x00: Waiting state<br>0x01: Grid-connected status<br>0x02: Off-grid status<br>0x03: Fault status<br>0x04: Burning status<br>0x05: Bypass status<br>0x06: Self-charging state |
| 1 | Group 1 — System operating parameters | StartDelayTime | Countdown to grid connection | uint16 | 1s |  |
| 2 | Group 1 — System operating parameters | INV_VolR | Inverter voltage | uint16 | 0.1V |  |
| 3 | Group 1 — System operating parameters | INV_VolS | Inverter voltage | uint16 | 0.1V |  |
| 4 | Group 1 — System operating parameters | INV_VolT | Inverter voltage | uint16 | 0.1V |  |
| 5 | Group 1 — System operating parameters | INV_CurrR | Inverter current | sint16 | 0.1A |  |
| 6 | Group 1 — System operating parameters | INV_CurrS | Inverter current | sint16 | 0.1A |  |
| 7 | Group 1 — System operating parameters | INV_CurrT | Inverter current | sint16 | 0.1A |  |
| 8 | Group 1 — System operating parameters | Bus1 Voltage | Bus1 internal voltage | uint16 | 0.1V |  |
| 9 | Group 1 — System operating parameters | Bus2 Voltage | Bus2 internal voltage | uint16 | 0.1V |  |
| 10 | Group 1 — System operating parameters | Inv_Temp | Inverter temperature | sint16 | 0.1C° |  |
| 11 | Group 1 — System operating parameters | Boost_Temp | Inverter internal IPM temperature | sint16 | 0.1C° |  |
| 12 | Group 1 — System operating parameters | LLC _Temp | LLC radiator temperature | sint16 | 0.1C° |  |
| 13 | Group 1 — System operating parameters | Bat_Temp | battery temperature | sint16 | 0.1C° | Lead-acid battery NTC sampling temperature |
| 14 | Group 1 — System operating parameters | TA_Temp | ambient temperature | sint16 | 0.1C° |  |
| 15 | Group 1 — System operating parameters | DCV-R | R phase DC voltage component | sint16 | 1mV |  |
| 16 | Group 1 — System operating parameters | DCV-S | S phase DC voltage component | sint16 | 1mV |  |
| 17 | Group 1 — System operating parameters | DCV-T | T phase DC voltage component | sint16 | 1mV |  |
| 18 | Group 1 — System operating parameters | DCI-R | R phase DC current component | sint16 | 1mA |  |
| 19 | Group 1 — System operating parameters | DCI-S | S phase DC current component | sint16 | 1mA |  |
| 20 | Group 1 — System operating parameters | DCI-T | T phase DC current component | sint16 | 1mA |  |
| 21 | Group 1 — System operating parameters | ISO阻值 | ISO resistance | uint16 | 1kΩ |  |
| 22 | Group 1 — System operating parameters | GFCI | leakage current | uint16 | 1mA |  |
| 23 | Group 1 — System operating parameters | HistoryEventCnt | Number of historical event records | uint16 |  |  |
| 24 | Group 1 — System operating parameters | Systemfault word0 | System failure word0 | uint16 |  |  |
| 25 | Group 1 — System operating parameters | Systemfault word1 | System failure word1 | uint16 |  |  |
| 26 | Group 1 — System operating parameters | Systemfault word2 | System failure word2 | uint16 |  |  |
| 27 | Group 1 — System operating parameters | Systemfault word3 | System failure word3 | uint16 |  |  |
| 28 | Group 1 — System operating parameters | Systemfault word4 | System failure word4 | uint16 |  |  |
| 29 | Group 1 — System operating parameters | Systemfault word5 | System failure word5 | uint16 |  |  |
| 30 | Group 1 — System operating parameters | Systemfault word6 | System failure word6 | uint16 |  |  |
| 31 | Group 1 — System operating parameters | Systemfault word7 | System failure word7 | uint16 |  |  |
| 32 | Group 1 — System operating parameters | InvMainErrorCode | Inverter main fault code | uint16 |  |  |
| 33 | Group 1 — System operating parameters | InvMainWarnCode | Inverter main warning code | uint16 |  |  |
| 34 | Group 1 — System operating parameters | InvErrorSubCode | Inverter sub-fault code | uint16 |  |  |
| 35 | Group 1 — System operating parameters | InvWarnSubCode | Inverter sub-warning code | uint16 |  |  |
| 36 | Group 1 — System operating parameters | DeviceType | Device type | uint16 |  |  |
| 37 | Group 1 — System operating parameters | 预留 | reserved |  |  |  |
| 38 | Group 1 — System operating parameters | DeratingModeFlag | Download mode flag | uint16 |  | 0: No load reduction; 1: Bus high voltage; 2: Grid low voltage; 3: Grid high voltage<br>4: High frequency; 5: BOOST high temperature<br>6: Inverter high temperature; 7: Ambient high temperature<br>8: Loading speed; 9: Reactive power<br>10: The load is too large; 11: Underfrequency loading<br>12: Active power setting limit; 13: Multi-machine anti-reverse flow; 14: Single-machine anti-reverse flow<br>15: Zero current mode; 16: Aging setting limit; 17: Line impedance limit<br>18: Fan abnormality; 19: CT abnormality<br>20: LLC overtemperature; 21: Battery discharge setting limit; 22: Electricity sales setting limit<br>23: PV power out of range |
| 39 | Group 1 — System operating parameters | PowerCosFlag | lead lag flag | uint16 |  | To be determined |
| 40 | Group 1 — System operating parameters | Bus1 Voltage | Positive Bus voltage | uint16 | 0.1V |  |
| 41 | Group 1 — System operating parameters | Bus1 Voltage | Negative Bus Voltage | uint16 | 0.1V |  |
| 42 | Group 1 — System operating parameters | Vac-R | Three-phase grid voltage | uint16 | 0.1V | A single camera only displays R parameters |
| 43 | Group 1 — System operating parameters | Iac-R | Three-phase grid output current | sint16 | 0.1A | A single camera only displays R parameters |
| 44 | Group 1 — System operating parameters | Vac-S | Three-phase grid voltage | uint16 | 0.1V |  |
| 45 | Group 1 — System operating parameters | Iac-S | Three-phase grid output current | sint16 | 0.1A |  |
| 46 | Group 1 — System operating parameters | Vac-T | Three-phase grid voltage | uint16 | 0.1V |  |
| 47 | Group 1 — System operating parameters | Iac-T | Three-phase grid output current | sint16 | 0.1A |  |
| 48 | Group 1 — System operating parameters | Vac_RS | Three-phase grid line voltage | uint16 | 0.1V |  |
| 49 | Group 1 — System operating parameters | Vac_ST | Three-phase grid line voltage | uint16 | 0.1V |  |
| 50 | Group 1 — System operating parameters | Vac_TR | Three-phase grid line voltage | uint16 | 0.1V |  |
| 51 | Group 1 — System operating parameters | Fac | Grid frequency | uint16 | 0.01Hz |  |
| 52 | Group 1 — System operating parameters | PF | power factor | sint16 | 0.0001 |  |
| 53 | Group 1 — System operating parameters | RealOPPercent | Actual output power percentage | uint16 | 0.01 | To be determined |
| 54 | Group 1 — System operating parameters | EPS Fac | Off-grid frequency | uint16 | 0.01Hz |  |
| 55 | Group 1 — System operating parameters | EPS Vac1 | Off-grid R phase output voltage | uint16 | 0.1V |  |
| 56 | Group 1 — System operating parameters | EPS Iac1 | Off-grid R phase output current | uint16 | 0.1A |  |
| 57 | Group 1 — System operating parameters | EPS Vac2 | Off-grid S phase output voltage | uint16 | 0.1V |  |
| 58 | Group 1 — System operating parameters | EPS Iac2 | Off-grid S phase output current | uint16 | 0.1A |  |
| 59 | Group 1 — System operating parameters | EPS Vac3 | Off-grid T phase output voltage | uint16 | 0.1V |  |
| 60 | Group 1 — System operating parameters | EPS Iac3 | Off-grid T phase output current | uint16 | 0.1A |  |
| 61 | Group 1 — System operating parameters | 预留 | reserved |  |  |  |
| 62 | Group 1 — System operating parameters | 预留 | reserved |  |  |  |
| 63 | Group 1 — System operating parameters | PvNum | Number of PV channels | uint16 |  |  |
| 64 | Group 1 — System operating parameters | Vpv1 | PV1 voltage | uint16 | 0.1V |  |
| 65 | Group 1 — System operating parameters | PV1Curr | PV1 input current | uint16 | 0.1A |  |
| 66 | Group 1 — System operating parameters | Vpv2 | PV2 voltage | uint16 | 0.1V |  |
| 67 | Group 1 — System operating parameters | PV2Curr | PV2 input current | uint16 | 0.1A |  |
| 68 | Group 1 — System operating parameters | Vpv3 | PV3 voltage | uint16 | 0.1V |  |
| 69 | Group 1 — System operating parameters | PV3Curr | PV3 input current | uint16 | 0.1A |  |
| 70 | Group 1 — System operating parameters | Vpv4 | PV4 voltage | uint16 | 0.1V |  |
| 71 | Group 1 — System operating parameters | PV4Curr | PV4 input current | uint16 | 0.1A |  |
| 72 | Group 1 — System operating parameters | Vpv5 | PV5 voltage | uint16 | 0.1V |  |
| 73 | Group 1 — System operating parameters | PV5Curr | PV5 input current | uint16 | 0.1A |  |
| 74 | Group 1 — System operating parameters | Vpv6 | PV6 voltage | uint16 | 0.1V |  |
| 75 | Group 1 — System operating parameters | PV6Curr | PV6 input current | uint16 | 0.1A |  |
| 76 | Group 1 — System operating parameters | Vpv7 | PV7 voltage | uint16 | 0.1V |  |
| 77 | Group 1 — System operating parameters | PV7Curr | PV7 input current | uint16 | 0.1A |  |
| 78 | Group 1 — System operating parameters | Vpv8 | PV8 voltage | uint16 | 0.1V |  |
| 79 | Group 1 — System operating parameters | PV8Curr | PV8 input current | uint16 | 0.1A |  |
| 80 | Group 1 — System operating parameters | Vpv9 | PV9 voltage | uint16 | 0.1V |  |
| 81 | Group 1 — System operating parameters | PV9Curr | PV9 input current | uint16 | 0.1A |  |
| 82 | Group 1 — System operating parameters | Vpv10 | PV10 voltage | uint16 | 0.1V |  |
| 83 | Group 1 — System operating parameters | PV10Curr | PV10 input current | uint16 | 0.1A |  |
| 84 | Group 1 — System operating parameters | Vpv11 | PV11 voltage | uint16 | 0.1V |  |
| 85 | Group 1 — System operating parameters | PV11Curr | PV11 input current | uint16 | 0.1A |  |
| 86 | Group 1 — System operating parameters | Vpv12 | PV12 voltage | uint16 | 0.1V |  |
| 87 | Group 1 — System operating parameters | PV12Curr | PV12 input current | uint16 | 0.1A |  |
| 88 | Group 1 — System operating parameters | Vpv13 | PV13 voltage | uint16 | 0.1V |  |
| 89 | Group 1 — System operating parameters | PV13Curr | PV13 input current | uint16 | 0.1A |  |
| 90 | Group 1 — System operating parameters | Vpv14 | PV14 voltage | uint16 | 0.1V |  |
| 91 | Group 1 — System operating parameters | PV14Curr | PV14 input current | uint16 | 0.1A |  |
| 92 | Group 1 — System operating parameters | Vpv15 | PV15 voltage | uint16 | 0.1V |  |
| 93 | Group 1 — System operating parameters | PV15Curr | PV15 input current | uint16 | 0.1A |  |
| 94 | Group 1 — System operating parameters | Vpv16 | PV16 voltage | uint16 | 0.1V |  |
| 95 | Group 1 — System operating parameters | PV16Curr | PV16 input current | uint16 | 0.1A |  |
| 96 | Group 1 — System operating parameters | uwGEN_v_R | Diesel generator voltage R | uint16 | 0.1V |  |
| 97 | Group 1 — System operating parameters | uwGEN_i_R | Diesel generator current R | uint16 | 0.1A |  |
| 98 | Group 1 — System operating parameters | uwGEN_v_S | Diesel generator voltage S | uint16 | 0.1V |  |
| 99 | Group 1 — System operating parameters | uwGEN_i_S | Diesel generator current S | uint16 | 0.1A |  |
| 100 | Group 1 — System operating parameters | uwGEN_v_T | Diesel generator voltage T | uint16 | 0.1V |  |
| 101 | Group 1 — System operating parameters | uwGEN_i_T | Diesel generator current T | uint16 | 0.1A |  |
| 102 | Group 1 — System operating parameters | uwGEN_Freq | Diesel generator frequency | uint16 | 0.01Hz |  |
| 103 | Group 1 — System operating parameters | 预留 | reserved |  |  |  |
| 104 | Group 1 — System operating parameters | 预留 | reserved |  |  |  |
| 105 | Group 1 — System operating parameters | 预留 | reserved |  |  |  |
| 106 | Group 1 — System operating parameters | fan_speed | fan speed | uint16 | rpm | rpm |
| 107 | Group 1 — System operating parameters | Time total H | total working time | uint32 | 0.5min |  |
| 108 | Group 1 — System operating parameters | Time total L |  |  |  |  |
| 109 | Group 1 — System operating parameters | Debuge1 | Main DSP debugging parameters | uint16 |  |  |
| 110 | Group 1 — System operating parameters | Debuge2 | Main DSP debugging parameters | uint16 |  |  |
| 111 | Group 1 — System operating parameters | Debuge3 | Main DSP debugging parameters | uint16 |  |  |
| 112 | Group 1 — System operating parameters | Debuge4 | Main DSP debugging parameters | uint16 |  |  |
| 113 | Group 1 — System operating parameters | Debuge5 | Main DSP debugging parameters | uint16 |  |  |
| 114 | Group 1 — System operating parameters | Debuge6 | Main DSP debugging parameters | uint16 |  |  |
| 115 | Group 1 — System operating parameters | Debuge7 | Main DSP debugging parameters | uint16 |  |  |
| 116 | Group 1 — System operating parameters | Debuge8 | Main DSP debugging parameters | uint16 |  |  |
| 117 | Group 1 — System operating parameters | Debuge9 | Debug parameters from DSP | uint16 |  |  |
| 118 | Group 1 — System operating parameters | Debuge10 | Debug parameters from DSP | uint16 |  |  |
| 119 | Group 1 — System operating parameters | Debuge11 | Debug parameters from DSP | uint16 |  |  |
| 120 | Group 1 — System operating parameters | Debuge12 | Debug parameters from DSP | uint16 |  |  |
| 121 | Group 1 — System operating parameters | Debuge13 | Debug parameters from DSP | uint16 |  |  |
| 122 | Group 1 — System operating parameters | Debuge14 | Debug parameters from DSP | uint16 |  |  |
| 123 | Group 1 — System operating parameters | Debuge15 | Debug parameters from DSP | uint16 |  |  |
| 124 | Group 1 — System operating parameters | Debuge16 | Debug parameters from DSP | uint16 |  |  |
| 125 | Group 2 | Priority | Current battery priority | uint16 |  | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 126 | Group 2 | Battery Type | Battery Type | uint16 |  | 0: Lead-acid battery<br>1: Lithium battery<br>2: User defined 1<br>3: User defined 2<br>4: User defined 3 |
| 127 | Group 2 | Vbat | battery voltage | uint16 | 0.1V | Lithium battery or lead acid |
| 128 | Group 2 | SOC | Battery SOC | uint16 | 0.01 | Lithium battery or lead acid |
| 129 | Group 2 | BatVolt_DSP | DSP samples battery voltage | uint16 | 0.1V | Lithium battery or lead acid |
| 130 | Group 2 | BMS_Status | battery status | uint16 |  | Lithium battery upload information |
| 131 | Group 2 | BMS_Error1 | Battery error message 1 | uint16 |  | Lithium battery upload information |
| 132 | Group 2 | BMS_Error2 | Battery error message 2 | uint16 |  | Lithium battery upload information |
| 133 | Group 2 | BMS_Error3 | Battery error message 3 | uint16 |  | Lithium battery upload information |
| 134 | Group 2 | BMS_Error4 | Battery error message 4 | uint16 |  | Lithium battery upload information |
| 135 | Group 2 | BMS_WarnInfo1 | Battery alarm 1 | uint16 |  | Lithium battery upload information |
| 136 | Group 2 | BMS_WarnInfo2 | Battery alarm 2 | uint16 |  | Lithium battery upload information |
| 137 | Group 2 | BMS_WarnInfo3 | Battery alarm 3 | uint16 |  | Lithium battery upload information |
| 138 | Group 2 | BMS_WarnInfo4 | Battery alarm 4 | uint16 |  | Lithium battery upload information |
| 139 | Group 2 | 预留 | reserved |  |  |  |
| 140 | Group 2 | 预留 | reserved |  |  |  |
| 141 | Group 2 | BMS_BatteryCurr | battery current | sint16 | 0.01A |  |
| 142 | Group 2 | BMS_BatteryTemp | battery temperature | sint16 | 0.1C° |  |
| 143 | Group 2 | BMS_MaxChargeCurr | The battery allows maximum charging current | uint16 | 0.1A |  |
| 144 | Group 2 | BMS_MaxDischargeCurr | The battery allows maximum discharge current | uint16 | 0.1A |  |
| 145 | Group 2 | BMS_GaugeFCC | Battery rated capacity | uint16 | 0.1Ah |  |
| 146 | Group 2 | BMS_GaugeRM | Battery real-time capacity | uint16 | 0.1Ah |  |
| 147 | Group 2 | BMS_SoftVersion_Major | Battery upload software main version | uint16 |  |  |
| 148 | Group 2 | BMS_SoftVersion_Minor | Battery upload software minor version | uint16 |  |  |
| 149 | Group 2 | BMS_HardVersion | Battery upload hardware version | uint16 |  |  |
| 150 | Group 2 | BMS_DeltaVolt | Battery cell pressure difference | uint16 | 0.001V |  |
| 151 | Group 2 | BMS_CycleCnt | Battery cycle times | uint16 |  |  |
| 152 | Group 2 | BMS_SOH | SOH | uint16 |  |  |
| 153 | Group 2 | BMS_ConstantVolt | Recommended battery charging voltage | uint16 | 0.1V |  |
| 154 | Group 2 | uwLVVoltage_Pack | LV voltage | uint16 | 0.1V |  |
| 155 | Group 2 | BMS_BMSInfo | BMS information | uint16 |  |  |
| 156 | Group 2 | BMS_PackInfo | Pack information | uint16 |  |  |
| 157 | Group 2 | MaxCellVol | Maximum battery cell voltage | uint16 | 0.001V |  |
| 158 | Group 2 | MinCellVol | Minimum cell voltage of battery | uint16 | 0.001V |  |
| 159 | Group 2 | ModuleNum | Number of batteries connected in parallel | uint16 |  |  |
| 160 | Group 2 | CellNum | Number of battery cells | uint16 |  |  |
| 161 | Group 2 | MaxVoltCellNo | Highest voltage unit number | uint16 |  |  |
| 162 | Group 2 | MinVoltCellNo | Lowest voltage unit number | uint16 |  |  |
| 163 | Group 2 | MaxTemprCell_10T | Maximum cell temperature | sint16 | 0.1C° |  |
| 164 | Group 2 | MinTemprCell_10T | Minimum cell temperature | sint16 | 0.1C° |  |
| 165 | Group 2 | MaxTemprCellNo | Maximum voltage temperature number | uint16 |  |  |
| 166 | Group 2 | MinTemprCellNo | Minimum voltage temperature number | uint16 |  |  |
| 167 | Group 2 | Protect pack ID | Faulty battery address | uint16 |  |  |
| 168 | Group 2 | MaxSOC | Maximum parallel machine SOC | uint16 | 0.01 |  |
| 169 | Group 2 | MinSOC | Minimum parallel machine SOC | uint16 | 0.01 |  |
| 170 | Group 2 | BMSCompany | Battery manufacturer information | uint16 |  | 0: NULL<br>1: Protocol 1<br>2: Protocol 2<br>3: Protocol 3<br>4: Protocol 4 |
| 171 | Group 2 | PowerPackSn | Throughput display battery pack number | uint16 |  |  |
| 172 | Group 2 | DisChargPower H | Cumulative discharge capacity | uint32 | 0.1kwh |  |
| 173 | Group 2 | DisChargPower L | Cumulative discharge capacity |  |  |  |
| 174 | Group 2 | ChargPower H | Accumulated charging capacity | uint32 | 0.1kwh |  |
| 175 | Group 2 | ChargPower L | Accumulated charging capacity |  |  |  |
| 176 | Group 2 | 预留 | reserved |  |  |  |
| 177 | Group 2 | 预留 | reserved |  |  |  |
| 178 | Group 2 | 预留 | reserved |  |  |  |
| 179 | Group 2 | 预留 | reserved |  |  |  |
| 180 | Group 2 | 预留 | reserved |  |  |  |
| 181 | Group 2 | 预留 | reserved |  |  |  |
| 182 | Group 2 | 预留 | reserved |  |  |  |
| 183 | Group 2 | 预留 | reserved |  |  |  |
| 184 | Group 2 | 预留 | reserved |  |  |  |
| 185 | Group 2 | 预留 | reserved |  |  |  |
| 186 | Group 2 | BatDebuge1 | Battery BMS debugging parameters | uint16 |  |  |
| 187 | Group 2 | BatDebuge2 | Battery BMS debugging parameters | uint16 |  |  |
| 188 | Group 2 | BatDebuge3 | Battery BMS debugging parameters | uint16 |  |  |
| 189 | Group 2 | BatDebuge4 | Battery BMS debugging parameters | uint16 |  |  |
| 190 | Group 2 | BatDebuge5 | Battery BMS debugging parameters | uint16 |  |  |
| 191 | Group 2 | BatDebuge6 | Battery BMS debugging parameters | uint16 |  |  |
| 192 | Group 2 | BatDebuge7 | Battery BMS debugging parameters | uint16 |  |  |
| 193 | Group 2 | BatDebuge8 | Battery BMS debugging parameters | uint16 |  |  |
| 194 | Group 2 | BatDebuge9 | Battery BMS debugging parameters | uint16 |  |  |
| 195 | Group 2 | BatDebuge10 | Battery BMS debugging parameters | uint16 |  |  |
| 196 | Group 2 |  |  |  |  |  |
| 249 | Group 2 | 预留 | reserved |  |  |  |
| 250 | Group 3 | PpvAll H | PV total input power | uint32 | 0.1W |  |
| 251 | Group 3 | PpvAll L |  |  |  |  |
| 252 | Group 3 | Ppv1 H | PV1 input power | uint32 | 0.1W |  |
| 253 | Group 3 | Ppv1 L |  |  |  |  |
| 254 | Group 3 | Ppv2 H | PV2 input power | uint32 | 0.1W |  |
| 255 | Group 3 | Ppv2 L |  |  |  |  |
| 256 | Group 3 | Ppv3 H | PV3 input power | uint32 | 0.1W |  |
| 257 | Group 3 | Ppv3 L |  |  |  |  |
| 258 | Group 3 | Ppv4 H | PV4 input power | uint32 | 0.1W |  |
| 259 | Group 3 | Ppv4 L |  |  |  |  |
| 260 | Group 3 | Ppv5 H | PV5 input power | uint32 | 0.1W |  |
| 261 | Group 3 | Ppv5 L |  |  |  |  |
| 262 | Group 3 | Ppv6 H | PV6 input power | uint32 | 0.1W |  |
| 263 | Group 3 | Ppv6 L |  |  |  |  |
| 264 | Group 3 | Ppv7 H | PV7 input power | uint32 | 0.1W |  |
| 265 | Group 3 | Ppv7 L |  |  |  |  |
| 266 | Group 3 | Ppv8 H | PV8 input power | uint32 | 0.1W |  |
| 267 | Group 3 | Ppv8 L |  |  |  |  |
| 268 | Group 3 | Ppv9 H | PV9 input power | uint32 | 0.1W |  |
| 269 | Group 3 | Ppv9 L |  |  |  |  |
| 270 | Group 3 | Ppv10 H | PV10 input power | uint32 | 0.1W |  |
| 271 | Group 3 | Ppv10 L |  |  |  |  |
| 272 | Group 3 | Ppv11 H | PV11 input power | uint32 | 0.1W |  |
| 273 | Group 3 | Ppv11 L |  |  |  |  |
| 274 | Group 3 | Ppv12 H | PV12 input power | uint32 | 0.1W |  |
| 275 | Group 3 | Ppv12 L |  |  |  |  |
| 276 | Group 3 | Ppv13 H | PV13 input power | uint32 | 0.1W |  |
| 277 | Group 3 | Ppv13 L |  |  |  |  |
| 278 | Group 3 | Ppv14 H | PV14 input power | uint32 | 0.1W |  |
| 279 | Group 3 | Ppv14 L |  |  |  |  |
| 280 | Group 3 | Ppv15 H | PV15 input power | uint32 | 0.1W |  |
| 281 | Group 3 | Ppv15 L |  |  |  |  |
| 282 | Group 3 | Ppv16 H | PV16 input power | uint32 | 0.1W |  |
| 283 | Group 3 | Ppv16 L |  |  |  |  |
| 284 | Group 3 | SPacAll H | Three-phase output apparent power ALL | uint32 | 0.1VA |  |
| 285 | Group 3 | SPacAll L |  |  |  |  |
| 286 | Group 3 | ActPacAll H | Three-phase output power ALL | sint32 | 0.1W |  |
| 287 | Group 3 | ActPacAll L |  |  |  |  |
| 288 | Group 3 | ReActPacAll H | Three-phase output reactive power ALL | sint32 | 0.1var |  |
| 289 | Group 3 | ReActPacAll L |  |  |  |  |
| 290 | Group 3 | SPac_R H | Three-phase output apparent power R | uint32 | 0.1VA |  |
| 291 | Group 3 | SPac_R L |  |  |  |  |
| 292 | Group 3 | ActPac_R H | Three-phase output power R | sint32 | 0.1W |  |
| 293 | Group 3 | ActPac_R L |  |  |  |  |
| 294 | Group 3 | ReActPac_R H | Three-phase output reactive power R | sint32 | 0.1var |  |
| 295 | Group 3 | ReActPac_R L |  |  |  |  |
| 296 | Group 3 | SPac_S H | Three-phase output apparent power S | uint32 | 0.1VA |  |
| 297 | Group 3 | SPac_S L |  |  |  |  |
| 298 | Group 3 | ActPac_S H | Three-phase output power S | sint32 | 0.1W |  |
| 299 | Group 3 | ActPac_S L |  |  |  |  |
| 300 | Group 3 | ReActPac_S H | Three-phase output reactive power S | sint32 | 0.1var |  |
| 301 | Group 3 | ReActPac_S L |  |  |  |  |
| 302 | Group 3 | SPac_T H | Three-phase output apparent power T | uint32 | 0.1VA |  |
| 303 | Group 3 | SPac_T L |  |  |  |  |
| 304 | Group 3 | ActPac_T H | Three-phase output power T | sint32 | 0.1W |  |
| 305 | Group 3 | ActPac_T L |  |  |  |  |
| 306 | Group 3 | ReActPac_T H | Three-phase output reactive power T | sint32 | 0.1var |  |
| 307 | Group 3 | ReActPac_T L |  |  |  |  |
| 308 | Group 3 | 预留 | reserved |  |  |  |
| 309 | Group 3 | 预留 | reserved |  |  |  |
| 310 | Group 3 | 预留 | reserved |  |  |  |
| 311 | Group 3 | 预留 | reserved |  |  |  |
| 312 | Group 3 | 预留 | reserved |  |  |  |
| 313 | Group 3 | 预留 | reserved |  |  |  |
| 314 | Group 3 | Pactouser R   H | R phase to user power | uint32 | 0.1W |  |
| 315 | Group 3 | Pactouser R   L |  |  |  |  |
| 316 | Group 3 | Pactouser S   H | S phase to user power | uint32 | 0.1W |  |
| 317 | Group 3 | Pactouser S   L |  |  |  |  |
| 318 | Group 3 | Pactouser T   H | T phase to user power | uint32 | 0.1W |  |
| 319 | Group 3 | Pactouser T   L |  |  |  |  |
| 320 | Group 3 | PactouserTotal H | The total AC power to the user | uint32 | 0.1W |  |
| 321 | Group 3 | PactouserTotal L |  |  |  |  |
| 322 | Group 3 | Pac to grid R  H | AC side to grid power R | uint32 | 0.1W |  |
| 323 | Group 3 | Pac to grid R  L |  |  |  |  |
| 324 | Group 3 | Pactogrid S  H | AC side to grid power S | uint32 | 0.1W |  |
| 325 | Group 3 | Pactogrid S  L |  |  |  |  |
| 326 | Group 3 | Pactogrid T H | AC side to grid power T | uint32 | 0.1W |  |
| 327 | Group 3 | Pactogrid T L |  |  |  |  |
| 328 | Group 3 | Pactogrid total H | Total power from AC side to grid | uint32 | 0.1W |  |
| 329 | Group 3 | Pactogrid total L |  |  |  |  |
| 330 | Group 3 | PLocalLoad total H | Inverter power to local load total | uint32 | 0.1W |  |
| 331 | Group 3 | PLocalLoad total L |  |  |  |  |
| 332 | Group 3 | EPS Pac_R H | Off-grid R phase output power | uint32 | 0.1VA |  |
| 333 | Group 3 | EPS Pac_R L |  |  |  |  |
| 334 | Group 3 | EPS ActPac_R H | Off-grid R phase output active power | uint32 | 0.1W |  |
| 335 | Group 3 | EPS ActPac_R L |  |  |  |  |
| 336 | Group 3 | EPS Pac_S H | Off-grid S phase output power | uint32 | 0.1VA |  |
| 337 | Group 3 | EPS Pac_S L |  |  |  |  |
| 338 | Group 3 | EPS ActPac_S H | Off-grid S phase output active power | uint32 | 0.1W |  |
| 339 | Group 3 | EPS ActPac_S L |  |  |  |  |
| 340 | Group 3 | EPS Pac_T H | Off-grid T phase output power | uint32 | 0.1VA |  |
| 341 | Group 3 | EPS Pac_T L |  |  |  |  |
| 342 | Group 3 | EPS ActPac_T H | Off-grid T phase output active power | uint32 | 0.1W |  |
| 343 | Group 3 | EPS ActPac_T L |  |  |  |  |
| 344 | Group 3 | Loadpercent | Off-grid output loading percentage | uint16 | 0.01 |  |
| 345 | Group 3 | PSystem H | System power generation | uint32 | 0.1W |  |
| 346 | Group 3 | PSystem L |  |  |  |  |
| 347 | Group 3 | PSelf H | Spontaneous self-consumption power | uint32 | 0.1W |  |
| 348 | Group 3 | PSelf L |  |  |  |  |
| 349 | Group 3 | Pdischarge H | Discharge power | uint32 | 0.1W |  |
| 350 | Group 3 | Pdischarge L |  |  |  |  |
| 351 | Group 3 | Pcharge H | Charging power | uint32 | 0.1W |  |
| 352 | Group 3 | Pcharge L |  |  |  |  |
| 353 | Group 3 | AC charge Power_H | AC charging power | uint32 | 0.1W |  |
| 354 | Group 3 | AC charge Power_L |  |  |  |  |
| 355 | Group 3 | Extra AC Power to  grid_H | Additional inverter AC power to grid H | uint32 | 0.1W |  |
| 356 | Group 3 | Extra AC Power to  grid_L |  |  |  |  |
| 357 | Group 3 | udGEN_ApparentP_R   H | Diesel generator R phase apparent power | uint32 | 0.1W |  |
| 358 | Group 3 | udGEN_ApparentP_R   L |  |  |  |  |
| 359 | Group 3 | udGEN_ApparentP_S   H | Diesel generator S phase apparent power | uint32 | 0.1W |  |
| 360 | Group 3 | udGEN_ApparentP_S   L |  |  |  |  |
| 361 | Group 3 | udGEN_ApparentP_T   H | Diesel generator T phase apparent power | uint32 | 0.1W |  |
| 362 | Group 3 | udGEN_ApparentP_T   L |  |  |  |  |
| 363 | Group 3 | udGEN_ActiveP_R   H | Diesel generator R phase active power | uint32 | 0.1W |  |
| 364 | Group 3 | udGEN_ActiveP_R   L |  |  |  |  |
| 365 | Group 3 | udGEN_ActiveP_S   H | Diesel generator S-phase active power | uint32 | 0.1W |  |
| 366 | Group 3 | udGEN_ActiveP_S   L |  |  |  |  |
| 367 | Group 3 | udGEN_ActiveP_T   H | Diesel generator T-phase active power | uint32 | 0.1W |  |
| 368 | Group 3 | udGEN_ActiveP_T   L |  |  |  |  |
| 375 | Group 4 | Eactoday H | Daily power generation | uint32 | 0.1kWh |  |
| 376 | Group 4 | Eac today L |  |  |  |  |
| 377 | Group 4 | Eac total H | Total power generation | uint32 | 0.1kWh |  |
| 378 | Group 4 | Eac total L |  |  |  |  |
| 379 | Group 4 | EPVAll_Today H | PV daily power generation | uint32 | 0.1kWh |  |
| 380 | Group 4 | EPVAll_Today L |  |  |  |  |
| 381 | Group 4 | Epv_total H | PV total energy | uint32 | 0.1kWh |  |
| 382 | Group 4 | Epv_total L |  |  |  |  |
| 383 | Group 4 | EChargeToday H | Daily charging capacity | uint32 | 0.1kWh |  |
| 384 | Group 4 | EChargeToday L |  |  |  |  |
| 385 | Group 4 | EChargeTotal H | Total charge | uint32 | 0.1kWh |  |
| 386 | Group 4 | EChargeTotal L |  |  |  |  |
| 387 | Group 4 | EDischargeToday H | Daily discharge capacity | uint32 | 0.1kWh |  |
| 388 | Group 4 | EDischargeToday L |  |  |  |  |
| 389 | Group 4 | EDischargeTotal H | total discharge | uint32 | 0.1kWh |  |
| 390 | Group 4 | EDischargeTotal L |  |  |  |  |
| 391 | Group 4 | EACharge_Today_H | AC daily charging capacity | uint32 | 0.1kWh |  |
| 392 | Group 4 | EACharge_Today_L |  |  |  |  |
| 393 | Group 4 | EACharge_Total_H | Total AC charge | uint32 | 0.1kWh |  |
| 394 | Group 4 | EACharge_Total_L |  |  |  |  |
| 395 | Group 4 | Eextra_today H | External grid-connected inverter energy for the day | uint32 | 0.1kWh | Meter 2 or CT2 energy statistics |
| 396 | Group 4 | Eextra_today L |  |  |  |  |
| 397 | Group 4 | Eextra_total H | Total external grid-connected inverter energy | uint32 | 0.1kWh |  |
| 398 | Group 4 | Eextra_total L |  |  |  |  |
| 399 | Group 4 | Esystem_today H | System daily power generation | uint32 | 0.1kWh |  |
| 400 | Group 4 | Esystem_ today L |  |  |  |  |
| 401 | Group 4 | Esystem_total H | Total power generation of the system | uint32 | 0.1kWh |  |
| 402 | Group 4 | Esystem_ total L |  |  |  |  |
| 403 | Group 4 | Eself_today H | Self-consumption daily power generation | uint32 | 0.1kWh |  |
| 404 | Group 4 | Eself_ today L |  |  |  |  |
| 405 | Group 4 | Eself_total H | Total self-consumption power generation | uint32 | 0.1kWh |  |
| 406 | Group 4 | Eself_ total L |  |  |  |  |
| 407 | Group 4 | Eload_today H | Load power consumption per day | uint32 | 0.1kWh |  |
| 408 | Group 4 | Eload_today L |  |  |  |  |
| 409 | Group 4 | Eload_total H | Load power consumption total | uint32 | 0.1kWh |  |
| 410 | Group 4 | Eload_total L |  |  |  |  |
| 411 | Group 4 | EtoGrid_today H | Electricity fed into the grid, day | uint32 | 0.1kWh |  |
| 412 | Group 4 | EtoGrid_today L |  |  |  |  |
| 413 | Group 4 | EtoGrid_total H | Electricity fed into the grid Total | uint32 | 0.1kWh |  |
| 414 | Group 4 | EtoGrid_total L |  |  |  |  |
| 415 | Group 4 | EfromGrid_today H | Electricity drawn from the grid per day | uint32 | 0.1kWh |  |
| 416 | Group 4 | EfromGrid_today L |  |  |  |  |
| 417 | Group 4 | EfromGrid_total H | Power taken from the grid Total | uint32 | 0.1kWh |  |
| 418 | Group 4 | EfromGrid_total L |  |  |  |  |
| 419 | Group 4 | dEpvToGridTodayEE | On-grid power (sold electricity) day | uint32 | 0.1kWh |  |
| 420 | Group 4 | dEpvToGridTodayEE |  |  |  |  |
| 421 | Group 4 | dEpvToGridTotalEE | On-grid electricity (sold electricity) Total | uint32 | 0.1kWh |  |
| 422 | Group 4 | dEpvToGridTotalEE |  |  |  |  |
| 423 | Group 4 | dEGridToLoadTodayEE | Purchased electricity (purchased electricity) day | uint32 | 0.1kWh |  |
| 424 | Group 4 | dEGridToLoadTodayEE |  |  |  |  |
| 425 | Group 4 | dEGridToLoadTotalEE | Purchased electricity (purchased electricity) Total | uint32 | 0.1kWh |  |
| 426 | Group 4 | dEGridToLoadTotalEE |  |  |  |  |
| 427 | Group 4 | dESelfToLoadTodayEE | Self-sufficient power day | uint32 | 0.1kWh |  |
| 428 | Group 4 | dESelfToLoadTodayEE |  |  |  |  |
| 429 | Group 4 | dESelfToLoadTotalEE | Self-sufficient power total | uint32 | 0.1kWh |  |
| 430 | Group 4 | dESelfToLoadTotalEE |  |  |  |  |
| 450 | Group 4 | uwParallelType | Parallel type | uint16 |  | 0x00: Standalone<br>0x01: Host<br>0x02: slave |
| 451 | Group 4 | HostSerialNum5 | The serial number of the host is 9~10 characters, indicating the year of production of the machine. | ASCII |  | The last eight characters of the host serial number. If it is the same parallel system, the serial number reported by the slave machine will be the same. |
| 452 | Group 4 | HostSerialNum6 | The serial number of the host is 11~12 characters, indicating the week in which the machine was produced. | ASCII |  |  |
| 453 | Group 4 | HostSerialNum7 | Host serial number 13~14 characters | ASCII |  |  |
| 454 | Group 4 | HostSerialNum8 | Host serial number 15~16 characters | ASCII |  |  |
| 455 | Group 4 | ubParallelDeviceID | Parallel device ID | uint8 |  | Range: 0~36 |
| 456 | Group 4 | udwParallelPVPower-H | Total parallel PV power | uint32 | 0.1W |  |
| 457 | Group 4 | udwParallelPVPower-L |  |  |  |  |
| 458 | Group 4 | sdwParallelGridPower-H | Total power of parallel power grid | sint32 | 0.1W | Feed: Negative<br>Power extraction: Positive value |
| 459 | Group 4 | sdwParallelGridPower-L |  |  |  |  |
| 460 | Group 4 | udwParallelLoadPower-H | Total parallel load power | uint32 | 0.1W |  |
| 461 | Group 4 | udwParallelLoadPower-L |  |  |  |  |
| 462 | Group 4 | sdwParallelBatPower-H | Total parallel battery power | sint32 | 0.1W | Charge: negative value<br>Discharge: positive |
| 463 | Group 4 | sdwParallelBatPower-L |  |  |  |  |
| 464 | Group 4 | udwParallelSelfPower-H | Parallel machine spontaneous self-use power | uint32 | 0.1W |  |
| 465 | Group 4 | udwParallelSelfPower-L |  |  |  |  |
| 466 | Group 4 | udwParallel_EPVToady_H | Parallel PV daily power generation capacity | uint32 | 0.1kWh |  |
| 467 | Group 4 | udwParallel_EPVToady_L |  |  |  |  |
| 468 | Group 4 | udwParallel_EPVTotal_H | Total energy of parallel PV | uint32 | 0.1kWh |  |
| 469 | Group 4 | udwParallel_EPVTotal_L |  |  |  |  |
| 470 | Group 4 | udwParallel_ESelfToday_H | Daily power generated by parallel machines for self-use | uint32 | 0.1kWh |  |
| 471 | Group 4 | udwParallel_ESelfToday_L |  |  |  |  |
| 472 | Group 4 | udwParallel_ESelfTotal_H | Total power generated by parallel machines for self-use | uint32 | 0.1kWh |  |
| 473 | Group 4 | udwParallel_ESelfTotal_L |  |  |  |  |
| 474 | Group 4 | udwParallel_ELoadToday_H | Parallel load power consumption day | uint32 | 0.1kWh |  |
| 475 | Group 4 | udwParallel_ELoadTotal_H |  |  |  |  |
| 476 | Group 4 | udwParallel_ELoadToday_H | Parallel load power consumption total | uint32 | 0.1kWh |  |
| 477 | Group 4 | udwParallel_ELoadTotal_L |  |  |  |  |
| 478 | Group 4 | udwParallel_EPVtoGridToday_H | Parallel online electricity consumption (electricity sold) day | uint32 | 0.1kWh |  |
| 479 | Group 4 | udwParallel_EPVtoGridToday_L |  |  |  |  |
| 480 | Group 4 | udwParallel_EPVtoGridTotal_H | Parallel online power (sold electricity) Total | uint32 | 0.1kWh |  |
| 481 | Group 4 | udwParallel_EPVtoGridTotal_L |  |  |  |  |
| 482 | Group 4 | udwParallel_EGridtoLoadToday_H | Parallel purchased electricity (purchased electricity) day | uint32 | 0.1kWh |  |
| 483 | Group 4 | udwParallel_EGridtoLoadToday_L |  |  |  |  |
| 484 | Group 4 | udwParallel_EGridtoLoadTotal_H | Purchase electricity in parallel (Purchase electricity) Total | uint32 | 0.1kWh |  |
| 485 | Group 4 | udwParallel_EGridtoLoadTotal_L |  |  |  |  |
| 486 | Group 4 | udwParallel_ESelftoLoadToday_H | Parallel machine self-sufficient power day | uint32 | 0.1kWh |  |
| 487 | Group 4 | udwParallel_ESelftoLoadToday_L |  |  |  |  |
| 488 | Group 4 | udwParallel_ESelftoLoadTotal_H | Parallel self-sufficient power total | uint32 | 0.1kWh |  |
| 489 | Group 4 | udwParallel_ESelftoLoadTotal_L |  |  |  |  |
| 490 | Group 4 | SOC | Battery SOC | uint16 | 0.01 |  |
| 491 | Group 4 | udwParallel_EBatChrToday_H | Parallel battery charging capacity in days | uint32 | 0.1kWh |  |
| 492 | Group 4 | udwParallel_EBatChrToday_L |  |  |  |  |
| 493 | Group 4 | udwParallel_EBatChrTotal_H | Parallel battery charging capacity total | uint32 | 0.1kWh |  |
| 494 | Group 4 | udwParallel_EBatChrTotal_L |  |  |  |  |
| 495 | Group 4 | udwParallel_EBatDisChrToday_H | Parallel battery discharge capacity in days | uint32 | 0.1kWh |  |
| 496 | Group 4 | udwParallel_EBatDisChrToday_L |  |  |  |  |
| 497 | Group 4 | udwParallel_EBatDisChrTotal_H | Parallel battery discharge capacity total | uint32 | 0.1kWh |  |
| 498 | Group 4 | udwParallel_EBatDisChrTotal_L |  |  |  |  |

## Holding registers (function code 0x03)

**Total:** 260 registers

| Address | Group | Variable name | Description | Access | Default | Range | Data type | Unit | Persisted | Notes |
|---------|-------|---------------|-------------|--------|---------|-------|-----------|------|-----------|-------|
| 0 | Group 1 — System parameters | OnOffSet | Turn on and off | R/W | 1 | 0~1或0xA5 | uint16 | - | No | On：1<br>Off: 0<br>Restart: 0xA5 (to be determined) |
| 1 | Group 1 — System parameters | SystemSetBit | System enable flag | R/W |  |  |  |  |  | Single camera and triple camera use |
| 2 | Group 1 — System parameters | DeviceType | Device type | R |  |  | uint16 | - | No | Used for model identification |
| 3 | Group 1 — System parameters | DeviceID | Device communication address | R/W | 1 | 1~245 | uint16 | - | Yes | Communication ID |
| 4 | Group 1 — System parameters | BaudrateSet | Select baud rate | R/W | 0 | 0~1 | uint16 | - | Yes | 0:9600bps<br>1:38400bps |
| 5 | Group 1 — System parameters | Serial NO.1 | Serial number 1 | R/W | - | - | ASCII | - | Yes | Product serial number, the lowest valid digit is 16 digits |
| 6 | Group 1 — System parameters | Serial NO.2 | Serial number 2 | R/W | - | - | ASCII | - | Yes |  |
| 7 | Group 1 — System parameters | Serial NO.3 | Serial number 3 | R/W | - | - | ASCII | - | Yes |  |
| 8 | Group 1 — System parameters | Serial NO.4 | Serial numbe 4 | R/W | - | - | ASCII | - | Yes |  |
| 9 | Group 1 — System parameters | Serial NO.5 | Serial number 5 | R/W | - | - | ASCII | - | Yes |  |
| 10 | Group 1 — System parameters | Serial NO.6 | Serial number 6 | R/W | - | - | ASCII | - | Yes |  |
| 11 | Group 1 — System parameters | Serial NO.7 | Serial numbe 7 | R/W | - | - | ASCII | - | Yes |  |
| 12 | Group 1 — System parameters | Serial NO.8 | Serial numbe 8 | R/W | - | - | ASCII | - | Yes |  |
| 13 | Group 1 — System parameters | Serial NO.9 | Serial number 9 | R/W | - | - | ASCII | - | Yes |  |
| 14 | Group 1 — System parameters | Serial NO.10 | Serial number 10 | R/W | - | - | ASCII | - | Yes |  |
| 15 | Group 1 — System parameters | Serial NO.11 | Serial number 11 | R/W | - | - | ASCII | - | Yes |  |
| 16 | Group 1 — System parameters | Serial NO.12 | Serial number 12 | R/W | - | - | ASCII | - | Yes |  |
| 17 | Group 1 — System parameters | Serial NO.13 | Serial number 13 | R/W | - | - | ASCII | - | Yes |  |
| 18 | Group 1 — System parameters | Serial NO.14 | Serial number 14 | R/W | - | - | ASCII | - | Yes |  |
| 19 | Group 1 — System parameters | Serial NO.15 | Serial numbe 15 | R/W | - | - | ASCII | - | Yes |  |
| 20 | Group 1 — System parameters | Rs485WorkMode | 485 working mode selection | R/W | 0 | 0~2 | uint16 |  | Yes | 0: Slave mode (ATE)<br>1: Host mode (BMS485)<br>2: Host mode (Meter485) |
| 21 | Group 1 — System parameters | Year | System time - year | R/W | 2022 | 读：2022~2050<br>写：22~50 | uint16 | 年 | No |  |
| 22 | Group 1 — System parameters | Month | System time-month | R/W | 1 | 1~12 | uint16 | 月 | No |  |
| 23 | Group 1 — System parameters | Day | System time - day | R/W | 1 | 1~31 | uint16 | 日 | No |  |
| 24 | Group 1 — System parameters | Hour | System time - hours | R/W | 0 | 0~59 | uint16 | 时 | No |  |
| 25 | Group 1 — System parameters | Minute | System time - minutes | R/W | 0 | 0~59 | uint16 | 分 | No |  |
| 26 | Group 1 — System parameters | Second | System time - seconds | R/W | 0 | 0~59 | uint16 | 秒 | No | The set time will not take effect until seconds |
| 27 | Group 1 — System parameters | Weekday | system week | R/W | 1 | 1~7 | uint16 | - | No |  |
| 28 | Group 1 — System parameters | SoftVersion_Attest | Firmware version (high) | R | - |  | ASCII | - | No | Firmware version (XX1.0) |
| 29 | Group 1 — System parameters |  | Firmware version (medium) | R | - |  | ASCII | - | No |  |
| 30 | Group 1 — System parameters |  | Firmware version (lower) | R | - |  | ASCII | - | No |  |
| 31 | Group 1 — System parameters | SoftVersion_Monitor | ARM firmware version name | R | - |  | ASCII | - | No | ARM software version (XXXX0000) |
| 32 | Group 1 — System parameters |  | ARM firmware version name | R | - |  | ASCII | - | No |  |
| 33 | Group 1 — System parameters |  | ARM firmware version number | R | - |  | uint16 | - | No |  |
| 34 | Group 1 — System parameters | SoftVersion_Control | DSP software version name (TJ) | R | - |  | ASCII | - | No | DSP software version (XXXX0000) |
| 35 | Group 1 — System parameters |  | DSP software version name (AA) | R | - |  | ASCII | - | No |  |
| 36 | Group 1 — System parameters |  | DSP1 software major version number | R | - |  | uint16 | - | No |  |
| 37 | Group 1 — System parameters |  | DSP2 software major version number | R | - |  | uint16 | - | No |  |
| 38 | Group 1 — System parameters | MasterDSPTestVersion | DSP1 software debugging version number | R | - |  | uint16 | - | No |  |
| 39 | Group 1 — System parameters | SlaveDSPTestVersion | DSP2 software debugging version number | R | - |  | uint16 | - | No |  |
| 40 | Group 1 — System parameters | ARM TestVersion | ARM debug version number | R | - |  | uint16 | - | No |  |
| 41 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 42 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 43 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 44 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 45 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 46 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 47 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 48 | Group 1 — System parameters | DSP Hard version | Main control board hardware version | R | - |  | uint16 | - | No | Hardware version |
| 49 | Group 1 — System parameters | ARM Hard version | Monitoring board hardware version | R | - |  | uint16 | - | No | Hardware version |
| 50 | Group 1 — System parameters | Manufacturer Info 8 | Manufacturer information 8 | R | - |  | ASCII | - | No | Manufacturer information |
| 51 | Group 1 — System parameters | Manufacturer Info 7 | Manufacturer information 7 | R | - |  | ASCII | - | No |  |
| 52 | Group 1 — System parameters | Manufacturer Info 6 | Manufacturer information 6 | R | - |  | ASCII | - | No |  |
| 53 | Group 1 — System parameters | Manufacturer Info 5 | Manufacturer information 5 | R | - |  | ASCII | - | No |  |
| 54 | Group 1 — System parameters | Manufacturer Info 4 | Manufacturer information 4 | R | - |  | ASCII | - | No |  |
| 55 | Group 1 — System parameters | Manufacturer Info3 | Manufacturer information 3 | R | - |  | ASCII | - | No |  |
| 56 | Group 1 — System parameters | Manufacturer Info 2 | Manufacturer information 2 | R | - |  | ASCII | - | No |  |
| 57 | Group 1 — System parameters | Manufacturer Info 1 | Manufacturer information 1 | R/W | - | 0~4 | ASCII/uint16 | - | Yes | Optional manufacturer name during configuration |
| 58 | Group 1 — System parameters | ModbusVersion | Modbus version | R | - | - | uint16 | - | No | Communication protocol version (01) |
| 59 | Group 1 — System parameters | Module 4 | Inverter mode(4) | R/W | - | - | uint16 | - | Yes |  |
| 60 | Group 1 — System parameters | Module 3 | Inverter mode(3) | R/W | - | - | uint16 | - | Yes |  |
| 61 | Group 1 — System parameters | Module 2 | Inverter mode(2) | R/W | - | - | uint16 | - | Yes |  |
| 62 | Group 1 — System parameters | Module 1 | Inverter mode(1) | R/W | - | - | uint16 | - | Yes |  |
| 63 | Group 1 — System parameters | MaxInvPower | Rated power (high) | R | - | 0~65535 | uint16 | 0.1W | No |  |
| 64 | Group 1 — System parameters |  | Rated power (low) | R | - | 0~65535 | uint16 | 0.1W | No |  |
| 65 | Group 1 — System parameters | Reset to factory | Factory reset | W | - | - | uint16 | - | No | 0x01: Restore user data<br>0xA0: Restore factory settings |
| 66 | Group 1 — System parameters | UpdateFileType | Upgrade file type | W | - | - | uint16 | - | No | 0x01: bin upgrade<br>0x10: Hex upgrade |
| 67 | Group 1 — System parameters | UpdateState | Firmware update progress | R | - | - | uint16 | - | No | 读取（0~100：升级进度<br>Greater than 100: upgrade fault code) |
| 68 | Group 1 — System parameters | ubScreenType | Screen type | R/W | - | - | uint8 | - | Yes | 0: small screen<br>1: Big screen |
| 69 | Group 1 — System parameters | SafetyId | Safety number | R/W | 0 | 0~200 | uint16 |  | Yes |  |
| 70 | Group 1 — System parameters | ReactivePowerDelayTIme | Reactive power percentage response time | R/W | 0 | 0~30000 | uint16 | 20ms | Yes |  |
| 71 | Group 1 — System parameters | ActiveOverloadEnable | Active power overload enable | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 72 | Group 1 — System parameters | AcChargePowerRate | Maximum power draw percentage of the inverter | R/W | 100 | 0~100 | uint16 | 1%Pn | Yes | Power from the grid |
| 73 | Group 1 — System parameters | ActivePowerSlope | Active power change rate (N4105) | R/W | 0 | 0~30000 | uint16 | 0.1Pn/min | Yes | 0: Disabled<br>Others: enabled |
| 74 | Group 1 — System parameters | ActivePowerRate | Inverter maximum output active power percentage | R/W | 100 | 0~100 | uint16 | 1%Pn | Yes | Generate electricity to the grid |
| 75 | Group 1 — System parameters | ReactivePowerRate | Inverter maximum output reactive power percentage | R/W |  | 100~-100 | sint16 | 1%Pn | Yes |  |
| 76 | Group 1 — System parameters | PowerFactorSet | 10000 times of inverter output power factor | R/W | 10000 | 0~20000 | uint16 |  | Yes | PF=(X-10000)/10000 |
| 77 | Group 1 — System parameters | PVModelSelect | MPPT mode | R/W | 0 | 0~2 | uint16 |  | Yes | 0: Independent MPPT mode<br>1:DC source mode<br>2: Parallel MPPT mode |
| 78 | Group 1 — System parameters | PvStartVoltage | PV starting voltage | R/W |  |  | uint16 | 0.1V | Yes |  |
| 79 | Group 1 — System parameters | FastDerating_en | Fast load shedding enable | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 80 | Group 1 — System parameters | Island_en | Island enablement | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 81 | Group 1 — System parameters | VFRT_en | High and low crossover enable | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 82 | Group 1 — System parameters | DRMS_en | DRMS enabled | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 83 | Group 1 — System parameters | NLineConnectMode | N line enable | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 84 | Group 1 — System parameters | NToGNDDetect | ground zero detection | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 85 | Group 1 — System parameters | ZeroPowerOutputEnable | Zero power output enable | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 86 | Group 1 — System parameters | FastMpptEnable | Fast mppt enable | R/W | 0 | 0~1 | uint16 | - | Yes | 0: Disabled<br>1: enable |
| 87 | Group 1 — System parameters | CtRatioSet | CT current ratio setting | R/W | 2000 | 1~3000 | uint16 |  | Yes | reserved |
| 88 | Group 1 — System parameters | CTMode | Use CT mode | R/W | 0 | 0~1 | uint16 |  | Yes | 0：METER<br>1：CT |
| 89 | Group 1 — System parameters | LocalAntiBackflowEnable | Anti-backflow enable | R/W | 0 | 0~3 | uint16 |  | Yes | 0: Disabled<br>1: Total backflow prevention enabled<br>2: Three-phase independent anti-reverse flow enable |
| 90 | Group 1 — System parameters | BackflowMeterPowerLimit_R | Anti-backflow and backflow power limit value | R/W | 0 | 0~100 | sint16 | 1Pn% | Yes |  |
| 91 | Group 1 — System parameters | BackflowMeterPowerLimit_S | Anti-backflow and backflow power limit value | R/W | 0 | 0~100 | sint16 | 1Pn% | Yes |  |
| 92 | Group 1 — System parameters | BackflowMeterPowerLimit_T | Anti-backflow and backflow power limit value | R/W | 0 | 0~100 | sint16 | 1Pn% | Yes |  |
| 93 | Group 1 — System parameters | BackflowHostNoResponseFlag | Anti-backflow host failure flag bit | R | 0 |  | uint16 |  | Yes | 0: normal<br>1: Invalid |
| 94 | Group 1 — System parameters | BackflowFaultTime | Anti-backflow failure time | R/W | 30 | 30~120 | uint16 | 1s | Yes |  |
| 95 | Group 1 — System parameters | BackflowFaultPowerRate | Anti-backflow failure active percentage | R/W | 50 | 0~100 | sint16 | 1Pn% | Yes | After the anti-backflow failure, the machine works according to the given power. |
| 96 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 97 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 98 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 99 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 100 | Group 1 — System parameters | Power on config falg | Boot navigation logo | R/W | 0 | 0~1或0x55 | uint16 |  | Yes | 0x00: default<br>0x01: Configuring (not saved, shutdown)<br>0x55: Configuration completed (save) |
| 101 | Group 1 — System parameters | Vac low C | Grid Low Voltage Restrictions Connect to the Grid | R/W |  | 1700~2400 | uint16 | 0.1V | Yes | Grid connection conditions |
| 102 | Group 1 — System parameters | Vac high C | Grid High Voltage Limits Connecting to the Grid | R/W |  | 2000~2900 | uint16 | 0.1V | Yes |  |
| 103 | Group 1 — System parameters | Fac low C | Grid low frequency limit connection to the grid | R/W |  | 50Hz：4700~5010<br>60Hz：<br>5700~6010 | uint16 | 0.01Hz | Yes |  |
| 104 | Group 1 — System parameters | Fac high C | Grid High Frequency Limitations Connect to the Grid | R/W |  | 50Hz：<br>4990~5300<br>60Hz：<br>5990~6300 | uint16 | 0.01Hz | Yes |  |
| 105 | Group 1 — System parameters | 预留 | reserved |  |  |  | uint16 |  |  |  |
| 106 | Group 1 — System parameters | NominalEPSVolt | Optional rated off-grid voltage | R/W | 0 | 0~4 | uint16 |  | Yes | 0:230V<br>1:240V<br>2:208V<br>3:220V (off-grid)<br>4:200V (off-grid) |
| 107 | Group 1 — System parameters | NominalEPSFre | Optional rated off-grid frequency | R/W | 0 | 0~1 | uint16 |  | Yes | 0:50Hz<br>1:60Hz |
| 108 | Group 1 — System parameters | EPS_En | Off-grid function enabled | R/W | 1 | 0~1 | uint16 |  | Yes |  |
| 109 | Group 1 — System parameters | Bypass_En | Bypass mode enabled | R/W | 0 | 0~1 | uint16 |  | Yes |  |
| 110 | Group 1 — System parameters | UPS_En | UPS function enabled | R/W | 0 | 0~1 | uint16 |  | Yes | To be determined |
| 111 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 112 | Group 1 — System parameters | ubN_PE_RelayCMD | Zero ground relay control enable | R/W | 0 | 0~1 | uint16 |  | Yes | Assignment functional requirements |
| 113 | Group 1 — System parameters | CheckFanCmd | Fan detection |  |  |  | uint16 |  | Yes | To be determined |
| 114 | Group 1 — System parameters | unAFCICtrlReg | AFCI self-test command | R/W |  |  | uint16 |  | Yes | Bit0: SelfCheckCmd；<br>Bit1: ClrFaultCmd；<br>Bit2~7:reserved； |
| 115 | Group 1 — System parameters | uwAFCIThresholdValue | AFCI error threshold | R/W |  |  | uint16 |  | Yes | AFCI error threshold |
| 116 | Group 1 — System parameters | AFCIClrFaultCmd | AFCI error clearing command | R/W |  |  | uint16 |  | No |  |
| 117 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 118 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 119 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 120 | Group 1 — System parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 121 | Group 1 — System parameters | uwRestartVoltL | Fault reconnection to grid low voltage | R/W |  | 1700~2400 | uint16 | 0.1V | Yes | Fault reconnection and grid connection conditions |
| 122 | Group 1 — System parameters | uwRestartVoltH | Fault reconnection to grid high voltage | R/W |  | 2000~2900 | uint16 | 0.1V | Yes |  |
| 123 | Group 1 — System parameters | uwRestartFreqL | Fault reconnection to grid low frequency | R/W |  | 50Hz：4700~5010<br>60Hz：<br>5700~6010 | uint16 | 0.01Hz | Yes |  |
| 124 | Group 1 — System parameters | uwRestartFreqH | Fault reconnection to power grid high frequency | R/W |  | 50Hz：<br>4990~5300<br>60Hz：<br>5990~6300 | uint16 | 0.01Hz | Yes |  |
| 125 | Group 2 — Battery parameters | BatteryType | Battery Type | R/W | 1 |  | uint16 |  | Yes | 0: lead acid<br>1: Lithium battery<br>2: Lithium battery without communication (off-grid)<br>3: User 2 (off-grid)<br>4: User 3 (off-grid)<br>5:NO Bat |
| 126 | Group 2 — Battery parameters | BatteryCompanySet | Battery communication protocol selection | R/W | 0 |  | uint16 |  | Yes | 0: NULL<br>1: Protocol 1<br>2: Protocol 2<br>3: Protocol 3<br>4: Protocol 4 |
| 127 | Group 2 — Battery parameters | BatMdlSerialNum | Number of battery cells in series - high voltage battery; | R/W | 36 | 12,18,24,36 | uint16 |  | Yes | Lead-acid batteries (for high-voltage battery systems) |
| 128 | Group 2 — Battery parameters | BatMdlParallNum | Number of batteries connected in parallel; | R/W | 1 | 1~160 | uint16 |  | Yes | Lead-acid battery (reserved, not used yet) |
| 129 | Group 2 — Battery parameters | ChargeCurrentLimit | Charge limit current | R/W | 8500 | S、O:<br>100~12000<br>T:10~250 | uint16 | 0.01A | Yes | When the charging current needs to be lower than this value, enter the floating charge CC |
| 130 | Group 2 — Battery parameters | VbatStopForDischarge | Discharge cutoff voltage | R/W | 4600 | S:4200~5000<br>T:700~1200<br>O:4000~5200 | uint16 | 0.01V | Yes |  |
| 131 | Group 2 — Battery parameters | Vbat constant charge | Charge cutoff voltage | R/W | 5800 | S、O:<br>4800~5920<br>T:1200~1600 | uint16 | 0.01V | Yes | CV voltage (lead acid battery) |
| 132 | Group 2 — Battery parameters | ubHighVoltBatRatedVolt | Battery nominal voltage | R/W | 400 | T:100~800 | uint16 | 1V | Yes |  |
| 133 | Group 2 — Battery parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 134 | Group 2 — Battery parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 135 | Group 2 — Battery parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 136 | Group 2 — Battery parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 137 | Group 2 — Battery parameters | ChargeRate | Charging power | R/W | 100 | 0~100 | uint16 | 0.01 | Yes |  |
| 138 | Group 2 — Battery parameters | ChargeRate | Discharge power | R/W | 100 | 0~100 | uint16 | 0.01 | Yes |  |
| 139 | Group 2 — Battery parameters | BatFirstStopSOC | Charge cutoff SOC | R/W | 100 | 10~100 | uint16 | 0.01 | Yes |  |
| 140 | Group 2 — Battery parameters | OnLineStopSOC | Grid-connected discharge cutoff SOC | R/W | 10 | 10~100 | uint16 | 0.01 | Yes |  |
| 141 | Group 2 — Battery parameters | OffLineStopSoc | Off-grid discharge cutoff SOC | R/W | 10 | 10~100 | uint16 | 0.01 | Yes |  |
| 142 | Group 2 — Battery parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 143 | Group 2 — Battery parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 144 | Group 2 — Battery parameters | Gen Charge En | Diesel engine charging total enable | R/W | 0 | 0~1 | uint16 |  | Yes | 0: Disabled<br>1: enable |
| 145 | Group 2 — Battery parameters | AcCharge_En | AC charging enable | R/W | 1 | 0~1 | uint16 |  | Yes | 0: Disabled<br>1: enable |
| 146 | Group 2 — Battery parameters | LoadFirstDischargeDisableFlag | Load priority prohibition sign | R/W | 0 | 0~1 | uint16 |  | Yes | To be determined |
| 147 | Group 2 — Battery parameters | RemotePowerControl | One-click charging and discharging | R/W | 255 | 0~2，255 | uint16 |  | No | 255: Invalid<br>0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 148 | Group 2 — Battery parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 149 | Group 2 — Battery parameters | 预留 | reserved |  |  |  |  |  |  |  |
| 150 | Group 2 — Battery parameters | NumberTimePeriods | The number of charging and discharging periods - the number of current valid periods, starting from period 1 | R/W | 0 | 0~10 | uint16 |  | Yes | 0~10: Number of time periods<br>0xA5: The number of time periods is cleared, and all time period setting values are cleared. |
| 151 | Group 2 — Battery parameters | PeriodTimeStart1 | Period 1 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 152 | Group 2 — Battery parameters | PeriodTimeEnd1 | Period 1 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 153 | Group 2 — Battery parameters | PeriodTimeRate1 | period 1 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 154 | Group 2 — Battery parameters | PeriodTimeStart2 | Period 2 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 155 | Group 2 — Battery parameters | PeriodTimeEnd2 | Period 2 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 156 | Group 2 — Battery parameters | PeriodTimeRate2 | Period 2 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 157 | Group 2 — Battery parameters | PeriodTimeStart3 | Period 3 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 158 | Group 2 — Battery parameters | PeriodTimeEnd3 | Period 3 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 159 | Group 2 — Battery parameters | PeriodTimeRate3 | Period 3 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 160 | Group 2 — Battery parameters | PeriodTimeStart4 | Period 4 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 161 | Group 2 — Battery parameters | PeriodTimeEnd4 | Period 4 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 162 | Group 2 — Battery parameters | PeriodTimeRate4 | Period 4 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 163 | Group 2 — Battery parameters | PeriodTimeStart5 | Period 5 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 164 | Group 2 — Battery parameters | PeriodTimeEnd5 | Period 5 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 165 | Group 2 — Battery parameters | PeriodTimeRate5 | Period 5 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 166 | Group 2 — Battery parameters | PeriodTimeStart6 | Period 6 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 167 | Group 2 — Battery parameters | PeriodTimeEnd1 | Period 6 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 168 | Group 2 — Battery parameters | PeriodTimeRate1 | Period 6 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 169 | Group 2 — Battery parameters | PeriodTimeStart7 | Period 7 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 170 | Group 2 — Battery parameters | PeriodTimeEnd1 | Period 7 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 171 | Group 2 — Battery parameters | PeriodTimeRate1 | Period 7 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 172 | Group 2 — Battery parameters | PeriodTimeStart8 | Period 8 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 173 | Group 2 — Battery parameters | PeriodTimeEnd1 | Period 8 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 174 | Group 2 — Battery parameters | PeriodTimeRate1 | Period 8 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 175 | Group 2 — Battery parameters | PeriodTimeStart9 | Period 9 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 176 | Group 2 — Battery parameters | PeriodTimeEnd1 | Period 9 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 177 | Group 2 — Battery parameters | PeriodTimeRate1 | Period 9 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 178 | Group 2 — Battery parameters | PeriodTimeStart10 | Period 10 start time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 179 | Group 2 — Battery parameters | PeriodTimeEnd10 | Period 10 end time | R/W | 0 | 0~0x173B | uint16 | 1min | Yes | H: hour 0~23<br>L: Minutes 0~59 |
| 180 | Group 2 — Battery parameters | PeriodTimeRate10 | Period 10 priority | R/W | 0 | 0~2 | uint16 | 1Pn% | Yes | 0: Load priority<br>1: Battery priority<br>2: Grid priority |
| 181 | Group 2 — Battery parameters | ChargeSourcePriority | Charging priority | R/W | 1 | 0~2 | uint8 |  | Yes | 0:CSO<br>1:SNU<br>2:OSO |
| 182 | Group 2 — Battery parameters | SourcePriority | Energy supply priority | R/W | 1 | 0~10 | uint8 |  | Yes | 0:SOL<br>1:UTI<br>2: SBU<br>10: Grid-connected output mode |
| 183 | Group 2 — Battery parameters | uwCC_DisChrLead_100T | Lead-acid discharge current | R/W | 13700 | 100~13700 | uint16 | 0.01A | Yes |  |
| 184 | Group 2 — Battery parameters | 预留 |  |  |  |  |  |  |  |  |
| 185 | Group 2 — Battery parameters | ubOP_RecoverDischargeSOC | Grid connected, stop discharging and restore SOC | R/W | 90 | 20~100 | uint8 | 0.01 | Yes |  |
| 186 | Group 2 — Battery parameters | 预留 |  |  |  |  |  |  |  |  |
| 187 | Group 2 — Battery parameters | ubOffGrid_RecoverDischargeSOC | Off-grid, stop discharging and restore SOC | R/W | 30 | 10~100 | uint8 | 0.01 | Yes |  |
| 188 | Group 2 — Battery parameters | BatUnderVol | Battery low voltage shutdown voltage | R/W | 400 | 400~480 | uint16 | 0.1V | Yes |  |
| 189 | Group 2 — Battery parameters | AcChargingCurrent | AC charging current limit | R/W | 600 | 10~1000 | uint16 | 0.1A | Yes |  |
| 190 | Group 2 — Battery parameters | uwFloatV_Lead_100T | float charge voltage | R/W | 5520 | 4800~5840 | uint16 | 0.01V | Yes |  |
| 191 | Group 2 — Battery parameters | BAT2AC_Volt | Battery to mains voltage | R/W | 460 | 440~520 | uint16 | 0.1V | Yes |  |
| 192 | Group 2 — Battery parameters | AC2BAT_Volt | Mains power to battery voltage | R/W | 540 | 480~580 | uint16 | 0.1V | Yes |  |
| 193 | Group 2 — Battery parameters | ubLeadAcid_BatSubType | Lead Acid Battery Subtypes | R/W | 3 | 0~8 | uint8 |  | Yes | 0:USE<br>1:SLD<br>2:FLD<br>3:GEL<br>4:L14<br>5:L15<br>6:L16<br>7:N13<br>8:N14<br>9:LIT |
| 194 | Group 2 — Battery parameters | IncreChar_MaxTim | Improve charging time | R/W | 120 | 5~900 | uint16 | 1min | Yes |  |
| 195 | Group 2 — Battery parameters | BatUnderVolt_Point | Battery undervoltage alarm point | R/W | 440 | 400~500 | uint16 | 0.1V | Yes |  |
| 196 | Group 2 — Battery parameters | Equalization | Balanced mode enabled | R/W | 1 | 0~1 | uint8 |  | Yes | 0: disable<br>1: enable |
| 197 | Group 2 — Battery parameters | EQBatteryTime | Equilibrium charging time | R/W | 120 | 5~900 | uint16 | 1min | Yes |  |
| 198 | Group 2 — Battery parameters | EQBatteryTimeout | Balanced charging delay time | R/W | 120 | 5~900 | uint16 | 1min | Yes |  |
| 199 | Group 2 — Battery parameters | EqualizationCycle | Balanced charging interval | R/W | 30 | 0~30 | uint8 | 1DAY | Yes |  |
| 200 | Group 2 — Battery parameters | EqualizationImmediately | Start equalizing charging immediately | R/W | 0 | 0~1 | uint16 |  | No | 0: disable<br>1: enable |
| 201 | Group 2 — Battery parameters | flcdEn | LCD setting enable bit | R/W |  |  | uint16 |  | Yes | 0:ECOMode_En (energy saving mode enable)<br>1:OverLoad_RestartEn (overload auto-start enable)<br>2:OverTemp_RestartEn (over-temperature restart enable)<br>3:InputChange_RemEn (mode conversion reminder enable)<br>4:OPSplit_PhaseEn (output phase enable)<br>5:Generator_AutoIPEn (generator automatic input enable)<br>6:DualChannel_LoadEn (dual load enable)<br>7:ubGridFeedBackEn (grid feed enable)<br>8~15:unused |
| 202 | Group 2 — Battery parameters | BatLVBreak_RestartVolt | Low voltage disconnect battery recovery point | R/W | 520 | 500~580 | uint16 | 0.1V | Yes |  |
| 203 | Group 2 — Battery parameters | BatNeedChr_Volt | Battery recharge recovery point | R/W | 520 | 500~560 | uint16 | 0.1V | Yes |  |
| 204 | Group 2 — Battery parameters | NonCriticlLoad_BatDisConVolt | Non-essential loads disconnect battery voltage | R/W | 460 | 420~540 | uint16 | 0.1V | Yes |  |
| 205 | Group 2 — Battery parameters | BatHighVolt_DisConPoint | Overvoltage cut-off voltage | R/W | 600 | 300~600 | uint16 | 0.1V | Yes |  |
| 206 | Group 2 — Battery parameters | BatOverDisCharge_Delay | Battery over-discharge delay time | R/W | 5 | 5~50 | uint16 | 1s | Yes |  |
| 207 | Group 2 — Battery parameters | DspBeepOnOff | buzzer switch | R/W | 1 | 0~1 | uint8 |  | Yes | 0: disable<br>1: enable |
| 208 | Group 2 — Battery parameters | OverloadToBypass | Overload transfer to bypass enable | R/W | 1 | 0~1 | uint8 |  | Yes | 0: disable<br>1: enable |
| 209 | Group 2 — Battery parameters | AcInputType | Off-grid output mode | R/W | 1 | 0~1 | uint8 |  | Yes | 0:APL<br>1:UPS |
| 210 | Group 2 — Battery parameters | EQBatteryVoltage_100T | Balanced charging voltage | R/W | 5840 | 4800~5840 | uint16 |  | Yes |  |
| 211 | Group 2 — Battery parameters | Parallel_Mode | Parallel mode | R/W | 0 | 0~4 | uint8 |  | Yes | 0:SIG<br>1:PAL<br>2:3P1<br>3:3P2<br>4:3P3 |
| 212 | Group 2 — Battery parameters | ubParallelDeviveID | Parallel CAN communication address | R/W | 0 | 0~9 | uint8 |  | Yes |  |
| 213 | Group 2 — Battery parameters | ubParallelDeviveType | Parallel equipment type | R/W | 0 | 0~1 | uint8 |  | Yes | 0: Host<br>1: slave |
| 214 | Group 2 — Battery parameters | ubBMSWorkMode | BMS communication method | R/W | 0 | 0~2 | uint8 |  | Yes | 0: Disabled<br>1: CAN communication<br>2:485 Communication |
| 215 | Group 2 — Battery parameters | uwGridPowerCompensation | Grid power compensation | R/W | 40 | 0~200 | uint16 |  | Yes |  |
| 216 | Group 2 — Battery parameters | Gen Port Work Mode | Diesel engine port function selection | R/W | 0 |  | uint16 |  | Yes | 0.Default<br>1.Generator En<br>2.Gen Force<br>3.SmartLoad Output<br>4.On Grid always on<br>5.Off Grid immediately off<br>6.AC Couple on SecEPS side |
| 217 | Group 2 — Battery parameters | Gen Charge Curr Limit | Diesel generator charging current limit | R/W | 100A |  | uint16 | 1A | Yes |  |
| 218 | Group 2 — Battery parameters | Gen Input Rated Power | Generator input rated power | R/W | 8000W |  | uint16 | 10W | Yes |  |
| 219 | Group 2 — Battery parameters | SecEPS ON SOC/Vbat | (Lithium battery) Start SOC | R/W | 0.4 |  | uint16 | 0.01 | Yes |  |
| 220 | Group 2 — Battery parameters | SecEPS ON Vbat | (Lead Acid) Starting Battery Voltage | R/W | 45.0V |  | uint16 | 0.1V | Yes |  |
| 221 | Group 2 — Battery parameters | SecEPS OFF SOC/Vbat | (Lithium battery) Shut down SOC | R/W | 0.4 |  | uint16 | 0.01 | Yes |  |
| 222 | Group 2 — Battery parameters | SecEPS OFF Vbat | (lead acid) shut down battery voltage | R/W | 55.0V |  | uint16 | 0.1V | Yes |  |
| 223 | Group 2 — Battery parameters | SecEPS  On PV Power Min | Minimum power of smart load when starting photovoltaic | R/W | 3000W |  | uint16 | 10W | Yes |  |
| 231 | Group 2 — Battery parameters | ubBluetoothEn | Bluetooth enabled | R/W | 1 |  | uint8 |  | Yes | 1: Turn on Bluetooth<br>0: Turn off Bluetooth |
| 232 | Group 2 — Battery parameters | upgrade notification | Data update notification, wifi re-reports 0304 data to the server | R/W | 0 |  | uint8 |  | No | 0: Invalid by default<br>1: Trigger update |
| 233 | Group 2 — Battery parameters | Datalogger Restart | Restore wifi to factory settings, modify server domain name and reporting time | R/W | 0 |  | uint8 |  | No | 0: Invalid by default<br>1: Trigger a factory reset |
| 234 | Group 2 — Battery parameters | ubConnectServer | Collector networking status | R/W |  | 0x0055、<br>0x00AA、<br>0x0100、<br>0x0200 | uint8 |  | No | The lower 8 bits indicate the networking status:<br>0x0055: Network abnormality<br>0x00AA: The network is normal<br>The high 8 bits indicate the collector type:<br>0x0100: Wifi-U<br>0x0200: 4G-U |
| 235 | Group 2 — Battery parameters | ubDatalogAndArmCommunication | Communication status between collector and inverter | R/W |  | 0x55、0xAA | uint8 |  | No | 0x55: Communication abnormality<br>0xAA: Communication is normal |
| 250 | Group 3 — Safety parameters | LocalSafetyCmd | User safety selection instructions | R/W | 0 |  | uint16 |  | Yes | To be determined<br>0: Regional standard safety regulations<br>1: Wide range of users<br>2: Power grid company safety regulations |
| 251 | Group 3 — Safety parameters | fGridVoltLow1EE | Low grid voltage protection first level | R/W |  | 460~2400 | uint16 | 0.1V | Yes |  |
| 252 | Group 3 — Safety parameters | fGridVoltHigh1EE | High grid voltage protection first level | R/W |  | 2000~2900 | uint16 | 0.1V | Yes |  |
| 253 | Group 3 — Safety parameters | fFreqLow1EE | Grid low frequency protection first level | R/W |  | 50Hz：4700~5010<br>60Hz：<br>5700~6010 | uint16 | 0.01Hz | Yes |  |
| 254 | Group 3 — Safety parameters | fFreqHigh1EE | Grid high frequency protection first level | R/W |  | 50Hz：<br>4990~5300<br>60Hz：<br>5990~6300 | uint16 | 0.01Hz | Yes |  |
| 255 | Group 3 — Safety parameters | fGridVoltLow2EE | Low grid voltage protection second stage | R/W |  | 460~2400 | uint16 | 0.1V | Yes |  |
| 256 | Group 3 — Safety parameters | fGridVoltHigh2EE | High grid voltage protection second stage | R/W |  | 2000~2900 | uint16 | 0.1V | Yes |  |
| 257 | Group 3 — Safety parameters | fFreqLow2EE | Grid low frequency protection second stage | R/W |  | 50Hz：4700~5010<br>60Hz：<br>5700~6010 | uint16 | 0.01Hz | Yes |  |
| 258 | Group 3 — Safety parameters | fFreqHigh2EE | Grid high frequency protection second level | R/W |  | 50Hz：<br>4990~5300<br>60Hz：<br>5990~6300 | uint16 | 0.01Hz | Yes |  |
| 259 | Group 3 — Safety parameters | fGridVoltLow3EE | Low grid voltage protection third level | R/W |  | 460~2400 | uint16 | 0.1V | Yes |  |
| 260 | Group 3 — Safety parameters | fGridVoltHigh3EE | High grid voltage protection level 3 | R/W |  | 2000~2900 | uint16 | 0.1V | Yes |  |
| 261 | Group 3 — Safety parameters | fFreqLow3EE | Grid low frequency protection third level | R/W |  | 50Hz：4700~5010<br>60Hz：<br>5700~6010 | uint16 | 0.01Hz | Yes |  |
| 262 | Group 3 — Safety parameters | fFreqHigh3EE | Grid high frequency protection third level | R/W |  | 50Hz：<br>4990~5300<br>60Hz：<br>5990~6300 | uint16 | 0.01Hz | Yes |  |
| 263 | Group 3 — Safety parameters | wVLowCutTime1EE | Low grid voltage first-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 264 | Group 3 — Safety parameters | wVHighCutTime1EE | High grid voltage first-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 265 | Group 3 — Safety parameters | udFLowCutTime1EE | Low grid frequency first-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 266 | Group 3 — Safety parameters | udFHighCutTime1EE | High grid frequency first-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 267 | Group 3 — Safety parameters | wVLowCutTime2EE | Low grid voltage second-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 268 | Group 3 — Safety parameters | wVHighCutTime2EE | High grid voltage second-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 269 | Group 3 — Safety parameters | udFLowCutTime2EE | Low grid frequency second-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 270 | Group 3 — Safety parameters | udFHighCutTime2EE | High grid frequency second-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 271 | Group 3 — Safety parameters | wVLowCutTime3EE | Low grid voltage third-level protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 272 | Group 3 — Safety parameters | wVHighCutTime3EE | High grid voltage third-level protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 273 | Group 3 — Safety parameters | udFLowCutTime3EE | Low grid frequency third-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 274 | Group 3 — Safety parameters | udFHighCutTime3EE | High grid frequency third-order protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 275 | Group 3 — Safety parameters | 10MinAVLimit | Voltage protection for ten minutes | R/W |  | 200~2900 | uint16 | 0.1V | Yes |  |
| 276 | Group 3 — Safety parameters | U10minTime | Ten minutes average voltage protection time | R/W |  | 0~5000 | uint16 | 20ms | Yes |  |
| 277 | Group 3 — Safety parameters | Time start | Grid connection time | R/W |  | 30~900 | uint16 | 1s | Yes |  |
| 278 | Group 3 — Safety parameters | RestartDelayTime | Reconnect time | R/W |  | 30~900 | uint16 | 1s | Yes |  |
| 279 | Group 3 — Safety parameters | PowerStartSlope | loading rate | R/W |  | 1-30000 | uint16 | 0.1Pn%/min | Yes |  |
| 280 | Group 3 — Safety parameters | PowerRestartSlopeEE | Restart loading rate | R/W |  | 1-30000 | uint16 | 0.1Pn%/min | Yes |  |

## Inverter status codes (input register 0)

Register **0** (`Inverter Status`) uses the following values (from protocol notes):

| Value | State |
|-------|--------|
| 0x00 | Waiting |
| 0x01 | Grid-connected |
| 0x02 | Off-grid |
| 0x03 | Fault |
| 0x04 | Firmware update / programming |
| 0x05 | Bypass |
| 0x06 | Self-charge |
