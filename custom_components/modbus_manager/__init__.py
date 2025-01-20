"""The Modbus Manager Integration."""
from __future__ import annotations

<<<<<<< HEAD
import asyncio
import logging
=======
import logging
import asyncio
>>>>>>> task/name_helpers_2025-01-16_1
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import importlib as helper_importlib
from homeassistant.helpers.typing import ConfigType

<<<<<<< HEAD
from .const import DOMAIN, PLATFORMS
from .modbus_hub import ModbusManagerHub
from .logger import ModbusManagerLogger
=======
from .const import DOMAIN
from .logger import ModbusManagerLogger
from .modbus_hub import ModbusManagerHub

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH
]
>>>>>>> task/name_helpers_2025-01-16_1

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Modbus Manager component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry."""
<<<<<<< HEAD
    try:
        hass.data.setdefault(DOMAIN, {})
        
        # Erstelle und initialisiere den Hub
        try:
            hub = ModbusManagerHub(hass, entry)
        except ValueError as config_error:
            _LOGGER.error(
                "Ungültige Hub-Konfiguration",
                extra={
                    "error": str(config_error),
                    "entry_id": entry.entry_id
                }
            )
            return False
            
        if not await hub.async_setup():
            _LOGGER.error(
                "Hub-Setup fehlgeschlagen",
                extra={"entry_id": entry.entry_id}
            )
            return False
            
        # Speichere den Hub in hass.data
        hass.data[DOMAIN][entry.entry_id] = hub
        
        # Importiere die Plattformen asynchron
        for platform in PLATFORMS:
            try:
                platform_module = await helper_importlib.async_import_module(
                    name=f"custom_components.{DOMAIN}.{platform}",
                    hass=hass
                )
                _LOGGER.debug(
                    f"Platform {platform} erfolgreich importiert",
                    extra={
                        "entry_id": entry.entry_id,
                        "platform": platform
                    }
                )
            except ImportError as e:
                _LOGGER.error(
                    f"Fehler beim Importieren der Platform {platform}",
                    extra={
                        "error": str(e),
                        "entry_id": entry.entry_id,
                        "platform": platform
                    }
                )
                return False
        
        # Warte kurz, damit der Hub Zeit hat, alle Entities zu initialisieren
        await asyncio.sleep(2)
        
        # Setup der Plattformen
        try:
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            _LOGGER.info(
                "Alle Plattformen erfolgreich eingerichtet",
                extra={
                    "entry_id": entry.entry_id,
                    "platforms": PLATFORMS
                }
            )
            return True
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup der Plattformen",
                extra={
                    "error": str(e),
                    "entry_id": entry.entry_id
                }
            )
            return False
            
    except Exception as error:
        _LOGGER.error(
            "Fehler beim Setup der Integration",
            extra={
                "error": str(error),
                "entry_id": entry.entry_id,
                "traceback": error.__traceback__
            }
        )
        return False
=======
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
>>>>>>> task/name_helpers_2025-01-16_1

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
