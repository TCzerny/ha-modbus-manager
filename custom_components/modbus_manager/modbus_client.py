"""Backend-neutral Modbus I/O: Core units on HA 2026.9+, ModbusHub fallback.

The hub fallback is scheduled for removal after
``MODBUS_HUB_FALLBACK_UNTIL_HA`` (end of 2026). Callers must not change
``unique_id`` / ``entity_id`` when switching backends.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_DELAY,
    DEFAULT_MESSAGE_WAIT_MS,
    DEFAULT_SLAVE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MODBUS_HUB_FALLBACK_UNTIL_HA,
)
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

try:
    from homeassistant.components.modbus.const import (
        CALL_TYPE_COIL,
        CALL_TYPE_DISCRETE,
        CALL_TYPE_REGISTER_HOLDING,
        CALL_TYPE_REGISTER_INPUT,
        CALL_TYPE_WRITE_COIL,
        CALL_TYPE_WRITE_COILS,
        CALL_TYPE_WRITE_REGISTERS,
    )
except ImportError:  # pragma: no cover - very old cores
    CALL_TYPE_REGISTER_HOLDING = "holding"
    CALL_TYPE_REGISTER_INPUT = "input"
    CALL_TYPE_WRITE_REGISTERS = "write_registers"
    CALL_TYPE_COIL = "coil"
    CALL_TYPE_DISCRETE = "discrete"
    CALL_TYPE_WRITE_COIL = "write_coil"
    CALL_TYPE_WRITE_COILS = "write_coils"

try:
    from homeassistant.components.modbus.const import CALL_TYPE_WRITE_REGISTER
except ImportError:
    CALL_TYPE_WRITE_REGISTER = CALL_TYPE_WRITE_REGISTERS


def core_units_available() -> bool:
    """Return True when HA Core exposes ``async_get_unit`` (2026.9+)."""
    try:
        from homeassistant.components.modbus import (
            async_get_temporary_unit,
            async_get_unit,
        )
        from modbus_connection import ModbusTcpParams  # noqa: F401
    except ImportError:
        return False
    return callable(async_get_unit) and callable(async_get_temporary_unit)


def slave_ids_for_entry(entry: ConfigEntry) -> list[int]:
    """Unique Modbus unit ids referenced by a hub config entry."""
    ids: set[int] = set()
    data = entry.data

    def _add(raw: Any) -> None:
        if raw is None or raw == "":
            return
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            return

    _add(data.get("slave_id", DEFAULT_SLAVE))
    _add(data.get("battery_slave_id"))
    devices = data.get("devices")
    if isinstance(devices, list):
        for device in devices:
            if isinstance(device, dict):
                _add(device.get("slave_id"))
    return sorted(ids) or [DEFAULT_SLAVE]


def _framer_for_modbus_type(modbus_type: str) -> str:
    normalized = str(modbus_type or "tcp").strip().lower()
    if normalized == "rtuovertcp":
        return "rtu"
    return "socket"


def connection_params_from_entry(entry: ConfigEntry) -> Any:
    """Build ``modbus_connection`` params from a hub config entry."""
    from modbus_connection import ModbusSerialParams, ModbusTcpParams

    data = entry.data
    hub = data.get("hub") if isinstance(data.get("hub"), dict) else {}
    modbus_type = (
        str(data.get("modbus_type") or data.get("type") or hub.get("type") or "tcp")
        .strip()
        .lower()
    )
    if modbus_type == "serial":
        device = (
            data.get("serial_port")
            or hub.get("port")
            or data.get("port")
            or "/dev/ttyUSB0"
        )
        parity_raw = str(data.get("parity") or hub.get("parity") or "N")[:1].upper()
        if parity_raw not in ("N", "E", "O"):
            parity_raw = "N"
        stopbits = int(data.get("stop_bits") or hub.get("stopbits") or 1)
        bytesize = int(data.get("data_bits") or hub.get("bytesize") or 8)
        return ModbusSerialParams(
            device=str(device),
            baudrate=int(data.get("baudrate") or hub.get("baudrate") or 9600),
            bytesize=8 if bytesize not in (7, 8) else bytesize,  # type: ignore[arg-type]
            parity=parity_raw,  # type: ignore[arg-type]
            stopbits=1 if stopbits not in (1, 2) else stopbits,  # type: ignore[arg-type]
        )
    host = data.get("host") or hub.get("host") or ""
    port = int(data.get("port") or hub.get("port") or 502)
    return ModbusTcpParams(
        host=str(host),
        port=port,
        framer=_framer_for_modbus_type(modbus_type),  # type: ignore[arg-type]
    )


def connection_params_from_probe(params: dict[str, Any]) -> Any:
    """Build ``modbus_connection`` params from an FC43 service payload."""
    from modbus_connection import ModbusSerialParams, ModbusTcpParams

    connection_type = str(params.get("connection_type", "tcp")).strip().lower()
    if connection_type == "serial":
        parity_raw = str(params.get("parity_name") or "none")[:1].upper()
        if parity_raw not in ("N", "E", "O"):
            parity_raw = "N"
        return ModbusSerialParams(
            device=str(params["serial_port"]),
            baudrate=int(params.get("baudrate") or 9600),
            bytesize=int(params.get("data_bits") or 8),  # type: ignore[arg-type]
            parity=parity_raw,  # type: ignore[arg-type]
            stopbits=int(params.get("stop_bits") or 1),  # type: ignore[arg-type]
        )
    framer = "rtu" if connection_type == "rtuovertcp" else "socket"
    return ModbusTcpParams(
        host=str(params["host"]),
        port=int(params.get("port") or 502),
        framer=framer,  # type: ignore[arg-type]
    )


class ModbusTransport:
    """Duck-types the ModbusHub calls the coordinator already uses.

    ``uses_core_units`` is True on HA 2026.9+. Asking for a unit does no I/O;
    the first read opens the link. Do not reload the config entry on a drop.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry | None,
        *,
        hub: Any | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self._hub = hub
        self._units: dict[int, Any] = {}
        self._params: Any | None = None
        self.uses_core_units = hub is None
        if self.uses_core_units and entry is not None:
            self._params = connection_params_from_entry(entry)

    def _pacing_from_entry(self) -> tuple[float, float | None, float | None]:
        data = self.entry.data if self.entry is not None else {}
        hub = data.get("hub") if isinstance(data.get("hub"), dict) else {}
        wait_ms = data.get(
            "message_wait_milliseconds",
            hub.get("message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS),
        )
        timeout = data.get("timeout", hub.get("timeout", DEFAULT_TIMEOUT))
        delay = data.get("delay", hub.get("delay", DEFAULT_DELAY))
        try:
            spacing = max(0.0, float(wait_ms) / 1000.0)
        except (TypeError, ValueError):
            spacing = DEFAULT_MESSAGE_WAIT_MS / 1000.0
        try:
            timeout_s = float(timeout) if timeout is not None else None
        except (TypeError, ValueError):
            timeout_s = float(DEFAULT_TIMEOUT)
        try:
            delay_s = float(delay) if delay else None
        except (TypeError, ValueError):
            delay_s = None
        return spacing, timeout_s, delay_s

    def _apply_unit_pacing(self, unit: Any) -> None:
        spacing, timeout_s, delay_s = self._pacing_from_entry()
        if hasattr(unit, "set_message_spacing"):
            unit.set_message_spacing(spacing)
        if timeout_s is not None and hasattr(unit, "require_timeout"):
            unit.require_timeout(timeout_s)
        if delay_s and hasattr(unit, "require_connect_delay"):
            unit.require_connect_delay(delay_s)

    def _unit_for(self, slave_id: int) -> Any:
        if not self.uses_core_units:
            raise RuntimeError("unit lookup on hub backend")
        if slave_id not in self._units:
            from homeassistant.components.modbus import async_get_unit

            if self.entry is None or self._params is None:
                raise RuntimeError("Core unit transport needs a config entry")
            unit = async_get_unit(self.hass, self.entry, self._params, slave_id)
            self._apply_unit_pacing(unit)
            self._units[slave_id] = unit
        return self._units[slave_id]

    def is_connected(self) -> bool:
        """Hub: live socket. Units: always ready (lazy connect on first I/O)."""
        if self.uses_core_units:
            return True
        from .device_utils import hub_is_connected

        return hub_is_connected(self._hub)

    async def async_ensure_connected(self, timeout: float) -> bool:
        """Wait for the hub connect task, or no-op on the unit backend."""
        if self.uses_core_units:
            return True
        from .device_utils import async_ensure_hub_connected

        return await async_ensure_hub_connected(self._hub, timeout)

    async def async_close(self) -> None:
        """Close the fallback hub. Core units are released on entry unload."""
        if self.uses_core_units:
            return
        if self._hub is not None:
            await self._hub.async_close()

    async def async_pb_call(
        self,
        slave_id: int,
        address: int,
        value: Any,
        call_type: str,
    ) -> Any:
        """Read or write, matching Home Assistant ``ModbusHub.async_pb_call``."""
        if not self.uses_core_units:
            return await self._hub.async_pb_call(slave_id, address, value, call_type)
        unit = self._unit_for(int(slave_id))
        try:
            if call_type == CALL_TYPE_REGISTER_INPUT:
                registers = await unit.read_input_registers(int(address), int(value))
                return SimpleNamespace(registers=list(registers))
            if call_type == CALL_TYPE_REGISTER_HOLDING:
                registers = await unit.read_holding_registers(int(address), int(value))
                return SimpleNamespace(registers=list(registers))
            if call_type == CALL_TYPE_COIL:
                bits = await unit.read_coils(int(address), int(value))
                return SimpleNamespace(bits=list(bits), registers=[])
            if call_type == CALL_TYPE_DISCRETE:
                bits = await unit.read_discrete_inputs(int(address), int(value))
                return SimpleNamespace(bits=list(bits), registers=[])
            if call_type == CALL_TYPE_WRITE_REGISTERS:
                values = value if isinstance(value, list) else [value]
                await unit.write_registers(int(address), [int(v) for v in values])
                return True
            if call_type == CALL_TYPE_WRITE_REGISTER:
                if isinstance(value, list):
                    await unit.write_registers(int(address), [int(v) for v in value])
                else:
                    await unit.write_register(int(address), int(value))
                return True
            if call_type == CALL_TYPE_WRITE_COILS:
                bits = value if isinstance(value, list) else [value]
                await unit.write_coils(int(address), [bool(v) for v in bits])
                return True
            if call_type == CALL_TYPE_WRITE_COIL:
                if isinstance(value, list):
                    await unit.write_coils(int(address), [bool(v) for v in value])
                else:
                    await unit.write_coil(int(address), bool(value))
                return True
        except Exception as err:
            _LOGGER.debug(
                "Core unit I/O failed slave=%s addr=%s type=%s: %s",
                slave_id,
                address,
                call_type,
                err,
            )
            return None
        _LOGGER.debug("Unsupported call_type on core unit backend: %s", call_type)
        return None

    async def async_pymodbus_call(
        self,
        slave_id: int,
        address: int,
        count: int,
        call_type: str,
    ) -> list[int] | None:
        """SunSpec helper: return raw register words."""
        if not self.uses_core_units:
            result = await self._hub.async_pymodbus_call(
                slave_id, address, count, call_type
            )
            if result is None:
                return None
            if isinstance(result, list):
                return result
            registers = getattr(result, "registers", None)
            return list(registers) if registers is not None else None
        result = await self.async_pb_call(slave_id, address, count, call_type)
        if result is None:
            return None
        registers = getattr(result, "registers", None)
        return list(registers) if registers is not None else None


async def async_create_modbus_transport(
    hass: HomeAssistant, entry: ConfigEntry
) -> ModbusTransport:
    """Create the I/O backend for a hub config entry."""
    if core_units_available():
        transport = ModbusTransport(hass, entry)
        for slave_id in slave_ids_for_entry(entry):
            transport._unit_for(slave_id)
        _LOGGER.info(
            "Using Core async_get_unit for %s (hub fallback until HA %s)",
            entry.title or entry.entry_id,
            MODBUS_HUB_FALLBACK_UNTIL_HA,
        )
        return transport

    from homeassistant.components.modbus import ModbusHub

    from .device_utils import async_wait_for_hub_connected, hub_is_connected

    host = entry.data.get("host")
    port = entry.data.get("port", 502)
    hub_name = f"modbus_manager_{host}_{port}"
    global_hub_key = f"global_hub_{host}_{port}"
    connect_timeout = entry.data.get("timeout", 5)
    domain_data = hass.data.setdefault(DOMAIN, {})

    existing_hub = domain_data.get(global_hub_key)
    inner = getattr(existing_hub, "_hub", None) if existing_hub is not None else None
    if inner is not None:
        existing_hub = inner
    if existing_hub is not None and getattr(existing_hub, "uses_core_units", False):
        existing_hub = None
    if existing_hub is not None and hub_is_connected(existing_hub):
        _LOGGER.info("Reusing existing ModbusHub for coordinator: %s", hub_name)
        return ModbusTransport(hass, entry, hub=existing_hub)

    if existing_hub is not None:
        try:
            await existing_hub.async_close()
        except Exception as err:
            _LOGGER.warning("Error closing stale Modbus hub before recreate: %s", err)

    modbus_type = entry.data.get("modbus_type") or entry.data.get("type", "tcp")
    modbus_config = {
        "name": hub_name,
        "type": modbus_type,
        "host": host,
        "port": port,
        "delay": entry.data.get("delay", 0),
        "message_wait_milliseconds": entry.data.get(
            "message_wait_milliseconds",
            entry.data.get("request_delay", DEFAULT_MESSAGE_WAIT_MS),
        ),
        "timeout": connect_timeout,
        "slave": entry.data.get("slave_id", DEFAULT_SLAVE),
    }
    hub = ModbusHub(hass, modbus_config)
    try:
        await hub.async_setup()
    except Exception as err:
        _LOGGER.error("Failed to setup ModbusHub for coordinator: %s", err)
        raise
    if await async_wait_for_hub_connected(hub, connect_timeout):
        _LOGGER.info("ModbusHub connected successfully for coordinator")
    else:
        _LOGGER.warning(
            "ModbusHub connect timed out after %ss (continuing offline)",
            connect_timeout,
        )
    domain_data[hub_name] = hub
    domain_data[global_hub_key] = hub
    _LOGGER.info(
        "Using ModbusHub fallback (remove after HA %s)",
        MODBUS_HUB_FALLBACK_UNTIL_HA,
    )
    return ModbusTransport(hass, entry, hub=hub)


async def async_read_device_identification_via_unit(
    hass: HomeAssistant, params: dict[str, Any]
) -> dict[int, str]:
    """FC43 via ``async_get_temporary_unit`` (no second pymodbus socket)."""
    from homeassistant.components.modbus import async_get_temporary_unit

    from .device_identification import (
        DeviceIdentificationError,
        decode_identification_value,
    )

    slave_id = int(params["slave_id"])
    target = params.get("target", "device")
    link_params = connection_params_from_probe(params)
    read_code = params.get("read_code")
    if read_code not in (None, 1):
        _LOGGER.debug(
            "Core unit FC43 returns basic identification; ignoring read_code=%s",
            read_code,
        )
    try:
        async with async_get_temporary_unit(hass, link_params, slave_id) as unit:
            timeout = params.get("timeout")
            if timeout is not None and hasattr(unit, "require_timeout"):
                unit.require_timeout(float(timeout))
            wait_ms = params.get("message_wait_milliseconds")
            if wait_ms and hasattr(unit, "set_message_spacing"):
                unit.set_message_spacing(float(wait_ms) / 1000.0)
            raw = await unit.read_device_identification()
    except DeviceIdentificationError:
        raise
    except Exception as err:
        raise DeviceIdentificationError(
            f"Could not read device identification from {target}: {err}"
        ) from err
    decoded: dict[int, str] = {}
    if not raw:
        return decoded
    for object_key, raw_value in raw.items():
        try:
            oid = int(object_key)
        except (TypeError, ValueError):
            continue
        value = decode_identification_value(raw_value)
        if value:
            decoded[oid] = value
    return decoded


def _probe_connection_type(params: dict[str, Any]) -> str:
    """Map config-flow modbus_type to FC43/temporary-unit connection_type."""
    raw = (
        str(params.get("connection_type") or params.get("modbus_type") or "tcp")
        .strip()
        .lower()
    )
    if raw in ("serial", "rtu"):
        return "serial"
    if raw in ("rtuovertcp", "rtu_over_tcp"):
        return "rtuovertcp"
    return "tcp"


class TemporaryRegisterReader:
    """Short-lived register reads before a config entry exists.

    HA 2026.9+ uses ``async_get_temporary_unit`` (no extra socket). Older cores
    open a ModbusHub for the probe and close it afterwards.
    """

    def __init__(self, hass: HomeAssistant, params: dict[str, Any]) -> None:
        self.hass = hass
        self.params = dict(params)
        self._hub: Any | None = None
        self._uses_core = core_units_available()

    async def __aenter__(self) -> TemporaryRegisterReader:
        if self._uses_core:
            return self
        from homeassistant.components.modbus import ModbusHub

        from .device_utils import async_wait_for_hub_connected

        host = str(self.params.get("host") or "")
        port = int(self.params.get("port") or 502)
        modbus_type = _probe_connection_type(self.params)
        if modbus_type == "serial":
            raise RuntimeError("Serial identify uses the template path in this slice")
        timeout = int(self.params.get("timeout") or DEFAULT_TIMEOUT)
        hub_name = f"mm_identify_{host}_{port}"
        hub = ModbusHub(
            self.hass,
            {
                "name": hub_name,
                "type": "rtuovertcp" if modbus_type == "rtuovertcp" else "tcp",
                "host": host,
                "port": port,
                "delay": int(self.params.get("delay") or DEFAULT_DELAY),
                "message_wait_milliseconds": int(
                    self.params.get(
                        "message_wait_milliseconds", DEFAULT_MESSAGE_WAIT_MS
                    )
                ),
                "timeout": timeout,
                "slave": int(self.params.get("slave_id") or DEFAULT_SLAVE),
            },
        )
        await hub.async_setup()
        await async_wait_for_hub_connected(hub, timeout)
        self._hub = hub
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._hub is None:
            return
        try:
            await self._hub.async_close()
        except Exception as err:
            _LOGGER.debug("Identify hub close failed: %s", err)
        self._hub = None

    async def async_read(
        self,
        slave_id: int,
        address: int,
        count: int,
        input_type: str,
    ) -> list[int] | None:
        """Return register words, or None when the read fails."""
        call_type = (
            CALL_TYPE_REGISTER_INPUT
            if str(input_type).strip().lower() == "input"
            else CALL_TYPE_REGISTER_HOLDING
        )
        if self._uses_core:
            from homeassistant.components.modbus import async_get_temporary_unit

            probe_params = {
                **self.params,
                "connection_type": _probe_connection_type(self.params),
                "host": self.params.get("host"),
                "port": self.params.get("port") or 502,
            }
            link_params = connection_params_from_probe(probe_params)
            try:
                async with async_get_temporary_unit(
                    self.hass, link_params, int(slave_id)
                ) as unit:
                    timeout = self.params.get("timeout")
                    if timeout is not None and hasattr(unit, "require_timeout"):
                        unit.require_timeout(float(timeout))
                    wait_ms = self.params.get("message_wait_milliseconds")
                    if wait_ms and hasattr(unit, "set_message_spacing"):
                        unit.set_message_spacing(float(wait_ms) / 1000.0)
                    if call_type == CALL_TYPE_REGISTER_INPUT:
                        registers = await unit.read_input_registers(
                            int(address), int(count)
                        )
                    else:
                        registers = await unit.read_holding_registers(
                            int(address), int(count)
                        )
                    return list(registers) if registers is not None else None
            except Exception as err:
                _LOGGER.debug(
                    "Temporary unit read failed slave=%s addr=%s type=%s: %s",
                    slave_id,
                    address,
                    input_type,
                    err,
                )
                return None

        if self._hub is None:
            return None
        result = await self._hub.async_pb_call(
            int(slave_id), int(address), int(count), call_type
        )
        if result is None:
            return None
        registers = getattr(result, "registers", None)
        return list(registers) if registers is not None else None
