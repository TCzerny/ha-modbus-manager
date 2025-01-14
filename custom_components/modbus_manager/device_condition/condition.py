"""ModbusManager Device Conditions."""
from __future__ import annotations

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_TYPE,
    CONF_ENTITY_ID,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from ..const import DOMAIN

# Schema für die Condition-Konfiguration
CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional("above"): vol.Coerce(float),
        vol.Optional("below"): vol.Coerce(float),
        vol.Optional("after"): cv.string,
        vol.Optional("before"): cv.string,
    }
)

async def async_validate_condition_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    return CONDITION_SCHEMA(config)

async def async_get_conditions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """Liste der verfügbaren Conditions für ein Gerät."""
    conditions = []
    
    # Hole die Conditions aus dem Device Registry
    if DOMAIN in hass.data and "device_conditions" in hass.data[DOMAIN]:
        device_conditions = hass.data[DOMAIN]["device_conditions"].get(device_id, [])
        for cond in device_conditions:
            condition_data = {
                "condition": "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: cond["id"],
                CONF_ENTITY_ID: cond.get("entity_id", ""),  # Fallback für fehlende entity_id
                "name": cond["name"]  # Verwende den Namen direkt aus der YAML-Definition
            }
            
            # Füge optionale Parameter hinzu
            if "above" in cond:
                condition_data["above"] = cond["above"]
            if "below" in cond:
                condition_data["below"] = cond["below"]
            if "after" in cond:
                condition_data["after"] = cond["after"]
            if "before" in cond:
                condition_data["before"] = cond["before"]
                
            conditions.append(condition_data)
    
    return conditions

async def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    condition_type = config[CONF_TYPE]
    entity_id = config[CONF_ENTITY_ID]

    @callback
    def test_is_state(hass: HomeAssistant, variables=None) -> bool:
        """Test if the condition is met."""
        state = hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return False

        try:
            if condition_type in ["battery_available", "battery_charging", "grid_exporting"]:
                value = float(state.state)
                
                if condition_type == "battery_available":
                    return value > config.get("above", 5)  # Batterie über 5%
                elif condition_type == "battery_charging":
                    return value > 0  # Positive Leistung = Laden
                elif condition_type == "grid_exporting":
                    return value < 0  # Negative Leistung = Einspeisung
                    
            elif condition_type in ["is_daytime", "is_peak_time"]:
                from datetime import datetime
                import time
                
                now = datetime.fromtimestamp(time.time())
                after_time = datetime.strptime(config["after"], "%H:%M:%S").time()
                before_time = datetime.strptime(config["before"], "%H:%M:%S").time()
                
                if condition_type == "is_daytime":
                    # Spezielle Behandlung für "sunrise" und "sunset"
                    if config["after"] == "sunrise":
                        after_time = hass.states.get("sun.sun").attributes["next_rising"].time()
                    if config["before"] == "sunset":
                        before_time = hass.states.get("sun.sun").attributes["next_setting"].time()
                        
                return after_time <= now.time() <= before_time
                
        except (ValueError, KeyError):
            return False
            
        return False

    return test_is_state 