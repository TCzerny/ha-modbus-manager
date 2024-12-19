"""Support for Modbus Manager automations."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import ModbusManagerDevice
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up automations from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    # Sammle alle Automation Entities von allen Geräten
    entities = []
    for device in hub._devices.values():
        if isinstance(device, ModbusManagerDevice):
            # Füge alle Automation Entities aus dem Device hinzu
            for entity in device.entities.values():
                if hasattr(entity, 'entity_id') and entity.entity_id and entity.entity_id.startswith("automation."):
                    entities.append(entity)
    
    if entities:
        _LOGGER.debug(f"Füge {len(entities)} Automation Entities hinzu")
        async_add_entities(entities) 