"""Calculated sensor class for Modbus Manager."""

import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.template import Template

from .const import DOMAIN
from .device_utils import (
    create_base_extra_state_attributes,
    generate_entity_name,
    generate_unique_id,
)

_LOGGER = logging.getLogger(__name__)


class ModbusCalculatedSensor(SensorEntity):
    """Representation of a calculated sensor."""

    def __init__(
        self,
        hass,
        config: Dict[str, Any],
        prefix: str,
        template_name: str,
        host: str = None,
        port: int = 502,
        slave_id: int = 1,
        config_entry_id: str = None,
        device_prefix: str = None,
    ):
        """Initialize the calculated sensor."""
        self.hass = hass
        self._config = config
        self._template_name = template_name
        self._host = host
        self._port = port
        self._slave_id = slave_id

        # Extract configuration
        base_name = config.get("name", "Unknown Calculated Sensor")

        # Handle prefix - if None, config is already processed by coordinator
        if prefix is None:
            # Config is already processed by coordinator
            # Use device_prefix for display in attributes
            self._prefix = device_prefix if device_prefix else "unknown"
            # Set friendly_name to "prefix entityname" format
            self._attr_name = f"{self._prefix} {base_name}"
            unique_id = config.get("unique_id", "unknown")
        else:
            # Legacy mode - process prefix
            self._prefix = prefix
            # Set friendly_name to "prefix entityname" format
            # Remove prefix from base_name if present to avoid double prefix
            if base_name.startswith(f"{prefix} "):
                clean_base_name = base_name[len(f"{prefix} ") :]
            else:
                clean_base_name = base_name
            self._attr_name = f"{prefix} {clean_base_name}"
            unique_id = generate_unique_id(prefix, config.get("unique_id"), base_name)

        # unique_id should be just the value, not "sensor.{value}"
        # Home Assistant will auto-generate entity_id from unique_id
        self._attr_unique_id = unique_id
        default_entity_id = config.get("default_entity_id")
        if default_entity_id:
            if isinstance(default_entity_id, str):
                default_entity_id = default_entity_id.lower()
            if "." in default_entity_id:
                self._attr_entity_id = default_entity_id
            else:
                self._attr_entity_id = f"sensor.{default_entity_id}"
        # Set has_entity_name=False so friendly_name uses _attr_name directly (prefix entityname format)
        self._attr_has_entity_name = False

        # Template processing - support both 'template' and 'state' parameters
        template_str = config.get("template", config.get("state", ""))
        if not template_str:
            raise ValueError(
                f"Calculated entity {self._attr_name} has no template or state defined"
            )

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
            processed_availability = self._process_template_with_prefix(
                availability_template
            )
            self._availability_template = Template(processed_availability, hass)
        else:
            self._availability_template = None

        # Entity attributes
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")
        self._attr_entity_registry_enabled_default = True

        # Set entity category - calculated sensors are typically primary (None) or diagnostic
        entity_category_str = config.get("entity_category")
        if entity_category_str == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category_str == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            # Default: None for primary calculated sensors (main data points)
            self._attr_entity_category = None

        # Icon support
        self._static_icon = config.get("icon")
        self._icon_template = config.get("icon_template")
        if self._static_icon:
            self._attr_icon = self._static_icon
            _LOGGER.debug(
                "Static icon set for calculated sensor %s: %s",
                self._attr_name,
                self._static_icon,
            )
        elif self._icon_template:
            # Icon template will be processed during updates
            _LOGGER.debug(
                "Dynamic icon template set for calculated sensor %s", self._attr_name
            )

        # Group for organization - set as attribute so Home Assistant can access it
        self._group = config.get("group", "calculated")
        self._attr_group = self._group

        # Set precision for display formatting
        # This ensures small values are displayed with decimal places (e.g., 0.00234 V instead of 0 V)
        # Only set precision if not explicitly disabled (will be removed if sensor returns string)
        precision = config.get("precision")
        if precision is not None and isinstance(precision, int) and precision > 0:
            self._attr_suggested_display_precision = precision
        elif precision is None:
            # Default to 5 decimal places for calculated entities if not specified
            # Will be removed in async_update if sensor returns a string value
            self._attr_suggested_display_precision = 5
        # If precision is explicitly set to 0 or False, don't set suggested_display_precision

        # Use device_info from config (already attached by coordinator)
        device_info_from_config = config.get("device_info")
        if device_info_from_config:
            # Device info already provided by coordinator
            # Convert dict to DeviceInfo object for proper device membership
            from homeassistant.helpers.entity import DeviceInfo

            self._attr_device_info = DeviceInfo(**device_info_from_config)
            _LOGGER.debug(
                "Using device_info from coordinator config for %s", self._attr_name
            )
        else:
            _LOGGER.error(
                "Calculated entity %s missing device_info. Coordinator should provide this.",
                self._attr_name,
            )
            raise ValueError("device_info missing from coordinator")

        # State
        self._attr_native_value = None

        _LOGGER.debug(
            "Created calculated sensor: %s (unique_id: %s, group: %s)",
            self._attr_name,
            self._attr_unique_id,
            self._group,
        )

    def _process_template_with_prefix(self, template_str: str) -> str:
        """Process template string to inject prefix into sensor references."""
        try:
            # Replace {PREFIX} placeholder with actual prefix
            # This allows templates to use {PREFIX} as a placeholder
            if self._prefix is not None:
                processed_template = template_str.replace("{PREFIX}", self._prefix)
            else:
                # If prefix is None, config is already processed by coordinator
                # Just return the template as-is
                processed_template = template_str
            return processed_template

        except Exception as e:
            _LOGGER.error(
                "Error processing template for %s: %s", self._attr_name, str(e)
            )
            return template_str

    # device_info is now handled via _attr_device_info (DeviceInfo object)
    # Home Assistant will automatically use _attr_device_info for device membership

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
            _LOGGER.error(
                "Error checking availability for %s: %s", self._attr_name, str(e)
            )
            return True  # Default to available if check fails

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        # Create a register_config-like dict for the central function
        # Calculated entities don't have register addresses, so we use None/0
        register_config_like = {
            "address": self._config.get("address", 0),  # May not exist for calculated
            "data_type": self._config.get("data_type"),  # May not exist
            "slave_id": self._slave_id,
            "input_type": self._config.get("input_type"),  # May not exist
            "scale": self._config.get("scale"),
            "offset": self._config.get("offset"),
            "precision": self._config.get("precision"),
            "group": self._group,
            "scan_interval": self._config.get("scan_interval"),
            "swap": self._config.get("swap"),
        }

        # Use central function and add calculated-specific attributes
        return create_base_extra_state_attributes(
            unique_id=self._attr_unique_id,
            register_config=register_config_like,
            scan_interval=self._config.get("scan_interval"),
            additional_attributes={
                "template": self._template_name,
                "prefix": self._prefix,
                "calculation_type": "state",
            },
        )

    @property
    def group(self) -> str:
        """Return the group this sensor belongs to."""
        return self._group

    @property
    def should_poll(self) -> bool:
        """Return True to enable polling for calculated sensors.

        This is required for Home Assistant to automatically update
        the sensor and make it available in Helper UI (e.g., Riemann Integral).
        """
        return True

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
                _LOGGER.debug(
                    "Error checking availability for %s: %s", self._attr_name, str(e)
                )
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
                    _LOGGER.debug(
                        "Template rendering issue for %s, trying alternative method",
                        self._attr_name,
                    )
                    # Try to get the value directly
                    try:
                        rendered_value = self._template.template
                        if hasattr(rendered_value, "result"):
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
                if rendered_value.lower() in ["unknown", "unavailable", "none"]:
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
                    # Remove suggested_display_precision for string values
                    self._attr_native_value = str(rendered_value)
                    if hasattr(self, "_attr_suggested_display_precision"):
                        self._attr_suggested_display_precision = None
            else:
                # Direct numeric value
                self._attr_native_value = rendered_value
                # Ensure precision is set for numeric values if not already set
                if (
                    not hasattr(self, "_attr_suggested_display_precision")
                    or self._attr_suggested_display_precision is None
                ):
                    precision = self._config.get("precision")
                    if (
                        precision is not None
                        and isinstance(precision, int)
                        and precision > 0
                    ):
                        self._attr_suggested_display_precision = precision
                    else:
                        self._attr_suggested_display_precision = 5

            # Update dynamic icon if template is configured
            if self._icon_template and self._attr_native_value is not None:
                try:
                    # Process icon template with prefix injection
                    processed_icon_template = self._process_template_with_prefix(
                        self._icon_template
                    )
                    icon_template = Template(processed_icon_template, self.hass)
                    rendered_icon = await self.hass.async_add_executor_job(
                        icon_template.render
                    )
                    if rendered_icon and isinstance(rendered_icon, str):
                        self._attr_icon = rendered_icon.strip()
                        _LOGGER.debug(
                            "Dynamic icon updated for %s: %s",
                            self._attr_name,
                            self._attr_icon,
                        )
                except Exception as icon_error:
                    _LOGGER.debug(
                        "Error updating dynamic icon for %s: %s",
                        self._attr_name,
                        str(icon_error),
                    )
                    # Keep existing icon or use static icon as fallback
                    if self._static_icon:
                        self._attr_icon = self._static_icon

        except Exception as e:
            # Check if it's a template error with 'unknown' input
            if "float got invalid input 'unknown'" in str(e):
                _LOGGER.debug(
                    "Sensor %s has 'unknown' value, setting to None", self._attr_name
                )
                self._attr_native_value = None
            elif "Cannot be called from within the event loop" in str(e):
                _LOGGER.debug(
                    "Template rendering issue for %s, setting to None", self._attr_name
                )
                self._attr_native_value = None
            else:
                _LOGGER.error(
                    "Error updating calculated sensor %s: %s", self._attr_name, str(e)
                )
                self._attr_native_value = None


class ModbusCalculatedBinarySensor(BinarySensorEntity):
    """Representation of a calculated binary sensor."""

    def __init__(
        self,
        hass,
        config: Dict[str, Any],
        prefix: str,
        template_name: str,
        host: str = None,
        port: int = 502,
        slave_id: int = 1,
        config_entry_id: str = None,
        device_prefix: str = None,
    ):
        """Initialize the calculated binary sensor."""
        self.hass = hass
        self._config = config
        self._template_name = template_name
        self._host = host
        self._port = port
        self._slave_id = slave_id

        # Extract configuration
        base_name = config.get("name", "Unknown Binary Sensor")

        # Handle prefix - if None, config is already processed by coordinator
        if prefix is None:
            # Config is already processed by coordinator
            # Use device_prefix for display in attributes
            self._prefix = device_prefix if device_prefix else "unknown"
            # Set friendly_name to "prefix entityname" format
            self._attr_name = f"{self._prefix} {base_name}"
            unique_id = config.get("unique_id", "unknown")
        else:
            # Legacy mode - process prefix
            self._prefix = prefix
            # Set friendly_name to "prefix entityname" format
            # Remove prefix from base_name if present to avoid double prefix
            if base_name.startswith(f"{prefix} "):
                clean_base_name = base_name[len(f"{prefix} ") :]
            else:
                clean_base_name = base_name
            self._attr_name = f"{prefix} {clean_base_name}"
            unique_id = generate_unique_id(prefix, config.get("unique_id"), base_name)

        # unique_id should be just the value, not "binary_sensor.{value}"
        # Home Assistant will auto-generate entity_id from unique_id
        self._attr_unique_id = unique_id
        default_entity_id = config.get("default_entity_id")
        if default_entity_id:
            if isinstance(default_entity_id, str):
                default_entity_id = default_entity_id.lower()
            if "." in default_entity_id:
                self._attr_entity_id = default_entity_id
            else:
                self._attr_entity_id = f"binary_sensor.{default_entity_id}"
        # Set has_entity_name=False so friendly_name uses _attr_name directly (prefix entityname format)
        self._attr_has_entity_name = False

        # Template processing - support 'state' parameter
        template_str = config.get("state", "")
        if not template_str:
            raise ValueError(
                f"Calculated binary sensor {self._attr_name} has no state template defined"
            )

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
            processed_availability = self._process_template_with_prefix(
                availability_template
            )
            self._availability_template = Template(processed_availability, hass)
        else:
            self._availability_template = None

        # Entity attributes
        self._attr_device_class = config.get("device_class")
        self._attr_is_on = None

        # Group for organization
        self._group = config.get("group", "calculated")
        self._attr_group = self._group

        # Use device_info from config (already attached by coordinator)
        device_info_from_config = config.get("device_info")
        if device_info_from_config:
            # Device info already provided by coordinator
            # Convert dict to DeviceInfo object for proper device membership
            from homeassistant.helpers.entity import DeviceInfo

            self._attr_device_info = DeviceInfo(**device_info_from_config)
            _LOGGER.debug(
                "Using device_info from coordinator config for %s", self._attr_name
            )
        else:
            _LOGGER.error(
                "Calculated binary sensor %s missing device_info. Coordinator should provide this.",
                self._attr_name,
            )
            raise ValueError("device_info missing from coordinator")

        _LOGGER.debug(
            "Created calculated binary sensor: %s (unique_id: %s, group: %s)",
            self._attr_name,
            self._attr_unique_id,
            self._group,
        )

    def _process_template_with_prefix(self, template_str: str) -> str:
        """Process template string to inject prefix into sensor references."""
        try:
            # Replace {PREFIX} placeholder with actual prefix
            if self._prefix is not None:
                processed_template = template_str.replace("{PREFIX}", self._prefix)
            else:
                # If prefix is None, config is already processed by coordinator
                # Just return the template as-is
                processed_template = template_str
            return processed_template

        except Exception as e:
            _LOGGER.error(
                "Error processing template for %s: %s", self._attr_name, str(e)
            )
            return template_str

    # device_info is now handled via _attr_device_info (DeviceInfo object)
    # Home Assistant will automatically use _attr_device_info for device membership

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._availability_template is None:
            return True

        try:
            # Use cached result
            if not hasattr(self, "_availability_result"):
                self._availability_result = True
            return bool(self._availability_result)
        except Exception as e:
            _LOGGER.error(
                "Error checking availability for %s: %s", self._attr_name, str(e)
            )
            return True

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        # Create a register_config-like dict for the central function
        # Calculated entities don't have register addresses, so we use None/0
        register_config_like = {
            "address": self._config.get("address", 0),  # May not exist for calculated
            "data_type": self._config.get("data_type"),  # May not exist
            "slave_id": self._slave_id,
            "input_type": self._config.get("input_type"),  # May not exist
            "scale": self._config.get("scale"),
            "offset": self._config.get("offset"),
            "precision": self._config.get("precision"),
            "group": self._group,
            "scan_interval": self._config.get("scan_interval"),
            "swap": self._config.get("swap"),
        }

        # Use central function and add calculated-specific attributes
        return create_base_extra_state_attributes(
            unique_id=self._attr_unique_id,
            register_config=register_config_like,
            scan_interval=self._config.get("scan_interval"),
            additional_attributes={
                "template": self._template_name,
                "prefix": self._prefix,
                "calculation_type": "binary_state",
            },
        )

    @property
    def group(self) -> str:
        """Return the group this sensor belongs to."""
        return self._group

    async def async_update(self) -> None:
        """Update the calculated binary sensor value."""
        # Update availability first if template exists
        if self._availability_template is not None:
            try:
                availability_result = await self.hass.async_add_executor_job(
                    self._availability_template.render
                )
                self._availability_result = bool(availability_result)
            except Exception as e:
                _LOGGER.debug(
                    "Error checking availability for %s: %s", self._attr_name, str(e)
                )
                self._availability_result = True

        # If not available, don't update the state
        if hasattr(self, "_availability_result") and not self._availability_result:
            self._attr_is_on = None
            return

        try:
            # Handle template rendering
            try:
                rendered_value = await self.hass.async_add_executor_job(
                    self._template.render
                )
            except Exception as e:
                if "Cannot be called from within the event loop" in str(e):
                    _LOGGER.debug(
                        "Template rendering issue for %s, trying alternative method",
                        self._attr_name,
                    )
                    try:
                        rendered_value = self._template.template
                        if hasattr(rendered_value, "result"):
                            rendered_value = rendered_value.result()
                        else:
                            rendered_value = None
                    except Exception:
                        rendered_value = None
                else:
                    raise

            if rendered_value is None:
                self._attr_is_on = None
                return

            # Convert rendered value to boolean
            if isinstance(rendered_value, bool):
                self._attr_is_on = rendered_value
            elif isinstance(rendered_value, (int, float)):
                # For numeric values, 0 is False, anything else is True
                self._attr_is_on = bool(rendered_value) and rendered_value != 0
            elif isinstance(rendered_value, str):
                # For strings, check for special values first
                rendered_lower = rendered_value.lower().strip()
                if rendered_lower in ["unknown", "unavailable", "none", ""]:
                    self._attr_is_on = None
                elif rendered_lower in ["on", "true", "1", "yes"]:
                    self._attr_is_on = True
                elif rendered_lower in ["off", "false", "0", "no"]:
                    self._attr_is_on = False
                else:
                    # Try to convert to boolean/int
                    try:
                        self._attr_is_on = bool(int(rendered_value))
                    except (ValueError, TypeError):
                        # If conversion fails, log warning and treat as False
                        _LOGGER.warning(
                            "Binary sensor %s received unrecognized string value: '%s', treating as False",
                            self._attr_name,
                            rendered_value,
                        )
                        self._attr_is_on = False
            else:
                # Fallback: convert to bool
                self._attr_is_on = (
                    bool(rendered_value) if rendered_value is not None else None
                )

            _LOGGER.debug(
                "Binary sensor %s updated: state=%s (rendered=%s)",
                self._attr_name,
                self._attr_is_on,
                rendered_value,
            )

        except Exception as e:
            _LOGGER.error(
                "Error updating calculated binary sensor %s: %s",
                self._attr_name,
                str(e),
            )
            self._attr_is_on = None
