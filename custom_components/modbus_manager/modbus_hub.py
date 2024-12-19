"""Modbus Manager Hub for managing Modbus connections."""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

import yaml
import asyncio
from pymodbus.client.tcp import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_FIRMWARE_VERSION
from .errors import ModbusDeviceError, handle_modbus_error
from .logger import ModbusManagerLogger
from .optimization import ModbusManagerOptimizer
from .proxy import ModbusManagerProxy
from .device import ModbusManagerDevice
from .firmware import FirmwareManager

import aiofiles

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerHub:
    """Class for managing Modbus connection for devices."""

    def __init__(self, name: str, host: str, port: int, slave: int, device_type: str, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the hub."""
        self.name = name
        self.host = host
        self.port = port
        self.slave = slave
        self.device_type = device_type
        self.hass = hass
        self.config_entry = config_entry
        self.device = None
        self._device_definition_cache: Dict[str, Dict[str, Any]] = {}
        self.coordinators: Dict[str, DataUpdateCoordinator] = {}
        self.firmware_manager = None

        self.client = AsyncModbusTcpClient(host=host, port=port)

        _LOGGER.debug("Initialisiere ModbusManagerDevice mit hass und config")
        try:
            # Definieren des config-Dictionary
            self.config = {
                "name": self.name,
                "host": self.host,
                "port": self.port,
                "slave": self.slave,
                "device_type": self.device_type,
                "entry_id": self.config_entry.entry_id
            }
            
            _LOGGER.debug("Hub config: %s", self.config)
            
            # Initialisiere den Proxy
            self.proxy = ModbusManagerProxy(
                client=self.client,
                slave=self.slave
            )
            _LOGGER.debug("ModbusManagerProxy erfolgreich initialisiert")
            
        except Exception as e:
            _LOGGER.error(f"Fehler bei der Initialisierung von ModbusManagerHub: {e}")
            raise

    async def async_setup(self) -> bool:
        """Set up the Modbus Manager Hub."""
        try:
            # Verbindung herstellen
            if not await self.client.connect():
                _LOGGER.error("Verbindung zum Modbus-Gerät fehlgeschlagen")
                return False

            # Lade die Gerätedefinition
            device_def = await self.get_device_definition(self.device_type)
            if not device_def:
                _LOGGER.error("Keine Gerätedefinition gefunden")
                return False

            # Initialisiere den FirmwareManager
            selected_version = self.config_entry.data.get(CONF_FIRMWARE_VERSION)
            self.firmware_manager = FirmwareManager(device_def, selected_version)
            
            # Initialisiere die Firmware-Version
            firmware_version = await self.firmware_manager.initialize(self)
            _LOGGER.info(f"Firmware-Version: {firmware_version}")

            # Aktualisiere die Register-Definitionen basierend auf der Firmware
            register_defs = self.firmware_manager.get_register_definitions()
            
            # Erstelle das Device mit den aktualisierten Definitionen
            self.device = ModbusManagerDevice(
                hub=self,
                device_type=self.device_type,
                config=self.config,
                register_definitions=register_defs
            )

            return await self.device.async_setup()

        except Exception as e:
            _LOGGER.error(f"Fehler beim Setup des Hubs: {e}")
            return False

    async def async_teardown(self):
        """Teardown method for the hub."""
        try:
            _LOGGER.debug("Starte Teardown für Hub %s", self.name)
            
            # Device Teardown
            if self.device:
                try:
                    await self.device.async_teardown()
                except Exception as e:
                    _LOGGER.error("Fehler beim Device Teardown: %s", str(e))
            
            # Modbus Client Teardown
            if hasattr(self, 'client') and self.client is not None:
                try:
                    if hasattr(self.client, 'connected') and self.client.connected:
                        try:
                            if hasattr(self.client, 'close'):
                                await self.client.close()
                            else:
                                self.client.connected = False
                        except Exception as e:
                            _LOGGER.error("Fehler beim Schließen der Modbus-Verbindung: %s", str(e))
                except Exception as e:
                    _LOGGER.error("Fehler beim Zugriff auf Modbus-Client-Attribute: %s", str(e))
                finally:
                    self.client = None
            
            _LOGGER.info("Modbus-Hub %s erfolgreich heruntergefahren", self.name)
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Hub Teardown",
                extra={
                    "error": str(e),
                    "hub": self.name
                }
            )

    async def get_device_definition(self, device_definition_name: str) -> Optional[Dict]:
        """Lade die Gerätedefinition aus dem Cache oder der Datei."""
        try:
            # Prüfe zuerst den Cache
            if device_definition_name in self._device_definition_cache:
                return self._device_definition_cache[device_definition_name]
                
            # Wenn nicht im Cache, lade aus Datei
            definition_path = Path(__file__).parent / "device_definitions" / f"{device_definition_name}.yaml"
            if not definition_path.exists():
                _LOGGER.error(f"Device definition file not found: {definition_path}")
                return None
                
            async with aiofiles.open(definition_path, "r", encoding="utf-8") as f:
                content = await f.read()
                definition = yaml.safe_load(content)
                
            # Cache the definition
            self._device_definition_cache[device_definition_name] = definition
            return definition
            
        except Exception as e:
            _LOGGER.error("Error loading device definition: %s", e)
            return None

    async def read_register(self, device_name: str, address: int, reg_type: str, count: int = 1, scale: float = 1, swap: Optional[str] = None, register_type: str = "holding") -> Any:
        """Liest ein einzelnes Register."""
        try:
            _LOGGER.debug(
                "Starte Modbus-Lesevorgang",
                extra={
                    "device": device_name,
                    "address": address,
                    "type": reg_type,
                    "count": count,
                    "scale": scale,
                    "swap": swap,
                    "register_type": register_type,
                    "connected": self.client.connected if self.client else False
                }
            )

            if not self.client:
                _LOGGER.error("Kein Modbus-Client verfügbar")
                return None

            if not self.client.connected:
                _LOGGER.debug("Verbinde mit Modbus-Gerät...")
                if not await self.client.connect():
                    _LOGGER.error(
                        "Verbindung zum Modbus-Gerät fehlgeschlagen",
                        extra={"host": self.host, "port": self.port}
                    )
                    return None
                _LOGGER.debug("Verbindung hergestellt")

            # Wähle die richtige Lesefunktion basierend auf dem Register-Typ
            try:
                if register_type == "holding":
                    response = await self.client.read_holding_registers(
                        address=address,
                        count=count,
                        slave=self.slave
                    )
                elif register_type == "input":
                    response = await self.client.read_input_registers(
                        address=address,
                        count=count,
                        slave=self.slave
                    )
                else:
                    _LOGGER.error(
                        f"Unbekannter Register-Typ: {register_type}",
                        extra={
                            "device": device_name,
                            "address": address
                        }
                    )
                    return None
                
                _LOGGER.debug(
                    "Modbus-Antwort erhalten",
                    extra={
                        "device": device_name,
                        "address": address,
                        "register_type": register_type,
                        "response": response,
                        "is_error": response.isError() if response else True
                    }
                )

                if response and not response.isError():
                    values = response.registers
                    _LOGGER.debug(
                        "Register erfolgreich gelesen",
                        extra={
                            "device": device_name,
                            "address": address,
                            "register_type": register_type,
                            "raw_values": values
                        }
                    )
                    return values
                else:
                    error_msg = str(response) if response else "Keine Antwort"
                    _LOGGER.error(
                        "Modbus-Fehler",
                        extra={
                            "device": device_name,
                            "address": address,
                            "register_type": register_type,
                            "error": error_msg
                        }
                    )
                    return None

            except Exception as e:
                _LOGGER.error(
                    "Fehler bei Modbus-Kommunikation",
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
                "Allgemeiner Fehler beim Lesen des Registers",
                extra={
                    "error": str(e),
                    "device": device_name,
                    "address": address,
                    "register_type": register_type
                }
            )
            return None

    async def write_register(self, device_name: str, address: int, value: Any, reg_type: str, scale: float = 1, swap: Optional[str] = None) -> bool:
        """Schreibt einen Wert in ein Register."""
        try:
            if not self.client.connected:
                await self.client.connect()

            # Skaliere den Wert
            if reg_type != "string":
                value = value / scale

            # Konvertiere den Wert in das richtige Format
            if reg_type == "uint16":
                register_value = int(value) & 0xFFFF
                values = [register_value]
            elif reg_type == "int16":
                register_value = int(value)
                if register_value < 0:
                    register_value += 65536
                values = [register_value]
            elif reg_type in ["uint32", "int32"]:
                register_value = int(value)
                if reg_type == "int32" and register_value < 0:
                    register_value += 4294967296
                if swap == "word":
                    values = [register_value & 0xFFFF, (register_value >> 16) & 0xFFFF]
                else:
                    values = [(register_value >> 16) & 0xFFFF, register_value & 0xFFFF]
            elif reg_type == "float":
                import struct
                float_bytes = struct.pack(">f", float(value))
                if swap == "word":
                    values = [
                        struct.unpack(">H", float_bytes[2:4])[0],
                        struct.unpack(">H", float_bytes[0:2])[0]
                    ]
                else:
                    values = [
                        struct.unpack(">H", float_bytes[0:2])[0],
                        struct.unpack(">H", float_bytes[2:4])[0]
                    ]
            elif reg_type == "string":
                # Konvertiere String in Register-Werte
                string_bytes = value.encode("ascii")
                values = []
                for i in range(0, len(string_bytes), 2):
                    if i + 1 < len(string_bytes):
                        values.append((string_bytes[i] << 8) + string_bytes[i + 1])
                    else:
                        values.append(string_bytes[i] << 8)
            else:
                _LOGGER.warning("Unbekannter Registertyp: %s", reg_type)
                return False

            # Schreibe die Register
            if len(values) == 1:
                response = await self.client.write_register(address, values[0], slave=self.slave)
            else:
                response = await self.client.write_registers(address, values, slave=self.slave)

            if response.isError():
                raise ModbusException(f"Fehler beim Schreiben des Registers {address}: {response}")

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Schreiben des Registers",
                extra={
                    "error": str(e),
                    "address": address,
                    "value": value,
                    "type": reg_type,
                    "device": device_name
                }
            )
            return False

    def get_firmware_version(self) -> str:
        """Get current firmware version."""
        if self.firmware_manager:
            return self.firmware_manager.get_version()
        return "unknown"

    def is_firmware_supported(self) -> bool:
        """Check if current firmware version is supported."""
        if self.firmware_manager:
            return self.firmware_manager.is_version_supported(self.firmware_manager.get_version())
        return False