"""Modbus utility functions for function code handling and byte ordering."""

import struct
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


def _normalize_byte_order(byte_order: str | None) -> str:
    """Normalize byte order to supported values."""
    return "little" if str(byte_order).lower() == "little" else "big"


def _is_word_swap_enabled(swap: str | bool | None) -> bool:
    """Check whether word swap is enabled.

    Backward compatibility:
    - Historical templates mostly use `swap: word`
    - Some templates/docs mention boolean swap values
    """
    if isinstance(swap, bool):
        return swap
    return str(swap).lower() == "word"


def is_valid_modbus_address(address: object) -> bool:
    """Return True for supported Modbus register addresses.

    Modbus templates in this project allow zero-based addresses,
    so address 0 is valid while negative values are rejected.
    """
    return isinstance(address, int) and not isinstance(address, bool) and address >= 0


def registers_to_bytes(
    registers: list[int],
    byte_order: str = "big",
    swap: str | bool = "none",
) -> bytes:
    """Convert Modbus 16-bit registers to byte stream with byte/word order."""
    if not registers:
        return b""

    words = list(registers)
    if _is_word_swap_enabled(swap):
        words.reverse()

    normalized_byte_order = _normalize_byte_order(byte_order)
    byte_values: list[int] = []
    for word in words:
        value = int(word) & 0xFFFF
        high_byte = (value >> 8) & 0xFF
        low_byte = value & 0xFF
        if normalized_byte_order == "little":
            byte_values.extend([low_byte, high_byte])
        else:
            byte_values.extend([high_byte, low_byte])

    return bytes(byte_values)


def bytes_to_registers(
    data: bytes,
    byte_order: str = "big",
    swap: str | bool = "none",
) -> list[int]:
    """Convert byte stream to Modbus 16-bit registers with byte/word order."""
    if not data:
        return []
    if len(data) % 2 != 0:
        raise ValueError("Byte length must be even to convert to Modbus registers")

    normalized_byte_order = _normalize_byte_order(byte_order)
    registers: list[int] = []
    for idx in range(0, len(data), 2):
        first = data[idx]
        second = data[idx + 1]
        if normalized_byte_order == "little":
            reg = (second << 8) | first
        else:
            reg = (first << 8) | second
        registers.append(reg)

    if _is_word_swap_enabled(swap):
        registers.reverse()

    return registers


def encode_register_write_value(
    value, register_config: dict
) -> tuple[int | list[int], int]:
    """Encode a value to Modbus register payload based on register config.

    Returns:
        tuple(write_value, register_count)
    """
    data_type = register_config.get("data_type", "uint16")
    byte_order = register_config.get("byte_order", "big")
    swap = register_config.get("swap", "none")

    if data_type in ("float", "float32"):
        bytes_data = struct.pack(">f", float(value))
        regs = bytes_to_registers(bytes_data, byte_order=byte_order, swap=swap)
        return regs, 2

    if data_type == "float64":
        bytes_data = struct.pack(">d", float(value))
        regs = bytes_to_registers(bytes_data, byte_order=byte_order, swap=swap)
        return regs, 4

    if data_type in ("uint32", "int32"):
        int_value = int(value)
        if data_type == "int32":
            bytes_data = int_value.to_bytes(4, byteorder="big", signed=True)
        else:
            bytes_data = int_value.to_bytes(4, byteorder="big", signed=False)
        regs = bytes_to_registers(bytes_data, byte_order=byte_order, swap=swap)
        return regs, 2

    if data_type == "string":
        raw_value = value if isinstance(value, str) else str(value)
        encoding = register_config.get("encoding", "utf-8")
        encoded = raw_value.encode(encoding, errors="ignore")

        max_length = register_config.get("max_length")
        if max_length is not None:
            encoded = encoded[: int(max_length)]

        configured_count = register_config.get("count")
        if configured_count:
            target_bytes = int(configured_count) * 2
            encoded = encoded[:target_bytes].ljust(target_bytes, b"\x00")
            count = int(configured_count)
        else:
            if len(encoded) % 2 != 0:
                encoded += b"\x00"
            count = max(1, len(encoded) // 2) if encoded else 1
            encoded = encoded.ljust(count * 2, b"\x00")

        regs = bytes_to_registers(encoded, byte_order=byte_order, swap=swap)
        return regs, count

    count = register_config.get("count", 1) or 1
    return int(value), int(count)
