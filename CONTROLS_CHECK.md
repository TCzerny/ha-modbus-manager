# Controls Check for SH10RT + SBR160 + DTSU666

## Expected Controls (with conditions)

### Number Controls (11 visible in your image - all present ✓)

1. **Active Power Limit Ratio** (line 2558) - No condition ✓
2. **Battery Max Charging Power** (line 2598) - No condition ✓
3. **Battery Max Discharging Power** (line 2615) - No condition ✓
4. **Export Power Limit Value Wide Range** (line 2632) - No condition ✓
5. **Battery Charging Start Power** (line 2650) - No condition ✓
6. **Battery Discharging Start Power** (line 2669) - No condition ✓
7. **Max SoC** (line 2456) - No condition ✓
8. **Min SoC** (line 2471) - No condition ✓
9. **Reserved SoC for Backup** (line 2573) - No condition ✓
10. **Export Power Limit** (line 2499) - condition: `meter_type != 'iHomeManager'` ✓ (DTSU666)
11. **Export Power Limit Ratio** (line 2529) - condition: `meter_type != 'iHomeManager'` ✓ (DTSU666)

### Select Controls (should be visible but not shown in your image)

12. **Inverter Run Mode** (line 2381) - condition: `meter_type != 'iHomeManager'` ✓ (DTSU666)
13. **EMS Mode Selection** (line 2394) - condition: `meter_type != 'iHomeManager'` ✓ (DTSU666)
14. **Battery forced charge discharge cmd** (line 2409) - condition: `battery_enabled == true and meter_type != 'iHomeManager'` ✓ (SBR160 + DTSU666)
15. **Load Adjustment Mode** (line 2442) - No condition ✓
16. **Backup Mode** (line 2486) - condition: `battery_enabled == true` ✓ (SBR160)
17. **Export Power Limit Mode** (line 2516) - condition: `meter_type != 'iHomeManager'` ✓ (DTSU666)
18. **Active Power Limitation** (line 2546) - No condition ✓
19. **Load Adjustment Mode ON/OFF** (line 2586) - No condition ✓
20. **Forced Startup Under Low SoC Standby** (line 2688) - condition: `battery_enabled == true` ✓ (SBR160)
21. **PV Power Limitation** (line 2701) - No condition ✓

### Switch Controls (should be visible but not shown in your image)

None for DTSU666 (switches are only for iHomeManager)

## Summary

**Number Controls:** 11 visible ✓ (all present)
**Select Controls:** 10 should be visible (not shown in your image - might be in different UI section)
**Switch Controls:** 0 for DTSU666

**Total Expected Controls:** 21 controls (11 numbers + 10 selects)

## Note

The image you showed only displays **Number** controls in the "Konfiguration" panel. The **Select** controls are likely in a different section of the UI (possibly under "Settings" or "Modes" groups).

To verify all controls are present:
1. Check the device page in Home Assistant
2. Look for different groups: "PV_control", "PV_modes", "PV_battery_control"
3. Select controls might be displayed as dropdowns, not in the number controls section
