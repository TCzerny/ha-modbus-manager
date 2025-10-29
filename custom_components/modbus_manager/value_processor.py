"""Central value processing for Modbus Manager.

This module provides centralized value processing functions that can be used
by both legacy sensors and coordinator-based entities.
"""

from typing import Any, Dict, Optional

from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


def apply_bit_operations(value: Any, config: Dict[str, Any]) -> Optional[int]:
    """Apply bit operations to a value.

    Supports:
    - bit_position: Extract single bit
    - bit_range: Extract range of bits [start, end]
    - bitmask: Apply AND mask
    - bit_shift: Shift bits left (positive) or right (negative)
    - bit_rotate: Rotate bits left (positive) or right (negative)

    Args:
        value: Input value (int or float)
        config: Configuration dict with bit operation parameters

    Returns:
        Processed integer value or None if error
    """
    try:
        if not isinstance(value, (int, float)):
            return value

        int_value = int(value)

        # 1. Extract bit position (single bit)
        bit_position = config.get("bit_position")
        if bit_position is not None:
            bit_pos = int(bit_position)
            if 0 <= bit_pos <= 31:
                int_value = (int_value >> bit_pos) & 1
            else:
                _LOGGER.warning(
                    "bit_position %d out of range (0-31), skipping", bit_pos
                )

        # 2. Extract bit range
        bit_range = config.get("bit_range")
        if (
            bit_range is not None and bit_position is None
        ):  # Don't apply if bit_position was used
            if isinstance(bit_range, list) and len(bit_range) == 2:
                start_bit, end_bit = bit_range
                if 0 <= start_bit <= end_bit <= 31:
                    mask = ((1 << (end_bit - start_bit + 1)) - 1) << start_bit
                    int_value = (int_value & mask) >> start_bit
                else:
                    _LOGGER.warning(
                        "bit_range %s out of range (0-31), skipping", bit_range
                    )
            else:
                _LOGGER.warning(
                    "bit_range must be list of 2 integers [start, end], got: %s",
                    bit_range,
                )

        # 3. Apply bitmask
        bitmask = config.get("bitmask")
        if bitmask is not None:
            int_value = int_value & int(bitmask)

        # 4. Apply bit shift
        bit_shift = config.get("bit_shift", 0)
        if bit_shift != 0:
            if bit_shift > 0:
                int_value = int_value << bit_shift
            else:
                int_value = int_value >> abs(bit_shift)

        # 5. Apply bit rotation
        bit_rotate = config.get("bit_rotate", 0)
        if bit_rotate != 0:
            bits = 32  # Assume 32-bit integers
            rotate_amount = bit_rotate % bits
            if rotate_amount > 0:
                # Rotate left
                int_value = (
                    (int_value << rotate_amount) | (int_value >> (bits - rotate_amount))
                ) & ((1 << bits) - 1)
            elif rotate_amount < 0:
                # Rotate right
                rotate_amount = abs(rotate_amount)
                int_value = (
                    (int_value >> rotate_amount) | (int_value << (bits - rotate_amount))
                ) & ((1 << bits) - 1)

        return int_value

    except Exception as e:
        _LOGGER.error("Error applying bit operations: %s", str(e))
        return value


def apply_value_mapping(value: Any, config: Dict[str, Any]) -> Any:
    """Apply value mapping (map, flags, options) to a value.

    Priority order:
    1. map: Direct value-to-value mapping
    2. flags: Bit flags to list of active flags
    3. options: Value to option label mapping

    Args:
        value: Input value
        config: Configuration dict with map/flags/options

    Returns:
        Mapped value or original value if no mapping found
    """
    try:
        if value is None:
            return None

        # 1. Apply map (direct value mapping)
        value_map = config.get("map")
        if value_map:
            if isinstance(value, (int, float)):
                int_value = int(value)
                # Try int key first, then string key
                if int_value in value_map:
                    return value_map[int_value]
                elif str(int_value) in value_map:
                    return value_map[str(int_value)]
            elif isinstance(value, str):
                # Try string key first, then int key if string is numeric
                if value in value_map:
                    return value_map[value]
                elif value.isdigit() and int(value) in value_map:
                    return value_map[int(value)]

        # 2. Apply flags (bit flags to list)
        flags = config.get("flags")
        if flags and isinstance(value, (int, float)):
            int_value = int(value)
            active_flags = []
            for bit_pos, flag_name in flags.items():
                try:
                    bit = int(bit_pos)
                    if 0 <= bit <= 31:
                        if (int_value >> bit) & 1:
                            active_flags.append(flag_name)
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid flag bit position: %s", bit_pos)
            if active_flags:
                return ", ".join(active_flags)
            return "None"

        # 3. Apply options (similar to map but for specific use case)
        options = config.get("options")
        if options:
            if isinstance(value, (int, float)):
                int_value = int(value)
                if int_value in options:
                    return options[int_value]
                elif str(int_value) in options:
                    return options[str(int_value)]
            elif isinstance(value, str):
                if value in options:
                    return options[value]

        return value

    except Exception as e:
        _LOGGER.error("Error applying value mapping: %s", str(e))
        return value


def process_register_value(
    value: Any,
    config: Dict[str, Any],
    apply_precision: bool = True,
) -> Any:
    """Complete value processing pipeline.

    Processing order:
    1. Scale and offset (if applicable)
    2. Bit operations (if defined)
    3. Precision/rounding (if applicable and requested)
    4. Value mapping (map/flags/options)

    Args:
        value: Raw register value
        config: Register configuration dict
        apply_precision: Whether to apply precision rounding

    Returns:
        Fully processed value
    """
    try:
        if value is None:
            return None

        processed_value = value

        # 1. Apply scale and offset (for numeric values)
        if isinstance(processed_value, (int, float)):
            scale = config.get("scale", 1.0)
            offset = config.get("offset", 0.0)
            if scale != 1.0 or offset != 0.0:
                processed_value = (processed_value * scale) + offset

        # 2. Apply bit operations (for numeric values)
        # Only apply if at least one bit operation parameter is actually set
        has_bit_ops = any(
            config.get(key) is not None
            for key in ["bitmask", "bit_position", "bit_range"]
        ) or any(config.get(key, 0) != 0 for key in ["bit_shift", "bit_rotate"])

        if isinstance(processed_value, (int, float)) and has_bit_ops:
            processed_value = apply_bit_operations(processed_value, config)

        # 3. Apply precision (after bit operations, before mapping)
        if apply_precision and isinstance(processed_value, (int, float)):
            precision = config.get("precision")
            if precision is not None and precision > 0:
                processed_value = round(float(processed_value), precision)

        # 4. Apply value mapping (map, flags, options)
        if any(config.get(key) for key in ["map", "flags", "options"]):
            processed_value = apply_value_mapping(processed_value, config)

        return processed_value

    except Exception as e:
        _LOGGER.error(
            "Error processing register value for %s: %s",
            config.get("name", "unknown"),
            str(e),
        )
        return value
