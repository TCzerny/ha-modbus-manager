"""Modbus Manager Service Handling."""
from __future__ import annotations

import logging
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
from .const import DOMAIN, NameType, CONF_SERVICES, CONF_REGISTER, CONF_MIN, CONF_MAX, CONF_STEP, CONF_OPTIONS, SERVICE_TYPE_NUMBER, SERVICE_TYPE_SELECT, SERVICE_TYPE_BUTTON
from .device_interfaces import IModbusManagerDevice, IModbusManagerServiceProvider

_LOGGER = logging.getLogger(__name__)

class ModbusManagerServiceHandler(IModbusManagerServiceProvider):
    """Handler für ModbusManager Services."""

    def __init__(self, device: IModbusManagerDevice) -> None:
        """Initialisiere den Service Handler."""
        self._device = device
        self._services: Dict[str, Dict[str, Any]] = {}
        self._service_handlers: Dict[str, Any] = {}

    async def setup_services(self, service_configs: list[dict]) -> bool:
        """Richte die Services ein."""
        try:
            for service_config in service_configs:
                service_name = service_config.get(CONF_NAME)
                if not service_name:
                    _LOGGER.error("Service ohne Namen gefunden")
                    continue

                if not self._validate_service_config(service_config):
                    continue

                self._services[service_name] = service_config
                
                # Erstelle Service Handler
                handler = self._create_service_handler(service_name, service_config)
                if handler:
                    self._service_handlers[service_name] = handler
                    _LOGGER.debug(
                        "Service Handler erstellt für %s",
                        service_name
                    )

            return True
        except Exception as ex:
            _LOGGER.error(
                "Fehler beim Setup der Services: %s",
                str(ex),
                exc_info=True
            )
            return False

    def _validate_service_config(self, config: dict) -> bool:
        """Validiere die Service-Konfiguration."""
        required_fields = [CONF_NAME, CONF_TYPE, CONF_REGISTER]
        for field in required_fields:
            if field not in config:
                _LOGGER.error(
                    "Pflichtfeld %s fehlt in Service-Konfiguration",
                    field
                )
                return False

        service_type = config[CONF_TYPE]
        if service_type not in [SERVICE_TYPE_NUMBER, SERVICE_TYPE_SELECT, SERVICE_TYPE_BUTTON]:
            _LOGGER.error(
                "Ungültiger Service-Typ: %s",
                service_type
            )
            return False

        return True

    def _create_service_handler(self, service_name: str, config: dict) -> Optional[Any]:
        """Erstelle einen Service Handler."""
        try:
            async def service_handler(call: ServiceCall) -> None:
                """Handle den Service Call."""
                try:
                    value = call.data.get("value")
                    if value is None and config[CONF_TYPE] != SERVICE_TYPE_BUTTON:
                        _LOGGER.error(
                            "Kein Wert für Service %s angegeben",
                            service_name
                        )
                        return

                    if not self._validate_service_value(config, value):
                        return

                    await self._execute_service_action(config, value)
                except Exception as ex:
                    _LOGGER.error(
                        "Fehler bei Service Ausführung %s: %s",
                        service_name,
                        str(ex),
                        exc_info=True
                    )

            return service_handler
        except Exception as ex:
            _LOGGER.error(
                "Fehler beim Erstellen des Service Handlers %s: %s",
                service_name,
                str(ex),
                exc_info=True
            )
            return None

    def _validate_service_value(self, config: dict, value: Any) -> bool:
        """Validiere den Service-Wert."""
        service_type = config[CONF_TYPE]

        if service_type == SERVICE_TYPE_NUMBER:
            try:
                value = float(value)
                min_val = float(config.get(CONF_MIN, float("-inf")))
                max_val = float(config.get(CONF_MAX, float("inf")))
                
                if not min_val <= value <= max_val:
                    _LOGGER.error(
                        "Wert %s außerhalb des gültigen Bereichs [%s, %s]",
                        value, min_val, max_val
                    )
                    return False
            except ValueError:
                _LOGGER.error("Ungültiger numerischer Wert: %s", value)
                return False

        elif service_type == SERVICE_TYPE_SELECT:
            options = config.get(CONF_OPTIONS, [])
            if value not in options:
                _LOGGER.error(
                    "Ungültige Option %s. Erlaubte Optionen: %s",
                    value, options
                )
                return False

        return True

    async def _execute_service_action(self, config: dict, value: Any) -> None:
        """Führe die Service-Aktion aus."""
        register = config[CONF_REGISTER]
        success = self._device.write_register(register, value)
        
        if success:
            _LOGGER.debug(
                "Wert %s erfolgreich in Register %s geschrieben",
                value, register
            )
        else:
            _LOGGER.error(
                "Fehler beim Schreiben von %s in Register %s",
                value, register
            )

    def get_service_config(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Gibt die Konfiguration eines Services zurück."""
        return self._services.get(service_name) 