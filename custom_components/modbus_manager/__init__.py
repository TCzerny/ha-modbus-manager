"""The Modbus Manager Integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from .const import DOMAIN
from .modbus_hub import ModbusManagerHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry."""
    try:
        # Erstelle Hub-Instanz
        hub = ModbusManagerHub(hass, entry)
        
        # Speichere Hub in hass.data
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
        
        # Setup Hub
        if not await hub.async_setup():
            return False
            
        # Setup Plattformen
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler beim Setup der Integration: %s", str(e))
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        # Unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        
        if unload_ok:
            # Cleanup hub
            hub = hass.data[DOMAIN][entry.entry_id]
            await hub.async_teardown()
            
            # Remove from hass.data
            hass.data[DOMAIN].pop(entry.entry_id)
            
        return unload_ok
        
    except Exception as e:
        _LOGGER.error("Fehler beim Unload der Integration: %s", str(e))
        return False
