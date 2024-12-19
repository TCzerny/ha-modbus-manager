"""ModbusManager Select Platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .device_base import ModbusManagerDeviceBase
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richte Select Entities basierend auf einem Config Entry ein."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    # Hole die Entities aus dem Hub
    entities = []
    for device in hub._devices.values():
        if hasattr(device, "entities"):
            entities.extend([
                entity for entity in device.entities.values()
                if isinstance(entity, SelectEntity)
            ])
    
    if entities:
        async_add_entities(entities, True) 