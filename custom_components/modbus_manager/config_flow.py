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

from .combined_specs import resolve_combination_type
from .const import (
    CONF_ENTRY_TYPE,
    DEFAULT_DELAY,
    DEFAULT_MESSAGE_WAIT_MS,
    DEFAULT_PORT,
    DEFAULT_POST_WRITE_SETTLE_MS,
    DEFAULT_SLAVE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ENTRY_TYPE_COMBINED_DEVICE,
    ENTRY_TYPE_HUB,
    MAX_POST_WRITE_SETTLE_MS,
    MIN_DELAY,
    MIN_MESSAGE_WAIT_MS,
    MIN_POST_WRITE_SETTLE_MS,
    MIN_TIMEOUT,
    EntityIdStrategy,
)
from .device_utils import (
    async_get_registry_device,
    build_device_entry_id,
    connection_type_allowed,
    ensure_entity_id_strategy_on_device,
    entry_device_type_set,
    entry_host_port,
    generate_unique_id,
    get_entity_mm_group,
    hub_device_identifier,
    hub_entry_title_for_new_entry,
    is_hub_endpoint_taken,
    legacy_build_device_entry_id,
    legacy_hub_device_identifier,
    migrate_hub_device_identifiers,
    reload_dependent_combined_entries,
    replace_template_placeholders,
    resolve_device_role_type,
    updated_hub_entry_title,
)
from .dynamic_processing import process_dynamic_config
from .logger import ModbusManagerLogger
from .template_loader import (
    _evaluate_condition,
    get_template_by_name,
    get_template_names,
    invalidate_template_cache,
    resolve_template_key,
    set_hass_instance,
)

_LOGGER = ModbusManagerLogger(__name__)
COMBINED_TEMPLATE_SENTINEL = "__combined_device__"
# Dev-only: allow a second hub on the same host:port (local combined-device testing).
# CONF_TEST_ALLOW_SAME_ENDPOINT_NEW_HUB = "test_allow_same_endpoint_new_hub"


def _first_dynamic_option_value(options: Any) -> Any:
    """First selectable value from dynamic_config options (list/tuple or dict keys)."""
    if isinstance(options, dict) and options:
        return next(iter(options))
    if isinstance(options, (list, tuple)) and options:
        return options[0]
    return None


def _vol_in_from_dynamic_options(
    field_config: dict,
    *,
    current_value: Any | None = None,
) -> tuple[Any, vol.In]:
    """Build default and vol.In for dynamic_config options (list/tuple or value -> label dict)."""
    options = field_config.get("options", [])
    if not options:
        raise ValueError("options required")
    explicit = field_config.get("default")

    if isinstance(options, dict):
        keys = list(options.keys())
        if current_value is not None and current_value in options:
            default = current_value
        elif explicit is not None and explicit in options:
            default = explicit
        else:
            default = keys[0]
        return default, vol.In(options)

    seq = list(options)
    if current_value is not None and current_value in seq:
        default = current_value
    elif explicit is not None and explicit in seq:
        default = explicit
    else:
        default = seq[0]
    return default, vol.In(options)


_WINET_BATTERY_CONFIGS = frozenset({"none", "standard_battery", "sbr_battery", "other"})


def _entry_post_write_settle_ms(entry_data: dict[str, Any]) -> int:
    """Read configured post-write settle delay from hub entry data."""
    if "post_write_settle_milliseconds" in entry_data:
        return int(entry_data["post_write_settle_milliseconds"])
    hub = entry_data.get("hub")
    if isinstance(hub, dict) and "post_write_settle_milliseconds" in hub:
        return int(hub["post_write_settle_milliseconds"])
    return DEFAULT_POST_WRITE_SETTLE_MS


def _apply_post_write_settle_to_entry_data(
    entry_data: dict[str, Any], milliseconds: int
) -> None:
    """Persist post-write settle on hub entry (top-level + hub dict)."""
    entry_data["post_write_settle_milliseconds"] = milliseconds
    hub = entry_data.get("hub")
    if isinstance(hub, dict):
        hub["post_write_settle_milliseconds"] = milliseconds


def _clamp_battery_config_for_connection(
    battery_config: Any, connection_type: Any
) -> str:
    """Keep battery_config on a known option for the hub connection type.

    WiNet-S can use the separate SBR/SBH pack template (forwarded unit id).
    ``other`` is still remapped to ``standard_battery`` (inverter slave 1).
    """
    value = str(battery_config or "none").strip()
    if str(connection_type or "LAN").strip().upper() == "WINET":
        if value == "other":
            return "standard_battery"
        if value not in _WINET_BATTERY_CONFIGS:
            return "none"
    return value


def _default_battery_slave_id(template_default: Any, connection_type: Any) -> int:
    """Default pack unit id: 200 on LAN/RS485, forwarded id 2 on WiNet-S."""
    if str(connection_type or "LAN").strip().upper() == "WINET":
        return 2
    try:
        return int(template_default if template_default is not None else 200)
    except (TypeError, ValueError):
        return 200


# Hub-level keys copied onto per-device records when missing (legacy setups).
_ENTRY_LEVEL_DEVICE_FIELD_FALLBACKS = (
    "connection_type",
    "meter_type",
    "battery_config",
    "firmware_version",
    "selected_model",
    "phases",
    "mppt_count",
    "string_count",
    "modules",
    "entity_id_strategy",
    "wallbox_connected",
)


def _apply_entry_data_fallbacks_to_device(
    device: dict[str, Any], entry_data: dict[str, Any]
) -> dict[str, Any]:
    """Merge hub-level dynamic fields into a device record when missing per-device."""
    merged = dict(device)
    for key in _ENTRY_LEVEL_DEVICE_FIELD_FALLBACKS:
        if key not in merged and key in entry_data:
            merged[key] = entry_data[key]
    return merged


def _device_display_title(device: dict[str, Any]) -> str:
    """Short label for a hub device in options / reconfigure forms."""
    identity = device.get("selected_model") or device.get("prefix")
    text = str(identity).strip() if identity else ""
    return text or "device"


def _normalize_stored_device(device: dict[str, Any]) -> dict[str, Any]:
    """Ensure type, template_key, and device_entry_id on a devices[] record."""
    normalized = dict(device)
    normalized["type"] = resolve_device_role_type(normalized)
    template_key = normalized.get("template_key") or resolve_template_key(
        str(normalized.get("template", "template"))
    )
    normalized["template_key"] = template_key
    normalized["device_entry_id"] = normalized.get(
        "device_entry_id", build_device_entry_id(normalized)
    )
    return normalized


def _device_reconfigure_schema(
    selected_device: dict[str, Any], template_data: dict[str, Any] | None
) -> vol.Schema:
    """Build prefix / slave / model / dynamic_config schema for one device."""
    dynamic_config = (
        template_data.get("dynamic_config", {})
        if isinstance(template_data, dict)
        else {}
    )
    if not isinstance(dynamic_config, dict):
        dynamic_config = {}

    schema_fields: dict[Any, Any] = {
        vol.Required("prefix", default=selected_device.get("prefix", "device")): str,
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
        schema_fields[vol.Optional("selected_model", default=default_model)] = vol.In(
            model_options
        )

    for field_name, field_config in dynamic_config.items():
        if field_name in ("valid_models", "selected_model"):
            continue
        if isinstance(field_config, dict) and "options" in field_config:
            options = field_config.get("options", [])
            if options:
                if (
                    field_name == "battery_config"
                    and str(selected_device.get("connection_type", "LAN"))
                    .strip()
                    .upper()
                    == "WINET"
                ):
                    field_config = dict(field_config)
                    opts = field_config.get("options", [])
                    if isinstance(opts, list):
                        field_config["options"] = [
                            o for o in opts if o in _WINET_BATTERY_CONFIGS
                        ]
                current = selected_device.get(field_name, field_config.get("default"))
                if (
                    field_name == "battery_config"
                    and selected_device.get("battery_enabled") is True
                    and current in (None, "none", field_config.get("default"))
                ):
                    current = "battery"
                if field_name == "battery_config":
                    current = _clamp_battery_config_for_connection(
                        current, selected_device.get("connection_type")
                    )
                default, vol_in = _vol_in_from_dynamic_options(
                    field_config, current_value=current
                )
                schema_fields[vol.Optional(field_name, default=default)] = vol_in
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

    return vol.Schema(schema_fields)


def _apply_device_reconfigure(
    entry_data: dict[str, Any],
    selected_device_id: str,
    user_input: dict[str, Any],
    template_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return new hub entry.data with one devices[] record updated."""
    devices: list[dict[str, Any]] = []
    for device in entry_data.get("devices") or []:
        if not isinstance(device, dict):
            continue
        record = dict(device)
        if not record.get("device_entry_id"):
            record["device_entry_id"] = build_device_entry_id(record)
        devices.append(record)

    selected_device = next(
        (d for d in devices if d.get("device_entry_id") == selected_device_id),
        None,
    )
    if selected_device is None:
        raise ValueError(f"Device {selected_device_id} not found in hub data")

    selected_device = _apply_entry_data_fallbacks_to_device(selected_device, entry_data)
    dynamic_config = (
        template_data.get("dynamic_config", {})
        if isinstance(template_data, dict)
        else {}
    )
    if not isinstance(dynamic_config, dict):
        dynamic_config = {}

    updated_device = dict(selected_device)
    updated_device["prefix"] = str(
        user_input.get("prefix", updated_device.get("prefix", ""))
    )
    updated_device["slave_id"] = user_input.get(
        "slave_id", updated_device.get("slave_id", 1)
    )
    if "selected_model" in user_input:
        updated_device["selected_model"] = user_input["selected_model"]

    for field_name in dynamic_config:
        if field_name == "valid_models":
            continue
        if field_name in user_input:
            updated_device[field_name] = user_input[field_name]

    updated_device["battery_config"] = _clamp_battery_config_for_connection(
        updated_device.get("battery_config"),
        updated_device.get("connection_type"),
    )
    updated_device = _normalize_stored_device(updated_device)

    new_devices = [
        updated_device if d.get("device_entry_id") == selected_device_id else d
        for d in devices
    ]
    new_data = dict(entry_data)
    new_data["devices"] = new_devices

    legacy_device_id = build_device_entry_id(
        {
            "prefix": entry_data.get("prefix"),
            "slave_id": entry_data.get("slave_id", 1),
            "template": entry_data.get("template"),
        }
    )
    if selected_device_id == legacy_device_id:
        new_data["prefix"] = updated_device.get("prefix", entry_data.get("prefix"))
        new_data["slave_id"] = updated_device.get(
            "slave_id", entry_data.get("slave_id", 1)
        )
        if "selected_model" in updated_device:
            new_data["selected_model"] = updated_device["selected_model"]
        for field_name in dynamic_config:
            if field_name in updated_device:
                new_data[field_name] = updated_device[field_name]

    return new_data


def _dynamic_input_for_device(
    device: dict[str, Any],
    template_data: dict[str, Any],
    entry_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build _process_dynamic_config input from one devices[] record."""
    merged = _apply_entry_data_fallbacks_to_device(device, entry_data or {})
    dynamic_config = (
        template_data.get("dynamic_config", {})
        if isinstance(template_data, dict)
        else {}
    )
    if not isinstance(dynamic_config, dict):
        dynamic_config = {}

    result: dict[str, Any] = {
        "slave_id": merged.get("slave_id", 1),
        "phases": merged.get("phases", 1),
        "mppt_count": merged.get("mppt_count", 2),
        "string_count": merged.get("string_count", 0),
        "battery_config": merged.get("battery_config", "none"),
        "battery_slave_id": merged.get("battery_slave_id", 200),
        "firmware_version": merged.get("firmware_version", "1.0.0"),
        "connection_type": merged.get("connection_type", "LAN"),
        "meter_type": merged.get("meter_type", "DTSU666"),
        "selected_model": merged.get("selected_model"),
    }
    for field_name, field_config in dynamic_config.items():
        if field_name == "valid_models":
            continue
        if field_name in merged:
            result[field_name] = merged[field_name]
            continue
        if isinstance(field_config, dict):
            if "default" in field_config:
                result[field_name] = field_config.get("default")
            elif "options" in field_config:
                result[field_name] = _first_dynamic_option_value(
                    field_config.get("options", [])
                )
    return result


def _format_template_reload_summary(rows: list[dict[str, Any]], language: str) -> str:
    """Plain-text confirmation list for every hub device template."""
    lang = str(language or "en").split("-", 1)[0].lower()
    changed_word = "changed" if lang != "de" else "geändert"
    same_word = "unchanged" if lang != "de" else "unverändert"
    blocks: list[str] = []
    for row in rows:
        status = (
            changed_word
            if row.get("stored_version") != row.get("current_version")
            else same_word
        )
        blocks.append(
            f"{row.get('title')} — {row.get('template_name')}\n"
            f"  v{row.get('stored_version')} → v{row.get('current_version')} ({status})\n"
            f"  {row.get('sensors', 0)} sensors, {row.get('calculated', 0)} calculated, "
            f"{row.get('controls', 0)} controls"
        )
    return "\n\n".join(blocks) if blocks else ""


def _backfill_devices_from_entry_data(
    devices: list[dict[str, Any]],
    entry_data: dict[str, Any],
    normalize_fn,
) -> list[dict[str, Any]]:
    """Backfill missing per-device dynamic fields from legacy hub-level entry.data."""
    backfilled: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        backfilled.append(
            normalize_fn(_apply_entry_data_fallbacks_to_device(device, entry_data))
        )
    return backfilled


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
        entry_type = entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_HUB)
        if entry_type == ENTRY_TYPE_COMBINED_DEVICE:
            combined_prefix = str(entry.data.get("combined_prefix", "")).strip().lower()
            if combined_prefix and combined_prefix == normalized:
                return False
            continue

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

    VERSION = 7

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self._templates = {}
        self._selected_template = None

    def _combined_source_candidates(self) -> dict[str, str]:
        """Return selectable source entries for combined device flow."""
        candidates: dict[str, str] = {}
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_HUB)
                == ENTRY_TYPE_COMBINED_DEVICE
            ):
                continue
            type_set = entry_device_type_set(entry)
            if not ({"inverter", "energy_manager"} & type_set):
                continue

            devices = entry.data.get("devices", [])
            if isinstance(devices, list) and devices:
                prefixes = sorted(
                    {
                        str(device.get("prefix", "")).strip()
                        for device in devices
                        if isinstance(device, dict)
                        and str(device.get("prefix", "")).strip()
                    }
                )
                label = (
                    ", ".join(prefixes) if prefixes else entry.title or entry.entry_id
                )
            else:
                label = entry.title or entry.entry_id

            candidates[entry.entry_id] = f"{label} ({entry.entry_id[:8]})"

        return candidates

    def _resolve_combination_type(
        self, source_a: config_entries.ConfigEntry, source_b: config_entries.ConfigEntry
    ) -> str | None:
        """Return supported combination type for two source entries."""
        return resolve_combination_type(source_a, source_b)

    def _build_device_entry_id(self, device: dict[str, Any]) -> str:
        """Build a stable logical device id inside one hub entry."""
        return build_device_entry_id(device)

    def _normalize_device_record(self, device: dict[str, Any]) -> dict[str, Any]:
        """Normalize a device record and ensure required subentry-like fields."""
        normalized = dict(device)
        normalized["type"] = resolve_device_role_type(normalized)
        template_key = normalized.get("template_key") or resolve_template_key(
            str(normalized.get("template", "template"))
        )
        normalized["template_key"] = template_key
        normalized["device_entry_id"] = normalized.get(
            "device_entry_id", self._build_device_entry_id(normalized)
        )
        ensure_entity_id_strategy_on_device(normalized)
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
                new_data["devices"] = _backfill_devices_from_entry_data(
                    normalized_devices,
                    new_data,
                    self._normalize_device_record,
                )
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

            # v6: device registry identifiers are keyed by device_entry_id (one device per subentry).
            if config_entry.version < 6:
                new_data.pop("device_registry_relink_completed", None)
                new_data["pending_registry_relink"] = True

            # v7: device_entry_id uses template file stem (sungrow_shx_dynamic), not display name.
            if config_entry.version < 7:
                set_hass_instance(hass)
                id_remap: dict[str, str] = {}
                devices_for_v7 = new_data.get("devices", [])
                if isinstance(devices_for_v7, list):
                    migrated_devices_v7: list[dict[str, Any]] = []
                    for device in devices_for_v7:
                        if not isinstance(device, dict):
                            continue
                        normalized = dict(device)
                        old_id = normalized.get(
                            "device_entry_id"
                        ) or legacy_build_device_entry_id(normalized)
                        template_key = resolve_template_key(
                            str(normalized.get("template", "template"))
                        )
                        normalized["template_key"] = template_key
                        new_id = build_device_entry_id(normalized)
                        normalized["device_entry_id"] = new_id
                        if old_id != new_id:
                            id_remap[old_id] = new_id
                        migrated_devices_v7.append(
                            self._normalize_device_record(normalized)
                        )
                    new_data["devices"] = migrated_devices_v7
                if id_remap:
                    new_data["device_entry_id_remap"] = id_remap
                new_data.pop("device_registry_relink_completed", None)
                new_data["pending_registry_relink"] = True

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
                    if self._selected_template == COMBINED_TEMPLATE_SENTINEL:
                        return await self.async_step_combined_device()
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

            # Show template selection (stored value = template `name`; label = display_name)
            template_names = sorted(list(self._templates.keys()))
            template_choices = {
                name: (
                    (self._templates[name].get("display_name") or "").strip() or name
                )
                for name in template_names
            }
            template_choices[COMBINED_TEMPLATE_SENTINEL] = "Combined Device (cross-hub)"
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("template"): vol.In(template_choices),
                    }
                ),
                description_placeholders={
                    "config_flow_note": "",
                    "template_count": str(len(template_names)),
                    "template_list": ", ".join(template_choices.values()),
                },
            )

        except Exception as e:
            _LOGGER.error("Error in Config Flow: %s", str(e))
            return self.async_abort(
                reason="unknown_error", description_placeholders={"error": str(e)}
            )

    async def async_step_combined_device(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Create a virtual cross-hub combined-device entry."""
        source_choices = self._combined_source_candidates()
        if len(source_choices) < 2:
            return self.async_abort(reason="no_eligible_sources")

        errors: dict[str, str] = {}
        if user_input is not None:
            source_a_id = user_input.get("source_entry_id_a")
            source_b_id = user_input.get("source_entry_id_b")
            combined_prefix = str(user_input.get("combined_prefix", "")).strip()

            if source_a_id == source_b_id:
                errors["base"] = "same_source_selected"
            else:
                source_a = next(
                    (
                        entry
                        for entry in self.hass.config_entries.async_entries(DOMAIN)
                        if entry.entry_id == source_a_id
                    ),
                    None,
                )
                source_b = next(
                    (
                        entry
                        for entry in self.hass.config_entries.async_entries(DOMAIN)
                        if entry.entry_id == source_b_id
                    ),
                    None,
                )
                if not source_a or not source_b:
                    errors["base"] = "source_not_found"
                else:
                    combination_type = self._resolve_combination_type(
                        source_a, source_b
                    )
                    if not combination_type:
                        errors["base"] = "invalid_pair"
                    elif not _is_prefix_unique_across_hubs(self.hass, combined_prefix):
                        errors["combined_prefix"] = "already_configured"
                    else:
                        source_ids_sorted = sorted([source_a_id, source_b_id])
                        await self.async_set_unique_id(
                            f"combined_{source_ids_sorted[0]}_{source_ids_sorted[1]}"
                        )
                        self._abort_if_unique_id_configured()

                        title = f"Combined {combined_prefix}"
                        data = {
                            CONF_ENTRY_TYPE: ENTRY_TYPE_COMBINED_DEVICE,
                            "source_entry_id_a": source_a_id,
                            "source_entry_id_b": source_b_id,
                            "combination_type": combination_type,
                            "combined_prefix": combined_prefix,
                        }
                        return self.async_create_entry(title=title, data=data)

        defaults = list(source_choices.keys())
        default_a = defaults[0]
        default_b = defaults[1]
        default_prefix = "combined"
        if default_a in source_choices and default_b in source_choices:
            label_a = source_choices[default_a].split(" (", 1)[0]
            label_b = source_choices[default_b].split(" (", 1)[0]
            default_prefix = f"{label_a}_{label_b}".strip().lower().replace(" ", "_")

        return self.async_show_form(
            step_id="combined_device",
            data_schema=vol.Schema(
                {
                    vol.Required("source_entry_id_a", default=default_a): vol.In(
                        source_choices
                    ),
                    vol.Required("source_entry_id_b", default=default_b): vol.In(
                        source_choices
                    ),
                    vol.Required("combined_prefix", default=default_prefix): str,
                }
            ),
            errors=errors,
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
            _apply_post_write_settle_to_entry_data(
                new_data,
                int(
                    user_input.get(
                        "post_write_settle_milliseconds",
                        _entry_post_write_settle_ms(config_entry.data),
                    )
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
                    vol.Required(
                        "post_write_settle_milliseconds",
                        default=_entry_post_write_settle_ms(config_entry.data),
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

            # Proceed to model selection or dynamic config
            _LOGGER.info(
                "Connection parameters stored, proceeding to dynamic configuration"
            )
            return await self._route_after_connection_setup()

        # Get template defaults for prefilling
        template_data = self._templates.get(self._selected_template, {})
        default_prefix = template_data.get("default_prefix", "SG")
        default_slave_id = template_data.get("default_slave_id", DEFAULT_SLAVE)
        # Show config_flow_note when selected template has one (e.g. SBR slave-id hint)
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
                    vol.Optional(
                        "post_write_settle_milliseconds",
                        default=DEFAULT_POST_WRITE_SETTLE_MS,
                    ): int,
                    # vol.Optional(
                    #     CONF_TEST_ALLOW_SAME_ENDPOINT_NEW_HUB, default=False
                    # ): bool,
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
            return await self._route_after_connection_setup()

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
            selected_model = getattr(self, "_selected_model", None) or self.context.get(
                "selected_model"
            )
            dynamic_partial: dict[str, Any] = {}
            if selected_model:
                dynamic_partial["selected_model"] = selected_model
            # Combine connection params with dynamic config
            combined_input = {
                **self._connection_params,
                **dynamic_partial,
                **user_input,
            }

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
                # Check battery_config condition (skip battery flow when not met)
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
        include_model_selection = not self._template_has_model_selection(template_data)
        schema_fields = self._get_dynamic_config_schema(
            template_data,
            user_input,
            include_model_selection=include_model_selection,
        )

        description_placeholders = {
            "template_name": self._selected_template,
            "model_note": "",
        }
        selected_model = getattr(self, "_selected_model", None) or self.context.get(
            "selected_model"
        )
        if selected_model:
            description_placeholders["model_note"] = f" ({selected_model})"

        return self.async_show_form(
            step_id="dynamic_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders=description_placeholders,
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
                vol.Optional(
                    "post_write_settle_milliseconds",
                    default=DEFAULT_POST_WRITE_SETTLE_MS,
                ): int,
                # vol.Optional(
                #     CONF_TEST_ALLOW_SAME_ENDPOINT_NEW_HUB, default=False
                # ): bool,
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

    @staticmethod
    def _battery_config_in_separate_flow(template_data: dict) -> bool:
        """PV inverters use async_step_battery_detection; others show battery_config inline."""
        template_type = (template_data.get("type") or "").lower()
        return template_type in (
            "pv_inverter",
            "pv_hybrid_inverter",
        ) and isinstance(
            template_data.get("dynamic_config", {}).get("battery_config"), dict
        )

    @staticmethod
    def _get_valid_models(template_data: dict) -> dict[str, Any] | None:
        """Return valid_models mapping from template dynamic_config or root."""
        dynamic_config = template_data.get("dynamic_config", {})
        valid_models = dynamic_config.get("valid_models") or template_data.get(
            "valid_models"
        )
        if valid_models and isinstance(valid_models, dict):
            return valid_models
        return None

    def _template_has_model_selection(self, template_data: dict) -> bool:
        """Return True when template exposes a valid_models model picker."""
        return self._get_valid_models(template_data) is not None

    @staticmethod
    def _build_model_option_labels(valid_models: dict[str, Any]) -> dict[str, str]:
        """Build display labels for valid_models dropdown options."""
        model_options: dict[str, str] = {}
        for model_name, config in valid_models.items():
            field_parts = []
            for field_name, field_value in config.items():
                if field_name == "phases":
                    field_parts.append(f"{field_value}Φ")
                elif field_name == "mppt_count":
                    field_parts.append(f"{field_value} MPPT")
                elif field_name == "string_count":
                    field_parts.append(f"{field_value} Strings")
                elif field_name == "modules":
                    field_parts.append(f"{field_value} Modules")
                elif field_name == "type_code":
                    continue
                else:
                    field_parts.append(f"{field_name}: {field_value}")
            model_options[model_name] = f"{model_name} ({', '.join(field_parts)})"
        return model_options

    def _get_model_selection_schema(
        self, template_data: dict, selected_model: str | None = None
    ) -> dict[Any, Any]:
        """Generate schema for the dedicated model-selection step."""
        valid_models = self._get_valid_models(template_data)
        if not valid_models:
            return {}

        model_options = self._build_model_option_labels(valid_models)
        default_model = next(iter(model_options))
        current_model = (
            selected_model
            if selected_model and selected_model in model_options
            else default_model
        )
        return {
            vol.Required("selected_model", default=current_model): vol.In(model_options)
        }

    async def _route_after_connection_setup(self) -> FlowResult:
        """Proceed to model selection or dynamic params after connection step."""
        template_data = self._templates.get(self._selected_template, {})
        if self._template_has_model_selection(template_data):
            return await self.async_step_model_selection()
        return await self.async_step_dynamic_config()

    async def async_step_model_selection(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle dedicated model selection step before other dynamic parameters."""
        template_data = self._templates.get(self._selected_template, {})
        if not self._template_has_model_selection(template_data):
            return await self.async_step_dynamic_config()

        if user_input is not None:
            self._selected_model = user_input["selected_model"]
            self.context["selected_model"] = user_input["selected_model"]
            return await self.async_step_dynamic_config()

        stored_model = getattr(self, "_selected_model", None) or self.context.get(
            "selected_model"
        )
        schema_fields = self._get_model_selection_schema(template_data, stored_model)
        return self.async_show_form(
            step_id="model_selection",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={"template_name": self._selected_template},
        )

    def _get_dynamic_config_schema(
        self,
        template_data: dict,
        user_input: dict = None,
        *,
        include_model_selection: bool = True,
    ) -> dict:
        """Generate dynamic configuration schema based on template."""
        dynamic_config = template_data.get("dynamic_config", {})
        schema_fields = {}

        valid_models = self._get_valid_models(template_data)

        # Get selected_model from user_input if available (for dynamic updates)
        selected_model = None
        if user_input:
            selected_model = user_input.get("selected_model")

        if include_model_selection and valid_models:
            model_options = self._build_model_option_labels(valid_models)
            default_model = next(iter(model_options))
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
        should_hide_model_fields = bool(valid_models)

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
            if (
                field_name == "battery_config"
                and self._battery_config_in_separate_flow(template_data)
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

                if options:
                    # Handle boolean fields specially (list/tuple only; dict options are labels)
                    if not isinstance(options, dict) and (
                        all(isinstance(opt, bool) for opt in options)
                        or (len(options) == 2 and set(options) == {True, False})
                    ):
                        default = field_config.get(
                            "default",
                            options[0] if options else None,
                        )
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
                        default, vol_in = _vol_in_from_dynamic_options(field_config)
                        schema_fields[
                            vol.Optional(field_name, default=default)
                        ] = vol_in
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
            fw_cfg = dynamic_config["firmware_version"]
            if isinstance(fw_cfg, dict) and "options" in fw_cfg:
                fw_default, fw_in = _vol_in_from_dynamic_options(fw_cfg)
                schema_fields[
                    vol.Optional("firmware_version", default=fw_default)
                ] = fw_in

        # Add connection type if available
        if "connection_type" in dynamic_config:
            ct_cfg = dynamic_config["connection_type"]
            if isinstance(ct_cfg, dict) and "options" in ct_cfg:
                ct_default, ct_in = _vol_in_from_dynamic_options(ct_cfg)
                schema_fields[
                    vol.Optional("connection_type", default=ct_default)
                ] = ct_in

        # Battery slave ID removed - using connection slave_id instead
        # SunSpec model address fields are now handled automatically via dynamic_config
        # They will be added by the generic loop above if defined in template's dynamic_config

        _LOGGER.debug("Final schema fields: %s", list(schema_fields.keys()))
        return schema_fields

    # Process dynamic configuration and filtering out the sensors, calculated, controls and binary sensors
    def _process_dynamic_config(self, user_input: dict, template_data: dict) -> dict:
        """Process template based on dynamic configuration parameters."""
        return process_dynamic_config(user_input, template_data)

    # Step 4: Battery detection for PV inverters
    async def async_step_battery_detection(self, user_input: dict = None) -> FlowResult:
        """Ask if battery is available for PV inverter."""
        _LOGGER.debug("=== BATTERY DETECTION STEP CALLED ===")
        _LOGGER.debug("User input: %s", user_input)

        if user_input is not None:
            _LOGGER.debug("Battery available: %s", user_input.get("battery_available"))
            if user_input.get("battery_available"):
                conn = (
                    str(
                        (self._inverter_config or {}).get("connection_type")
                        or self.context.get("connection_type")
                        or "LAN"
                    )
                    .strip()
                    .upper()
                )
                if conn == "WINET":
                    if self._inverter_config is not None:
                        self._inverter_config["battery_config"] = "standard_battery"
                        self._inverter_config["battery_template"] = "none"
                        if not self._inverter_config.get("connection_type"):
                            self._inverter_config["connection_type"] = (
                                self.context.get("connection_type") or "WINET"
                            )
                    self._keep_inverter_battery_entities = True
                    return await self.async_step_final_config(self._inverter_config)
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
                    # Filter by requires_connection_type (string or list)
                    required_conn = template_data.get("requires_connection_type")
                    if required_conn and not connection_type_allowed(
                        connection_type_norm, required_conn
                    ):
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
                    display_name = (
                        template_data.get("display_name") or ""
                    ).strip() or template_name
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
        config_flow_note = ""

        if battery_template_data and isinstance(battery_template_data, dict):
            default_slave_id = _default_battery_slave_id(
                battery_template_data.get("default_slave_id", 200),
                (self._inverter_config or {}).get("connection_type", "LAN"),
            )
            default_prefix = battery_template_data.get("default_prefix", "SBR")
            config_flow_note = battery_template_data.get("config_flow_note", "") or ""

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
                "config_flow_note": config_flow_note,
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
            sensor_group = get_entity_mm_group(sensor) or ""
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
                        "message_wait_milliseconds": self._inverter_config.get(
                            "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                        ),
                        "post_write_settle_milliseconds": self._inverter_config.get(
                            "post_write_settle_milliseconds",
                            DEFAULT_POST_WRITE_SETTLE_MS,
                        ),
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
                    "type": template_data.get("type", "inverter"),
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
                    device["connection_type"] = connection_type

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
                    "post_write_settle_milliseconds": user_input.get(
                        "post_write_settle_milliseconds",
                        DEFAULT_POST_WRITE_SETTLE_MS,
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
                "post_write_settle_milliseconds": user_input.get(
                    "post_write_settle_milliseconds",
                    DEFAULT_POST_WRITE_SETTLE_MS,
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
                entity_strategy_opt = config_values.get("dynamic_config", {}).get(
                    "entity_id_strategy"
                )
                if entity_strategy_opt is not None:
                    config_data["entity_id_strategy"] = entity_strategy_opt

            if config_data.get("devices"):
                config_data["devices"] = [
                    self._normalize_device_record(
                        _apply_entry_data_fallbacks_to_device(device, config_data)
                    )
                    for device in config_data["devices"]
                ]

            # Create title from identity for new hubs; do not rename existing entries.
            host = config_data.get("host", "unknown")
            port = config_data.get("port", 502)
            title = hub_entry_title_for_new_entry(devices, host, port)
            # Dev-only: re-enable CONF_TEST_ALLOW_SAME_ENDPOINT_NEW_HUB in schema to test
            # combined device on a single physical Modbus endpoint.
            allow_same_endpoint_new_hub = False
            # allow_same_endpoint_new_hub = bool(
            #     user_input.get(CONF_TEST_ALLOW_SAME_ENDPOINT_NEW_HUB, False)
            # )

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

            if existing_entry and not allow_same_endpoint_new_hub:
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
                # if existing_entry and allow_same_endpoint_new_hub:
                #     _LOGGER.warning(
                #         "TEST-ONLY MODE active: creating separate hub for duplicate endpoint %s:%s. "
                #         "Remove '%s' usage after local combined testing.",
                #         host,
                #         port,
                #         CONF_TEST_ALLOW_SAME_ENDPOINT_NEW_HUB,
                #     )
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
                    for key in (
                        "connection_type",
                        "battery_config",
                        "battery_enabled",
                        "meter_type",
                        "wallbox_connected",
                        "entity_id_strategy",
                    ):
                        if key in config_data:
                            legacy_device[key] = config_data[key]
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

            # Create title from identity for new hubs; do not rename existing entries.
            host = self._connection_data.get("host", "unknown")
            port = self._connection_data.get("port", 502)
            title = hub_entry_title_for_new_entry(
                [
                    {
                        "type": template_data.get("type"),
                        "template": self._selected_template,
                        "prefix": user_input["prefix"],
                        "selected_model": user_input.get("selected_model"),
                    }
                ],
                host,
                port,
            )

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
        if config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_COMBINED_DEVICE:
            return {}
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
                    default, vol_in = _vol_in_from_dynamic_options(field_config)
                    schema_fields[vol.Optional(field_name, default=default)] = vol_in
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

        template_choices = {}
        for tn in template_names:
            td = await get_template_by_name(tn)
            label = (
                (td.get("display_name") or "").strip() or tn
                if isinstance(td, dict)
                else tn
            )
            template_choices[tn] = label

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
                        template_choices
                    ),
                }
            ),
        )

    @staticmethod
    def _build_device_entry_id(device: dict[str, Any]) -> str:
        return build_device_entry_id(device)

    @classmethod
    def _normalize_device_record(cls, device: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(device)
        normalized["type"] = resolve_device_role_type(normalized)
        template_key = normalized.get("template_key") or resolve_template_key(
            str(normalized.get("template", "template"))
        )
        normalized["template_key"] = template_key
        normalized["device_entry_id"] = normalized.get(
            "device_entry_id", cls._build_device_entry_id(normalized)
        )
        return normalized

    @classmethod
    def _get_devices(cls, entry: config_entries.ConfigEntry) -> list[dict[str, Any]]:
        entry_data = entry.data
        devices = entry_data.get("devices", [])
        if isinstance(devices, list) and devices:
            return [
                cls._normalize_device_record(
                    _apply_entry_data_fallbacks_to_device(device, entry_data)
                )
                for device in devices
                if isinstance(device, dict)
            ]
        template = entry_data.get("template")
        if not template:
            return []
        legacy_device = _apply_entry_data_fallbacks_to_device(
            {
                "type": "inverter",
                "template": template,
                "prefix": entry_data.get("prefix", "unknown"),
                "slave_id": entry_data.get("slave_id", 1),
            },
            entry_data,
        )
        return [cls._normalize_device_record(legacy_device)]

    @staticmethod
    def _build_subentry_title(device: dict[str, Any]) -> str:
        return _device_display_title(device)

    @staticmethod
    def _build_subentry_data(device: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "device_entry_id",
            "template_key",
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
                        dynamic_input[field_name] = _first_dynamic_option_value(options)

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
        """Add a new device to the selected hub (stored in devices[], no extra row)."""
        entry = self._get_entry()
        if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_COMBINED_DEVICE:
            return self.async_abort(reason="combined_device")
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
            new_data.pop("pending_subentry_device_id", None)
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_abort(reason="device_attached")

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

        selected_device = _apply_entry_data_fallbacks_to_device(
            selected_device, entry.data
        )

        template_name = selected_device.get("template")
        template_data = (
            await get_template_by_name(template_name) if template_name else None
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

            new_data = _apply_device_reconfigure(
                entry.data,
                selected_device_id,
                user_input,
                template_data,
            )
            updated_device = next(
                (
                    device
                    for device in new_data.get("devices", [])
                    if device.get("device_entry_id") == selected_device_id
                ),
                selected_device,
            )
            new_device_id = updated_device.get("device_entry_id")

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
                        template_uid = entity_def.get("unique_id")
                        resolved_uid = replace_template_placeholders(
                            template_uid or "",
                            device_prefix,
                            0,
                            0,
                            EntityIdStrategy.LEGACY_PREFIXED,
                            for_registry_unique_id=True,
                        )
                        expected_unique_ids.add(
                            generate_unique_id(
                                device_prefix,
                                resolved_uid or template_uid,
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

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_device_reconfigure_schema(selected_device, template_data),
            description_placeholders={
                "device": _device_display_title(selected_device),
            },
        )


# Dict labels for async_show_menu (list lookups stay blank until HA restarts).
_OPTIONS_MENU_LABELS = {
    "en": {
        "connection": "Connection — host, port, and request timing",
        "inverter": "Inverter — model, MPPT, and connection",
        "device": "Device — heating, wallbox, and other options",
        "battery": "Battery — model, prefix, and slave",
        "battery_template": "Battery — add, change, or remove template",
        "reload_template": "Reload register templates",
    },
    "de": {
        "connection": "Verbindung — Host, Port und Timing",
        "inverter": "Wechselrichter — Modell, MPPT und Verbindung",
        "device": "Gerät — Heizkreis, Wallbox und Optionen",
        "battery": "Batterie — Modell, Prefix und Slave",
        "battery_template": "Batterie — Template hinzufügen, wechseln oder entfernen",
        "reload_template": "Register-Templates neu laden",
    },
}


class ModbusManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Manager."""

    def __init__(self) -> None:
        """Initialize options flow state."""
        super().__init__()

    def _build_device_entry_id(self, device: dict[str, Any]) -> str:
        """Build stable logical device id."""
        return build_device_entry_id(device)

    def _get_editable_devices(self) -> list[dict[str, Any]]:
        """Return normalized list of devices that can be edited."""
        devices = self.config_entry.data.get("devices", [])
        if not isinstance(devices, list):
            return []

        normalized_devices: list[dict[str, Any]] = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            normalized = _apply_entry_data_fallbacks_to_device(
                device, self.config_entry.data
            )
            normalized = _normalize_stored_device(normalized)
            normalized_devices.append(normalized)
        return normalized_devices

    def _devices_with_role(self, role: str) -> list[dict[str, Any]]:
        """Devices whose resolved role matches ``role``."""
        return [
            device
            for device in self._get_editable_devices()
            if resolve_device_role_type(device) == role
        ]

    def _other_option_devices(self) -> list[dict[str, Any]]:
        """Heating, wallbox, energy manager — not inverter or battery."""
        return [
            device
            for device in self._get_editable_devices()
            if resolve_device_role_type(device) not in {"inverter", "battery"}
        ]

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
                device_entry_id = battery_device.get(
                    "device_entry_id"
                ) or build_device_entry_id(battery_device)
                device_identifier = hub_device_identifier(host, port, device_entry_id)

                device_entry = async_get_registry_device(
                    device_registry,
                    device_identifier,
                    self.config_entry.entry_id,
                )
                if device_entry is None:
                    battery_slave_id = battery_device.get("slave_id", 200)
                    legacy_identifier = legacy_hub_device_identifier(
                        host, port, battery_slave_id
                    )
                    device_entry = async_get_registry_device(
                        device_registry,
                        legacy_identifier,
                        self.config_entry.entry_id,
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
                            "Removed battery device '%s' (%s) from device registry",
                            battery_device.get("prefix", "unknown"),
                            device_entry_id,
                        )
                    else:
                        _LOGGER.debug(
                            "Battery device '%s' (%s) not found in device registry or belongs to different config entry",
                            battery_device.get("prefix", "unknown"),
                            device_entry_id,
                        )
                else:
                    _LOGGER.debug(
                        "Battery device '%s' (%s) not found in device registry",
                        battery_device.get("prefix", "unknown"),
                        device_entry_id,
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

    def _options_menu_options(self) -> list[str]:
        """Connection always; device forms and template reload when applicable."""
        options = ["connection"]
        devices = self._get_editable_devices()
        roles = {resolve_device_role_type(device) for device in devices}
        if "inverter" in roles:
            options.append("inverter")
        if self._other_option_devices():
            options.append("device")
        if "battery" in roles:
            options.append("battery")
        if "inverter" in roles or "battery" in roles:
            options.append("battery_template")
        if devices:
            options.append("reload_template")
        return options

    def _options_menu_labels(self, option_ids: list[str]) -> dict[str, str]:
        """Hardcoded menu labels so rows stay visible if translations are stale.

        ``async_show_menu`` with a list looks up
        ``options.step.init.menu_options.<id>``. New keys are blank until a
        Home Assistant restart. A dict bypasses that cache.
        """
        language = str(getattr(self.hass.config, "language", "en") or "en")
        language = language.split("-", 1)[0].lower()
        catalog = _OPTIONS_MENU_LABELS.get(language, _OPTIONS_MENU_LABELS["en"])
        fallback = _OPTIONS_MENU_LABELS["en"]
        return {
            option_id: catalog.get(option_id) or fallback.get(option_id, option_id)
            for option_id in option_ids
        }

    async def async_step_init(self, user_input: dict = None) -> FlowResult:
        """Show an options menu, or the connection form when it is the only item."""
        if (
            self.config_entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_HUB)
            == ENTRY_TYPE_COMBINED_DEVICE
        ):
            return self.async_abort(reason="combined_device")

        menu_options = self._options_menu_options()
        if len(menu_options) == 1:
            return await self.async_step_connection()
        return self.async_show_menu(
            step_id="init",
            menu_options=self._options_menu_labels(menu_options),
        )

    async def _async_device_options(
        self,
        selected_device: dict[str, Any],
        user_input: dict | None,
        step_id: str,
    ) -> FlowResult:
        """Show or save the former subentry reconfigure form for one device."""
        selected_device = _apply_entry_data_fallbacks_to_device(
            selected_device, self.config_entry.data
        )
        template_name = selected_device.get("template")
        template_data = (
            await get_template_by_name(template_name) if template_name else None
        )
        errors: dict[str, str] = {}

        if user_input is not None:
            new_prefix = str(
                user_input.get("prefix", selected_device.get("prefix", ""))
            )
            if not _is_prefix_unique_across_hubs(
                self.hass,
                new_prefix,
                exclude_entry_id=self.config_entry.entry_id,
                exclude_device_entry_id=selected_device.get("device_entry_id"),
            ):
                errors["prefix"] = "already_configured"
            else:
                try:
                    new_data = _apply_device_reconfigure(
                        self.config_entry.data,
                        selected_device.get("device_entry_id"),
                        user_input,
                        template_data,
                    )
                except ValueError:
                    return self.async_abort(reason="config_error")
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id=step_id,
            data_schema=_device_reconfigure_schema(selected_device, template_data),
            errors=errors,
            description_placeholders={
                "device": _device_display_title(selected_device),
            },
        )

    async def _async_pick_or_edit_device(
        self,
        devices: list[dict[str, Any]],
        *,
        state_attr: str,
        step_id: str,
        user_input: dict | None,
    ) -> FlowResult:
        """Pick among several devices, then show the device options form."""
        if not devices:
            return self.async_abort(reason="config_error")

        stored = getattr(self, state_attr, None)
        picking = stored is None and len(devices) > 1
        picker_submit = bool(
            user_input
            and "prefix" not in user_input
            and user_input.get("device_entry_id")
        )
        if picking and picker_submit:
            chosen = next(
                (
                    device
                    for device in devices
                    if device.get("device_entry_id")
                    == user_input.get("device_entry_id")
                ),
                None,
            )
            if not chosen:
                return self.async_abort(reason="config_error")
            setattr(self, state_attr, chosen)
            return await self._async_device_options(chosen, None, step_id)

        if picking and not picker_submit:
            choices = {
                device.get("device_entry_id"): _device_display_title(device)
                for device in devices
            }
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema(
                    {vol.Required("device_entry_id"): vol.In(choices)}
                ),
            )

        device = stored or devices[0]
        return await self._async_device_options(device, user_input, step_id)

    async def async_step_inverter(self, user_input: dict = None) -> FlowResult:
        """Edit inverter prefix, slave, model, and template dynamic_config."""
        return await self._async_pick_or_edit_device(
            self._devices_with_role("inverter"),
            state_attr="_options_inverter_device",
            step_id="inverter",
            user_input=user_input,
        )

    async def async_step_device(self, user_input: dict = None) -> FlowResult:
        """Edit heating / wallbox / energy-manager device options."""
        return await self._async_pick_or_edit_device(
            self._other_option_devices(),
            state_attr="_options_other_device",
            step_id="device",
            user_input=user_input,
        )

    async def async_step_battery(self, user_input: dict = None) -> FlowResult:
        """Edit the configured battery device (prefix, slave, model, modules)."""
        batteries = self._devices_with_role("battery")
        if batteries:
            return await self._async_pick_or_edit_device(
                batteries,
                state_attr="_options_battery_device",
                step_id="battery",
                user_input=user_input,
            )
        return await self.async_step_battery_options_selection()

    async def async_step_battery_template(self, user_input: dict = None) -> FlowResult:
        """Add, replace, or remove the battery template on this hub."""
        return await self.async_step_battery_options_selection()

    async def async_step_reload_template(self, user_input: dict = None) -> FlowResult:
        """Reload YAML register templates for this hub."""
        return await self.async_step_update_template()

    async def async_step_connection(self, user_input: dict = None) -> FlowResult:
        """Manage hub-level connection options."""
        if (
            self.config_entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_HUB)
            == ENTRY_TYPE_COMBINED_DEVICE
        ):
            return self.async_abort(reason="combined_device")

        current_host, current_port = entry_host_port(self.config_entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            new_host = str(user_input.get("host", current_host)).strip()
            try:
                new_port = int(user_input.get("port", current_port))
            except (TypeError, ValueError):
                errors["port"] = "invalid_port"
            else:
                if not new_host:
                    errors["host"] = "invalid_host"
                elif is_hub_endpoint_taken(
                    self.hass,
                    new_host,
                    new_port,
                    self.config_entry.entry_id,
                ):
                    errors["host"] = "endpoint_in_use"

            if not errors:
                new_data = dict(self.config_entry.data)
                new_data["timeout"] = user_input.get(
                    "timeout",
                    self.config_entry.data.get("timeout", DEFAULT_TIMEOUT),
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
                _apply_post_write_settle_to_entry_data(
                    new_data,
                    int(
                        user_input.get(
                            "post_write_settle_milliseconds",
                            _entry_post_write_settle_ms(self.config_entry.data),
                        )
                    ),
                )
                new_data["host"] = new_host
                new_data["port"] = new_port
                hub_config = new_data.get("hub")
                if isinstance(hub_config, dict):
                    hub_config = dict(hub_config)
                    hub_config["host"] = new_host
                    hub_config["port"] = new_port
                    hub_config["post_write_settle_milliseconds"] = new_data[
                        "post_write_settle_milliseconds"
                    ]
                    new_data["hub"] = hub_config

                endpoint_changed = (new_host, new_port) != (
                    current_host,
                    current_port,
                )
                if endpoint_changed:
                    migrate_hub_device_identifiers(
                        self.hass,
                        self.config_entry,
                        current_host,
                        current_port,
                        new_host,
                        new_port,
                    )

                entry_title = updated_hub_entry_title(
                    self.config_entry.title,
                    current_host,
                    current_port,
                    new_host,
                    new_port,
                )
                update_kwargs: dict[str, Any] = {"data": new_data}
                if entry_title is not None:
                    update_kwargs["title"] = entry_title
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    **update_kwargs,
                )

                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                if endpoint_changed:
                    await reload_dependent_combined_entries(
                        self.hass, self.config_entry.entry_id
                    )
                return self.async_create_entry(title="", data={})

        schema_fields: dict[Any, Any] = {
            vol.Required("host", default=current_host): str,
            vol.Required("port", default=current_port): int,
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
            vol.Required(
                "post_write_settle_milliseconds",
                default=_entry_post_write_settle_ms(self.config_entry.data),
            ): int,
        }

        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
        )

    async def _async_build_template_reload_plan(self) -> list[dict[str, Any]]:
        """Load current YAML for every hub device and collect version/count rows."""
        invalidate_template_cache()
        pending_update = getattr(self, "_pending_options_update", None) or {}
        devices = self._get_editable_devices()
        if not devices:
            devices = [
                _normalize_stored_device(
                    _apply_entry_data_fallbacks_to_device(
                        {
                            "type": "inverter",
                            "template": self.config_entry.data.get("template"),
                            "prefix": self.config_entry.data.get("prefix", "unknown"),
                            "slave_id": self.config_entry.data.get("slave_id", 1),
                        },
                        self.config_entry.data,
                    )
                )
            ]

        rows: list[dict[str, Any]] = []
        for device in devices:
            merged = dict(device)
            if pending_update and resolve_device_role_type(merged) == "inverter":
                merged.update(pending_update)
            template_name = merged.get("template")
            if not template_name:
                continue
            template_data = await get_template_by_name(template_name)
            if not template_data or isinstance(template_data, str):
                _LOGGER.error(
                    "Template %s could not be loaded for reload", template_name
                )
                continue

            stored_version = merged.get("template_version")
            if (
                stored_version is None
                and resolve_device_role_type(merged) == "inverter"
            ):
                stored_version = self.config_entry.data.get("template_version", 1)
            if stored_version is None:
                stored_version = 1
            current_version = template_data.get("version", 1)

            try:
                processed = self._process_dynamic_config(
                    _dynamic_input_for_device(
                        merged, template_data, self.config_entry.data
                    ),
                    copy.deepcopy(template_data),
                )
            except Exception as err:
                _LOGGER.warning(
                    "Dynamic config failed while planning template reload for %s: %s",
                    template_name,
                    err,
                )
                processed = {
                    "sensors": template_data.get("sensors", []),
                    "calculated": template_data.get("calculated", []),
                    "controls": template_data.get("controls", []),
                    "binary_sensors": template_data.get("binary_sensors", []),
                }

            rows.append(
                {
                    "device_entry_id": merged.get("device_entry_id"),
                    "role": resolve_device_role_type(merged),
                    "title": _device_display_title(merged),
                    "template_name": template_name,
                    "stored_version": stored_version,
                    "current_version": current_version,
                    "sensors": len(processed.get("sensors", [])),
                    "calculated": len(processed.get("calculated", [])),
                    "controls": len(processed.get("controls", [])),
                    "processed": processed,
                }
            )
        return rows

    async def async_step_update_template(self, user_input: dict = None) -> FlowResult:
        """Reload YAML register maps for every device on this hub."""
        try:
            plan = getattr(self, "_template_reload_plan", None)
            if user_input is None or not plan:
                plan = await self._async_build_template_reload_plan()
                self._template_reload_plan = plan

            if not plan:
                return self.async_abort(
                    reason="template_not_found",
                    description_placeholders={
                        "template_name": self.config_entry.data.get(
                            "template", "Unknown"
                        )
                    },
                )

            if user_input is not None:
                pending_update = getattr(self, "_pending_options_update", None)
                new_data = dict(self.config_entry.data)
                if pending_update:
                    new_data.update(pending_update)
                    if "battery_config" in pending_update:
                        new_data["battery_enabled"] = (
                            pending_update["battery_config"] != "none"
                        )

                devices = list(new_data.get("devices") or [])
                versions = {
                    row.get("device_entry_id"): row.get("current_version")
                    for row in plan
                    if row.get("device_entry_id")
                }
                for device in devices:
                    device_id = device.get("device_entry_id")
                    if device_id in versions:
                        device["template_version"] = versions[device_id]
                if devices:
                    new_data["devices"] = devices

                snapshot = next(
                    (row for row in plan if row.get("role") == "inverter"),
                    plan[0],
                )
                processed = snapshot.get("processed") or {}
                new_data["template_version"] = snapshot.get("current_version", 1)
                if snapshot.get("template_name"):
                    new_data["template"] = snapshot["template_name"]
                if processed.get("sensors"):
                    new_data["registers"] = processed["sensors"]
                if processed.get("calculated"):
                    new_data["calculated_entities"] = processed["calculated"]
                if processed.get("controls"):
                    new_data["controls"] = processed["controls"]
                if processed.get("binary_sensors"):
                    new_data["binary_sensors"] = processed["binary_sensors"]

                import time

                new_data["template_last_updated"] = int(time.time())
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                self._pending_options_update = None
                self._template_reload_plan = None
                _LOGGER.info(
                    "Reloaded %d hub template(s): %s",
                    len(plan),
                    ", ".join(
                        f"{row.get('template_name')} v{row.get('current_version')}"
                        for row in plan
                    ),
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

            language = str(getattr(self.hass.config, "language", "en") or "en")
            names = ", ".join(str(row.get("template_name") or "") for row in plan)
            return self.async_show_form(
                step_id="update_template",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "template_summary": _format_template_reload_summary(plan, language),
                    "template_name": names,
                    "stored_version": ", ".join(
                        str(row.get("stored_version")) for row in plan
                    ),
                    "current_version": ", ".join(
                        str(row.get("current_version")) for row in plan
                    ),
                    "version_changed": (
                        "yes"
                        if any(
                            row.get("stored_version") != row.get("current_version")
                            for row in plan
                        )
                        else "no"
                    ),
                    "content_changed": "yes",
                    "current_sensors": str(sum(row.get("sensors", 0) for row in plan)),
                    "current_calculated": str(
                        sum(row.get("calculated", 0) for row in plan)
                    ),
                    "current_controls": str(
                        sum(row.get("controls", 0) for row in plan)
                    ),
                },
            )

        except Exception as e:
            _LOGGER.error("Error updating template: %s", str(e))
            return self.async_abort(
                reason="update_error", description_placeholders={"error": str(e)}
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
                    # Filter by requires_connection_type (string or list)
                    required_conn = template_data.get("requires_connection_type")
                    if required_conn and not connection_type_allowed(
                        connection_type_norm, required_conn
                    ):
                        continue
                    display_name = (
                        template_data.get("display_name") or ""
                    ).strip() or template_name
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

        battery_devices = self._devices_with_role("battery")
        current_selection = "none"
        if battery_devices:
            current_template = str(battery_devices[0].get("template") or "").strip()
            if current_template in battery_templates:
                current_selection = current_template
            else:
                current_selection = "other"
        else:
            stored = self.config_entry.data.get("battery_config", "none")
            if stored in battery_templates:
                current_selection = stored
            elif stored in ("none", "other"):
                current_selection = stored

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
            battery_devices = self._devices_with_role("battery")
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

        # Prefer a stored slave id; otherwise LAN/RS485 → 200, WiNet-S → 2
        config_flow_note = ""
        battery_device: dict[str, Any] = {}
        if battery_template_data and isinstance(battery_template_data, dict):
            battery_devices = self._devices_with_role("battery")
            battery_device = battery_devices[0] if battery_devices else {}
            template_default_slave_id = battery_template_data.get("default_slave_id")
            template_default_prefix = battery_template_data.get("default_prefix")
            config_flow_note = battery_template_data.get("config_flow_note", "") or ""

            stored_slave_id = battery_device.get("slave_id")
            if stored_slave_id is None:
                stored_slave_id = self.config_entry.data.get("battery_slave_id")
            if stored_slave_id is not None:
                try:
                    default_slave_id = int(stored_slave_id)
                except (TypeError, ValueError):
                    default_slave_id = _default_battery_slave_id(
                        template_default_slave_id,
                        self.config_entry.data.get("connection_type", "LAN"),
                    )
            else:
                default_slave_id = _default_battery_slave_id(
                    template_default_slave_id,
                    self.config_entry.data.get("connection_type", "LAN"),
                )
            default_prefix = (
                battery_device.get("prefix")
                or self.config_entry.data.get("battery_prefix")
                or template_default_prefix
                or "SBR"
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
            current_model = battery_device.get(
                "selected_model"
            ) or self.config_entry.data.get("battery_model")
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
                "config_flow_note": config_flow_note,
            },
        )

    async def async_step_apply_config_changes(self, user_input: dict) -> FlowResult:
        """Apply configuration changes and reload integration if needed."""
        try:
            # Force battery_config to none when battery_config condition not met
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
                user_input = dict(user_input)
                if condition and not _evaluate_condition(condition, effective_data):
                    user_input["battery_config"] = "none"
                    user_input["battery_template"] = "none"
                    _LOGGER.info(
                        "Battery disabled: condition '%s' not met (connection_type=%s)",
                        condition,
                        effective_data.get("connection_type"),
                    )
                else:
                    user_input["battery_config"] = _clamp_battery_config_for_connection(
                        user_input.get(
                            "battery_config", effective_data.get("battery_config")
                        ),
                        user_input.get(
                            "connection_type", effective_data.get("connection_type")
                        ),
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
        return process_dynamic_config(user_input, template_data)
