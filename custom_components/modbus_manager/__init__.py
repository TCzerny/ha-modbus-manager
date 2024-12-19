"""The Modbus Manager integration."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
from homeassistant.helpers import entity_registry, device_registry
from .const import DOMAIN, CONF_DEVICE_TYPE
from .modbus_hub import ModbusManagerHub
from .logger import ModbusManagerLogger
import asyncio

_LOGGER = ModbusManagerLogger("init")

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Modbus Manager component."""
    _LOGGER.debug("Setting up Modbus Manager integration")
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Modbus Manager from a config entry."""
    _LOGGER.debug(
        "Setting up config entry", 
        extra={"entry_id": entry.entry_id, "name": entry.data[CONF_NAME]}
    )
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave = entry.data[CONF_SLAVE]
    device_type = entry.data[CONF_DEVICE_TYPE]
    
    # Erstelle Hub-Instanz und übergebe config_entry
    hub = ModbusManagerHub(name, host, port, slave, device_type, hass, entry)
    
    # Speichere den Hub in hass.data bevor async_setup aufgerufen wird
    hass.data[DOMAIN][entry.entry_id] = hub
    _LOGGER.debug(f"Hub saved in hass.data under entry_id={entry.entry_id}")
    
    if not await hub.async_setup():
        _LOGGER.error(f"Hub Setup failed for entry_id={entry.entry_id}")
        return False

    # Forward setup zu sensor und switch Plattformen und warten darauf
    await asyncio.gather(
        hass.config_entries.async_forward_entry_setup(entry, "sensor"),
        hass.config_entries.async_forward_entry_setup(entry, "switch")
    )
    
    _LOGGER.info(f"Modbus Manager Integration for {entry.entry_id} successfully set up")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
       """Entlade einen Konfigurationseintrag und entferne alle zugehörigen Komponenten."""
       hub = hass.data[DOMAIN].get(entry.entry_id)
       if not hub:
           return True

       ent_reg = entity_registry.async_get(hass)
       dev_reg = device_registry.async_get(hass)

       # Entlade Plattformen
       unload_ok = all(
           await asyncio.gather(
               *[
                   hass.config_entries.async_forward_entry_unload(entry, component)
                   for component in ["sensor", "switch", "binary_sensor", "number"]
               ]
           )
       )

       if unload_ok:
           # Entferne Gerät aus dem Registry
           device_entry = dev_reg.async_get_device(identifiers={(DOMAIN, hub.name)})
           if device_entry:
               _LOGGER.debug("Entferne Gerät: %s", hub.name)
               dev_reg.async_remove_device(device_entry.id)

           # Schließe Verbindung und bereinige
           await hub.async_teardown()
           hass.data[DOMAIN].pop(entry.entry_id)
           _LOGGER.info("Modbus Manager Integration für %s erfolgreich entfernt", hub.name)

       return unload_ok