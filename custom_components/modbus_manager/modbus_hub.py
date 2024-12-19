"""Modbus Manager Hub."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Optional, Union, List
import aiofiles
import yaml
from pathlib import Path
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SLAVE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException
from pymodbus.pdu import ExceptionResponse

from .const import (
    DOMAIN,
    CONF_DEVICE_TYPE,
)
from .logger import ModbusManagerLogger
from .device import ModbusManagerDevice

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerHub:
    """Modbus Manager Hub class."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ):
        """Initialize the hub."""
        self.hass = hass
        self.config_entry = config_entry
        self.config = config_entry.data
        
        # Basis-Konfiguration
        self.name = self.config.get(CONF_NAME)
        self.host = self.config.get(CONF_HOST)
        self.port = self.config.get(CONF_PORT)
        self.slave = self.config.get(CONF_SLAVE)
        self.device_type = self.config.get(CONF_DEVICE_TYPE)
        
        # Modbus Client
        self._client = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._available = False
        
        # Geräte-Verwaltung
        self._devices: Dict[str, ModbusManagerDevice] = {}
        
        # Koordinatoren für verschiedene Polling-Intervalle
        self.coordinators: Dict[str, DataUpdateCoordinator] = {}

    async def async_setup(self) -> bool:
        """Führt das Setup des Hubs durch."""
        try:
            # Initialisiere den Modbus-Client
            self._client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
            )
            
            # Hole die Device-Definition
            device_def = await self._load_device_definition()
            if not device_def:
                return False

            # Registriere ein einzelnes Gerät im Device Registry
            dev_reg = dr.async_get(self.hass)
            device_entry = dev_reg.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, f"{self.name}")},
                name=self.name,
                manufacturer=device_def.get("manufacturer", "Modbus Manager"),
                model=device_def.get("model", self.device_type),
                sw_version=device_def.get("version", "1.0")
            )

            # Initialisiere die Koordinatoren-Map
            self.coordinators = {}
                
            # Erstelle Koordinatoren für alle einzigartigen Polling-Intervalle
            polling_intervals = set()
            
            # Sammle Polling-Intervalle aus den Registern
            if "registers" in device_def:
                for register in device_def["registers"].get("read", []):
                    polling_intervals.add(str(register.get("polling_interval", 30)))
                for register in device_def["registers"].get("write", []):
                    polling_intervals.add(str(register.get("polling_interval", 30)))
            
            # Erstelle einen Koordinator für jedes Intervall
            for interval in polling_intervals:
                update_interval = timedelta(seconds=int(interval))
                _LOGGER.debug(
                    "Erstelle Koordinator",
                    extra={
                        "interval": interval,
                        "update_interval": str(update_interval),
                        "hub": self.name
                    }
                )
                
                coordinator = DataUpdateCoordinator(
                    self.hass,
                    _LOGGER,
                    name=f"{self.name}_coordinator_{interval}",
                    update_method=lambda interval=interval: self._async_update_data(interval),
                    update_interval=update_interval
                )
                self.coordinators[interval] = coordinator
                
                # Starte den Koordinator
                try:
                    _LOGGER.debug(
                        "Starte Koordinator",
                        extra={
                            "interval": interval,
                            "hub": self.name
                        }
                    )
                    await coordinator.async_config_entry_first_refresh()
                    _LOGGER.debug(
                        "Koordinator erfolgreich gestartet",
                        extra={
                            "interval": interval,
                            "hub": self.name
                        }
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Starten des Koordinators",
                        extra={
                            "error": str(e),
                            "interval": interval,
                            "hub": self.name
                        }
                    )
                    return False
                
            # Erstelle und speichere das Gerät
            device = ModbusManagerDevice(
                hub=self,
                device_type=self.device_type,
                config={
                    "name": self.name,  # Verwende den Hub-Namen statt des Gerätetyps
                    "entry_id": self.config_entry.entry_id,
                    "config_entry": self.config_entry,
                    "manufacturer": device_def.get("manufacturer", "Modbus Manager"),
                    "model": device_def.get("model", self.device_type)
                },
                register_definitions=device_def
            )
            
            # Setup des Geräts
            if not await device.async_setup():
                return False
                
            # Speichere das Gerät in der Geräte-Map
            self._devices[self.name] = device
                
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup des Hubs",
                extra={
                    "error": str(e),
                    "hub": self.name
                }
            )
            return False

    def _group_registers(self, registers: Dict) -> Dict[int, list]:
        """Gruppiert Register nach Polling-Intervall."""
        polling_groups = {}
        
        for reg_type in ["read", "write"]:
            if reg_type not in registers:
                continue
                
            for register in registers[reg_type]:
                interval = register.get("polling_interval", 30)
                if interval not in polling_groups:
                    polling_groups[interval] = []
                polling_groups[interval].append(register)
        
        return polling_groups

    async def _load_device_definition(self) -> Optional[dict]:
        """Lädt die Gerätedefinition aus der YAML-Datei."""
        try:
            definition_path = (
                Path(__file__).parent / "device_definitions" / f"{self.device_type}.yaml"
            )

            if not definition_path.exists():
                _LOGGER.error(f"Gerätedefinition nicht gefunden: {self.device_type}")
                return None

            async with aiofiles.open(definition_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
                
                # Ersetze die Slave-ID-Variable
                content = content.replace("SLAVE_ID", str(self.slave))
                
                # Lade die YAML
                definition = yaml.safe_load(content)
                
                if not definition:
                    return None

                # Entferne Sonderzeichen und Leerzeichen aus dem Gerätenamen für die Entity-ID
                sanitized_device_name = re.sub(r'[^\w\s-]', '', self.name.lower())
                sanitized_device_name = re.sub(r'[-\s]+', '_', sanitized_device_name)

                # Aktualisiere die Register-Namen und Beschreibungen
                if "registers" in definition:
                    for reg_type in ["read", "write"]:
                        if reg_type in definition["registers"]:
                            for register in definition["registers"][reg_type]:
                                if "name" in register:
                                    # Generiere die Entity-ID mit Präfix
                                    base_name = register["name"]
                                    entity_id = f"sensor.{sanitized_device_name}_{base_name}"
                                    
                                    # Generiere den Anzeigenamen mit EINEM Präfix
                                    if "description" in register:
                                        display_name = register["description"]
                                    else:
                                        # Konvertiere snake_case in Title Case für bessere Lesbarkeit
                                        words = base_name.split("_")
                                        display_name = " ".join(word.capitalize() for word in words)
                                    
                                    # Setze Entity-ID und Namen
                                    register["entity_id"] = entity_id
                                    register["unique_id"] = f"{sanitized_device_name}_{base_name}"
                                    register["name"] = f"{self.name} {display_name}"  # Genau EIN Präfix

                return definition

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Laden der Gerätedefinition",
                extra={
                    "error": str(e),
                    "device_type": self.device_type,
                    "name": self.name
                }
            )
            return None

    async def _async_update_data(self, interval: str = "30") -> Dict[str, Any]:
        """Update data für alle Register mit dem spezifizierten Polling-Intervall."""
        try:
            _LOGGER.debug(
                "Starte Update-Zyklus",
                extra={
                    "interval": interval,
                    "hub": self.name,
                    "connected": self._connected,
                    "available": self._available
                }
            )

            if not self._connected or not self._available:
                _LOGGER.debug(
                    "Versuche Verbindung wiederherzustellen",
                    extra={
                        "hub": self.name,
                        "host": self.host,
                        "port": self.port
                    }
                )
                connect_result = await self._client.connect()
                if not connect_result:
                    raise Exception("Verbindung konnte nicht hergestellt werden")
                self._connected = True
                self._available = True

            data = {}
            for device in self._devices.values():
                _LOGGER.debug(
                    "Aktualisiere Gerät",
                    extra={
                        "device": device.name,
                        "interval": interval,
                        "hub": self.name
                    }
                )
                # Aktualisiere nur Register mit dem entsprechenden Polling-Intervall
                device_data = await device.async_update(polling_interval=interval)
                if device_data:
                    data[device.name] = device_data
                    _LOGGER.debug(
                        "Gerät erfolgreich aktualisiert",
                        extra={
                            "device": device.name,
                            "data": device_data,
                            "interval": interval,
                            "hub": self.name
                        }
                    )
                else:
                    _LOGGER.warning(
                        "Keine Daten vom Gerät erhalten",
                        extra={
                            "device": device.name,
                            "interval": interval,
                            "hub": self.name
                        }
                    )

            return data

        except Exception as e:
            self._available = False
            _LOGGER.error(
                f"Fehler beim Aktualisieren der Daten für Intervall {interval}",
                extra={
                    "error": str(e),
                    "hub": self.name,
                    "interval": interval,
                    "traceback": e.__traceback__
                }
            )
            raise e

    async def async_teardown(self):
        """Bereinigt den Hub und alle zugehörigen Entitäten."""
        try:
            _LOGGER.debug(
                "Starte Teardown-Prozess",
                extra={
                    "hub": self.name
                }
            )

            # Stoppe alle Koordinatoren
            if self.coordinators:
                for coordinator in self.coordinators.values():
                    if coordinator:
                        await coordinator.async_shutdown()

            # Bereinige alle Geräte
            if self._devices:
                for device in list(self._devices.values()):
                    if device:
                        try:
                            await device.async_teardown()
                        except Exception as device_error:
                            _LOGGER.warning(
                                "Fehler beim Teardown eines Geräts",
                                extra={
                                    "error": str(device_error),
                                    "device": device.name,
                                    "hub": self.name
                                }
                            )
            
            # Schließe die Modbus-Verbindung
            if self._client and self._connected:
                try:
                    await self._client.close()
                except Exception as client_error:
                    _LOGGER.warning(
                        "Fehler beim Schließen der Modbus-Verbindung",
                        extra={
                            "error": str(client_error),
                            "hub": self.name
                        }
                    )

            # Entferne Entitäten aus dem Entity Registry
            try:
                ent_reg = er.async_get(self.hass)
                if ent_reg:
                    # Finde alle Entitäten, die zu diesem Hub gehören
                    entries = er.async_entries_for_config_entry(
                        ent_reg, self.config_entry.entry_id
                    )
                    
                    # Entferne jede Entität
                    for entry in entries:
                        _LOGGER.debug(
                            "Entferne Entität",
                            extra={
                                "entity_id": entry.entity_id,
                                "hub": self.name
                            }
                        )
                        ent_reg.async_remove(entry.entity_id)
            except Exception as ent_error:
                _LOGGER.warning(
                    "Fehler beim Entfernen von Entitäten aus dem Entity Registry",
                    extra={
                        "error": str(ent_error),
                        "hub": self.name
                    }
                )

            # Entferne das Gerät aus dem Device Registry
            try:
                dev_reg = dr.async_get(self.hass)
                if dev_reg:
                    device_entry = dev_reg.async_get_device(
                        identifiers={(DOMAIN, f"{self.name}")}
                    )
                    if device_entry:
                        _LOGGER.debug(
                            "Entferne Gerät aus dem Device Registry",
                            extra={
                                "device_id": device_entry.id,
                                "hub": self.name
                            }
                        )
                        dev_reg.async_remove_device(device_entry.id)
            except Exception as reg_error:
                _LOGGER.warning(
                    "Fehler beim Entfernen des Geräts aus dem Device Registry",
                    extra={
                        "error": str(reg_error),
                        "hub": self.name
                    }
                )

            # Bereinige lokale Referenzen
            self._client = None
            self._connected = False
            self._available = False
            self._devices.clear()
            self.coordinators.clear()

            _LOGGER.debug(
                "Teardown-Prozess abgeschlossen",
                extra={
                    "hub": self.name
                }
            )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Hub-Teardown",
                extra={
                    "error": str(e),
                    "hub": self.name
                }
            )

    async def connect(self) -> None:
        """Verbindung zum Modbus-Client herstellen."""
        if self._client is None:
            _LOGGER.debug(
                "Erstelle neuen Modbus-Client",
                extra={
                    "host": self.host,
                    "port": self.port,
                    "slave": self.slave,
                }
            )
            self._client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.config.get("tcp_timeout", 3),
                retries=self.config.get("max_retries", 3),
                retry_on_empty=True,
                close_comm_on_error=False,
                reconnect_delay=self.config.get("retry_delay", 0.1),
            )
        
        if not self._client.connected:
            try:
                await self._client.connect()
                _LOGGER.debug(
                    "Modbus-Client erfolgreich verbunden",
                    extra={
                        "host": self.host,
                        "port": self.port,
                        "slave": self.slave,
                    }
                )
            except Exception as e:
                _LOGGER.error(
                    "Fehler beim Verbinden des Modbus-Clients",
                    extra={
                        "error": str(e),
                        "host": self.host,
                        "port": self.port,
                        "slave": self.slave,
                    }
                )
                self._client = None
                raise

    async def disconnect(self) -> None:
        """Verbindung zum Modbus-Client trennen."""
        if self._client and self._client.connected:
            _LOGGER.debug(
                "Trenne Modbus-Client",
                extra={
                    "host": self.host,
                    "port": self.port,
                    "slave": self.slave,
                }
            )
            await self._client.close()
            self._client = None

    async def ensure_connected(self) -> None:
        """Stelle sicher, dass eine Verbindung besteht."""
        try:
            if not self._client or not self._client.connected:
                await self.connect()
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Sicherstellen der Modbus-Verbindung",
                extra={
                    "error": str(e),
                    "host": self.host,
                    "port": self.port,
                    "slave": self.slave,
                }
            )
            raise

    async def read_register(
        self,
        device_name: str,
        address: int,
        count: int = 1,
        reg_type: str = "uint16",
        register_type: str = "input"
    ) -> Optional[list]:
        """Liest Modbus Register."""
        try:
            # Verbindungsstatus loggen
            _LOGGER.debug(
                "Prüfe Modbus-Verbindungsstatus",
                extra={
                    "connected": self._connected,
                    "available": self._available,
                    "host": self.host,
                    "port": self.port,
                    "device": device_name,
                    "register_type": register_type,
                    "address": address
                }
            )
            
            if not self._connected:
                _LOGGER.debug(
                    "Versuche Modbus-Verbindung herzustellen",
                    extra={
                        "host": self.host,
                        "port": self.port,
                        "device": device_name
                    }
                )
                connect_result = await self._client.connect()
                _LOGGER.debug(
                    "Modbus-Verbindungsversuch abgeschlossen",
                    extra={
                        "success": connect_result,
                        "host": self.host,
                        "port": self.port,
                        "device": device_name
                    }
                )
                
                if not connect_result:
                    _LOGGER.error(
                        "Modbus-Verbindung konnte nicht hergestellt werden",
                        extra={
                            "host": self.host,
                            "port": self.port,
                            "device": device_name
                        }
                    )
                    self._connected = False
                    return None
                self._connected = True

            async with self._lock:
                # Stelle sicher, dass eine Slave-ID gesetzt ist
                slave_id = self.slave if self.slave is not None else 1
                
                _LOGGER.debug(
                    "Sende Modbus Leseanfrage",
                    extra={
                        "device": device_name,
                        "address": address,
                        "count": count,
                        "type": reg_type,
                        "register_type": register_type,
                        "slave": slave_id
                    }
                )

                # Versuche zuerst als Input Register zu lesen, wenn es fehlschlägt und register_type "holding" ist,
                # versuche es als Holding Register
                result = None
                if register_type == "input" or register_type != "holding":
                    result = await self._client.read_input_registers(
                        address=address-1,
                        count=count,
                        slave=slave_id
                    )
                    
                if (result is None or result.isError()) and register_type == "holding":
                    result = await self._client.read_holding_registers(
                        address=address-1,
                        count=count,
                        slave=slave_id
                    )

                if result is None or result.isError():
                    error_message = "Keine Antwort"
                    if isinstance(result, ExceptionResponse):
                        error_message = f"Modbus Exception Code: {result.exception_code}"
                    elif hasattr(result, 'message'):
                        error_message = str(result.message)
                        
                    _LOGGER.error(
                        "Fehler bei Modbus-Abfrage",
                        extra={
                            "device": device_name,
                            "address": address,
                            "slave": slave_id,
                            "error": error_message,
                            "register_type": register_type,
                            "raw_result": str(result) if result else None
                        }
                    )
                    return None

                _LOGGER.debug(
                    "Modbus Leseanfrage erfolgreich",
                    extra={
                        "device": device_name,
                        "address": address,
                        "registers": result.registers,
                        "register_type": register_type,
                        "slave": slave_id
                    }
                )
                return result.registers
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Lesen des Registers",
                extra={
                    "error": str(e),
                    "device": device_name,
                    "address": address,
                    "register_type": register_type,
                    "slave": self.slave,
                    "traceback": e.__traceback__
                }
            )
        return None

    async def write_register(
        self,
        device_name: str,
        address: int,
        value: int,
        reg_type: str = "uint16",
        scale: float = 1
    ) -> bool:
        """Schreibt in ein Modbus Register."""
        try:
            if not self._connected or not self._available:
                _LOGGER.debug(
                    "Versuche Modbus-Verbindung herzustellen",
                    extra={
                        "host": self.host,
                        "port": self.port,
                        "device": device_name
                    }
                )
                if not await self._client.connect():
                    _LOGGER.error(
                        "Modbus-Verbindung konnte nicht hergestellt werden",
                        extra={
                            "host": self.host,
                            "port": self.port,
                            "device": device_name
                        }
                    )
                    return False
                self._connected = True
                self._available = True

            async with self._lock:
                # Stelle sicher, dass eine Slave-ID gesetzt ist
                slave_id = self.slave if self.slave is not None else 1
                
                # Skaliere den Wert wenn nötig
                scaled_value = int(value / scale) if scale != 1 else value
                
                _LOGGER.debug(
                    "Sende Modbus Schreibanfrage",
                    extra={
                        "device": device_name,
                        "address": address,
                        "value": value,
                        "scaled_value": scaled_value,
                        "scale": scale,
                        "type": reg_type,
                        "slave": slave_id
                    }
                )

                result = await self._client.write_register(
                    address=address-1,  # Modbus uses 0-based addressing
                    value=scaled_value,
                    slave=slave_id
                )

                if result is None or result.isError():
                    self._available = False
                    error_message = "Keine Antwort"
                    if isinstance(result, ExceptionResponse):
                        error_message = f"Modbus Exception Code: {result.exception_code}"
                    elif hasattr(result, 'message'):
                        error_message = str(result.message)
                    
                    _LOGGER.error(
                        "Fehler beim Schreiben des Registers",
                        extra={
                            "device": device_name,
                            "address": address,
                            "value": value,
                            "scaled_value": scaled_value,
                            "slave": slave_id,
                            "error": error_message,
                            "raw_result": str(result) if result else None
                        }
                    )
                    return False

                _LOGGER.debug(
                    "Modbus Schreibanfrage erfolgreich",
                    extra={
                        "device": device_name,
                        "address": address,
                        "value": value,
                        "scaled_value": scaled_value,
                        "slave": slave_id
                    }
                )
                return True

        except Exception as e:
            self._available = False
            _LOGGER.error(
                "Fehler beim Schreiben des Registers",
                extra={
                    "error": str(e),
                    "device": device_name,
                    "address": address,
                    "value": value,
                    "slave": self.slave,
                    "traceback": e.__traceback__
                }
            )
            return False
