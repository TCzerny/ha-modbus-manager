"""ModbusManager Hub Implementation."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

from homeassistant.components.modbus import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    get_hub,
    ModbusHub
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SLAVE,
    EVENT_HOMEASSISTANT_STOP
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .device import ModbusManagerDevice
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)
