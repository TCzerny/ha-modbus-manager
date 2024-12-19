"""The Modbus Manager Integration."""
from __future__ import annotations

import asyncio
from typing import Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .modbus_hub import ModbusManagerHub

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richte ModbusManager basierend auf einem ConfigEntry ein."""
    hass.data.setdefault(DOMAIN, {})
    
    # Erstelle und initialisiere den Hub
    hub = ModbusManagerHub(hass, entry)
    if not await hub.async_setup():
        return False
    
    hass.data[DOMAIN][entry.entry_id] = hub
    
    # Lade die Plattformen
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entlade einen ConfigEntry."""
    # Entlade die Plattformen
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Führe Teardown für den Hub durch
        hub = hass.data[DOMAIN][entry.entry_id]
        await hub.async_teardown()
        
        # Entferne den Hub aus den Daten
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
