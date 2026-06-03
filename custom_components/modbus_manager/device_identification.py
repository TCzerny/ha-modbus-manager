"""Modbus FC43 (0x2B) Read Device Identification via Home Assistant ModbusHub."""

from __future__ import annotations

import inspect
from typing import Any

from homeassistant.components.modbus import ModbusHub
from pymodbus.exceptions import ModbusException

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
    """Read FC43 device identification using the hub's pymodbus client and lock."""
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


def format_identification_message(
    entry_title: str,
    slave_id: int,
    read_code_name: str,
    objects: dict[int, str],
) -> str:
    """Build human-readable text for logs and notifications."""
    lines = [
        "Modbus device identification (FC43)",
        f"Hub: {entry_title}",
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
    entry_title: str,
    slave_id: int,
    read_code_name: str,
    objects: dict[int, str],
) -> None:
    """Log identification objects at INFO level."""
    message = format_identification_message(
        entry_title, slave_id, read_code_name, objects
    )
    for line in message.splitlines():
        _LOGGER.info("%s", line)
