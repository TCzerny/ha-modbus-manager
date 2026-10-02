"""Normalize UI generic-device rows into YAML-equivalent register dicts."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from .const import (
    CONF_GENERIC_REGISTERS,
    DEFAULT_PRECISION,
    DEFAULT_UPDATE_INTERVAL,
    GENERIC_TEMPLATE_SENTINEL,
)
from .modbus_utils import is_valid_modbus_address, reject_hex_encoding_for_control

_UNIQUE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

SENSOR_ENTITY_TYPES = frozenset({"sensor"})
BINARY_ENTITY_TYPES = frozenset({"binary_sensor"})
CONTROL_ENTITY_TYPES = frozenset({"number", "switch", "select", "text", "button"})
GENERIC_ENTITY_TYPES = SENSOR_ENTITY_TYPES | BINARY_ENTITY_TYPES | CONTROL_ENTITY_TYPES
GENERIC_ENTITY_TYPE_CHOICES = {
    "sensor": "Sensor (read-only)",
    "binary_sensor": "Binary sensor",
    "number": "Number",
    "switch": "Switch",
    "select": "Select",
    "text": "Text",
    "button": "Button",
}

ALLOWED_INPUT_TYPES = frozenset({"holding", "input"})
ALLOWED_DATA_TYPES = frozenset(
    {
        "uint16",
        "int16",
        "uint32",
        "int32",
        "float",
        "float32",
        "float64",
        "string",
    }
)
ALLOWED_BYTE_ORDERS = frozenset({"big", "little"})
WRITE_FUNCTION_CODES = frozenset({6, 16})
READ_FUNCTION_CODES = frozenset({3, 4})

_COUNT_BY_DATA_TYPE = {
    "uint32": 2,
    "int32": 2,
    "float": 2,
    "float32": 2,
    "float64": 4,
}


class GenericRegisterError(ValueError):
    """Invalid generic-device register row."""


def is_generic_device_template(template_name: object) -> bool:
    """Return True when a devices[] template is the generic sentinel."""
    return str(template_name or "").strip() == GENERIC_TEMPLATE_SENTINEL


def slug_unique_id(value: object) -> str:
    """Return a stable unique_id slug (independent of display name)."""
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def parse_value_map(text: object) -> dict[Any, str]:
    """Parse ``0: Off`` / ``0=Off`` lines (or commas) into a value map."""
    if isinstance(text, dict):
        parsed: dict[Any, str] = {}
        for key, value in text.items():
            key_text = str(key).strip()
            parsed[_map_key(key_text)] = str(value).strip()
        return parsed
    raw = str(text or "").strip()
    if not raw:
        return {}
    parsed = {}
    for part in re.split(r"[\n,;]+", raw):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            key_text, value = part.split(":", 1)
        elif "=" in part:
            key_text, value = part.split("=", 1)
        else:
            raise GenericRegisterError("options must be lines like '0: Off' or '1=On'")
        parsed[_map_key(key_text.strip())] = value.strip()
    return parsed


def _map_key(key_text: str) -> Any:
    if key_text.isdigit() or (key_text.startswith("-") and key_text[1:].isdigit()):
        return int(key_text)
    return key_text


def normalize_generic_register(row: dict[str, Any]) -> dict[str, Any]:
    """Validate one UI/stored row and return a template-style register dict.

    ``address`` is the YAML / pymodbus read address (no protocol-1 offset).
    ``register`` is accepted as an alias for the same number.
    """
    if not isinstance(row, dict):
        raise GenericRegisterError("register row must be a mapping")

    unique_id = slug_unique_id(row.get("unique_id"))
    if not unique_id or not _UNIQUE_ID_RE.match(unique_id):
        raise GenericRegisterError(
            "unique_id must start with a letter and contain only a-z, 0-9, _"
        )

    name = str(row.get("name") or "").strip()
    if not name:
        raise GenericRegisterError("name is required")

    entity_type = str(row.get("entity_type") or row.get("type") or "sensor").strip()
    if entity_type not in GENERIC_ENTITY_TYPES:
        raise GenericRegisterError(f"unsupported entity type: {entity_type}")

    input_type = str(row.get("input_type") or "holding").strip().lower()
    if input_type not in ALLOWED_INPUT_TYPES:
        raise GenericRegisterError(
            "input_type must be holding or input (coils are not in generic v1)"
        )

    data_type = str(row.get("data_type") or "uint16").strip().lower()
    if data_type not in ALLOWED_DATA_TYPES:
        raise GenericRegisterError(f"unsupported data_type: {data_type}")

    encoding = str(row.get("encoding") or "utf-8").strip() or "utf-8"
    if entity_type in CONTROL_ENTITY_TYPES:
        try:
            reject_hex_encoding_for_control(encoding)
        except ValueError as err:
            raise GenericRegisterError(str(err)) from err

    if row.get("address") not in (None, ""):
        address = int(row["address"])
    elif row.get("register") not in (None, ""):
        address = int(row["register"])
    else:
        raise GenericRegisterError("address (same as YAML address) is required")

    if not is_valid_modbus_address(address):
        raise GenericRegisterError(f"invalid Modbus address: {address}")

    byte_order = str(row.get("byte_order") or "big").strip().lower()
    if byte_order not in ALLOWED_BYTE_ORDERS:
        raise GenericRegisterError("byte_order must be big or little")

    swap_raw = row.get("swap", "none")
    if isinstance(swap_raw, bool):
        swap = "word" if swap_raw else "none"
    else:
        swap = str(swap_raw or "none").strip().lower() or "none"

    count = _optional_int(row.get("count"))
    if count is None:
        count = _COUNT_BY_DATA_TYPE.get(data_type, 1)
    if count < 1:
        raise GenericRegisterError("count must be >= 1")

    scan_interval = _optional_int(row.get("scan_interval")) or DEFAULT_UPDATE_INTERVAL
    if scan_interval < 1:
        raise GenericRegisterError("scan_interval must be >= 1")

    scale = _optional_float(row.get("scale"))
    if scale is None:
        scale = 1.0
    offset = _optional_float(row.get("offset")) or 0.0
    precision = _optional_int(row.get("precision"))
    if precision is None:
        precision = DEFAULT_PRECISION

    read_fc = _optional_int(row.get("read_function_code"))
    if read_fc is not None and read_fc not in READ_FUNCTION_CODES:
        raise GenericRegisterError("read_function_code must be 3, 4, or empty")
    write_fc = _optional_int(row.get("write_function_code"))
    if write_fc is not None and write_fc not in WRITE_FUNCTION_CODES:
        raise GenericRegisterError("write_function_code must be 6, 16, or empty")

    entity_category = row.get("entity_category") or None
    if entity_category in ("", "none"):
        entity_category = None

    normalized: dict[str, Any] = {
        "name": name,
        "unique_id": unique_id,
        "address": address,
        "entity_type": entity_type,
        "type": entity_type,
        "input_type": input_type,
        "data_type": data_type,
        "count": count,
        "scan_interval": scan_interval,
        "scale": scale,
        "offset": offset,
        "precision": precision,
        "unit_of_measurement": str(row.get("unit_of_measurement") or ""),
        "device_class": row.get("device_class") or None,
        "state_class": row.get("state_class") or None,
        "swap": swap,
        "byte_order": byte_order,
        "encoding": encoding,
        "entity_category": entity_category,
        "icon": row.get("icon") or None,
        "mm_group": row.get("mm_group") or None,
        "force_update": bool(row.get("force_update", False)),
        "never_resets": bool(row.get("never_resets", False)),
    }

    bitmask = _optional_int(row.get("bitmask"))
    if bitmask is not None:
        normalized["bitmask"] = bitmask
    bit_position = _optional_int(row.get("bit_position"))
    if bit_position is not None:
        normalized["bit_position"] = bit_position
    max_length = _optional_int(row.get("max_length"))
    if max_length is not None:
        normalized["max_length"] = max_length
    if read_fc is not None:
        normalized["read_function_code"] = read_fc
    if write_fc is not None:
        normalized["write_function_code"] = write_fc

    if entity_type == "number":
        min_value = _optional_float(row.get("min_value"))
        max_value = _optional_float(row.get("max_value"))
        step = _optional_float(row.get("step"))
        if min_value is not None:
            normalized["min_value"] = min_value
        if max_value is not None:
            normalized["max_value"] = max_value
        if step is not None:
            normalized["step"] = step

    if entity_type == "switch":
        write_on = _optional_int(row.get("write_value"))
        write_off = _optional_int(row.get("write_value_off"))
        normalized["write_value"] = 1 if write_on is None else write_on
        normalized["write_value_off"] = 0 if write_off is None else write_off
        on_value = _optional_int(row.get("on_value"))
        off_value = _optional_int(row.get("off_value"))
        normalized["on_value"] = (
            normalized["write_value"] if on_value is None else on_value
        )
        normalized["off_value"] = (
            normalized["write_value_off"] if off_value is None else off_value
        )

    if entity_type == "button":
        press = _optional_int(row.get("button_press_value"))
        normalized["button_press_value"] = 1 if press is None else press

    if entity_type == "select":
        options = parse_value_map(row.get("options_text") or row.get("options"))
        if not options:
            raise GenericRegisterError("select needs options (e.g. 0: Off)")
        normalized["options"] = options

    if entity_type == "text" and encoding.lower() == "hex":
        raise GenericRegisterError(
            "encoding 'hex' is read-only and cannot be used on a control"
        )

    return normalized


def normalize_generic_registers(rows: list[Any] | None) -> list[dict[str, Any]]:
    """Normalize a list of generic register rows; unique_id must be unique."""
    if not rows:
        raise GenericRegisterError("at least one register is required")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        normalized = normalize_generic_register(row)
        uid = normalized["unique_id"]
        if uid in seen:
            raise GenericRegisterError(f"duplicate unique_id: {uid}")
        seen.add(uid)
        out.append(normalized)
    return out


def split_generic_registers(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Split normalized rows into coordinator template buckets."""
    sensors: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    binary_sensors: list[dict[str, Any]] = []
    for row in rows:
        entity_type = row.get("entity_type") or row.get("type")
        if entity_type in SENSOR_ENTITY_TYPES:
            sensors.append(row)
        elif entity_type in BINARY_ENTITY_TYPES:
            binary_sensors.append(row)
        elif entity_type in CONTROL_ENTITY_TYPES:
            controls.append(row)
        else:
            raise GenericRegisterError(f"unsupported entity type: {entity_type}")
    return {
        "sensors": sensors,
        "controls": controls,
        "binary_sensors": binary_sensors,
        "calculated": [],
    }


def template_from_generic_device(device: dict[str, Any]) -> dict[str, Any]:
    """Build an in-memory template dict from a generic devices[] record."""
    rows = normalize_generic_registers(device.get(CONF_GENERIC_REGISTERS))
    buckets = split_generic_registers(rows)
    return {
        "name": "Generic Modbus Device",
        "display_name": "Generic Modbus Device",
        "manufacturer": "Generic",
        "type": "generic",
        "version": "0.1.0",
        **buckets,
    }


GENERIC_OPT_ACTIONS = {
    "add": "Add entity",
    "edit": "Edit entity",
    "remove": "Remove entity (registry row stays)",
    "save": "Save and reload",
}


def format_options_text(options: object) -> str:
    """Serialize a select options map for the form textarea."""
    if not isinstance(options, dict) or not options:
        return ""
    return "\n".join(f"{key}: {value}" for key, value in options.items())


def generic_row_form_defaults(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten a stored generic row into config-flow form defaults."""
    defaults = dict(row)
    defaults["entity_category"] = row.get("entity_category") or ""
    defaults["icon"] = row.get("icon") or ""
    defaults["mm_group"] = row.get("mm_group") or ""
    defaults["unit_of_measurement"] = row.get("unit_of_measurement") or ""
    defaults["device_class"] = row.get("device_class") or ""
    defaults["state_class"] = row.get("state_class") or ""
    if "options" in row and "options_text" not in row:
        defaults["options_text"] = format_options_text(row.get("options"))
    return defaults


def generic_entity_type_schema(default: str = "sensor") -> vol.Schema:
    """Entity-platform picker."""
    choice = default if default in GENERIC_ENTITY_TYPE_CHOICES else "sensor"
    return vol.Schema(
        {
            vol.Required("entity_type", default=choice): vol.In(
                GENERIC_ENTITY_TYPE_CHOICES
            )
        }
    )


def generic_entity_core_schema(
    defaults: dict[str, Any] | None = None,
    *,
    include_unique_id: bool = True,
) -> vol.Schema:
    """Identity, YAML address, and data type."""
    d = defaults or {}
    data_types = {name: name for name in sorted(ALLOWED_DATA_TYPES)}
    data_type = str(d.get("data_type") or "uint16")
    if data_type not in data_types:
        data_type = "uint16"
    input_type = str(d.get("input_type") or "holding")
    if input_type not in ALLOWED_INPUT_TYPES:
        input_type = "holding"
    category = str(d.get("entity_category") or "")
    if category not in ("", "diagnostic", "config"):
        category = ""
    fields: dict[Any, Any] = {}
    if include_unique_id:
        unique_id = str(d.get("unique_id") or "")
        if unique_id:
            fields[vol.Required("unique_id", default=unique_id)] = str
        else:
            fields[vol.Required("unique_id")] = str
    name = str(d.get("name") or "")
    if name:
        fields[vol.Required("name", default=name)] = str
    else:
        fields[vol.Required("name")] = str
    if d.get("address") not in (None, ""):
        fields[vol.Required("address", default=int(d["address"]))] = int
    else:
        fields[vol.Required("address")] = int
    fields.update(
        {
            vol.Required("input_type", default=input_type): vol.In(
                {"holding": "Holding", "input": "Input"}
            ),
            vol.Required("data_type", default=data_type): vol.In(data_types),
            vol.Optional(
                "scan_interval", default=int(d.get("scan_interval") or 10)
            ): int,
            vol.Optional("entity_category", default=category): vol.In(
                {"": "none", "diagnostic": "diagnostic", "config": "config"}
            ),
            vol.Optional("icon", default=str(d.get("icon") or "")): str,
            vol.Optional("mm_group", default=str(d.get("mm_group") or "")): str,
        }
    )
    return vol.Schema(fields)


def _opt_with_default(
    name: str,
    defaults: dict[str, Any],
    fallback: Any,
    conv: Any,
) -> tuple[Any, Any]:
    value = defaults.get(name, fallback)
    if value in (None, ""):
        value = fallback
    return vol.Optional(name, default=value), conv


def generic_entity_extras_schema(
    entity_type: str,
    data_type: str,
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Extras that apply to this platform and data type."""
    d = defaults or {}
    fields: dict[Any, Any] = {}
    numeric = data_type in {
        "uint16",
        "int16",
        "uint32",
        "int32",
        "float",
        "float32",
        "float64",
    }
    wide = data_type in {"uint32", "int32", "float", "float32", "float64"}
    if numeric:
        fields.update(
            dict(
                (
                    _opt_with_default("scale", d, 1.0, vol.Coerce(float)),
                    _opt_with_default("offset", d, 0.0, vol.Coerce(float)),
                    _opt_with_default("precision", d, 2, int),
                    _opt_with_default("unit_of_measurement", d, "", str),
                    _opt_with_default("device_class", d, "", str),
                    _opt_with_default("state_class", d, "", str),
                    _opt_with_default("force_update", d, False, bool),
                )
            )
        )
        if entity_type == "sensor":
            key, conv = _opt_with_default("never_resets", d, False, bool)
            fields[key] = conv
    if data_type in ("uint16", "int16") or entity_type == "binary_sensor":
        if d.get("bitmask") not in (None, ""):
            fields[vol.Optional("bitmask", default=int(d["bitmask"]))] = int
        else:
            fields[vol.Optional("bitmask")] = int
        if d.get("bit_position") not in (None, ""):
            fields[vol.Optional("bit_position", default=int(d["bit_position"]))] = int
        else:
            fields[vol.Optional("bit_position")] = int
    if wide:
        byte_order = str(d.get("byte_order") or "big")
        swap = str(d.get("swap") or "none")
        fields.update(
            {
                vol.Optional("byte_order", default=byte_order): vol.In(
                    {"big": "big", "little": "little"}
                ),
                vol.Optional("swap", default=swap): vol.In(
                    {"none": "none", "word": "word"}
                ),
            }
        )
        if d.get("count") not in (None, ""):
            fields[vol.Optional("count", default=int(d["count"]))] = int
        else:
            fields[vol.Optional("count")] = int
    if data_type == "string":
        fields.update(
            {
                vol.Optional(
                    "encoding", default=str(d.get("encoding") or "utf-8")
                ): str,
                vol.Optional(
                    "byte_order", default=str(d.get("byte_order") or "big")
                ): vol.In({"big": "big", "little": "little"}),
                vol.Optional("swap", default=str(d.get("swap") or "none")): vol.In(
                    {"none": "none", "word": "word"}
                ),
            }
        )
        if d.get("count") not in (None, ""):
            fields[vol.Optional("count", default=int(d["count"]))] = int
        else:
            fields[vol.Optional("count")] = int
        if d.get("max_length") not in (None, ""):
            fields[vol.Optional("max_length", default=int(d["max_length"]))] = int
        else:
            fields[vol.Optional("max_length")] = int
    if entity_type in ("sensor", "binary_sensor", "number"):
        if d.get("read_function_code") not in (None, ""):
            fields[
                vol.Optional("read_function_code", default=int(d["read_function_code"]))
            ] = int
        else:
            fields[vol.Optional("read_function_code")] = int
    if entity_type == "number":
        fields.update(
            dict(
                (
                    _opt_with_default("min_value", d, 0.0, vol.Coerce(float)),
                    _opt_with_default("max_value", d, 100.0, vol.Coerce(float)),
                    _opt_with_default("step", d, 1.0, vol.Coerce(float)),
                )
            )
        )
        if d.get("write_function_code") not in (None, ""):
            fields[
                vol.Optional(
                    "write_function_code", default=int(d["write_function_code"])
                )
            ] = int
        else:
            fields[vol.Optional("write_function_code")] = int
    if entity_type == "switch":
        fields.update(
            dict(
                (
                    _opt_with_default("write_value", d, 1, int),
                    _opt_with_default("write_value_off", d, 0, int),
                )
            )
        )
        if d.get("on_value") not in (None, ""):
            fields[vol.Optional("on_value", default=int(d["on_value"]))] = int
        else:
            fields[vol.Optional("on_value")] = int
        if d.get("off_value") not in (None, ""):
            fields[vol.Optional("off_value", default=int(d["off_value"]))] = int
        else:
            fields[vol.Optional("off_value")] = int
        if d.get("write_function_code") not in (None, ""):
            fields[
                vol.Optional(
                    "write_function_code", default=int(d["write_function_code"])
                )
            ] = int
        else:
            fields[vol.Optional("write_function_code")] = int
    if entity_type == "button":
        fields.update(dict((_opt_with_default("button_press_value", d, 1, int),)))
        if d.get("write_function_code") not in (None, ""):
            fields[
                vol.Optional(
                    "write_function_code", default=int(d["write_function_code"])
                )
            ] = int
        else:
            fields[vol.Optional("write_function_code")] = int
    if entity_type == "select":
        options_text = str(
            d.get("options_text") or format_options_text(d.get("options"))
        )
        fields[vol.Required("options_text", default=options_text)] = str
        if d.get("write_function_code") not in (None, ""):
            fields[
                vol.Optional(
                    "write_function_code", default=int(d["write_function_code"])
                )
            ] = int
        else:
            fields[vol.Optional("write_function_code")] = int
    if entity_type == "text":
        fields.update(
            {vol.Optional("encoding", default=str(d.get("encoding") or "utf-8")): str}
        )
        if d.get("max_length") not in (None, ""):
            fields[vol.Optional("max_length", default=int(d["max_length"]))] = int
        else:
            fields[vol.Optional("max_length")] = int
        if d.get("count") not in (None, ""):
            fields[vol.Optional("count", default=int(d["count"]))] = int
        else:
            fields[vol.Optional("count")] = int
        if d.get("write_function_code") not in (None, ""):
            fields[
                vol.Optional(
                    "write_function_code", default=int(d["write_function_code"])
                )
            ] = int
        else:
            fields[vol.Optional("write_function_code")] = int
    if not fields:
        fields[vol.Optional("force_update", default=False)] = bool
    return vol.Schema(fields)
