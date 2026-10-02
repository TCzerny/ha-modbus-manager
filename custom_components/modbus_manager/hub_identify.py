"""Hub identify for a known host (config-flow probe, not FC43).

Step 1 reads each parent template's existing type-code entity and maps
``valid_models.type_code`` to template plus selected_model. Step 2 runs only
after an inverter or iHomeManager hit: connection path, then battery/wallbox
on child ``detect_slave_ids``. The user must confirm; existing config entries
are never rewritten here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant

from .logger import ModbusManagerLogger
from .modbus_client import TemporaryRegisterReader
from .modbus_utils import decode_string_registers

_LOGGER = ModbusManagerLogger(__name__)

ABSENT_U16 = 0xFFFF
CHILD_TYPES = frozenset({"battery", "ev_charger"})
INVERTER_TYPES = frozenset({"pv_inverter", "pv_hybrid_inverter"})
ENERGY_MANAGER_TYPES = frozenset({"energy_manager"})
INVERTER_SLAVE_SKIP = 1
# Protocol register 6100. Not an entity — can fault WiNet-S.
CONNECTION_PATH_SPEC: dict[str, Any] = {
    "address": 6099,
    "input_type": ["input", "holding"],
    "data_type": "uint16",
}


@dataclass(slots=True)
class IdentifyHit:
    """One template that matched the device on the wire."""

    template_name: str
    display_name: str
    slave_id: int
    selected_model: str | None = None
    serial: str | None = None
    connection_type: str | None = None
    battery_config: str | None = None
    battery_slave_id: int | None = None
    battery_template: str | None = None
    battery_model: str | None = None
    battery_modules: int | None = None
    battery_prefix: str | None = None
    wallbox_connected: str | None = None
    wallbox_template: str | None = None
    wallbox_slave_id: int | None = None
    wallbox_model: str | None = None
    wallbox_prefix: str | None = None
    charger_enabled: bool | None = None
    extras: dict[str, Any] = field(default_factory=dict)


def parse_type_code(raw: Any) -> int | None:
    """Parse a YAML type_code (int, decimal string, or 0xHEX) to int."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        if text.lower().startswith("0x"):
            return int(text, 16)
        return int(text, 10)
    except ValueError:
        return None


def type_code_models(template_data: dict[str, Any]) -> dict[int, str]:
    """Map numeric type_code → model name from valid_models."""
    dynamic = template_data.get("dynamic_config") or {}
    valid_models = dynamic.get("valid_models") or template_data.get("valid_models")
    if not isinstance(valid_models, dict):
        return {}
    mapping: dict[int, str] = {}
    for model_name, config in valid_models.items():
        if not isinstance(config, dict):
            continue
        code = parse_type_code(config.get("type_code"))
        if code is not None:
            mapping[code] = str(model_name)
    return mapping


def _template_type(template_data: dict[str, Any]) -> str:
    return str(template_data.get("type") or "").strip().lower()


def _manufacturer(template_data: dict[str, Any]) -> str:
    return str(template_data.get("manufacturer") or "").strip().lower()


def _display_name(template_name: str, template_data: dict[str, Any]) -> str:
    return str(template_data.get("display_name") or "").strip() or template_name


def _default_slave_id(template_data: dict[str, Any]) -> int:
    try:
        return int(template_data.get("default_slave_id") or 1)
    except (TypeError, ValueError):
        return 1


def _detect_slave_ids(template_data: dict[str, Any]) -> list[int]:
    raw = template_data.get("detect_slave_ids")
    slaves: list[int] = []
    if isinstance(raw, list):
        for item in raw:
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            if value not in slaves:
                slaves.append(value)
    if not slaves:
        slaves.append(_default_slave_id(template_data))
    return slaves


def _is_type_code_unique_id(unique_id: str) -> bool:
    uid = str(unique_id or "").strip()
    return uid == "device_type_code" or uid.endswith("_device_type_code")


def _iter_entities(template_data: dict[str, Any]):
    for key in ("sensors", "binary_sensors", "controls"):
        rows = template_data.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                yield row


def _entity_by_unique_id(
    template_data: dict[str, Any], unique_id: str
) -> dict[str, Any] | None:
    wanted = str(unique_id or "").strip()
    if not wanted:
        return None
    for row in _iter_entities(template_data):
        if str(row.get("unique_id") or "").strip() == wanted:
            return row
    return None


def _type_code_entity(template_data: dict[str, Any]) -> dict[str, Any] | None:
    for row in _iter_entities(template_data):
        if _is_type_code_unique_id(str(row.get("unique_id") or "")):
            return row
    return None


def _register_count(spec: dict[str, Any]) -> int:
    data_type = str(spec.get("data_type") or "uint16").strip().lower()
    if data_type == "string":
        return max(1, int(spec.get("count") or 1))
    if data_type in {"uint32", "int32", "float32", "float"}:
        return 2
    return max(1, int(spec.get("count") or 1))


def _input_types(spec: dict[str, Any]) -> list[str]:
    raw = spec.get("input_type") or "input"
    if isinstance(raw, (list, tuple)):
        values = [str(item).strip().lower() for item in raw if str(item).strip()]
        return values or ["input"]
    return [str(raw).strip().lower() or "input"]


def _decode_registers(spec: dict[str, Any], registers: list[int]) -> Any:
    data_type = str(spec.get("data_type") or "uint16").strip().lower()
    if data_type == "string":
        return decode_string_registers(
            registers,
            encoding=str(spec.get("encoding") or "utf-8"),
            byte_order=str(spec.get("byte_order") or "big"),
            swap=spec.get("swap") or "none",
        )
    if not registers:
        return None
    if data_type in {"uint32", "int32"}:
        if len(registers) < 2:
            return None
        high, low = int(registers[0]) & 0xFFFF, int(registers[1]) & 0xFFFF
        if str(spec.get("swap") or "").strip().lower() == "word":
            high, low = low, high
        value = (high << 16) | low
        if data_type == "int32" and value >= 0x80000000:
            value -= 0x100000000
        return value
    return int(registers[0]) & 0xFFFF


def _read_key(slave_id: int, spec: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(slave_id),
        int(spec.get("address") or 0),
        tuple(_input_types(spec)),
        _register_count(spec),
        str(spec.get("data_type") or "uint16").strip().lower(),
        str(spec.get("swap") or ""),
        str(spec.get("encoding") or ""),
    )


class _ReadCache:
    """Dedupe identical temporary-unit reads within one identify run."""

    def __init__(self, reader: TemporaryRegisterReader) -> None:
        self._reader = reader
        self._values: dict[tuple[Any, ...], Any] = {}

    async def read(self, slave_id: int, spec: dict[str, Any]) -> Any | None:
        address = spec.get("address")
        if address is None:
            return None
        key = _read_key(slave_id, spec)
        if key in self._values:
            return self._values[key]
        value = await _read_spec(self._reader, slave_id, spec)
        self._values[key] = value
        return value


async def _read_spec(
    reader: TemporaryRegisterReader,
    slave_id: int,
    spec: dict[str, Any],
) -> Any | None:
    """Read one register spec. None means no usable value."""
    address = spec.get("address")
    if address is None:
        return None
    count = _register_count(spec)
    last_error: Exception | None = None
    for input_type in _input_types(spec):
        try:
            registers = await reader.async_read(
                slave_id, int(address), count, input_type
            )
        except Exception as err:
            last_error = err
            _LOGGER.debug(
                "Identify read failed slave=%s addr=%s type=%s: %s",
                slave_id,
                address,
                input_type,
                err,
            )
            continue
        if not registers:
            continue
        decoded = _decode_registers(spec, registers)
        if decoded is None:
            continue
        if isinstance(decoded, int) and decoded == ABSENT_U16:
            continue
        if isinstance(decoded, str) and not decoded:
            continue
        return decoded
    if last_error is not None:
        _LOGGER.debug(
            "Identify spec at %s slave %s had no usable value", address, slave_id
        )
    return None


def _sbr_family_model(kwh: float, models: dict[str, Any]) -> tuple[str, int] | None:
    """Map measured pack kWh to an SBR/SBH valid_models name."""
    best_name: str | None = None
    best_modules = 0
    best_error: float | None = None
    for name, config in models.items():
        if not isinstance(config, dict):
            continue
        try:
            modules = int(config.get("modules") or 0)
        except (TypeError, ValueError):
            continue
        if modules < 1:
            continue
        per_module = 3.52 if str(name).upper().startswith("SBH") else 3.2
        error = abs(kwh - (modules * per_module))
        if best_error is None or error < best_error:
            best_error = error
            best_name = str(name)
            best_modules = modules
    if best_name is None or best_error is None or best_error > 1.0:
        return None
    return best_name, best_modules


def _parent_catalog(
    templates: dict[str, dict[str, Any]],
) -> list[tuple[str, dict[str, Any], dict[str, Any], dict[int, str]]]:
    """Parent templates that expose a type-code entity (not battery/wallbox)."""
    catalog: list[tuple[str, dict[str, Any], dict[str, Any], dict[int, str]]] = []
    for name, data in templates.items():
        if _template_type(data) in CHILD_TYPES:
            continue
        entity = _type_code_entity(data)
        if entity is None or entity.get("address") is None:
            continue
        catalog.append((name, data, entity, type_code_models(data)))
    catalog.sort(
        key=lambda item: (
            0 if item[3] else 1,
            _default_slave_id(item[1]),
            int(item[2].get("address") or 0),
            item[0],
        )
    )
    return catalog


def _match_type_code(
    value: Any,
    models: dict[int, str],
) -> str | bool | None:
    """Return selected_model, True for a unique-slave match, or None."""
    if not isinstance(value, int):
        return None
    if models:
        return models.get(value)
    if 1 <= value <= 65534:
        return True
    return None


async def _step1_match(
    cache: _ReadCache,
    templates: dict[str, dict[str, Any]],
) -> IdentifyHit | None:
    """Read type-code entities; first matching parent template wins."""
    for name, data, entity, models in _parent_catalog(templates):
        slave_id = _default_slave_id(data)
        try:
            value = await cache.read(slave_id, entity)
        except Exception as err:
            _LOGGER.debug("Identify skipped template %s: %s", name, err)
            continue
        matched = _match_type_code(value, models)
        if matched is None:
            continue
        selected_model = matched if isinstance(matched, str) else None
        hit = IdentifyHit(
            template_name=name,
            display_name=_display_name(name, data),
            slave_id=slave_id,
            selected_model=selected_model,
        )
        if isinstance(value, int):
            hit.extras["type_code"] = value
        await _fill_serial(cache, data, hit)
        return hit
    return None


async def _fill_serial(
    cache: _ReadCache,
    template_data: dict[str, Any],
    hit: IdentifyHit,
) -> None:
    entity = _entity_by_unique_id(template_data, "inverter_serial")
    if entity is None:
        return
    decoded = await cache.read(hit.slave_id, entity)
    if decoded:
        hit.serial = str(decoded)


async def _probe_connection_path(
    reader: TemporaryRegisterReader, slave_id: int
) -> tuple[str | None, int | None]:
    """Distinguish LAN (6100 present) from WINET (answered but absent).

    Transport failures leave the type unset so the template default applies.
    """
    saw_response = False
    for input_type in _input_types(CONNECTION_PATH_SPEC):
        try:
            registers = await reader.async_read(
                slave_id,
                int(CONNECTION_PATH_SPEC["address"]),
                1,
                input_type,
            )
        except Exception as err:
            _LOGGER.debug(
                "Identify connection-path read failed slave=%s type=%s: %s",
                slave_id,
                input_type,
                err,
            )
            continue
        # TemporaryRegisterReader returns None on transport/exception failure.
        if registers is None:
            continue
        saw_response = True
        if not registers:
            continue
        value = int(registers[0]) & 0xFFFF
        if value != ABSENT_U16:
            return "LAN", value
    if saw_response:
        return "WINET", None
    return None, None


async def _fill_connection_path(
    reader: TemporaryRegisterReader,
    template_data: dict[str, Any],
    hit: IdentifyHit,
) -> None:
    if _manufacturer(template_data) != "sungrow":
        return
    if _template_type(template_data) not in INVERTER_TYPES:
        return
    connection_type, value = await _probe_connection_path(reader, hit.slave_id)
    if connection_type is None:
        return
    hit.connection_type = connection_type
    if value is not None:
        hit.extras["connection_path_value"] = value


async def _fill_battery_model(
    cache: _ReadCache,
    parent_data: dict[str, Any],
    hit: IdentifyHit,
    battery_data: dict[str, Any],
) -> None:
    valid_models = (battery_data.get("dynamic_config") or {}).get("valid_models") or {}
    if not isinstance(valid_models, dict) or not valid_models:
        return
    capacity = _entity_by_unique_id(parent_data, "battery_capacity")
    if capacity is None:
        return
    raw = await cache.read(hit.slave_id, capacity)
    if not isinstance(raw, int):
        return
    try:
        scale = float(capacity.get("scale") or 1)
    except (TypeError, ValueError):
        scale = 1.0
    kwh = raw * scale
    mapped = _sbr_family_model(kwh, valid_models)
    if mapped is None:
        return
    hit.battery_model, hit.battery_modules = mapped
    hit.extras["battery_capacity_kwh"] = kwh


def _battery_config_default(battery_data: dict[str, Any]) -> str:
    dynamic = battery_data.get("dynamic_config") or {}
    section = dynamic.get("battery_config") if isinstance(dynamic, dict) else None
    if isinstance(section, dict) and section.get("default") is not None:
        return str(section.get("default"))
    return "sbr_battery"


async def _fill_battery(
    cache: _ReadCache,
    hit: IdentifyHit,
    parent_data: dict[str, Any],
    templates: dict[str, dict[str, Any]],
) -> None:
    parent_mfr = _manufacturer(parent_data)
    if not parent_mfr:
        return
    for name, data in sorted(templates.items(), key=lambda item: item[0]):
        if _template_type(data) != "battery":
            continue
        if _manufacturer(data) != parent_mfr:
            continue
        serial_entity = _entity_by_unique_id(data, "battery_1_serial_number")
        if serial_entity is None:
            continue
        for slave_id in _detect_slave_ids(data):
            if slave_id == INVERTER_SLAVE_SKIP or slave_id == hit.slave_id:
                continue
            decoded = await cache.read(slave_id, serial_entity)
            if not decoded:
                continue
            hit.battery_slave_id = slave_id
            hit.battery_template = name
            hit.battery_config = _battery_config_default(data)
            hit.battery_prefix = str(data.get("default_prefix") or "SBR")
            hit.extras["battery_serial"] = str(decoded)
            await _fill_battery_model(cache, parent_data, hit, data)
            return


async def _fill_wallbox(
    cache: _ReadCache,
    hit: IdentifyHit,
    parent_data: dict[str, Any],
    templates: dict[str, dict[str, Any]],
) -> None:
    parent_mfr = _manufacturer(parent_data)
    if not parent_mfr:
        return
    skip_ids = {INVERTER_SLAVE_SKIP, int(hit.slave_id)}
    if hit.battery_slave_id is not None:
        skip_ids.add(int(hit.battery_slave_id))
    for name, data in sorted(templates.items(), key=lambda item: item[0]):
        if _template_type(data) != "ev_charger":
            continue
        if _manufacturer(data) != parent_mfr:
            continue
        entity = _type_code_entity(data)
        models = type_code_models(data)
        if entity is None or not models:
            continue
        for slave_id in _detect_slave_ids(data):
            if slave_id in skip_ids:
                continue
            value = await cache.read(slave_id, entity)
            if not isinstance(value, int) or value not in models:
                continue
            hit.wallbox_connected = "yes"
            hit.wallbox_template = name
            hit.wallbox_slave_id = slave_id
            hit.wallbox_model = models[value]
            hit.wallbox_prefix = str(data.get("default_prefix") or "WB")
            hit.extras["wallbox_type_code"] = value
            return


async def _fill_ihm_extras(
    cache: _ReadCache,
    template_data: dict[str, Any],
    hit: IdentifyHit,
) -> None:
    """Battery and charger on unit 247 only — no RS485 sibling sweep."""
    capacity = _entity_by_unique_id(template_data, "total_battery_rated_capacity")
    if capacity is not None:
        raw = await cache.read(hit.slave_id, capacity)
        if isinstance(raw, int) and raw > 0:
            hit.battery_config = "battery"
            hit.extras["ihm_battery_capacity"] = raw
    if hit.battery_config is None:
        level = _entity_by_unique_id(template_data, "battery_level")
        if level is not None:
            raw = await cache.read(hit.slave_id, level)
            if isinstance(raw, int) and raw != ABSENT_U16:
                hit.battery_config = "battery"
                hit.extras["ihm_battery_level"] = raw
    charger = _entity_by_unique_id(template_data, "charger_status_raw")
    if charger is None:
        return
    status = await cache.read(hit.slave_id, charger)
    if isinstance(status, int) and status not in {0, ABSENT_U16}:
        hit.charger_enabled = True
        hit.extras["ihm_charger_status"] = status


async def _step2_fill(
    cache: _ReadCache,
    reader: TemporaryRegisterReader,
    hit: IdentifyHit,
    templates: dict[str, dict[str, Any]],
) -> None:
    parent = templates.get(hit.template_name) or {}
    template_type = _template_type(parent)
    if template_type in ENERGY_MANAGER_TYPES:
        await _fill_ihm_extras(cache, parent, hit)
        return
    if template_type not in INVERTER_TYPES:
        return
    await _fill_connection_path(reader, parent, hit)
    await _fill_battery(cache, hit, parent, templates)
    await _fill_wallbox(cache, hit, parent, templates)


async def async_identify_hub(
    hass: HomeAssistant,
    connection: dict[str, Any],
    templates: dict[str, dict[str, Any]],
) -> IdentifyHit | None:
    """Probe parent type-code entities, then bus extras. First match wins."""
    catalog = _parent_catalog(templates)
    if not catalog:
        return None
    async with TemporaryRegisterReader(hass, connection) as reader:
        cache = _ReadCache(reader)
        hit = await _step1_match(cache, templates)
        if hit is None:
            return None
        await _step2_fill(cache, reader, hit, templates)
        if hit.wallbox_slave_id is not None:
            ev_charger = f"{hit.wallbox_model}/{hit.wallbox_slave_id}"
        elif hit.charger_enabled:
            ev_charger = "ihm"
        else:
            ev_charger = "none"
        _LOGGER.info(
            "Identified %s (%s) slave=%s model=%s connection=%s battery=%s/%s ev_charger=%s",
            hit.display_name,
            hit.template_name,
            hit.slave_id,
            hit.selected_model,
            hit.connection_type,
            hit.battery_model or hit.battery_config,
            hit.battery_slave_id,
            ev_charger,
        )
        return hit
