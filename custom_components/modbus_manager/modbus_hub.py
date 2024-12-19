"""ModbusManager Hub Implementation."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SLAVE,
    EVENT_HOMEASSISTANT_STOP
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY_ON_EMPTY,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_DELAY
)
from .device_base import ModbusManagerDeviceBase as ModbusManagerDevice
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerHub:
    """ModbusManager Hub Klasse."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialisiere den ModbusManager Hub."""
        self.hass = hass
        self.entry = entry
        self.name = entry.data[CONF_NAME]
        self._client: Optional[AsyncModbusTcpClient] = None
        self._devices: Dict[str, ModbusManagerDevice] = {}
        self._setup_lock = asyncio.Lock()
        self._device_configs: Dict[str, Dict[str, Any]] = {}
        self._connected = False

    async def async_setup(self) -> bool:
        """Richte den ModbusManager Hub ein."""
        try:
            # Konfiguriere den ModBus Client
            host = self.entry.data[CONF_HOST]
            port = self.entry.data.get(CONF_PORT, DEFAULT_PORT)
            
            self._client = AsyncModbusTcpClient(
                host=host,
                port=port,
                timeout=DEFAULT_TIMEOUT,
                retries=DEFAULT_RETRIES,
                reconnect_delay=DEFAULT_RETRY_DELAY,
                name=self.name
            )
            
            # Verbinde den Client
            if not await self._client.connect():
                _LOGGER.error(
                    "Verbindung zum ModBus Server fehlgeschlagen",
                    extra={
                        "host": host,
                        "port": port,
                        "entry_id": self.entry.entry_id
                    }
                )
                return False

            self._connected = True
            _LOGGER.info(
                "ModBus Verbindung hergestellt",
                extra={
                    "host": host,
                    "port": port,
                    "entry_id": self.entry.entry_id
                }
            )

            # Registriere den Stop-Handler
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP,
                self._handle_ha_stop
            )

            return True

        except Exception as error:
            _LOGGER.error(
                "Fehler beim Setup des ModBus Hubs",
                extra={"error": error, "entry_id": self.entry.entry_id}
            )
            return False

    async def async_write_register(self, slave: int, address: int, value: Any) -> None:
        """Schreibe einen Wert in ein Register."""
        try:
            if not self._connected or not self._client:
                _LOGGER.error(
                    "ModBus Client nicht verbunden",
                    extra={
                        "slave": slave,
                        "address": address,
                        "value": value
                    }
                )
                return

            # Schreibe den Wert
            result = await self._client.write_register(
                address=address,
                value=value,
                slave=slave
            )
            
            if isinstance(result, ExceptionResponse):
                _LOGGER.error(
                    "ModBus Fehler beim Schreiben",
                    extra={
                        "slave": slave,
                        "address": address,
                        "value": value,
                        "error": result
                    }
                )
                return
                
            _LOGGER.debug(
                "Register erfolgreich geschrieben",
                extra={
                    "slave": slave,
                    "address": address,
                    "value": value
                }
            )

        except ModbusException as error:
            _LOGGER.error(
                "ModBus Fehler beim Schreiben des Registers",
                extra={
                    "error": error,
                    "slave": slave,
                    "address": address,
                    "value": value
                }
            )
            raise

    async def async_read_registers(self, slave: int, address: int, count: int) -> List[int]:
        """Lese mehrere Register."""
        try:
            if not self._connected or not self._client:
                _LOGGER.error(
                    "ModBus Client nicht verbunden",
                    extra={
                        "slave": slave,
                        "address": address,
                        "count": count
                    }
                )
                return []

            # Lese die Register
            result = await self._client.read_holding_registers(
                address=address,
                count=count,
                slave=slave
            )
            
            if isinstance(result, ExceptionResponse):
                _LOGGER.error(
                    "ModBus Fehler beim Lesen",
                    extra={
                        "slave": slave,
                        "address": address,
                        "count": count,
                        "error": result
                    }
                )
                return []
                
            values = result.registers if result and hasattr(result, 'registers') else []
            
            _LOGGER.debug(
                "Register erfolgreich gelesen",
                extra={
                    "slave": slave,
                    "address": address,
                    "count": count,
                    "values": values
                }
            )
            
            return values

        except ModbusException as error:
            _LOGGER.error(
                "ModBus Fehler beim Lesen der Register",
                extra={
                    "error": error,
                    "slave": slave,
                    "address": address,
                    "count": count
                }
            )
            return []

    @callback
    def _handle_ha_stop(self, event: Event) -> None:
        """Handle Home Assistant stopping."""
        self.async_unload()

    def async_unload(self) -> None:
        """Entlade den Hub und alle Geräte."""
        if self._client and self._connected:
            asyncio.create_task(self._client.close())
            self._client = None
            self._connected = False
