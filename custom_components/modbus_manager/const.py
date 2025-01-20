"""Constants for the Modbus Manager integration."""
from __future__ import annotations

import logging
from typing import Final
from enum import Enum
from homeassistant.const import Platform

# Setze Debug-Level für detaillierte Logging-Informationen
logging.getLogger(__package__).setLevel(logging.DEBUG)

DOMAIN: Final = "modbus_manager"
CONF_DEVICE_TYPE: Final = "device_type"

# Default values
DEFAULT_TIMEOUT: Final = 3  # Sekunden
DEFAULT_RETRY_ON_EMPTY: Final = True
DEFAULT_RETRIES: Final = 3
DEFAULT_RETRY_DELAY: Final = 0.1

# Standard-Werte
DEFAULT_SLAVE = 1
DEFAULT_PORT = 502

# Service Namen
SERVICE_SET_BATTERY_MODE = "set_battery_mode"
SERVICE_SET_INVERTER_MODE = "set_inverter_mode"
SERVICE_SET_EXPORT_POWER_LIMIT = "set_export_power_limit"

# Event Namen
EVENT_MODBUS_MANAGER_REGISTER_UPDATED = "modbus_manager_register_updated"
EVENT_MODBUS_MANAGER_DEVICE_UPDATED = "modbus_manager_device_updated"
EVENT_MODBUS_MANAGER_ERROR = "modbus_manager_error"

# Plattformen, die diese Integration nutzt
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH
]

class NameType(Enum):
    """Typen für die Namenskonvertierung."""
    BASE_NAME = "base_name"
    UNIQUE_ID = "unique_id"
    DISPLAY_NAME = "display_name"