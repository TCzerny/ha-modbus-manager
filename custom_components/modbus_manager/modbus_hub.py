"""ModbusManager Hub Implementation."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set
import os
import yaml
import aiofiles

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
    DEFAULT_RETRY_DELAY,
    NameType
)
from .device_base import ModbusManagerDeviceBase as ModbusManagerDevice
from .logger import ModbusManagerLogger
from .helpers import EntityNameHelper

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerHub:
    """ModbusManager Hub Klasse."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry | dict) -> None:
        """Initialisiere den ModbusManager Hub."""
        self.hass = hass
        self.entry = entry
        self._devices = {}
        self._client = None
        self._lock = asyncio.Lock()
        self._connected = False
        
        # Initialisiere den Name Helper
        self.name_helper = EntityNameHelper(entry)
        
        # Extrahiere die Konfigurationsdaten
        config_data = entry.data if hasattr(entry, 'data') else entry
        
        # Generiere eindeutige Namen
        self._name = self.name_helper.convert(config_data[CONF_NAME], NameType.BASE_NAME)
        self._unique_id = self.name_helper.convert(config_data[CONF_NAME], NameType.UNIQUE_ID)
        
        _LOGGER.debug(
            "ModbusManager Hub initialisiert",
            extra={
                "name": self._name,
                "unique_id": self._unique_id,
                "entry_id": entry.entry_id if hasattr(entry, 'entry_id') else None
            }
        )

    @property
    def name(self) -> str:
        """Gibt den Namen des Hubs zurück."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Gibt die eindeutige ID des Hubs zurück."""
        return self._unique_id

    async def async_setup(self) -> bool:
        """Richte den ModbusManager Hub ein."""
        try:
            # Extrahiere die Konfigurationsdaten
            config_data = self.entry.data if hasattr(self.entry, 'data') else self.entry
            
            # Konfiguriere den ModBus Client
            host = config_data[CONF_HOST]
            port = config_data.get(CONF_PORT, DEFAULT_PORT)
            
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
                        "entry_id": self.entry.entry_id if hasattr(self.entry, 'entry_id') else None
                    }
                )
                return False

            self._connected = True
            _LOGGER.info(
                "ModBus Verbindung hergestellt",
                extra={
                    "host": host,
                    "port": port,
                    "entry_id": self.entry.entry_id if hasattr(self.entry, 'entry_id') else None
                }
            )

            # Initialisiere das Device
            device_type = config_data.get("device_type", "")
            device_config = {
                CONF_NAME: config_data[CONF_NAME],
                CONF_SLAVE: config_data.get(CONF_SLAVE, DEFAULT_SLAVE),
                CONF_HOST: config_data[CONF_HOST],
                CONF_PORT: config_data.get(CONF_PORT, DEFAULT_PORT),
            }
            
            # Lade die Gerätedefinitionen
            definition_file = os.path.join(os.path.dirname(__file__), "device_definitions", f"{device_type}.yaml")
            try:
                async with aiofiles.open(definition_file, 'r') as f:
                    content = await f.read()
                    register_definitions = yaml.safe_load(content)
            except Exception as error:
                _LOGGER.error(
                    "Fehler beim Laden der Gerätedefinition",
                    extra={
                        "error": error,
                        "file": definition_file
                    }
                )
                return False
            
            device = ModbusManagerDevice(
                self,
                device_type,
                device_config,
                register_definitions
            )
            
            if await device.async_setup():
                self._devices[config_data[CONF_NAME]] = device
                _LOGGER.info(
                    "Device erfolgreich initialisiert",
                    extra={
                        "name": config_data[CONF_NAME],
                        "type": device_type
                    }
                )
            else:
                _LOGGER.error(
                    "Device-Initialisierung fehlgeschlagen",
                    extra={
                        "name": config_data[CONF_NAME],
                        "type": device_type
                    }
                )
                return False

            # Registriere den Stop-Handler
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP,
                self._handle_ha_stop
            )

            return True

        except Exception as error:
            _LOGGER.error(
                "Fehler beim Setup des ModBus Hubs",
                extra={
                    "error": error,
                    "entry_id": self.entry.entry_id if hasattr(self.entry, 'entry_id') else None
                }
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
        """Liest mehrere Holding-Register."""
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
                    "ModBus Fehler beim Lesen der Holding-Register",
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
                "Holding-Register erfolgreich gelesen",
                extra={
                    "slave": slave,
                    "address": address,
                    "count": count,
                    "values": values
                }
            )
            
            return values

        except ModbusException as e:
            _LOGGER.error(
                "ModBus Fehler beim Lesen der Holding-Register",
                extra={
                    "error": str(e),
                    "slave": slave,
                    "address": address,
                    "count": count,
                    "traceback": e.__traceback__
                }
            )
            return []

    async def async_read_input_registers(self, slave: int, address: int, count: int) -> List[int]:
        """Liest mehrere Input-Register."""
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
            result = await self._client.read_input_registers(
                address=address,
                count=count,
                slave=slave
            )
            
            if isinstance(result, ExceptionResponse):
                _LOGGER.error(
                    "ModBus Fehler beim Lesen der Input-Register",
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
                "Input-Register erfolgreich gelesen",
                extra={
                    "slave": slave,
                    "address": address,
                    "count": count,
                    "values": values
                }
            )
            
            return values

        except ModbusException as e:
            _LOGGER.error(
                "ModBus Fehler beim Lesen der Input-Register",
                extra={
                    "error": str(e),
                    "slave": slave,
                    "address": address,
                    "count": count,
                    "traceback": e.__traceback__
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
