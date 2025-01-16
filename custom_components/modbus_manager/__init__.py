"""The Modbus Manager Integration."""
from __future__ import annotations

import logging
import asyncio
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .logger import ModbusManagerLogger
from .modbus_hub import ModbusManagerHub

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SCRIPT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH
]

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Modbus Manager component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Erstelle und initialisiere den Hub
    hub = ModbusManagerHub(hass, entry)
    if not await hub.async_setup():
        return False
        
    # Speichere den Hub in hass.data
    hass.data[DOMAIN][entry.entry_id] = hub
    
    # Importiere die Plattformen asynchron
    for platform in PLATFORMS:
        await helper_importlib.async_import_module(
            name=f"custom_components.{DOMAIN}.{platform}",
            hass=hass
        )
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
