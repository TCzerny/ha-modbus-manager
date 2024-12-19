"""The Modbus Manager Integration."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    CONF_SLAVE,
    CONF_DEVICE_TYPE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
)
from .modbus_hub import ModbusManagerHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_SLAVE, default=DEFAULT_SLAVE_ID): cv.positive_int,
                vol.Required(CONF_DEVICE_TYPE): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Modbus Manager component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Erstelle den Hub
    hub = ModbusManagerHub(
        name=entry.data[CONF_NAME],
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        slave=entry.data.get(CONF_SLAVE, DEFAULT_SLAVE_ID),
        device_type=entry.data[CONF_DEVICE_TYPE],
        hass=hass,
        config_entry=entry,
    )

    # Speichere den Hub in der Home Assistant Datenstruktur
    hass.data[DOMAIN][entry.entry_id] = hub

    # Setup des Hubs
    if not await hub.async_setup():
        return False

    # Setup der Plattformen
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hub = hass.data[DOMAIN].pop(entry.entry_id)
        await hub.async_teardown()
    
    return unload_ok
