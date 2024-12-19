"""Support for Modbus Manager scripts."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device_base import ModbusManagerDeviceBase
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scripts from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    # Sammle alle Script Entities von allen Geräten
    entities = []
    for device in hub._devices.values():
        if isinstance(device, ModbusManagerDeviceBase):
            # Füge alle Script Entities aus dem Device hinzu
            for entity in device.entities.values():
                if hasattr(entity, 'entity_id') and entity.entity_id and entity.entity_id.startswith("script."):
                    entities.append(entity)
    
    if entities:
        _LOGGER.debug(f"Füge {len(entities)} Script Entities hinzu")
        async_add_entities(entities) 