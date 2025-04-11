"""ModbusManager Entity Manager."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union, Type

from homeassistant.const import (
    STATE_UNAVAILABLE
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass
)
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.button import ButtonEntity

from custom_components.modbus_manager.const import (
    DOMAIN,
    NameType
)
from custom_components.modbus_manager.logger import ModbusManagerLogger
from custom_components.modbus_manager.entities import ModbusRegisterEntity

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerEntityManager:
    """ModbusManager Entity Manager."""

    def __init__(self, device) -> None:
        """Initialisiere den Entity Manager."""
        self._device = device
        self._entities = {}
        self._validation_errors = []
        self._setup_complete = False

    @property
    def entities(self) -> Dict[str, Entity]:
        """Gibt alle verwalteten Entities zurück."""
        return self._entities

    def _create_entity(
        self,
        entity_type: str,
        name: str,
        config: Dict[str, Any],
        coordinator: DataUpdateCoordinator = None
    ) -> Optional[Entity]:
        """Erstellt eine Entity basierend auf Typ und Konfiguration."""
        try:
            # Validiere die Entity-Konfiguration
            if not self._validate_entity_config(entity_type, name, config):
                return None

            # Hole den passenden Coordinator basierend auf dem Polling-Intervall
            if not coordinator:
                polling = config.get("polling", "normal")
                coordinator = self._device._update_coordinators.get(polling)
                
            if not coordinator:
                _LOGGER.error(
                    "Kein Coordinator verfügbar",
                    extra={
                        "device": self._device.name,
                        "entity_type": entity_type,
                        "name": name
                    }
                )
                return None

            # Erstelle die Entity basierend auf dem Typ
            entity = None
            
            if entity_type == "register":
                entity = ModbusRegisterEntity(
                    device=self._device,
                    name=name,
                    register_config=config,
                    coordinator=coordinator
                )
            elif entity_type == "button":
                entity = ModbusManagerButton(
                    device=self._device,
                    name=name,
                    config=config,
                    coordinator=coordinator
                )
            elif entity_type == "switch":
                entity = ModbusManagerSwitch(
                    device=self._device,
                    name=name,
                    config=config,
                    coordinator=coordinator
                )
            elif entity_type == "number":
                entity = ModbusManagerInputNumber(
                    device=self._device,
                    name=name,
                    config=config,
                    coordinator=coordinator
                )
            elif entity_type == "select":
                entity = ModbusManagerInputSelect(
                    device=self._device,
                    name=name,
                    config=config,
                    coordinator=coordinator
                )
            else:
                _LOGGER.error(
                    "Unbekannter Entity-Typ",
                    extra={
                        "device": self._device.name,
                        "type": entity_type,
                        "name": name
                    }
                )
                return None

            if entity:
                _LOGGER.debug(
                    "Entity erstellt",
                    extra={
                        "device": self._device.name,
                        "type": entity_type,
                        "name": name,
                        "coordinator": coordinator.name if coordinator else None
                    }
                )
                return entity

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Entity-Erstellung",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "type": entity_type,
                    "name": name,
                    "traceback": str(e.__traceback__)
                }
            )
            return None

    def _validate_entity_config(self, entity_type: str, name: str, config: Dict[str, Any]) -> bool:
        """Validiert die Entity-Konfiguration."""
        try:
            # Setze Validierungsfehler zurück
            self._validation_errors = []
            
            # Prüfe Basis-Anforderungen
            if not name or not isinstance(name, str):
                self._validation_errors.append(f"Ungültiger Name: {name}")
                return False

            if not config or not isinstance(config, dict):
                self._validation_errors.append(f"Ungültige Konfiguration für {name}")
                return False

            # Normalisiere den Entity-Typ
            entity_type = entity_type.replace(" ", "_")

            # Entity-Typ Validierung
            valid_entity_types = [
                "register",
                "switch",
                "number",
                "select",
                "button",
                "binary_sensor",
                "sensor"
            ]
            
            if entity_type not in valid_entity_types and "calculation" not in config:
                self._validation_errors.append(
                    f"Ungültiger Entity-Typ für {name}: {entity_type}",
                    extra={
                        "device": self._device.name,
                        "valid_types": valid_entity_types
                    }
                )
                return False

            # Register-spezifische Validierung
            if entity_type == "register":
                # Pflichtfelder für Register
                required_fields = ["address"]
                for field in required_fields:
                    if field not in config:
                        self._validation_errors.append(f"Pflichtfeld '{field}' fehlt für Register {name}")
                        return False
                
                # Register-Typ Validierung
                register_type = config.get("register_type")
                if register_type and register_type not in ["input", "holding"]:
                    self._validation_errors.append(f"Ungültiger Register-Typ für {name}: {register_type}")
                    return False
                
                # Register-Adresse Validierung
                address = config.get("address")
                if address is not None:
                    if not isinstance(address, int):
                        self._validation_errors.append(f"Ungültige Register-Adresse für {name}: {address}")
                        return False
                    if address < 0:
                        self._validation_errors.append(f"Negative Register-Adresse für {name}: {address}")
                        return False

            # Prüfe auf doppelte Entity-IDs
            unique_id = self._device.name_helper.convert(name, NameType.UNIQUE_ID)
            if unique_id in self._entities:
                self._validation_errors.append(f"Doppelte Entity-ID: {unique_id}")
                return False

            return True

        except Exception as e:
            self._validation_errors.append(f"Validierungsfehler: {str(e)}")
            _LOGGER.error(
                "Fehler bei der Entity-Validierung",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "name": name,
                    "type": entity_type
                }
            )
            return False

    async def setup_entities(self, device_config: Dict[str, Any]) -> bool:
        """Richtet die Entities basierend auf der Konfiguration ein."""
        try:
            _LOGGER.info(
                "Starte Entity-Setup",
                extra={"device": self._device.name}
            )
            
            # Setze Validierungsfehler zurück
            self._validation_errors = []

            # Hole Register-Definitionen
            registers = device_config.get("registers", {})
            
            # Erstelle Register-Entities und konvertiere sie in spezifische Entity-Typen
            for name, config in registers.items():
                # Bestimme den Entity-Typ aus der Konfiguration
                entity_type = config.get("entity_type", "register")
                # Normalisiere den Entity-Typ (ersetze Leerzeichen durch Unterstrich)
                entity_type = entity_type.replace(" ", "_")
                
                # Erstelle die Entity
                entity = self._create_entity(entity_type, name, config)
                if entity:
                    unique_id = self._device.name_helper.convert(name, NameType.UNIQUE_ID)
                    self._entities[unique_id] = entity
                else:
                    _LOGGER.warning(
                        "Entity konnte nicht erstellt werden",
                        extra={
                            "device": self._device.name,
                            "name": name,
                            "type": entity_type
                        }
                    )

            # Aktualisiere bestehende Entities
            await self.update_entities()

            # Setup abgeschlossen
            self._setup_complete = True

            _LOGGER.info(
                "Entity-Setup abgeschlossen",
                extra={
                    "device": self._device.name,
                    "entity_count": len(self._entities),
                    "entity_types": list(set(type(entity).__name__ for entity in self._entities.values()))
                }
            )

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Entity-Setup",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": str(e.__traceback__)
                }
            )
            return False

    async def update_entity_states(self, register_data: Dict[str, Any] = None) -> None:
        """Aktualisiert die Zustände aller Entities."""
        try:
            if not self._entities:
                _LOGGER.debug(
                    "Keine Entities zum Aktualisieren vorhanden",
                    extra={
                        "device": self._device.name
                    }
                )
                return

            for entity_id, entity in self._entities.items():
                try:
                    # Prüfe ob Entity initialisiert ist
                    if not hasattr(entity, "hass") or not entity.hass:
                        _LOGGER.debug(
                            "Entity noch nicht initialisiert",
                            extra={
                                "device": self._device.name,
                                "entity_id": entity_id
                            }
                        )
                        continue

                    # Prüfe ob Entity update_value und async_write_ha_state Methoden hat
                    if not hasattr(entity, "async_write_ha_state"):
                        _LOGGER.debug(
                            "Entity hat keine async_write_ha_state Methode",
                            extra={
                                "device": self._device.name,
                                "entity_id": entity_id,
                                "entity_type": type(entity).__name__
                            }
                        )
                        continue

                    # Update den Entity-Wert wenn register_data vorhanden
                    if register_data and hasattr(entity, "_update_value"):
                        await entity._update_value(register_data)
                        
                    # Aktualisiere den Entity-State
                    await entity.async_write_ha_state()
                    
                    # Markiere das Entity-Setup als abgeschlossen
                    if hasattr(entity, "entity_id"):
                        await self._device._hub.async_entity_setup_complete(entity.entity_id)
                    
                    _LOGGER.debug(
                        "Entity-Status erfolgreich aktualisiert",
                        extra={
                            "device": self._device.name,
                            "entity_id": entity_id,
                            "state": getattr(entity, "_attr_native_value", None)
                        }
                    )

                except Exception as entity_error:
                    _LOGGER.error(
                        "Fehler bei der Aktualisierung einer einzelnen Entity",
                        extra={
                            "error": str(entity_error),
                            "device": self._device.name,
                            "entity_id": entity_id,
                            "traceback": entity_error
                        }
                    )
                    continue

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Entity-Status-Aktualisierung",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e
                }
            )

    def get_entities(self, entity_type: Union[str, List[Type[Entity]]]) -> List[Any]:
        """Gibt alle Entities eines bestimmten Typs zurück.
        
        Args:
            entity_type: Entweder ein String ("sensor", "switch", etc.) oder
                        eine Liste von Entity-Klassen
        """
        try:
            # Mapping von Entity-Typen zu Entity-Klassen
            type_mapping = {
                "sensor": [SensorEntity],
                "binary_sensor": [BinarySensorEntity],
                "switch": [SwitchEntity],
                "number": [NumberEntity],
                "select": [SelectEntity],
                "button": [ButtonEntity],
            }

            # Bestimme die Entity-Klassen basierend auf dem Input
            if isinstance(entity_type, str):
                entity_classes = type_mapping.get(entity_type, [])
                if not entity_classes:
                    _LOGGER.warning(
                        "Unbekannter Entity-Typ angefordert",
                        extra={
                            "device": self._device.name,
                            "entity_type": entity_type
                        }
                    )
                    return []
            else:
                entity_classes = entity_type

            # Filtere die Entities nach Typ
            entities = []
            for entity in self._entities.values():
                # Prüfe ob die Entity eine der gewünschten Klassen ist
                if any(isinstance(entity, entity_class) for entity_class in entity_classes):
                    # Prüfe ob die Entity auch ein ModbusRegisterEntity ist
                    if isinstance(entity, ModbusRegisterEntity):
                        entities.append(entity)

            _LOGGER.debug(
                "Entities gefiltert nach Typ",
                extra={
                    "device": self._device.name,
                    "entity_type": str(entity_type),
                    "count": len(entities)
                }
            )

            return entities

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Abrufen der Entities nach Typ",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "entity_type": str(entity_type),
                    "traceback": e.__traceback__
                }
            )
            return []

    async def update_entities(self) -> None:
        """Aktualisiert alle verwalteten Entities."""
        try:
            if not self._entities:
                _LOGGER.debug(
                    "Keine Entities zum Aktualisieren vorhanden",
                    extra={"device": self._device.name}
                )
                return

            for entity in self._entities.values():
                if hasattr(entity, "async_update") and callable(entity.async_update):
                    await entity.async_update()

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Aktualisieren der Entities",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": str(e.__traceback__)
                }
            ) 