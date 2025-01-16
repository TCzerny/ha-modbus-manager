"""Modbus Manager Service Handling."""
from __future__ import annotations

from typing import Dict, Any, Optional, List, Callable
import asyncio
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_NAME,
    CONF_TYPE,
    CONF_MINIMUM,
    CONF_MAXIMUM,
    CONF_UNIT_OF_MEASUREMENT,
)

from .logger import ModbusManagerLogger
from .device_base import ModbusManagerDeviceBase
from .const import DOMAIN, NameType
from .helpers import EntityNameHelper

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerServiceHandler:
    """Klasse für die Verwaltung von Modbus-Services."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: ModbusManagerDeviceBase,
    ) -> None:
        """Initialisiert den Service Handler."""
        try:
            self._hass = hass
            self._device = device
            self._services: Dict[str, Dict[str, Any]] = {}
            self._service_handlers: Dict[str, Callable] = {}
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Initialisierung des Service Handlers",
                extra={
                    "error": str(e),
                    "device": device.name,
                    "traceback": e.__traceback__
                }
            )
            raise

    async def setup_services(self, service_definitions: Dict[str, Any]) -> None:
        """Richtet die Services basierend auf der Konfiguration ein."""
        try:
            # Hole die Service-Definitionen
            services = service_definitions.get("services", {})
            
            # Verarbeite die Services
            for service_id, service_config in services.items():
                try:
                    # Validiere die Service-Konfiguration
                    if not self._validate_service_config(service_id, service_config):
                        continue
                        
                    # Erstelle den Service-Handler
                    handler = await self._create_service_handler(service_id, service_config)
                    if handler:
                        # Registriere den Service
                        service_name = self._device.name_helper.convert(service_id, NameType.SERVICE_NAME)
                        self._hass.services.async_register(
                            DOMAIN,
                            service_name,
                            handler,
                            schema=self._create_service_schema(service_config)
                        )
                        
                        # Speichere die Service-Konfiguration
                        self._services[service_id] = service_config
                        
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Einrichten eines Services",
                        extra={
                            "error": str(e),
                            "service_id": service_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup der Services",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    def _validate_service_config(self, service_id: str, service_config: Dict[str, Any]) -> bool:
        """Validiert eine Service-Konfiguration."""
        try:
            # Prüfe ob alle erforderlichen Felder vorhanden sind
            required_fields = ["name", "register", "type"]
            for field in required_fields:
                if field not in service_config:
                    _LOGGER.error(
                        f"Pflichtfeld {field} fehlt in der Service-Konfiguration",
                        extra={
                            "service_id": service_id,
                            "device": self._device.name
                        }
                    )
                    return False
                    
            # Prüfe den Service-Typ
            service_type = service_config["type"]
            if service_type not in ["number", "select", "button"]:
                _LOGGER.error(
                    "Ungültiger Service-Typ",
                    extra={
                        "type": service_type,
                        "service_id": service_id,
                        "device": self._device.name
                    }
                )
                return False
                
            # Prüfe typ-spezifische Felder
            if service_type == "number":
                if "minimum" not in service_config or "maximum" not in service_config:
                    _LOGGER.error(
                        "Minimum und Maximum müssen für Number-Services definiert sein",
                        extra={
                            "service_id": service_id,
                            "device": self._device.name
                        }
                    )
                    return False
                    
            elif service_type == "select":
                if "options" not in service_config:
                    _LOGGER.error(
                        "Options müssen für Select-Services definiert sein",
                        extra={
                            "service_id": service_id,
                            "device": self._device.name
                        }
                    )
                    return False
                    
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Validierung der Service-Konfiguration",
                extra={
                    "error": str(e),
                    "service_id": service_id,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    def _create_service_schema(self, service_config: Dict[str, Any]) -> vol.Schema:
        """Erstellt das Schema für einen Service."""
        try:
            schema = {}
            
            # Basis-Schema für alle Service-Typen
            schema[vol.Required("value")] = self._get_value_schema(service_config)
            
            return vol.Schema(schema)
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen des Service-Schemas",
                extra={
                    "error": str(e),
                    "config": service_config,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return vol.Schema({})

    def _get_value_schema(self, service_config: Dict[str, Any]) -> Any:
        """Erstellt das Schema für den Wert-Parameter eines Services."""
        try:
            service_type = service_config["type"]
            
            if service_type == "number":
                return vol.All(
                    vol.Coerce(float),
                    vol.Range(
                        min=float(service_config["minimum"]),
                        max=float(service_config["maximum"])
                    )
                )
                
            elif service_type == "select":
                return vol.In(service_config["options"])
                
            elif service_type == "button":
                return vol.Coerce(bool)
                
            else:
                return vol.Coerce(str)
                
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen des Wert-Schemas",
                extra={
                    "error": str(e),
                    "config": service_config,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return vol.Coerce(str)

    async def _create_service_handler(self, service_id: str, service_config: Dict[str, Any]) -> Optional[Callable]:
        """Erstellt einen Handler für einen Service."""
        try:
            async def service_handler(call: ServiceCall) -> None:
                """Handler für den Service."""
                try:
                    # Hole den Wert aus dem Service-Call
                    value = call.data.get("value")
                    if value is None:
                        _LOGGER.error(
                            "Kein Wert im Service-Call",
                            extra={
                                "service_id": service_id,
                                "device": self._device.name
                            }
                        )
                        return
                        
                    # Führe die Service-Aktion aus
                    await self._execute_service_action(service_id, service_config, value)
                    
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Ausführung des Services",
                        extra={
                            "error": str(e),
                            "service_id": service_id,
                            "value": value,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
            return service_handler
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen des Service-Handlers",
                extra={
                    "error": str(e),
                    "service_id": service_id,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def _execute_service_action(self, service_id: str, service_config: Dict[str, Any], value: Any) -> None:
        """Führt die Aktion eines Services aus."""
        try:
            # Hole das Register
            register_name = service_config["register"]
            if not register_name:
                _LOGGER.error(
                    "Kein Register für Service definiert",
                    extra={
                        "service_id": service_id,
                        "device": self._device.name
                    }
                )
                return
                
            # Konvertiere den Register-Namen
            prefixed_name = self._device.name_helper.convert(register_name, NameType.BASE_NAME)
            
            # Validiere den Wert
            if not self._validate_service_value(service_config, value):
                return
                
            # Schreibe den Wert in das Register
            try:
                await self._device._hub.async_write_register(prefixed_name, value)
                _LOGGER.debug(
                    "Service-Aktion erfolgreich ausgeführt",
                    extra={
                        "service_id": service_id,
                        "register": register_name,
                        "value": value,
                        "device": self._device.name
                    }
                )
                
            except Exception as e:
                _LOGGER.error(
                    "Fehler beim Schreiben des Register-Werts",
                    extra={
                        "error": str(e),
                        "service_id": service_id,
                        "register": register_name,
                        "value": value,
                        "device": self._device.name,
                        "traceback": e.__traceback__
                    }
                )
                
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Ausführung der Service-Aktion",
                extra={
                    "error": str(e),
                    "service_id": service_id,
                    "value": value,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    def _validate_service_value(self, service_config: Dict[str, Any], value: Any) -> bool:
        """Validiert den Wert für einen Service."""
        try:
            service_type = service_config["type"]
            
            if service_type == "number":
                try:
                    value = float(value)
                    minimum = float(service_config["minimum"])
                    maximum = float(service_config["maximum"])
                    
                    if value < minimum or value > maximum:
                        _LOGGER.error(
                            "Wert außerhalb des gültigen Bereichs",
                            extra={
                                "value": value,
                                "minimum": minimum,
                                "maximum": maximum,
                                "device": self._device.name
                            }
                        )
                        return False
                        
                except (ValueError, TypeError) as e:
                    _LOGGER.error(
                        "Ungültiger Zahlenwert",
                        extra={
                            "error": str(e),
                            "value": value,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    return False
                    
            elif service_type == "select":
                if value not in service_config["options"]:
                    _LOGGER.error(
                        "Ungültige Option",
                        extra={
                            "value": value,
                            "options": service_config["options"],
                            "device": self._device.name
                        }
                    )
                    return False
                    
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Validierung des Service-Werts",
                extra={
                    "error": str(e),
                    "value": value,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    def get_service_config(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Gibt die Konfiguration eines Services zurück."""
        return self._services.get(service_id) 