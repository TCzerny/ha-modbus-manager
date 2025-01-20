"""ModbusManager Input Entities."""
from __future__ import annotations

<<<<<<< HEAD
from typing import Any, Dict, Final

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import NameType
=======
import logging
from typing import Any, Dict, Optional

from homeassistant.components.input_number import InputNumber
from homeassistant.components.input_select import InputSelect
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NameType
>>>>>>> task/name_helpers_2025-01-16_1
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

<<<<<<< HEAD
class ModbusManagerInputNumber(CoordinatorEntity, NumberEntity):
=======
class ModbusManagerInputNumber(NumberEntity):
>>>>>>> task/name_helpers_2025-01-16_1
    """Input Number Entity für Modbus Register."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
<<<<<<< HEAD
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the input number."""
        super().__init__(coordinator)
        
        self._device = device
        self._config = config
=======
        register_config: Dict[str, Any],
    ) -> None:
        """Initialize the input number."""
        self._device = device
        self._config = config
        self._register = register_config
>>>>>>> task/name_helpers_2025-01-16_1
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
<<<<<<< HEAD
        self.entity_id = device.name_helper.convert(name, NameType.ENTITY_ID, domain="number")
=======
>>>>>>> task/name_helpers_2025-01-16_1
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
<<<<<<< HEAD
        # Number spezifische Eigenschaften
=======
        # Number-Eigenschaften
>>>>>>> task/name_helpers_2025-01-16_1
        self._attr_native_min_value = float(config.get("min", 0))
        self._attr_native_max_value = float(config.get("max", 100))
        self._attr_native_step = float(config.get("step", 1))
        self._attr_mode = NumberMode.BOX
        
<<<<<<< HEAD
        if "device_class" in config:
            self._attr_device_class = config["device_class"]
        if "unit_of_measurement" in config:
            self._attr_native_unit_of_measurement = config["unit_of_measurement"]
            
=======
        # Skalierung für Register
        self._scale = register_config.get("scale", 1)
        
>>>>>>> task/name_helpers_2025-01-16_1
        _LOGGER.debug(
            "Input Number Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
<<<<<<< HEAD
                "entity_id": self.entity_id,
                "attributes": {
                    "min": self._attr_native_min_value,
                    "max": self._attr_native_max_value,
                    "step": self._attr_native_step,
                    "device_class": self._attr_device_class,
                    "unit": self._attr_native_unit_of_measurement
                },
=======
                "min": self._attr_native_min_value,
                "max": self._attr_native_max_value,
                "step": self._attr_native_step,
                "scale": self._scale,
>>>>>>> task/name_helpers_2025-01-16_1
                "device": device.name
            }
        )

<<<<<<< HEAD
    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not self.coordinator.data:
            return None
            
        device_data = self.coordinator.data.get(self._device.name, {})
        value = device_data.get(self._name)
        
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
                
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        try:
            if "register" in self._config:
                register = self._config["register"]
                
                _LOGGER.debug(
                    "Setze Input Number Wert",
                    extra={
                        "device": self._device.name,
                        "entity_id": self.entity_id,
                        "register": register,
                        "value": value
                    }
                )
                
                await self._device.async_write_register(register, value)
                await self.coordinator.async_request_refresh()
                
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setzen des Werts",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "entity_id": self.entity_id,
                    "value": value,
=======
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
>>>>>>> task/name_helpers_2025-01-16_1
                    "traceback": e.__traceback__
                }
            )

<<<<<<< HEAD
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None


class ModbusManagerInputSelect(CoordinatorEntity, SelectEntity):
=======
class ModbusManagerInputSelect(SelectEntity):
>>>>>>> task/name_helpers_2025-01-16_1
    """Input Select Entity für Modbus Register."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
<<<<<<< HEAD
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the input select."""
        super().__init__(coordinator)
        
        self._device = device
        self._config = config
=======
        register_config: Dict[str, Any],
    ) -> None:
        """Initialize the input select."""
        self._device = device
        self._config = config
        self._register = register_config
>>>>>>> task/name_helpers_2025-01-16_1
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
<<<<<<< HEAD
        self.entity_id = device.name_helper.convert(name, NameType.ENTITY_ID, domain="select")
=======
>>>>>>> task/name_helpers_2025-01-16_1
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
<<<<<<< HEAD
        # Select spezifische Eigenschaften
        self._attr_options = config.get("options", [])
        self._options_map = config.get("options_map", {})
        self._attr_current_option = None
=======
        # Select-Eigenschaften
        self._attr_options = config.get("options", [])
        self._options_map = register_config.get("options", {})
        self._attr_current_option = self._attr_options[0] if self._attr_options else None
>>>>>>> task/name_helpers_2025-01-16_1
        
        _LOGGER.debug(
            "Input Select Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
<<<<<<< HEAD
                "entity_id": self.entity_id,
                "options": self._attr_options,
                "options_map": self._options_map,
=======
                "options": self._attr_options,
                "options_map": self._options_map,
                "current_option": self._attr_current_option,
>>>>>>> task/name_helpers_2025-01-16_1
                "device": device.name
            }
        )

<<<<<<< HEAD
    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        if not self.coordinator.data:
            return None
            
        device_data = self.coordinator.data.get(self._device.name, {})
        value = device_data.get(self._name)
        
        if value is not None:
            # Suche nach dem passenden Option-Text für den Wert
            for option, option_value in self._options_map.items():
                if option_value == value:
                    return option
                    
        return None

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        try:
            if "register" in self._config and option in self._options_map:
                register = self._config["register"]
                value = self._options_map[option]
                
                _LOGGER.debug(
                    "Setze Input Select Option",
                    extra={
                        "device": self._device.name,
                        "entity_id": self.entity_id,
                        "register": register,
                        "option": option,
                        "value": value
                    }
                )
                
                await self._device.async_write_register(register, value)
                await self.coordinator.async_request_refresh()
                
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setzen der Option",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "entity_id": self.entity_id,
                    "option": option,
                    "traceback": e.__traceback__
                }
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None 
=======
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
>>>>>>> task/name_helpers_2025-01-16_1
