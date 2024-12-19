"""Modbus Manager Sensor Platform."""
import logging
from datetime import timedelta
import struct
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .modbus_hub import ModbusManagerHub
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the sensor platform."""
    hub = hass.data[DOMAIN][entry.entry_id]
    device = hub.device
    
    if not device:
        _LOGGER.error("Kein Gerät verfügbar für Sensor-Setup")
        return

    entity_configs = device.get_entity_configs()
    
    if not entity_configs:
        _LOGGER.warning("Keine Entity-Konfigurationen gefunden")
        return

    # Erstelle einen Coordinator für die Sensoren
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{hub.name} Data",
        update_method=lambda: device.read_registers(),
        update_interval=timedelta(seconds=30),
    )

    # Führe erste Aktualisierung durch
    await coordinator.async_refresh()

    # Erstelle die Sensor-Entities
    entities = []
    for entity_id, config in entity_configs.items():
        entities.append(
            ModbusManagerSensor(
                coordinator=coordinator,
                hub=hub,
                device=device,
                entity_id=entity_id,
                config=config
            )
        )

    async_add_entities(entities)

class ModbusManagerSensor(CoordinatorEntity, SensorEntity):
    """Modbus Manager Sensor Entity."""

    def __init__(self, coordinator, hub, device, entity_id, config):
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self.hub = hub
        self.device = device
        self._entity_id = entity_id
        self._config = config
        self._attr_name = config["name"]
        self._attr_unique_id = config["unique_id"]
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        
        # Register-spezifische Konfiguration
        self._register = config["register"]
        self._register_name = self._register["name"]
        
        # Registriere die Entity beim Device
        self.device.register_entity(self._entity_id, self)
        
        _LOGGER.debug(
            "Sensor initialisiert",
            extra={
                "entity_id": self._entity_id,
                "name": self._attr_name,
                "register": self._register_name
            }
        )

    @property
    def device_info(self):
        """Return device information."""
        return self.device.device_info

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
            
        return self.coordinator.data.get(self._register_name)

    def update_value(self, value):
        """Update the sensor value."""
        if value is not None:
            self._attr_native_value = value
            self.async_write_ha_state()