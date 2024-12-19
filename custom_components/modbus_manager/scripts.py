"""ModbusManager Script Platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.script import ScriptEntity
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

class ModbusManagerScript(ScriptEntity):
    """Repräsentiert ein ModbusManager Script."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_name: str,
        script_id: str,
        config: dict,
        device_info: DeviceInfo
    ) -> None:
        """Initialisiere das Script."""
        super().__init__()
        
        self.hass = hass
        self._device_name = device_name
        self._script_id = script_id
        self._config = config
        self._device_info = device_info
        self._attr_unique_id = f"{device_name}_{script_id}"
        self._attr_name = config.get("name", script_id)
        
        # Setze die Script-Konfiguration
        self._sequence = config.get("sequence", [])

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
        """Führt das Script aus."""
        await super().async_turn_on(**kwargs)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die ModbusManager Scripts basierend auf einem ConfigEntry ein."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for device in hub.devices.values():
        if "script" in device._device_config:
            for script_id, script_config in device._device_config["script"].items():
                entities.append(
                    ModbusManagerScript(
                        hass=hass,
                        device_name=device.name,
                        script_id=script_id,
                        config=script_config,
                        device_info=device.device_info
                    )
                )
    
    if entities:
        async_add_entities(entities) 