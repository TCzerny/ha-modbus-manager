"""ModbusManager Sensor Platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity_registry import EntityRegistry, async_get

from .const import DOMAIN
from .device_base import ModbusManagerDeviceBase
from .entities import ModbusRegisterEntity
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richte Sensor Entities basierend auf einem Config Entry ein."""
    try:
        hub = hass.data[DOMAIN][config_entry.entry_id]
        
        if not hasattr(hub, '_devices'):
            _LOGGER.error(
                "Hub hat keine _devices Eigenschaft",
                extra={"entry_id": config_entry.entry_id}
            )
            return
        
        # Hole das Entity Registry
        entity_registry = async_get(hass)
        
        # Hole die Entities aus dem Hub
        entities = []
        for device in hub._devices.values():
            if not hasattr(device, "entities"):
                _LOGGER.warning(
                    "Device hat keine entities Eigenschaft",
                    extra={
                        "device": device.name if hasattr(device, 'name') else str(device),
                        "entry_id": config_entry.entry_id
                    }
                )
                continue
                
            try:
                # Sammle alle Sensor Entities
                device_entities = []
                for entity in device.entities.values():
                    if isinstance(entity, (SensorEntity, ModbusRegisterEntity)):
                        # Validiere die Entity
                        if not await validate_entity(entity, entity_registry, device):
                            continue
                            
                        _LOGGER.debug(
                            "Sensor Entity validiert",
                            extra={
                                "device": device.name,
                                "entity_id": entity.entity_id if hasattr(entity, 'entity_id') else None,
                                "type": type(entity).__name__,
                                "attributes": {
                                    "name": getattr(entity, "name", None),
                                    "unique_id": getattr(entity, "unique_id", None),
                                    "device_class": getattr(entity, "_attr_device_class", None),
                                    "unit": getattr(entity, "_attr_native_unit_of_measurement", None),
                                    "state_class": getattr(entity, "_attr_state_class", None)
                                }
                            }
                        )
                        device_entities.append(entity)
                
                if device_entities:
                    _LOGGER.info(
                        f"{len(device_entities)} Sensor Entities validiert",
                        extra={
                            "device": device.name,
                            "entry_id": config_entry.entry_id,
                            "entity_ids": [e.entity_id for e in device_entities if hasattr(e, 'entity_id')]
                        }
                    )
                    entities.extend(device_entities)
                    
            except Exception as e:
                _LOGGER.error(
                    "Fehler beim Verarbeiten der Device Entities",
                    extra={
                        "error": str(e),
                        "device": device.name if hasattr(device, 'name') else str(device),
                        "entry_id": config_entry.entry_id,
                        "traceback": str(e.__traceback__)
                    }
                )

        if entities:
            _LOGGER.info(
                f"Füge {len(entities)} validierte Sensor Entities hinzu",
                extra={
                    "entry_id": config_entry.entry_id,
                    "entity_ids": [e.entity_id for e in entities if hasattr(e, 'entity_id')]
                }
            )
            # Füge die Entities hinzu und erzwinge ein Update
            async_add_entities(entities, True)
            
            # Aktualisiere den Hub-Status
            hub.entities_added = True
        else:
            _LOGGER.warning(
                "Keine validierten Sensor Entities gefunden",
                extra={"entry_id": config_entry.entry_id}
            )
            
    except Exception as e:
        _LOGGER.error(
            "Unerwarteter Fehler beim Setup der Sensor Platform",
            extra={
                "error": str(e),
                "entry_id": config_entry.entry_id,
                "traceback": str(e.__traceback__)
            }
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