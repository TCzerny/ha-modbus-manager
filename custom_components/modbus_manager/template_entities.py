"""ModbusManager Template Entity Support."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.template.sensor import TemplateSensor
from homeassistant.components.template.binary_sensor import TemplateBinarySensor
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.template import Template, TemplateError
from homeassistant.helpers.event import async_track_template_result, TrackTemplate

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

# State Class Mapping
STATE_CLASS_MAPPING = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total": SensorStateClass.TOTAL,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}

# Device Class Mapping
DEVICE_CLASS_MAPPING = {
    "battery": SensorDeviceClass.BATTERY,
    "current": SensorDeviceClass.CURRENT,
    "energy": SensorDeviceClass.ENERGY,
    "frequency": SensorDeviceClass.FREQUENCY,
    "power": SensorDeviceClass.POWER,
    "power_factor": SensorDeviceClass.POWER_FACTOR,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "voltage": SensorDeviceClass.VOLTAGE,
}

class ModbusManagerTemplateEntity:
    """Basis-Klasse für Template Entities."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
    ) -> None:
        """Initialize the template entity."""
        self._device = device
        self._config = config
        
        # Entity-Eigenschaften
        self._attr_name = f"{device.name} {name}"
        self._attr_unique_id = config.get("unique_id", f"{device.name}_{name}")
        self._attr_device_info = device.device_info
        
        # Template-Eigenschaften
        self._state_template = None
        self._availability_template = None
        self._attributes_template = None
        
        # Template-Tracking
        self._async_track_state_change = None
        self._async_track_availability_change = None
        self._async_track_attributes_change = None

    async def async_setup(self):
        """Set up the template entity."""
        try:
            # State Template
            if "state" in self._config:
                self._state_template = Template(self._config["state"], self._device.hass)
                self._async_track_state_change = async_track_template_result(
                    self._device.hass,
                    [TrackTemplate(self._state_template, None)],
                    self._async_update_state
                )
                self._async_track_state_change.async_refresh()

            # Availability Template
            if "availability" in self._config:
                self._availability_template = Template(self._config["availability"], self._device.hass)
                self._async_track_availability_change = async_track_template_result(
                    self._device.hass,
                    [TrackTemplate(self._availability_template, None)],
                    self._async_update_availability
                )
                self._async_track_availability_change.async_refresh()

            # Attributes Template
            if "attributes" in self._config:
                self._attributes_template = Template(self._config["attributes"], self._device.hass)
                self._async_track_attributes_change = async_track_template_result(
                    self._device.hass,
                    [TrackTemplate(self._attributes_template, None)],
                    self._async_update_attributes
                )
                self._async_track_attributes_change.async_refresh()

            return True

        except TemplateError as ex:
            _LOGGER.error(
                "Fehler beim Template-Setup",
                extra={
                    "error": str(ex),
                    "entity": self._attr_name
                }
            )
            return False

    async def async_teardown(self):
        """Remove template tracking."""
        if self._async_track_state_change is not None:
            self._async_track_state_change.async_remove()
        if self._async_track_availability_change is not None:
            self._async_track_availability_change.async_remove()
        if self._async_track_attributes_change is not None:
            self._async_track_attributes_change.async_remove()

    @callback
    def _async_update_state(self, event, updates):
        """Handle state changes."""
        result = updates.pop().result

        if isinstance(result, TemplateError):
            _LOGGER.error(
                "Fehler beim Template-Update",
                extra={
                    "error": str(result),
                    "entity": self._attr_name
                }
            )
            return

        self._handle_state_update(result)
        self.async_write_ha_state()

    def _handle_state_update(self, result):
        """Handle the state update."""
        raise NotImplementedError()

class ModbusManagerTemplateSensor(ModbusManagerTemplateEntity, SensorEntity):
    """Template Sensor Entity."""

    def __init__(self, device, name: str, config: Dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(device, name, config)
        
        # Sensor-spezifische Eigenschaften
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        
        # Device Class
        if device_class := config.get("device_class"):
            if device_class in DEVICE_CLASS_MAPPING:
                self._attr_device_class = DEVICE_CLASS_MAPPING[device_class]
            else:
                _LOGGER.warning(
                    "Ungültige device_class",
                    extra={
                        "device_class": device_class,
                        "name": name,
                        "valid_classes": list(DEVICE_CLASS_MAPPING.keys())
                    }
                )
        
        # State Class
        if state_class := config.get("state_class"):
            if state_class in STATE_CLASS_MAPPING:
                self._attr_state_class = STATE_CLASS_MAPPING[state_class]
            else:
                _LOGGER.warning(
                    "Ungültige state_class",
                    extra={
                        "state_class": state_class,
                        "name": name,
                        "valid_classes": list(STATE_CLASS_MAPPING.keys())
                    }
                )

    def _handle_state_update(self, result):
        """Handle the state update."""
        self._attr_native_value = result

class ModbusManagerTemplateBinarySensor(ModbusManagerTemplateEntity, BinarySensorEntity):
    """Template Binary Sensor Entity."""

    def __init__(self, device, name: str, config: Dict[str, Any]) -> None:
        """Initialize the binary sensor."""
        super().__init__(device, name, config)
        
        # Binary Sensor spezifische Eigenschaften
        if device_class := config.get("device_class"):
            try:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning(
                    "Ungültige device_class für Binary Sensor",
                    extra={
                        "device_class": device_class,
                        "name": name,
                        "valid_classes": [cls.value for cls in BinarySensorDeviceClass]
                    }
                )

    def _handle_state_update(self, result):
        """Handle the state update."""
        self._attr_is_on = bool(result) 