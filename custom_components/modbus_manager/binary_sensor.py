"""ModbusManager Binary Sensor Platform."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity_registry import EntityRegistry, async_get

from .const import DOMAIN, NameType
from .device_base import ModbusManagerDeviceBase
from .entities import ModbusRegisterEntity
from .logger import ModbusManagerLogger
from .device_common import setup_platform_entities

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Richte die ModbusManager Binary Sensor Entities ein."""
    return await setup_platform_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        entity_types=[ModbusRegisterEntity, BinarySensorEntity],
        platform_name="Binary Sensor"
    )

class ModbusManagerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """ModbusManager Binary Sensor Entity."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        
        self._device = device
        self._config = config
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
        self.entity_id = device.name_helper.convert(name, NameType.ENTITY_ID, domain="binary_sensor")
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
        # Binary Sensor spezifische Eigenschaften
        if "device_class" in config:
            self._attr_device_class = config["device_class"]
            
        _LOGGER.debug(
            "Binary Sensor Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
                "entity_id": self.entity_id,
                "device_class": self._attr_device_class,
                "device": device.name
            }
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data:
            return None
            
        device_data = self.coordinator.data.get(self._device.name, {})
        return bool(device_data.get(self._name, False))

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None
