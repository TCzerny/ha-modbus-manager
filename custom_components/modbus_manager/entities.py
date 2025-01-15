"""Modbus Manager entities."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.core import callback

from .helpers import EntityNameHelper, NameType

_LOGGER = logging.getLogger(__name__)

class ModbusRegisterEntity(CoordinatorEntity, SensorEntity):
    """Modbus Register Entity."""

    def __init__(
        self,
        device: ModbusManagerDevice,
        register_name: str,
        register_config: dict,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device = device
        
        # Generiere alle Entity-Namen und IDs mit dem Helper
        name_helper = EntityNameHelper(device.config_entry)
        
        # Der register_name kommt bereits mit Präfix aus dem device_definition
        self.register_name = register_name
        
        # Speichere die Konfiguration
        self.register_config = register_config
        
        # Setze die Entity-Attribute
        # Entferne den Präfix für die Anzeige, da der Helper ihn wieder hinzufügt
        display_name = name_helper._remove_device_prefix(register_name)
        self._attr_name = name_helper.convert(display_name, NameType.DISPLAY_NAME)
        self._attr_unique_id = name_helper.convert(display_name, NameType.UNIQUE_ID)
        self.entity_id = name_helper.convert(display_name, NameType.ENTITY_ID, domain="sensor")
        
        # Device Info
        self._attr_device_info = device.device_info
        
        # Setze device_class wenn vorhanden
        if "device_class" in register_config:
            self._attr_device_class = register_config["device_class"]
            
            # Setze Standard-Einheit basierend auf device_class wenn keine Einheit definiert ist
            if "unit" not in register_config and self._attr_device_class in self.DEVICE_CLASS_UNITS:
                self._attr_native_unit_of_measurement = self.DEVICE_CLASS_UNITS[self._attr_device_class]
            
        # Überschreibe mit spezifischer Einheit wenn definiert
        if "unit" in register_config:
            self._attr_native_unit_of_measurement = register_config["unit"]
            
        if "state_class" in register_config:
            self._attr_state_class = register_config["state_class"]

    # Standard-Einheiten für verschiedene Gerätetypen
    DEVICE_CLASS_UNITS = {
        "energy": "kWh",
        "power": "W",
        "current": "A",
        "voltage": "V",
        "temperature": "°C",
        "battery": "%",
        "frequency": "Hz"
    }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> Any:
        """Return the register value."""
        try:
            if not self.coordinator.data:
                _LOGGER.debug(
                    "Keine Daten vom Koordinator verfügbar",
                    extra={
                        "register": self.register_name,
                        "device": self.device.name
                    }
                )
                return None
            
            # Hole den Wert aus den Coordinator-Daten
            if self.device.name in self.coordinator.data:
                device_data = self.coordinator.data[self.device.name]
                value = device_data.get(self.register_name)
                _LOGGER.debug(
                    "Wert aus Device-Daten gelesen",
                    extra={
                        "register": self.register_name,
                        "device": self.device.name,
                        "raw_value": value,
                        "device_data": device_data
                    }
                )
            else:
                value = self.coordinator.data.get(self.register_name)
                _LOGGER.debug(
                    "Wert direkt aus Coordinator-Daten gelesen",
                    extra={
                        "register": self.register_name,
                        "device": self.device.name,
                        "raw_value": value,
                        "coordinator_data": self.coordinator.data
                    }
                )

            if value is None:
                _LOGGER.debug(
                    "Kein Wert für Register gefunden",
                    extra={
                        "register": self.register_name,
                        "device": self.device.name
                    }
                )
                return None

            # Skalierung anwenden wenn konfiguriert
            if "scale" in self.register_config:
                value = value * self.register_config["scale"]
                _LOGGER.debug(
                    "Skalierung angewendet",
                    extra={
                        "register": self.register_name,
                        "device": self.device.name,
                        "scale": self.register_config["scale"],
                        "scaled_value": value
                    }
                )

            # Runde auf die angegebene Präzision
            if "precision" in self.register_config and isinstance(value, (int, float)):
                value = round(value, self.register_config["precision"])
                _LOGGER.debug(
                    "Wert gerundet",
                    extra={
                        "register": self.register_name,
                        "device": self.device.name,
                        "precision": self.register_config["precision"],
                        "rounded_value": value
                    }
                )

            return value

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Abrufen des Register-Werts",
                extra={
                    "error": str(e),
                    "register": self.register_name,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def async_added_to_hass(self) -> None:
        """Wenn die Entity zu Home Assistant hinzugefügt wird."""
        await super().async_added_to_hass()
        
        _LOGGER.debug(
            "Entity zu Home Assistant hinzugefügt",
            extra={
                "entity_id": self.entity_id,
                "register": self.register_name,
                "device": self.device.name
            }
        )
        
        # Registriere einen Callback für Datenaktualisierungen
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            if not self.coordinator.data:
                return
                
            # Hole den aktuellen Wert
            value = self.native_value
            
            # Aktualisiere den State nur wenn die Entity initialisiert ist
            if hasattr(self, "hass") and self.hass:
                self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Verarbeiten des Koordinator-Updates",
                extra={
                    "error": str(e),
                    "entity_id": getattr(self, "entity_id", None),
                    "register": self.register_name,
                    "device": self.device.name
                }
            )

    async def async_write_value(self, value: Any) -> None:
        """Write value to register if writable."""
        try:
            if self.register_config.get("write", False):
                _LOGGER.debug(
                    "Schreibe Wert in Register",
                    extra={
                        "entity_id": self.entity_id,
                        "register": self.register_name,
                        "value": value
                    }
                )
                
                await self.device.async_write_register(
                    self.register_name,
                    value
                )
                
                # Warte kurz und aktualisiere dann den Wert
                await asyncio.sleep(0.1)
                await self.coordinator.async_request_refresh()
                
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Schreiben des Werts",
                extra={
                    "error": str(e),
                    "entity_id": self.entity_id,
                    "register": self.register_name,
                    "value": value,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            ) 