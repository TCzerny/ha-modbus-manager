"""ModbusManager Select Platform."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity_registry import EntityRegistry, async_get

from .const import DOMAIN, NameType
from .device_base import ModbusManagerDeviceBase
from .entities import ModbusRegisterEntity
from .logger import ModbusManagerLogger
from .device_common import setup_platform_entities

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Richte die ModbusManager Select Entities ein."""
    return await setup_platform_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        entity_types=[ModbusRegisterEntity, SelectEntity],
        platform_name="Select"
    ) 
