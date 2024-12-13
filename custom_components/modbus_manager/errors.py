"""Modbus Manager specific errors."""
from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ModbusException
from typing import Optional, Type

class ModbusManagerError(HomeAssistantError):
    """Base error for Modbus Manager."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Initialize the error."""
        super().__init__(message)
        self.original_error = original_error

class ModbusConnectionError(ModbusManagerError):
    """Error to indicate connection problems."""

class ModbusConfigError(ModbusManagerError):
    """Error to indicate a configuration problem."""

class ModbusDeviceError(ModbusManagerError):
    """Error to indicate a device specific problem."""

class ModbusRegisterError(ModbusManagerError):
    """Error to indicate a register access problem."""

class ModbusTimeoutError(ModbusManagerError):
    """Error to indicate a timeout."""

ERROR_MAPPING = {
    "Connection refused": (ModbusConnectionError, "Connection refused by device"),
    "Connection reset": (ModbusConnectionError, "Connection reset by device"),
    "Timeout": (ModbusTimeoutError, "Device did not respond in time"),
    "Invalid CRC": (ModbusDeviceError, "Invalid CRC in device response"),
    "Invalid response": (ModbusDeviceError, "Device sent invalid response"),
    "Invalid message": (ModbusDeviceError, "Invalid message received"),
    "Invalid address": (ModbusRegisterError, "Invalid register address"),
}

def handle_modbus_error(error: Exception) -> ModbusManagerError:
    """Convert pymodbus errors to Modbus Manager errors."""
    error_str = str(error)
    
    # Handle pymodbus exceptions specifically
    if isinstance(error, ModbusException):
        return ModbusDeviceError(
            f"Modbus protocol error: {error_str}",
            original_error=error
        )
    
    # Check mapped errors
    for error_text, (error_class, error_message) in ERROR_MAPPING.items():
        if error_text.lower() in error_str.lower():
            return error_class(error_message, original_error=error)
    
    # Default error handling
    return ModbusManagerError(f"Unknown error: {error_str}", original_error=error) 