"""Config Flow for Modbus Manager."""

import asyncio
import json
import os
from signal import default_int_handler
from typing import List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_DELAY,
    DEFAULT_MESSAGE_WAIT_MS,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MIN_DELAY,
    MIN_MESSAGE_WAIT_MS,
    MIN_TIMEOUT,
)
from .logger import ModbusManagerLogger
from .template_loader import get_template_by_name, get_template_names

_LOGGER = ModbusManagerLogger(__name__)


class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Manager."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self._templates = {}
        self._selected_template = None

    # def _read_file_sync(self, file_path: str) -> str:
    #     """Read file synchronously (to be run in executor)."""
    #     with open(file_path, "r", encoding="utf-8") as f:
    #         return f.read()

    # Step 1: User selects template
    # show all templates and let the user select one
    # if the template has dynamic_config, show the connection step
    # if the template has no dynamic_config, show the device config step
    async def async_step_user(self, user_input: dict = None) -> FlowResult:
        """Handle the initial step."""
        try:
            template_names = await get_template_names()
            self._templates = {}
            for name in template_names:
                template_data = await get_template_by_name(name)
                if template_data:
                    self._templates[name] = template_data
                    _LOGGER.debug(
                        "Loaded template %s: has_dynamic_config=%s",
                        name,
                        "dynamic_config" in template_data,
                    )

            if not self._templates:
                return self.async_abort(
                    reason="no_templates",
                    description_placeholders={
                        "error": "No templates found. Please ensure templates are present in the device_templates directory."
                    },
                )

            if user_input is not None:
                # Select template
                if "template" in user_input:
                    self._selected_template = user_input["template"]
                    _LOGGER.info("=== TEMPLATE SELECTION DEBUG ===")
                    _LOGGER.info("Selected template: %s", self._selected_template)

                    # Debug template data
                    template_data = self._templates.get(self._selected_template, {})
                    _LOGGER.info("Template data keys: %s", list(template_data.keys()))
                    _LOGGER.info(
                        "Template type: '%s'", template_data.get("type", "NOT_FOUND")
                    )

                    # Check template type
                    template_data = self._templates.get(self._selected_template, {})
                    _LOGGER.debug(
                        "Template data for %s: keys=%s, has_dynamic_config=%s",
                        self._selected_template,
                        list(template_data.keys()),
                        "dynamic_config" in template_data,
                    )

                    # Check for dynamic config
                    if template_data.get("dynamic_config"):
                        return await self.async_step_connection()
                    else:
                        return await self.async_step_device_config()

                # Device configuration
                return await self.async_step_final_config(user_input)

            # Show template selection
            template_names = list(self._templates.keys())
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("template"): vol.In(template_names),
                    }
                ),
                description_placeholders={
                    "template_count": str(len(template_names)),
                    "template_list": ", ".join(template_names),
                },
            )

        except Exception as e:
            _LOGGER.error("Fehler im Config Flow: %s", str(e))
            return self.async_abort(
                reason="unknown_error", description_placeholders={"error": str(e)}
            )

    # Step 2a: User selected a template with dynamic config
    # show the connection step for the modbus connection setup
    async def async_step_connection(self, user_input: dict = None) -> FlowResult:
        """Handle connection parameters step for dynamic templates."""
        if user_input is not None:
            # Store connection parameters and proceed to dynamic config
            self._connection_params = user_input
            _LOGGER.info("Connection parameters stored, proceeding to dynamic config")
            return await self.async_step_dynamic_config()

        # Get template defaults for prefilling
        template_data = self._templates.get(self._selected_template, {})
        default_prefix = template_data.get("default_prefix", "SG")
        default_slave_id = template_data.get("default_slave_id", DEFAULT_SLAVE)

        # Show connection parameters form
        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Required("prefix", default=default_prefix): str,
                    vol.Required("host"): str,
                    vol.Optional("port", default=DEFAULT_PORT): int,
                    vol.Optional("slave_id", default=default_slave_id): int,
                    vol.Optional("timeout", default=DEFAULT_TIMEOUT): int,
                    vol.Optional("delay", default=DEFAULT_DELAY): int,
                    vol.Optional("request_delay", default=DEFAULT_MESSAGE_WAIT_MS): int,
                }
            ),
            description_placeholders={
                "template_name": self._selected_template,
            },
        )

    # Step 3: User selected a template with dynamic config
    # show the dynamic config step for the template
    async def async_step_dynamic_config(self, user_input: dict = None) -> FlowResult:
        """Handle dynamic configuration step for templates with dynamic config."""

        if user_input is not None:
            # Combine connection params with dynamic config
            combined_input = {**self._connection_params, **user_input}

            # Check if this is a PV inverter template - if so, ask about battery
            template_data = self._templates.get(self._selected_template, {})
            template_type = template_data.get("type", "")

            _LOGGER.info("=== BATTERY DETECTION DEBUG ===")
            _LOGGER.info("Selected template: %s", self._selected_template)
            _LOGGER.info("Template data keys: %s", list(template_data.keys()))
            _LOGGER.info("Template type: '%s'", template_type)
            _LOGGER.info(
                "Template type == 'pv_inverter': %s", template_type == "pv_inverter"
            )
            _LOGGER.info(
                "Template type.lower() == 'pv_inverter': %s",
                template_type.lower() == "pv_inverter",
            )
            _LOGGER.info(
                "Template type.lower() in ['pv_inverter', 'pv_hybrid_inverter']: %s",
                template_type.lower() in ["pv_inverter", "pv_hybrid_inverter"],
            )

            # Check for PV inverter (case-insensitive) - support both PV_inverter and PV_Hybrid_Inverter
            if template_type.lower() in ["pv_inverter", "pv_hybrid_inverter"]:
                # Store the inverter config and ask about battery
                self._inverter_config = combined_input
                _LOGGER.info("PV inverter detected - proceeding to battery detection")
                return await self.async_step_battery_detection()
            else:
                # For non-PV inverters, proceed directly to final config
                _LOGGER.info("Non-PV inverter - proceeding directly to final config")
                return await self.async_step_final_config(combined_input)

        # Get template data
        template_data = self._templates.get(self._selected_template, {})

        # Generate schema for dynamic config using the helper function
        schema_fields = self._get_dynamic_config_schema(template_data)

        return self.async_show_form(
            step_id="dynamic_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "template_name": self._selected_template,
            },
        )

    # Step 3b: User selected a template without dynamic config
    async def async_step_device_config(self, user_input: dict = None) -> FlowResult:
        """Handle device configuration step."""
        if user_input is not None:
            battery_config = user_input.get("battery_config")

            # Battery configuration is now simplified - no separate SBR battery step needed
            _LOGGER.debug(
                "Battery config: %s, proceeding to final config", battery_config
            )
            return await self.async_step_final_config(user_input)

        # Check if this is a simple template
        template_data = self._templates.get(self._selected_template, {})
        if template_data.get("is_simple_template"):
            # Simple template - only requires prefix and name
            default_prefix = template_data.get("default_prefix", "device")
            return self.async_show_form(
                step_id="device_config",
                data_schema=vol.Schema(
                    {
                        vol.Required("prefix", default=default_prefix): str,
                        vol.Optional("name"): str,
                    }
                ),
                description_placeholders={
                    "template": self._selected_template,
                    "description": template_data.get(
                        "description", "Simplified Template"
                    ),
                },
            )
        else:
            # Regular template - requires full Modbus configuration
            default_prefix = template_data.get("default_prefix", "device")
            default_slave_id = template_data.get("default_slave_id", DEFAULT_SLAVE)

            # Field descriptions are handled by translation files
            schema_fields = {
                vol.Required("prefix", default=default_prefix): str,
                vol.Required("host"): str,
                vol.Optional("port", default=DEFAULT_PORT): int,
                vol.Optional("slave_id", default=default_slave_id): int,
                vol.Optional("timeout", default=DEFAULT_TIMEOUT): int,
                vol.Optional("delay", default=DEFAULT_DELAY): int,
                vol.Optional(
                    "message_wait_milliseconds", default=DEFAULT_MESSAGE_WAIT_MS
                ): int,
            }

            return self.async_show_form(
                step_id="device_config",
                data_schema=vol.Schema(schema_fields),
                description_placeholders={"template": self._selected_template},
            )

    def _supports_dynamic_config(self, template_data: dict) -> bool:
        """Check if template supports dynamic configuration."""
        # Check if template has dynamic_config section
        has_dynamic = "dynamic_config" in template_data
        _LOGGER.info(
            "_supports_dynamic_config: template_data keys=%s, has_dynamic=%s",
            list(template_data.keys()),
            has_dynamic,
        )

        return has_dynamic

    def _get_dynamic_config_schema(self, template_data: dict) -> dict:
        """Generate dynamic configuration schema based on template."""
        dynamic_config = template_data.get("dynamic_config", {})
        schema_fields = {}

        # Check if template has valid_models (model selection)
        # Look for valid_models in dynamic_config first, then at template root level
        valid_models = dynamic_config.get("valid_models") or template_data.get(
            "valid_models"
        )

        if valid_models:
            # Create model options with generic display names
            model_options = {}
            if valid_models and isinstance(valid_models, dict):
                for model_name, config in valid_models.items():
                    # Dynamically build display name from all fields in config
                    field_parts = []
                    for field_name, field_value in config.items():
                        # Format field names for display
                        if field_name == "phases":
                            field_parts.append(f"{field_value}Φ")
                        elif field_name == "mppt_count":
                            field_parts.append(f"{field_value} MPPT")
                        elif field_name == "string_count":
                            field_parts.append(f"{field_value} Strings")
                        elif field_name == "modules":
                            field_parts.append(f"{field_value} Modules")
                        elif field_name == "type_code":
                            # Skip type_code from display
                            continue
                        else:
                            # Generic formatting for other fields
                            field_parts.append(f"{field_name}: {field_value}")

                    display_name = f"{model_name} ({', '.join(field_parts)})"
                    model_options[model_name] = display_name

            schema_fields["selected_model"] = vol.In(model_options)
        else:
            # Individual field configuration - generic for any device type
            # Process all configurable fields dynamically
            for field_name, field_config in dynamic_config.items():
                # Skip special fields that are handled separately
                if field_name in [
                    "valid_models",
                    "firmware_version",
                    "connection_type",
                    "battery_slave_id",
                ]:
                    continue

                # Check if this field has options (making it configurable)
                if isinstance(field_config, dict) and "options" in field_config:
                    options = field_config.get("options", [])
                    default = field_config.get(
                        "default", options[0] if options else None
                    )

                    if options:
                        schema_fields[
                            vol.Optional(field_name, default=default)
                        ] = vol.In(options)
                        _LOGGER.debug(
                            "Added configurable field %s with options: %s, default: %s",
                            field_name,
                            options,
                            default,
                        )
                elif isinstance(field_config, dict) and "default" in field_config:
                    # Field with default value but no options (single value)
                    default_value = field_config.get("default")
                    # Use proper vol.Optional format for voluptuous_serialize compatibility
                    if isinstance(default_value, int):
                        schema_fields[
                            vol.Optional(field_name, default=default_value)
                        ] = int
                    elif isinstance(default_value, float):
                        schema_fields[
                            vol.Optional(field_name, default=default_value)
                        ] = float
                    else:
                        schema_fields[
                            vol.Optional(field_name, default=str(default_value))
                        ] = str
                    _LOGGER.debug(
                        "Added field %s with default: %s", field_name, default_value
                    )

        # Add firmware version if available
        if "firmware_version" in dynamic_config:
            firmware_options = dynamic_config["firmware_version"].get(
                "options", ["1.0"]
            )
            firmware_default = dynamic_config["firmware_version"].get("default", "1.0")
            schema_fields[
                vol.Optional("firmware_version", default=firmware_default)
            ] = vol.In(firmware_options)

        # Add connection type if available
        if "connection_type" in dynamic_config:
            connection_options = dynamic_config["connection_type"].get(
                "options", ["LAN", "WINET"]
            )
            connection_default = dynamic_config["connection_type"].get("default", "LAN")
            schema_fields[
                vol.Optional("connection_type", default=connection_default)
            ] = vol.In(connection_options)

        # Battery slave ID removed - using connection slave_id instead

        _LOGGER.debug("Final schema fields: %s", list(schema_fields.keys()))
        return schema_fields

    # Process dynamic configuration and filtering out the sensors, calculated, controls and binary sensors
    def _process_dynamic_config(self, user_input: dict, template_data: dict) -> dict:
        """Process template based on dynamic configuration parameters."""

        _LOGGER.debug(
            "_process_dynamic_config user_input keys: %s", list(user_input.keys())
        )

        original_sensors = template_data.get("sensors", [])
        original_calculated = template_data.get("calculated", [])
        original_controls = template_data.get("controls", [])
        dynamic_config = template_data.get("dynamic_config", {})

        processed_sensors = []
        processed_calculated = []
        processed_controls = []

        # Check if model-specific config is used
        selected_model = user_input.get("selected_model")
        if selected_model:
            # Get configuration from selected model
            # Look for valid_models in dynamic_config first, then at template root level
            valid_models = dynamic_config.get("valid_models") or template_data.get(
                "valid_models", {}
            )

            # Get model configuration directly from valid_models
            model_config = (
                valid_models.get(selected_model)
                if valid_models and isinstance(valid_models, dict)
                else None
            )
            if model_config:
                # Generic model configuration - extract all fields dynamically
                config_values = {}
                for field_name, field_value in model_config.items():
                    config_values[field_name] = field_value

                # Set defaults for common fields if not present
                phases = config_values.get("phases", 3)
                mppt_count = config_values.get("mppt_count", 1)
                string_count = config_values.get("string_count", 1)
                modules = config_values.get("modules", 3)

                # Log all configuration values
                config_str = ", ".join([f"{k}={v}" for k, v in config_values.items()])
                _LOGGER.info(
                    "Using model-specific config for %s: %s",
                    selected_model,
                    config_str,
                )
            else:
                _LOGGER.warning(
                    "Model config not found for %s, using defaults", selected_model
                )
                phases = 3
                mppt_count = 1
                string_count = 1
        else:
            # Individual field configuration - generic for any device type
            # Extract all configurable fields dynamically
            phases = user_input.get(
                "phases", dynamic_config.get("phases", {}).get("default", 3)
            )
            mppt_count = user_input.get(
                "mppt_count", dynamic_config.get("mppt_count", {}).get("default", 1)
            )
            string_count = user_input.get(
                "string_count", dynamic_config.get("string_count", {}).get("default", 1)
            )
            modules = user_input.get(
                "modules", dynamic_config.get("modules", {}).get("default", 3)
            )

            # Log all individual field values for debugging
            individual_fields = []
            for field_name, field_config in dynamic_config.items():
                if field_name not in [
                    "valid_models",
                    "firmware_version",
                    "connection_type",
                    "battery_slave_id",
                ]:
                    field_value = user_input.get(
                        field_name, field_config.get("default", "unknown")
                    )
                    individual_fields.append(f"{field_name}={field_value}")

            _LOGGER.info(
                "Using individual field configuration: %s",
                ", ".join(individual_fields),
            )

        battery_default = dynamic_config.get("battery_config", {}).get(
            "default", "none"
        )
        battery_config = user_input.get("battery_config", battery_default)

        # Use connection slave_id for all devices (including battery)
        battery_slave_id = user_input.get("slave_id", 1)

        firmware_version = user_input.get(
            "firmware_version", template_data.get("firmware_version", "1.0.0")
        )
        connection_type = user_input.get("connection_type", "LAN")

        # Derive battery settings from battery_config
        # For SBR templates, always enable battery mode
        if (
            "sbr" in template_data.get("name", "").lower()
            or "battery" in template_data.get("type", "").lower()
        ):
            battery_enabled = True
            battery_type = "sbr_battery"
        else:
            battery_enabled = battery_config != "none"
            battery_type = battery_config

        # Handle "Latest" firmware version - use the highest available version
        if firmware_version == "Latest":
            firmware_config = dynamic_config.get("firmware_version", {})
            available_firmware = firmware_config.get("options", [])

            if available_firmware:
                # Find the highest version (excluding "Latest")
                numeric_versions = [v for v in available_firmware if v != "Latest"]
                if numeric_versions:
                    from packaging import version

                    try:
                        # Sort by version and take the highest
                        sorted_versions = sorted(
                            numeric_versions, key=lambda x: version.parse(x)
                        )
                        firmware_version = sorted_versions[-1]
                        _LOGGER.debug(
                            "Using latest firmware version: %s", firmware_version
                        )
                    except version.InvalidVersion:
                        # Fallback to first numeric version
                        firmware_version = numeric_versions[0]
                        _LOGGER.debug(
                            "Using fallback firmware version: %s", firmware_version
                        )

        _LOGGER.info(
            "Processing dynamic config: phases=%d, mppt=%d, battery=%s, battery_type=%s, fw=%s, conn=%s",
            phases,
            mppt_count,
            battery_enabled,
            battery_type,
            firmware_version,
            connection_type,
        )

        # Add modules to dynamic_config for condition filtering
        if selected_model and model_config:
            dynamic_config["modules"] = modules
        else:
            # For individual field configuration, add all fields to dynamic_config
            dynamic_config["modules"] = modules
            # Add other individual fields that might be used for filtering
            for field_name, field_config in dynamic_config.items():
                if field_name not in [
                    "valid_models",
                    "firmware_version",
                    "connection_type",
                    "battery_slave_id",
                ]:
                    if isinstance(field_config, dict) and "default" in field_config:
                        field_value = user_input.get(
                            field_name, field_config.get("default")
                        )
                        dynamic_config[field_name] = field_value

        # Process sensors
        for sensor in original_sensors:
            # Check if sensor should be included based on configuration
            sensor_name = sensor.get("name", "unknown")
            unique_id = sensor.get("unique_id", "unknown")
            _LOGGER.debug(
                "Processing sensor: %s (unique_id: %s)", sensor_name, unique_id
            )

            should_include = self._should_include_sensor(
                sensor,
                phases,
                mppt_count,
                battery_enabled,
                battery_type,
                battery_slave_id,
                firmware_version,
                connection_type,
                dynamic_config,
                string_count,
            )

            if should_include:
                # Apply firmware-specific modifications
                modified_sensor = self._apply_firmware_modifications(
                    sensor, firmware_version, dynamic_config
                )
                processed_sensors.append(modified_sensor)
                _LOGGER.debug("Included sensor: %s", sensor_name)
            else:
                _LOGGER.debug("Excluded sensor: %s", sensor_name)

        # Process calculated sensors
        for calculated in original_calculated:
            # Check if calculated sensor should be included based on configuration
            if self._should_include_sensor(
                calculated,
                phases,
                mppt_count,
                battery_enabled,
                battery_type,
                battery_slave_id,
                firmware_version,
                connection_type,
                dynamic_config,
                string_count,
            ):
                processed_calculated.append(calculated)

        # Process binary sensors
        original_binary_sensors = template_data.get("binary_sensors", [])
        processed_binary_sensors = []
        for binary_sensor in original_binary_sensors:
            # Binary sensors are always included (they don't depend on hardware config)
            processed_binary_sensors.append(binary_sensor)

        # Process controls
        for control in original_controls:
            # Check if control should be included based on configuration
            if self._should_include_sensor(
                control,
                phases,
                mppt_count,
                battery_enabled,
                battery_type,
                battery_slave_id,
                firmware_version,
                connection_type,
                dynamic_config,
                string_count,
            ):
                processed_controls.append(control)

        # Return processed template data and configuration values

        return {
            "sensors": processed_sensors,
            "calculated": processed_calculated,
            "binary_sensors": processed_binary_sensors,
            "controls": processed_controls,
            # Also return configuration values for use in _create_regular_entry
            "config_values": {
                "phases": phases,
                "mppt_count": mppt_count,
                "string_count": string_count,
                "modules": modules,
                "battery_config": battery_config,
                "battery_enabled": battery_enabled,
                "battery_type": battery_type,
                "battery_slave_id": battery_slave_id,
                "firmware_version": firmware_version,
                "connection_type": connection_type,
                "selected_model": selected_model,
                "dynamic_config": dynamic_config,
            },
        }

    def _should_include_sensor(
        self,
        sensor: dict,
        phases: int,
        mppt_count: int,
        battery_enabled: bool,
        battery_type: str,
        battery_slave_id: int,
        firmware_version: str,
        connection_type: str,
        dynamic_config: dict,
        string_count: int = 0,
    ) -> bool:
        """Check if sensor should be included based on configuration."""
        sensor_name = sensor.get("name", "") or ""
        unique_id = sensor.get("unique_id", "") or ""

        # Ensure we have strings
        sensor_name = str(sensor_name).lower()
        unique_id = str(unique_id).lower()

        # Check both sensor_name and unique_id for filtering
        search_text = f"{sensor_name} {unique_id}".lower()

        # For SBR battery templates, only include battery-related sensors
        if battery_type == "sbr_battery":
            # Only include sensors that are battery-related
            battery_keywords = [
                "battery",
                "sbr",
                "soc",
                "soh",
                "cell",
                "module",
                "voltage",
                "current",
                "temperature",
                "charge",
                "discharge",
            ]
            if not any(keyword in search_text for keyword in battery_keywords):
                return False

        # Phase-specific sensors
        if phases == 1:
            # Exclude phase B and C sensors for single phase
            if any(phase in search_text for phase in ["phase b", "phase c"]):
                return False

        # MPPT-specific sensors
        if "mppt" in search_text:
            mppt_number = self._extract_mppt_number(search_text)
            if mppt_number and mppt_number > mppt_count:
                return False

        # String-specific sensors
        if "string" in search_text:
            string_number = self._extract_string_number(search_text)
            if string_number and string_number > string_count:
                return False

        # Module-specific sensors (for batteries)
        if "module" in search_text:
            module_number = self._extract_module_number(search_text)
            if module_number:
                actual_modules = dynamic_config.get("modules", 0)
                if module_number > actual_modules:
                    return False

        # All other sensors are included
        return True

    # REGEX FUNCTIONS
    def _extract_mppt_number(self, search_text: str) -> int:
        """Extract MPPT number from sensor name or unique_id."""
        import re

        if not search_text:
            return None

        match = re.search(r"mppt(\d+)", search_text.lower())
        if match and match.group(1):
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        return None

    def _extract_string_number(self, search_text: str) -> int:
        """Extract string number from sensor name or unique_id."""
        import re

        if not search_text:
            return None

        # Look for "string" followed by digits, with optional underscore or space
        match = re.search(r"string[_\s]*(\d+)", search_text.lower())
        if match and match.group(1):
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        return None

    def _extract_module_number(self, search_text: str) -> int:
        """Extract module number from sensor name or unique_id."""
        import re

        if not search_text:
            return None

        # Look for "module" followed by digits, with optional underscore or space
        match = re.search(r"module[_\s]*(\d+)", search_text.lower())
        if match and match.group(1):
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        return None

    # Firmware Handling to replace the sensors with the correct firmware version
    def _apply_firmware_modifications(
        self, sensor: dict, firmware_version: str, dynamic_config: dict
    ) -> dict:
        """Apply firmware-specific modifications to sensor based on unique_id."""
        modified_sensor = sensor.copy()

        # Get sensor replacements configuration
        sensor_replacements = dynamic_config.get("sensor_replacements", {})

        # Get sensor unique_id
        unique_id = sensor.get("unique_id", "")

        # Check if this sensor has firmware-specific replacements
        if unique_id in sensor_replacements:
            replacements = sensor_replacements.get(unique_id, {})

            # Check if replacements is valid and not empty
            if replacements and isinstance(replacements, dict) and replacements:
                # Find the highest firmware version that matches or is lower than current
                replacement_keys = list(replacements.keys()) if replacements else []
                applicable_version = self._find_applicable_firmware_version(
                    firmware_version, replacement_keys
                )

                if applicable_version:
                    replacement_config = replacements.get(applicable_version, {})
                    _LOGGER.debug(
                        "Applying firmware %s replacement for sensor %s",
                        applicable_version,
                        unique_id,
                    )

                    # Apply all replacement parameters
                    if replacement_config and isinstance(replacement_config, dict):
                        for param, value in replacement_config.items():
                            if (
                                param != "description"
                            ):  # Skip description, it's just for documentation
                                modified_sensor[param] = value
                                _LOGGER.debug(
                                    "Replaced %s=%s for sensor %s (firmware %s)",
                                    param,
                                    value,
                                    unique_id,
                                    applicable_version,
                                )

        return modified_sensor

    def _find_applicable_firmware_version(
        self, current_version: str, available_versions: list
    ) -> str:
        """Find the highest firmware version that matches or is lower than current version."""
        from packaging import version

        # Check if available_versions is valid
        if not available_versions or not isinstance(available_versions, (list, dict)):
            return None

        try:
            # Try to parse as semantic version first
            current_ver = version.parse(current_version)
            applicable_versions = []

            for ver_str in available_versions:
                try:
                    ver = version.parse(ver_str)
                    if ver <= current_ver:
                        applicable_versions.append(ver)
                except version.InvalidVersion:
                    # Skip invalid semantic versions
                    continue

            if applicable_versions:
                # Return the highest applicable version
                return str(max(applicable_versions))

        except version.InvalidVersion:
            # For non-semantic versions (like SAPPHIRE-H_03011.95.01),
            # try exact match first, then fallback to string comparison
            _LOGGER.debug(
                "Non-semantic firmware version format detected: %s", current_version
            )

            # Check for exact match
            if current_version in available_versions:
                return current_version

            # Try string comparison for similar formats
            for ver_str in available_versions:
                if ver_str == current_version:
                    return ver_str
                # For similar formats, we could add more sophisticated comparison logic here

        return None

    # Step 4: Battery detection for PV inverters
    async def async_step_battery_detection(self, user_input: dict = None) -> FlowResult:
        """Ask if battery is available for PV inverter."""
        _LOGGER.info("=== BATTERY DETECTION STEP CALLED ===")
        _LOGGER.info("User input: %s", user_input)

        if user_input is not None:
            _LOGGER.info("Battery available: %s", user_input.get("battery_available"))
            if user_input.get("battery_available"):
                return await self.async_step_battery_template_selection()
            else:
                # No battery - filter battery registers and proceed to final config
                return await self.async_step_finalize_inverter_without_battery()

        # Get inverter info for display
        inverter_prefix = self._inverter_config.get("prefix", "SG")
        inverter_host = self._inverter_config.get("host", "unknown")

        _LOGGER.info(
            "Showing battery detection form for inverter: %s (%s)",
            inverter_prefix,
            inverter_host,
        )

        return self.async_show_form(
            step_id="battery_detection",
            data_schema=vol.Schema(
                {
                    vol.Required("battery_available", default=False): bool,
                }
            ),
            description_placeholders={
                "inverter_prefix": inverter_prefix,
                "inverter_host": inverter_host,
                "template_name": self._selected_template,
            },
        )

    # Step 5: Battery template selection
    async def async_step_battery_template_selection(
        self, user_input: dict = None
    ) -> FlowResult:
        """Select battery template."""
        if user_input is not None:
            self._selected_battery_template = user_input["battery_template"]
            return await self.async_step_battery_config()

        # Get available battery templates
        battery_templates = {}
        template_names = await get_template_names()

        for template_name in template_names:
            template_data = await get_template_by_name(template_name)
            if template_data and isinstance(template_data, dict):
                template_type = template_data.get("type", "")
                if template_type == "battery":
                    display_name = template_data.get("display_name", template_name)
                    battery_templates[template_name] = display_name

        if not battery_templates:
            # No battery templates available - proceed without battery
            return await self.async_step_finalize_inverter_without_battery()

        return self.async_show_form(
            step_id="battery_template_selection",
            data_schema=vol.Schema(
                {
                    vol.Required("battery_template"): vol.In(battery_templates),
                }
            ),
            description_placeholders={
                "inverter_prefix": self._inverter_config.get("prefix", "SG"),
                "available_templates": ", ".join(battery_templates.values()),
            },
        )

    # Step 6: Battery configuration
    async def async_step_battery_config(self, user_input: dict = None) -> FlowResult:
        """Configure battery settings."""
        if user_input is not None:
            # Store battery config and proceed directly to finalization
            self._battery_config = user_input

            # Extract module count from selected model if available
            battery_template_data = await get_template_by_name(
                self._selected_battery_template
            )
            if battery_template_data and battery_template_data.get(
                "dynamic_config", {}
            ).get("valid_models"):
                selected_model = user_input.get("battery_model")
                if selected_model:
                    valid_models = battery_template_data["dynamic_config"][
                        "valid_models"
                    ]
                    if selected_model in valid_models:
                        modules = valid_models[selected_model].get("modules", 1)
                        self._battery_config["battery_modules"] = modules
                        _LOGGER.info(
                            "Selected battery model %s has %d modules",
                            selected_model,
                            modules,
                        )

            _LOGGER.info("Battery config completed - proceeding to finalization")
            return await self.async_step_finalize_inverter_with_battery()

        # Get battery template data for defaults and model selection
        battery_template_data = await get_template_by_name(
            self._selected_battery_template
        )
        default_slave_id = 200  # Standard battery slave ID
        default_prefix = "SBR"  # Default battery prefix

        if battery_template_data and isinstance(battery_template_data, dict):
            default_slave_id = battery_template_data.get("default_slave_id", 200)
            default_prefix = battery_template_data.get("default_prefix", "SBR")

        _LOGGER.info(
            "Battery template defaults - prefix: %s, slave_id: %d",
            default_prefix,
            default_slave_id,
        )

        # Build schema based on battery template
        schema_fields = {
            vol.Required("battery_prefix", default=default_prefix): str,
            vol.Required("battery_slave_id", default=default_slave_id): int,
        }

        # Add model selection if battery template has valid_models
        if battery_template_data and battery_template_data.get(
            "dynamic_config", {}
        ).get("valid_models"):
            valid_models = battery_template_data["dynamic_config"]["valid_models"]
            model_options = list(valid_models.keys())
            model_labels = {
                model: f"{model} ({valid_models[model].get('modules', 'Unknown')} Modules)"
                for model in model_options
            }

            schema_fields[
                vol.Required("battery_model", default=model_options[0])
            ] = vol.In(model_options)

            _LOGGER.info("Battery template has valid_models: %s", model_options)
        else:
            # Fallback to simple module count if no valid_models
            schema_fields[vol.Optional("battery_modules", default=1)] = int
            _LOGGER.info(
                "Battery template has no valid_models - using simple module count"
            )

        # Get inverter prefix for display
        inverter_prefix = self._inverter_config.get("prefix", "SG")

        return self.async_show_form(
            step_id="battery_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "inverter_prefix": inverter_prefix,
                "battery_template": self._selected_battery_template,
            },
        )

    # Step 7: Finalize inverter without battery
    async def async_step_finalize_inverter_without_battery(self) -> FlowResult:
        """Create inverter entry without battery, filtering out battery registers."""
        try:
            # Filter battery registers from inverter template
            filtered_config = self._filter_battery_registers_from_inverter()
            return await self.async_step_final_config(filtered_config)
        except Exception as e:
            _LOGGER.error("Error finalizing inverter without battery: %s", str(e))
            return self.async_abort(
                reason="finalization_error", description_placeholders={"error": str(e)}
            )

    # Step 8: Finalize inverter with battery
    async def async_step_finalize_inverter_with_battery(self) -> FlowResult:
        """Create both inverter and battery entries."""
        try:
            # First filter battery registers from inverter (updates self._inverter_config)
            filtered_inverter_config = self._filter_battery_registers_from_inverter()

            # Then create the devices array structure with both inverter and battery
            # This updates self._inverter_config with the devices array
            await self._create_battery_subentry()

            # Now create the config entry using self._inverter_config which has the devices array
            inverter_result = await self.async_step_final_config(
                self._inverter_config  # Use self._inverter_config which has devices array!
            )

            return inverter_result
        except Exception as e:
            _LOGGER.error("Error finalizing inverter with battery: %s", str(e))
            return self.async_abort(
                reason="finalization_error", description_placeholders={"error": str(e)}
            )

    def _filter_battery_registers_from_inverter(self) -> dict:
        """Filter battery-related registers from inverter config based on template groups."""
        try:
            # Get the inverter template data
            inverter_template_data = self._templates.get(self._selected_template, {})

            # Create a filtered config
            filtered_config = self._inverter_config.copy()

            # Define battery-specific groups that should be filtered out
            battery_groups = [
                "PV_battery_temperature",
                "PV_battery_control",
                "calculated_battery",
                "battery",
            ]

            _LOGGER.info(
                "Filtering battery groups from inverter template: %s",
                self._selected_template,
            )
            _LOGGER.info("Battery groups to filter: %s", battery_groups)

            # Filter sensors based on groups
            if "sensors" in inverter_template_data:
                original_count = len(inverter_template_data["sensors"])
                inverter_template_data["sensors"] = [
                    sensor
                    for sensor in inverter_template_data["sensors"]
                    if not self._is_battery_group_sensor(sensor, battery_groups)
                ]
                filtered_count = original_count - len(inverter_template_data["sensors"])
                _LOGGER.info(
                    "Filtered %d battery sensors from inverter template", filtered_count
                )

            # Filter calculated sensors based on groups
            if "calculated" in inverter_template_data:
                original_count = len(inverter_template_data["calculated"])
                inverter_template_data["calculated"] = [
                    calc
                    for calc in inverter_template_data["calculated"]
                    if not self._is_battery_group_sensor(calc, battery_groups)
                ]
                filtered_count = original_count - len(
                    inverter_template_data["calculated"]
                )
                _LOGGER.info(
                    "Filtered %d battery calculated sensors from inverter template",
                    filtered_count,
                )

            # Filter binary sensors based on groups
            if "binary_sensors" in inverter_template_data:
                original_count = len(inverter_template_data["binary_sensors"])
                inverter_template_data["binary_sensors"] = [
                    binary
                    for binary in inverter_template_data["binary_sensors"]
                    if not self._is_battery_group_sensor(binary, battery_groups)
                ]
                filtered_count = original_count - len(
                    inverter_template_data["binary_sensors"]
                )
                _LOGGER.info(
                    "Filtered %d battery binary sensors from inverter template",
                    filtered_count,
                )

            _LOGGER.info(
                "Battery group filtering completed for template: %s",
                self._selected_template,
            )
            return filtered_config

        except Exception as e:
            _LOGGER.error("Error filtering battery registers: %s", str(e))
            return self._inverter_config

    def _is_battery_group_sensor(self, sensor: dict, battery_groups: list) -> bool:
        """Check if a sensor belongs to a battery-specific group."""
        try:
            sensor_group = sensor.get("group", "")
            if sensor_group in battery_groups:
                _LOGGER.debug(
                    "Filtering sensor '%s' - belongs to battery group '%s'",
                    sensor.get("name", "unknown"),
                    sensor_group,
                )
                return True
            return False
        except Exception as e:
            _LOGGER.error("Error checking sensor group: %s", str(e))
            return False

    def _filter_battery_template_by_modules(
        self, template_data: dict, module_count: int
    ) -> dict:
        """Filter battery template to only include sensors for the selected number of modules."""
        try:
            _LOGGER.info("Filtering battery template for %d modules", module_count)

            # Create a copy of the template data
            filtered_template = template_data.copy()

            # Filter sensors based on module count
            if "sensors" in filtered_template:
                original_count = len(filtered_template["sensors"])
                filtered_template["sensors"] = [
                    sensor
                    for sensor in filtered_template["sensors"]
                    if self._is_sensor_for_selected_modules(sensor, module_count)
                ]
                filtered_count = original_count - len(filtered_template["sensors"])
                _LOGGER.info(
                    "Filtered %d sensors for %d modules (kept %d)",
                    filtered_count,
                    module_count,
                    len(filtered_template["sensors"]),
                )

            # Filter calculated sensors
            if "calculated" in filtered_template:
                original_count = len(filtered_template["calculated"])
                filtered_template["calculated"] = [
                    calc
                    for calc in filtered_template["calculated"]
                    if self._is_sensor_for_selected_modules(calc, module_count)
                ]
                filtered_count = original_count - len(filtered_template["calculated"])
                _LOGGER.info(
                    "Filtered %d calculated sensors for %d modules (kept %d)",
                    filtered_count,
                    module_count,
                    len(filtered_template["calculated"]),
                )

            # Filter binary sensors
            if "binary_sensors" in filtered_template:
                original_count = len(filtered_template["binary_sensors"])
                filtered_template["binary_sensors"] = [
                    binary
                    for binary in filtered_template["binary_sensors"]
                    if self._is_sensor_for_selected_modules(binary, module_count)
                ]
                filtered_count = original_count - len(
                    filtered_template["binary_sensors"]
                )
                _LOGGER.info(
                    "Filtered %d binary sensors for %d modules (kept %d)",
                    filtered_count,
                    module_count,
                    len(filtered_template["binary_sensors"]),
                )

            _LOGGER.info(
                "Battery template filtering completed for %d modules", module_count
            )
            return filtered_template

        except Exception as e:
            _LOGGER.error("Error filtering battery template by modules: %s", str(e))
            return template_data

    def _is_sensor_for_selected_modules(self, sensor: dict, module_count: int) -> bool:
        """Check if a sensor should be included for the selected module count."""
        try:
            # Get sensor name and unique_id
            sensor_name = sensor.get("name", "").lower()
            sensor_unique_id = sensor.get("unique_id", "").lower()

            # Check if sensor is module-specific by name/unique_id
            for module_num in range(1, 9):  # Check modules 1-8
                if module_num > module_count:
                    # This module is beyond our selected count
                    if (
                        f"module_{module_num}" in sensor_name
                        or f"module_{module_num}" in sensor_unique_id
                        or f"module {module_num}" in sensor_name
                    ):
                        _LOGGER.debug(
                            "Filtering out sensor '%s' - module %d > %d",
                            sensor.get("name", "unknown"),
                            module_num,
                            module_count,
                        )
                        return False

            # Check for module-specific patterns in register ranges
            register = sensor.get("register")
            if register is not None:
                # Define module-specific register ranges (these are Sungrow SBR specific)
                module_register_ranges = {
                    1: (10756, 10763),  # Module 1
                    2: (10764, 10771),  # Module 2
                    3: (10772, 10779),  # Module 3
                    4: (10780, 10787),  # Module 4
                    5: (10788, 10788),  # Module 5
                    6: (10821, 10829),  # Module 6
                    7: (10830, 10838),  # Module 7
                    8: (10839, 10847),  # Module 8
                }

                for module_num, (start, end) in module_register_ranges.items():
                    if module_num > module_count and start <= register <= end:
                        _LOGGER.debug(
                            "Filtering out sensor '%s' - register %d in module %d range",
                            sensor.get("name", "unknown"),
                            register,
                            module_num,
                        )
                        return False

            return True

        except Exception as e:
            _LOGGER.error("Error checking sensor for selected modules: %s", str(e))
            return True  # Keep sensor if there's an error

    async def _create_battery_subentry(self):
        """Create devices array structure with inverter and battery configurations."""
        try:
            # Get battery template data
            battery_template_data = await get_template_by_name(
                self._selected_battery_template
            )

            # Store module count for runtime filtering
            module_count = self._battery_config.get("battery_modules", 5)
            _LOGGER.info("Battery will be configured for %d modules", module_count)

            # Create devices array structure
            devices = []

            # Get inverter template data for version info
            inverter_template_data = await get_template_by_name(self._selected_template)

            # Add inverter device
            inverter_device = {
                "type": "inverter",
                "template": self._selected_template,  # Use the selected template
                "prefix": self._inverter_config.get("prefix"),
                "slave_id": self._inverter_config.get("slave_id"),
                "selected_model": self._inverter_config.get(
                    "selected_model"
                ),  # Store selected valid model
                "template_version": (
                    inverter_template_data.get("version", 1)
                    if inverter_template_data
                    else 1
                ),
                "firmware_version": (
                    inverter_template_data.get("firmware_version", "1.0.0")
                    if inverter_template_data
                    else "1.0.0"
                ),
            }

            # Add battery device
            battery_device = {
                "type": "battery",
                "template": self._selected_battery_template,
                "prefix": self._battery_config.get("battery_prefix"),
                "slave_id": self._battery_config.get("battery_slave_id"),
                "selected_model": self._battery_config.get(
                    "battery_model"
                ),  # Store selected valid model
                "template_version": (
                    battery_template_data.get("version", 1)
                    if battery_template_data
                    else 1
                ),
                "firmware_version": (
                    battery_template_data.get("firmware_version", "1.0.0")
                    if battery_template_data
                    else "1.0.0"
                ),
            }

            devices.append(inverter_device)
            devices.append(battery_device)

            # Update config with new structure
            self._inverter_config.update(
                {
                    "hub": {
                        "host": self._inverter_config.get("host"),
                        "port": self._inverter_config.get("port"),
                        "timeout": self._inverter_config.get("timeout"),
                        "delay": self._inverter_config.get("delay"),
                    },
                    "devices": devices,
                    # Keep legacy fields for backward compatibility during transition
                    "battery_template": self._selected_battery_template,
                    "battery_prefix": self._battery_config.get("battery_prefix"),
                    "battery_slave_id": self._battery_config.get("battery_slave_id"),
                    "battery_modules": module_count,
                }
            )

            # Add battery template metadata
            if battery_template_data and isinstance(battery_template_data, dict):
                self._inverter_config.update(
                    {
                        "battery_template_version": battery_template_data.get(
                            "version", 1
                        ),
                        "battery_template_last_updated": battery_template_data.get(
                            "last_updated", 0
                        ),
                    }
                )

            # Add battery dynamic config if available
            if self._battery_config.get("battery_model"):
                self._inverter_config[
                    "battery_selected_model"
                ] = self._battery_config.get("battery_model")

            _LOGGER.info("Devices array structure created:")
            _LOGGER.info(
                "  Inverter: %s (prefix: %s, slave_id: %s, model: %s, fw: %s)",
                inverter_device["template"],
                inverter_device["prefix"],
                inverter_device["slave_id"],
                inverter_device["selected_model"],
                inverter_device["firmware_version"],
            )
            _LOGGER.info(
                "  Battery: %s (prefix: %s, slave_id: %s, model: %s, fw: %s)",
                battery_device["template"],
                battery_device["prefix"],
                battery_device["slave_id"],
                battery_device["selected_model"],
                battery_device["firmware_version"],
            )

            return True

        except Exception as e:
            _LOGGER.error("Error creating devices array structure: %s", str(e))
            raise

    # Final Step to create the config entry
    async def async_step_final_config(self, user_input: dict) -> FlowResult:
        """Handle final configuration and create entry."""
        try:
            # Get template data
            template_data = self._templates[self._selected_template]
            template_version = (
                template_data.get("version", 1)
                if isinstance(template_data, dict)
                else 1
            )

            # Handle regular template
            return self._create_regular_entry(
                user_input, template_data, template_version
            )

        except Exception as e:
            _LOGGER.error("Error creating configuration: %s", str(e))
            return self.async_abort(
                reason="config_error", description_placeholders={"error": str(e)}
            )

    def _create_regular_entry(
        self, user_input: dict, template_data: dict, template_version: int
    ) -> FlowResult:
        """Create config entry for regular template."""
        try:
            # Check if this is a simple template
            if template_data.get("is_simple_template"):
                return self._create_simple_template_entry(
                    user_input, template_data, template_version
                )

            # Process dynamic configuration if supported
            if self._supports_dynamic_config(template_data):
                processed_data = self._process_dynamic_config(user_input, template_data)
                template_registers = processed_data.get("sensors", []) or []
                template_calculated = processed_data.get("calculated", []) or []
                template_binary_sensors = processed_data.get("binary_sensors", []) or []
                template_controls = processed_data.get("controls", []) or []

                # Extract configuration values from processed_data
                config_values = processed_data.get("config_values", {})
                phases = config_values.get("phases", 3)
                mppt_count = config_values.get("mppt_count", 1)
                string_count = config_values.get("string_count", 1)
                modules = config_values.get("modules", 3)
                battery_config = config_values.get("battery_config", "none")
                battery_enabled = config_values.get("battery_enabled", False)
                battery_type = config_values.get("battery_type", "none")
                battery_slave_id = config_values.get("battery_slave_id", 200)
                firmware_version = config_values.get("firmware_version", "1.0.0")
                connection_type = config_values.get("connection_type", "LAN")
                selected_model = config_values.get("selected_model")
                dynamic_config = config_values.get("dynamic_config", {})
            else:
                # Extract registers from template
                template_registers = (
                    template_data.get("sensors", []) or []
                    if isinstance(template_data, dict)
                    else template_data or []
                )

                template_calculated = (
                    template_data.get("calculated", []) or []
                    if isinstance(template_data, dict)
                    else []
                )
                template_binary_sensors = (
                    template_data.get("binary_sensors", []) or []
                    if isinstance(template_data, dict)
                    else []
                )
                template_controls = (
                    template_data.get("controls", []) or []
                    if isinstance(template_data, dict)
                    else []
                )

            _LOGGER.debug(
                "Template %s (Version %s) loaded with %d registers",
                self._selected_template,
                template_version,
                len(template_registers) if template_registers else 0,
            )

            # Validate template data
            if not template_registers:
                _LOGGER.error("Template %s has no registers", self._selected_template)
                return self.async_abort(
                    reason="no_registers",
                    description_placeholders={
                        "error": f"Template {self._selected_template} has no registers"
                    },
                )

            # Validate configuration
            if not self._validate_config(user_input):
                return self.async_abort(
                    reason="invalid_config",
                    description_placeholders={"error": "Invalid configuration"},
                )

            # Get firmware version from user input or template default
            firmware_version = user_input.get(
                "firmware_version", template_data.get("firmware_version", "1.0.0")
            )

            # Check if devices array already exists (from battery subentry creation)
            if "devices" in user_input and user_input["devices"]:
                # Use existing devices array (e.g., from battery subentry)
                devices = user_input["devices"]
                _LOGGER.info(
                    "Using existing devices array with %d devices", len(devices)
                )
            else:
                # Create new devices array for single device
                devices = []

                # Create single device entry
                device = {
                    "type": "inverter",  # Default type for regular templates
                    "template": self._selected_template,
                    "prefix": user_input["prefix"],
                    "slave_id": user_input.get("slave_id", DEFAULT_SLAVE),
                    "selected_model": user_input.get(
                        "selected_model"
                    ),  # Store selected valid model
                    "template_version": template_version,
                    "firmware_version": firmware_version,
                }

                devices.append(device)
                _LOGGER.info("Created new devices array with single device")

            config_data = {
                "hub": {
                    "host": user_input["host"],
                    "port": user_input.get("port", DEFAULT_PORT),
                    "timeout": user_input.get("timeout", DEFAULT_TIMEOUT),
                    "delay": user_input.get("delay", DEFAULT_DELAY),
                },
                "devices": devices,
                # Keep legacy fields for backward compatibility
                "template": self._selected_template,
                "prefix": user_input["prefix"],
                "host": user_input["host"],
                "port": user_input.get("port", DEFAULT_PORT),
                "slave_id": user_input.get("slave_id", DEFAULT_SLAVE),
                "timeout": user_input.get("timeout", DEFAULT_TIMEOUT),
                "delay": user_input.get("delay", DEFAULT_DELAY),
                "template_version": template_version,
                "firmware_version": firmware_version,
                "registers": template_registers,
                "calculated_entities": template_calculated,
                "binary_sensors": template_binary_sensors,
                "controls": template_controls,
            }

            # Add dynamic configuration parameters if available
            # Configuration values are already extracted from processed_data above
            if self._supports_dynamic_config(template_data):
                _LOGGER.info("Using configuration values from processed_data")
                config_data.update(
                    {
                        "phases": phases,
                        "mppt_count": mppt_count,
                        "string_count": string_count,
                        "modules": modules,
                        "battery_config": battery_config,
                        "battery_enabled": battery_enabled,
                        "battery_type": battery_type,
                        "battery_slave_id": battery_slave_id,
                        "firmware_version": firmware_version,
                        "connection_type": connection_type,
                        "selected_model": selected_model,
                    }
                )

            # Create title based on host:port for grouping (like Philips Hue)
            host = config_data.get("host", "unknown")
            port = config_data.get("port", 502)
            title = f"Modbus Hub ({host}:{port})"

            # Check if there's already a config entry with the same host:port
            # If so, we need to extend it instead of creating a new one
            existing_entry = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if (
                    entry.data.get("host") == host
                    and entry.data.get("port", 502) == port
                ):
                    existing_entry = entry
                    break

            if existing_entry:
                # Extend existing entry with new device
                _LOGGER.info(
                    "Extending existing hub %s:%s with new device (slave_id: %s)",
                    host,
                    port,
                    config_data.get("slave_id", 1),
                )

                # Get existing devices
                existing_devices = existing_entry.data.get("devices", [])

                # Add new device
                # Determine device type from template
                template_type = template_data.get("type", "inverter")
                device_type = template_type if template_type else "inverter"

                new_device = {
                    "type": device_type,
                    "prefix": config_data["prefix"],
                    "template": config_data["template"],
                    "slave_id": config_data.get("slave_id", 1),
                    "template_version": config_data.get("template_version"),
                    "firmware_version": config_data.get("firmware_version"),
                    "selected_model": config_data.get("selected_model"),
                    "registers": config_data.get("registers", []),
                    "calculated_entities": config_data.get("calculated_entities", []),
                    "controls": config_data.get("controls", []),
                    "binary_sensors": config_data.get("binary_sensors", []),
                }

                # Check if device with same slave_id already exists
                device_exists = False
                for i, device in enumerate(existing_devices):
                    if device.get("slave_id") == new_device["slave_id"]:
                        # Update existing device
                        existing_devices[i] = new_device
                        device_exists = True
                        _LOGGER.info(
                            "Updated existing device with slave_id %s",
                            new_device["slave_id"],
                        )
                        break

                if not device_exists:
                    existing_devices.append(new_device)
                    _LOGGER.info(
                        "Added new device with slave_id %s", new_device["slave_id"]
                    )

                # Update config entry
                new_data = dict(existing_entry.data)
                new_data["devices"] = existing_devices

                _LOGGER.info(
                    "🔍 Updating config entry with %d devices", len(existing_devices)
                )
                for i, device in enumerate(existing_devices):
                    _LOGGER.info(
                        "🔍 Device %d: prefix=%s, template=%s, slave_id=%s, registers=%d",
                        i,
                        device.get("prefix", "unknown"),
                        device.get("template", "unknown"),
                        device.get("slave_id", "unknown"),
                        len(device.get("registers", [])),
                    )

                # Update config entry
                self.hass.config_entries.async_update_entry(
                    existing_entry, data=new_data
                )

                _LOGGER.info(
                    "✅ Config entry updated successfully with %d devices",
                    len(existing_devices),
                )

                # FIX: Reload the integration AFTER updating the config entry
                # This ensures the new device is loaded immediately
                _LOGGER.info("🔄 Reloading integration to load new device")
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(existing_entry.entry_id)
                )

                # No restart required - integration is reloaded automatically
                _LOGGER.info("✅ New device loaded successfully - no restart required")

                return self.async_abort(reason="device_added_to_existing_hub")
            else:
                # Only create legacy devices array if one doesn't already exist
                # (Battery workflow creates devices array with 2 devices)
                if "devices" not in config_data or not config_data["devices"]:
                    _LOGGER.info(
                        "Creating legacy devices array for single device (no battery)"
                    )
                    config_data["devices"] = [
                        {
                            "prefix": config_data["prefix"],
                            "template": config_data["template"],
                            "slave_id": config_data.get("slave_id", 1),
                            "registers": config_data.get("registers", []),
                            "calculated_entities": config_data.get(
                                "calculated_entities", []
                            ),
                            "controls": config_data.get("controls", []),
                            "binary_sensors": config_data.get("binary_sensors", []),
                        }
                    ]
                else:
                    _LOGGER.info(
                        "Using existing devices array with %d devices from battery workflow",
                        len(config_data["devices"]),
                    )

                return self.async_create_entry(
                    title=title,
                    data=config_data,
                )

        except Exception as e:
            _LOGGER.error("Error creating regular configuration: %s", str(e))
            return self.async_abort(
                reason="regular_config_error",
                description_placeholders={"error": str(e)},
            )

    def _create_simple_template_entry(
        self, user_input: dict, template_data: dict, template_version: int
    ) -> FlowResult:
        """Create config entry for simple template."""
        try:
            _LOGGER.debug("Creating simple template entry: %s", self._selected_template)

            # Validate simple template input
            if not self._validate_simple_config(user_input):
                return self.async_abort(
                    reason="invalid_simple_config",
                    description_placeholders={
                        "error": "Invalid configuration for simple template"
                    },
                )

            # Create title based on host:port for grouping (like Philips Hue)
            host = self._connection_data.get("host", "unknown")
            port = self._connection_data.get("port", 502)
            title = f"Modbus Hub ({host}:{port})"

            # Create config entry for simple template
            return self.async_create_entry(
                title=title,
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "name": user_input.get("name", user_input["prefix"]),
                    "template_data": template_data,
                    "is_simple_template": True,
                },
            )

        except Exception as e:
            _LOGGER.error("Error creating simple template configuration: %s", str(e))
            return self.async_abort(
                reason="simple_config_error", description_placeholders={"error": str(e)}
            )

    def _validate_simple_config(self, user_input: dict) -> bool:
        """Validate simple template configuration."""
        try:
            # Check required fields
            required_fields = ["prefix"]
            if not all(field in user_input for field in required_fields):
                return False

            # Prefix validieren (alphanumeric, lowercase, underscore)
            prefix = user_input.get("prefix", "")
            if (
                not prefix
                or not prefix.replace("_", "").isalnum()
                or not prefix.islower()
            ):
                return False

            return True

        except Exception as e:
            _LOGGER.error("Error validating simplified configuration: %s", str(e))
            return False

    def _validate_config(self, user_input: dict) -> bool:
        """Validate user input configuration."""
        try:
            # Check required fields
            required_fields = ["prefix", "host"]
            if not all(field in user_input for field in required_fields):
                return False

            # Port validieren
            port = user_input.get("port", 502)
            if not isinstance(port, int) or port < 1 or port > 65535:
                return False

            # Slave ID validieren
            slave_id = user_input.get("slave_id", 1)
            if not isinstance(slave_id, int) or slave_id < 1 or slave_id > 255:
                return False

            # Timeout validieren
            timeout = user_input.get("timeout", 1)
            if not isinstance(timeout, int) or timeout < 1:
                return False

            # Delay validieren
            delay = user_input.get("delay", 0)
            if not isinstance(delay, int) or delay < 0:
                return False

            return True

        except Exception:
            return False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ModbusManagerOptionsFlow()


class ModbusManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Manager."""

    async def async_step_init(self, user_input: dict = None) -> FlowResult:
        """Manage the options."""

        if user_input is not None:
            if "update_template" in user_input and user_input["update_template"]:
                return await self.async_step_update_template()
            elif "firmware_version" in user_input:
                # Update firmware version
                return await self.async_step_firmware_update(user_input)
            # Battery configuration is now simplified - no separate SBR battery step needed
            else:
                # Update settings and apply dynamic configuration changes
                return await self.async_step_apply_config_changes(user_input)

        # Prepare template information for display
        template_name = self.config_entry.data.get("template", "Unknown")
        template_version = self.config_entry.data.get("template_version", 1)
        template_last_updated = self.config_entry.data.get("template_last_updated", 0)

        # Format timestamp for last update
        if template_last_updated > 0:
            import datetime

            last_updated_str = datetime.datetime.fromtimestamp(
                template_last_updated
            ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_updated_str = "Never"

        # Entity counts for display
        current_sensors_count = len(self.config_entry.data.get("registers", []))
        current_calculated_count = len(
            self.config_entry.data.get("calculated_entities", [])
        )
        current_controls_count = len(self.config_entry.data.get("controls", []))

        # Load template
        template_data = await get_template_by_name(template_name)

        # Build schema fields

        # Basic configuration fields
        schema_fields = {
            vol.Optional(
                "timeout",
                default=self.config_entry.data.get("timeout", DEFAULT_TIMEOUT),
            ): int,
            vol.Optional(
                "delay", default=self.config_entry.data.get("delay", DEFAULT_DELAY)
            ): int,
            vol.Optional(
                "message_wait_milliseconds",
                default=self.config_entry.data.get(
                    "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                ),
            ): int,
            vol.Optional("update_template"): bool,
        }

        # Add dynamic configuration options if template supports it
        if (
            template_data
            and isinstance(template_data, dict)
            and template_data.get("dynamic_config")
        ):
            dynamic_config = template_data.get("dynamic_config", {})

            # Add phases selection
            if "phases" in dynamic_config:
                current_phases = self.config_entry.data.get("phases", 3)
                phase_options = dynamic_config["phases"].get("options", [1, 3])

                schema_fields[vol.Optional("phases", default=current_phases)] = vol.In(
                    phase_options
                )

            # Add MPPT count selection
            if "mppt_count" in dynamic_config:
                current_mppt = self.config_entry.data.get("mppt_count", 2)
                mppt_options = dynamic_config["mppt_count"].get("options", [1, 2, 3])

                schema_fields[
                    vol.Optional("mppt_count", default=current_mppt)
                ] = vol.In(mppt_options)

            # Add battery configuration
            if "battery_config" in dynamic_config:
                current_battery = self.config_entry.data.get("battery_config", "none")
                battery_options = dynamic_config["battery_config"].get(
                    "options", ["none", "standard_battery", "sbr_battery"]
                )
                option_labels = dynamic_config["battery_config"].get(
                    "option_labels", {}
                )

                battery_choices = {}
                for option in battery_options:
                    display_label = option_labels.get(
                        option, option.replace("_", " ").title()
                    )
                    battery_choices[option] = display_label

                schema_fields[
                    vol.Optional("battery_config", default=current_battery)
                ] = vol.In(battery_choices)

            # Add connection type
            if "connection_type" in dynamic_config:
                current_connection = self.config_entry.data.get(
                    "connection_type", "LAN"
                )
                connection_options = dynamic_config["connection_type"].get(
                    "options", ["LAN", "WINET"]
                )
                schema_fields[
                    vol.Optional("connection_type", default=current_connection)
                ] = vol.In(connection_options)

            # Add firmware version if available in dynamic_config
            if "firmware_version" in dynamic_config:
                current_firmware = self.config_entry.data.get(
                    "firmware_version", "1.0.0"
                )
                firmware_options = dynamic_config["firmware_version"].get(
                    "options", ["1.0.0"]
                )
                schema_fields[
                    vol.Optional("firmware_version", default=current_firmware)
                ] = vol.In(firmware_options)

        # Basic options form
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "template_name": template_name,
                "template_version": str(template_version),
                "last_updated": last_updated_str,
                "current_sensors": str(current_sensors_count),
                "current_calculated": str(current_calculated_count),
                "current_controls": str(current_controls_count),
            },
        )

    async def async_step_update_template(self, user_input: dict = None) -> FlowResult:
        """Update the template to the latest version or reload for changes."""
        try:
            # Get current template information
            template_name = self.config_entry.data.get("template", "Unknown")
            stored_version = self.config_entry.data.get("template_version", 1)

            # Load new template
            template_data = await get_template_by_name(template_name)
            if not template_data:
                return self.async_abort(
                    reason="template_not_found",
                    description_placeholders={"template_name": template_name},
                )

            # Debug: Check template data type
            _LOGGER.debug("Template data type: %s", type(template_data))
            if isinstance(template_data, str):
                _LOGGER.error(
                    "Template data is string, expected dict: %s", template_data[:100]
                )
                return self.async_abort(
                    reason="template_format_error",
                    description_placeholders={"template_name": template_name},
                )

            # Extract template version and registers
            if isinstance(template_data, dict):
                current_version = template_data.get("version", 1)
                original_sensors = template_data.get("sensors", [])
                original_calculated = template_data.get("calculated", [])
                original_controls = template_data.get("controls", [])
                original_binary_sensors = template_data.get("binary_sensors", [])
                dynamic_config = template_data.get("dynamic_config", {})
            else:
                current_version = 1
                original_sensors = template_data
                original_calculated = []
                original_controls = []
                original_binary_sensors = []
                dynamic_config = {}

            if not original_sensors:
                return self.async_abort(
                    reason="no_registers",
                    description_placeholders={"template_name": template_name},
                )

            # Apply dynamic configuration (important for MPPT filtering!)
            if dynamic_config:
                try:
                    # Use current configuration from config entry
                    current_phases = self.config_entry.data.get("phases", 1)
                    current_mppt_count = self.config_entry.data.get("mppt_count", 2)
                    current_string_count = self.config_entry.data.get("string_count", 0)
                    current_battery_config = self.config_entry.data.get(
                        "battery_config", "none"
                    )
                    current_battery_slave_id = self.config_entry.data.get(
                        "battery_slave_id", 200
                    )
                    current_firmware_version = self.config_entry.data.get(
                        "firmware_version", "1.0.0"
                    )
                    current_connection_type = self.config_entry.data.get(
                        "connection_type", "LAN"
                    )

                    _LOGGER.info(
                        "Applying dynamic config during template update: phases=%d, mppt=%d, strings=%d, battery=%s, fw=%s",
                        current_phases,
                        current_mppt_count,
                        current_string_count,
                        current_battery_config,
                        current_firmware_version,
                    )

                    # Process template with current configuration
                    # Use the same logic as in _process_dynamic_config
                    processed_data = self._process_dynamic_config(
                        {
                            "phases": current_phases,
                            "mppt_count": current_mppt_count,
                            "string_count": current_string_count,
                            "battery_config": current_battery_config,
                            "battery_slave_id": current_battery_slave_id,
                            "firmware_version": current_firmware_version,
                            "connection_type": current_connection_type,
                        },
                        template_data,
                    )

                    template_registers = processed_data["sensors"]
                    calculated_entities = processed_data["calculated"]
                    template_controls = processed_data["controls"]
                    template_binary_sensors = processed_data.get("binary_sensors", [])

                    _LOGGER.info(
                        "Template processing completed: %d sensors, %d calculated, %d controls, %d binary_sensors",
                        len(template_registers),
                        len(calculated_entities),
                        len(template_controls),
                        len(template_binary_sensors),
                    )

                except Exception as e:
                    _LOGGER.warning(
                        "Error applying dynamic config during template update, using original: %s",
                        str(e),
                    )
                    # Fallback: Use original template without dynamic filtering
                    template_registers = original_sensors
                    calculated_entities = original_calculated
                    template_controls = original_controls
                    template_binary_sensors = original_binary_sensors
            else:
                # No dynamic configuration - use original
                template_registers = original_sensors
                calculated_entities = original_calculated
                template_controls = original_controls
                template_binary_sensors = original_binary_sensors

            if user_input is not None:
                # Update template
                new_data = dict(self.config_entry.data)
                new_data["template_version"] = current_version

                # Only update registers if they exist
                if template_registers:
                    new_data["registers"] = template_registers
                    _LOGGER.info(
                        "Updated registers: %d sensors", len(template_registers)
                    )
                else:
                    _LOGGER.warning(
                        "No template_registers found, keeping existing registers"
                    )
                    # Fallback: Try to load directly from template_data
                    if isinstance(template_data, dict) and template_data.get("sensors"):
                        new_data["registers"] = template_data["sensors"]
                        _LOGGER.info(
                            "Used fallback: loaded %d sensors directly from template",
                            len(template_data["sensors"]),
                        )

                # Update calculated entities if the new template has them
                if calculated_entities:
                    new_data["calculated_entities"] = calculated_entities

                # Update controls if the new template has them
                if template_controls:
                    new_data["controls"] = template_controls

                # Update binary sensors if present
                if template_binary_sensors:
                    new_data["binary_sensors"] = template_binary_sensors

                # Add template update timestamp
                import time

                new_data["template_last_updated"] = int(time.time())

                # Update config entry
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                _LOGGER.info(
                    "Template %s updated: v%s → v%s (%d sensors, %d calculated, %d controls, %d binary_sensors)",
                    template_name,
                    stored_version,
                    current_version,
                    len(template_registers),
                    len(calculated_entities),
                    len(template_controls),
                    len(template_binary_sensors),
                )

                # Reload integration to apply changes
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                # Return to main view
                return self.async_create_entry(title="", data={})

            # Show confirmation dialog
            # Check if anything has changed
            current_sensors_count = len(template_registers)
            current_calculated_count = len(calculated_entities)
            current_controls_count = len(template_controls)

            stored_sensors_count = len(self.config_entry.data.get("registers", []))
            stored_calculated_count = len(
                self.config_entry.data.get("calculated_entities", [])
            )
            stored_controls_count = len(self.config_entry.data.get("controls", []))

            version_changed = current_version != stored_version
            content_changed = (
                current_sensors_count != stored_sensors_count
                or current_calculated_count != stored_calculated_count
                or current_controls_count != stored_controls_count
            )

            return self.async_show_form(
                step_id="update_template",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "template_name": template_name,
                    "stored_version": str(stored_version),
                    "current_version": str(current_version),
                    "version_changed": "Ja" if version_changed else "Nein",
                    "content_changed": "Ja" if content_changed else "Nein",
                    "current_sensors": str(current_sensors_count),
                    "current_calculated": str(current_calculated_count),
                    "current_controls": str(current_controls_count),
                },
            )

        except Exception as e:
            _LOGGER.error("Error updating template: %s", str(e))
            return self.async_abort(
                reason="update_error", description_placeholders={"error": str(e)}
            )

    async def async_step_firmware_update(self, user_input: dict = None) -> FlowResult:
        """Update firmware version and reapply filtering."""
        try:
            template_name = self.config_entry.data.get("template", "Unknown")
            new_firmware_version = user_input.get("firmware_version", "1.0.0")
            current_firmware_version = self.config_entry.data.get(
                "firmware_version", "1.0.0"
            )

            _LOGGER.debug(
                "Firmware update: %s -> %s",
                current_firmware_version,
                new_firmware_version,
            )

            if new_firmware_version == current_firmware_version:
                _LOGGER.debug("Firmware version unchanged, no update needed")
                return self.async_create_entry(title="", data={})

            # Load template data
            template_data = await get_template_by_name(template_name)
            if not template_data:
                return self.async_abort(
                    reason="template_not_found",
                    description_placeholders={"template_name": template_name},
                )

            # Get all entities from template
            if isinstance(template_data, dict):
                all_sensors = template_data.get("sensors", [])
                all_calculated = template_data.get("calculated", [])
                all_controls = template_data.get("controls", [])
            else:
                all_sensors = template_data
                all_calculated = []
                all_controls = []

            # Apply firmware filtering
            from .coordinator import filter_by_firmware_version

            filtered_sensors = filter_by_firmware_version(
                all_sensors, new_firmware_version
            )
            filtered_calculated = filter_by_firmware_version(
                all_calculated, new_firmware_version
            )
            filtered_controls = filter_by_firmware_version(
                all_controls, new_firmware_version
            )

            _LOGGER.info(
                "Firmware filtering applied: %d sensors, %d calculated, %d controls (from %d, %d, %d)",
                len(filtered_sensors),
                len(filtered_calculated),
                len(filtered_controls),
                len(all_sensors),
                len(all_calculated),
                len(all_controls),
            )

            # Update config entry
            new_data = dict(self.config_entry.data)
            new_data["firmware_version"] = new_firmware_version
            new_data["registers"] = filtered_sensors
            new_data["calculated_entities"] = filtered_calculated
            new_data["controls"] = filtered_controls

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            _LOGGER.info(
                "Firmware version updated to %s, entities filtered accordingly",
                new_firmware_version,
            )

            # Reload the integration to update DeviceInfo with new firmware version
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        except Exception as e:
            _LOGGER.error("Fehler beim Aktualisieren der Firmware-Version: %s", str(e))
            return self.async_abort(
                reason="firmware_update_error",
                description_placeholders={"error": str(e)},
            )

    async def async_step_battery_config(self, user_input: dict = None) -> FlowResult:
        """Handle battery configuration step for SBR battery."""
        if user_input is not None and "battery_slave_id" in user_input:
            # Combine with previous input and apply changes
            combined_input = dict(user_input)
            # Get the previous user input from the flow
            if hasattr(self, "_temp_user_input"):
                combined_input.update(self._temp_user_input)
            return await self.async_step_apply_config_changes(combined_input)

        # Store the current user input temporarily
        self._temp_user_input = user_input

        # Show battery slave ID configuration
        current_battery_slave_id = self.config_entry.data.get("battery_slave_id", 200)

        return self.async_show_form(
            step_id="battery_config",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "battery_slave_id", default=current_battery_slave_id
                    ): int,
                }
            ),
            description_placeholders={"battery_config": "SBR Battery"},
        )

    async def async_step_apply_config_changes(self, user_input: dict) -> FlowResult:
        """Apply configuration changes and reload integration if needed."""
        try:
            # Check if dynamic configuration has changed
            dynamic_config_changed = False
            config_changes = {}

            # Check each dynamic config parameter
            dynamic_params = [
                "phases",
                "mppt_count",
                "battery_config",
                "battery_slave_id",
                "connection_type",
            ]
            for param in dynamic_params:
                if param in user_input:
                    old_value = self.config_entry.data.get(param)
                    new_value = user_input[param]
                    if old_value != new_value:
                        dynamic_config_changed = True
                        config_changes[param] = {"old": old_value, "new": new_value}

            # Update config entry
            new_data = dict(self.config_entry.data)
            new_data.update(user_input)

            # Remove temporary fields
            new_data.pop("update_template", None)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            _LOGGER.info("Configuration updated: %s", config_changes)

            # If dynamic configuration changed, reload the integration
            if dynamic_config_changed:
                _LOGGER.info("Dynamic configuration changed, reloading integration")
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        except Exception as e:
            _LOGGER.error("Error applying configuration changes: %s", str(e))
            return self.async_abort(
                reason="config_apply_error", description_placeholders={"error": str(e)}
            )

    def _process_dynamic_config(self, user_input: dict, template_data: dict) -> dict:
        """Process template based on dynamic configuration parameters."""

        _LOGGER.debug(
            "_process_dynamic_config user_input keys: %s", list(user_input.keys())
        )

        original_sensors = template_data.get("sensors", [])
        original_calculated = template_data.get("calculated", [])
        original_controls = template_data.get("controls", [])
        dynamic_config = template_data.get("dynamic_config", {})

        processed_sensors = []
        processed_calculated = []
        processed_controls = []

        # Check if model-specific config is used
        selected_model = user_input.get("selected_model")
        if selected_model:
            # Get configuration from selected model
            # Look for valid_models in dynamic_config first, then at template root level
            valid_models = dynamic_config.get("valid_models") or template_data.get(
                "valid_models", {}
            )

            # Get model configuration directly from valid_models
            model_config = (
                valid_models.get(selected_model)
                if valid_models and isinstance(valid_models, dict)
                else None
            )
            if model_config:
                # Generic model configuration - extract all fields dynamically
                config_values = {}
                for field_name, field_value in model_config.items():
                    config_values[field_name] = field_value

                # Set defaults for common fields if not present
                phases = config_values.get("phases", 3)
                mppt_count = config_values.get("mppt_count", 1)
                string_count = config_values.get("string_count", 1)
                modules = config_values.get("modules", 3)

                # Log all configuration values
                config_str = ", ".join([f"{k}={v}" for k, v in config_values.items()])
                _LOGGER.info(
                    "Using model-specific config for %s: %s",
                    selected_model,
                    config_str,
                )
            else:
                _LOGGER.warning(
                    "Model config not found for %s, using defaults", selected_model
                )
                phases = 3
                mppt_count = 1
                string_count = 1
        else:
            # Individual field configuration - generic for any device type
            # Extract all configurable fields dynamically
            phases = user_input.get(
                "phases", dynamic_config.get("phases", {}).get("default", 3)
            )
            mppt_count = user_input.get(
                "mppt_count", dynamic_config.get("mppt_count", {}).get("default", 1)
            )
            string_count = user_input.get(
                "string_count", dynamic_config.get("string_count", {}).get("default", 1)
            )
            modules = user_input.get(
                "modules", dynamic_config.get("modules", {}).get("default", 3)
            )

            # Log all individual field values for debugging
            individual_fields = []
            for field_name, field_config in dynamic_config.items():
                if field_name not in [
                    "valid_models",
                    "firmware_version",
                    "connection_type",
                    "battery_slave_id",
                ]:
                    field_value = user_input.get(
                        field_name, field_config.get("default", "unknown")
                    )
                    individual_fields.append(f"{field_name}={field_value}")

            _LOGGER.info(
                "Using individual field configuration: %s",
                ", ".join(individual_fields),
            )

        battery_default = dynamic_config.get("battery_config", {}).get(
            "default", "none"
        )
        battery_config = user_input.get("battery_config", battery_default)

        # Use connection slave_id for all devices (including battery)
        battery_slave_id = user_input.get("slave_id", 1)

        firmware_version = user_input.get(
            "firmware_version", template_data.get("firmware_version", "1.0.0")
        )
        connection_type = user_input.get("connection_type", "LAN")

        # Derive battery settings from battery_config
        # For SBR templates, always enable battery mode
        if (
            "sbr" in template_data.get("name", "").lower()
            or "battery" in template_data.get("type", "").lower()
        ):
            battery_enabled = True
            battery_type = "sbr_battery"
        else:
            battery_enabled = battery_config != "none"
            battery_type = battery_config

        # Handle "Latest" firmware version - use the highest available version
        if firmware_version == "Latest":
            firmware_config = dynamic_config.get("firmware_version", {})
            available_firmware = firmware_config.get("options", [])

            if available_firmware:
                # Find the highest version (excluding "Latest")
                numeric_versions = [v for v in available_firmware if v != "Latest"]
                if numeric_versions:
                    from packaging import version

                    try:
                        # Sort by version and take the highest
                        sorted_versions = sorted(
                            numeric_versions, key=lambda x: version.parse(x)
                        )
                        firmware_version = sorted_versions[-1]
                        _LOGGER.debug(
                            "Using latest firmware version: %s", firmware_version
                        )
                    except version.InvalidVersion:
                        # Fallback to first numeric version
                        firmware_version = numeric_versions[0]
                        _LOGGER.debug(
                            "Using fallback firmware version: %s", firmware_version
                        )

        _LOGGER.info(
            "Processing dynamic config: phases=%d, mppt=%d, battery=%s, battery_type=%s, fw=%s, conn=%s",
            phases,
            mppt_count,
            battery_enabled,
            battery_type,
            firmware_version,
            connection_type,
        )

        # Add modules to dynamic_config for condition filtering
        if selected_model and model_config:
            dynamic_config["modules"] = modules
        else:
            # For individual field configuration, add all fields to dynamic_config
            dynamic_config["modules"] = modules
            # Add other individual fields that might be used for filtering
            for field_name, field_config in dynamic_config.items():
                if field_name not in [
                    "valid_models",
                    "firmware_version",
                    "connection_type",
                    "battery_slave_id",
                ]:
                    if isinstance(field_config, dict) and "default" in field_config:
                        field_value = user_input.get(
                            field_name, field_config.get("default")
                        )
                        dynamic_config[field_name] = field_value

        # Process sensors
        for sensor in original_sensors:
            # Check if sensor should be included based on configuration
            sensor_name = sensor.get("name", "unknown")
            unique_id = sensor.get("unique_id", "unknown")
            _LOGGER.debug(
                "Processing sensor: %s (unique_id: %s)", sensor_name, unique_id
            )

            should_include = self._should_include_sensor(
                sensor,
                phases,
                mppt_count,
                battery_enabled,
                battery_type,
                battery_slave_id,
                firmware_version,
                connection_type,
                dynamic_config,
                string_count,
            )

            if should_include:
                # Apply firmware-specific modifications
                modified_sensor = self._apply_firmware_modifications(
                    sensor, firmware_version, dynamic_config
                )
                processed_sensors.append(modified_sensor)
                _LOGGER.debug("Included sensor: %s", sensor_name)
            else:
                _LOGGER.debug("Excluded sensor: %s", sensor_name)

        # Process calculated sensors
        for calculated in original_calculated:
            # Check if calculated sensor should be included based on configuration
            if self._should_include_sensor(
                calculated,
                phases,
                mppt_count,
                battery_enabled,
                battery_type,
                battery_slave_id,
                firmware_version,
                connection_type,
                dynamic_config,
                string_count,
            ):
                processed_calculated.append(calculated)

        # Process binary sensors
        original_binary_sensors = template_data.get("binary_sensors", [])
        processed_binary_sensors = []
        for binary_sensor in original_binary_sensors:
            # Binary sensors are always included (they don't depend on hardware config)
            processed_binary_sensors.append(binary_sensor)

        # Process controls
        for control in original_controls:
            # Check if control should be included based on configuration
            if self._should_include_sensor(
                control,
                phases,
                mppt_count,
                battery_enabled,
                battery_type,
                battery_slave_id,
                firmware_version,
                connection_type,
                dynamic_config,
                string_count,
            ):
                processed_controls.append(control)

        # Return processed template data and configuration values

        return {
            "sensors": processed_sensors,
            "calculated": processed_calculated,
            "binary_sensors": processed_binary_sensors,
            "controls": processed_controls,
            # Also return configuration values for use in _create_regular_entry
            "config_values": {
                "phases": phases,
                "mppt_count": mppt_count,
                "string_count": string_count,
                "modules": modules,
                "battery_config": battery_config,
                "battery_enabled": battery_enabled,
                "battery_type": battery_type,
                "battery_slave_id": battery_slave_id,
                "firmware_version": firmware_version,
                "connection_type": connection_type,
                "selected_model": selected_model,
                "dynamic_config": dynamic_config,
            },
        }

    def _should_include_sensor(
        self,
        sensor: dict,
        phases: int,
        mppt_count: int,
        battery_enabled: bool,
        battery_type: str,
        battery_slave_id: int,
        firmware_version: str,
        connection_type: str,
        dynamic_config: dict,
        string_count: int = 0,
    ) -> bool:
        """Check if sensor should be included based on configuration."""
        sensor_name = sensor.get("name", "") or ""
        unique_id = sensor.get("unique_id", "") or ""

        # Ensure we have strings
        sensor_name = str(sensor_name).lower()
        unique_id = str(unique_id).lower()

        # Check both sensor_name and unique_id for filtering
        search_text = f"{sensor_name} {unique_id}".lower()

        # For SBR battery templates, only include battery-related sensors
        if battery_type == "sbr_battery":
            # Only include sensors that are battery-related
            battery_keywords = [
                "battery",
                "sbr",
                "soc",
                "soh",
                "cell",
                "module",
                "voltage",
                "current",
                "temperature",
                "charge",
                "discharge",
            ]
            if not any(keyword in search_text for keyword in battery_keywords):
                return False

        # Phase-specific sensors
        if phases == 1:
            # Exclude phase B and C sensors for single phase
            if any(phase in search_text for phase in ["phase b", "phase c"]):
                return False

        # MPPT-specific sensors
        if "mppt" in search_text:
            mppt_number = self._extract_mppt_number(search_text)
            if mppt_number and mppt_number > mppt_count:
                return False

        # String-specific sensors
        if "string" in search_text:
            string_number = self._extract_string_number(search_text)
            if string_number and string_number > string_count:
                return False

        # Module-specific sensors (for batteries)
        if "module" in search_text:
            module_number = self._extract_module_number(search_text)
            if module_number:
                actual_modules = dynamic_config.get("modules", 0)
                if module_number > actual_modules:
                    return False

        # All other sensors are included
        return True

    # REGEX FUNCTIONS
    def _extract_mppt_number(self, search_text: str) -> int:
        """Extract MPPT number from sensor name or unique_id."""
        import re

        if not search_text:
            return None

        match = re.search(r"mppt(\d+)", search_text.lower())
        if match and match.group(1):
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        return None

    def _extract_string_number(self, search_text: str) -> int:
        """Extract string number from sensor name or unique_id."""
        import re

        if not search_text:
            return None

        # Look for "string" followed by digits, with optional underscore or space
        match = re.search(r"string[_\s]*(\d+)", search_text.lower())
        if match and match.group(1):
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        return None

    def _extract_module_number(self, search_text: str) -> int:
        """Extract module number from sensor name or unique_id."""
        import re

        if not search_text:
            return None

        # Look for "module" followed by digits, with optional underscore or space
        match = re.search(r"module[_\s]*(\d+)", search_text.lower())
        if match and match.group(1):
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        return None

    # Firmware Handling to replace the sensors with the correct firmware version
    def _apply_firmware_modifications(
        self, sensor: dict, firmware_version: str, dynamic_config: dict
    ) -> dict:
        """Apply firmware-specific modifications to sensor based on unique_id."""
        modified_sensor = sensor.copy()

        # Get sensor replacements configuration
        sensor_replacements = dynamic_config.get("sensor_replacements", {})

        # Get sensor unique_id
        unique_id = sensor.get("unique_id", "")

        # Check if this sensor has firmware-specific replacements
        if unique_id in sensor_replacements:
            replacements = sensor_replacements.get(unique_id, {})

            # Check if replacements is valid and not empty
            if replacements and isinstance(replacements, dict) and replacements:
                # Find the highest firmware version that matches or is lower than current
                replacement_keys = list(replacements.keys()) if replacements else []
                applicable_version = self._find_applicable_firmware_version(
                    firmware_version, replacement_keys
                )

                if applicable_version:
                    replacement_config = replacements.get(applicable_version, {})
                    _LOGGER.debug(
                        "Applying firmware %s replacement for sensor %s",
                        applicable_version,
                        unique_id,
                    )

                    # Apply all replacement parameters
                    if replacement_config and isinstance(replacement_config, dict):
                        for param, value in replacement_config.items():
                            if (
                                param != "description"
                            ):  # Skip description, it's just for documentation
                                modified_sensor[param] = value
                                _LOGGER.debug(
                                    "Replaced %s=%s for sensor %s (firmware %s)",
                                    param,
                                    value,
                                    unique_id,
                                    applicable_version,
                                )

        return modified_sensor

    def _find_applicable_firmware_version(
        self, current_version: str, available_versions: list
    ) -> str:
        """Find the highest firmware version that matches or is lower than current version."""
        from packaging import version

        # Check if available_versions is valid
        if not available_versions or not isinstance(available_versions, (list, dict)):
            return None

        try:
            # Try to parse as semantic version first
            current_ver = version.parse(current_version)
            applicable_versions = []

            for ver_str in available_versions:
                try:
                    ver = version.parse(ver_str)
                    if ver <= current_ver:
                        applicable_versions.append(ver)
                except version.InvalidVersion:
                    # Skip invalid semantic versions
                    continue

            if applicable_versions:
                # Return the highest applicable version
                return str(max(applicable_versions))

        except version.InvalidVersion:
            # For non-semantic versions (like SAPPHIRE-H_03011.95.01),
            # try exact match first, then fallback to string comparison
            _LOGGER.debug(
                "Non-semantic firmware version format detected: %s", current_version
            )

            # Check for exact match
            if current_version in available_versions:
                return current_version

            # Try string comparison for similar formats
            for ver_str in available_versions:
                if ver_str == current_version:
                    return ver_str
                # For similar formats, we could add more sophisticated comparison logic here

        return None
