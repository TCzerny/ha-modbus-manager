"""ModbusManager Entity Manager."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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

    def _create_entity(self, entity_type: str, name: str, config: Dict[str, Any], coordinator=None) -> Optional[Entity]:
        """Erstellt eine Entity basierend auf Typ und Konfiguration."""
        try:
            # Validiere die Basis-Konfiguration
            if not self._validate_entity_config(entity_type, name, config):
                _LOGGER.error(
                    "Entity-Konfiguration ungültig",
                    extra={
                        "device": self._device.name,
                        "name": name,
                        "type": entity_type,
                        "errors": self._validation_errors
                    }
                )
                return None

            # Generiere Entity-IDs
            unique_id = self._device.name_helper.convert(name, NameType.UNIQUE_ID)
            display_name = self._device.name_helper.convert(name, NameType.DISPLAY_NAME)

            # Bestimme die Domain basierend auf dem Entity-Typ und der Konfiguration
            domain = {
                "register": "sensor",
                "switch": "switch",
                "number": "number",
                "select": "select",
                "button": "button",
                "binary_sensor": "binary_sensor"
            }.get(entity_type)

            # Überschreibe Domain wenn in der Konfiguration angegeben
            if "entity_type" in config:
                domain = config["entity_type"]

            if not domain:
                _LOGGER.error(
                    "Keine Domain für Entity-Typ gefunden",
                    extra={
                        "device": self._device.name,
                        "name": name,
                        "type": entity_type
                    }
                )
                return None

            entity_id = self._device.name_helper.convert(name, NameType.ENTITY_ID, domain=domain)

            _LOGGER.debug(
                "Entity IDs generiert",
                extra={
                    "device": self._device.name,
                    "name": name,
                    "unique_id": unique_id,
                    "entity_id": entity_id,
                    "display_name": display_name,
                    "domain": domain
                }
            )

            # Erstelle die Entity basierend auf dem Typ
            entity = None
            try:
                if entity_type == "register" or "calculation" in config:
                    entity = ModbusRegisterEntity(
                        device=self._device,
                        register_name=name,
                        register_config=config,
                        coordinator=coordinator
                    )
                elif entity_type == "switch":
                    entity = SwitchEntity()
                elif entity_type == "number":
                    entity = NumberEntity()
                elif entity_type == "select":
                    entity = SelectEntity()
                elif entity_type == "button":
                    entity = ButtonEntity()
                elif entity_type == "binary_sensor":
                    entity = BinarySensorEntity()
                else:
                    _LOGGER.error(
                        f"Unbekannter Entity-Typ: {entity_type}",
                        extra={
                            "device": self._device.name,
                            "name": name,
                            "config": config
                        }
                    )
                    return None

                # Setze grundlegende Attribute
                if entity:
                    entity._attr_unique_id = unique_id
                    entity._attr_name = display_name
                    entity._attr_device_info = self._device.device_info
                    entity.entity_id = entity_id

                    # Setze optionale Attribute
                    if "device_class" in config:
                        entity._attr_device_class = config["device_class"]
                    if "unit_of_measurement" in config:
                        entity._attr_native_unit_of_measurement = config["unit_of_measurement"]
                    if "state_class" in config:
                        entity._attr_state_class = config["state_class"]

                _LOGGER.debug(
                    "Entity erfolgreich erstellt",
                    extra={
                        "device": self._device.name,
                        "entity_id": entity.entity_id,
                        "type": entity_type,
                        "domain": domain,
                        "attributes": {
                            "unique_id": entity.unique_id,
                            "name": entity.name,
                            "device_class": getattr(entity, "_attr_device_class", None),
                            "unit": getattr(entity, "_attr_native_unit_of_measurement", None),
                            "state_class": getattr(entity, "_attr_state_class", None),
                            "available": getattr(entity, "_attr_available", None),
                            "should_poll": getattr(entity, "_attr_should_poll", None),
                            "has_coordinator": coordinator is not None
                        }
                    }
                )

            except Exception as e:
                _LOGGER.error(
                    "Fehler bei der Entity-Instanziierung",
                    extra={
                        "error": str(e),
                        "device": self._device.name,
                        "type": entity_type,
                        "name": name,
                        "config": config,
                        "traceback": str(e.__traceback__)
                    }
                )
                return None

            return entity

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Entity-Erstellung",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "type": entity_type,
                    "name": name,
                    "config": config,
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

            # Register-spezifische Validierung
            if entity_type == "register":
                # Pflichtfelder für Register
                required_fields = ["type"]
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

            # Entity-Typ Validierung
            valid_entity_types = ["register", "switch", "number", "select", "button", "binary_sensor"]
            if entity_type not in valid_entity_types and "calculation" not in config:
                self._validation_errors.append(f"Ungültiger Entity-Typ für {name}: {entity_type}")
                return False

            # Prüfe auf doppelte Entity-IDs
            unique_id = self._device.name_helper.convert(name, NameType.UNIQUE_ID)
            if unique_id in self._entities:
                self._validation_errors.append(f"Doppelte Entity-ID: {unique_id}")
                return False

            # Optionale Attribute validieren
            if "device_class" in config:
                device_class = config["device_class"]
                if not isinstance(device_class, str):
                    self._validation_errors.append(f"Ungültige Device Class für {name}: {device_class}")
                    return False

            if "unit_of_measurement" in config:
                unit = config["unit_of_measurement"]
                if not isinstance(unit, str):
                    self._validation_errors.append(f"Ungültige Unit für {name}: {unit}")
                    return False

            # State Class Validierung
            if "state_class" in config:
                state_class = config["state_class"]
                valid_state_classes = ["measurement", "total", "total_increasing"]
                if not isinstance(state_class, str):
                    self._validation_errors.append(f"Ungültige State Class für {name}: {state_class}")
                    return False
                if state_class not in valid_state_classes:
                    self._validation_errors.append(f"Ungültige State Class für {name}: {state_class}")
                    return False

            # Validiere Berechnungen
            if "calculation" in config:
                calc_config = config["calculation"]
                if not isinstance(calc_config, dict):
                    self._validation_errors.append(f"Ungültige Berechnungskonfiguration für {name}")
                    return False
                
                calc_type = calc_config.get("type")
                if not calc_type:
                    self._validation_errors.append(f"Kein Berechnungstyp für {name} angegeben")
                    return False
                
                valid_calc_types = ["sum", "mapping", "conditional", "formula"]
                if calc_type not in valid_calc_types:
                    self._validation_errors.append(f"Ungültiger Berechnungstyp für {name}: {calc_type}")
                    return False

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Entity-Validierung",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "type": entity_type,
                    "name": name,
                    "config": config,
                    "traceback": str(e.__traceback__)
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
            
            # Verarbeite Register-Entities
            if "registers" in device_config:
                registers = device_config["registers"]
                if isinstance(registers, dict):
                    for reg_type in ["read", "write"]:
                        if reg_type in registers:
                            for reg_config in registers[reg_type]:
                                if "name" not in reg_config:
                                    continue
                                    
                                coordinator = self._device._update_coordinators.get(reg_config.get("polling", "normal"))
                                entity = self._create_entity("register", reg_config["name"], reg_config, coordinator)
                                if entity:
                                    # Verfolge das Entity-Setup
                                    await self._device._hub.async_track_entity_setup(entity.entity_id)
                                    self._entities[entity.unique_id] = entity
                                    _LOGGER.debug(
                                        f"Register-Entity hinzugefügt: {reg_config['name']}",
                                        extra={
                                            "device": self._device.name,
                                            "entity_id": entity.entity_id,
                                            "register_type": reg_type
                                        }
                                    )

            # Verarbeite berechnete Register
            if "calculated_registers" in device_config:
                calc_registers = device_config["calculated_registers"]
                if isinstance(calc_registers, (dict, list)):
                    # Konvertiere Liste in Dict wenn nötig
                    if isinstance(calc_registers, list):
                        calc_registers = {calc["name"]: calc for calc in calc_registers if "name" in calc}
                    
                    for calc_id, calc_config in calc_registers.items():
                        # Stelle sicher, dass die Konfiguration vollständig ist
                        if not isinstance(calc_config, dict):
                            continue
                            
                        # Füge den Entity-Typ hinzu
                        calc_config["entity_type"] = "sensor"
                        
                        # Erstelle die Entity
                        entity = self._create_entity("register", calc_id, calc_config)
                        if entity:
                            # Verfolge das Entity-Setup
                            await self._device._hub.async_track_entity_setup(entity.entity_id)
                            self._entities[entity.unique_id] = entity
                            _LOGGER.debug(
                                f"Berechnete Entity hinzugefügt: {calc_id}",
                                extra={
                                    "device": self._device.name,
                                    "entity_id": entity.entity_id,
                                    "config": calc_config
                                }
                            )

            # Aktualisiere die Entities im Device
            self._device.update_entities()
            
            # Markiere das Setup als abgeschlossen
            self._setup_complete = True
            
            _LOGGER.info(
                "Entity-Setup abgeschlossen",
                extra={
                    "device": self._device.name,
                    "entity_count": len(self._entities),
                    "entity_types": [type(e).__name__ for e in self._entities.values()]
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