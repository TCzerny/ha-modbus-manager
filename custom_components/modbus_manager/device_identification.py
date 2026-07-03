"""Modbus FC43 (0x2B) Read Device Identification — standalone probe (TCP/RTU)."""

from __future__ import annotations

import asyncio
import inspect
import re
from typing import Any

from homeassistant.components.modbus import ModbusHub
from homeassistant.core import HomeAssistant
from pymodbus.exceptions import ModbusException

from .const import DEFAULT_MESSAGE_WAIT_MS, DEFAULT_TIMEOUT
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

# Modbus read device identification access types (read_code).
READ_CODE_BASIC = 0x01
READ_CODE_REGULAR = 0x02
READ_CODE_EXTENDED = 0x03

READ_CODE_BY_NAME: dict[str, int] = {
    "basic": READ_CODE_BASIC,
    "regular": READ_CODE_REGULAR,
    "extended": READ_CODE_EXTENDED,
}

CONNECTION_TYPE_TCP = "tcp"
CONNECTION_TYPE_SERIAL = "serial"
CONNECTION_TYPE_RTU_OVER_TCP = "rtuovertcp"

CONNECTION_TYPES: frozenset[str] = frozenset(
    {CONNECTION_TYPE_TCP, CONNECTION_TYPE_SERIAL, CONNECTION_TYPE_RTU_OVER_TCP}
)

PARITY_BY_NAME: dict[str, str] = {
    "none": "N",
    "even": "E",
    "odd": "O",
}

DEFAULT_BAUDRATE = 9600
DEFAULT_DATA_BITS = 8
DEFAULT_STOP_BITS = 1
DEFAULT_PARITY = "none"
VALID_BAUDRATES = frozenset({9600, 19200, 38400, 57600, 115200})
VALID_DATA_BITS = frozenset({7, 8})
VALID_STOP_BITS = frozenset({1, 2})

# Standard object IDs (Modbus Application Protocol).
OBJECT_ID_LABELS: dict[int, str] = {
    0x00: "VendorName",
    0x01: "ProductCode",
    0x02: "MajorMinorRevision",
    0x03: "VendorUrl",
    0x04: "ProductName",
    0x05: "ModelName",
    0x06: "UserApplicationName",
}


class DeviceIdentificationError(Exception):
    """Raised when FC43 device identification cannot be read."""


def _sanitize_hub_token(value: str) -> str:
    """Make a string safe for ModbusHub name suffixes."""
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "probe"


def _format_serial_target(
    serial_port: str,
    baudrate: int,
    data_bits: int,
    parity_name: str,
    stop_bits: int,
) -> str:
    parity_char = PARITY_BY_NAME.get(parity_name, "N")
    return f"{serial_port} @ {baudrate} {data_bits}{parity_char}{stop_bits}"


def parse_identification_service_params(
    data: dict[str, Any],
    *,
    default_port: int,
    default_slave: int,
    default_timeout: int,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate service call data for a standalone FC43 probe."""
    connection_type = (
        str(data.get("connection_type", CONNECTION_TYPE_TCP)).strip().lower()
    )
    if connection_type not in CONNECTION_TYPES:
        return None, (
            f"Invalid connection_type '{connection_type}' "
            f"(use: {', '.join(sorted(CONNECTION_TYPES))})"
        )

    slave_id = data.get("slave_id", default_slave)
    try:
        slave_id = int(slave_id)
    except (TypeError, ValueError):
        return None, "slave_id must be an integer"
    if slave_id < 1 or slave_id > 247:
        return None, "slave_id must be between 1 and 247"

    read_code_name = str(data.get("read_code", "basic")).strip().lower()
    read_code = READ_CODE_BY_NAME.get(read_code_name)
    if read_code is None:
        return None, (
            f"Invalid read_code '{read_code_name}' "
            f"(use: {', '.join(READ_CODE_BY_NAME)})"
        )

    timeout = data.get("timeout", default_timeout)
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        return None, "timeout must be an integer"
    if timeout < 1 or timeout > 30:
        return None, "timeout must be between 1 and 30"

    params: dict[str, Any] = {
        "connection_type": connection_type,
        "slave_id": slave_id,
        "read_code": read_code,
        "read_code_name": read_code_name,
        "timeout": timeout,
    }

    if connection_type in {CONNECTION_TYPE_TCP, CONNECTION_TYPE_RTU_OVER_TCP}:
        host = str(data.get("host", "")).strip()
        if not host:
            return None, "host is required for tcp and rtuovertcp (IP or hostname)"

        port = data.get("port", default_port)
        try:
            port = int(port)
        except (TypeError, ValueError):
            return None, "port must be an integer"
        if port < 1 or port > 65535:
            return None, "port must be between 1 and 65535"

        params["host"] = host
        params["port"] = port
        if connection_type == CONNECTION_TYPE_RTU_OVER_TCP:
            params["target"] = f"{host}:{port} (RTU over TCP)"
            params["hub_name"] = f"fc43_probe_rtu_{_sanitize_hub_token(host)}_{port}"
        else:
            params["target"] = f"{host}:{port}"
            params["hub_name"] = f"fc43_probe_{_sanitize_hub_token(host)}_{port}"
        return params, None

    serial_port = str(data.get("serial_port", "")).strip()
    if not serial_port:
        return None, "serial_port is required for serial (e.g. /dev/ttyUSB0)"

    baudrate = data.get("baudrate", DEFAULT_BAUDRATE)
    try:
        baudrate = int(baudrate)
    except (TypeError, ValueError):
        return None, "baudrate must be an integer"
    if baudrate not in VALID_BAUDRATES:
        return None, f"baudrate must be one of {sorted(VALID_BAUDRATES)}"

    data_bits = data.get("data_bits", DEFAULT_DATA_BITS)
    try:
        data_bits = int(data_bits)
    except (TypeError, ValueError):
        return None, "data_bits must be an integer"
    if data_bits not in VALID_DATA_BITS:
        return None, "data_bits must be 7 or 8"

    stop_bits = data.get("stop_bits", DEFAULT_STOP_BITS)
    try:
        stop_bits = int(stop_bits)
    except (TypeError, ValueError):
        return None, "stop_bits must be an integer"
    if stop_bits not in VALID_STOP_BITS:
        return None, "stop_bits must be 1 or 2"

    parity_name = str(data.get("parity", DEFAULT_PARITY)).strip().lower()
    if parity_name not in PARITY_BY_NAME:
        return None, f"parity must be one of {', '.join(PARITY_BY_NAME)}"

    params["serial_port"] = serial_port
    params["baudrate"] = baudrate
    params["data_bits"] = data_bits
    params["stop_bits"] = stop_bits
    params["parity_name"] = parity_name
    params["target"] = _format_serial_target(
        serial_port, baudrate, data_bits, parity_name, stop_bits
    )
    params[
        "hub_name"
    ] = f"fc43_probe_serial_{_sanitize_hub_token(serial_port)}_{baudrate}"
    return params, None


def build_probe_modbus_config(
    params: dict[str, Any],
    *,
    message_wait_milliseconds: int = DEFAULT_MESSAGE_WAIT_MS,
) -> dict[str, Any]:
    """Build a short-lived ModbusHub config dict from parsed service params."""
    connection_type = params["connection_type"]
    modbus_config: dict[str, Any] = {
        "name": params["hub_name"],
        "type": connection_type,
        "delay": 0,
        "message_wait_milliseconds": message_wait_milliseconds,
        "timeout": params["timeout"],
        "slave": params["slave_id"],
    }

    if connection_type == CONNECTION_TYPE_SERIAL:
        modbus_config.update(
            {
                "port": params["serial_port"],
                "baudrate": params["baudrate"],
                "bytesize": params["data_bits"],
                "method": "rtu",
                "parity": PARITY_BY_NAME[params["parity_name"]],
                "stopbits": params["stop_bits"],
            }
        )
        return modbus_config

    modbus_config.update(
        {
            "host": params["host"],
            "port": params["port"],
        }
    )
    return modbus_config


def decode_identification_value(raw: Any) -> str:
    """Decode a device identification object value; strip NUL padding."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore").rstrip("\x00").strip()
    if isinstance(raw, str):
        return raw.replace("\x00", "").strip()
    return str(raw).strip()


async def _call_read_device_information(
    client: Any,
    *,
    slave_id: int,
    read_code: int,
    object_id: int = 0,
) -> Any:
    """Call pymodbus read_device_information with device_id/slave compatibility."""
    kwargs: dict[str, Any] = {
        "read_code": read_code,
        "object_id": object_id,
    }
    try:
        signature = inspect.signature(client.read_device_information)
        if "device_id" in signature.parameters:
            kwargs["device_id"] = slave_id
        else:
            kwargs["slave"] = slave_id
    except (TypeError, ValueError):
        kwargs["device_id"] = slave_id

    return await client.read_device_information(**kwargs)


async def async_read_device_identification(
    hub: ModbusHub,
    slave_id: int,
    read_code: int,
    *,
    object_id: int = 0,
) -> dict[int, str]:
    """Read FC43 device identification using an existing ModbusHub client and lock."""
    async with hub._lock:
        client = hub._client
        if client is None:
            raise DeviceIdentificationError("Modbus client is not connected")

        try:
            result = await _call_read_device_information(
                client,
                slave_id=slave_id,
                read_code=read_code,
                object_id=object_id,
            )
        except ModbusException as exc:
            raise DeviceIdentificationError(
                f"Modbus error (slave {slave_id}): {exc}"
            ) from exc
        except AttributeError as exc:
            raise DeviceIdentificationError(
                "Connected pymodbus client does not support read_device_information"
            ) from exc

    if result is None:
        raise DeviceIdentificationError(
            f"No response from slave {slave_id} (device may not support FC43)"
        )
    if hasattr(result, "isError") and result.isError():
        raise DeviceIdentificationError(
            f"Slave {slave_id} returned an error for read device identification"
        )

    information = getattr(result, "information", None)
    if not information:
        return {}

    decoded: dict[int, str] = {}
    for object_key, raw_value in information.items():
        try:
            oid = int(object_key)
        except (TypeError, ValueError):
            continue
        value = decode_identification_value(raw_value)
        if value:
            decoded[oid] = value
    return decoded


async def async_read_device_identification_probe(
    hass: HomeAssistant,
    params: dict[str, Any],
    *,
    message_wait_milliseconds: int = DEFAULT_MESSAGE_WAIT_MS,
) -> dict[int, str]:
    """Open a short-lived Modbus connection, read FC43, then close."""
    target = params["target"]
    slave_id = params["slave_id"]
    read_code = params["read_code"]
    timeout = params["timeout"]
    modbus_config = build_probe_modbus_config(
        params, message_wait_milliseconds=message_wait_milliseconds
    )

    hub = ModbusHub(hass, modbus_config)
    try:
        await hub.async_setup()
        await asyncio.wait_for(hub.async_pb_connect(), timeout=timeout)
    except TimeoutError as exc:
        raise DeviceIdentificationError(
            f"Connection to {target} timed out after {timeout}s"
        ) from exc
    except Exception as exc:
        raise DeviceIdentificationError(
            f"Could not connect to {target}: {exc}"
        ) from exc

    try:
        return await async_read_device_identification(hub, slave_id, read_code)
    finally:
        try:
            await hub.async_close()
        except Exception as close_err:
            _LOGGER.debug("FC43 probe close failed for %s: %s", target, close_err)


async def async_read_device_identification_tcp(
    hass: HomeAssistant,
    host: str,
    port: int,
    slave_id: int,
    read_code: int,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    message_wait_milliseconds: int = DEFAULT_MESSAGE_WAIT_MS,
) -> dict[int, str]:
    """Open a short-lived TCP connection, read FC43, then close."""
    params, error = parse_identification_service_params(
        {
            "connection_type": CONNECTION_TYPE_TCP,
            "host": host,
            "port": port,
            "slave_id": slave_id,
            "read_code": next(
                (name for name, code in READ_CODE_BY_NAME.items() if code == read_code),
                "basic",
            ),
            "timeout": timeout,
        },
        default_port=port,
        default_slave=slave_id,
        default_timeout=timeout,
    )
    if error or params is None:
        raise DeviceIdentificationError(error or "Invalid TCP probe parameters")
    params["read_code"] = read_code
    return await async_read_device_identification_probe(
        hass,
        params,
        message_wait_milliseconds=message_wait_milliseconds,
    )


def format_identification_message(
    target: str,
    slave_id: int,
    read_code_name: str,
    objects: dict[int, str],
) -> str:
    """Build human-readable text for logs and notifications."""
    lines = [
        "Modbus device identification (FC43)",
        f"Target: {target}",
        f"Slave ID: {slave_id}",
        f"Read code: {read_code_name}",
        "",
    ]
    if not objects:
        lines.append("No identification objects returned.")
        return "\n".join(lines)

    for oid in sorted(objects):
        label = OBJECT_ID_LABELS.get(oid, f"Object_{oid}")
        lines.append(f"{label} (0x{oid:02X}): {objects[oid]}")
    return "\n".join(lines)


def log_identification(
    target: str,
    slave_id: int,
    read_code_name: str,
    objects: dict[int, str],
) -> None:
    """Log identification objects at INFO level."""
    message = format_identification_message(target, slave_id, read_code_name, objects)
    for line in message.splitlines():
        _LOGGER.info("%s", line)
