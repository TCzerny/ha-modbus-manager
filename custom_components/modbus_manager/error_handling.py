"""Error handling utilities for Modbus communication.

This module implements error value detection and handling for unavailable registers
as specified in the PDF data requirements.
"""
from typing import Any, List, Optional, Union

from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

# Error values for unavailable registers as per PDF requirements
ERROR_VALUES = {
    # Unsigned values
    "uint16": 0xFFFF,
    "uint32": 0xFFFFFFFF,
    # Signed values (maximum positive number)
    "int16": 0x7FFF,
    "int32": 0x7FFFFFFF,
    # UTF-8 strings
    "string": 0x00,
    "utf8": 0x00,
}

# Alternative error values for different representations
ERROR_VALUES_ALT = {
    # For 16-bit values that might be represented as single register
    "uint16_single": 0xFFFF,
    "int16_single": 0x7FFF,
    # For 32-bit values that might be represented as two registers
    "uint32_high": 0xFFFF,  # High word
    "uint32_low": 0xFFFF,  # Low word
    "int32_high": 0x7FFF,  # High word
    "int32_low": 0x7FFF,  # Low word
}


def is_unavailable_register_value(
    value: Any, data_type: str, raw_registers: Optional[List[int]] = None
) -> bool:
    """Check if a value represents an unavailable register.

    Args:
        value: The processed value to check
        data_type: The data type (uint16, int16, uint32, int32, string, utf8)
        raw_registers: Optional raw register values for more detailed checking

    Returns:
        True if the value indicates an unavailable register, False otherwise
    """
    try:
        if value is None:
            return True

        # Get the error value for this data type
        error_value = ERROR_VALUES.get(data_type.lower())
        if error_value is None:
            _LOGGER.debug("Unknown data type for error checking: %s", data_type)
            return False

        # For string types, check for null byte
        if data_type.lower() in ["string", "utf8"]:
            if isinstance(value, str):
                # Check if string is empty or contains only null characters
                return len(value.strip("\x00")) == 0
            elif isinstance(value, (list, tuple)) and raw_registers:
                # Check if all registers contain null values
                return all(reg == 0x00 for reg in raw_registers)
            else:
                return value == 0x00

        # For numeric types, check against error values
        if isinstance(value, (int, float)):
            # Convert to integer for comparison
            int_value = int(value)

            # Check against the error value
            if int_value == error_value:
                _LOGGER.debug(
                    "Detected unavailable register for %s: value=0x%X matches error value 0x%X",
                    data_type,
                    int_value,
                    error_value,
                )
                return True

            # For 32-bit types, also check raw registers if available
            if data_type.lower() in ["uint32", "int32"] and raw_registers:
                # Check if both registers contain the error value
                if len(raw_registers) >= 2:
                    high_word = raw_registers[0]
                    low_word = raw_registers[1]

                    if data_type.lower() == "uint32":
                        # For uint32, both words should be 0xFFFF
                        if high_word == 0xFFFF and low_word == 0xFFFF:
                            _LOGGER.debug(
                                "Detected unavailable uint32 register: both words are 0xFFFF"
                            )
                            return True
                    elif data_type.lower() == "int32":
                        # For int32, both words should be 0x7FFF
                        if high_word == 0x7FFF and low_word == 0x7FFF:
                            _LOGGER.debug(
                                "Detected unavailable int32 register: both words are 0x7FFF"
                            )
                            return True

        return False

    except Exception as e:
        _LOGGER.error("Error checking unavailable register value: %s", str(e))
        return False


def get_unavailable_register_value(data_type: str) -> Any:
    """Get the appropriate error value for an unavailable register.

    Args:
        data_type: The data type (uint16, int16, uint32, int32, string, utf8)

    Returns:
        The error value for the specified data type
    """
    return ERROR_VALUES.get(data_type.lower(), None)


def handle_unavailable_register(data_type: str, register_name: str) -> Any:
    """Handle an unavailable register by returning the appropriate error value.

    Args:
        data_type: The data type of the register
        register_name: The name of the register for logging

    Returns:
        The appropriate error value or None
    """
    try:
        error_value = get_unavailable_register_value(data_type)

        if error_value is None:
            _LOGGER.warning(
                "No error value defined for data type %s in register %s",
                data_type,
                register_name,
            )
            return None

        _LOGGER.debug(
            "Register %s is unavailable (data_type: %s), returning error value: %s",
            register_name,
            data_type,
            error_value,
        )

        # For string types, return empty string
        if data_type.lower() in ["string", "utf8"]:
            return ""

        # For numeric types, return the error value
        return error_value

    except Exception as e:
        _LOGGER.error(
            "Error handling unavailable register %s: %s", register_name, str(e)
        )
        return None


def is_error_value(value: Any, data_type: str) -> bool:
    """Check if a value is an error value (not necessarily unavailable).

    This is a more general check that can be used for various error conditions.

    Args:
        value: The value to check
        data_type: The data type

    Returns:
        True if the value represents an error condition
    """
    try:
        if value is None:
            return True

        # Check for unavailable register values
        if is_unavailable_register_value(value, data_type):
            return True

        # Additional error checks can be added here
        # For example, checking for specific error codes, out-of-range values, etc.

        return False

    except Exception as e:
        _LOGGER.error("Error checking error value: %s", str(e))
        return True  # Assume error if we can't determine


def log_register_error(
    register_name: str, data_type: str, value: Any, error_type: str = "unavailable"
):
    """Log information about a register error.

    Args:
        register_name: The name of the register
        data_type: The data type of the register
        value: The value that caused the error
        error_type: The type of error (unavailable, invalid, etc.)
    """
    try:
        if error_type == "unavailable":
            _LOGGER.warning(
                "Register %s (%s) is unavailable - value: %s (0x%X)",
                register_name,
                data_type,
                value,
                value if isinstance(value, int) else 0,
            )
        else:
            _LOGGER.warning(
                "Register %s (%s) has %s value: %s",
                register_name,
                data_type,
                error_type,
                value,
            )

    except Exception as e:
        _LOGGER.error("Error logging register error: %s", str(e))


# Test function for validation
def test_error_handling():
    """Test error handling implementation with known test cases."""
    test_cases = [
        # (value, data_type, expected_unavailable, description)
        (0xFFFF, "uint16", True, "uint16 unavailable value"),
        (0x7FFF, "int16", True, "int16 unavailable value"),
        (0xFFFFFFFF, "uint32", True, "uint32 unavailable value"),
        (0x7FFFFFFF, "int32", True, "int32 unavailable value"),
        ("", "string", True, "empty string"),
        (0x00, "string", True, "null byte"),
        (0x1234, "uint16", False, "valid uint16"),
        (0x1234, "int16", False, "valid int16"),
        (0x12345678, "uint32", False, "valid uint32"),
        (0x12345678, "int32", False, "valid int32"),
        ("Hello", "string", False, "valid string"),
    ]

    _LOGGER.info("Testing error handling implementation...")

    for i, (value, data_type, expected, desc) in enumerate(test_cases):
        try:
            result = is_unavailable_register_value(value, data_type)
            status = "PASS" if result == expected else "FAIL"
            _LOGGER.info(
                "Test %d (%s): %s - value=%s, data_type=%s, expected=%s, got=%s",
                i + 1,
                desc,
                status,
                value,
                data_type,
                expected,
                result,
            )
        except Exception as e:
            _LOGGER.error("Test %d (%s): ERROR - %s", i + 1, desc, str(e))

    _LOGGER.info("Error handling test completed")


if __name__ == "__main__":
    # Run tests when module is executed directly
    test_error_handling()
