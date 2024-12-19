"""Fehlerbehandlung für Modbus Manager."""
from typing import Optional
from pymodbus.exceptions import ModbusException

class ModbusDeviceError(Exception):
    """Basisklasse für Modbus-Gerätefehler."""
    def __init__(self, message: str, device_name: Optional[str] = None):
        self.device_name = device_name
        super().__init__(message)

def handle_modbus_error(error: Exception, device_name: Optional[str] = None) -> ModbusDeviceError:
    """Konvertiert Modbus-Fehler in ModbusDeviceError."""
    if isinstance(error, ModbusException):
        return ModbusDeviceError(f"Modbus Fehler: {str(error)}", device_name)
    return ModbusDeviceError(f"Unerwarteter Fehler: {str(error)}", device_name) 