"""ModbusManager Sensor Platform."""
from __future__ import annotations

<<<<<<< HEAD
import logging
from typing import Any

=======
>>>>>>> task/name_helpers_2025-01-16_1
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity
<<<<<<< HEAD
from homeassistant.helpers.entity_registry import EntityRegistry, async_get

from .const import DOMAIN
from .device_base import ModbusManagerDeviceBase
from .entities import ModbusRegisterEntity
=======

from .const import DOMAIN
from .device_base import ModbusManagerDeviceBase as ModbusManagerDevice
>>>>>>> task/name_helpers_2025-01-16_1
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

<<<<<<< HEAD
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Richte die ModbusManager Sensor Entities ein."""
    return await setup_platform_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        entity_types=[ModbusRegisterEntity, SensorEntity],
        platform_name="Sensor"
    )

async def validate_entity(entity: SensorEntity, registry: EntityRegistry, device: ModbusManagerDeviceBase) -> bool:
    """Validiere eine Entity vor der Registrierung."""
    try:
        # Prüfe ob alle notwendigen Attribute vorhanden sind
        required_attrs = ['entity_id', 'unique_id', 'name']
        for attr in required_attrs:
            if not hasattr(entity, attr) or getattr(entity, attr) is None:
                _LOGGER.error(
                    f"Entity fehlt Pflichtattribut: {attr}",
                    extra={
                        "device": device.name,
                        "entity": str(entity)
                    }
                )
                return False

        # Prüfe auf doppelte Registrierung
        existing_entity = registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            entity.unique_id
        )
        if existing_entity:
            _LOGGER.warning(
                "Entity bereits registriert",
                extra={
                    "device": device.name,
                    "entity_id": entity.entity_id,
                    "existing_id": existing_entity
                }
            )
            return False

        # Validiere Device-Zuordnung
        if not entity.device_info:
            _LOGGER.error(
                "Entity hat keine Device-Info",
                extra={
                    "device": device.name,
                    "entity_id": entity.entity_id
                }
            )
            return False

        return True

    except Exception as e:
        _LOGGER.error(
            "Fehler bei der Entity-Validierung",
            extra={
                "error": str(e),
                "device": device.name,
                "entity": str(entity),
                "traceback": str(e.__traceback__)
            }
        )
        return False 
=======
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
>>>>>>> task/name_helpers_2025-01-16_1
