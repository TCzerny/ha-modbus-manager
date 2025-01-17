"""Modbus Manager Entity Management."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.number import NumberEntity
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
    ) -> None:
        """Initialisiere den Entity Manager."""
        self._device = device
        self._entities = {}
        self._setup_complete = False
        self.name_helper = device.name_helper

    async def setup_entities(self, device_config: Dict[str, Any]) -> bool:
        """Richtet die Entities basierend auf der Konfiguration ein."""
        try:
            # Verarbeite Register-Entities
            if "registers" in device_config:
                registers = device_config["registers"]
                
                # Verarbeite Read-Register
                if "read" in registers:
                    for register in registers["read"]:
                        entity = ModbusRegisterEntity(
                            self._device,
                            register["name"],
                            register,
                            self._device._update_coordinators.get(register.get("polling", "normal"))
                        )
                        self._entities[entity.unique_id] = entity
                        
                # Verarbeite Write-Register
                if "write" in registers:
                    for register in registers["write"]:
                        if register.get("min") is not None and register.get("max") is not None:
                            # Number Entity für Write-Register mit min/max
                            entity = ModbusManagerInputNumber(
                                self._device,
                                register["name"],
                                register
                            )
                        elif "options" in register:
                            # Select Entity für Write-Register mit Optionen
                            entity = ModbusManagerInputSelect(
                                self._device,
                                register["name"],
                                register
                            )
                        else:
                            # Standard Register Entity
                            entity = ModbusRegisterEntity(
                                self._device,
                                register["name"],
                                register,
                                self._device._update_coordinators.get(register.get("polling", "normal"))
                            )
                        self._entities[entity.unique_id] = entity

            # Verarbeite berechnete Register
            if "calculated_registers" in device_config:
                for calc_def in device_config["calculated_registers"]:
                    if "name" not in calc_def:
                        continue
                        
                    entity = ModbusRegisterEntity(
                        self._device,
                        calc_def["name"],
                        calc_def,
                        self._device._update_coordinators.get(calc_def.get("polling", "normal"))
                    )
                    self._entities[entity.unique_id] = entity

            # Aktualisiere die entities Property des Geräts
            self._device.entities = self._entities

            _LOGGER.info(
                "Entity-Setup abgeschlossen",
                extra={
                    "device": self._device.name,
                    "total_entities": len(self._entities)
                }
            )
            
            self._setup_complete = True
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

    async def update_entity_states(self, register_data: Dict[str, Any]) -> None:
        """Aktualisiert die Entity-Zustände mit den Register-Daten."""
        try:
            if not self._setup_complete:
                _LOGGER.warning(
                    "Entity-Update übersprungen - Setup nicht abgeschlossen",
                    extra={"device": self._device.name}
                )
                return

            for entity in self._entities.values():
                try:
                    if hasattr(entity, "async_update_from_register"):
                        await entity.async_update_from_register(register_data)
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Update der Entity",
                        extra={
                            "error": str(e),
                            "entity": entity.name,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Update der Entity-Zustände",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    @property
    def entities(self) -> Dict[str, Entity]:
        """Gibt alle verwalteten Entities zurück."""
        return self._entities.copy() 