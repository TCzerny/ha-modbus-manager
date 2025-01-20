"""Helper classes and methods for Modbus Manager."""

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NameType
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class EntityNameHelper:
    """Helper class for entity naming conventions."""

    def __init__(self, config: Union[ConfigEntry, Dict[str, Any], str]) -> None:
        """Initialize the helper with the config.

        Args:
            config: The configuration source, can be:
                   - ConfigEntry: A Home Assistant config entry
                   - Dict: A dictionary containing configuration
                   - str: A direct device name
        """
        try:
            # Extrahiere die Konfigurationsdaten
            if isinstance(config, str):
                self.device_name = config
            elif hasattr(config, 'data'):
                config_data = config.data
                if CONF_NAME not in config_data:
                    raise ValueError("Pflichtfeld CONF_NAME fehlt in der ConfigEntry")
                self.device_name = config_data[CONF_NAME]
            elif isinstance(config, dict):
                if CONF_NAME not in config:
                    raise ValueError("Pflichtfeld CONF_NAME fehlt im Konfigurations-Dict")
                self.device_name = config[CONF_NAME]
            else:
                raise ValueError(f"Ungültiger Konfigurationstyp: {type(config)}")
            
            self._sanitized_device_name = self._sanitize_name(self.device_name)
            
            _LOGGER.debug(
                "EntityNameHelper initialisiert",
                extra={
                    "device_name": self.device_name,
                    "sanitized_name": self._sanitized_device_name
                }
            )
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Initialisierung des EntityNameHelper",
                extra={
                    "error": str(e),
                    "config_type": type(config),
                    "traceback": e.__traceback__
                }
            )
            raise

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize a name for use in entity IDs."""
        # Entferne alle nicht-alphanumerischen Zeichen außer Leerzeichen und Bindestriche
        name = re.sub(r"[^\w\s-]", "", name.lower())
        # Ersetze Leerzeichen und mehrfache Bindestriche durch einzelne Unterstriche
        name = re.sub(r"[-\s]+", "_", name)
        # Entferne Zahlen am Ende
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
        """Konvertiert einen Namen in das gewünschte Format.

        Args:
            name: Der zu konvertierende Name (z.B. "battery_level")
            name_type: Der gewünschte Ausgabetyp (ENTITY_ID, UNIQUE_ID, etc.)
            domain: Optional - der Entity-Domain (nur für ENTITY_ID benötigt)

        Returns:
            Der konvertierte Name im gewünschten Format

        Raises:
            ValueError: Wenn ein ungültiger NameType übergeben wird oder
                      wenn domain für ENTITY_ID fehlt
        """
        # Entferne zuerst mögliche Device-Präfixe
        clean_name = self._remove_device_prefix(name)
        
        _LOGGER.debug(
            "Name wird konvertiert",
            extra={
                "original_name": name,
                "clean_name": clean_name,
                "name_type": str(name_type),
                "domain": domain,
                "device_name": self.device_name
            }
        )

        result = None
        if name_type == NameType.ENTITY_ID:
            if not domain:
                raise ValueError("Domain wird für ENTITY_ID benötigt")
            result = f"{domain}.{self._sanitized_device_name}_{self._sanitize_name(clean_name)}"

        elif name_type == NameType.UNIQUE_ID:
            result = f"{self._sanitized_device_name}_{self._sanitize_name(clean_name)}"

        elif name_type == NameType.DISPLAY_NAME:
            result = f"{self._title_case(self.device_name)} {self._title_case(clean_name)}"

        elif name_type == NameType.BASE_NAME:
            result = f"{self._sanitized_device_name}_{self._sanitize_name(clean_name)}"

        elif name_type == NameType.SERVICE_NAME:
            result = f"{self._sanitized_device_name}_{self._sanitize_name(clean_name)}"

        else:
            raise ValueError(f"Unbekannter NameType: {name_type}")

        _LOGGER.debug(
            "Name wurde konvertiert",
            extra={
                "original_name": name,
                "result": result,
                "name_type": str(name_type)
            }
        )

        return result
