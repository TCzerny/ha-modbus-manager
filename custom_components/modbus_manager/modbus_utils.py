"""Modbus utility functions for function code handling."""

from typing import Optional

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_REGISTERS,
)

# Try to import CALL_TYPE_WRITE_REGISTER (for Function Code 6)
# If it doesn't exist, we'll use CALL_TYPE_WRITE_REGISTERS as fallback
try:
    from homeassistant.components.modbus.const import CALL_TYPE_WRITE_REGISTER
except ImportError:
    # Fallback: Use WRITE_REGISTERS for single register writes
    # Some Home Assistant versions may not have CALL_TYPE_WRITE_REGISTER
    CALL_TYPE_WRITE_REGISTER = CALL_TYPE_WRITE_REGISTERS


def get_read_call_type(input_type: str, function_code: Optional[int] = None) -> str:
    """Get the appropriate call type for reading registers.

    Args:
        input_type: "input" or "holding"
        function_code: Optional Modbus function code (3 or 4)

    Returns:
        CALL_TYPE constant for reading
    """
    if function_code == 3:
        return CALL_TYPE_REGISTER_HOLDING
    elif function_code == 4:
        return CALL_TYPE_REGISTER_INPUT
    else:
        # Auto-detect based on input_type
        if input_type == "input":
            return CALL_TYPE_REGISTER_INPUT
        else:
            return CALL_TYPE_REGISTER_HOLDING


def get_write_call_type(count: int = 1, function_code: Optional[int] = None) -> str:
    """Get the appropriate call type for writing registers.

    Args:
        count: Number of registers to write
        function_code: Optional Modbus function code (6 or 16)

    Returns:
        CALL_TYPE constant for writing
    """
    if function_code == 6:
        # Function Code 6: Preset Single Register
        return CALL_TYPE_WRITE_REGISTER
    elif function_code == 16:
        # Function Code 16: Preset Multiple Registers
        return CALL_TYPE_WRITE_REGISTERS
    else:
        # Auto-detect: use 6 for single register, 16 for multiple
        if count == 1:
            return CALL_TYPE_WRITE_REGISTER
        else:
            return CALL_TYPE_WRITE_REGISTERS
