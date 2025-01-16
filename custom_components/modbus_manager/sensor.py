"""ModbusManager Sensor Platform."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .device import ModbusManagerDevice
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richte Sensor Entities basierend auf einem Config Entry ein."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    # Hole die Entities aus dem Hub
    entities = []
    for device in hub._devices.values():
        if hasattr(device, "entities"):
            entities.extend([
                entity for entity in device.entities.values()
                if isinstance(entity, SensorEntity)
            ])
    
    if entities:
        async_add_entities(entities, True) 