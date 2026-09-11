"""Filter YAML template entities from dynamic_config and user input."""

from __future__ import annotations

import copy
import re
from typing import Any

from packaging import version

from .device_utils import (
    apply_version_replacements,
    collect_version_replacements,
    entity_allowed_for_protocol,
    resolve_firmware_profile_version,
)
from .logger import ModbusManagerLogger
from .template_loader import _evaluate_condition

_LOGGER = ModbusManagerLogger(__name__)


def migrate_legacy_battery_enabled(
    dynamic_config: dict, legacy_source: dict | None = None
) -> None:
    """Map deprecated battery_enabled bool to battery_config (iHomeManager legacy)."""
    battery_config = dynamic_config.get("battery_config")
    if isinstance(battery_config, dict):
        return
    if battery_config not in (None, "none"):
        return
    sources = [dynamic_config]
    if legacy_source:
        sources.append(legacy_source)
    for source in sources:
        if source.get("battery_enabled") is True:
            dynamic_config["battery_config"] = "battery"
            return


def resolve_battery_config_value(dynamic_config: dict, fallback: str = "none") -> str:
    """Return concrete battery_config string from dynamic_config."""
    battery_config = dynamic_config.get("battery_config", fallback)
    if isinstance(battery_config, dict):
        return str(battery_config.get("default", fallback))
    return str(battery_config or fallback)


def process_dynamic_config(user_input: dict, template_data: dict) -> dict:
    """Process template based on dynamic configuration parameters."""

    _LOGGER.debug(
        "_process_dynamic_config user_input keys: %s", list(user_input.keys())
    )

    original_sensors = template_data.get("sensors", [])
    original_calculated = template_data.get("calculated", [])
    original_controls = template_data.get("controls", [])
    # Deep-copy: template_data may reference the global template cache; in-place
    # mutation would replace option dicts (meter_type, etc.) with scalars and break
    # later config flows / schema generation for all templates using that cache entry.
    _dc_raw = template_data.get("dynamic_config", {})
    original_dynamic_config = (
        copy.deepcopy(_dc_raw) if isinstance(_dc_raw, dict) else {}
    )
    dynamic_config = copy.deepcopy(_dc_raw) if isinstance(_dc_raw, dict) else {}

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

        phases = user_input.get("phases", _safe_default(dynamic_config, "phases", 3))
        mppt_count = user_input.get(
            "mppt_count", _safe_default(dynamic_config, "mppt_count", 1)
        )
        string_count = user_input.get(
            "string_count", _safe_default(dynamic_config, "string_count", 1)
        )
        modules = user_input.get("modules", _safe_default(dynamic_config, "modules", 3))

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
    firmware_version = resolve_firmware_profile_version(firmware_version, template_data)
    connection_type = user_input.get("connection_type", "LAN")
    dynamic_config["connection_type"] = connection_type

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
    # Use original_dynamic_config snapshot (deepcopy at start) so defaults match YAML schema.
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

    migrate_legacy_battery_enabled(dynamic_config, user_input)
    if (
        "sbr" in template_data.get("name", "").lower()
        or "battery" in template_data.get("type", "").lower()
    ):
        battery_config = "sbr_battery"
        battery_type = "sbr_battery"
        battery_enabled = True
    else:
        battery_config = resolve_battery_config_value(
            dynamic_config, fallback=battery_config
        )
        battery_type = battery_config
        battery_enabled = battery_config != "none"
    dynamic_config["battery_config"] = battery_config
    dynamic_config["battery_enabled"] = battery_enabled

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
        _LOGGER.debug("Processing sensor: %s (unique_id: %s)", sensor_name, unique_id)

        should_include = _should_include_sensor(
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
            modified_sensor = _apply_firmware_modifications(
                sensor,
                firmware_version,
                dynamic_config,
                original_dynamic_config,
            )
            processed_sensors.append(modified_sensor)
            _LOGGER.debug("Included sensor: %s", sensor_name)
        else:
            _LOGGER.debug("Excluded sensor: %s", sensor_name)

    # Process calculated sensors
    for calculated in original_calculated:
        # Check if calculated sensor should be included based on configuration
        if _should_include_sensor(
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
        if _should_include_sensor(
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
            processed_controls.append(
                _apply_firmware_modifications(
                    control,
                    firmware_version,
                    dynamic_config,
                    original_dynamic_config,
                )
            )

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

    if not entity_allowed_for_protocol(sensor, dynamic_config.get("protocol_version")):
        return False

    # Check firmware_min_version filter first
    sensor_firmware_min = sensor.get("firmware_min_version")
    if sensor_firmware_min and firmware_version:
        try:
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
        mppt_number = _extract_mppt_number(search_text)
        if mppt_number and mppt_number > mppt_count:
            return False

    # String-specific sensors
    if "string" in search_text:
        string_number = _extract_string_number(search_text)
        if string_number and string_number > string_count:
            return False

    # Module-specific sensors (for batteries)
    if "module" in search_text:
        module_number = _extract_module_number(search_text)
        if module_number:
            actual_modules = dynamic_config.get("modules", 0)
            if module_number > actual_modules:
                return False

    # All other sensors are included
    return True


# REGEX FUNCTIONS
def _extract_mppt_number(search_text: str) -> int:
    """Extract MPPT number from sensor name or unique_id."""

    if not search_text:
        return None

    match = re.search(r"mppt(\d+)", search_text.lower())
    if match and match.group(1):
        try:
            return int(match.group(1))
        except (ValueError, TypeError):
            return None
    return None


def _extract_string_number(search_text: str) -> int:
    """Extract string number from sensor name or unique_id."""

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


def _extract_module_number(search_text: str) -> int:
    """Extract module number from sensor name or unique_id."""

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


# Firmware field replacements keyed by unique_id
def _apply_firmware_modifications(
    sensor: dict,
    firmware_version: str,
    dynamic_config: dict,
    original_dynamic_config: dict | None = None,
) -> dict:
    """Apply firmware/protocol field replacements keyed by unique_id."""
    replacements = collect_version_replacements(
        original_dynamic_config or dynamic_config
    )
    modified = apply_version_replacements(sensor, firmware_version, replacements)
    protocol_version = None
    if isinstance(dynamic_config, dict):
        protocol_version = dynamic_config.get("protocol_version")
    return apply_version_replacements(modified, protocol_version, replacements)
