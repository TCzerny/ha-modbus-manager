"""ModbusManager Hub."""
from __future__ import annotations

import asyncio
import os
import yaml
import aiofiles
from typing import Any, Dict, List, Optional, Set

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
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
from .helpers import EntityNameHelper

from .device_base import ModbusManagerDeviceBase as ModbusManagerDevice
from .logger import ModbusManagerLogger

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
        
        # Entity-Status-Tracking
        self._entities_added = False
        self._entity_setup_tasks = {}
        self._pending_entities = set()
        
        # Extrahiere und validiere die Konfigurationsdaten
        if hasattr(entry, 'data'):
            config_data = entry.data
        elif isinstance(entry, dict):
            config_data = entry
        else:
            raise ValueError(f"Ungültige Konfiguration: {type(entry)}")
        
        # Prüfe ob alle erforderlichen Konfigurationsfelder vorhanden sind
        required_fields = [CONF_NAME, CONF_HOST]
        for field in required_fields:
            if field not in config_data:
                raise ValueError(f"Pflichtfeld {field} fehlt in der Konfiguration")
        
        # Initialisiere den Name Helper
        self.name_helper = EntityNameHelper(entry)
        
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
    def entities_added(self) -> bool:
        """Gibt zurück, ob alle Entities hinzugefügt wurden."""
        return self._entities_added

    @entities_added.setter
    def entities_added(self, value: bool) -> None:
        """Setzt den Status der Entity-Hinzufügung."""
        self._entities_added = value
        if value:
            _LOGGER.info(
                "Alle Entities wurden hinzugefügt",
                extra={"hub": self.name}
            )

    async def async_track_entity_setup(self, entity_id: str) -> None:
        """Verfolge das Setup einer Entity."""
        self._pending_entities.add(entity_id)
        _LOGGER.debug(
            "Entity-Setup wird verfolgt",
            extra={
                "hub": self.name,
                "entity_id": entity_id,
                "pending_count": len(self._pending_entities)
            }
        )

    async def async_entity_setup_complete(self, entity_id: str) -> None:
        """Markiere das Setup einer Entity als abgeschlossen."""
        if entity_id in self._pending_entities:
            self._pending_entities.remove(entity_id)
            _LOGGER.debug(
                "Entity-Setup abgeschlossen",
                extra={
                    "hub": self.name,
                    "entity_id": entity_id,
                    "pending_count": len(self._pending_entities)
                }
            )

    @property
    def has_pending_entities(self) -> bool:
        """Prüft, ob noch Entities auf Setup warten."""
        return len(self._pending_entities) > 0

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
            
            # Setze den Entity-Setup-Status zurück
            self._entities_added = False
            self._pending_entities.clear()
            
            # Konfiguriere den ModBus Client
            host = config_data[CONF_HOST]
            port = config_data.get(CONF_PORT, DEFAULT_PORT)
            
            _LOGGER.debug(
                "Initialisiere ModBus Client",
                extra={
                    "host": host,
                    "port": port,
                    "timeout": DEFAULT_TIMEOUT,
                    "retries": DEFAULT_RETRIES,
                    "reconnect_delay": DEFAULT_RETRY_DELAY
                }
            )
            
            self._client = AsyncModbusTcpClient(
                host=host,
                port=port,
                timeout=DEFAULT_TIMEOUT,
                retries=DEFAULT_RETRIES,
                reconnect_delay=DEFAULT_RETRY_DELAY,
                name=self.name
            )
            
            # Verbinde den Client mit Retry-Logik
            retry_count = 0
            max_retries = DEFAULT_RETRIES
            while retry_count < max_retries:
                try:
                    if await self._client.connect():
                        self._connected = True
                        _LOGGER.info(
                            "ModBus Verbindung hergestellt",
                            extra={
                                "host": host,
                                "port": port,
                                "retry": retry_count,
                                "entry_id": self.entry.entry_id if hasattr(self.entry, 'entry_id') else None
                            }
                        )
                        break
                    else:
                        retry_count += 1
                        _LOGGER.warning(
                            "Verbindungsversuch fehlgeschlagen, versuche erneut",
                            extra={
                                "host": host,
                                "port": port,
                                "retry": retry_count,
                                "max_retries": max_retries
                            }
                        )
                        await asyncio.sleep(DEFAULT_RETRY_DELAY)
                except Exception as connect_error:
                    retry_count += 1
                    _LOGGER.error(
                        "Fehler beim Verbindungsversuch",
                        extra={
                            "error": str(connect_error),
                            "host": host,
                            "port": port,
                            "retry": retry_count,
                            "max_retries": max_retries
                        }
                    )
                    await asyncio.sleep(DEFAULT_RETRY_DELAY)
            
            if not self._connected:
                _LOGGER.error(
                    "Verbindung zum ModBus Server fehlgeschlagen nach allen Versuchen",
                    extra={
                        "host": host,
                        "port": port,
                        "retries": retry_count,
                        "entry_id": self.entry.entry_id if hasattr(self.entry, 'entry_id') else None
                    }
                )
                return False

            # Initialisiere das Device
            device_type = config_data.get("device_type", "")
            _LOGGER.debug(
                "Initialisiere Device",
                extra={
                    "device_type": device_type,
                    "name": config_data[CONF_NAME]
                }
            )
            
            device_config = {
                CONF_NAME: config_data[CONF_NAME],
                CONF_SLAVE: config_data.get(CONF_SLAVE, DEFAULT_SLAVE),
                CONF_HOST: config_data[CONF_HOST],
                CONF_PORT: config_data.get(CONF_PORT, DEFAULT_PORT),
            }
            
            # Lade die Gerätedefinitionen
            definition_file = os.path.join(os.path.dirname(__file__), "device_definitions", f"{device_type}.yaml")
            try:
                _LOGGER.debug(
                    "Lade Gerätedefinition",
                    extra={"file": definition_file}
                )
                async with aiofiles.open(definition_file, 'r') as f:
                    content = await f.read()
                    register_definitions = yaml.safe_load(content)
                    _LOGGER.debug(
                        "Gerätedefinition geladen",
                        extra={
                            "file": definition_file,
                            "definitions": register_definitions.keys()
                        }
                    )
            except Exception as error:
                _LOGGER.error(
                    "Fehler beim Laden der Gerätedefinition",
                    extra={
                        "error": str(error),
                        "file": definition_file,
                        "traceback": error.__traceback__
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
                    "error": str(error),
                    "traceback": error.__traceback__,
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


