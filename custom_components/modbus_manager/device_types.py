"""Type definitions for Modbus Manager."""
from typing import Protocol, Dict, Any

class ModbusManagerDeviceProtocol(Protocol):
    """Protocol for ModbusManagerDevice."""
    hass: Any
    name: str
    device_type: str
    name_helper: Any 