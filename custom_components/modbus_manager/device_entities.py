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

from .const import (
    DOMAIN,
    NameType
)
from .logger import ModbusManagerLogger

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
                "button": "button"
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
            if entity_type == "register" or "calculation" in config:
                from .entities import ModbusRegisterEntity
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

            if not entity:
                return None

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
                if "type" not in config:
                    self._validation_errors.append(f"Kein Typ definiert für Register {name}")
                    return False
                
                # Register-Typ Validierung
                register_type = config.get("register_type")
                if register_type and register_type not in ["input", "holding"]:
                    self._validation_errors.append(f"Ungültiger Register-Typ für {name}: {register_type}")
                    return False
                
                # Register-Adresse Validierung
                address = config.get("address")
                if address is not None and not isinstance(address, int):
                    self._validation_errors.append(f"Ungültige Register-Adresse für {name}: {address}")
                    return False

            # Prüfe auf doppelte Entity-IDs
            unique_id = self._device.name_helper.convert(name, NameType.UNIQUE_ID)
            if unique_id in self._entities:
                self._validation_errors.append(f"Doppelte Entity-ID: {unique_id}")
                return False

            # Optionale Attribute validieren
            device_class = config.get("device_class")
            if device_class and not isinstance(device_class, str):
                self._validation_errors.append(f"Ungültige Device Class für {name}: {device_class}")
                return False

            unit = config.get("unit_of_measurement")
            if unit and not isinstance(unit, str):
                self._validation_errors.append(f"Ungültige Unit für {name}: {unit}")
                return False

            # State Class Validierung
            state_class = config.get("state_class")
            if state_class:
                if not isinstance(state_class, str):
                    self._validation_errors.append(f"Ungültige State Class für {name}: {state_class}")
                    return False
                if state_class not in ["measurement", "total", "total_increasing"]:
                    self._validation_errors.append(f"Ungültige State Class für {name}: {state_class}")
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
                    "config": config
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
            for entity in self._entities.values():
                if hasattr(entity, "async_write_ha_state"):
                    if register_data and hasattr(entity, "_update_value"):
                        await entity._update_value(register_data)
                    await entity.async_write_ha_state()
                    _LOGGER.debug(
                        "Entity-Status aktualisiert",
                        extra={
                            "device": self._device.name,
                            "entity_id": entity.entity_id,
                            "state": getattr(entity, "_attr_native_value", None)
                        }
                    )
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Entity-Status-Aktualisierung",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e
                }
            ) 