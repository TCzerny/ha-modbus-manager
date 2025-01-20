"""Modbus Manager Device Base."""
from __future__ import annotations

from typing import Dict, Any, Optional, List, Set
import asyncio
import re
from datetime import datetime, timedelta

from homeassistant.const import CONF_NAME, CONF_SLAVE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, NameType, DEFAULT_SLAVE
from .logger import ModbusManagerLogger
from .device_common import DeviceCommon
from .device_interfaces import IModbusManagerDevice, IModbusManagerServiceProvider, IModbusManagerEntityProvider

_LOGGER = ModbusManagerLogger(__name__)

class EntityNameHelper:
    """Helper class for entity naming conventions."""

    def __init__(self, config_entry):
        """Initialize the helper with the config entry."""
        if hasattr(config_entry, 'data'):
            config_data = config_entry.data
        elif isinstance(config_entry, dict):
            config_data = config_entry
        else:
            raise ValueError(f"Ungültige Konfiguration: {type(config_entry)}")
        
        if CONF_NAME not in config_data:
            raise ValueError("Pflichtfeld CONF_NAME fehlt in der Konfiguration")
            
        self.device_name = config_data[CONF_NAME]
        self._sanitized_device_name = self._sanitize_name(self.device_name)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize a name for use in entity IDs."""
        name = re.sub(r"[^\w\s-]", "", name.lower())
        name = re.sub(r"[-\s]+", "_", name)
        name = re.sub(r"_\d+$", "", name)
        return name

    @staticmethod
    def _title_case(name: str) -> str:
        """Convert snake_case or any string to Title Case."""
        return " ".join(word.capitalize() for word in name.replace("_", " ").split())

    def _remove_device_prefix(self, name: str) -> str:
        """Entfernt den Gerätenamen als Präfix, falls vorhanden."""
        device_prefix = self._sanitized_device_name.lower() + "_"
        if name.lower().startswith(device_prefix):
            return name[len(device_prefix):]
        return name

    def convert(
        self, name: str, name_type: NameType, domain: Optional[str] = None
    ) -> str:
        """Konvertiert einen Namen in das gewünschte Format."""
        clean_name = self._remove_device_prefix(name)
        
        if name_type == NameType.ENTITY_ID:
            if not domain:
                raise ValueError("Domain wird für ENTITY_ID benötigt")
            return f"{domain}.{self._sanitized_device_name}_{self._sanitize_name(clean_name)}"
        elif name_type == NameType.UNIQUE_ID:
            return f"{self._sanitized_device_name}_{self._sanitize_name(clean_name)}"
        elif name_type == NameType.DISPLAY_NAME:
            return f"{self._title_case(self.device_name)} {self._title_case(clean_name)}"
        elif name_type == NameType.BASE_NAME:
            return f"{self._sanitized_device_name}_{self._sanitize_name(clean_name)}"
        elif name_type == NameType.SERVICE_NAME:
            return f"{self._sanitized_device_name}_{self._sanitize_name(clean_name)}"
        else:
            raise ValueError(f"Unbekannter NameType: {name_type}")

class ModbusManagerDeviceBase(DeviceCommon, IModbusManagerDevice):
    """Base class for Modbus Manager devices."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the device."""
        super().__init__(hass, config_entry)
        self.register_processor = None  # Wird später initialisiert
        self.entity_manager = None      # Wird später initialisiert
        self.service_handler = None     # Wird später initialisiert
        self.calculator = None          # Wird später initialisiert
        self.test_suite = None          # Wird später initialisiert

    async def async_setup(self) -> bool:
        """Set up the device."""
        try:
            # Lazy imports to avoid circular dependencies
            from .device_registers import ModbusManagerRegisterProcessor
            from .device_entities import ModbusManagerEntityManager
            from .device_services import ModbusManagerServiceHandler
            from .device_calculations import ModbusManagerCalculator
            from .device_tests import ModbusManagerTestSuite
            
            self.register_processor = ModbusManagerRegisterProcessor(self)
            self.entity_manager = ModbusManagerEntityManager(self)
            self.service_handler = ModbusManagerServiceHandler(self.hass, self)
            self.calculator = ModbusManagerCalculator(self)
            self.test_suite = ModbusManagerTestSuite(self)
            
            return True
        except Exception as e:
            _LOGGER.error("Error setting up device: %s", str(e))
            return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return self._attr_device_info

    def get_register_value(self, register_name: str) -> Any:
        """Hole den Wert eines Registers."""
        if self.register_processor:
            return self.register_processor.get_register_value(register_name)
        return None

    async def write_register(self, register_name: str, value: Any) -> bool:
        """Schreibe einen Wert in ein Register."""
        if self.register_processor:
            return await self.register_processor.write_register(register_name, value)
        return False

    def update_entities(self) -> None:
        """Aktualisiere die Entities aus dem Entity Manager."""
        try:
            if hasattr(self, 'entity_manager') and self.entity_manager:
                self.entities = self.entity_manager.entities
                _LOGGER.debug(
                    "Entities aus Entity Manager aktualisiert",
                    extra={
                        "device": self.name,
                        "entity_count": len(self.entities),
                        "entity_types": [type(e).__name__ for e in self.entities.values()]
                    }
                )
            else:
                _LOGGER.warning(
                    "Entity Manager nicht verfügbar",
                    extra={"device": self.name}
                )
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Aktualisieren der Entities",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": str(e.__traceback__)
                }
            )

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
            success = await self.register_processor.update_registers(interval)
            if not success:
                _LOGGER.warning(
                    f"Update der {interval} Register fehlgeschlagen",
                    extra={"device": self.name}
                )
                return {}
                
            # Hole die aktuellen Register-Daten
            register_data = self.register_processor.get_register_data()
            
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
                            "traceback": str(e.__traceback__)
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
                            "traceback": str(e.__traceback__)
                        }
                    )
            
            # Gib die Daten für den Coordinator zurück
            return {self.name: register_data}
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Update",
                extra={
                    "error": str(e),
                    "interval": interval,
                    "device": self.name,
                    "traceback": str(e.__traceback__)
                }
            )
            return {} 