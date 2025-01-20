"""ModbusManager Switch Platform."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, NameType
from .device_base import ModbusManagerDeviceBase as ModbusManagerDevice
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Richte die ModbusManager Switch Entities ein."""
    return await setup_platform_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        entity_types=[ModbusManagerSwitch],
        platform_name="Switch"
    )

class ModbusManagerSwitch(CoordinatorEntity, SwitchEntity):
    """ModbusManager Switch Entity."""

    def __init__(
        self,
        device,
        name: str,
        config: Dict[str, Any],
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        
        self._device = device
        self._config = config
        
        # Verwende name_helper für eindeutige Namen
        self._name = device.name_helper.convert(name, NameType.BASE_NAME)
        self._attr_name = device.name_helper.convert(name, NameType.DISPLAY_NAME)
        self._attr_unique_id = device.name_helper.convert(name, NameType.UNIQUE_ID)
        self.entity_id = device.name_helper.convert(name, NameType.ENTITY_ID, domain="switch")
        
        # Entity-Eigenschaften
        self._attr_device_info = device.device_info
        
        # Switch spezifische Eigenschaften
        if "device_class" in config:
            self._attr_device_class = config["device_class"]
            
        _LOGGER.debug(
            "Switch Entity initialisiert",
            extra={
                "name": self._name,
                "display_name": self._attr_name,
                "unique_id": self._attr_unique_id,
                "entity_id": self.entity_id,
                "device_class": self._attr_device_class,
                "device": device.name
            }
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if not self.coordinator.data:
            return None
            
        device_data = self.coordinator.data.get(self._device.name, {})
        return bool(device_data.get(self._name, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            if "register" in self._config:
                register = self._config["register"]
                value = self._config.get("on_value", 1)
                
                _LOGGER.debug(
                    "Schalte Switch ein",
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
                "Fehler beim Einschalten",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "entity_id": self.entity_id,
                    "traceback": e.__traceback__
                }
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            if "register" in self._config:
                register = self._config["register"]
                value = self._config.get("off_value", 0)
                
                _LOGGER.debug(
                    "Schalte Switch aus",
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
                "Fehler beim Ausschalten",
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