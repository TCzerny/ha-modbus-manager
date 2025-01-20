"""ModbusManager Button Platform."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, NameType
from .device_base import ModbusManagerDeviceBase as ModbusManagerDevice
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Richte die ModbusManager Button Entities ein."""
    return await setup_platform_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        entity_types=[ModbusManagerButton],
        platform_name="Button"
    )


class ModbusManagerButton(CoordinatorEntity, ButtonEntity):
    """ModbusManager Button Entity."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        
        self._device = device
        self._config = config
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
        self.entity_id = device.name_helper.convert(name, NameType.ENTITY_ID, domain="button")
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
        # Button spezifische Eigenschaften
        if "device_class" in config:
            self._attr_device_class = config["device_class"]
            
        _LOGGER.debug(
            "Button Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
                "entity_id": self.entity_id,
                "device_class": self._attr_device_class,
                "device": device.name
            }
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            if "register" in self._config:
                register = self._config["register"]
                value = self._config.get("value", 1)
                
                _LOGGER.debug(
                    "Button gedrückt",
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
                "Fehler beim Button-Press",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "entity_id": self.entity_id,
                    "traceback": e.__traceback__
                }
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None 