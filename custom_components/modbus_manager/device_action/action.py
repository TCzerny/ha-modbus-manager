"""ModbusManager Device Actions."""
from __future__ import annotations

from typing import Any

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_TYPE,
    CONF_ENTITY_ID,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from ..const import DOMAIN

# Schema für die Action-Konfiguration
ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required("target"): {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
        },
        vol.Required("fields"): {
            vol.Optional("option"): cv.string,  # Für select Optionen
            vol.Optional("value"): vol.Coerce(float),  # Für numerische Werte
        },
    }
)

async def async_validate_action_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    return ACTION_SCHEMA(config)

async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """Liste der verfügbaren Actions für ein Gerät."""
    actions = []
    
    # Hole die Actions aus dem Device Registry
    if DOMAIN in hass.data and "device_actions" in hass.data[DOMAIN]:
        device_actions = hass.data[DOMAIN]["device_actions"].get(device_id, [])
        for action in device_actions:
            action_data = {
                "domain": DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: action["id"],
                "name": action["name"],  # Verwende den Namen direkt aus der YAML-Definition
                "target": action["target"],
                "fields": action["fields"]
            }
            actions.append(action_data)
    
    return actions

async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    action_type = config[CONF_TYPE]
    
    service_data = {
        "entity_id": config["target"]["entity_id"],
    }
    
    # Füge die entsprechenden Felder basierend auf dem Action-Typ hinzu
    if action_type == "set_battery_mode":
        service = "select.select_option"
        service_data["option"] = config["fields"]["option"]
    else:
        service = "number.set_value"
        service_data["value"] = config["fields"]["value"]
    
    domain = service.split(".")[0]
    service_name = service.split(".")[1]
    
    await hass.services.async_call(
        domain,
        service_name,
        service_data,
        blocking=True,
        context=context,
    ) 