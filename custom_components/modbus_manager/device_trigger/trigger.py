"""ModbusManager Device Triggers."""
from __future__ import annotations

from typing import Any

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_ENTITY_ID,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from ..const import DOMAIN

__all__ = [
    "TRIGGER_SCHEMA",
    "async_validate_trigger_config",
    "async_get_triggers",
    "async_attach_trigger",
]

# Schema für die Trigger-Konfiguration
TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "device",
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional("above"): vol.Coerce(float),
        vol.Optional("below"): vol.Coerce(float),
    }
)

async def async_validate_trigger_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    return TRIGGER_SCHEMA(config)

async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """Liste der verfügbaren Trigger für ein Gerät."""
    triggers = []
    
    # Hole die Trigger aus dem Device Registry
    if DOMAIN in hass.data and "device_triggers" in hass.data[DOMAIN]:
        device_triggers = hass.data[DOMAIN]["device_triggers"].get(device_id, [])
        for trigger in device_triggers:
            trigger_data = {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: trigger["id"],
                CONF_ENTITY_ID: trigger["entity_id"],
                "name": trigger["name"],  # Verwende den Namen direkt aus der YAML-Definition
                "metadata": {},  # Optional: Zusätzliche Metadaten für die UI
            }
            
            # Füge optionale Parameter hinzu
            if "above" in trigger:
                trigger_data["above"] = trigger["above"]
            if "below" in trigger:
                trigger_data["below"] = trigger["below"]
                
            triggers.append(trigger_data)
    
    return triggers

async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trigger_type = config[CONF_TYPE]
    entity_id = config[CONF_ENTITY_ID]
        
    from homeassistant.helpers.event import async_track_state_change_event
    
    def _check_trigger(state, above=None, below=None):
        """Überprüfe ob der Trigger ausgelöst werden soll."""
        if state is None or state.state in ("unknown", "unavailable"):
            return False
            
        try:
            value = float(state.state)
            
            if above is not None and value <= above:
                return False
            if below is not None and value >= below:
                return False
                
            return True
            
        except (ValueError, TypeError):
            return False
    
    async def _state_changed_listener(event):
        """Handle state changes."""
        new_state = event.data.get("new_state")
        if _check_trigger(
            new_state,
            config.get("above"),
            config.get("below")
        ):
            await action({
                "platform": "device",
                "domain": DOMAIN,
                "device_id": config[CONF_DEVICE_ID],
                "type": trigger_type,
                "entity_id": entity_id,
                "description": f"State changed for {entity_id}",
            })
    
    return async_track_state_change_event(hass, [entity_id], _state_changed_listener) 