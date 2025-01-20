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

    def __init__(self, config_entry):
        """Initialize the helper with the config entry.

        Args:
            config_entry: The config entry or dictionary containing the user-provided device name
        """
        # Extrahiere die Konfigurationsdaten
        if hasattr(config_entry, 'data'):
            config_data = config_entry.data
        elif isinstance(config_entry, dict):
            config_data = config_entry
        else:
            raise ValueError(f"Ungültige Konfiguration: {type(config_entry)}")
        
        # Prüfe ob der Name vorhanden ist
        if CONF_NAME not in config_data:
            raise ValueError("Pflichtfeld CONF_NAME fehlt in der Konfiguration")
            
        self.device_name = config_data[CONF_NAME]
        self._sanitized_device_name = self._sanitize_name(self.device_name)
        
        _LOGGER.debug(
            "EntityNameHelper initialisiert",
            extra={
                "device_name": self.device_name,
                "sanitized_name": self._sanitized_device_name
            }
        )

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

async def setup_platform_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entity_types: List[Type[Entity]],
    platform_name: str
) -> bool:
    """Richtet die Entities für eine Platform ein."""
    try:
        # Hole den Hub
        hub: ModbusManagerHub = hass.data[DOMAIN][entry.entry_id]
        if not hub:
            _LOGGER.error(
                "Hub nicht gefunden",
                extra={
                    "entry_id": entry.entry_id,
                    "platform": platform_name
                }
            )
            return False

        # Sammle alle passenden Entities von allen Geräten
        entities = []
        for device in hub.devices.values():
            if not device.entity_manager:
                continue
                
            # Hole alle passenden Entities
            device_entities = [
                entity for entity in device.entity_manager.entities.values()
                if any(isinstance(entity, entity_type) for entity_type in entity_types)
            ]
            
            if device_entities:
                _LOGGER.debug(
                    f"{platform_name} Entities gefunden",
                    extra={
                        "device": device.name,
                        "count": len(device_entities),
                        "entities": [e.entity_id for e in device_entities]
                    }
                )
                entities.extend(device_entities)
            else:
                _LOGGER.debug(
                    f"Keine {platform_name} Entities gefunden",
                    extra={
                        "device": device.name
                    }
                )

        # Füge die Entities hinzu
        if entities:
            async_add_entities(entities)
            _LOGGER.info(
                f"{platform_name} Entities hinzugefügt",
                extra={
                    "count": len(entities),
                    "entry_id": entry.entry_id
                }
            )
            return True
            
        return False

    except Exception as e:
        _LOGGER.error(
            f"Fehler beim Setup der {platform_name} Entities",
            extra={
                "error": str(e),
                "entry_id": entry.entry_id,
                "traceback": str(e.__traceback__)
            }
        )
        return False
