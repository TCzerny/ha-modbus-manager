<<<<<<< HEAD
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
=======
"""Modbus Manager Entity Management."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator
)

from .const import DOMAIN, NameType
from .input_entities import (
    ModbusManagerInputNumber,
    ModbusManagerInputSelect
)
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class ModbusRegisterEntity(CoordinatorEntity, SensorEntity):
    """Modbus Register Entity."""

    def __init__(
        self,
        device,
        register_name: str,
        register_config: dict,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialisiert die ModbusRegisterEntity."""
        super().__init__(coordinator)
        
        self._device = device
        self._register = register_config
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(register_name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(register_name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(register_name, NameType.UNIQUE_ID)
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
        # Setze device_class und unit_of_measurement wenn vorhanden
        if "device_class" in register_config:
            self._attr_device_class = register_config["device_class"]
        if "unit_of_measurement" in register_config:
            self._attr_native_unit_of_measurement = register_config["unit_of_measurement"]
            
        # Setze state_class wenn vorhanden
        if "state_class" in register_config:
            self._attr_state_class = register_config["state_class"]
            
        _LOGGER.debug(
            "ModbusRegisterEntity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
                "device": device.name
            }
        )

class ModbusManagerEntityManager:
    """Klasse zur Verwaltung von Modbus Manager Entities."""

    def __init__(
        self,
        device,
        async_add_entities: Optional[AddEntitiesCallback] = None
    ) -> None:
        """Initialisiere den Entity Manager."""
        self._device = device
        self._async_add_entities = async_add_entities
        self._entities: Dict[str, Entity] = {}
        self._setup_complete = False
        self.name_helper = device.name_helper

    async def setup_entities(self, async_add_entities: AddEntitiesCallback) -> bool:
        """Setup der Entities für das Gerät."""
        try:
            self._async_add_entities = async_add_entities
            
            # Erstelle Register-Entities
            register_entities = await self._create_register_entities()
            if register_entities:
                self._async_add_entities(register_entities, True)
                _LOGGER.debug(
                    "Register-Entities erstellt",
                    extra={
                        "count": len(register_entities),
                        "device": self._device.name
                    }
                )
                
            # Erstelle Helper-Entities
            helper_entities = await self._create_helper_entities()
            if helper_entities:
                self._async_add_entities(helper_entities, True)
                _LOGGER.debug(
                    "Helper-Entities erstellt",
                    extra={
                        "count": len(helper_entities),
                        "device": self._device.name
                    }
                )
                
            # Validiere die Entity-Registrierung
            if not await self.validate_entity_registration():
                _LOGGER.error(
                    "Validierung der Entity-Registrierung fehlgeschlagen",
                    extra={"device": self._device.name}
                )
                return False
                
            # Teste die Entity-Zustandsaktualisierung
            if not await self.test_entity_state_updates():
                _LOGGER.error(
                    "Test der Entity-Zustandsaktualisierung fehlgeschlagen",
                    extra={"device": self._device.name}
                )
                return False
                
            self._setup_complete = True
            
            _LOGGER.info(
                "Entity Setup erfolgreich abgeschlossen",
                extra={
                    "register_count": len(register_entities) if register_entities else 0,
                    "helper_count": len(helper_entities) if helper_entities else 0,
                    "total_entities": len(self._entities),
                    "device": self._device.name
                }
            )
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup der Entities",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _create_register_entities(self) -> List[Entity]:
        """Erstellt Entities für alle Register."""
        try:
            entities = []
            registers = self._device._device_config.get("registers", {})
            
            # Verarbeite read und write Register
            for register_type in ["read", "write"]:
                for register in registers.get(register_type, []):
                    try:
                        entity = await self._create_register_entity(register)
                        if entity:
                            entities.append(entity)
                            self._entities[entity.unique_id] = entity
                    except Exception as e:
                        _LOGGER.error(
                            "Fehler beim Erstellen einer Register-Entity",
                            extra={
                                "error": str(e),
                                "register": register,
                                "device": self._device.name,
                                "traceback": e.__traceback__
                            }
                        )
                        
            return entities
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen der Register-Entities",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return []

    async def _create_helper_entities(self) -> List[Entity]:
        """Erstellt Helper-Entities (Input Number, Input Select)."""
        try:
            entities = []
            
            # Erstelle Input Number Entities
            input_numbers = self._device._device_config.get("input_number", {})
            for input_id, config in input_numbers.items():
                try:
                    entity = await self._create_input_number_entity(input_id, config)
                    if entity:
                        entities.append(entity)
                        self._entities[entity.unique_id] = entity
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Erstellen einer Input Number Entity",
                        extra={
                            "error": str(e),
                            "input_id": input_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
            
            # Erstelle Input Select Entities
            input_selects = self._device._device_config.get("input_select", {})
            for input_id, config in input_selects.items():
                try:
                    entity = await self._create_input_select_entity(input_id, config)
                    if entity:
                        entities.append(entity)
                        self._entities[entity.unique_id] = entity
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Erstellen einer Input Select Entity",
                        extra={
                            "error": str(e),
                            "input_id": input_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
            return entities
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen der Helper-Entities",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return []

    async def update_entity_states(self, register_data: Dict[str, Any]) -> None:
        """Aktualisiert die Zustände aller Entities."""
        if not self._setup_complete:
            return
            
        try:
            for entity in self._entities.values():
                try:
                    await self._update_entity_state(entity, register_data)
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Aktualisierung einer Entity",
                        extra={
                            "error": str(e),
                            "entity": entity.unique_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Aktualisierung der Entity-Zustände",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def _update_entity_state(self, entity: Entity, register_data: Dict[str, Any]) -> None:
        """Aktualisiert den Zustand einer einzelnen Entity."""
        try:
            if not hasattr(entity, "_register"):
                return
                
            register_name = entity._register.get("name")
            if not register_name:
                return
                
            # Konvertiere den Register-Namen
            register_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
            
            # Hole den aktuellen Wert
            value = register_data.get(register_name)
            if value is not None:
                entity._attr_native_value = value
                entity.async_write_ha_state()
                
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Aktualisierung des Entity-Zustands",
                extra={
                    "error": str(e),
                    "entity": entity.unique_id if entity else None,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def async_teardown(self) -> None:
        """Cleanup bei Entfernung des Geräts."""
        try:
            # Führe Teardown für alle Entities durch
            for entity in self._entities.values():
                try:
                    if hasattr(entity, "async_teardown"):
                        await entity.async_teardown()
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Teardown einer Entity",
                        extra={
                            "error": str(e),
                            "entity": entity.unique_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
            self._entities.clear()
            self._setup_complete = False
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Teardown des Entity Managers",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            ) 

    async def _create_register_entity(self, register_config: Dict[str, Any]) -> Optional[Entity]:
        """Erstellt eine Register-Entity basierend auf der Konfiguration."""
        try:
            if not register_config.get("name"):
                _LOGGER.error(
                    "Register hat keinen Namen in der Konfiguration",
                    extra={
                        "register": register_config,
                        "device": self._device.name
                    }
                )
                return None

            entity = ModbusRegisterEntity(
                device=self._device,
                register_name=register_config["name"],
                register_config=register_config,
                coordinator=self._device.coordinator
            )

            _LOGGER.debug(
                "Register-Entity erstellt",
                extra={
                    "name": entity.name,
                    "unique_id": entity.unique_id,
                    "entity_id": entity.entity_id,
                    "device": self._device.name
                }
            )

            return entity

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen der Register-Entity",
                extra={
                    "error": str(e),
                    "register": register_config,
                    "device": self._device.name,
                    "traceback": e.__traceback__
>>>>>>> task/name_helpers_2025-01-16_1
                }
            )
            return None

<<<<<<< HEAD
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

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Entity-Validierung",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "type": entity_type,
                    "name": name,
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
                    # Verarbeite read/write Register
                    for reg_type, reg_list in registers.items():
                        if not isinstance(reg_list, list):
                            continue
                            
                        for reg_config in reg_list:
                            if "name" not in reg_config:
                                continue
                                
                            coordinator = self._device._update_coordinators.get(reg_config.get("polling", "normal"))
                            entity = self._create_entity("register", reg_config["name"], reg_config, coordinator)
                            if entity:
                                # Registriere die Entity in Home Assistant
                                await self._device.hass.async_add_entity(entity)
                                
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
                        
                        # Verwende den normalen Coordinator für berechnete Register
                        coordinator = self._device._update_coordinators.get("normal")
                        
                        # Erstelle die Entity
                        entity = self._create_entity("register", calc_id, calc_config, coordinator)
                        if entity:
                            # Registriere die Entity in Home Assistant
                            await self._device.hass.async_add_entity(entity)
                            
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
=======
    async def _create_input_number_entity(self, input_id: str, config: Dict[str, Any]) -> Optional[Entity]:
        """Erstellt eine Input Number Entity basierend auf der Konfiguration."""
        try:
            if not config.get("register", {}).get("name"):
                _LOGGER.error(
                    "Input Number hat kein Register in der Konfiguration",
                    extra={
                        "input_id": input_id,
                        "config": config,
                        "device": self._device.name
                    }
                )
                return None

            entity = ModbusManagerInputNumber(
                device=self._device,
                name=input_id,
                config=config,
                register_config=config["register"]
            )

            _LOGGER.debug(
                "Input Number Entity erstellt",
                extra={
                    "name": entity.name,
                    "unique_id": entity.unique_id,
                    "entity_id": entity.entity_id,
                    "device": self._device.name
                }
            )

            return entity

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen der Input Number Entity",
                extra={
                    "error": str(e),
                    "input_id": input_id,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def _create_input_select_entity(self, input_id: str, config: Dict[str, Any]) -> Optional[Entity]:
        """Erstellt eine Input Select Entity basierend auf der Konfiguration."""
        try:
            if not config.get("register", {}).get("name"):
                _LOGGER.error(
                    "Input Select hat kein Register in der Konfiguration",
                    extra={
                        "input_id": input_id,
                        "config": config,
                        "device": self._device.name
                    }
                )
                return None

            entity = ModbusManagerInputSelect(
                device=self._device,
                name=input_id,
                config=config,
                register_config=config["register"]
            )

            _LOGGER.debug(
                "Input Select Entity erstellt",
                extra={
                    "name": entity.name,
                    "unique_id": entity.unique_id,
                    "entity_id": entity.entity_id,
                    "device": self._device.name
                }
            )

            return entity

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen der Input Select Entity",
                extra={
                    "error": str(e),
                    "input_id": input_id,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return None 

    async def validate_entity_registration(self) -> bool:
        """Validiert die Registrierung aller Entities."""
        try:
            entity_registry = er.async_get(self._device.hass)
            device_registry = dr.async_get(self._device.hass)
            
            # Hole das Device aus dem Registry
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, self._device.unique_id)}
            )
            
            if not device:
                _LOGGER.error(
                    "Device nicht in Registry gefunden",
                    extra={
                        "device": self._device.name,
                        "unique_id": self._device.unique_id
                    }
                )
                return False
                
            # Prüfe alle Entities
            for entity in self._entities.values():
                try:
                    # Hole die Entity aus der Registry
                    registry_entry = entity_registry.async_get(entity.entity_id)
                    
                    if not registry_entry:
                        _LOGGER.error(
                            "Entity nicht in Registry gefunden",
                            extra={
                                "entity_id": entity.entity_id,
                                "unique_id": entity.unique_id,
                                "device": self._device.name
                            }
                        )
                        return False
                        
                    # Prüfe ob die Entity dem richtigen Device zugeordnet ist
                    if registry_entry.device_id != device.id:
                        _LOGGER.error(
                            "Entity ist falschem Device zugeordnet",
                            extra={
                                "entity_id": entity.entity_id,
                                "entity_device_id": registry_entry.device_id,
                                "expected_device_id": device.id,
                                "device": self._device.name
                            }
                        )
                        return False
                        
                    # Prüfe ob die Unique ID korrekt ist
                    if registry_entry.unique_id != entity.unique_id:
                        _LOGGER.error(
                            "Entity hat falsche Unique ID in Registry",
                            extra={
                                "entity_id": entity.entity_id,
                                "registry_unique_id": registry_entry.unique_id,
                                "entity_unique_id": entity.unique_id,
                                "device": self._device.name
                            }
                        )
                        return False
                        
                    _LOGGER.debug(
                        "Entity-Registrierung validiert",
                        extra={
                            "entity_id": entity.entity_id,
                            "unique_id": entity.unique_id,
                            "device": self._device.name
                        }
                    )
                    
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Validierung einer Entity",
                        extra={
                            "error": str(e),
                            "entity_id": entity.entity_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    return False
                    
            _LOGGER.info(
                "Alle Entity-Registrierungen erfolgreich validiert",
                extra={
                    "device": self._device.name,
                    "entity_count": len(self._entities)
                }
            )
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Validierung der Entity-Registrierungen",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False 

    async def test_entity_state_updates(self) -> bool:
        """Testet die Zustandsaktualisierung aller Entities."""
        try:
            # Erstelle Test-Daten für Register
            test_data = {}
            
            # Teste Register-Entities
            registers = self._device._device_config.get("registers", {})
            for register_type in ["read", "write"]:
                for register in registers.get(register_type, []):
                    try:
                        register_name = register.get("name")
                        if not register_name:
                            continue
                            
                        # Konvertiere den Register-Namen
                        register_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                        
                        # Erstelle Test-Wert basierend auf Register-Typ
                        if register.get("type") == "uint16":
                            test_data[register_name] = 1000
                        elif register.get("type") == "int16":
                            test_data[register_name] = -500
                        elif register.get("type") == "float32":
                            test_data[register_name] = 123.45
                        else:
                            test_data[register_name] = 1
                            
                    except Exception as e:
                        _LOGGER.error(
                            "Fehler beim Erstellen der Test-Daten für Register",
                            extra={
                                "error": str(e),
                                "register": register,
                                "device": self._device.name,
                                "traceback": e.__traceback__
                            }
                        )
                        return False
                        
            # Aktualisiere Entity-Zustände mit Test-Daten
            await self.update_entity_states(test_data)
            
            # Validiere die aktualisierten Zustände
            for entity in self._entities.values():
                try:
                    if not hasattr(entity, "_register"):
                        continue
                        
                    register_name = entity._register.get("name")
                    if not register_name:
                        continue
                        
                    # Konvertiere den Register-Namen
                    register_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                    
                    # Prüfe ob der Wert korrekt gesetzt wurde
                    if register_name in test_data:
                        expected_value = test_data[register_name]
                        if entity._attr_native_value != expected_value:
                            _LOGGER.error(
                                "Entity-Wert stimmt nicht mit Test-Daten überein",
                                extra={
                                    "entity_id": entity.entity_id,
                                    "register": register_name,
                                    "expected": expected_value,
                                    "actual": entity._attr_native_value,
                                    "device": self._device.name
                                }
                            )
                            return False
                            
                        _LOGGER.debug(
                            "Entity-Zustand erfolgreich aktualisiert",
                            extra={
                                "entity_id": entity.entity_id,
                                "register": register_name,
                                "value": entity._attr_native_value,
                                "device": self._device.name
                            }
                        )
                        
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Validierung des Entity-Zustands",
                        extra={
                            "error": str(e),
                            "entity_id": entity.entity_id if entity else None,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    return False
                    
            _LOGGER.info(
                "Alle Entity-Zustandsaktualisierungen erfolgreich getestet",
                extra={
                    "device": self._device.name,
                    "entity_count": len(self._entities),
                    "register_count": len(test_data)
                }
            )
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Testen der Entity-Zustandsaktualisierungen",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False 
>>>>>>> task/name_helpers_2025-01-16_1
