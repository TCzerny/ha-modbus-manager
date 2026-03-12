"""Config Flow for Modbus Manager."""

import asyncio
import copy
import json
import os
from signal import default_int_handler
from typing import Any, List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

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
from .device_utils import generate_unique_id
from .logger import ModbusManagerLogger
from .template_loader import (
    _evaluate_condition,
    get_template_by_name,
    get_template_names,
    set_hass_instance,
)

_LOGGER = ModbusManagerLogger(__name__)


def _is_prefix_unique_across_hubs(
    hass: HomeAssistant,
    prefix: str,
    exclude_entry_id: str | None = None,
    exclude_device_entry_id: str | None = None,
) -> bool:
    """Return True if prefix is unique across all hubs and devices."""
    if not prefix:
        return False

    normalized = str(prefix).strip().lower()
    if not normalized:
        return False

    for entry in hass.config_entries.async_entries(DOMAIN):
        # New structure: check all devices
        devices = entry.data.get("devices", [])
        if isinstance(devices, list) and devices:
            for device in devices:
                if (
                    exclude_entry_id
                    and entry.entry_id == exclude_entry_id
                    and exclude_device_entry_id
                    and device.get("device_entry_id") == exclude_device_entry_id
                ):
                    continue
                device_prefix = str(device.get("prefix", "")).strip().lower()
                if device_prefix and device_prefix == normalized:
                    return False
        else:
            # Legacy fallback: check top-level prefix
            if exclude_entry_id and entry.entry_id == exclude_entry_id:
                continue
            entry_prefix = str(entry.data.get("prefix", "")).strip().lower()
            if entry_prefix and entry_prefix == normalized:
                return False

    return True


class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Manager."""

    VERSION = 3

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self._templates = {}
        self._selected_template = None

    def _build_device_entry_id(self, device: dict[str, Any]) -> str:
        """Build a stable logical device id inside one hub entry."""
        prefix = str(device.get("prefix", "device")).strip() or "device"
        slave_id = str(device.get("slave_id", 1)).strip() or "1"
        template = str(device.get("template", "template")).strip() or "template"
        return f"{prefix}_{slave_id}_{template}"

    def _normalize_device_record(self, device: dict[str, Any]) -> dict[str, Any]:
        """Normalize a device record and ensure required subentry-like fields."""
        normalized = dict(device)
        if not normalized.get("type"):
            normalized["type"] = "inverter"
        normalized["device_entry_id"] = normalized.get(
            "device_entry_id", self._build_device_entry_id(normalized)
        )
        return normalized

    async def async_migrate_entry(
        self, hass: HomeAssistant, config_entry: config_entries.ConfigEntry
    ):
        """Migrate old config entries to new devices array structure."""
        _LOGGER.info(
            "Migration handler called for entry %s (version %d -> %d)",
            config_entry.entry_id,
            config_entry.version,
            self.VERSION,
        )

        # Migration is needed only for older entry versions.
        if config_entry.version < self.VERSION:
            _LOGGER.info(
                "Migrating config entry %s from version %d to %d",
                config_entry.entry_id,
                config_entry.version,
                self.VERSION,
            )

            # Create new data with devices array
            new_data = dict(config_entry.data)
            existing_devices = new_data.get("devices")

            # Keep existing devices list order/values and only backfill required fields.
            if isinstance(existing_devices, list) and existing_devices:
                normalized_devices = []
                for idx, device in enumerate(existing_devices):
                    if isinstance(device, dict):
                        normalized_devices.append(self._normalize_device_record(device))
                    else:
                        _LOGGER.warning(
                            "Skipping invalid non-dict device at index %d during migration for entry %s",
                            idx,
                            config_entry.entry_id,
                        )
                new_data["devices"] = normalized_devices
            else:
                # Legacy path: build devices list from top-level keys
                prefix = new_data.get("prefix", "unknown")
                template = new_data.get("template")
                slave_id = new_data.get("slave_id", 1)
                battery_template = new_data.get("battery_template")
                battery_prefix = new_data.get("battery_prefix", "SBR")
                battery_slave_id = new_data.get("battery_slave_id", 200)

                devices = []

                # Add main device (inverter)
                if template:
                    main_device = {
                        "prefix": prefix,
                        "template": template,
                        "slave_id": slave_id,
                        "type": "inverter",
                        "registers": new_data.get("registers", []),
                        "calculated_entities": new_data.get("calculated_entities", []),
                        "controls": new_data.get("controls", []),
                        "binary_sensors": new_data.get("binary_sensors", []),
                    }

                    # Add dynamic config if present
                    if "phases" in new_data:
                        main_device["phases"] = new_data.get("phases")
                    if "mppt_count" in new_data:
                        main_device["mppt_count"] = new_data.get("mppt_count")
                    if "string_count" in new_data:
                        main_device["string_count"] = new_data.get("string_count")
                    if "modules" in new_data:
                        main_device["modules"] = new_data.get("modules")
                    if "firmware_version" in new_data:
                        main_device["firmware_version"] = new_data.get(
                            "firmware_version"
                        )
                    if "connection_type" in new_data:
                        main_device["connection_type"] = new_data.get("connection_type")
                    if "selected_model" in new_data:
                        main_device["selected_model"] = new_data.get("selected_model")

                    devices.append(self._normalize_device_record(main_device))

                # Add battery device if configured
                if battery_template:
                    battery_device = {
                        "prefix": battery_prefix,
                        "template": battery_template,
                        "slave_id": battery_slave_id,
                        "type": "battery",
                    }

                    # Add battery-specific config
                    if "battery_modules" in new_data:
                        battery_device["modules"] = new_data.get("battery_modules")
                    if "battery_model" in new_data:
                        battery_device["selected_model"] = new_data.get("battery_model")

                    devices.append(self._normalize_device_record(battery_device))

                new_data["devices"] = devices

            # Create hub config if not present
            if "hub" not in new_data:
                new_data["hub"] = {
                    "host": new_data.get("host", "unknown"),
                    "port": new_data.get("port", 502),
                    "timeout": new_data.get("timeout", 3),
                    "delay": new_data.get("delay", 0),
                }

            # Migrate modbus_type if present as "type"
            if "type" in new_data and "modbus_type" not in new_data:
                new_data["modbus_type"] = new_data.pop("type")

            # Update config entry
            hass.config_entries.async_update_entry(
                config_entry, data=new_data, version=self.VERSION
            )

            _LOGGER.info(
                "Successfully migrated config entry to version %d with %d device(s)",
                self.VERSION,
                len(new_data.get("devices", [])),
            )
            return True

        return True

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
            # Required for first-ever integration setup so user templates from
            # config/modbus_manager/templates are visible immediately.
            set_hass_instance(self.hass)
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
                    _LOGGER.debug("=== TEMPLATE SELECTION DEBUG ===")
                    _LOGGER.debug("Selected template: %s", self._selected_template)

                    # Debug template data
                    template_data = self._templates.get(self._selected_template, {})
                    _LOGGER.debug("Template data keys: %s", list(template_data.keys()))
                    _LOGGER.debug(
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
            # Sort template names alphabetically for better UX
            template_names = sorted(list(self._templates.keys()))
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("template"): vol.In(template_names),
                    }
                ),
                description_placeholders={
                    "config_flow_note": "",
                    "template_count": str(len(template_names)),
                    "template_list": ", ".join(template_names),
                },
            )

        except Exception as e:
            _LOGGER.error("Error in Config Flow: %s", str(e))
            return self.async_abort(
                reason="unknown_error", description_placeholders={"error": str(e)}
            )

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle hub-level reconfigure flow (no device edit here)."""
        config_entry = self._get_reconfigure_entry()
        if config_entry is None:
            return self.async_abort(
                reason="config_error",
                description_placeholders={"error": "No config entry for reconfigure"},
            )

        if user_input is not None:
            new_data = dict(config_entry.data)
            new_data["timeout"] = user_input.get(
                "timeout", config_entry.data.get("timeout", DEFAULT_TIMEOUT)
            )
            new_data["delay"] = user_input.get(
                "delay", config_entry.data.get("delay", DEFAULT_DELAY)
            )
            new_data["message_wait_milliseconds"] = user_input.get(
                "message_wait_milliseconds",
                config_entry.data.get(
                    "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                ),
            )
            self.hass.config_entries.async_update_entry(config_entry, data=new_data)
            await self.hass.config_entries.async_reload(config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "timeout",
                        default=config_entry.data.get("timeout", DEFAULT_TIMEOUT),
                    ): int,
                    vol.Required(
                        "delay", default=config_entry.data.get("delay", DEFAULT_DELAY)
                    ): int,
                    vol.Required(
                        "message_wait_milliseconds",
                        default=config_entry.data.get(
                            "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                        ),
                    ): int,
                }
            ),
        )

    # Step 2a: User selected a template with dynamic config
    # show the connection step for the modbus connection setup
    async def async_step_connection(self, user_input: dict = None) -> FlowResult:
        """Handle connection parameters step for dynamic templates."""
        if user_input is not None:
            # Backward-compatible normalization: older flow used "request_delay".
            if (
                "message_wait_milliseconds" not in user_input
                and "request_delay" in user_input
            ):
                user_input["message_wait_milliseconds"] = user_input["request_delay"]
            user_input.pop("request_delay", None)

            # Store connection parameters
            self._connection_params = user_input

            # Proceed directly to dynamic config
            _LOGGER.info("Connection parameters stored, proceeding to dynamic config")
            return await self.async_step_dynamic_config()

        # Get template defaults for prefilling
        template_data = self._templates.get(self._selected_template, {})
        default_prefix = template_data.get("default_prefix", "SG")
        default_slave_id = template_data.get("default_slave_id", DEFAULT_SLAVE)
        # Show config_flow_note when selected template has one (e.g. SBR: LAN required)
        config_flow_note = template_data.get("config_flow_note", "") or ""

        # Show connection parameters form
        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Required("prefix", default=default_prefix): str,
                    vol.Required("host"): str,
                    vol.Optional("port", default=DEFAULT_PORT): int,
                    vol.Optional("slave_id", default=default_slave_id): int,
                    vol.Optional("modbus_type", default="tcp"): vol.In(
                        {
                            "tcp": "TCP",
                            "rtuovertcp": "RTU over TCP",
                        }
                    ),
                    vol.Optional("timeout", default=DEFAULT_TIMEOUT): int,
                    vol.Optional("delay", default=DEFAULT_DELAY): int,
                    vol.Optional(
                        "message_wait_milliseconds", default=DEFAULT_MESSAGE_WAIT_MS
                    ): int,
                }
            ),
            description_placeholders={
                "template_name": self._selected_template,
                "config_flow_note": config_flow_note,
            },
        )

    async def async_step_rtu_parameters(self, user_input: dict = None) -> FlowResult:
        """Handle RTU-specific parameters step (for dynamic config flow)."""
        if user_input is not None:
            # Merge RTU parameters with connection parameters
            self._connection_params.update(user_input)
            return await self.async_step_dynamic_config()

        # Show RTU parameters form
        return self.async_show_form(
            step_id="rtu_parameters",
            data_schema=vol.Schema(
                {
                    vol.Required("baudrate", default=9600): vol.In(
                        [9600, 19200, 38400, 57600, 115200]
                    ),
                    vol.Required("data_bits", default=8): vol.In([7, 8]),
                    vol.Required("stop_bits", default=1): vol.In([1, 2]),
                    vol.Required("parity", default="none"): vol.In(
                        ["none", "even", "odd"]
                    ),
                }
            ),
            description_placeholders={
                "template_name": self._selected_template,
            },
        )

    async def async_step_rtu_parameters_device(
        self, user_input: dict = None
    ) -> FlowResult:
        """Handle RTU-specific parameters step (for device config flow)."""
        if user_input is not None:
            # Merge RTU parameters with device config input
            self._device_config_input.update(user_input)
            battery_config = self._device_config_input.get("battery_config")
            _LOGGER.debug(
                "Battery config: %s, proceeding to final config", battery_config
            )
            return await self.async_step_final_config(self._device_config_input)

        # Show RTU parameters form
        return self.async_show_form(
            step_id="rtu_parameters_device",
            data_schema=vol.Schema(
                {
                    vol.Required("baudrate", default=9600): vol.In(
                        [9600, 19200, 38400, 57600, 115200]
                    ),
                    vol.Required("data_bits", default=8): vol.In([7, 8]),
                    vol.Required("stop_bits", default=1): vol.In([1, 2]),
                    vol.Required("parity", default="none"): vol.In(
                        ["none", "even", "odd"]
                    ),
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

            _LOGGER.debug("=== BATTERY DETECTION DEBUG ===")
            _LOGGER.debug("Selected template: %s", self._selected_template)
            _LOGGER.debug("Template data keys: %s", list(template_data.keys()))
            _LOGGER.debug("Template type: '%s'", template_type)
            _LOGGER.debug(
                "Template type == 'pv_inverter': %s", template_type == "pv_inverter"
            )
            _LOGGER.debug(
                "Template type.lower() == 'pv_inverter': %s",
                template_type.lower() == "pv_inverter",
            )
            _LOGGER.debug(
                "Template type.lower() in ['pv_inverter', 'pv_hybrid_inverter']: %s",
                template_type.lower() in ["pv_inverter", "pv_hybrid_inverter"],
            )

            # Check for PV inverter (case-insensitive) - support both PV_inverter and PV_Hybrid_Inverter
            if template_type.lower() in [
                "pv_inverter",
                "pv_hybrid_inverter",
            ] and self._supports_battery_config(template_data):
                # Check battery_config condition (e.g. connection_type != WINET - skip battery when WINET)
                battery_config_def = template_data.get("dynamic_config", {}).get(
                    "battery_config", {}
                )
                condition = (
                    battery_config_def.get("condition")
                    if isinstance(battery_config_def, dict)
                    else None
                )
                if condition and not _evaluate_condition(condition, combined_input):
                    _LOGGER.info(
                        "Skipping battery flow: condition '%s' not met (connection_type=%s)",
                        condition,
                        combined_input.get("connection_type"),
                    )
                    self._inverter_config = combined_input
                    self._inverter_config["battery_config"] = "none"
                    self._inverter_config["battery_template"] = "none"
                    self._keep_inverter_battery_entities = False
                    return await self.async_step_finalize_inverter_without_battery()

                # Store the inverter config and ask about battery
                self._inverter_config = combined_input
                # Persist connection_type in flow context (survives flow restoration between steps)
                self.context["connection_type"] = combined_input.get(
                    "connection_type", "LAN"
                )
                _LOGGER.debug("PV inverter detected - proceeding to battery detection")
                return await self.async_step_battery_detection()
            else:
                # For non-PV inverters, proceed directly to final config
                _LOGGER.debug("Non-PV inverter - proceeding directly to final config")
                return await self.async_step_final_config(combined_input)

        # Get template data
        template_data = self._templates.get(self._selected_template, {})

        # Generate schema for dynamic config using the helper function
        # Get current user_input for dynamic schema updates (e.g., when model changes)
        schema_fields = self._get_dynamic_config_schema(template_data, user_input)

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
            # Store user input
            self._device_config_input = user_input

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
                vol.Optional("modbus_type", default="tcp"): vol.In(
                    {
                        "tcp": "TCP",
                        "rtuovertcp": "RTU over TCP",
                    }
                ),
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
        _LOGGER.debug(
            "_supports_dynamic_config: template_data keys=%s, has_dynamic=%s",
            list(template_data.keys()),
            has_dynamic,
        )

        return has_dynamic

    def _supports_battery_config(self, template_data: dict) -> bool:
        """Check if template defines a battery_config dynamic section."""
        dynamic_config = template_data.get("dynamic_config", {})
        has_battery_config = isinstance(dynamic_config.get("battery_config"), dict)
        _LOGGER.debug(
            "_supports_battery_config: template_data keys=%s, has_battery_config=%s",
            list(template_data.keys()),
            has_battery_config,
        )
        return has_battery_config

    def _get_dynamic_config_schema(
        self, template_data: dict, user_input: dict = None
    ) -> dict:
        """Generate dynamic configuration schema based on template."""
        dynamic_config = template_data.get("dynamic_config", {})
        schema_fields = {}

        # Check if template has valid_models (model selection)
        # Look for valid_models in dynamic_config first, then at template root level
        valid_models = dynamic_config.get("valid_models") or template_data.get(
            "valid_models"
        )

        # Get selected_model from user_input if available (for dynamic updates)
        selected_model = None
        if user_input:
            selected_model = user_input.get("selected_model")

        # Get model config if selected_model is available
        model_config = {}
        if selected_model and valid_models and isinstance(valid_models, dict):
            model_config = valid_models.get(selected_model, {})

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

            default_model = next(iter(model_options)) if model_options else None
            if default_model is not None:
                # Use selected_model from user_input if available, otherwise use default
                current_model = (
                    selected_model
                    if selected_model and selected_model in model_options
                    else default_model
                )
                schema_fields[
                    vol.Required("selected_model", default=current_model)
                ] = vol.In(model_options)

        # Fields that should be hidden when template has valid_models (they're defined by the model)
        model_defined_fields = ["phases", "mppt_count", "string_count"]

        # If template has valid_models, these fields should NEVER be shown
        # because they are always defined by the selected model
        should_hide_model_fields = bool(valid_models and isinstance(valid_models, dict))

        # Process ALL configurable fields from dynamic_config (works for both valid_models and individual fields)
        # This ensures that fields like dual_channel_meter are always available
        for field_name, field_config in dynamic_config.items():
            # Skip special fields that are handled separately
            if field_name in [
                "valid_models",
                "firmware_version",
                "connection_type",
                "battery_slave_id",
            ]:
                continue
            if field_name == "battery_config" and self._supports_battery_config(
                template_data
            ):
                continue

            # Skip if already added (e.g., selected_model)
            if field_name in schema_fields:
                continue

            # Skip fields that are defined by models if template has valid_models
            if should_hide_model_fields and field_name in model_defined_fields:
                _LOGGER.debug(
                    "Skipping field %s - template has valid_models, field will be defined by selected model",
                    field_name,
                )
                continue

            # Check if this field has options (making it configurable)
            if isinstance(field_config, dict) and "options" in field_config:
                options = field_config.get("options", [])
                default = field_config.get("default", options[0] if options else None)

                if options:
                    # Handle boolean fields specially
                    if all(isinstance(opt, bool) for opt in options) or (
                        len(options) == 2 and set(options) == {True, False}
                    ):
                        # Boolean field with options [true, false] or [True, False]
                        schema_fields[
                            vol.Optional(field_name, default=bool(default))
                        ] = bool
                        _LOGGER.debug(
                            "Added boolean field %s with default: %s",
                            field_name,
                            default,
                        )
                    else:
                        # Regular options field
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
                if isinstance(default_value, bool):
                    schema_fields[
                        vol.Optional(field_name, default=default_value)
                    ] = bool
                elif isinstance(default_value, int):
                    # Check if min/max constraints are specified
                    min_value = field_config.get("min")
                    max_value = field_config.get("max")
                    if min_value is not None or max_value is not None:
                        # Apply range validation for integer fields
                        validators = [vol.Coerce(int)]
                        if min_value is not None or max_value is not None:
                            validators.append(
                                vol.Range(
                                    min=min_value if min_value is not None else 1,
                                    max=max_value if max_value is not None else 65535,
                                )
                            )
                        schema_fields[
                            vol.Optional(field_name, default=default_value)
                        ] = vol.All(*validators)
                        _LOGGER.debug(
                            "Added integer field %s with default: %s, min: %s, max: %s",
                            field_name,
                            default_value,
                            min_value,
                            max_value,
                        )
                    else:
                        schema_fields[
                            vol.Optional(field_name, default=default_value)
                        ] = int
                        _LOGGER.debug(
                            "Added integer field %s with default: %s",
                            field_name,
                            default_value,
                        )
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
        # SunSpec model address fields are now handled automatically via dynamic_config
        # They will be added by the generic loop above if defined in template's dynamic_config

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
            dynamic_config["selected_model"] = selected_model
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
                    # Store model config values in dynamic_config for condition filtering
                    # This ensures model-specific values are available and not overwritten by defaults
                    dynamic_config[field_name] = field_value

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
                modules = 3
        else:
            # Individual field configuration - generic for any device type
            # Extract all configurable fields dynamically
            # Safe access: config values may be overwritten with primitives
            def _safe_default(config: dict, key: str, default: Any) -> Any:
                val = config.get(key, {})
                return val.get("default", default) if isinstance(val, dict) else default

            phases = user_input.get(
                "phases", _safe_default(dynamic_config, "phases", 3)
            )
            mppt_count = user_input.get(
                "mppt_count", _safe_default(dynamic_config, "mppt_count", 1)
            )
            string_count = user_input.get(
                "string_count", _safe_default(dynamic_config, "string_count", 1)
            )
            modules = user_input.get(
                "modules", _safe_default(dynamic_config, "modules", 3)
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
                    default_val = (
                        field_config.get("default", "unknown")
                        if isinstance(field_config, dict)
                        else "unknown"
                    )
                    field_value = user_input.get(field_name, default_val)
                    individual_fields.append(f"{field_name}={field_value}")

            _LOGGER.debug(
                "Using individual field configuration: %s",
                ", ".join(individual_fields),
            )

        # Safe access: battery_config may be overwritten with string (e.g. "none")
        battery_config_val = dynamic_config.get("battery_config", {})
        battery_default = (
            battery_config_val.get("default", "none")
            if isinstance(battery_config_val, dict)
            else "none"
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
            battery_config = "sbr_battery"  # Set battery_config for condition filtering
        else:
            battery_enabled = battery_config != "none"
            battery_type = battery_config

        # Handle "Latest" firmware version - use the highest available version
        if firmware_version == "Latest":
            firmware_config = dynamic_config.get("firmware_version", {})
            available_firmware = (
                firmware_config.get("options", [])
                if isinstance(firmware_config, dict)
                else []
            )

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

        # Add modules to dynamic_config for condition filtering
        if selected_model and model_config:
            dynamic_config["modules"] = modules
        else:
            # For individual field configuration, add all fields to dynamic_config
            dynamic_config["modules"] = modules

        # Add ALL user input fields to dynamic_config for condition filtering
        # This ensures fields like meter_type, dual_channel_meter are available for condition checks
        for field_name, field_value in user_input.items():
            if field_name not in [
                "valid_models",
                "firmware_version",
                "connection_type",
                "battery_slave_id",
                "selected_model",  # Already handled separately
            ]:
                # Store the actual value from user_input, or use default from dynamic_config
                if field_name in dynamic_config:
                    field_config = dynamic_config[field_name]
                    if isinstance(field_config, dict) and "default" in field_config:
                        # Use user input value if provided, otherwise use default
                        dynamic_config[field_name] = user_input.get(
                            field_name, field_config.get("default")
                        )
                    else:
                        # Field exists but no default, use user input value
                        dynamic_config[field_name] = field_value
                else:
                    # New field not in dynamic_config, add it
                    dynamic_config[field_name] = field_value

        # Also ensure all fields from dynamic_config with defaults are in dynamic_config
        # This is important for fields that might not be in user_input (e.g., when using defaults)
        # BUT: Don't overwrite values that came from selected_model - those are already set above
        # We need to check the original template_data, not the already-modified dynamic_config
        original_dynamic_config = template_data.get("dynamic_config", {})
        for field_name, field_config in original_dynamic_config.items():
            if field_name not in [
                "valid_models",
                "firmware_version",
                "connection_type",
                "battery_slave_id",
            ]:
                if isinstance(field_config, dict) and "default" in field_config:
                    # If field not already set from user_input or selected_model, use default
                    # Check if it's still a dict (meaning it wasn't set) or if it's missing
                    # Don't overwrite if it's already a concrete value (not a dict)
                    if field_name not in dynamic_config or isinstance(
                        dynamic_config.get(field_name), dict
                    ):
                        dynamic_config[field_name] = field_config.get("default")
                        _LOGGER.debug(
                            "Setting default value for %s: %s",
                            field_name,
                            field_config.get("default"),
                        )

        # Log meter_type if present for debugging
        meter_type = dynamic_config.get("meter_type", "not_set")
        _LOGGER.debug(
            "Processing dynamic config: phases=%d, mppt=%d, battery=%s, battery_type=%s, fw=%s, conn=%s, meter_type=%s",
            phases,
            mppt_count,
            battery_enabled,
            battery_type,
            firmware_version,
            connection_type,
            meter_type,
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

        # Check firmware_min_version filter first
        sensor_firmware_min = sensor.get("firmware_min_version")
        if sensor_firmware_min and firmware_version:
            try:
                from packaging import version

                # Compare firmware versions
                current_ver = version.parse(firmware_version)
                min_ver = version.parse(sensor_firmware_min)
                if current_ver < min_ver:
                    _LOGGER.debug(
                        "Excluding sensor due to firmware version: %s (unique_id: %s, requires: %s, current: %s)",
                        sensor.get("name", "unknown"),
                        sensor.get("unique_id", "unknown"),
                        sensor_firmware_min,
                        firmware_version,
                    )
                    return False
            except Exception:
                # Fallback to string comparison for non-semantic versions
                try:
                    if firmware_version < sensor_firmware_min:
                        _LOGGER.debug(
                            "Excluding sensor due to firmware version (string): %s (unique_id: %s, requires: %s, current: %s)",
                            sensor.get("name", "unknown"),
                            sensor.get("unique_id", "unknown"),
                            sensor_firmware_min,
                            firmware_version,
                        )
                        return False
                except Exception as e:
                    # If comparison fails, include the sensor (better safe than sorry)
                    _LOGGER.debug(
                        "Could not compare firmware versions for sensor %s: %s",
                        sensor.get("name", "unknown"),
                        str(e),
                    )

        # Check condition filter
        condition = sensor.get("condition")
        if condition:
            if not _evaluate_condition(condition, dynamic_config):
                _LOGGER.debug(
                    "Excluding sensor due to condition '%s': %s (unique_id: %s)",
                    condition,
                    sensor.get("name", "unknown"),
                    sensor.get("unique_id", "unknown"),
                )
                return False

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

    def _evaluate_single_condition(self, condition: str, dynamic_config: dict) -> bool:
        """Evaluate a single condition (no AND/OR).

        Supports:
        - "variable == value" (string, int, bool)
        - "variable != value" (string, int, bool)
        - "variable >= value" (int)
        - "variable in [value1, value2]" (string list)
        - "variable not in [value1, value2]" (string list)
        """
        condition = condition.strip()

        if " not in " in condition:
            try:
                parts = condition.split(" not in ")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_values_str = parts[1].strip()

                    actual_value = dynamic_config.get(variable_name)

                    if required_values_str.startswith(
                        "["
                    ) and required_values_str.endswith("]"):
                        required_values_str = required_values_str[1:-1]
                    required_values = [
                        value.strip().strip("'\"")
                        for value in required_values_str.split(",")
                        if value.strip()
                    ]

                    if isinstance(actual_value, (list, tuple, set)):
                        actual_values = {str(value) for value in actual_value}
                        return not any(
                            value in actual_values for value in required_values
                        )
                    return str(actual_value) not in required_values
            except (ValueError, IndexError):
                return False
        elif " in " in condition:
            try:
                parts = condition.split(" in ")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_values_str = parts[1].strip()

                    actual_value = dynamic_config.get(variable_name)

                    if required_values_str.startswith(
                        "["
                    ) and required_values_str.endswith("]"):
                        required_values_str = required_values_str[1:-1]
                    required_values = [
                        value.strip().strip("'\"")
                        for value in required_values_str.split(",")
                        if value.strip()
                    ]

                    if isinstance(actual_value, (list, tuple, set)):
                        actual_values = {str(value) for value in actual_value}
                        return any(value in actual_values for value in required_values)
                    return str(actual_value) in required_values
            except (ValueError, IndexError):
                return False
        elif "!=" in condition:
            try:
                parts = condition.split("!=")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip().strip("'\"")

                    actual_value = dynamic_config.get(variable_name)

                    if required_value_str.lower() in ["true", "false"]:
                        required_value = required_value_str.lower() == "true"
                        actual_value = (
                            bool(actual_value) if actual_value is not None else False
                        )
                    else:
                        try:
                            required_value = int(required_value_str)
                            actual_value = (
                                int(actual_value) if actual_value is not None else 0
                            )
                        except (ValueError, TypeError):
                            required_value = required_value_str
                            actual_value = (
                                str(actual_value) if actual_value is not None else ""
                            )

                    return actual_value != required_value
            except (ValueError, IndexError):
                return False
        elif "==" in condition:
            try:
                parts = condition.split("==")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip().strip("'\"")

                    actual_value = dynamic_config.get(variable_name)

                    if required_value_str.lower() in ["true", "false"]:
                        required_value = required_value_str.lower() == "true"
                        actual_value = (
                            bool(actual_value) if actual_value is not None else False
                        )
                    else:
                        try:
                            required_value = int(required_value_str)
                            actual_value = (
                                int(actual_value) if actual_value is not None else 0
                            )
                        except (ValueError, TypeError):
                            required_value = required_value_str
                            actual_value = (
                                str(actual_value) if actual_value is not None else ""
                            )

                    return actual_value == required_value
            except (ValueError, IndexError):
                return False
        elif ">=" in condition:
            try:
                parts = condition.split(">=")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip()

                    try:
                        required_value = int(required_value_str)
                        actual_value = dynamic_config.get(variable_name, 0)
                        if isinstance(actual_value, str):
                            actual_value = int(actual_value)
                        return actual_value >= required_value
                    except ValueError:
                        return False
            except (ValueError, IndexError):
                return False

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
        _LOGGER.debug("=== BATTERY DETECTION STEP CALLED ===")
        _LOGGER.debug("User input: %s", user_input)

        if user_input is not None:
            _LOGGER.debug("Battery available: %s", user_input.get("battery_available"))
            if user_input.get("battery_available"):
                return await self.async_step_battery_template_selection()
            else:
                if self._inverter_config is not None:
                    self._inverter_config["battery_config"] = "none"
                    self._inverter_config["battery_template"] = "none"
                self._keep_inverter_battery_entities = False
                # No battery - filter battery registers and proceed to final config
                return await self.async_step_finalize_inverter_without_battery()

        # Get inverter info for display
        inverter_prefix = self._inverter_config.get("prefix", "SG")
        inverter_host = self._inverter_config.get("host", "unknown")

        _LOGGER.debug(
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
                "config_flow_note": "",
            },
        )

    # Step 5: Battery template selection
    async def async_step_battery_template_selection(
        self, user_input: dict = None
    ) -> FlowResult:
        """Select battery template."""
        if user_input is not None:
            selected_template = user_input["battery_template"]
            if selected_template == "other":
                self._selected_battery_template = None
                if self._inverter_config is not None:
                    self._inverter_config["battery_config"] = "other"
                    self._inverter_config["battery_template"] = "other"
                self._keep_inverter_battery_entities = True
                return await self.async_step_finalize_inverter_with_other_battery()

            self._selected_battery_template = selected_template
            if self._inverter_config is not None:
                self._inverter_config["battery_config"] = selected_template
                self._inverter_config["battery_template"] = selected_template
            self._keep_inverter_battery_entities = True
            return await self.async_step_battery_config()

        # Get available battery templates
        battery_templates = {}
        template_names = await get_template_names()
        # Read connection_type from inverter_config; fallback to flow context
        # (context persists when flow is serialized between steps, _inverter_config may not)
        connection_type = "LAN"
        if self._inverter_config and "connection_type" in self._inverter_config:
            connection_type = self._inverter_config["connection_type"]
        elif self.context.get("connection_type"):
            connection_type = self.context["connection_type"]
        # Normalize for comparison (WINET/Winet/LAN etc.)
        connection_type_norm = (
            str(connection_type).strip().upper() if connection_type else "LAN"
        )
        source = (
            "inverter_config"
            if (self._inverter_config and "connection_type" in self._inverter_config)
            else "flow_context"
        )
        _LOGGER.info(
            "Battery template filter: connection_type=%s (from %s), SBR will be %s",
            connection_type,
            source,
            "hidden" if connection_type_norm == "WINET" else "shown",
        )

        filtered_out_notes = []
        for template_name in template_names:
            template_data = await get_template_by_name(template_name)
            if template_data and isinstance(template_data, dict):
                template_type = template_data.get("type", "")
                if template_type == "battery":
                    # Filter by requires_connection_type (e.g. SBR needs LAN, not WiNet-S)
                    required_conn = template_data.get("requires_connection_type")
                    if required_conn:
                        required_norm = str(required_conn).strip().upper()
                        if connection_type_norm != required_norm:
                            _LOGGER.info(
                                "Excluding battery template %s: requires connection %s, current is %s",
                                template_name,
                                required_conn,
                                connection_type,
                            )
                            note = template_data.get("config_flow_note", "")
                            if note:
                                filtered_out_notes.append(f"{template_name}: {note}")
                            continue
                    display_name = template_data.get("display_name", template_name)
                    battery_templates[template_name] = display_name

        config_flow_note = ""
        if filtered_out_notes:
            config_flow_note = "Filtered out (connection type): " + "; ".join(
                filtered_out_notes
            )

        if not battery_templates:
            battery_templates = {"other": "Other (no template)"}
        else:
            # Sort battery templates alphabetically by display name for better UX
            sorted_battery_templates = dict(
                sorted(battery_templates.items(), key=lambda x: x[1])
            )
            battery_templates = {
                **sorted_battery_templates,
                "other": "Other (no template)",
            }

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
                "config_flow_note": config_flow_note,
            },
        )

    # Step 6: Battery configuration
    async def async_step_battery_config(self, user_input: dict = None) -> FlowResult:
        """Configure battery settings."""
        if user_input is not None:
            battery_prefix = user_input.get("battery_prefix")
            if not _is_prefix_unique_across_hubs(self.hass, battery_prefix):
                return self.async_abort(
                    reason="invalid_config",
                    description_placeholders={
                        "error": (
                            f"Prefix '{battery_prefix}' already exists. "
                            "Please choose a unique prefix."
                        )
                    },
                )

            # Store battery config and proceed directly to finalization
            self._battery_config = user_input
            if self._inverter_config is not None and self._selected_battery_template:
                self._inverter_config[
                    "battery_config"
                ] = self._selected_battery_template
                self._inverter_config[
                    "battery_template"
                ] = self._selected_battery_template

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
                        _LOGGER.debug(
                            "Selected battery model %s has %d modules",
                            selected_model,
                            modules,
                        )

            _LOGGER.debug("Battery config completed - proceeding to finalization")
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

        _LOGGER.debug(
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

            _LOGGER.debug("Battery template has valid_models: %s", model_options)
        else:
            # Fallback to simple module count if no valid_models
            schema_fields[vol.Optional("battery_modules", default=1)] = int
            _LOGGER.debug(
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
            if self._inverter_config is not None:
                self._inverter_config["battery_config"] = "none"
                self._inverter_config["battery_template"] = "none"
            # Filter battery registers from inverter template
            filtered_config = self._filter_battery_registers_from_inverter()
            return await self.async_step_final_config(filtered_config)
        except Exception as e:
            _LOGGER.error("Error finalizing inverter without battery: %s", str(e))
            return self.async_abort(
                reason="finalization_error", description_placeholders={"error": str(e)}
            )

    async def async_step_finalize_inverter_with_other_battery(self) -> FlowResult:
        """Create inverter entry with inverter-only battery entities (no template)."""
        try:
            if self._inverter_config is not None:
                self._inverter_config["battery_config"] = "other"
                self._inverter_config["battery_template"] = "other"
            return await self.async_step_final_config(self._inverter_config)
        except Exception as e:
            _LOGGER.error("Error finalizing inverter with other battery: %s", str(e))
            return self.async_abort(
                reason="finalization_error", description_placeholders={"error": str(e)}
            )

    # Step 8: Finalize inverter with battery
    async def async_step_finalize_inverter_with_battery(self) -> FlowResult:
        """Create both inverter and battery entries."""
        try:
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

            _LOGGER.debug(
                "Filtering battery groups from inverter template: %s",
                self._selected_template,
            )
            _LOGGER.debug("Battery groups to filter: %s", battery_groups)

            # Filter sensors based on groups
            if "sensors" in inverter_template_data:
                original_count = len(inverter_template_data["sensors"])
                inverter_template_data["sensors"] = [
                    sensor
                    for sensor in inverter_template_data["sensors"]
                    if not self._is_battery_group_sensor(sensor, battery_groups)
                ]
                filtered_count = original_count - len(inverter_template_data["sensors"])
                _LOGGER.debug(
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
                _LOGGER.debug(
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
                _LOGGER.debug(
                    "Filtered %d battery binary sensors from inverter template",
                    filtered_count,
                )

            _LOGGER.debug(
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
            _LOGGER.debug("Filtering battery template for %d modules", module_count)

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
                _LOGGER.debug(
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
                _LOGGER.debug(
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
                _LOGGER.debug(
                    "Filtered %d binary sensors for %d modules (kept %d)",
                    filtered_count,
                    module_count,
                    len(filtered_template["binary_sensors"]),
                )

            _LOGGER.debug(
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
            _LOGGER.debug("Battery will be configured for %d modules", module_count)

            # Create devices array structure
            devices = []

            # Get inverter template data for version info
            inverter_template_data = await get_template_by_name(self._selected_template)

            # Add inverter device - copy all dynamic_config fields from _inverter_config
            inverter_device = {
                "type": "inverter",
                "template": self._selected_template,
                "prefix": self._inverter_config.get("prefix"),
                "slave_id": self._inverter_config.get("slave_id"),
                "selected_model": self._inverter_config.get("selected_model"),
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
            # Copy all dynamic_config fields (entity_ids_without_prefix, meter_type, etc.)
            inverter_dynamic_config = inverter_template_data.get("dynamic_config", {})
            if isinstance(inverter_dynamic_config, dict):
                for field_name in inverter_dynamic_config.keys():
                    if field_name in (
                        "valid_models",
                        "battery_config",
                        "battery_slave_id",
                    ):
                        continue
                    if field_name in self._inverter_config:
                        inverter_device[field_name] = self._inverter_config[field_name]

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

            devices.append(self._normalize_device_record(inverter_device))
            devices.append(self._normalize_device_record(battery_device))

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

            _LOGGER.debug("Devices array structure created:")
            _LOGGER.debug(
                "  Inverter: %s (prefix: %s, slave_id: %s, model: %s, fw: %s)",
                inverter_device["template"],
                inverter_device["prefix"],
                inverter_device["slave_id"],
                inverter_device["selected_model"],
                inverter_device["firmware_version"],
            )
            _LOGGER.debug(
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
            if not (
                template_registers
                or template_calculated
                or template_controls
                or template_binary_sensors
            ):
                _LOGGER.error("Template %s has no entities", self._selected_template)
                return self.async_abort(
                    reason="no_registers",
                    description_placeholders={
                        "error": f"Template {self._selected_template} has no entities"
                    },
                )

            # Validate configuration
            if not self._validate_config(user_input):
                return self.async_abort(
                    reason="invalid_config",
                    description_placeholders={"error": "Invalid configuration"},
                )

            # Enforce globally unique prefix across all hubs/devices
            if not _is_prefix_unique_across_hubs(self.hass, user_input["prefix"]):
                return self.async_abort(
                    reason="invalid_config",
                    description_placeholders={
                        "error": (
                            f"Prefix '{user_input['prefix']}' already exists. "
                            "Please choose a unique prefix."
                        )
                    },
                )

            # Get firmware version from user input or template default
            firmware_version = user_input.get(
                "firmware_version", template_data.get("firmware_version", "1.0.0")
            )

            # Check if devices array already exists (from battery subentry creation)
            if "devices" in user_input and user_input["devices"]:
                # Use existing devices array (e.g., from battery subentry)
                devices = [
                    self._normalize_device_record(d) for d in user_input["devices"]
                ]
                _LOGGER.debug(
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

                # Add all dynamic config fields to device (e.g., dual_channel_meter)
                if self._supports_dynamic_config(template_data):
                    dynamic_config_dict = config_values.get("dynamic_config", {})
                    for key, value in dynamic_config_dict.items():
                        if key not in [
                            "valid_models",
                            "firmware_version",
                            "connection_type",
                            "battery_slave_id",
                        ]:
                            device[key] = value

                devices.append(self._normalize_device_record(device))
                _LOGGER.debug("Created new devices array with single device")

            config_data = {
                "hub": {
                    "host": user_input["host"],
                    "port": user_input.get("port", DEFAULT_PORT),
                    "timeout": user_input.get("timeout", DEFAULT_TIMEOUT),
                    "delay": user_input.get("delay", DEFAULT_DELAY),
                    "message_wait_milliseconds": user_input.get(
                        "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                    ),
                },
                "devices": devices,
                # Keep legacy fields for backward compatibility
                "template": self._selected_template,
                "prefix": user_input["prefix"],
                "modbus_type": user_input.get("modbus_type", "tcp"),
                "host": user_input["host"],
                "port": user_input.get("port", DEFAULT_PORT),
                "slave_id": user_input.get("slave_id", DEFAULT_SLAVE),
                "timeout": user_input.get("timeout", DEFAULT_TIMEOUT),
                "delay": user_input.get("delay", DEFAULT_DELAY),
                "message_wait_milliseconds": user_input.get(
                    "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                ),
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
                _LOGGER.debug("Using configuration values from processed_data")
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
                # Persist entity_ids_without_prefix at entry level for coordinator fallback
                entity_ids_opt = config_values.get("dynamic_config", {}).get(
                    "entity_ids_without_prefix"
                )
                if entity_ids_opt is not None:
                    config_data["entity_ids_without_prefix"] = entity_ids_opt

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
                _LOGGER.debug(
                    "Extending existing hub %s:%s with new device (slave_id: %s)",
                    host,
                    port,
                    config_data.get("slave_id", 1),
                )

                # Get existing devices
                existing_devices = [
                    self._normalize_device_record(d)
                    for d in existing_entry.data.get("devices", [])
                ]
                incoming_devices = [
                    self._normalize_device_record(d)
                    for d in config_data.get("devices", [])
                ]

                for incoming_device in incoming_devices:
                    match_index = None
                    for i, existing_device in enumerate(existing_devices):
                        same_entry_id = existing_device.get(
                            "device_entry_id"
                        ) == incoming_device.get("device_entry_id")
                        same_identity = (
                            existing_device.get("prefix")
                            == incoming_device.get("prefix")
                            and existing_device.get("slave_id")
                            == incoming_device.get("slave_id")
                            and existing_device.get("template")
                            == incoming_device.get("template")
                        )
                        if same_entry_id or same_identity:
                            match_index = i
                            break

                    if match_index is not None:
                        existing_devices[match_index] = incoming_device
                        _LOGGER.debug(
                            "Updated existing device %s",
                            incoming_device.get("device_entry_id"),
                        )
                    else:
                        existing_devices.append(incoming_device)
                        _LOGGER.debug(
                            "Added new device %s",
                            incoming_device.get("device_entry_id"),
                        )

                # Update config entry
                new_data = dict(existing_entry.data)
                new_data["devices"] = existing_devices

                _LOGGER.debug(
                    "🔍 Updating config entry with %d devices", len(existing_devices)
                )
                for i, device in enumerate(existing_devices):
                    _LOGGER.debug(
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
                    legacy_device = {
                        "type": template_data.get("type", "inverter"),
                        "prefix": config_data["prefix"],
                        "template": config_data["template"],
                        "slave_id": config_data.get("slave_id", 1),
                        "selected_model": config_data.get("selected_model"),
                        "template_version": config_data.get("template_version"),
                        "firmware_version": config_data.get("firmware_version"),
                        "registers": config_data.get("registers", []),
                        "calculated_entities": config_data.get(
                            "calculated_entities", []
                        ),
                        "controls": config_data.get("controls", []),
                        "binary_sensors": config_data.get("binary_sensors", []),
                    }
                    # Copy dynamic_config fields (entity_ids_without_prefix, meter_type, etc.)
                    template_dynamic = template_data.get("dynamic_config", {})
                    if isinstance(template_dynamic, dict):
                        for field_name in template_dynamic.keys():
                            if field_name in (
                                "valid_models",
                                "battery_config",
                                "battery_slave_id",
                            ):
                                continue
                            if field_name in config_data:
                                legacy_device[field_name] = config_data[field_name]
                    config_data["devices"] = [
                        self._normalize_device_record(legacy_device)
                    ]
                else:
                    _LOGGER.info(
                        "Using existing devices array with %d devices from battery workflow",
                        len(config_data["devices"]),
                    )
                    config_data["devices"] = [
                        self._normalize_device_record(d) for d in config_data["devices"]
                    ]

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

            if not _is_prefix_unique_across_hubs(self.hass, user_input["prefix"]):
                return self.async_abort(
                    reason="invalid_simple_config",
                    description_placeholders={
                        "error": (
                            f"Prefix '{user_input['prefix']}' already exists. "
                            "Please choose a unique prefix."
                        )
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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return supported config subentry types for this integration."""
        return {"device": ModbusManagerDeviceSubentryFlow}


class ModbusManagerDeviceSubentryFlow(config_entries.ConfigSubentryFlow):
    """Config subentry flow for Modbus Manager devices."""

    @staticmethod
    async def _get_template_defaults(template_name: str) -> tuple[str, int]:
        """Return default prefix/slave_id for a template."""
        template_data = await get_template_by_name(template_name)
        if not isinstance(template_data, dict):
            return "device", 1
        return (
            str(template_data.get("default_prefix", "device")),
            int(template_data.get("default_slave_id", 1)),
        )

    async def _show_add_device_form(
        self,
        selected_template: str,
        prefix_default: str | None = None,
        slave_id_default: int | None = None,
    ) -> FlowResult:
        """Render add-device form with template-aware defaults."""
        template_names = sorted(await get_template_names())
        if not template_names:
            return self.async_abort(reason="no_templates")

        if selected_template not in template_names:
            selected_template = template_names[0]

        if prefix_default is None or slave_id_default is None:
            resolved_prefix, resolved_slave_id = await self._get_template_defaults(
                selected_template
            )
            if prefix_default is None:
                prefix_default = resolved_prefix
            if slave_id_default is None:
                slave_id_default = resolved_slave_id

        self._add_form_template_name = selected_template
        self._add_form_prefix_default = prefix_default
        self._add_form_slave_default = slave_id_default

        template_data = await get_template_by_name(selected_template)
        dynamic_config = (
            template_data.get("dynamic_config", {})
            if isinstance(template_data, dict)
            else {}
        )

        schema_fields: dict[Any, Any] = {
            vol.Required("prefix", default=prefix_default): str,
            vol.Required("slave_id", default=slave_id_default): int,
        }

        valid_models = dynamic_config.get("valid_models")
        if isinstance(valid_models, dict) and valid_models:
            model_options = {name: name for name in valid_models.keys()}
            default_model = next(iter(model_options))
            schema_fields[
                vol.Optional("selected_model", default=default_model)
            ] = vol.In(model_options)

        for field_name, field_config in dynamic_config.items():
            if field_name in [
                "valid_models",
                "battery_slave_id",
                "battery_config",
                "selected_model",
            ]:
                continue

            if isinstance(field_config, dict) and "options" in field_config:
                options = field_config.get("options", [])
                if options:
                    default = field_config.get("default", options[0])
                    if default not in options:
                        default = options[0]
                    schema_fields[vol.Optional(field_name, default=default)] = vol.In(
                        options
                    )
            elif isinstance(field_config, dict) and "default" in field_config:
                default = field_config.get("default")
                if isinstance(default, bool):
                    schema_fields[vol.Optional(field_name, default=default)] = bool
                elif isinstance(default, int):
                    schema_fields[vol.Optional(field_name, default=default)] = int
                elif isinstance(default, float):
                    schema_fields[vol.Optional(field_name, default=default)] = float
                else:
                    schema_fields[vol.Optional(field_name, default=str(default))] = str

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_fields),
        )

    async def _show_add_template_select_form(self) -> FlowResult:
        """Render first add-device step with template selection only."""
        template_names = sorted(await get_template_names())
        if not template_names:
            return self.async_abort(reason="no_templates")

        default_template = template_names[0]
        self._add_form_template_name = None
        self._add_template_candidate = default_template
        self._add_form_prefix_default = None
        self._add_form_slave_default = None

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("template", default=default_template): vol.In(
                        template_names
                    ),
                }
            ),
        )

    @staticmethod
    def _build_device_entry_id(device: dict[str, Any]) -> str:
        prefix = str(device.get("prefix", "device")).strip() or "device"
        slave_id = str(device.get("slave_id", 1)).strip() or "1"
        template = str(device.get("template", "template")).strip() or "template"
        return f"{prefix}_{slave_id}_{template}"

    @classmethod
    def _normalize_device_record(cls, device: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(device)
        if not normalized.get("type"):
            normalized["type"] = "inverter"
        normalized["device_entry_id"] = normalized.get(
            "device_entry_id", cls._build_device_entry_id(normalized)
        )
        return normalized

    @classmethod
    def _get_devices(cls, entry: config_entries.ConfigEntry) -> list[dict[str, Any]]:
        devices = entry.data.get("devices", [])
        if isinstance(devices, list) and devices:
            return [
                cls._normalize_device_record(device)
                for device in devices
                if isinstance(device, dict)
            ]
        template = entry.data.get("template")
        if not template:
            return []
        legacy_device = {
            "type": "inverter",
            "template": template,
            "prefix": entry.data.get("prefix", "unknown"),
            "slave_id": entry.data.get("slave_id", 1),
            "selected_model": entry.data.get("selected_model"),
        }
        return [cls._normalize_device_record(legacy_device)]

    @staticmethod
    def _build_subentry_title(device: dict[str, Any]) -> str:
        return (
            f"{device.get('prefix', 'unknown')} | "
            f"slave {device.get('slave_id', '?')} | "
            f"{device.get('template', 'unknown')}"
        )

    @staticmethod
    def _build_subentry_data(device: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "device_entry_id",
            "type",
            "template",
            "prefix",
            "slave_id",
            "template_version",
            "firmware_version",
            "selected_model",
            "phases",
            "mppt_count",
            "string_count",
            "modules",
            "connection_type",
            "meter_type",
            "battery_config",
            "battery_slave_id",
        ]
        return {key: device[key] for key in keys if key in device}

    def _build_dynamic_input_for_device(
        self, device: dict[str, Any], template_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Build effective dynamic user input for one device from template + stored values."""
        dynamic_config = template_data.get("dynamic_config", {})
        dynamic_input: dict[str, Any] = {
            "slave_id": device.get("slave_id", 1),
        }

        if not isinstance(dynamic_config, dict):
            return dynamic_input

        for field_name, field_config in dynamic_config.items():
            if field_name == "valid_models":
                continue

            if field_name in device:
                dynamic_input[field_name] = device.get(field_name)
                continue

            if isinstance(field_config, dict):
                if "default" in field_config:
                    dynamic_input[field_name] = field_config.get("default")
                elif "options" in field_config:
                    options = field_config.get("options", [])
                    if options:
                        dynamic_input[field_name] = options[0]

        return dynamic_input

    async def _cleanup_stale_subentry_entities(
        self,
        entry: config_entries.ConfigEntry,
        subentry_id: str | None,
        expected_unique_ids: set[str],
    ) -> None:
        """Remove stale entity registry entries for one subentry after dynamic filtering changes."""
        if not subentry_id:
            return

        normalized_expected = {
            str(unique_id).strip().lower()
            for unique_id in expected_unique_ids
            if unique_id
        }
        if not normalized_expected:
            return

        def _matches_expected(registry_unique_id: str) -> bool:
            normalized_registry = str(registry_unique_id).strip().lower()
            if not normalized_registry:
                return False
            return normalized_registry in normalized_expected

        entity_registry = er.async_get(self.hass)
        managed_domains = {
            "sensor",
            "number",
            "select",
            "switch",
            "button",
            "text",
            "binary_sensor",
        }
        removed_entities = 0

        for registry_entry in list(entity_registry.entities.values()):
            if registry_entry.config_entry_id != entry.entry_id:
                continue
            if registry_entry.config_subentry_id != subentry_id:
                continue

            entity_domain = registry_entry.entity_id.split(".", 1)[0]
            if entity_domain not in managed_domains:
                continue

            registry_unique_id = registry_entry.unique_id or ""
            if _matches_expected(registry_unique_id):
                continue

            entity_registry.async_remove(registry_entry.entity_id)
            removed_entities += 1

        if removed_entities:
            _LOGGER.info(
                "Removed %d stale entities for subentry %s after reconfigure",
                removed_entities,
                subentry_id,
            )

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Add a new device to current hub and create its subentry."""
        entry = self._get_entry()
        if user_input is not None:
            # Stage 1: template selected, now show defaults for prefix/slave_id.
            if "prefix" not in user_input and "slave_id" not in user_input:
                template_name = user_input["template"]
                self._add_template_candidate = template_name
                default_prefix, default_slave_id = await self._get_template_defaults(
                    template_name
                )
                return await self._show_add_device_form(
                    selected_template=template_name,
                    prefix_default=default_prefix,
                    slave_id_default=default_slave_id,
                )

            template_name = user_input.get(
                "template", getattr(self, "_add_template_candidate", None)
            )
            template_data = await get_template_by_name(template_name)
            if not template_data or not isinstance(template_data, dict):
                return self.async_abort(reason="template_not_found")

            prefix = str(user_input.get("prefix", "")).strip()
            slave_id = int(user_input.get("slave_id", 1))

            # UX helper: if user changed only template, but prefix/slave still match
            # the previous form defaults, automatically apply defaults of the newly
            # selected template.
            shown_template = getattr(self, "_add_form_template_name", None)
            shown_prefix_default = getattr(self, "_add_form_prefix_default", None)
            shown_slave_default = getattr(self, "_add_form_slave_default", None)
            template_changed = shown_template and shown_template != template_name
            prefix_matches_shown_default = (
                shown_prefix_default is not None
                and prefix == str(shown_prefix_default).strip()
            )
            slave_matches_shown_default = (
                shown_slave_default is not None and slave_id == int(shown_slave_default)
            )

            if (
                template_changed
                and prefix_matches_shown_default
                and slave_matches_shown_default
            ):
                # Re-render form so user sees updated defaults of the chosen template.
                new_prefix, new_slave_id = await self._get_template_defaults(
                    template_name
                )
                return await self._show_add_device_form(
                    selected_template=template_name,
                    prefix_default=new_prefix,
                    slave_id_default=new_slave_id,
                )

            device = {
                "type": template_data.get("type", "inverter") or "inverter",
                "template": template_name,
                "prefix": prefix,
                "slave_id": slave_id,
                "template_version": template_data.get("version", 1),
                "firmware_version": template_data.get("firmware_version", "1.0.0"),
            }

            dynamic_config = template_data.get("dynamic_config", {})
            if isinstance(dynamic_config, dict):
                valid_models = dynamic_config.get("valid_models")
                if isinstance(valid_models, dict) and valid_models:
                    default_model = next(iter(valid_models))
                    device["selected_model"] = user_input.get(
                        "selected_model", default_model
                    )
                for field_name, field_config in dynamic_config.items():
                    if field_name in [
                        "valid_models",
                        "battery_slave_id",
                        "battery_config",
                    ]:
                        continue
                    if field_name in user_input:
                        device[field_name] = user_input.get(field_name)
                    elif isinstance(field_config, dict) and "default" in field_config:
                        device[field_name] = field_config.get("default")

            normalized_device = self._normalize_device_record(device)

            devices = self._get_devices(entry)
            active_subentry_unique_ids = {
                subentry.unique_id
                for subentry in entry.subentries.values()
                if subentry.subentry_type == "device" and subentry.unique_id
            }

            # If a device subentry was deleted in HA UI, devices[] can be temporarily stale
            # until the next sync/reload. Prune only the stale duplicate candidate here so
            # re-adding the same logical device works immediately.
            pruned_devices: list[dict[str, Any]] = []
            removed_stale_duplicate = False
            for existing in devices:
                existing_device_id = existing.get("device_entry_id")
                same_entry_id = existing_device_id == normalized_device.get(
                    "device_entry_id"
                )
                same_identity = (
                    existing.get("prefix") == normalized_device.get("prefix")
                    and existing.get("slave_id") == normalized_device.get("slave_id")
                    and existing.get("template") == normalized_device.get("template")
                )
                is_orphaned = existing_device_id not in active_subentry_unique_ids

                if is_orphaned and (same_entry_id or same_identity):
                    removed_stale_duplicate = True
                    _LOGGER.info(
                        "Pruned stale device record without subentry before add: %s",
                        existing_device_id,
                    )
                    continue

                pruned_devices.append(existing)

            if removed_stale_duplicate:
                devices = pruned_devices
                new_data = dict(entry.data)
                new_data["devices"] = devices
                self.hass.config_entries.async_update_entry(entry, data=new_data)

            # Prefix must be unique across other hubs.
            # Current hub duplicates are validated below against active devices[].
            if not _is_prefix_unique_across_hubs(
                self.hass, prefix, exclude_entry_id=entry.entry_id
            ):
                return self.async_abort(reason="already_configured")

            for existing in devices:
                same_entry_id = existing.get(
                    "device_entry_id"
                ) == normalized_device.get("device_entry_id")
                same_identity = (
                    existing.get("prefix") == normalized_device.get("prefix")
                    and existing.get("slave_id") == normalized_device.get("slave_id")
                    and existing.get("template") == normalized_device.get("template")
                )
                if same_entry_id or same_identity:
                    return self.async_abort(reason="already_configured")

            new_data = dict(entry.data)
            new_data["devices"] = devices + [normalized_device]
            # Mark newly added logical device as pending until its subentry exists.
            # This avoids add-flow race conditions where setup pruning runs before
            # HA persists the subentry.
            new_data["pending_subentry_device_id"] = normalized_device.get(
                "device_entry_id"
            )
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)

            return self.async_create_entry(
                title=self._build_subentry_title(normalized_device),
                data=self._build_subentry_data(normalized_device),
                unique_id=normalized_device.get("device_entry_id"),
            )

        return await self._show_add_template_select_form()

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Reconfigure one device subentry."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        selected_device_id = subentry.unique_id or subentry.data.get("device_entry_id")
        devices = self._get_devices(entry)
        selected_device = next(
            (
                device
                for device in devices
                if device.get("device_entry_id") == selected_device_id
            ),
            None,
        )
        if not selected_device:
            return self.async_abort(reason="config_error")

        template_name = selected_device.get("template")
        template_data = (
            await get_template_by_name(template_name) if template_name else None
        )
        dynamic_config = (
            template_data.get("dynamic_config", {})
            if isinstance(template_data, dict)
            else {}
        )

        if user_input is not None:
            new_prefix = str(
                user_input.get("prefix", selected_device.get("prefix", ""))
            )
            if not _is_prefix_unique_across_hubs(
                self.hass,
                new_prefix,
                exclude_entry_id=entry.entry_id,
                exclude_device_entry_id=selected_device_id,
            ):
                return self.async_abort(reason="already_configured")

            updated_device = dict(selected_device)
            updated_device["prefix"] = new_prefix
            updated_device["slave_id"] = user_input.get(
                "slave_id", updated_device.get("slave_id", 1)
            )
            if "selected_model" in user_input:
                updated_device["selected_model"] = user_input["selected_model"]

            for field_name in dynamic_config.keys():
                if field_name == "valid_models":
                    continue
                if field_name in user_input:
                    updated_device[field_name] = user_input[field_name]

            updated_device = self._normalize_device_record(updated_device)
            new_device_id = updated_device.get("device_entry_id")

            new_devices = []
            for device in devices:
                if device.get("device_entry_id") == selected_device_id:
                    new_devices.append(updated_device)
                else:
                    new_devices.append(device)

            new_data = dict(entry.data)
            new_data["devices"] = new_devices

            # Keep legacy top-level keys in sync for the legacy main device
            legacy_device_id = self._build_device_entry_id(
                {
                    "prefix": entry.data.get("prefix"),
                    "slave_id": entry.data.get("slave_id", 1),
                    "template": entry.data.get("template"),
                }
            )
            if selected_device_id == legacy_device_id:
                new_data["prefix"] = updated_device.get(
                    "prefix", entry.data.get("prefix")
                )
                new_data["slave_id"] = updated_device.get(
                    "slave_id", entry.data.get("slave_id", 1)
                )
                if "selected_model" in updated_device:
                    new_data["selected_model"] = updated_device["selected_model"]
                for field_name in dynamic_config.keys():
                    if field_name in updated_device:
                        new_data[field_name] = updated_device[field_name]

            self.hass.config_entries.async_update_entry(entry, data=new_data)
            self.hass.config_entries.async_update_subentry(
                entry=entry,
                subentry=subentry,
                unique_id=new_device_id,
                title=self._build_subentry_title(updated_device),
                data=self._build_subentry_data(updated_device),
            )

            # Build expected entity unique_ids with current dynamic filtering
            # and remove obsolete registry entries for this subentry.
            expected_unique_ids: set[str] = set()
            if isinstance(template_data, dict):
                try:
                    dynamic_input = self._build_dynamic_input_for_device(
                        updated_device, template_data
                    )
                    # _process_dynamic_config mutates template_data["dynamic_config"].
                    # Use a deep copy so cached template definitions stay untouched.
                    template_data_for_processing = copy.deepcopy(template_data)
                    processed_data = ModbusManagerConfigFlow()._process_dynamic_config(
                        dynamic_input, template_data_for_processing
                    )
                    all_entities = (
                        processed_data.get("sensors", [])
                        + processed_data.get("calculated", [])
                        + processed_data.get("controls", [])
                        + processed_data.get("binary_sensors", [])
                    )
                    device_prefix = str(updated_device.get("prefix", "")).strip()
                    for entity_def in all_entities:
                        expected_unique_ids.add(
                            generate_unique_id(
                                device_prefix,
                                entity_def.get("unique_id"),
                                entity_def.get("name"),
                            )
                        )
                except Exception as err:
                    _LOGGER.warning(
                        "Failed to build expected dynamic entities for subentry cleanup: %s",
                        str(err),
                    )

            await self._cleanup_stale_subentry_entities(
                entry=entry,
                subentry_id=subentry.subentry_id,
                expected_unique_ids=expected_unique_ids,
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        schema_fields: dict[Any, Any] = {
            vol.Required(
                "prefix", default=selected_device.get("prefix", "device")
            ): str,
            vol.Required("slave_id", default=selected_device.get("slave_id", 1)): int,
        }

        valid_models = dynamic_config.get("valid_models")
        if isinstance(valid_models, dict) and valid_models:
            model_options = {name: name for name in valid_models.keys()}
            current_model = selected_device.get("selected_model")
            default_model = (
                current_model
                if current_model in model_options
                else next(iter(model_options))
            )
            schema_fields[
                vol.Optional("selected_model", default=default_model)
            ] = vol.In(model_options)

        for field_name, field_config in dynamic_config.items():
            if field_name == "valid_models":
                continue
            if field_name == "selected_model":
                continue
            if isinstance(field_config, dict) and "options" in field_config:
                options = field_config.get("options", [])
                if options:
                    current = selected_device.get(
                        field_name, field_config.get("default")
                    )
                    default = current if current in options else options[0]
                    schema_fields[vol.Optional(field_name, default=default)] = vol.In(
                        options
                    )
            elif isinstance(field_config, dict) and "default" in field_config:
                current = selected_device.get(field_name, field_config.get("default"))
                if isinstance(current, bool):
                    schema_fields[vol.Optional(field_name, default=current)] = bool
                elif isinstance(current, int):
                    schema_fields[vol.Optional(field_name, default=current)] = int
                elif isinstance(current, float):
                    schema_fields[vol.Optional(field_name, default=current)] = float
                else:
                    schema_fields[vol.Optional(field_name, default=str(current))] = str

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "device": self._build_subentry_title(selected_device),
            },
        )


class ModbusManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Manager."""

    def __init__(self) -> None:
        """Initialize options flow state."""
        super().__init__()

    def _build_device_entry_id(self, device: dict[str, Any]) -> str:
        """Build stable logical device id."""
        prefix = str(device.get("prefix", "device")).strip() or "device"
        slave_id = str(device.get("slave_id", 1)).strip() or "1"
        template = str(device.get("template", "template")).strip() or "template"
        return f"{prefix}_{slave_id}_{template}"

    def _get_editable_devices(self) -> list[dict[str, Any]]:
        """Return normalized list of devices that can be edited."""
        devices = self.config_entry.data.get("devices", [])
        if not isinstance(devices, list):
            return []

        normalized_devices: list[dict[str, Any]] = []
        for device in devices:
            normalized = dict(device)
            if not normalized.get("device_entry_id"):
                normalized["device_entry_id"] = self._build_device_entry_id(normalized)
            normalized_devices.append(normalized)
        return normalized_devices

    async def _remove_battery_devices_from_registry(
        self, battery_devices: list
    ) -> None:
        """Remove battery devices from device registry when they are removed from config."""
        try:
            device_registry = dr.async_get(self.hass)
            hub_config = self.config_entry.data.get("hub", {})
            host = hub_config.get("host") or self.config_entry.data.get(
                "host", "unknown"
            )
            port = hub_config.get("port") or self.config_entry.data.get("port", 502)

            for battery_device in battery_devices:
                battery_slave_id = battery_device.get("slave_id", 200)
                device_identifier = (
                    f"modbus_manager_{host}_{port}_slave_{battery_slave_id}"
                )

                # Find device in registry
                device_entry = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_identifier)}
                )

                if device_entry:
                    # Check if this device belongs to this config entry
                    if (
                        device_entry.config_entries
                        and self.config_entry.entry_id in device_entry.config_entries
                    ):
                        # Remove device from registry
                        device_registry.async_remove_device(device_entry.id)
                        _LOGGER.info(
                            "Removed battery device '%s' (slave %d) from device registry",
                            battery_device.get("prefix", "unknown"),
                            battery_slave_id,
                        )
                    else:
                        _LOGGER.debug(
                            "Battery device '%s' (slave %d) not found in device registry or belongs to different config entry",
                            battery_device.get("prefix", "unknown"),
                            battery_slave_id,
                        )
                else:
                    _LOGGER.debug(
                        "Battery device '%s' (slave %d) not found in device registry",
                        battery_device.get("prefix", "unknown"),
                        battery_slave_id,
                    )
        except Exception as e:
            _LOGGER.error("Error removing battery devices from registry: %s", str(e))

    def _supports_battery_config(self, template_data: dict) -> bool:
        """Check if template defines a battery_config dynamic section."""
        dynamic_config = template_data.get("dynamic_config", {})
        has_battery_config = isinstance(dynamic_config.get("battery_config"), dict)
        _LOGGER.debug(
            "_supports_battery_config: template_data keys=%s, has_battery_config=%s",
            list(template_data.keys()),
            has_battery_config,
        )
        return has_battery_config

    async def async_step_init(self, user_input: dict = None) -> FlowResult:
        """Manage hub-level options only."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_data["timeout"] = user_input.get(
                "timeout", self.config_entry.data.get("timeout", DEFAULT_TIMEOUT)
            )
            new_data["delay"] = user_input.get(
                "delay", self.config_entry.data.get("delay", DEFAULT_DELAY)
            )
            new_data["message_wait_milliseconds"] = user_input.get(
                "message_wait_milliseconds",
                self.config_entry.data.get(
                    "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                ),
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "timeout",
                        default=self.config_entry.data.get("timeout", DEFAULT_TIMEOUT),
                    ): int,
                    vol.Required(
                        "delay",
                        default=self.config_entry.data.get("delay", DEFAULT_DELAY),
                    ): int,
                    vol.Required(
                        "message_wait_milliseconds",
                        default=self.config_entry.data.get(
                            "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                        ),
                    ): int,
                }
            ),
        )

    async def async_step_update_template(self, user_input: dict = None) -> FlowResult:
        """Update the template to the latest version or reload for changes."""
        try:
            pending_update = getattr(self, "_pending_options_update", None)

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

            if not (
                original_sensors
                or original_calculated
                or original_controls
                or original_binary_sensors
            ):
                return self.async_abort(
                    reason="no_registers",
                    description_placeholders={"template_name": template_name},
                )

            # Build effective data (config entry + pending options updates)
            effective_data = dict(self.config_entry.data)
            if pending_update:
                effective_data.update(pending_update)
                if "battery_config" in pending_update:
                    effective_data["battery_enabled"] = (
                        pending_update["battery_config"] != "none"
                    )

            # Apply dynamic configuration (important for MPPT filtering!)
            if dynamic_config:
                try:
                    # Build user_input dict with ALL dynamic config values from config entry
                    # This ensures all fields like dual_channel_meter are included
                    user_input_for_processing = {}

                    # Read all dynamic config fields from config entry
                    for field_name, field_config in dynamic_config.items():
                        if field_name in [
                            "valid_models",
                            "firmware_version",
                            "connection_type",
                            "battery_slave_id",
                        ]:
                            # These are handled separately or don't need to be read
                            continue

                        # Get value from config entry, or use default from field_config
                        if isinstance(field_config, dict) and "default" in field_config:
                            default_value = field_config.get("default")
                            current_value = effective_data.get(
                                field_name, default_value
                            )
                            user_input_for_processing[field_name] = current_value
                        elif (
                            isinstance(field_config, dict) and "options" in field_config
                        ):
                            # Field with options - get current value or use first option as default
                            options = field_config.get("options", [])
                            default_value = options[0] if options else None
                            current_value = effective_data.get(
                                field_name, default_value
                            )
                            user_input_for_processing[field_name] = current_value

                    # Add explicitly handled fields
                    user_input_for_processing["phases"] = effective_data.get(
                        "phases", 1
                    )
                    user_input_for_processing["mppt_count"] = effective_data.get(
                        "mppt_count", 2
                    )
                    user_input_for_processing["string_count"] = effective_data.get(
                        "string_count", 0
                    )
                    user_input_for_processing["battery_config"] = effective_data.get(
                        "battery_config", "none"
                    )
                    user_input_for_processing["battery_slave_id"] = effective_data.get(
                        "battery_slave_id", 200
                    )
                    user_input_for_processing["firmware_version"] = effective_data.get(
                        "firmware_version", "1.0.0"
                    )
                    user_input_for_processing["connection_type"] = effective_data.get(
                        "connection_type", "LAN"
                    )
                    user_input_for_processing["meter_type"] = effective_data.get(
                        "meter_type", "DTSU666"
                    )
                    user_input_for_processing["selected_model"] = effective_data.get(
                        "selected_model"
                    )

                    _LOGGER.info(
                        "Applying dynamic config during template update: %s",
                        ", ".join(
                            [f"{k}={v}" for k, v in user_input_for_processing.items()]
                        ),
                    )

                    # Process template with current configuration
                    # Use the same logic as in _process_dynamic_config
                    processed_data = self._process_dynamic_config(
                        user_input_for_processing,
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
                if pending_update:
                    new_data.update(pending_update)
                    if "battery_config" in pending_update:
                        new_data["battery_enabled"] = (
                            pending_update["battery_config"] != "none"
                        )
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

                # Keep device-specific dynamic config in sync with options updates
                if dynamic_config:
                    dynamic_config_fields = [
                        key
                        for key in dynamic_config.keys()
                        if key
                        not in [
                            "valid_models",
                            "firmware_version",
                            "connection_type",
                            "battery_slave_id",
                        ]
                    ]
                else:
                    dynamic_config_fields = []

                dynamic_params = [
                    "phases",
                    "mppt_count",
                    "battery_config",
                    "battery_slave_id",
                    "connection_type",
                    "meter_type",
                    "firmware_version",
                    "selected_model",
                ] + dynamic_config_fields

                devices = new_data.get("devices")
                if isinstance(devices, list) and template_name:
                    for device in devices:
                        if device.get("template") != template_name:
                            continue
                        for key in dynamic_params:
                            if key in new_data:
                                device[key] = new_data[key]

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

                # Clear pending updates after successful application
                if pending_update:
                    self._pending_options_update = None

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
            _LOGGER.error("Error updating the firmware version: %s", str(e))
            return self.async_abort(
                reason="firmware_update_error",
                description_placeholders={"error": str(e)},
            )

    async def async_step_battery_options_selection(
        self, user_input: dict = None
    ) -> FlowResult:
        """Select battery setup for options flow."""
        if user_input is not None:
            selection = user_input["battery_selection"]
            pending_update = getattr(self, "_pending_options_update", {}) or {}
            pending_update.pop("configure_battery", None)

            if selection in ["none", "other"]:
                combined_input = {
                    **pending_update,
                    "battery_config": selection,
                    "battery_template": selection,
                }
                return await self.async_step_apply_config_changes(combined_input)

            self._selected_battery_template = selection
            self._battery_options_base = {
                **pending_update,
                "battery_config": selection,
                "battery_template": selection,
            }
            return await self.async_step_battery_config()

        battery_templates_dict = {}
        template_names = await get_template_names()
        connection_type = self.config_entry.data.get("connection_type", "LAN")
        connection_type_norm = (
            str(connection_type).strip().upper() if connection_type else "LAN"
        )
        for template_name in template_names:
            template_data = await get_template_by_name(template_name)
            if template_data and isinstance(template_data, dict):
                if template_data.get("type", "") == "battery":
                    # Filter by requires_connection_type (e.g. SBR needs LAN)
                    required_conn = template_data.get("requires_connection_type")
                    if required_conn:
                        required_norm = str(required_conn).strip().upper()
                        if connection_type_norm != required_norm:
                            continue
                    display_name = template_data.get("display_name", template_name)
                    battery_templates_dict[template_name] = display_name

        # Sort battery templates alphabetically by display name for better UX
        sorted_battery_templates = dict(
            sorted(battery_templates_dict.items(), key=lambda x: x[1])
        )
        battery_templates = {
            "none": "None",
            **sorted_battery_templates,
            "other": "Other (no template)",
        }

        current_selection = self.config_entry.data.get("battery_config", "none")
        if current_selection not in battery_templates:
            current_selection = "none"

        return self.async_show_form(
            step_id="battery_options_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "battery_selection", default=current_selection
                    ): vol.In(battery_templates),
                }
            ),
        )

    async def async_step_battery_config(self, user_input: dict = None) -> FlowResult:
        """Handle battery configuration step for options flow."""
        if user_input is not None:
            battery_devices = [
                d
                for d in self._get_editable_devices()
                if str(d.get("type", "")).lower() == "battery"
            ]
            current_battery_device_id = (
                battery_devices[0].get("device_entry_id") if battery_devices else None
            )
            new_battery_prefix = user_input.get("battery_prefix")
            if new_battery_prefix and not _is_prefix_unique_across_hubs(
                self.hass,
                new_battery_prefix,
                exclude_entry_id=self.config_entry.entry_id,
                exclude_device_entry_id=current_battery_device_id,
            ):
                return self.async_abort(
                    reason="config_apply_error",
                    description_placeholders={
                        "error": (
                            f"Prefix '{new_battery_prefix}' already exists. "
                            "Please choose a unique prefix."
                        )
                    },
                )

            combined_input = dict(user_input)
            base_update = getattr(self, "_battery_options_base", {}) or {}
            # Also merge pending_options_update if available
            pending_update = getattr(self, "_pending_options_update", {}) or {}
            combined_input.update(base_update)
            combined_input.update(pending_update)
            # Clear pending updates
            self._pending_options_update = {}
            self._battery_options_base = {}
            _LOGGER.debug(
                "Battery config step completed, applying changes with combined_input: %s",
                {
                    k: v
                    for k, v in combined_input.items()
                    if k not in ["registers", "calculated_entities", "controls"]
                },
            )
            return await self.async_step_apply_config_changes(combined_input)

        # Get battery template name - either from _selected_battery_template or from pending update
        battery_template_name = getattr(self, "_selected_battery_template", None)
        if not battery_template_name:
            pending_update = getattr(self, "_pending_options_update", {}) or {}
            battery_template_name = pending_update.get("battery_config")

        _LOGGER.debug(
            "Battery config step: template_name=%s, _selected_battery_template=%s",
            battery_template_name,
            getattr(self, "_selected_battery_template", None),
        )

        if not battery_template_name or battery_template_name == "none":
            _LOGGER.error("No battery template selected for configuration")
            return self.async_abort(reason="no_battery_template")

        battery_template_data = await get_template_by_name(battery_template_name)

        if not battery_template_data:
            _LOGGER.error("Battery template '%s' not found", battery_template_name)
            return self.async_abort(reason="battery_template_not_found")

        # Get defaults from template FIRST (highest priority), then from config_entry
        if battery_template_data and isinstance(battery_template_data, dict):
            # Template defaults have highest priority
            template_default_slave_id = battery_template_data.get("default_slave_id")
            template_default_prefix = battery_template_data.get("default_prefix")

            # Use template defaults if available, otherwise use config_entry values, otherwise use fallback
            default_slave_id = (
                template_default_slave_id
                if template_default_slave_id is not None
                else self.config_entry.data.get("battery_slave_id", 200)
            )
            default_prefix = (
                template_default_prefix
                if template_default_prefix
                else self.config_entry.data.get("battery_prefix", "SBR")
            )

            _LOGGER.debug(
                "Battery config defaults: template_slave_id=%s, template_prefix=%s, using slave_id=%s, prefix=%s",
                template_default_slave_id,
                template_default_prefix,
                default_slave_id,
                default_prefix,
            )
        else:
            # Fallback if template data is invalid
            default_slave_id = self.config_entry.data.get("battery_slave_id", 200)
            default_prefix = self.config_entry.data.get("battery_prefix", "SBR")

        schema_fields = {
            vol.Required("battery_prefix", default=default_prefix): str,
            vol.Required("battery_slave_id", default=default_slave_id): int,
        }

        if battery_template_data and battery_template_data.get(
            "dynamic_config", {}
        ).get("valid_models"):
            valid_models = battery_template_data["dynamic_config"]["valid_models"]
            model_options = list(valid_models.keys())
            current_model = self.config_entry.data.get("battery_model")
            default_model = (
                current_model if current_model in model_options else model_options[0]
            )
            schema_fields[
                vol.Required("battery_model", default=default_model)
            ] = vol.In(model_options)
        else:
            current_modules = self.config_entry.data.get("battery_modules", 1)
            schema_fields[
                vol.Optional("battery_modules", default=current_modules)
            ] = int

        return self.async_show_form(
            step_id="battery_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "battery_template": battery_template_name or "Unknown",
            },
        )

    async def async_step_apply_config_changes(self, user_input: dict) -> FlowResult:
        """Apply configuration changes and reload integration if needed."""
        try:
            # Force battery_config to none when battery_config condition not met (e.g. WINET)
            template_name = self.config_entry.data.get("template", "Unknown")
            template_data = await get_template_by_name(template_name)
            if template_data:
                battery_config_def = (
                    template_data.get("dynamic_config", {}).get("battery_config", {})
                    if isinstance(template_data.get("dynamic_config"), dict)
                    else {}
                )
                condition = (
                    battery_config_def.get("condition")
                    if isinstance(battery_config_def, dict)
                    else None
                )
                effective_data = {**self.config_entry.data, **user_input}
                if condition and not _evaluate_condition(condition, effective_data):
                    user_input = dict(user_input)
                    user_input["battery_config"] = "none"
                    user_input["battery_template"] = "none"
                    _LOGGER.info(
                        "Battery disabled: condition '%s' not met (connection_type=%s)",
                        condition,
                        effective_data.get("connection_type"),
                    )

            # Check if dynamic configuration has changed
            dynamic_config_changed = False
            config_changes = {}

            # Check each dynamic config parameter
            # Get all dynamic config fields from template to check for changes
            template_name = self.config_entry.data.get("template", "Unknown")
            template_data = await get_template_by_name(template_name)
            dynamic_config_fields = []

            if (
                template_data
                and isinstance(template_data, dict)
                and template_data.get("dynamic_config")
            ):
                dynamic_config = template_data.get("dynamic_config", {})
                # Add all configurable fields from dynamic_config
                for field_name in dynamic_config.keys():
                    if field_name not in [
                        "valid_models",
                        "firmware_version",
                        "connection_type",
                        "battery_slave_id",
                    ]:
                        dynamic_config_fields.append(field_name)

            # Add explicitly handled fields
            dynamic_params = [
                "phases",
                "mppt_count",
                "battery_config",
                "battery_template",
                "battery_prefix",
                "battery_slave_id",
                "battery_model",
                "battery_modules",
                "connection_type",
                "meter_type",
                "firmware_version",
                "selected_model",
            ] + dynamic_config_fields

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

            # Ensure battery_enabled is stored based on battery_config
            if "battery_config" in user_input:
                new_data["battery_enabled"] = user_input["battery_config"] != "none"

            battery_selection = new_data.get("battery_config")
            if battery_selection in ["none", "other"]:
                new_data["battery_template"] = battery_selection
            elif battery_selection:
                new_data["battery_template"] = battery_selection

            # Sync devices array for battery selection changes
            devices = new_data.get("devices")
            battery_removed = False
            removed_battery_devices = []  # Store removed devices for cleanup
            if isinstance(devices, list) and devices:
                battery_devices = [
                    device for device in devices if device.get("type") == "battery"
                ]
                if battery_selection in ["none", "other"]:
                    if battery_devices:
                        # Store removed devices for device registry cleanup
                        removed_battery_devices = battery_devices.copy()

                        # Remove battery devices from devices array
                        devices[:] = [
                            device
                            for device in devices
                            if device.get("type") != "battery"
                        ]
                        battery_removed = True
                        _LOGGER.info(
                            "Removed %d battery device(s) from devices array (battery_config set to '%s')",
                            len(battery_devices),
                            battery_selection,
                        )
                elif battery_selection:
                    battery_template_data = await get_template_by_name(
                        battery_selection
                    )
                    battery_prefix = new_data.get("battery_prefix", "SBR")
                    battery_slave_id = new_data.get("battery_slave_id", 200)
                    battery_model = new_data.get("battery_model")
                    battery_device = {
                        "type": "battery",
                        "template": battery_selection,
                        "prefix": battery_prefix,
                        "slave_id": battery_slave_id,
                        "selected_model": battery_model,
                    }
                    if battery_template_data and isinstance(
                        battery_template_data, dict
                    ):
                        battery_device["template_version"] = battery_template_data.get(
                            "version", 1
                        )
                        battery_device["firmware_version"] = battery_template_data.get(
                            "firmware_version", "1.0.0"
                        )
                    if battery_devices:
                        for i, device in enumerate(devices):
                            if device.get("type") == "battery":
                                devices[i] = battery_device
                                break
                    else:
                        devices.append(battery_device)

            # Keep device-specific dynamic config in sync with options updates
            devices = new_data.get("devices")
            if isinstance(devices, list) and template_name:
                for device in devices:
                    if device.get("template") != template_name:
                        continue
                    for key in dynamic_params:
                        if key in user_input:
                            device[key] = user_input[key]

            # Remove temporary fields
            new_data.pop("update_template", None)
            new_data.pop("configure_battery", None)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            _LOGGER.info("Configuration updated: %s", config_changes)

            # If battery was removed, clean up device registry entries
            if battery_removed and removed_battery_devices:
                await self._remove_battery_devices_from_registry(
                    removed_battery_devices
                )

            # If battery was removed or dynamic configuration changed, reload the integration
            # This will:
            # 1. Remove battery device entities (because device is removed from devices array)
            # 2. Hide battery registers from inverter template (because battery_enabled=False)
            if battery_removed or dynamic_config_changed:
                if battery_removed:
                    _LOGGER.info(
                        "Battery device removed and battery_config set to 'none', reloading integration to deregister battery entities and hide battery registers"
                    )
                else:
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
            dynamic_config["selected_model"] = selected_model
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
                    # Store model config values in dynamic_config for condition filtering
                    # This ensures model-specific values are available and not overwritten by defaults
                    dynamic_config[field_name] = field_value

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
                modules = 3
        else:
            # Individual field configuration - generic for any device type
            # Extract all configurable fields dynamically
            # Safe access: config values may be overwritten with primitives
            def _safe_default(config: dict, key: str, default: Any) -> Any:
                val = config.get(key, {})
                return val.get("default", default) if isinstance(val, dict) else default

            phases = user_input.get(
                "phases", _safe_default(dynamic_config, "phases", 3)
            )
            mppt_count = user_input.get(
                "mppt_count", _safe_default(dynamic_config, "mppt_count", 1)
            )
            string_count = user_input.get(
                "string_count", _safe_default(dynamic_config, "string_count", 1)
            )
            modules = user_input.get(
                "modules", _safe_default(dynamic_config, "modules", 3)
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
                    default_val = (
                        field_config.get("default", "unknown")
                        if isinstance(field_config, dict)
                        else "unknown"
                    )
                    field_value = user_input.get(field_name, default_val)
                    individual_fields.append(f"{field_name}={field_value}")

            _LOGGER.info(
                "Using individual field configuration: %s",
                ", ".join(individual_fields),
            )

        # Safe access: battery_config may be overwritten with string (e.g. "none")
        battery_config_val = dynamic_config.get("battery_config", {})
        battery_default = (
            battery_config_val.get("default", "none")
            if isinstance(battery_config_val, dict)
            else "none"
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
            battery_config = "sbr_battery"  # Set battery_config for condition filtering
        else:
            battery_enabled = battery_config != "none"
            battery_type = battery_config

        # Handle "Latest" firmware version - use the highest available version
        if firmware_version == "Latest":
            firmware_config = dynamic_config.get("firmware_version", {})
            available_firmware = (
                firmware_config.get("options", [])
                if isinstance(firmware_config, dict)
                else []
            )

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

        # Add modules to dynamic_config for condition filtering
        if selected_model and model_config:
            dynamic_config["modules"] = modules
        else:
            # For individual field configuration, add all fields to dynamic_config
            dynamic_config["modules"] = modules

        # Add ALL user input fields to dynamic_config for condition filtering
        # SunSpec model address fields are now handled automatically via the generic loop below
        # This ensures fields like meter_type, dual_channel_meter are available for condition checks
        for field_name, field_value in user_input.items():
            if field_name not in [
                "valid_models",
                "firmware_version",
                "connection_type",
                "battery_slave_id",
                "selected_model",  # Already handled separately
            ]:
                # Skip SunSpec address fields - already processed above
                if field_name.startswith("sunspec_model_") and field_name.endswith(
                    "_address"
                ):
                    continue
                # Store the actual value from user_input, or use default from dynamic_config
                if field_name in dynamic_config:
                    field_config = dynamic_config[field_name]
                    if isinstance(field_config, dict) and "default" in field_config:
                        # Use user input value if provided, otherwise use default
                        dynamic_config[field_name] = user_input.get(
                            field_name, field_config.get("default")
                        )
                    else:
                        # Field exists but no default, use user input value
                        dynamic_config[field_name] = field_value
                else:
                    # New field not in dynamic_config, add it
                    dynamic_config[field_name] = field_value

        # Also ensure all fields from dynamic_config with defaults are in dynamic_config
        # This is important for fields that might not be in user_input (e.g., when using defaults)
        # BUT: Don't overwrite values that came from selected_model - those are already set above
        # We need to check the original template_data, not the already-modified dynamic_config
        original_dynamic_config = template_data.get("dynamic_config", {})
        for field_name, field_config in original_dynamic_config.items():
            if field_name not in [
                "valid_models",
                "firmware_version",
                "connection_type",
                "battery_slave_id",
            ]:
                if isinstance(field_config, dict) and "default" in field_config:
                    # If field not already set from user_input or selected_model, use default
                    # Check if it's still a dict (meaning it wasn't set) or if it's missing
                    # Don't overwrite if it's already a concrete value (not a dict)
                    if field_name not in dynamic_config or isinstance(
                        dynamic_config.get(field_name), dict
                    ):
                        dynamic_config[field_name] = field_config.get("default")
                        _LOGGER.debug(
                            "Setting default value for %s: %s",
                            field_name,
                            field_config.get("default"),
                        )

        # Log meter_type if present for debugging
        meter_type = dynamic_config.get("meter_type", "not_set")
        _LOGGER.debug(
            "Processing dynamic config: phases=%d, mppt=%d, battery=%s, battery_type=%s, fw=%s, conn=%s, meter_type=%s",
            phases,
            mppt_count,
            battery_enabled,
            battery_type,
            firmware_version,
            connection_type,
            meter_type,
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

        # Check firmware_min_version filter first
        sensor_firmware_min = sensor.get("firmware_min_version")
        if sensor_firmware_min and firmware_version:
            try:
                from packaging import version

                # Compare firmware versions
                current_ver = version.parse(firmware_version)
                min_ver = version.parse(sensor_firmware_min)
                if current_ver < min_ver:
                    _LOGGER.debug(
                        "Excluding sensor due to firmware version: %s (unique_id: %s, requires: %s, current: %s)",
                        sensor.get("name", "unknown"),
                        sensor.get("unique_id", "unknown"),
                        sensor_firmware_min,
                        firmware_version,
                    )
                    return False
            except Exception:
                # Fallback to string comparison for non-semantic versions
                try:
                    if firmware_version < sensor_firmware_min:
                        _LOGGER.debug(
                            "Excluding sensor due to firmware version (string): %s (unique_id: %s, requires: %s, current: %s)",
                            sensor.get("name", "unknown"),
                            sensor.get("unique_id", "unknown"),
                            sensor_firmware_min,
                            firmware_version,
                        )
                        return False
                except Exception as e:
                    # If comparison fails, include the sensor (better safe than sorry)
                    _LOGGER.debug(
                        "Could not compare firmware versions for sensor %s: %s",
                        sensor.get("name", "unknown"),
                        str(e),
                    )

        # Check condition filter
        condition = sensor.get("condition")
        if condition:
            if not _evaluate_condition(condition, dynamic_config):
                _LOGGER.debug(
                    "Excluding sensor due to condition '%s': %s (unique_id: %s)",
                    condition,
                    sensor.get("name", "unknown"),
                    sensor.get("unique_id", "unknown"),
                )
                return False

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

    def _evaluate_single_condition(self, condition: str, dynamic_config: dict) -> bool:
        """Evaluate a single condition (no AND/OR).

        Supports:
        - "variable == value" (string, int, bool)
        - "variable != value" (string, int, bool)
        - "variable >= value" (int)
        """
        condition = condition.strip()

        if " not in " in condition:
            try:
                parts = condition.split(" not in ")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_values_str = parts[1].strip()

                    actual_value = dynamic_config.get(variable_name)

                    if required_values_str.startswith(
                        "["
                    ) and required_values_str.endswith("]"):
                        required_values_str = required_values_str[1:-1]
                    required_values = [
                        value.strip().strip("'\"")
                        for value in required_values_str.split(",")
                        if value.strip()
                    ]

                    if isinstance(actual_value, (list, tuple, set)):
                        actual_values = {str(value) for value in actual_value}
                        return not any(
                            value in actual_values for value in required_values
                        )
                    return str(actual_value) not in required_values
            except (ValueError, IndexError):
                return False
        elif " in " in condition:
            try:
                parts = condition.split(" in ")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_values_str = parts[1].strip()

                    actual_value = dynamic_config.get(variable_name)

                    if required_values_str.startswith(
                        "["
                    ) and required_values_str.endswith("]"):
                        required_values_str = required_values_str[1:-1]
                    required_values = [
                        value.strip().strip("'\"")
                        for value in required_values_str.split(",")
                        if value.strip()
                    ]

                    if isinstance(actual_value, (list, tuple, set)):
                        actual_values = {str(value) for value in actual_value}
                        return any(value in actual_values for value in required_values)
                    return str(actual_value) in required_values
            except (ValueError, IndexError):
                return False
        elif "!=" in condition:
            try:
                parts = condition.split("!=")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip().strip("'\"")

                    actual_value = dynamic_config.get(variable_name)

                    if required_value_str.lower() in ["true", "false"]:
                        required_value = required_value_str.lower() == "true"
                        actual_value = (
                            bool(actual_value) if actual_value is not None else False
                        )
                    else:
                        try:
                            required_value = int(required_value_str)
                            actual_value = (
                                int(actual_value) if actual_value is not None else 0
                            )
                        except (ValueError, TypeError):
                            required_value = required_value_str
                            actual_value = (
                                str(actual_value) if actual_value is not None else ""
                            )

                    return actual_value != required_value
            except (ValueError, IndexError):
                return False
        elif "==" in condition:
            try:
                parts = condition.split("==")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip().strip("'\"")

                    actual_value = dynamic_config.get(variable_name)

                    if required_value_str.lower() in ["true", "false"]:
                        required_value = required_value_str.lower() == "true"
                        actual_value = (
                            bool(actual_value) if actual_value is not None else False
                        )
                    else:
                        try:
                            required_value = int(required_value_str)
                            actual_value = (
                                int(actual_value) if actual_value is not None else 0
                            )
                        except (ValueError, TypeError):
                            required_value = required_value_str
                            actual_value = (
                                str(actual_value) if actual_value is not None else ""
                            )

                    return actual_value == required_value
            except (ValueError, IndexError):
                return False
        elif ">=" in condition:
            try:
                parts = condition.split(">=")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip()

                    try:
                        required_value = int(required_value_str)
                        actual_value = dynamic_config.get(variable_name, 0)
                        if isinstance(actual_value, str):
                            actual_value = int(actual_value)
                        return actual_value >= required_value
                    except ValueError:
                        return False
            except (ValueError, IndexError):
                return False

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
