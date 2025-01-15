"""Helper classes and methods for Modbus Manager."""
import re
from enum import Enum
from typing import Optional
from homeassistant.const import CONF_NAME

class NameType(Enum):
    """Definiert die verschiedenen Typen von Namen/IDs."""
    ENTITY_ID = "entity_id"          # Für Entity IDs (z.B. sensor.sungrow_inverter_battery_level)
    UNIQUE_ID = "unique_id"          # Für eindeutige IDs (z.B. sungrow_inverter_battery_level)
    DISPLAY_NAME = "display_name"    # Für UI-Anzeigenamen (z.B. Sungrow Battery Level)
    BASE_NAME = "base_name"          # Für interne Referenzen (z.B. sungrow_battery_level)

class EntityNameHelper:
    """Helper class for entity naming conventions."""

    def __init__(self, config_entry):
        """Initialize the helper with the config entry.
        
        Args:
            config_entry: The config entry containing the user-provided device name
        """
        self.device_name = config_entry.data[CONF_NAME]
        self._sanitized_device_name = self._sanitize_name(self.device_name)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize a name for use in entity IDs."""
        # Entferne alle nicht-alphanumerischen Zeichen außer Leerzeichen und Bindestriche
        name = re.sub(r'[^\w\s-]', '', name.lower())
        # Ersetze Leerzeichen und mehrfache Bindestriche durch einzelne Unterstriche
        name = re.sub(r'[-\s]+', '_', name)
        # Entferne Zahlen am Ende
        name = re.sub(r'_\d+$', '', name)
        return name

    @staticmethod
    def _title_case(name: str) -> str:
        """Convert snake_case or any string to Title Case."""
        return ' '.join(word.capitalize() for word in name.replace('_', ' ').split())

    def _remove_device_prefix(self, name: str) -> str:
        """Entfernt den Gerätenamen als Präfix, falls vorhanden."""
        device_prefix = self._sanitized_device_name.lower() + "_"
        if name.lower().startswith(device_prefix):
            return name[len(device_prefix):]
        return name

    def convert(self, name: str, name_type: NameType, domain: Optional[str] = None) -> str:
        """
        Konvertiert einen Namen in das gewünschte Format.
        
        Args:
            name: Der zu konvertierende Name (z.B. "battery_level")
            name_type: Der gewünschte Ausgabetyp (ENTITY_ID, UNIQUE_ID, etc.)
            domain: Optional - der Entity-Domain (nur für ENTITY_ID benötigt)
            
        Returns:
            Der konvertierte Name im gewünschten Format
        """
        # Entferne zuerst mögliche Device-Präfixe
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
            
        raise ValueError(f"Unbekannter NameType: {name_type}") 