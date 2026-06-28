"""Modbus FC43 (0x2B) Read Device Identification — standalone TCP probe."""

from __future__ import annotations

import asyncio
import inspect
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
    hub_name = f"fc43_probe_{host}_{port}"
    modbus_config = {
        "name": hub_name,
        "type": "tcp",
        "host": host,
        "port": port,
        "delay": 0,
        "message_wait_milliseconds": message_wait_milliseconds,
        "timeout": timeout,
        "slave": slave_id,
    }

    hub = ModbusHub(hass, modbus_config)
    try:
        await hub.async_setup()
        await asyncio.wait_for(hub.async_pb_connect(), timeout=timeout)
    except TimeoutError as exc:
        raise DeviceIdentificationError(
            f"Connection to {host}:{port} timed out after {timeout}s"
        ) from exc
    except Exception as exc:
        raise DeviceIdentificationError(
            f"Could not connect to {host}:{port}: {exc}"
        ) from exc

    try:
        return await async_read_device_identification(hub, slave_id, read_code)
    finally:
        try:
            await hub.async_close()
        except Exception as close_err:
            _LOGGER.debug(
                "FC43 probe close failed for %s:%s: %s",
                host,
                port,
                close_err,
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
