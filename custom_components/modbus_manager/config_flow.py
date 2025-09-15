"""Config Flow for Modbus Manager."""

import asyncio
import json
import os
from typing import List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_DELAY,
    DEFAULT_MESSAGE_WAIT_MS,
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
        self._translations = {}

    async def _load_translations(self) -> dict:
        """Load translations from JSON files asynchronously."""
        translations = {}
        try:
            # Get the directory of this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            translations_dir = os.path.join(current_dir, "translations")

            # Load German translations
            de_file = os.path.join(translations_dir, "de.json")
            if os.path.exists(de_file):
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(
                    None, self._read_file_sync, de_file
                )
                translations["de"] = json.loads(content)

            # Load English translations
            en_file = os.path.join(translations_dir, "en.json")
            if os.path.exists(en_file):
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(
                    None, self._read_file_sync, en_file
                )
                translations["en"] = json.loads(content)

        except Exception as e:
            _LOGGER.error("Error loading translations: %s", str(e))
            translations = {}

        return translations

    def _read_file_sync(self, file_path: str) -> str:
        """Read file synchronously (to be run in executor)."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _get_translation(self, key: str, language: str = "de") -> str:
        """Get translation for a key."""
        try:
            if language in self._translations:
                # Navigate through the nested structure
                keys = key.split(".")
                value = self._translations[language]
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return key  # Return key if translation not found
                return value if isinstance(value, str) else key
            return key
        except Exception:
            return key

    async def async_step_user(self, user_input: dict = None) -> FlowResult:
        """Handle the initial step."""
        try:
            # Load translations if not loaded yet
            if not self._translations:
                _LOGGER.debug("Loading translations...")
                self._translations = await self._load_translations()
                _LOGGER.debug(
                    "Translations loaded: %s", list(self._translations.keys())
                )

            # Templates laden (always reload for now to pick up changes)
            _LOGGER.debug("Loading templates...")
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
            _LOGGER.debug("Templates loaded: %s", list(self._templates.keys()))

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
                    _LOGGER.debug("Selected template: %s", self._selected_template)

                    # Check if this is an aggregates template
                    template_data = self._templates.get(self._selected_template, {})
                    _LOGGER.debug(
                        "Template data for %s: keys=%s, has_dynamic_config=%s",
                        self._selected_template,
                        list(template_data.keys()),
                        "dynamic_config" in template_data,
                    )
                    if template_data.get("aggregates"):
                        return await self.async_step_aggregates_config()
                    else:
                        # Check if template has dynamic config
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

    async def async_step_aggregates_config(self, user_input: dict = None) -> FlowResult:
        """Configure aggregates for the selected template."""
        try:
            if not self._selected_template:
                return self.async_abort(reason="no_template_selected")

            template_data = self._templates.get(self._selected_template, {})
            available_aggregates = template_data.get("aggregates", [])

            if not available_aggregates:
                return self.async_abort(
                    reason="no_aggregates",
                    description_placeholders={"template": self._selected_template},
                )

            if user_input is not None:
                # Process selected aggregates
                selected_aggregates = user_input.get("selected_aggregates", [])

                if not selected_aggregates:
                    return self.async_show_form(
                        step_id="aggregates_config",
                        data_schema=self._get_aggregates_schema(available_aggregates),
                        errors={"base": "select_aggregates"},
                    )

                # Create final config with selected aggregates
                final_config = {
                    "template": self._selected_template,
                    "template_version": template_data.get("version", 1),
                    "prefix": user_input.get("prefix", "aggregates"),
                    "selected_aggregates": selected_aggregates,
                    "aggregates_config": user_input,
                }

                return await self.async_step_final_config(final_config)

            # Show aggregates configuration form
            return self.async_show_form(
                step_id="aggregates_config",
                data_schema=self._get_aggregates_schema(available_aggregates),
                description_placeholders={
                    "template_name": self._selected_template,
                    "aggregate_count": str(len(available_aggregates)),
                },
            )

        except Exception as e:
            _LOGGER.error("Error in aggregates configuration: %s", str(e))
            return self.async_abort(
                reason="aggregates_error", description_placeholders={"error": str(e)}
            )

    def _get_aggregates_schema(self, available_aggregates: List[dict]) -> vol.Schema:
        """Generate schema for aggregates configuration."""
        # Create options for aggregate selection
        aggregate_options = {}
        for i, aggregate in enumerate(available_aggregates):
            name = aggregate.get("name", f"Aggregate {i+1}")
            group = aggregate.get("group", "unknown")
            method = aggregate.get("method", "sum")
            aggregate_options[f"{i}"] = f"{name} ({group} - {method})"

        return vol.Schema(
            {
                vol.Required("prefix", default="aggregates"): str,
                vol.Required("selected_aggregates"): vol.All(
                    cv.multi_select(aggregate_options),
                    vol.Length(min=1, msg="Mindestens eine Aggregation auswählen"),
                ),
            }
        )

    async def async_step_connection(self, user_input: dict = None) -> FlowResult:
        """Handle connection parameters step for dynamic templates."""
        if user_input is not None:
            # Store connection parameters and proceed to dynamic config
            self._connection_params = user_input
            _LOGGER.info("Connection parameters stored, proceeding to dynamic config")
            return await self.async_step_dynamic_config()

        # Show connection parameters form
        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Required("prefix", default="SG"): str,
                    vol.Required("host"): str,
                    vol.Optional("port", default=502): int,
                    vol.Optional("slave_id", default=1): int,
                    vol.Optional("timeout", default=3): int,
                    vol.Optional("delay", default=0): int,
                    vol.Optional("request_delay", default=100): int,
                }
            ),
            description_placeholders={
                "template_name": self._selected_template,
            },
        )

    async def async_step_dynamic_config(self, user_input: dict = None) -> FlowResult:
        """Handle dynamic configuration step for templates with dynamic config."""
        _LOGGER.info(
            "async_step_dynamic_config called with user_input: %s",
            user_input is not None,
        )
        if user_input is not None:
            # Combine connection params with dynamic config
            combined_input = {**self._connection_params, **user_input}
            _LOGGER.info("Combined input keys: %s", list(combined_input.keys()))
            return await self.async_step_final_config(combined_input)

        # Get template data
        template_data = self._templates.get(self._selected_template, {})
        dynamic_config = template_data.get("dynamic_config", {})

        _LOGGER.info(
            "Template data keys: %s",
            list(template_data.keys())
            if isinstance(template_data, dict)
            else "Not a dict",
        )
        _LOGGER.info(
            "Dynamic config keys: %s",
            list(dynamic_config.keys())
            if isinstance(dynamic_config, dict)
            else "Not a dict",
        )
        _LOGGER.info(
            "Dynamic config valid_models: %s", dynamic_config.get("valid_models")
        )
        _LOGGER.info("Template valid_models: %s", template_data.get("valid_models"))

        # Generate schema for dynamic config
        schema_fields = {}

        # Check if template has valid_models (model selection)
        # Look for valid_models in dynamic_config first, then at template root level
        valid_models = dynamic_config.get("valid_models") or template_data.get(
            "valid_models"
        )
        _LOGGER.info(
            "Valid models check: dynamic_config.valid_models=%s, template.valid_models=%s, final=%s",
            dynamic_config.get("valid_models") is not None,
            template_data.get("valid_models") is not None,
            valid_models is not None,
        )
        if valid_models:
            # Create model options with display names
            model_options = {}
            if valid_models and isinstance(valid_models, dict):
                for model_name, config in valid_models.items():
                    phases = config.get("phases", 1)
                    mppt_count = config.get("mppt_count", 1)
                    string_count = config.get("string_count", 0)
                    display_name = f"{model_name} ({phases}Φ, {mppt_count} MPPT, {string_count} Strings)"
                    model_options[model_name] = display_name

            schema_fields["selected_model"] = vol.In(model_options)
        else:
            # Individual field configuration
            if "phases" in dynamic_config:
                phase_options = dynamic_config["phases"].get("options", [1, 3])
                phase_default = dynamic_config["phases"].get("default", 3)
                schema_fields["phases"] = vol.In(phase_options)

            if "mppt_count" in dynamic_config:
                mppt_options = dynamic_config["mppt_count"].get("options", [1, 2, 3])
                mppt_default = dynamic_config["mppt_count"].get("default", 1)
                schema_fields["mppt_count"] = vol.In(mppt_options)

            if "string_count" in dynamic_config:
                string_options = dynamic_config["string_count"].get(
                    "options", [0, 1, 2, 3, 4]
                )
                string_default = dynamic_config["string_count"].get("default", 0)
                schema_fields["string_count"] = vol.In(string_options)

        # Add firmware version if available
        if "firmware_version" in dynamic_config:
            firmware_options = dynamic_config["firmware_version"].get(
                "options", ["SAPPHIRE-H_xxxx"]
            )
            firmware_default = dynamic_config["firmware_version"].get(
                "default", "SAPPHIRE-H_xxxx"
            )
            schema_fields["firmware_version"] = vol.In(firmware_options)

        # Add connection type if available
        if "connection_type" in dynamic_config:
            connection_options = dynamic_config["connection_type"].get(
                "options", ["LAN"]
            )
            connection_default = dynamic_config["connection_type"].get("default", "LAN")
            schema_fields["connection_type"] = vol.In(connection_options)

        return self.async_show_form(
            step_id="dynamic_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "template_name": self._selected_template,
            },
        )

    async def async_step_device_config(self, user_input: dict = None) -> FlowResult:
        """Handle device configuration step."""
        if user_input is not None:
            # Check if SBR battery is selected and we need battery slave ID
            _LOGGER.debug("Device config user input: %s", user_input)
            _LOGGER.debug("Device config user input keys: %s", list(user_input.keys()))
            battery_config = user_input.get("battery_config")
            _LOGGER.debug("Battery config selected: %s", battery_config)
            _LOGGER.debug(
                "All config values: phases=%s, mppt_count=%s, battery_config=%s",
                user_input.get("phases"),
                user_input.get("mppt_count"),
                battery_config,
            )
            if battery_config == "sbr_battery":
                # Store current input and go to battery slave ID step
                _LOGGER.info(
                    "SBR Battery selected, redirecting to battery slave ID step"
                )
                self._temp_device_config = user_input
                return await self.async_step_battery_slave_id()
            else:
                _LOGGER.debug("No SBR battery selected, proceeding to final config")
                return await self.async_step_final_config(user_input)

        # Check if this is a simple template
        template_data = self._templates.get(self._selected_template, {})
        if template_data.get("is_simple_template"):
            # Check if this is a SunSpec Standard Configuration template
            if "SunSpec Standard Configuration" in self._selected_template:
                # SunSpec Standard Configuration - requires model addresses
                default_prefix = template_data.get("default_prefix", "device")
                return self.async_show_form(
                    step_id="device_config",
                    data_schema=vol.Schema(
                        {
                            vol.Required("prefix", default=default_prefix): str,
                            vol.Optional("name"): str,
                            vol.Required("common_model_address", default=40001): int,
                            vol.Required("inverter_model_address", default=40069): int,
                            vol.Optional("storage_model_address"): int,
                            vol.Optional("meter_model_address"): int,
                        }
                    ),
                    description_placeholders={
                        "template": self._selected_template,
                        "description": "SunSpec Standard - Modell-Adressen angeben",
                    },
                )
            else:
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
            # Check if this template supports dynamic configuration
            _LOGGER.debug("Template data keys: %s", list(template_data.keys()))
            _LOGGER.debug("Has dynamic_config: %s", "dynamic_config" in template_data)
            _LOGGER.debug("Template name: %s", template_data.get("name", "Unknown"))

            default_prefix = template_data.get("default_prefix", "device")

            # Field descriptions are handled by translation files

            schema_fields = {
                vol.Required("prefix", default=default_prefix): str,
                vol.Required("host"): str,
                vol.Optional("port", default=502): int,
                vol.Optional("slave_id", default=1): int,
                vol.Optional("timeout", default=DEFAULT_TIMEOUT): int,
                vol.Optional("delay", default=DEFAULT_DELAY): int,
                vol.Optional(
                    "message_wait_milliseconds", default=DEFAULT_MESSAGE_WAIT_MS
                ): int,
            }

            # Add dynamic template parameters if supported
            if self._supports_dynamic_config(template_data):
                _LOGGER.debug("Template supports dynamic config, adding schema fields")
                dynamic_schema = self._get_dynamic_config_schema(template_data)
                _LOGGER.debug("Dynamic schema fields: %s", list(dynamic_schema.keys()))
                schema_fields.update(dynamic_schema)
            else:
                _LOGGER.debug("Template does not support dynamic config")

            # Add firmware version selection for all templates that have available_firmware_versions
            available_firmware = template_data.get("available_firmware_versions", [])
            if available_firmware:
                _LOGGER.debug(
                    "Adding firmware_version field to schema with options: %s",
                    available_firmware,
                )
                label = self._get_translation(
                    "config.step.device_config.data.firmware_version"
                )
                schema_fields[label] = vol.In(available_firmware)

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

        # Debug: Show dynamic_config content if it exists
        if has_dynamic:
            dynamic_config = template_data.get("dynamic_config", {})
            _LOGGER.info("Dynamic config found: %s", list(dynamic_config.keys()))
        else:
            _LOGGER.warning("No dynamic_config found in template!")

        return has_dynamic

    def _get_dynamic_config_schema(self, template_data: dict) -> dict:
        """Generate dynamic configuration schema based on template."""
        dynamic_config = template_data.get("dynamic_config", {})
        _LOGGER.debug(
            "_get_dynamic_config_schema: dynamic_config keys=%s",
            list(dynamic_config.keys()),
        )
        schema_fields = {}

        # Check if model-specific config is enabled
        model_specific_config = dynamic_config.get("model_specific_config", {}).get(
            "default", False
        )

        if model_specific_config:
            # Model-specific configuration: show model dropdown
            valid_models = template_data.get("valid_models", {})

            # Create model options with display names
            model_options = {}
            if valid_models and isinstance(valid_models, dict):
                for model_name, config in valid_models.items():
                    phases = config.get("phases", 1)
                    mppt_count = config.get("mppt_count", 1)
                    string_count = config.get("string_count", 0)
                    display_name = f"{model_name} ({phases}Φ, {mppt_count} MPPT, {string_count} Strings)"
                    model_options[model_name] = display_name

            _LOGGER.debug(
                "Adding model_specific_config field to schema with %d models",
                len(model_options),
            )
            schema_fields["selected_model"] = vol.In(model_options)

        else:
            # Individual field configuration: show separate fields
            # Phase configuration
            if "phases" in dynamic_config:
                phase_options = dynamic_config["phases"].get("options", [1, 3])
                phase_default = dynamic_config["phases"].get("default", 3)
                _LOGGER.debug(
                    "Adding phases field to schema with options: %s, default: %s",
                    phase_options,
                    phase_default,
                )
                schema_fields["phases"] = vol.In(phase_options)

            # MPPT configuration
            if "mppt_count" in dynamic_config:
                mppt_options = dynamic_config["mppt_count"].get("options", [1, 2, 3])
                mppt_default = dynamic_config["mppt_count"].get("default", 1)
                _LOGGER.debug(
                    "Adding mppt_count field to schema with options: %s, default: %s",
                    mppt_options,
                    mppt_default,
                )
                schema_fields["mppt_count"] = vol.In(mppt_options)

            # String count configuration
            if "string_count" in dynamic_config:
                string_options = dynamic_config["string_count"].get(
                    "options", [0, 1, 2, 3, 4]
                )
                string_default = dynamic_config["string_count"].get("default", 0)
                _LOGGER.debug(
                    "Adding string_count field to schema with options: %s, default: %s",
                    string_options,
                    string_default,
                )
                schema_fields["string_count"] = vol.In(string_options)

        # Battery configuration (single combo box)
        if "battery_config" in dynamic_config:
            battery_config_options = dynamic_config["battery_config"].get(
                "options", ["none", "standard_battery", "sbr_battery"]
            )
            battery_default = dynamic_config["battery_config"].get("default", "none")
            option_labels = dynamic_config["battery_config"].get("option_labels", {})

            # Create options dict with labels
            battery_options = {}
            for option in battery_config_options:
                display_label = option_labels.get(
                    option, option.replace("_", " ").title()
                )
                battery_options[option] = display_label

            _LOGGER.debug(
                "Adding battery_config field to schema with options: %s, default: %s",
                battery_options,
                battery_default,
            )
            schema_fields["battery_config"] = vol.In(battery_options)

        # Battery Slave ID (only needed for SBR Battery) - will be added conditionally in separate step

        # Firmware version - prefer available_firmware_versions over dynamic_config
        available_firmware = template_data.get("available_firmware_versions", [])
        if available_firmware:
            _LOGGER.debug(
                "Adding firmware_version field to schema with options: %s",
                available_firmware,
            )
            schema_fields["firmware_version"] = vol.In(available_firmware)
        elif "firmware_version" in dynamic_config:
            _LOGGER.debug("Adding firmware_version field to schema from dynamic config")
            schema_fields["firmware_version"] = vol.Str()

        # String count - removed as no string-specific sensors exist in current templates

        # Connection type
        if "connection_type" in dynamic_config:
            conn_options = dynamic_config["connection_type"].get(
                "options", ["LAN", "WINET"]
            )
            _LOGGER.debug(
                "Adding connection_type field to schema with options: %s", conn_options
            )
            schema_fields["connection_type"] = vol.In(conn_options)

        _LOGGER.debug("Final schema fields: %s", list(schema_fields.keys()))
        return schema_fields

    async def async_step_battery_slave_id(self, user_input: dict = None) -> FlowResult:
        """Handle battery slave ID configuration for SBR battery."""
        if user_input is not None:
            # Combine with previous device config and proceed
            combined_input = dict(self._temp_device_config)
            combined_input.update(user_input)
            return await self.async_step_final_config(combined_input)

        # Show battery slave ID configuration
        return self.async_show_form(
            step_id="battery_slave_id",
            data_schema=vol.Schema(
                {
                    vol.Optional("battery_slave_id", default=200): int,
                }
            ),
            description_placeholders={
                "template": self._selected_template,
                "battery_config": "SBR Battery",
            },
        )

    def _process_dynamic_config(self, user_input: dict, template_data: dict) -> dict:
        """Process template based on dynamic configuration parameters."""
        _LOGGER.debug("_process_dynamic_config called with user_input: %s", user_input)
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
                phases = model_config.get("phases", 3)
                mppt_count = model_config.get("mppt_count", 1)
                string_count = model_config.get("string_count", 0)
                _LOGGER.info(
                    "Using model-specific config for %s: phases=%d, mppt=%d, strings=%d",
                    selected_model,
                    phases,
                    mppt_count,
                    string_count,
                )
            else:
                _LOGGER.warning(
                    "Model config not found for %s, using defaults", selected_model
                )
                phases = 3
                mppt_count = 1
                string_count = 0
        else:
            # Individual field configuration
            phases_default = dynamic_config.get("phases", {}).get("default", 3)
            phases = user_input.get("phases", phases_default)

            mppt_default = dynamic_config.get("mppt_count", {}).get("default", 1)
            mppt_count = user_input.get("mppt_count", mppt_default)

            string_default = dynamic_config.get("string_count", {}).get("default", 0)
            string_count = user_input.get("string_count", string_default)

        battery_default = dynamic_config.get("battery_config", {}).get(
            "default", "none"
        )
        battery_config = user_input.get("battery_config", battery_default)

        battery_slave_id_default = dynamic_config.get("battery_slave_id", {}).get(
            "default", 200
        )
        battery_slave_id = user_input.get("battery_slave_id", battery_slave_id_default)

        firmware_version = user_input.get(
            "firmware_version", template_data.get("firmware_version", "1.0.0")
        )
        connection_type = user_input.get("connection_type", "LAN")

        # Derive battery settings from battery_config
        battery_enabled = battery_config != "none"
        battery_type = battery_config

        _LOGGER.debug(
            "Dynamic config processing: battery_config=%s, battery_enabled=%s, battery_type=%s, battery_slave_id=%d",
            battery_config,
            battery_enabled,
            battery_type,
            battery_slave_id,
        )
        _LOGGER.debug(
            "Dynamic config parameters: phases=%d, mppt_count=%d, firmware_version=%s, connection_type=%s",
            phases,
            mppt_count,
            firmware_version,
            connection_type,
        )

        # Handle "Latest" firmware version - use the highest available version
        if firmware_version == "Latest":
            available_firmware = template_data.get("available_firmware_versions", [])
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
                if "mppt3" in unique_id.lower() or "mppt 3" in sensor_name.lower():
                    _LOGGER.info(
                        "MPPT3 sensor correctly excluded: %s (unique_id: %s)",
                        sensor_name,
                        unique_id,
                    )

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

        # Return processed template data

        return {
            "sensors": processed_sensors,
            "calculated": processed_calculated,
            "binary_sensors": processed_binary_sensors,
            "controls": processed_controls,
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

        # All other sensors are included
        return True

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

            # Check if this is an aggregates template
            if isinstance(template_data, dict) and template_data.get("aggregates"):
                # Handle aggregates template
                return self._create_aggregates_entry(
                    user_input, template_data, template_version
                )
            else:
                # Handle regular template
                return self._create_regular_entry(
                    user_input, template_data, template_version
                )

        except Exception as e:
            _LOGGER.error("Error creating configuration: %s", str(e))
            return self.async_abort(
                reason="config_error", description_placeholders={"error": str(e)}
            )

    def _create_aggregates_entry(
        self, user_input: dict, template_data: dict, template_version: int
    ) -> FlowResult:
        """Create config entry for aggregates template."""
        try:
            # Get selected aggregates
            selected_aggregates = user_input.get("selected_aggregates", [])
            available_aggregates = template_data.get("aggregates", [])

            # Filter aggregates based on selection
            filtered_aggregates = []
            for i, aggregate in enumerate(available_aggregates):
                if str(i) in selected_aggregates:
                    filtered_aggregates.append(aggregate)

            if not filtered_aggregates:
                return self.async_abort(
                    reason="no_aggregates_selected",
                    description_placeholders={"error": "No aggregates selected"},
                )

            _LOGGER.debug(
                "Aggregates Template %s (Version %s) with %d selected aggregates",
                self._selected_template,
                template_version,
                len(filtered_aggregates),
            )

            # Create config entry
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "aggregates": filtered_aggregates,
                    "selected_aggregates": selected_aggregates,
                    "is_aggregates_template": True,
                },
            )

        except Exception as e:
            _LOGGER.error("Error creating aggregates configuration: %s", str(e))
            return self.async_abort(
                reason="aggregates_config_error",
                description_placeholders={"error": str(e)},
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
            else:
                # Extract registers from template
                template_registers = (
                    template_data.get("sensors", []) or []
                    if isinstance(template_data, dict)
                    else template_data or []
                )
                _LOGGER.info("Template registers: %s", template_registers is not None)
                _LOGGER.info("Template data type: %s", type(template_data))
                _LOGGER.info(
                    "Template data keys: %s",
                    list(template_data.keys())
                    if isinstance(template_data, dict)
                    else "Not a dict",
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

            # Debug: Show template structure
            _LOGGER.debug(
                "Template structure: %s",
                template_registers[:2] if template_registers else "No registers",
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

            # Create config entry
            config_data = {
                "template": self._selected_template,
                "template_version": template_version,
                "prefix": user_input["prefix"],
                "host": user_input["host"],
                "port": user_input.get("port", 502),
                "slave_id": user_input.get("slave_id", 1),
                "timeout": user_input.get("timeout", 1),  # PDF requirement: 1000ms
                "delay": user_input.get("delay", 0),
                "firmware_version": firmware_version,
                "registers": template_registers,
                "calculated_entities": template_calculated,
                "binary_sensors": template_binary_sensors,
                "controls": template_controls,
                "is_aggregates_template": False,
            }

            _LOGGER.info(
                "Config data created with %d binary_sensors",
                len(template_binary_sensors),
            )

            # Add dynamic configuration parameters if available
            if self._supports_dynamic_config(template_data):
                # Check if model-specific config is used
                selected_model = user_input.get("selected_model")
                _LOGGER.info("Selected model from user_input: %s", selected_model)
                _LOGGER.info("User input keys: %s", list(user_input.keys()))
                if selected_model:
                    # Get configuration from selected model
                    # Look for valid_models in dynamic_config first, then at template root level
                    valid_models = template_data.get("dynamic_config", {}).get(
                        "valid_models"
                    ) or template_data.get("valid_models", {})

                    # Get model configuration directly from valid_models
                    model_config = (
                        valid_models.get(selected_model)
                        if valid_models and isinstance(valid_models, dict)
                        else None
                    )
                    if model_config and isinstance(model_config, dict):
                        phases = model_config.get("phases", 3)
                        mppt_count = model_config.get("mppt_count", 1)
                        string_count = model_config.get("string_count", 0)
                        _LOGGER.info(
                            "Using model-specific config for %s: phases=%d, mppt=%d, strings=%d",
                            selected_model,
                            phases,
                            mppt_count,
                            string_count,
                        )
                    else:
                        _LOGGER.warning(
                            "Model config not found for %s, using defaults",
                            selected_model,
                        )
                        phases = 3
                        mppt_count = 1
                        string_count = 0
                else:
                    # Individual field configuration
                    phases = user_input.get("phases", 3)
                    mppt_count = user_input.get("mppt_count", 1)
                    string_count = user_input.get("string_count", 0)

                config_data.update(
                    {
                        "phases": phases,
                        "mppt_count": mppt_count,
                        "string_count": string_count,
                        "battery_config": user_input.get("battery_config", "none"),
                        "battery_slave_id": user_input.get("battery_slave_id", 200),
                        "firmware_version": user_input.get(
                            "firmware_version", "SAPPHIRE-H_xxxx"
                        ),
                        "connection_type": user_input.get("connection_type", "LAN"),
                    }
                )

            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
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

            # Check if this is a SunSpec Standard Configuration template
            if "SunSpec Standard Configuration" in self._selected_template:
                return self._create_sunspec_config_entry(
                    user_input, template_data, template_version
                )

            # Validate simple template input
            if not self._validate_simple_config(user_input):
                return self.async_abort(
                    reason="invalid_simple_config",
                    description_placeholders={
                        "error": "Invalid configuration for simple template"
                    },
                )

            # Create config entry for simple template
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "name": user_input.get("name", user_input["prefix"]),
                    "template_data": template_data,
                    "is_simple_template": True,
                    "is_aggregates_template": False,
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

    def _create_sunspec_config_entry(
        self, user_input: dict, template_data: dict, template_version: int
    ) -> FlowResult:
        """Create config entry for SunSpec Standard Configuration template."""
        try:
            _LOGGER.debug(
                "Creating SunSpec Standard Configuration Entry: %s",
                self._selected_template,
            )

            # Validate SunSpec configuration input
            if not self._validate_sunspec_config(user_input):
                return self.async_abort(
                    reason="invalid_sunspec_config",
                    description_placeholders={"error": "Invalid SunSpec configuration"},
                )

            # Build model addresses from user input
            model_addresses = {
                "common_model": user_input["common_model_address"],
                "inverter_model": user_input["inverter_model_address"],
            }

            # Add optional model addresses
            if user_input.get("storage_model_address"):
                model_addresses["storage_model"] = user_input["storage_model_address"]

            if user_input.get("meter_model_address"):
                model_addresses["meter_model"] = user_input["meter_model_address"]

            # Create config entry for SunSpec Standard Configuration
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "name": user_input.get("name", user_input["prefix"]),
                    "template_data": template_data,
                    "model_addresses": model_addresses,
                    "is_simple_template": True,
                    "is_sunspec_config": True,
                    "is_aggregates_template": False,
                },
            )

        except Exception as e:
            _LOGGER.error("Error creating SunSpec configuration: %s", str(e))
            return self.async_abort(
                reason="sunspec_config_error",
                description_placeholders={"error": str(e)},
            )

    def _validate_sunspec_config(self, user_input: dict) -> bool:
        """Validate SunSpec Standard Configuration."""
        try:
            # Check required fields
            required_fields = [
                "prefix",
                "common_model_address",
                "inverter_model_address",
            ]
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

            # Modell-Adressen validieren
            common_addr = user_input.get("common_model_address")
            inverter_addr = user_input.get("inverter_model_address")

            if (
                not isinstance(common_addr, int)
                or common_addr < 1
                or common_addr > 65535
            ):
                return False

            if (
                not isinstance(inverter_addr, int)
                or inverter_addr < 1
                or inverter_addr > 65535
            ):
                return False

            # Optional: Storage und Meter Adressen validieren
            if (
                "storage_model_address" in user_input
                and user_input["storage_model_address"]
            ):
                storage_addr = user_input["storage_model_address"]
                if (
                    not isinstance(storage_addr, int)
                    or storage_addr < 1
                    or storage_addr > 65535
                ):
                    return False

            if (
                "meter_model_address" in user_input
                and user_input["meter_model_address"]
            ):
                meter_addr = user_input["meter_model_address"]
                if (
                    not isinstance(meter_addr, int)
                    or meter_addr < 1
                    or meter_addr > 65535
                ):
                    return False

            return True

        except Exception as e:
            _LOGGER.error("Error validating SunSpec configuration: %s", str(e))
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
            timeout = user_input.get("timeout", 1)  # PDF requirement: 1000ms
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
        # Check if this is an aggregates template
        is_aggregates_template = self.config_entry.data.get(
            "is_aggregates_template", False
        )

        if is_aggregates_template:
            # Show aggregates selection options
            return await self.async_step_aggregates_options()

        if user_input is not None:
            if "update_template" in user_input and user_input["update_template"]:
                return await self.async_step_update_template()
            elif "firmware_version" in user_input:
                # Update firmware version
                return await self.async_step_firmware_update(user_input)
            elif (
                "battery_config" in user_input
                and user_input["battery_config"] == "sbr_battery"
            ):
                # If SBR battery is selected, show battery slave ID configuration
                return await self.async_step_battery_config(user_input)
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

        # Load template to get available firmware versions
        template_data = await get_template_by_name(template_name)
        available_firmware = []
        if template_data and isinstance(template_data, dict):
            available_firmware = template_data.get("available_firmware_versions", [])

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
                _LOGGER.debug(
                    "Adding phases field: current=%s, options=%s",
                    current_phases,
                    phase_options,
                )
                schema_fields[vol.Optional("phases", default=current_phases)] = vol.In(
                    phase_options
                )

            # Add MPPT count selection
            if "mppt_count" in dynamic_config:
                current_mppt = self.config_entry.data.get("mppt_count", 2)
                mppt_options = dynamic_config["mppt_count"].get("options", [1, 2, 3])
                _LOGGER.debug(
                    "Adding mppt_count field: current=%s, options=%s",
                    current_mppt,
                    mppt_options,
                )
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

                _LOGGER.debug(
                    "Adding battery_config field: current=%s, choices=%s",
                    current_battery,
                    battery_choices,
                )
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

        # Add firmware version selection if available
        if available_firmware:
            current_firmware = self.config_entry.data.get("firmware_version", "1.0.0")
            schema_fields[
                vol.Optional("firmware_version", default=current_firmware)
            ] = vol.In(available_firmware)

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

    async def async_step_aggregates_options(
        self, user_input: dict = None
    ) -> FlowResult:
        """Handle aggregates options for existing aggregate hubs."""
        try:
            # Get current template data
            template_name = self.config_entry.data.get(
                "template", "Modbus Manager Aggregates"
            )
            template_data = await get_template_by_name(template_name)

            if not template_data:
                return self.async_abort(
                    reason="template_not_found",
                    description_placeholders={"template_name": template_name},
                )

            available_aggregates = template_data.get("aggregates", [])
            if not available_aggregates:
                return self.async_abort(
                    reason="no_aggregates",
                    description_placeholders={"template_name": template_name},
                )

            # Get currently selected aggregates
            current_aggregates = self.config_entry.data.get("aggregates", [])
            current_selected = self.config_entry.data.get("selected_aggregates", [])

            if user_input is not None:
                # Update the configuration
                selected_aggregates = user_input.get("selected_aggregates", [])

                if not selected_aggregates:
                    return self.async_show_form(
                        step_id="aggregates_options",
                        data_schema=self._get_aggregates_options_schema(
                            available_aggregates, current_selected
                        ),
                        errors={"base": "select_aggregates"},
                    )

                # Filter aggregates based on selection
                filtered_aggregates = []
                for i, aggregate in enumerate(available_aggregates):
                    if str(i) in selected_aggregates:
                        filtered_aggregates.append(aggregate)

                # Update config entry
                new_data = dict(self.config_entry.data)
                new_data["aggregates"] = filtered_aggregates
                new_data["selected_aggregates"] = selected_aggregates

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                _LOGGER.debug(
                    "Aggregate options updated: %d of %d aggregates selected",
                    len(filtered_aggregates),
                    len(available_aggregates),
                )

                return self.async_create_entry(title="", data={})

            # Show aggregates selection form
            return self.async_show_form(
                step_id="aggregates_options",
                data_schema=self._get_aggregates_options_schema(
                    available_aggregates, current_selected
                ),
                description_placeholders={
                    "template_name": template_name,
                    "template_version": str(
                        self.config_entry.data.get("template_version", 1)
                    ),
                    "current_count": str(len(current_aggregates)),
                    "available_count": str(len(available_aggregates)),
                },
            )

        except Exception as e:
            _LOGGER.error("Error in aggregate options configuration: %s", str(e))
            return self.async_abort(
                reason="aggregates_options_error",
                description_placeholders={"error": str(e)},
            )

    def _get_aggregates_options_schema(
        self, available_aggregates: List[dict], current_selected: List[str]
    ) -> vol.Schema:
        """Generate schema for aggregates options configuration."""
        # Create options for aggregate selection
        aggregate_options = {}
        for i, aggregate in enumerate(available_aggregates):
            name = aggregate.get("name", f"Aggregate {i+1}")
            group = aggregate.get("group", "unknown")
            method = aggregate.get("method", "sum")
            aggregate_options[f"{i}"] = f"{name} ({group} - {method})"

        return vol.Schema(
            {
                vol.Required("selected_aggregates", default=current_selected): vol.All(
                    cv.multi_select(aggregate_options),
                    vol.Length(min=1, msg="Mindestens eine Aggregation auswählen"),
                )
            }
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
            from .__init__ import _filter_by_firmware_version

            filtered_sensors = _filter_by_firmware_version(
                all_sensors, new_firmware_version
            )
            filtered_calculated = _filter_by_firmware_version(
                all_calculated, new_firmware_version
            )
            filtered_controls = _filter_by_firmware_version(
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
