"""Modbus Manager Input Entity Classes."""
from __future__ import annotations

from typing import Any, Dict, Final

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

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
        
        # Entity-Eigenschaften
        self._attr_name = f"{device.name} {name}"
        self._attr_unique_id = f"{device.name}_{name}"
        self._attr_device_info = device.device_info
        
        # Number-Eigenschaften
        self._attr_native_min_value = float(config.get("min", 0))
        self._attr_native_max_value = float(config.get("max", 100))
        self._attr_native_step = float(config.get("step", 1))
        self._attr_mode = NumberMode.BOX
        
        # Skalierung für Register
        self._scale = register_config.get("scale", 1)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        # Skaliere den Wert für das Register
        register_value = int(value / self._scale) if self._scale != 1 else int(value)
        
        # Schreibe in das Register
        await self._device.async_write_register(
            self._register["name"],
            register_value
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
        
        # Entity-Eigenschaften
        self._attr_name = f"{device.name} {name}"
        self._attr_unique_id = f"{device.name}_{name}"
        self._attr_device_info = device.device_info
        
        # Select-Eigenschaften
        self._attr_options = config.get("options", [])
        self._options_map = register_config.get("options", {})
        self._attr_current_option = self._attr_options[0] if self._attr_options else None

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        # Wandle Option in Register-Wert um
        if option in self._options_map:
            register_value = self._options_map[option]
            await self._device.async_write_register(
                self._register["name"],
                register_value
            )
            self._attr_current_option = option 