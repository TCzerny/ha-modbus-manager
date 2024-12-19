"""Modbus Manager entities."""
from __future__ import annotations

import logging
import asyncio
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
        device: "ModbusManagerDevice",
        register_name: str,
        register_config: dict,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialisiert die ModbusRegisterEntity."""
        super().__init__(coordinator)
        
        self.device = device
        self.name_helper = EntityNameHelper(device.config_entry)
        
        # Speichere die Original-Konfiguration
        self.register_config = register_config
        self.original_register_name = register_config.get("name")
        
        if not self.original_register_name:
            raise ValueError(f"Register hat keinen Namen in der Konfiguration: {register_config}")
        
        # Konvertiere den Register-Namen mit Präfix für verschiedene Verwendungszwecke
        self.register_name = self.name_helper.convert(self.original_register_name, NameType.BASE_NAME)
        self.display_name = self.name_helper.convert(self.original_register_name, NameType.DISPLAY_NAME)
        self.unique_id = self.name_helper.convert(self.original_register_name, NameType.UNIQUE_ID)
        self.entity_id = self.name_helper.convert(self.original_register_name, NameType.ENTITY_ID, domain="sensor")
        
        # Setze die Entity-Attribute
        self._attr_name = self.display_name
        self._attr_unique_id = self.unique_id
        
        # Device Info
        self._attr_device_info = device.device_info
        
        # Setze device_class und unit_of_measurement
        self._setup_device_class_and_unit()
        
        # Setze state_class wenn vorhanden
        if "state_class" in register_config:
            self._attr_state_class = register_config["state_class"]
            
        _LOGGER.debug(
            "ModbusRegisterEntity initialisiert",
            extra={
                "device": self.device.name,
                "original_name": self.original_register_name,
                "register_name": self.register_name,
                "display_name": self.display_name,
                "unique_id": self.unique_id,
                "entity_id": self.entity_id
            }
        )

    def _setup_device_class_and_unit(self) -> None:
        """Setzt device_class und unit_of_measurement basierend auf der Konfiguration."""
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
        
        # Setze device_class wenn vorhanden
        if "device_class" in self.register_config:
            self._attr_device_class = self.register_config["device_class"]
            
            # Setze Standard-Einheit basierend auf device_class wenn keine Einheit definiert ist
            if ("unit_of_measurement" not in self.register_config and 
                self._attr_device_class in DEVICE_CLASS_UNITS):
                self._attr_native_unit_of_measurement = DEVICE_CLASS_UNITS[self._attr_device_class]
        
        # Überschreibe mit spezifischer Einheit wenn definiert
        if "unit_of_measurement" in self.register_config:
            self._attr_native_unit_of_measurement = self.register_config["unit_of_measurement"]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> Any:
        """Return the native value of the entity."""
        return self._attr_native_value

    async def async_added_to_hass(self) -> None:
        """Wenn die Entity zu Home Assistant hinzugefügt wird."""
        await super().async_added_to_hass()
        
        # Registriere einen Callback für Datenaktualisierungen
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        
        _LOGGER.debug(
            "Entity zu Home Assistant hinzugefügt",
            extra={
                "entity_id": self.entity_id,
                "register_name": self.register_name
            }
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            if not self.coordinator.data:
                _LOGGER.debug(
                    "Keine Daten vom Coordinator",
                    extra={
                        "entity_id": self.entity_id,
                        "register_name": self.register_name
                    }
                )
                return
                
            # Hole die Daten für dieses Device
            if self.device.name in self.coordinator.data:
                device_data = self.coordinator.data[self.device.name]
                self._update_value(device_data)
            else:
                _LOGGER.debug(
                    "Device nicht in Coordinator-Daten gefunden",
                    extra={
                        "entity_id": self.entity_id,
                        "device": self.device.name,
                        "register_name": self.register_name,
                        "verfügbare_devices": list(self.coordinator.data.keys())
                    }
                )
            
            # Aktualisiere den State nur wenn die Entity initialisiert ist
            if hasattr(self, "hass") and self.hass:
                self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Verarbeiten des Koordinator-Updates",
                extra={
                    "error": str(e),
                    "entity_id": self.entity_id,
                    "register_name": self.register_name,
                    "device": self.device.name,
                    "traceback": str(e.__traceback__)
                }
            )

    async def async_write_value(self, value: Any) -> None:
        """Write value to register if writable."""
        try:
            if not self.register_config.get("write", False):
                _LOGGER.debug(
                    "Register ist nicht schreibbar",
                    extra={
                        "entity_id": self.entity_id,
                        "register_name": self.register_name
                    }
                )
                return
                
            _LOGGER.debug(
                "Schreibe Wert in Register",
                extra={
                    "entity_id": self.entity_id,
                    "register_name": self.register_name,
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
                    "register_name": self.register_name,
                    "value": value,
                    "device": self.device.name,
                    "traceback": str(e.__traceback__)
                }
            ) 

    def _update_value(self, device_data: Dict[str, Any]) -> None:
        """Aktualisiert den Wert der Entity aus den Device-Daten."""
        try:
            _LOGGER.debug(
                "Entity sucht Register",
                extra={
                    "entity": self.display_name,
                    "original_name": self.original_register_name,
                    "register_name": self.register_name,
                    "device": self.device.name,
                    "register_config": self.register_config,
                    "verfügbare_register": list(device_data.keys()) if device_data else "keine"
                }
            )
            
            if self.register_name in device_data:
                self._attr_native_value = device_data[self.register_name]
                _LOGGER.debug(
                    "Wert erfolgreich aktualisiert",
                    extra={
                        "entity": self.display_name,
                        "original_name": self.original_register_name,
                        "register_name": self.register_name,
                        "value": self._attr_native_value
                    }
                )
            else:
                _LOGGER.debug(
                    "Register nicht in Device-Daten gefunden",
                    extra={
                        "entity": self.display_name,
                        "original_name": self.original_register_name,
                        "register_name": self.register_name,
                        "verfügbare_register": list(device_data.keys())
                    }
                )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Aktualisieren des Werts",
                extra={
                    "error": str(e),
                    "entity": self.display_name,
                    "original_name": self.original_register_name,
                    "register_name": self.register_name,
                    "device": self.device.name,
                    "traceback": str(e.__traceback__)
                }
            ) 