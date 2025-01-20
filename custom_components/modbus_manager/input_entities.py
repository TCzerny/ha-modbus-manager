"""ModbusManager Input Entities."""
from __future__ import annotations

from typing import Any, Dict, Final

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import NameType
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerInputNumber(CoordinatorEntity, NumberEntity):
    """Input Number Entity für Modbus Register."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the input number."""
        super().__init__(coordinator)
        
        self._device = device
        self._config = config
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
        self.entity_id = device.name_helper.convert(name, NameType.ENTITY_ID, domain="number")
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
        # Number spezifische Eigenschaften
        self._attr_native_min_value = float(config.get("min", 0))
        self._attr_native_max_value = float(config.get("max", 100))
        self._attr_native_step = float(config.get("step", 1))
        self._attr_mode = NumberMode.BOX
        
        if "device_class" in config:
            self._attr_device_class = config["device_class"]
        if "unit_of_measurement" in config:
            self._attr_native_unit_of_measurement = config["unit_of_measurement"]
            
        _LOGGER.debug(
            "Input Number Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
                "entity_id": self.entity_id,
                "attributes": {
                    "min": self._attr_native_min_value,
                    "max": self._attr_native_max_value,
                    "step": self._attr_native_step,
                    "device_class": self._attr_device_class,
                    "unit": self._attr_native_unit_of_measurement
                },
                "device": device.name
            }
        )

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
                    "traceback": e.__traceback__
                }
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None


class ModbusManagerInputSelect(CoordinatorEntity, SelectEntity):
    """Input Select Entity für Modbus Register."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the input select."""
        super().__init__(coordinator)
        
        self._device = device
        self._config = config
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
        self.entity_id = device.name_helper.convert(name, NameType.ENTITY_ID, domain="select")
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
        # Select spezifische Eigenschaften
        self._attr_options = config.get("options", [])
        self._options_map = config.get("options_map", {})
        self._attr_current_option = None
        
        _LOGGER.debug(
            "Input Select Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
                "entity_id": self.entity_id,
                "options": self._attr_options,
                "options_map": self._options_map,
                "device": device.name
            }
        )

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