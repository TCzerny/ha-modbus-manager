## SMA Dynamic Template

This document describes the Modbus registers for the SMA dynamic template: `sma_dynamic.yaml`.

### Template Overview

- **Name**: SMA Sunny Tripower/Boy Series Inverter
- **Type**: `PV_Inverter`
- **Default prefix**: `SMA`
- **Default slave ID**: `1`
- **Firmware**: `1.0.0`
- **Protocol**: SMA Modbus TCP/UDP (not RTU)

### ⚠️ BETA STATUS

**This template is in BETA status - use at your own risk.**

The template has been created based on community documentation and may need verification with actual devices. Sunny Boy register addresses are preliminary and may need adjustment.

### Dynamic Configuration

- `valid_models`: Model list based on power rating
  - Sunny Tripower Series: STP-5000TL to STP-20000TL (5-20kW, three phase)
  - Sunny Boy Series: SB-2500 to SB-5000 (2.5-5kW, single phase) - Preliminary support
- `phases`: Options [1, 3] (default: 3)
- `mppt_count`: Options [1, 2] (default: 2)
- `firmware_version`: Options ["1.0.0", "Latest"] (default: "1.0.0")

### Key Features

- **Production Data**: Solar production total energy
- **DC Data**: DC current, voltage, power
- **AC Data**: AC power total and per-phase (L1, L2, L3)
- **Calculated Sensors**: PV Power Total, AC Power Phase Total
- **Binary Sensors**: PV Generating, AC Power Active

### Register Notes

- Uses **Modbus TCP/UDP** (not RTU)
- All values are **32-bit unsigned integers** (2 registers combined)
- **Big Endian, Big Word Order**
- Invalid values: **0x7FFFFFFF (2147483647)** - should be treated as 0
- Modbus server TCP and UDP must be enabled on the inverter
- Register addresses from Domoticz plugin (plugin.py)
- Tested on Domoticz version 4.10717

### Sensor Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Solar Production Total | solar_production_total | 30529 | input | uint32 | Wh | 1 | |
| DC Current | dc_current | 30769 | input | uint32 | A | 0.001 | |
| DC Voltage | dc_voltage | 30771 | input | uint32 | V | 0.001 | |
| DC Power | dc_power | 30773 | input | uint32 | W | 1 | |
| AC Power Total | ac_power_total | 30775 | input | uint32 | W | 1 | |
| AC Power L1 | ac_power_l1 | 30777 | input | uint32 | W | 1 | phases >= 1 |
| AC Power L2 | ac_power_l2 | 30779 | input | uint32 | W | 1 | phases >= 2 |
| AC Power L3 | ac_power_l3 | 30781 | input | uint32 | W | 1 | phases >= 3 |

**Note**: All registers use `byte_order: "big"` and `swap: "word"` for proper 32-bit value handling.

### Calculated Sensors

- **PV Power Total**: DC Power (same value)
- **AC Power Phase Total**: Sum of AC Power L1, L2, L3 (for three-phase models)

### Binary Sensors

- **PV Generating**: True when PV power > 0
- **AC Power Active**: True when AC power > 0

### Remaining Work

This template is a basic implementation. Future enhancements may include:

- Energy registers (daily, total production)
- System status registers
- Fault/warning registers
- Temperature sensors
- Control registers (power limits, system settings)
- Grid voltage/current/frequency registers
- Verify Sunny Boy register addresses with actual devices

### References

- Repository: https://github.com/doopa75/SMA-Inverter-ModbusTCPIP
- SMA Documentation: https://www.sma-sunny.com/en/how-to-test-the-connection-to-your-sma-inverter/
- Tested on: Domoticz version 4.10717
