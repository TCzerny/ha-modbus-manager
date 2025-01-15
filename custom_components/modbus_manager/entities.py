"""Modbus Manager Entity Classes."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.core import callback
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

class ModbusRegisterEntity(CoordinatorEntity, SensorEntity):
    """Entity für Modbus Register."""

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

    def __init__(
        self,
        device,
        register_name: str,
        register_config: Dict[str, Any],
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = device
        self._register_name = register_name
        self._register = register_config
        self.hass = device.hass
        
        # Entity-Eigenschaften aus Register-Definition
        self._attr_name = register_config.get("name", register_name)
        self._attr_unique_id = f"{device.name}_{register_name}"
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
                        "register": self._register_name,
                        "device": self._device.name
                    }
                )
                return None
            
            # Hole den Wert aus den Coordinator-Daten
            if self._device.name in self.coordinator.data:
                device_data = self.coordinator.data[self._device.name]
                value = device_data.get(self._register_name)
                _LOGGER.debug(
                    "Wert aus Device-Daten gelesen",
                    extra={
                        "register": self._register_name,
                        "device": self._device.name,
                        "raw_value": value,
                        "device_data": device_data
                    }
                )
            else:
                value = self.coordinator.data.get(self._register_name)
                _LOGGER.debug(
                    "Wert direkt aus Coordinator-Daten gelesen",
                    extra={
                        "register": self._register_name,
                        "device": self._device.name,
                        "raw_value": value,
                        "coordinator_data": self.coordinator.data
                    }
                )

            if value is None:
                _LOGGER.debug(
                    "Kein Wert für Register gefunden",
                    extra={
                        "register": self._register_name,
                        "device": self._device.name
                    }
                )
                return None

            # Skalierung anwenden wenn konfiguriert
            if "scale" in self._register:
                value = value * self._register["scale"]
                _LOGGER.debug(
                    "Skalierung angewendet",
                    extra={
                        "register": self._register_name,
                        "device": self._device.name,
                        "scale": self._register["scale"],
                        "scaled_value": value
                    }
                )

            # Runde auf die angegebene Präzision
            if "precision" in self._register and isinstance(value, (int, float)):
                value = round(value, self._register["precision"])
                _LOGGER.debug(
                    "Wert gerundet",
                    extra={
                        "register": self._register_name,
                        "device": self._device.name,
                        "precision": self._register["precision"],
                        "rounded_value": value
                    }
                )

            return value

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Abrufen des Register-Werts",
                extra={
                    "error": str(e),
                    "register": self._register_name,
                    "device": self._device.name,
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
                "register": self._register_name,
                "device": self._device.name
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
                    "register": self._register_name,
                    "device": self._device.name
                }
            )

    async def async_write_value(self, value: Any) -> None:
        """Write value to register if writable."""
        try:
            if self._register.get("write", False):
                _LOGGER.debug(
                    "Schreibe Wert in Register",
                    extra={
                        "entity_id": self.entity_id,
                        "register": self._register_name,
                        "value": value
                    }
                )
                
                await self._device.async_write_register(
                    self._register_name,
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
                    "register": self._register_name,
                    "value": value,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            ) 