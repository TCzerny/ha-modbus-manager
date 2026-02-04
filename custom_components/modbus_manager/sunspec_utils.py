"""SunSpec protocol utilities for Modbus Manager.

SunSpec is an open communication standard for monitoring and controlling
Distributed Energy Resource (DER) systems. This module provides utilities
for detecting SunSpec model start addresses and calculating register addresses
based on SunSpec model offsets.
"""

from typing import Any, Dict, List, Optional

from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

# Standard SunSpec Model IDs
SUNSPEC_MODEL_COMMON = 1  # Common Model Block
SUNSPEC_MODEL_INVERTER_SINGLE_PHASE = 103  # Single Phase Inverter
SUNSPEC_MODEL_INVERTER_MPPT = 160  # Multiple MPPT Inverter Extension
SUNSPEC_MODEL_BATTERY = 124  # Battery

# Common SunSpec start addresses (typical defaults)
SUNSPEC_DEFAULT_START_ADDRESS = 40000  # Common default for Holding Registers
SUNSPEC_INPUT_REGISTER_START = 30000  # Common default for Input Registers


async def find_sunspec_model_start_address(
    hub,
    slave_id: int,
    model_id: int,
    start_address: int = SUNSPEC_DEFAULT_START_ADDRESS,
    max_search_range: int = 1000,
    input_type: str = "holding",
) -> Optional[int]:
    """Find the start address of a SunSpec model by reading Model ID registers.

    SunSpec devices typically start with Model ID 1 (Common Model Block) at
    a known address (often 40000 for Holding Registers or 30000 for Input Registers).
    Subsequent models follow sequentially. This function searches for a specific
    model ID within a reasonable range.

    Args:
        hub: Modbus hub instance for reading registers
        slave_id: Modbus slave ID
        model_id: SunSpec Model ID to find (e.g., 103, 160, 124)
        start_address: Starting address to begin search (default: 40000)
        max_search_range: Maximum number of registers to search (default: 1000)
        input_type: "input" or "holding" (default: "holding")

    Returns:
        Start address of the model if found, None otherwise
    """
    try:
        _LOGGER.debug(
            "Searching for SunSpec Model %d starting at address %d (slave_id=%d, type=%s)",
            model_id,
            start_address,
            slave_id,
            input_type,
        )

        # SunSpec models are typically 2 registers apart (Model ID + Length)
        # But we'll search more conservatively, checking every register
        search_step = 1
        current_address = start_address

        while current_address < start_address + max_search_range:
            try:
                # Read 2 registers: Model ID (16-bit) and Length (16-bit)
                if input_type == "input":
                    from homeassistant.components.modbus.const import (
                        CALL_TYPE_REGISTER_INPUT,
                    )

                    call_type = CALL_TYPE_REGISTER_INPUT
                else:
                    from homeassistant.components.modbus.const import (
                        CALL_TYPE_REGISTER_HOLDING,
                    )

                    call_type = CALL_TYPE_REGISTER_HOLDING

                result = await hub.async_pymodbus_call(
                    slave_id,
                    current_address,
                    2,
                    call_type,
                )

                if result and len(result) >= 1:
                    # First register contains Model ID (16-bit unsigned)
                    read_model_id = result[0] if isinstance(result, list) else result

                    # Handle both list and single value responses
                    if isinstance(read_model_id, list) and len(read_model_id) > 0:
                        read_model_id = read_model_id[0]

                    # Check if we found the model
                    if read_model_id == model_id:
                        _LOGGER.info(
                            "Found SunSpec Model %d at address %d (slave_id=%d)",
                            model_id,
                            current_address,
                            slave_id,
                        )
                        return current_address

                    # If we find Model ID 1 (Common Model Block), we can calculate
                    # subsequent model addresses more efficiently
                    if read_model_id == SUNSPEC_MODEL_COMMON:
                        # Read the length register (next register)
                        length_result = await hub.async_pymodbus_call(
                            slave_id,
                            current_address + 1,
                            1,
                            call_type,
                        )
                        if length_result:
                            length = (
                                length_result[0]
                                if isinstance(length_result, list)
                                else length_result
                            )
                            if isinstance(length, list) and len(length) > 0:
                                length = length[0]

                            # Next model starts after: Model ID (1) + Length (1) + Data (length)
                            next_model_address = current_address + 2 + length
                            _LOGGER.debug(
                                "Found Common Model Block at %d, length=%d, next model at %d",
                                current_address,
                                length,
                                next_model_address,
                            )

                            # If we're looking for a model after Common, jump ahead
                            if model_id > SUNSPEC_MODEL_COMMON:
                                current_address = next_model_address
                                continue

            except Exception as e:
                # Continue searching if read fails
                _LOGGER.debug(
                    "Error reading address %d during SunSpec search: %s",
                    current_address,
                    str(e),
                )

            current_address += search_step

        _LOGGER.warning(
            "SunSpec Model %d not found in range %d-%d (slave_id=%d)",
            model_id,
            start_address,
            start_address + max_search_range,
            slave_id,
        )
        return None

    except Exception as e:
        _LOGGER.error(
            "Error searching for SunSpec Model %d: %s",
            model_id,
            str(e),
        )
        return None


def calculate_sunspec_register_address(
    base_address: int,
    sunspec_offset: int,
    register_address: Optional[int] = None,
) -> int:
    """Calculate the actual Modbus register address for a SunSpec register.

    SunSpec registers are defined with offsets relative to the model start address.
    This function calculates the absolute Modbus address.

    Args:
        base_address: SunSpec model start address (from find_sunspec_model_start_address)
        sunspec_offset: Offset within the SunSpec model (0-based, excluding Model ID and Length)
        register_address: Fallback fixed address if SunSpec calculation fails

    Returns:
        Calculated Modbus register address
    """
    try:
        # SunSpec model structure:
        # - Register 0: Model ID (16-bit)
        # - Register 1: Length (16-bit)
        # - Registers 2+: Data (offset 0-based from start of data)
        # So actual address = base_address + 2 (skip Model ID and Length) + offset
        calculated_address = base_address + 2 + sunspec_offset

        _LOGGER.debug(
            "Calculated SunSpec address: base=%d + 2 + offset=%d = %d",
            base_address,
            sunspec_offset,
            calculated_address,
        )

        return calculated_address

    except Exception as e:
        _LOGGER.error("Error calculating SunSpec address: %s", str(e))
        # Fallback to fixed address if provided
        if register_address is not None:
            _LOGGER.warning(
                "Using fallback address %d due to calculation error", register_address
            )
            return register_address
        raise


async def detect_sunspec_model_addresses(
    hub,
    slave_id: int,
    sunspec_models: Dict[int, Dict[str, Any]],
    user_config: Optional[Dict[int, int]] = None,
    start_address: int = SUNSPEC_DEFAULT_START_ADDRESS,
    input_type: str = "holding",
) -> Dict[int, int]:
    """Detect SunSpec model start addresses with fallback to user configuration.

    This function combines automatic detection with user-provided addresses.
    Priority:
    1. User-provided addresses (from config_flow)
    2. Automatic detection (if user didn't provide)
    3. Template defaults (if detection fails)

    Args:
        hub: Modbus hub instance
        slave_id: Modbus slave ID
        sunspec_models: Dictionary mapping model IDs to model configs (from template)
        user_config: Optional user-provided model addresses (from config_flow)
        start_address: Starting address for search (default: 40000)
        input_type: "input" or "holding" (default: "holding")

    Returns:
        Dictionary mapping model IDs to their start addresses
    """
    detected_addresses: Dict[int, int] = {}

    try:
        # Process each model defined in template
        for model_id, model_config in sunspec_models.items():
            # Priority 1: Use user-provided address if available
            if user_config and model_id in user_config:
                user_address = user_config[model_id]
                if user_address and user_address > 0:
                    detected_addresses[model_id] = user_address
                    _LOGGER.info(
                        "Using user-provided address %d for SunSpec Model %d",
                        user_address,
                        model_id,
                    )
                    continue

            # Priority 2: Try automatic detection
            model_start_address = model_config.get("start_address", start_address)
            detected_address = await find_sunspec_model_start_address(
                hub=hub,
                slave_id=slave_id,
                model_id=model_id,
                start_address=model_start_address,
                input_type=input_type,
            )

            if detected_address:
                detected_addresses[model_id] = detected_address
                _LOGGER.info(
                    "Auto-detected address %d for SunSpec Model %d",
                    detected_address,
                    model_id,
                )
            else:
                # Priority 3: Use template default
                fallback_address = model_config.get("start_address", start_address)
                detected_addresses[model_id] = fallback_address
                _LOGGER.warning(
                    "Using template default address %d for SunSpec Model %d (detection failed)",
                    fallback_address,
                    model_id,
                )

        return detected_addresses

    except Exception as e:
        _LOGGER.error("Error detecting SunSpec model addresses: %s", str(e))
        # Return template defaults as fallback
        fallback_addresses = {}
        for model_id, model_config in sunspec_models.items():
            fallback_addresses[model_id] = model_config.get(
                "start_address", start_address
            )
        return fallback_addresses
