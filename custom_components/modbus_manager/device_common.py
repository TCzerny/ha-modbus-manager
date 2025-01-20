"""Common functionality for Modbus Manager devices."""
from __future__ import annotations

from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta

from homeassistant.const import CONF_NAME, CONF_SLAVE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, NameType, DEFAULT_SLAVE
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class DeviceCommon:
    """Common functionality for Modbus Manager devices."""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the common device functionality."""
        self.hass = hass
        self.config_entry = config_entry
        self.name = config_entry.data.get(CONF_NAME, "")
        self.slave = config_entry.data.get(CONF_SLAVE, DEFAULT_SLAVE)
        
    def get_register_name(self, register_name: str, name_type: NameType = NameType.DISPLAY_NAME) -> str:
        """Get the formatted name for a register."""
        if name_type == NameType.BASE_NAME:
            return register_name
        elif name_type == NameType.UNIQUE_ID:
            return f"{self.name}_{register_name}".lower()
        else:  # DISPLAY_NAME
            return f"{self.name} {register_name}" 