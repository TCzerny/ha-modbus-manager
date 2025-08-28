"""The Modbus Manager Integration."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.modbus.hub import ModbusHub
from homeassistant.components.modbus.const import CONF_TYPE, CONF_HOST, CONF_PORT

from .const import DOMAIN, PLATFORMS
from .logger import ModbusManagerLogger
from .performance_monitor import PerformanceMonitor
from .register_optimizer import RegisterOptimizer

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH
]

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Modbus Manager component."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Cleanup Hub
    hub_name = f"modbus_manager_{entry.data['prefix']}"
    if DOMAIN in hass.data and hub_name in hass.data[DOMAIN]:
        hub = hass.data[DOMAIN][hub_name]
        await hub.async_shutdown()
        del hass.data[DOMAIN][hub_name]
    
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry."""
    try:
        hub_name = f"modbus_manager_{entry.data['prefix']}"
        
        # Erzeuge ModbusHub-Instanz mit Standard Home Assistant API
        hub = ModbusHub(
            hass=hass,
            name=hub_name,
            client_type="tcp",
            host=entry.data["host"],
            port=entry.data.get("port", 502),
            delay=entry.data.get("delay", 0),
            timeout=entry.data.get("timeout", 3),
            retries=entry.data.get("retries", 3),
            # Erweiterte Konfiguration
            close_comm_on_error=entry.data.get("close_comm_on_error", True),
            reconnect_delay=entry.data.get("reconnect_delay", 10),
            message_wait_milliseconds=entry.data.get("message_wait", 0),
        )

        # Registriere Hub in hass.data
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN][hub_name] = hub
        
        # Performance-Monitoring und Register-Optimierung initialisieren
        performance_monitor = PerformanceMonitor()
        register_optimizer = RegisterOptimizer()
        
        # In hass.data speichern
        hass.data[DOMAIN][f"{hub_name}_performance"] = performance_monitor
        hass.data[DOMAIN][f"{hub_name}_optimizer"] = register_optimizer
        
        _LOGGER.info("Performance-Monitoring und Register-Optimierung für %s initialisiert", hub_name)

        # Starte Hub
        await hub.async_setup()
        
        _LOGGER.info("Modbus Hub %s erfolgreich gestartet für %s", hub_name, entry.data["host"])

        # Alle Entity-Typen hinzufügen
        await hass.config_entries.async_forward_entry_setup(entry, "sensor")
        await hass.config_entries.async_forward_entry_setup(entry, "number")
        await hass.config_entries.async_forward_entry_setup(entry, "select")
        await hass.config_entries.async_forward_entry_setup(entry, "switch")
        await hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
        await hass.config_entries.async_forward_entry_setup(entry, "button")
        await hass.config_entries.async_forward_entry_setup(entry, "text")
        
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler beim Setup von Modbus Manager: %s", str(e))
        return False
