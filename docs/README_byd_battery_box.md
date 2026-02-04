# BYD Battery Box Template

## Overview

This template provides support for **BYD Battery-Box** energy storage systems via Modbus RTU over TCP communication. The template supports multiple BYD Battery-Box series including HVS, HVM, HVL, and LVS models.

## BETA Status

⚠️ **This template is in BETA status** - It has been created based on community reverse-engineered Modbus protocol documentation and may require adjustments for specific firmware versions or battery configurations.

## Supported Models

### High Voltage Series (P3 - Modules in Serial)
- **HVS Series**: 5.1, 7.7, 10.2, 12.8 kWh
- **HVM Series**: 8.3, 11.0, 13.8, 16.5, 19.3, 22.1 kWh
- **HVL Series**: Various capacities

### Low Voltage Series (P2 - Modules in Parallel)
- **LVS/LVS Lite**: Various capacities
- **LVL**: Various capacities
- **LVFlex(Lite)**: Various capacities

## Connection Details

### Network Configuration
- **Protocol**: Modbus RTU over TCP
- **Default IP Address**: `192.168.16.254`
- **Port**: `8080`
- **Default Slave ID**: `1`
- **Connection Type**: LAN cable required (wireless connection disables after timeout)

### Important Notes
- The battery must be connected via LAN cable as wireless connections timeout
- Later firmware versions support DHCP - check your network for assigned IP
- You can test connectivity by accessing `http://192.168.16.254` in a browser
- Using other applications simultaneously may cause unexpected results

## Template Configuration

### Required Settings
- **Template**: Select "BYD Battery Box"
- **Host**: Battery IP address (default: `192.168.16.254`)
- **Port**: `8080`
- **Slave ID**: `1` (default)
- **Connection Type**: TCP (Modbus RTU over TCP)
- **Prefix**: `BYD` (default, can be customized)

### Dynamic Configuration
- **Model Selection**: Choose your specific battery model (HVS-5.1, HVM-11.0, etc.)
- **Firmware Version**: Select BMU firmware version (3.16 or 3.24)

## Available Sensors

### Battery Status
- **State of Charge (SOC)**: Battery charge level in %
- **State of Health (SOH)**: Battery health indicator in %
- **Battery Voltage**: Total battery voltage in V
- **Battery Current**: Current flow in A (positive = charging, negative = discharging)
- **Output Voltage**: Battery output voltage in V
- **Battery Power**: Calculated power in W (Current × Output Voltage)

### Cell Monitoring
- **Max Cell Voltage**: Highest individual cell voltage in V
- **Min Cell Voltage**: Lowest individual cell voltage in V
- **Max Cell Temperature**: Highest cell temperature in °C
- **Min Cell Temperature**: Lowest cell temperature in °C
- **BMU Temperature**: Battery Management Unit temperature in °C

### Diagnostics
- **Charge Cycles**: Total number of charge cycles
- **Discharge Cycles**: Total number of discharge cycles
- **Module Count**: Number of battery modules
- **BMS Count**: Number of Battery Management Systems

### Alarms
- **Battery Error**: Binary sensor indicating if any error is present (Error bitmask non-zero)

## Register Map

### Main Battery Status Registers (0x0500-0x0513)
- `0x0500` (1280): State of Charge (%)
- `0x0501` (1281): Max Cell Voltage (0.01V)
- `0x0502` (1282): Min Cell Voltage (0.01V)
- `0x0503` (1283): State of Health (%)
- `0x0504` (1284): Battery Current (0.1A, signed)
- `0x0505` (1285): Battery Voltage (0.01V)
- `0x0506` (1286): Max Cell Temperature (°C)
- `0x0507` (1287): Min Cell Temperature (°C)
- `0x0508` (1288): BMU Temperature (°C)
- `0x0510` (1296): Output Voltage (0.01V)
- `0x0511` (1297): Charge Cycles
- `0x0513` (1299): Discharge Cycles

### BMU Configuration Registers (0x0000-0x0065)
- `0x0010` (16): Module Count (lower 4 bits) and BMS Count (bits 4-7)
- `0x050D` (1293): Error Bitmask

## Error and Warning Codes

The template includes basic error detection via the error bitmask register. Detailed error and warning decoding would require additional calculated sensors. Common error codes include:

- Cells Voltage Sensor Failure
- Temperature Sensor Failure
- BIC Communication Failure
- Pack Voltage Sensor Failure
- Current Sensor Failure
- Charging/Discharging Mos Failure
- Main Relay Failure
- And more...

Warning codes include:
- Battery Over/Under Voltage
- Cells Over/Under Voltage
- Cells Imbalance
- High/Low Temperature (Charging/Discharging)
- Over Current (Charging/Discharging)
- Short Circuit
- And more...

## Compatible Inverters

BYD Battery-Box systems are compatible with various inverter manufacturers:

### High Voltage Batteries (HVS/HVM/HVL)
- Fronius HV
- Goodwe HV/Viessmann HV
- KOSTAL HV
- SMA SBS3.7/5.0/6.0 HV, SMA SBS2.5 HV, SMA STP 5.0-10.0 SE HV
- Sungrow HV
- KACO_HV, KACO_NH
- Solis HV
- GE HV
- Deye HV
- Solplanet
- Western HV
- SOSEN
- Hoymiles HV
- SAJ HV

### Low Voltage Batteries (LVS/LVL/LVFlex)
- Goodwe LV/Viessmann LV
- Selectronic LV
- SMA LV
- Victron LV
- Studer LV
- SolarEdge LV
- Sungrow LV
- Schneider LV
- Solis LV
- Deye LV
- Phocos LV
- Raion LV
- Hoymiles LV

## Limitations

1. **BMS Detailed Data**: Detailed BMS cell-level data requires special Modbus commands (0x0550+) that are not currently implemented in this template
2. **History Data**: Battery history/log data requires special read commands (0x05A0+) that are not currently implemented
3. **Write Controls**: BYD Battery Box typically doesn't expose write controls via Modbus - battery control is handled by the inverter/BMS communication
4. **Warning Decoding**: Full warning bitmask decoding is not implemented - only basic error detection

## References

- [BYD Battery-Box Infos - Read_Modbus.py](https://github.com/sarnau/BYD-Battery-Box-Infos/blob/main/Read_Modbus.py)
- [BYD Battery Box HA Integration](https://github.com/redpomodoro/byd_battery_box)
- [BYD Battery-Box Official Website](https://www.bydbatterybox.com/)
- [BYD Battery-Box Downloads](https://www.bydbatterybox.com/downloads)

## Troubleshooting

### Connection Issues
- Verify battery is connected via LAN cable
- Check IP address (default: `192.168.16.254` or DHCP-assigned)
- Test connectivity: `http://[battery-ip]` should show login page
- Ensure port 8080 is accessible
- Verify Modbus RTU over TCP framer is used (not standard Modbus TCP)

### Data Issues
- Check firmware version matches template configuration
- Verify slave ID is set to 1
- Ensure no other applications are accessing the battery simultaneously
- Check Modbus register addresses match your firmware version

### Missing Data
- Some advanced features (BMS details, history) require special Modbus commands not implemented in this template
- Consider using the dedicated BYD Battery Box Home Assistant integration for full feature support

## Support

For issues or questions:
- Check the [BYD Battery-Box community integrations](https://github.com/redpomodoro/byd_battery_box)
- Review the [Modbus protocol reference](https://github.com/sarnau/BYD-Battery-Box-Infos)
- Contact BYD support: bboxservice@byd.com
