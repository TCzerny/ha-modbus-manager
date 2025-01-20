"""Modbus Manager Device Interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, NameType
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class IModbusManagerDevice(ABC):
    """Interface für Modbus Manager Geräte."""
    
    @property
    @abstractmethod
    def hass(self) -> HomeAssistant:
        """Home Assistant Instanz."""
        pass
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Name des Geräts."""
        pass
        
    @property
    @abstractmethod
    def device_info(self) -> DeviceInfo:
        """Geräteinformationen."""
        pass
        
    @abstractmethod
    def get_register_value(self, register_name: str) -> Any:
        """Hole den Wert eines Registers."""
        pass
        
    @abstractmethod
    async def write_register(self, register_name: str, value: Any) -> bool:
        """Schreibe einen Wert in ein Register."""
        pass

class IModbusManagerServiceProvider(ABC):
    """Interface für Service-Provider."""
    
    @abstractmethod
    async def setup_services(self, service_definitions: Dict[str, Any]) -> None:
        """Richtet Services ein."""
        pass
        
    @abstractmethod
    def get_service_config(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Hole die Konfiguration eines Services."""
        pass

class IModbusManagerEntityProvider(ABC):
    """Interface für Entity-Provider."""
    
    @abstractmethod
    def update_entities(self) -> None:
        """Aktualisiere die Entities."""
        pass
        
    @abstractmethod
    async def update_entity_states(self, data: Dict[str, Any]) -> None:
        """Aktualisiere die Entity-Zustände."""
        pass 