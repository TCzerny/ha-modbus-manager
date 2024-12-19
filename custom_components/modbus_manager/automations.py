"""ModbusManager Automation Platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.automation import AutomationEntity
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

class ModbusManagerAutomation(AutomationEntity):
    """Repräsentiert eine ModbusManager Automation."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_name: str,
        automation_id: str,
        config: dict,
        device_info: DeviceInfo
    ) -> None:
        """Initialisiere die Automation."""
        super().__init__()
        
        self.hass = hass
        self._device_name = device_name
        self._automation_id = automation_id
        self._config = config
        self._device_info = device_info
        self._attr_unique_id = f"{device_name}_{automation_id}"
        self._attr_name = config.get("name", automation_id)
        
        # Setze die Automation-Konfiguration
        self._trigger = config.get("trigger", [])
        self._condition = config.get("condition", [])
        self._action = config.get("action", [])

    @property
    def device_info(self) -> DeviceInfo:
        """Gibt die Geräteinformationen zurück."""
        return self._device_info

    @property
    def unique_id(self) -> str:
        """Gibt die eindeutige ID zurück."""
        return self._attr_unique_id

    @property
    def name(self) -> str:
        """Gibt den Namen zurück."""
        return self._attr_name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Aktiviert die Automation."""
        await super().async_turn_on(**kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deaktiviert die Automation."""
        await super().async_turn_off(**kwargs)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die ModbusManager Automationen basierend auf einem ConfigEntry ein."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for device in hub.devices.values():
        if "automation" in device._device_config:
            for automation in device._device_config["automation"]:
                entities.append(
                    ModbusManagerAutomation(
                        hass=hass,
                        device_name=device.name,
                        automation_id=automation["id"],
                        config=automation,
                        device_info=device.device_info
                    )
                )
    
    if entities:
        async_add_entities(entities) 