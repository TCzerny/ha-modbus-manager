# Battery Cell Position Explanation

## Overview

The **Cell Position** values (e.g., 269, 769) represent unique identifiers assigned by the Battery Management System (BMS) to identify individual cells within the battery pack.

## What the Values Mean

### Max/Min Voltage Cell Position

- **Max Voltage Cell Position (e.g., 269)**: The unique cell ID where the highest cell voltage was detected across all modules
- **Min Voltage Cell Position (e.g., 769)**: The unique cell ID where the lowest cell voltage was detected across all modules

### Position Numbering System

The position is a unique identifier that allows the BMS to track and locate specific cells. The exact numbering scheme depends on the battery manufacturer's implementation, but typically:

1. **Each cell has a unique position number** assigned by the BMS
2. **The position is used for diagnostics** to identify which specific cell has the highest/lowest voltage
3. **This helps with balancing** - you can identify which cells need attention

## How to Interpret the Position

The position number itself doesn't directly tell you "Module X, Cell Y", but it's a unique identifier that the BMS uses internally. However, you can use it to:

1. **Track problematic cells** - If the same position consistently shows max/min voltage, that cell may need attention
2. **Monitor balancing** - Positions should change over time as cells balance
3. **Diagnostics** - Combined with module-level data, you can narrow down which module contains the problematic cell

## Example Values

- **Position 269**: Cell with maximum voltage (e.g., 3.3457 V)
- **Position 769**: Cell with minimum voltage (e.g., 3.3390 V)

## Understanding the Position Number

The position is a **unique cell identifier** used by the BMS. It's not a simple coordinate like "Module 2, Cell 15", but rather an internal ID that the BMS uses to track each cell.

### Typical Interpretation

For a battery with multiple modules:
- Each module contains multiple cells (typically 14-16 cells per module for SBR batteries)
- The BMS assigns a unique position number to each cell
- The numbering may be sequential across all modules, or module-specific

### Example Calculation (Estimate)

If you have 5 modules with ~16 cells each:
- Module 1: Cells ~1-16 (estimated)
- Module 2: Cells ~17-32 (estimated)
- Module 3: Cells ~33-48 (estimated)
- Module 4: Cells ~49-64 (estimated)
- Module 5: Cells ~65-80 (estimated)

**Note**: This is an estimate. The actual numbering scheme is manufacturer-specific and may not follow this pattern exactly.

### Your Values

- **Position 269**: This is likely a cell in a higher-numbered module (if sequential) or a specific cell ID
- **Position 769**: This is likely a different cell, possibly in a different module

## Related Sensors

- `Battery 1 Max Voltage of Cell` - Shows the actual voltage value at the max position
- `Battery 1 Min Voltage of Cell` - Shows the actual voltage value at the min position
- `Battery 1 Position of Max Voltage Cell` - The position number (e.g., 269)
- `Battery 1 Position of Min Voltage Cell` - The position number (e.g., 769)
- `Battery 1 Module X Max/Min Cell Voltage` - Module-level data that can help narrow down which module contains the cell
- `Battery 1 Max Voltage Cell Info` - Human-readable format: "Cell Position 269 (3.3457 V)"
- `Battery 1 Min Voltage Cell Info` - Human-readable format: "Cell Position 769 (3.3390 V)"

## Notes

- Position values are read directly from Modbus registers (addresses 10757 and 10759)
- The numbering scheme is manufacturer-specific and may not follow a simple "Module X, Cell Y" pattern
- For detailed cell-level diagnostics, refer to the module-specific cell voltage sensors
- The position helps identify which specific cell needs attention for balancing
- If the same position consistently shows extreme values, that cell may require service
