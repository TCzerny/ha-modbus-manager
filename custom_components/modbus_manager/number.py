"""ModbusManager Number Platform."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity_registry import EntityRegistry, async_get

from .const import DOMAIN, NameType
from .device_base import ModbusManagerDeviceBase
from .entities import ModbusRegisterEntity
from .logger import ModbusManagerLogger
from .device_common import setup_platform_entities

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Richte die ModbusManager Number Entities ein."""
    return await setup_platform_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        entity_types=[ModbusRegisterEntity, NumberEntity],
        platform_name="Number"
    )

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richte Number Entities basierend auf einem Config Entry ein."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    # Hole die Entities aus dem Hub
    entities = []
    for device in hub._devices.values():
        if hasattr(device, "entity_manager"):
            entities.extend([
                entity for entity in device.entity_manager._entities.values()
                if isinstance(entity, NumberEntity)
            ])
    
    if entities:
        async_add_entities(entities, True) 