"""Interfaces für Modbus Manager Komponenten."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant

class IModbusManagerDevice(ABC):
    """Interface für ein Modbus Manager Gerät."""

    @property
    @abstractmethod
    def hass(self) -> HomeAssistant:
        """Gibt die Home Assistant Instanz zurück."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Gibt den Namen des Geräts zurück."""
        pass

    @property
    @abstractmethod
    def device_info(self) -> Dict[str, Any]:
        """Gibt die Geräteinformationen zurück."""
        pass

    @abstractmethod
    async def get_register_value(self, register_name: str) -> Optional[Any]:
        """Gibt den Wert eines Registers zurück."""
        pass

    @abstractmethod
    async def write_register(self, register_name: str, value: Any) -> bool:
        """Schreibt einen Wert in ein Register."""
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