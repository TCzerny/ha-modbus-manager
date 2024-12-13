"""Modbus Manager specific errors."""
from homeassistant.exceptions import HomeAssistantError

class ModbusManagerError(HomeAssistantError):
    """Base error for Modbus Manager."""

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

def handle_modbus_error(error: Exception) -> ModbusManagerError:
    """Convert pymodbus errors to Modbus Manager errors."""
    error_mapping = {
        "Connection refused": ModbusConnectionError("Connection refused by device"),
        "Timeout": ModbusTimeoutError("Device did not respond in time"),
        "Invalid CRC": ModbusDeviceError("Invalid CRC in device response"),
        "Invalid response": ModbusDeviceError("Device sent invalid response"),
    }
    
    for error_text, error_class in error_mapping.items():
        if error_text in str(error):
            return error_class
            
    return ModbusManagerError(f"Unknown error: {str(error)}") 