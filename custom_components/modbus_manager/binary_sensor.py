"""Modbus Manager Binary Sensor Platform."""
from __future__ import annotations
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.template import Template
from homeassistant.exceptions import TemplateError

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager binary sensors from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    binary_sensors = entry.data.get("binary_sensors", [])
    hub_name = f"modbus_manager_{prefix}"

    entities = []

    # Process binary sensors from binary_sensors section
    _LOGGER.debug("Processing %d binary sensors", len(binary_sensors))
    for binary_sensor in binary_sensors:
        _LOGGER.debug("Processing binary sensor: %s (type: %s)", binary_sensor.get("name"), binary_sensor.get("type"))
        if binary_sensor.get("type") == "binary_sensor":
            # Unique_ID Format: {prefix}_{template_sensor_name}
            sensor_name = binary_sensor.get("name", "unknown")
            # Use unique_id from template if available, otherwise use cleaned name
            template_unique_id = binary_sensor.get("unique_id")
            if template_unique_id:
                # Check if template_unique_id already has prefix
                if template_unique_id.startswith(f"{prefix}_"):
                    unique_id = template_unique_id
                else:
                    unique_id = f"{prefix}_{template_unique_id}"
            else:
                # Fallback: Bereinige den Namen für den unique_id
                clean_name = sensor_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                unique_id = f"{prefix}_{clean_name}"
            
            entities.append(TemplateBinarySensor(
                hass=hass,
                name=sensor_name,
                unique_id=unique_id,
                template_data=binary_sensor,
                device_info={
                    "identifiers": {(DOMAIN, f"{prefix}_{template_name}")},
                    "name": f"Modbus Manager {prefix}",
                    "manufacturer": "Modbus Manager",
                    "model": template_name,
                },
                prefix=prefix,
            ))

    # Process binary sensors from registers section (legacy support)
    for reg in registers:
        # Binary-Sensor-Entities aus Registern mit data_type: "boolean" oder control: "switch" erstellen
        if reg.get("data_type") == "boolean" or reg.get("control") == "switch":
            # Unique_ID Format: {prefix}_{template_sensor_name}
            sensor_name = reg.get("name", "unknown")
            # Use unique_id from template if available, otherwise use cleaned name
            template_unique_id = reg.get("unique_id")
            if template_unique_id:
                # Check if template_unique_id already has prefix
                if template_unique_id.startswith(f"{prefix}_"):
                    unique_id = template_unique_id
                else:
                    unique_id = f"{prefix}_{template_unique_id}"
            else:
                # Fallback: Bereinige den Namen für den unique_id
                clean_name = sensor_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                unique_id = f"{prefix}_{clean_name}"
            
            entities.append(TemplateBinarySensor(
                hass=hass,
                name=sensor_name,
                unique_id=unique_id,
                template_data=reg,
                device_info={
                    "identifiers": {(DOMAIN, f"{prefix}_{template_name}")},
                    "name": f"{prefix} {template_name}",
                    "manufacturer": "Modbus Manager",
                    "model": template_name,
                    "sw_version": f"Firmware: {entry.data.get('firmware_version', '1.0.0')}",
                },
                prefix=prefix,
            ))

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Modbus Manager: Created %d binary sensor entities", len(entities))
        _LOGGER.debug("Created binary sensor entities: %s", [e.entity_id for e in entities])


class TemplateBinarySensor(BinarySensorEntity):
    """Representation of a Template Binary Sensor Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, 
                 template_data: dict, device_info: dict, prefix: str = None):
        """Initialize the template binary sensor entity."""
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._template_data = template_data
        self._attr_device_info = DeviceInfo(**device_info)
        self._prefix = prefix or "SG"  # Default prefix if not provided
        
        # Template properties
        self._state_template = None
        self._availability_template = None
        self._delay_on = template_data.get("delay_on", {})
        self._delay_off = template_data.get("delay_off", {})
        
        # Binary-Sensor properties
        self._attr_device_class = template_data.get("device_class", "problem")
        
        # Group for aggregations
        self._group = template_data.get("group")
        if self._group:
            self._attr_extra_state_attributes = {"group": self._group}
        
        self._attr_is_on = False
        
        # Initialize templates
        self._init_templates()

    def _init_templates(self):
        """Initialize template objects."""
        # State template
        state_template_str = self._template_data.get("state")
        if state_template_str:
            processed_state = self._process_template_with_prefix(state_template_str)
            self._state_template = Template(processed_state, self.hass)
        
        # Availability template
        availability_template_str = self._template_data.get("availability")
        if availability_template_str:
            processed_availability = self._process_template_with_prefix(availability_template_str)
            self._availability_template = Template(processed_availability, self.hass)

    def _process_template_with_prefix(self, template_str: str) -> str:
        """Process template string to inject prefix into sensor references."""
        try:
            # Replace {PREFIX} placeholder with actual prefix (uppercase for sensor names)
            # This allows templates to use {PREFIX} as a placeholder
            processed_template = template_str.replace("{PREFIX}", self._prefix)
            
            _LOGGER.debug("Template processing: %s -> %s", template_str, processed_template)
            return processed_template
            
        except Exception as e:
            _LOGGER.error("Error processing template for %s: %s", self._attr_name, str(e))
            return template_str

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return True

    async def async_update(self):
        """Update the binary sensor entity state."""
        try:
            # Check availability first
            if self._availability_template:
                try:
                    availability_result = self._availability_template.async_render()
                    if not availability_result:
                        self._attr_is_on = False
                        return
                except TemplateError as e:
                    _LOGGER.warning("Template error in availability for %s: %s", self.name, e)
                    self._attr_is_on = False
                    return
            
            # Update state from template
            if self._state_template:
                try:
                    state_result = self._state_template.async_render()
                    
                    # Handle 'unknown' and 'unavailable' values gracefully
                    if isinstance(state_result, str):
                        if state_result.lower() in ['unknown', 'unavailable', 'none']:
                            self._attr_is_on = False
                            return
                    
                    # Convert template result to boolean
                    if isinstance(state_result, bool):
                        self._attr_is_on = state_result
                    elif isinstance(state_result, str):
                        self._attr_is_on = state_result.lower() in ['true', 'on', '1', 'yes']
                    elif isinstance(state_result, (int, float)):
                        self._attr_is_on = bool(state_result)
                    else:
                        self._attr_is_on = False
                        
                except TemplateError as e:
                    # Check if it's a template error with 'unknown' input
                    if "int got invalid input 'unknown'" in str(e):
                        _LOGGER.debug("Binary sensor %s has 'unknown' value, setting to False", self.name)
                        self._attr_is_on = False
                    elif "float got invalid input 'unknown'" in str(e):
                        _LOGGER.debug("Binary sensor %s has 'unknown' value, setting to False", self.name)
                        self._attr_is_on = False
                    else:
                        _LOGGER.warning("Template error in state for %s: %s", self.name, e)
                        self._attr_is_on = False
            else:
                self._attr_is_on = False
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Binary Sensor %s: %s", self.name, str(e))
            self._attr_is_on = False