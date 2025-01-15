"""Modbus Manager Hub."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Optional, List
import aiofiles
import yaml
from pathlib import Path
import re

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException
from pymodbus.pdu import ExceptionResponse

from homeassistant.components.modbus import get_hub
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SLAVE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, CONF_DEVICE_TYPE
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
        
        # Thread-Sicherheit
        self._lock = asyncio.Lock()
        
        # Modbus Client
        self._client: Optional[AsyncModbusTcpClient] = None
        
        # Geräte-Verwaltung
        self._devices: Dict[str, ModbusManagerDevice] = {}
        
        # Koordinatoren für verschiedene Polling-Intervalle
        self.coordinators: Dict[int, DataUpdateCoordinator] = {}

    def get_coordinator(self, interval: int) -> DataUpdateCoordinator | None:
        """Gibt den Koordinator für das angegebene Intervall zurück."""
        return self.coordinators.get(interval)

    def create_coordinator(self, interval: int) -> DataUpdateCoordinator:
        """Erstellt einen neuen Koordinator für das angegebene Intervall."""
        coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=f"{self.name} {interval}s",
            update_method=self._create_update_method(interval),
            update_interval=timedelta(seconds=interval),
        )
        self.coordinators[interval] = coordinator
        return coordinator

    def _create_update_method(self, interval: int):
        """Erstellt eine Update-Methode für den angegebenen Intervall."""
        async def update_method():
            try:
                data = {}
                # Aktualisiere jedes Gerät
                for device_name, device in self._devices.items():
                    try:
                        device_data = await device.async_update(interval)
                        data[device_name] = device_data
                    except Exception as e:
                        _LOGGER.error(
                            "Fehler beim Aktualisieren der Daten",
                            extra={
                                "error": str(e),
                                "interval": interval,
                                "hub": self.name
                            }
                        )
                return data
            except Exception as e:
                _LOGGER.error(
                    f"Unexpected error fetching {self.name} {interval}s data",
                    exc_info=e
                )
                raise
        return update_method

    async def _async_update_data(self, interval: int) -> dict:
        """Aktualisiert die Daten für den angegebenen Intervall."""
        try:
            data = {}
            # Aktualisiere jedes Gerät
            for device_name, device in self._devices.items():
                try:
                    device_data = await device.async_update(interval)
                    data[device_name] = device_data
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Aktualisieren der Daten",
                        extra={
                            "error": str(e),
                            "interval": interval,
                            "hub": self.name
                        }
                    )
            return data
        except Exception as e:
            _LOGGER.error(
                f"Unexpected error fetching {self.name} {interval}s data",
                exc_info=e
            )
            raise

    async def _read_registers(self, registers: List[dict]) -> Dict[str, Any]:
        """Liest die angegebenen Register."""
        try:
            if not self._client or not self._client.connected:
                if not await self._client.connect():
                    return {}

            data = {}
            for register in registers:
                try:
                    address = register.get("address")
                    if address is None:  # Überspringe Register ohne Adresse
                        continue
                        
                    count = register.get("count", 1)
                    register_type = register.get("register_type", "holding")
                    data_type = register.get("type")
                    
                    # Lese das Register
                    if register_type == "input":
                        values = await self._client.read_input_registers(address, count, slave=self.slave)
                    else:
                        values = await self._client.read_holding_registers(address, count, slave=self.slave)
                    
                    if not values or values.isError():
                        continue
                    
                    # Verarbeite die Werte basierend auf dem Datentyp
                    if data_type == "string":
                        value = self._decode_string(values.registers)
                    elif data_type == "uint32":
                        value = self._decode_uint32(values.registers)
                    elif data_type == "int32":
                        value = self._decode_int32(values.registers)
                    else:
                        value = values.registers[0]
                    
                    data[register.get("name")] = value
                    
                except Exception as e:
                    _LOGGER.warning(
                        "Fehler beim Lesen eines Registers",
                        extra={
                            "error": str(e),
                            "register": register.get("name"),
                            "address": address,
                            "hub": self.name
                        }
                    )
                    continue
                    
            return data
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Lesen der Register",
                extra={
                    "error": str(e),
                    "hub": self.name
                }
            )
            return {}

    async def async_setup(self) -> bool:
        """Führt das Setup des Hubs durch."""
        try:
            # Initialisiere den Modbus Client mit optimierten Timeouts

                # AsyncModbusTcpClient.
                # Parameters:
                #  - host – Host IP address or host name
                # 
                # Optional parameters:
                #  - framer – Framer name, default FramerType.SOCKET
                #  - port – Port used for communication
                #  - name – Set communication name, used in logging
                #  - source_address – source address of client
                #  - reconnect_delay – Minimum delay in seconds.milliseconds before reconnecting.
                #  - reconnect_delay_max – Maximum delay in seconds.milliseconds before reconnecting.
                #  - timeout – Timeout for connecting and receiving data, in seconds.
                #  - retries – Max number of retries per request.
                #  - trace_packet – Called with bytestream received/to be sent
                #  - trace_pdu – Called with PDU received/to be sent
                #  - trace_connect – Called when connected/disconnected

            self._client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                reconnect_delay=1,
                reconnect_delay_max=10,
                timeout=3,  
                retries=2
            )
            
            if not await self._client.connect():
                _LOGGER.error(
                    "Verbindung zum Modbus Gerät fehlgeschlagen",
                    extra={
                        "host": self.host,
                        "port": self.port,
                        "hub": self.name
                    }
                )
                return False

            _LOGGER.debug(
                "Modbus Client erfolgreich verbunden",
                extra={"hub": self.name}
            )

            # Hole die Device-Definition
            device_def = await self._load_device_definition()
            if not device_def:
                _LOGGER.error("Keine Gerätedefinition gefunden", extra={"hub": self.name})
                return False

            # Erstelle das Gerät
            device = ModbusManagerDevice(
                hub=self,
                device_type=self.device_type,
                config={
                    **self.config,
                    "entry_id": self.config_entry.entry_id,
                    "config_entry": self.config_entry,
                },
                register_definitions=device_def,
            )
            
            # Füge das Gerät zum Hub hinzu
            self._devices[self.name] = device
            
            # Setup des Geräts
            if not await device.async_setup():
                _LOGGER.error("Fehler beim Setup des Geräts", extra={"hub": self.name})
                return False

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
            if not self._client or not self._client.connected:
                if not await self._client.connect():
                    _LOGGER.error(
                        "Keine Verbindung zum Modbus Gerät",
                        extra={
                            "device": device_name,
                            "address": address
                        }
                    )
                    return None

            slave_id = self.slave if self.slave is not None else 1
            
            async with self._lock:
                try:
                    if register_type == "input":
                        result = await self._client.read_input_registers(
                            address,
                            count,
                            slave=slave_id
                        )
                    else:
                        result = await self._client.read_holding_registers(
                            address,
                            count,
                            slave=slave_id
                        )
                    
                    if result and not result.isError():
                        return result.registers
                    
                    _LOGGER.error(
                        "Modbus Lesefehler",
                        extra={
                            "device": device_name,
                            "address": address,
                            "error": str(result) if result else "Keine Antwort"
                        }
                    )
                    return None
                    
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Lesen des Registers",
                        extra={
                            "error": str(e),
                            "device": device_name,
                            "address": address,
                            "register_type": register_type
                        }
                    )
                    return None

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Zugriff auf den Modbus Client",
                extra={
                    "error": str(e),
                    "device": device_name,
                    "address": address
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
            if not self._client or not self._client.connected:
                if not await self._client.connect():
                    _LOGGER.error(
                        "Keine Verbindung zum Modbus Gerät",
                        extra={
                            "device": device_name,
                            "address": address,
                            "value": value
                        }
                    )
                    return False

            scaled_value = int(value / scale) if scale != 1 else value
            slave_id = self.slave if self.slave is not None else 1
            
            async with self._lock:
                result = await self._client.write_register(
                    address,
                    scaled_value,
                    slave=slave_id
                )
                
                if result and not result.isError():
                    return True
                
                _LOGGER.error(
                    "Modbus Schreibfehler",
                    extra={
                        "device": device_name,
                        "address": address,
                        "value": value,
                        "error": str(result) if result else "Keine Antwort"
                    }
                )
                return False

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Schreiben des Registers",
                extra={
                    "error": str(e),
                    "device": device_name,
                    "address": address,
                    "value": value
                }
            )
            return False

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

    def _decode_string(self, registers: List[int]) -> str:
        """Dekodiert eine Liste von Registern als String."""
        try:
            # Konvertiere die Register in Bytes
            bytes_data = bytearray()
            for register in registers:
                bytes_data.extend(register.to_bytes(2, byteorder='big'))
            
            # Entferne Nullbytes und 0xFF Bytes am Ende
            while bytes_data and bytes_data[-1] in (0x00, 0xFF):
                bytes_data.pop()
            
            # Wenn alle Bytes 0xFF sind, gib einen leeren String zurück
            if all(b == 0xFF for b in bytes_data):
                return ""
            
            # Dekodiere die Bytes als UTF-8 String
            return bytes_data.decode('utf-8', errors='replace')
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Dekodieren des Strings",
                extra={
                    "error": str(e),
                    "registers": registers,
                    "hub": self.name
                }
            )
            return ""

    def _decode_uint32(self, registers: List[int]) -> int:
        """Dekodiert zwei Register als unsigned 32-bit Integer."""
        try:
            if len(registers) < 2:
                raise ValueError("Mindestens zwei Register erforderlich")
            
            # Kombiniere die Register
            return (registers[0] << 16) | registers[1]
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Dekodieren des uint32",
                extra={
                    "error": str(e),
                    "registers": registers,
                    "hub": self.name
                }
            )
            return 0

    def _decode_int32(self, registers: List[int]) -> int:
        """Dekodiert zwei Register als signed 32-bit Integer."""
        try:
            if len(registers) < 2:
                raise ValueError("Mindestens zwei Register erforderlich")
            
            # Kombiniere die Register
            value = (registers[0] << 16) | registers[1]
            
            # Konvertiere zu signed int wenn nötig
            if value & 0x80000000:
                value -= 0x100000000
                
            return value
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Dekodieren des int32",
                extra={
                    "error": str(e),
                    "registers": registers,
                    "hub": self.name
                }
            )
            return 0
