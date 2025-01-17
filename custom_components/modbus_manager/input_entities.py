"""ModbusManager Input Entities."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NameType
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerInputNumber(NumberEntity):
    """Input Number Entity für Modbus Register."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
        register_config: Dict[str, Any],
    ) -> None:
        """Initialize the input number."""
        self._device = device
        self._config = config
        self._register = register_config
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
        # Number-Eigenschaften
        self._attr_native_min_value = float(config.get("min", 0))
        self._attr_native_max_value = float(config.get("max", 100))
        self._attr_native_step = float(config.get("step", 1))
        self._attr_mode = NumberMode.BOX
        
        # Skalierung für Register
        self._scale = register_config.get("scale", 1)
        
        _LOGGER.debug(
            "Input Number Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
                "min": self._attr_native_min_value,
                "max": self._attr_native_max_value,
                "step": self._attr_native_step,
                "scale": self._scale,
                "device": device.name
            }
        )

    async def async_set_native_value(self, value: float) -> None:
        """Setze den Wert der Entity und schreibe ihn ins Register."""
        try:
            # Skaliere den Wert für das Register
            register_value = value * self._scale
            
            # Hole den Register-Namen
            register_name = self._register.get("name")
            if not register_name:
                _LOGGER.error(
                    "Register hat keinen Namen",
                    extra={
                        "entity": self._name,
                        "device": self._device.name
                    }
                )
                return
                
            # Schreibe den Wert ins Register
            await self._device.async_write_register(register_name, register_value)
            
            # Aktualisiere den Entity-Zustand
            self._attr_native_value = value
            self.async_write_ha_state()
            
            _LOGGER.debug(
                "Input Number Wert gesetzt",
                extra={
                    "entity": self._name,
                    "value": value,
                    "register_value": register_value,
                    "device": self._device.name
                }
            )
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setzen des Input Number Werts",
                extra={
                    "error": str(e),
                    "entity": self._name,
                    "value": value,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

class ModbusManagerInputSelect(SelectEntity):
    """Input Select Entity für Modbus Register."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
        register_config: Dict[str, Any],
    ) -> None:
        """Initialize the input select."""
        self._device = device
        self._config = config
        self._register = register_config
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
        # Select-Eigenschaften
        self._attr_options = config.get("options", [])
        self._options_map = register_config.get("options", {})
        self._attr_current_option = self._attr_options[0] if self._attr_options else None
        
        _LOGGER.debug(
            "Input Select Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
                "options": self._attr_options,
                "options_map": self._options_map,
                "current_option": self._attr_current_option,
                "device": device.name
            }
        )

    async def async_select_option(self, option: str) -> None:
        """Setze die ausgewählte Option und schreibe den Wert ins Register."""
        try:
            if option not in self._attr_options:
                _LOGGER.error(
                    "Ungültige Option für Input Select",
                    extra={
                        "entity": self._name,
                        "option": option,
                        "valid_options": self._attr_options,
                        "device": self._device.name
                    }
                )
                return
                
            # Hole den Register-Wert aus dem Options-Mapping
            register_value = self._options_map.get(option)
            if register_value is None:
                _LOGGER.error(
                    "Keine Mapping-Definition für Option gefunden",
                    extra={
                        "entity": self._name,
                        "option": option,
                        "device": self._device.name
                    }
                )
                return
                
            # Hole den Register-Namen
            register_name = self._register.get("name")
            if not register_name:
                _LOGGER.error(
                    "Register hat keinen Namen",
                    extra={
                        "entity": self._name,
                        "device": self._device.name
                    }
                )
                return
                
            # Schreibe den Wert ins Register
            await self._device.async_write_register(register_name, register_value)
            
            # Aktualisiere den Entity-Zustand
            self._attr_current_option = option
            self.async_write_ha_state()
            
            _LOGGER.debug(
                "Input Select Option gesetzt",
                extra={
                    "entity": self._name,
                    "option": option,
                    "register_value": register_value,
                    "device": self._device.name
                }
            )
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setzen der Input Select Option",
                extra={
                    "error": str(e),
                    "entity": self._name,
                    "option": option,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            ) 