"""Modbus Manager Base Device Class."""
from __future__ import annotations

import logging
import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator
)

from .const import DOMAIN, NameType
from .logger import ModbusManagerLogger
from .helpers import EntityNameHelper

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerDeviceBase:
    """Base class for Modbus Manager Device."""

    def __init__(
        self,
        hub,
        device_type: str,
        config: dict,
        register_definitions: dict,
    ) -> None:
        """Initialize the device."""
        try:
            self.hub = hub
            self.hass = hub.hass
            self.config = config
            self.name = config[CONF_NAME]
            self.device_type = device_type
            self._device_config = register_definitions
            
            # Initialisiere den Name Helper
            self.name_helper = EntityNameHelper(config)
            
            # Hole die Registries
            self._entity_registry = er.async_get(self.hass)
            self._device_registry = dr.async_get(self.hass)
            
            # Setze die Geräte-Identifikation
            self.unique_id = f"modbus_manager_{self.name.lower()}"
            self.manufacturer = config.get("manufacturer", "Unknown")
            self.model = config.get("model", "Generic Modbus Device")
            
            # Initialisiere die Update-Koordinatoren
            self._update_coordinators = {}
            self._remove_state_change_listeners = []
            
            # Platzhalter für die Komponenten
            self.register_processor = None
            self.entity_manager = None
            self.service_handler = None
            self.calculator = None
            self.test_suite = None
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Initialisierung des Basis-Geräts",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            raise

    @property
    def device_info(self) -> DeviceInfo:
        """Liefert die Geräte-Informationen."""
        try:
            return DeviceInfo(
                identifiers={(DOMAIN, self.unique_id)},
                name=self.name,
                manufacturer=self.manufacturer,
                model=self.model,
                via_device=(DOMAIN, self.hub.unique_id)
            )
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Abrufen der Geräte-Informationen",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            raise

    async def async_setup(self) -> bool:
        """Setup des Geräts."""
        try:
            _LOGGER.info(
                "Starte Setup des Geräts",
                extra={"device": self.name}
            )
            
            # Initialisiere die Register-Listen
            if not await self._setup_register_lists():
                return False
                
            # Führe initiales Update durch
            if not await self._initial_update():
                return False
                
            # Führe verzögertes Setup durch
            if not await self._delayed_setup():
                return False
                
            # Führe Tests durch
            if self.test_suite:
                _LOGGER.info(
                    "Starte Test-Suite",
                    extra={"device": self.name}
                )
                
                # Teste Register-Verarbeitung
                if not await self.test_suite.run_register_tests():
                    _LOGGER.error(
                        "Register-Tests fehlgeschlagen",
                        extra={"device": self.name}
                    )
                    return False
                    
                # Teste Entity-Verwaltung
                if not await self.test_suite.run_entity_tests():
                    _LOGGER.error(
                        "Entity-Tests fehlgeschlagen",
                        extra={"device": self.name}
                    )
                    return False
                    
                # Teste Berechnungen
                if not await self.test_suite.run_calculation_tests():
                    _LOGGER.error(
                        "Berechnungs-Tests fehlgeschlagen",
                        extra={"device": self.name}
                    )
                    return False
                    
                # Teste Service-Aufrufe
                if not await self.test_suite.run_service_tests():
                    _LOGGER.error(
                        "Service-Tests fehlgeschlagen",
                        extra={"device": self.name}
                    )
                    return False
                    
                _LOGGER.info(
                    "Test-Suite erfolgreich abgeschlossen",
                    extra={
                        "device": self.name,
                        "test_results": await self.test_suite.get_test_results()
                    }
                )
                
            _LOGGER.info(
                "Setup des Geräts erfolgreich abgeschlossen",
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

    async def _setup_register_lists(self) -> bool:
        """Initialisiert die Register-Listen."""
        try:
            if not self.register_processor:
                _LOGGER.error(
                    "Register-Processor nicht initialisiert",
                    extra={"device": self.name}
                )
                return False
                
            return await self.register_processor.setup_registers()
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Initialisierung der Register-Listen",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _initial_update(self) -> bool:
        """Führt ein initiales Update der Register durch."""
        try:
            if not self.register_processor:
                _LOGGER.error(
                    "Register-Processor nicht initialisiert",
                    extra={"device": self.name}
                )
                return False
                
            # Update der "schnellen" Register
            register_data = await self.register_processor.update_registers("fast")
            if not register_data:
                _LOGGER.error(
                    "Initiales Update der Register fehlgeschlagen",
                    extra={"device": self.name}
                )
                return False
                
            # Aktualisiere Entity-Zustände
            if self.entity_manager:
                await self.entity_manager.update_entity_states(register_data)
                
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim initialen Update",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _delayed_setup(self) -> bool:
        """Führt verzögerte Setup-Tasks aus."""
        try:
            # Warte kurz, um dem System Zeit für die Initialisierung zu geben
            await asyncio.sleep(2)
            
            if not self.register_processor:
                _LOGGER.error(
                    "Register-Processor nicht initialisiert",
                    extra={"device": self.name}
                )
                return False
                
            # Update der "normalen" und "langsamen" Register
            for interval in ["normal", "slow"]:
                register_data = await self.register_processor.update_registers(interval)
                if not register_data:
                    _LOGGER.error(
                        f"Update der {interval} Register fehlgeschlagen",
                        extra={"device": self.name}
                    )
                    return False
                    
                # Aktualisiere Entity-Zustände
                if self.entity_manager:
                    await self.entity_manager.update_entity_states(register_data)
                    
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim verzögerten Setup",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def async_update(self, interval: str) -> Dict[str, Any]:
        """Aktualisiert die Register für das angegebene Intervall."""
        try:
            if not self.register_processor:
                _LOGGER.error(
                    "Register-Processor nicht initialisiert",
                    extra={"device": self.name}
                )
                return {}
                
            # Update der Register
            register_data = await self.register_processor.update_registers(interval)
            if not register_data:
                _LOGGER.warning(
                    f"Keine Daten beim Update der {interval} Register",
                    extra={"device": self.name}
                )
                return {}
                
            # Aktualisiere berechnete Register
            if self.calculator:
                try:
                    await self.calculator.update_calculations(register_data)
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Aktualisierung der Berechnungen",
                        extra={
                            "error": str(e),
                            "device": self.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
            # Aktualisiere Entity-Zustände
            if self.entity_manager:
                try:
                    await self.entity_manager.update_entity_states(register_data)
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Aktualisierung der Entity-Zustände",
                        extra={
                            "error": str(e),
                            "device": self.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
            return register_data
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Update",
                extra={
                    "error": str(e),
                    "interval": interval,
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return {} 