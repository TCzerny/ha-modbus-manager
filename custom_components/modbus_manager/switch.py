"""Switch platform for Modbus Manager."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .modbus_hub import ModbusManagerHub
from .device import ModbusManagerDevice

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Switch platform."""
    hub: ModbusManagerHub = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Erstelle die Schreibsperre-Entity für jedes Gerät
    for device in hub._devices.values():
        if isinstance(device, ModbusManagerDevice):
            # Verwende den Gerätenamen aus der Config Entry
            device_name = config_entry.title
            
            # Erstelle den Switch mit Gerätenamen als Präfix
            entities.append(
                ModbusManagerWriteLockSwitch(
                    hub=hub,
                    entry_id=config_entry.entry_id,
                    device_name=device_name,
                    unique_id=f"{config_entry.entry_id}_write_lock",
                    name=f"{device_name} Write Lock"
                )
            )
            
            # Füge alle gerätespezifischen Switches hinzu
            for entity in device.entities.values():
                if hasattr(entity, 'entity_id') and entity.entity_id and "switch" in entity.entity_id:
                    entities.append(entity)
    
    if entities:
        _LOGGER.debug(
            "Adding switch entities",
            extra={
                "count": len(entities),
                "entities": [e.entity_id for e in entities if hasattr(e, 'entity_id')]
            }
        )
    
    async_add_entities(entities)

class ModbusManagerWriteLockSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Modbus Manager Write Lock Switch."""

    def __init__(
        self,
        hub: ModbusManagerHub,
        entry_id: str,
        device_name: str,
        unique_id: str,
        name: str,
    ) -> None:
        """Initialize the switch."""
        self._hub = hub
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_is_on = False  # Default disabled
        self._attr_should_poll = False
        self._attr_icon = "mdi:lock"  # Lock icon
        
        # Link the switch to the specific device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device_name,
            manufacturer="Modbus Manager",
            model="Modbus Device",
            via_device=(DOMAIN, entry_id),  # Link to the hub
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        self.async_write_ha_state() 