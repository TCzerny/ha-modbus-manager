"""Basis-Implementierung für Modbus Manager Geräte."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .device_interfaces import IModbusManagerDevice, IModbusManagerServiceProvider, IModbusManagerEntityProvider
from .helpers import EntityNameHelper
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerDeviceBase(IModbusManagerDevice):
    """Basis-Implementierung für ein Modbus Manager Gerät."""

    def __init__(
        self,
        hub,
        device_type: str,
        device_config: Dict[str, Any],
        register_definitions: Dict[str, Any]
    ) -> None:
        """Initialisiere das Gerät."""
        try:
            self._hub = hub
            self._hass = hub.hass
            self._device_type = device_type
            self._device_config = device_config
            self._register_definitions = register_definitions
            self._name = device_config.get("name", "unknown")
            
            # Initialisiere den EntityNameHelper mit dem Gerätenamen
            self._name_helper = EntityNameHelper(self._name)
            
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._name)},
                name=self._name,
                manufacturer="Modbus Manager",
                model=self._device_type
            )
            
            _LOGGER.debug(
                "ModbusManagerDeviceBase initialisiert",
                extra={
                    "device_type": device_type,
                    "name": self._name
                }
            )
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Initialisierung des ModbusManagerDeviceBase",
                extra={
                    "error": str(e),
                    "device_type": device_type,
                    "name": device_config.get("name", "unknown"),
                    "traceback": e.__traceback__
                }
            )
            raise

    @property
    def hass(self) -> HomeAssistant:
        """Gibt die Home Assistant Instanz zurück."""
        return self._hass

    @property
    def name(self) -> str:
        """Gibt den Namen des Geräts zurück."""
        return self._name

    @property
    def device_info(self) -> Dict[str, Any]:
        """Gibt die Geräteinformationen zurück."""
        return self._attr_device_info

    async def get_register_value(self, register_name: str) -> Optional[Any]:
        """Gibt den Wert eines Registers zurück."""
        try:
            if not hasattr(self, "_register_processor"):
                _LOGGER.error(
                    "Register Processor nicht initialisiert",
                    extra={"device": self.name}
                )
                return None
            return await self._register_processor.get_value(register_name)
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Lesen des Registers",
                extra={
                    "error": str(e),
                    "register": register_name,
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def write_register(self, register_name: str, value: Any) -> bool:
        """Schreibt einen Wert in ein Register."""
        try:
            if not hasattr(self, "_register_processor"):
                _LOGGER.error(
                    "Register Processor nicht initialisiert",
                    extra={"device": self.name}
                )
                return False
            return await self._register_processor.write_value(register_name, value)
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Schreiben des Registers",
                extra={
                    "error": str(e),
                    "register": register_name,
                    "value": value,
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def async_setup(self) -> bool:
        """Richtet das Gerät ein."""
        try:
            # Lazy imports to avoid circular dependencies
            from .device_registers import ModbusManagerRegisterProcessor
            from .device_entities import ModbusManagerEntityManager
            from .device_calculations import ModbusManagerCalculator
            from .device_services import ModbusManagerServiceHandler
            from .device_tests import ModbusManagerTestSuite

            # Initialize components
            self._register_processor = ModbusManagerRegisterProcessor(self)
            self._entity_manager = ModbusManagerEntityManager(self)
            self._calculator = ModbusManagerCalculator(self)
            self._service_handler = ModbusManagerServiceHandler(self)
            self._test_suite = ModbusManagerTestSuite(
                self.hass,
                self,
                self._register_processor,
                self._entity_manager,
                self._service_handler,
                self._calculator
            )

            _LOGGER.debug(
                "ModbusManagerDeviceBase Setup abgeschlossen",
                extra={"device": self.name}
            )

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup des Geräts",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def update_entities(self) -> None:
        """Aktualisiert die Entities des Geräts."""
        try:
            if not hasattr(self, "_entity_manager"):
                _LOGGER.error(
                    "Entity Manager nicht initialisiert",
                    extra={"device": self.name}
                )
                return
            await self._entity_manager.update_entities()
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Update der Entities",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )

    async def get_entities(self, entity_types: List[Any]) -> List[Any]:
        """Gibt die Entities des Geräts zurück."""
        try:
            if not hasattr(self, "_entity_manager"):
                _LOGGER.error(
                    "Entity Manager nicht initialisiert",
                    extra={"device": self.name}
                )
                return []
            return [entity for entity in self._entity_manager.entities.values() 
                   if any(isinstance(entity, entity_type) for entity_type in entity_types)]
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Abrufen der Entities",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return [] 