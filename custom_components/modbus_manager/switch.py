"""Modbus Manager Switch Platform."""
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .modbus_hub import ModbusManagerHub
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the switch platform."""
    hub = hass.data[DOMAIN][entry.entry_id]
    device = hub.device
    
    if not device:
        _LOGGER.error("Kein Gerät verfügbar für Switch-Setup")
        return

    entity_configs = device.get_entity_configs()
    
    if not entity_configs:
        _LOGGER.warning("Keine Entity-Konfigurationen gefunden")
        return

    # Erstelle einen Coordinator für die Switches
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{hub.name} Data",
        update_method=lambda: device.read_registers(),
        update_interval=timedelta(seconds=30),
    )

    # Führe erste Aktualisierung durch
    await coordinator.async_refresh()

    # Erstelle die Switch-Entities
    entities = []
    for entity_id, config in entity_configs.items():
        if config["register"].get("writeable", False):  # Nur schreibbare Register
            entities.append(
                ModbusManagerSwitch(
                    coordinator=coordinator,
                    hub=hub,
                    device=device,
                    entity_id=entity_id,
                    config=config
                )
            )

    async_add_entities(entities)

class ModbusManagerSwitch(CoordinatorEntity, SwitchEntity):
    """Modbus Manager Switch Entity."""

    def __init__(self, coordinator, hub, device, entity_id, config):
        """Initialize the switch."""
        super().__init__(coordinator)
        
        self.hub = hub
        self.device = device
        self._entity_id = entity_id
        self._config = config
        self._attr_name = config["name"]
        self._attr_unique_id = config["unique_id"]
        
        # Register-spezifische Konfiguration
        self._register = config["register"]
        self._register_name = self._register["name"]
        
        # Registriere die Entity beim Device
        self.device.register_entity(self._entity_id, self)
        
        _LOGGER.debug(
            "Switch initialisiert",
            extra={
                "entity_id": self._entity_id,
                "name": self._attr_name,
                "register": self._register_name
            }
        )

    @property
    def device_info(self):
        """Return device information."""
        return self.device.device_info

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self.coordinator.data is None:
            return None
            
        value = self.coordinator.data.get(self._register_name)
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.device.write_register(self._register_name, 1)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.device.write_register(self._register_name, 0)
        await self.coordinator.async_request_refresh()

    def update_value(self, value):
        """Update the switch value."""
        if value is not None:
            self._attr_is_on = bool(value)
            self.async_write_ha_state() 