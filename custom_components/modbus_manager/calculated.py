"""Calculated sensor class for Modbus Manager."""
import logging
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.template import Template

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ModbusCalculatedSensor(SensorEntity):
    """Representation of a calculated sensor."""
    
    def __init__(
        self,
        hass,
        config: Dict[str, Any],
        prefix: str,
        template_name: str
    ):
        """Initialize the calculated sensor."""
        self.hass = hass
        self._config = config
        self._prefix = prefix
        self._template_name = template_name
        
        # Extract configuration
        base_name = config.get("name", "Unknown Calculated Sensor")
        self._attr_name = f"{prefix} {base_name}"
        self._attr_unique_id = f"sensor.{prefix}_{config.get('unique_id', config.get('name', 'unknown')).lower().replace(' ', '_')}"
        
        # Set explicit entity_id for proper tracking
        clean_unique_id = config.get('unique_id', config.get('name', 'unknown')).lower().replace(' ', '_')
        self._attr_entity_id = f"sensor.{prefix}_{clean_unique_id}"
        
        # Force entity_id to be used (prevent Home Assistant from overriding)
        self._attr_has_entity_name = False
        
        # Template processing - support both 'template' and 'state' parameters
        template_str = config.get("template", config.get("state", ""))
        if not template_str:
            raise ValueError(f"Calculated entity {self._attr_name} has no template or state defined")
        
        # Process template with prefix injection
        processed_template = self._process_template_with_prefix(template_str)
        try:
            self._template = Template(processed_template, hass)
        except Exception as e:
            _LOGGER.error("Error creating template for %s: %s", self._attr_name, str(e))
            raise
        
        # Availability template processing
        availability_template = config.get("availability")
        if availability_template:
            processed_availability = self._process_template_with_prefix(availability_template)
            self._availability_template = Template(processed_availability, hass)
        else:
            self._availability_template = None
        
        # Entity attributes
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")
        self._attr_entity_registry_enabled_default = True
        
        # Group for organization - set as attribute so Home Assistant can access it
        self._group = config.get("group", "calculated")
        self._attr_group = self._group
        
        # Device info for proper grouping
        self._device_info = {
            "identifiers": {(DOMAIN, f"{prefix}_{template_name}")},
            "name": f"{prefix} {template_name}",
            "manufacturer": "Modbus Manager",
            "model": template_name,
        }
        
        # State
        self._attr_native_value = None
        
        _LOGGER.debug("Created calculated sensor: %s (entity_id: %s, group: %s)", 
                      self._attr_name, self._attr_entity_id, self._group)
    
    def _process_template_with_prefix(self, template_str: str) -> str:
        """Process template string to inject prefix into sensor references."""
        try:
            # Replace {PREFIX} placeholder with actual prefix
            # This allows templates to use {PREFIX} as a placeholder
            processed_template = template_str.replace("{PREFIX}", self._prefix)
            
            _LOGGER.debug("Template processing: %s -> %s", template_str, processed_template)
            return processed_template
            
        except Exception as e:
            _LOGGER.error("Error processing template for %s: %s", self._attr_name, str(e))
            return template_str
    
    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device info for proper grouping."""
        return self._device_info
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._availability_template is None:
            return True
        
        try:
            # Use executor_job to avoid event loop issues
            if not hasattr(self, "_availability_result"):
                # Initialize with default value
                self._availability_result = True
            
            # We can't do async operations in a property, so we return the cached result
            # The actual update happens in async_update
            return bool(self._availability_result)
        except Exception as e:
            _LOGGER.error("Error checking availability for %s: %s", self._attr_name, str(e))
            return True  # Default to available if check fails
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "group": self._group,
            "template": self._template_name,
            "prefix": self._prefix,
            "calculation_type": "state"
        }
    
    @property
    def group(self) -> str:
        """Return the group this sensor belongs to."""
        return self._group
    
    async def async_update(self) -> None:
        """Update the calculated sensor value."""
        # Update availability first if template exists
        if self._availability_template is not None:
            try:
                # Use executor_job to safely run the sync render method
                availability_result = await self.hass.async_add_executor_job(
                    self._availability_template.render
                )
                self._availability_result = bool(availability_result)
            except Exception as e:
                _LOGGER.debug("Error checking availability for %s: %s", self._attr_name, str(e))
                self._availability_result = True  # Default to available if check fails
        
        # If not available, don't update the state
        if hasattr(self, "_availability_result") and not self._availability_result:
            self._attr_native_value = None
            return
            
        try:
            # Handle template rendering with proper async/sync detection
            try:
                # Use executor_job to safely run the sync render method
                rendered_value = await self.hass.async_add_executor_job(
                    self._template.render
                )
            except Exception as e:
                if "Cannot be called from within the event loop" in str(e):
                    _LOGGER.debug("Template rendering issue for %s, trying alternative method", self._attr_name)
                    # Try to get the value directly
                    try:
                        rendered_value = self._template.template
                        if hasattr(rendered_value, 'result'):
                            rendered_value = rendered_value.result()
                        else:
                            # If all else fails, set to None
                            rendered_value = None
                    except Exception:
                        rendered_value = None
                else:
                    raise
            
            if rendered_value is None:
                self._attr_native_value = None
                return
            
            # Handle 'unknown' and 'unavailable' values gracefully
            if isinstance(rendered_value, str):
                if rendered_value.lower() in ['unknown', 'unavailable', 'none']:
                    self._attr_native_value = None
                    return
                # Try to convert string to float/int
                try:
                    if "." in rendered_value:
                        self._attr_native_value = float(rendered_value)
                    else:
                        self._attr_native_value = int(rendered_value)
                except (ValueError, TypeError):
                    # If conversion fails, keep as string
                    self._attr_native_value = str(rendered_value)
            else:
                # Direct numeric value
                self._attr_native_value = rendered_value
                
        except Exception as e:
            # Check if it's a template error with 'unknown' input
            if "float got invalid input 'unknown'" in str(e):
                _LOGGER.debug("Sensor %s has 'unknown' value, setting to None", self._attr_name)
                self._attr_native_value = None
            elif "Cannot be called from within the event loop" in str(e):
                _LOGGER.debug("Template rendering issue for %s, setting to None", self._attr_name)
                self._attr_native_value = None
            else:
                _LOGGER.error("Error updating calculated sensor %s: %s", self._attr_name, str(e))
                self._attr_native_value = None
