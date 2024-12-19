"""ModbusManager Device Trigger."""
from typing import Any

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .trigger import TRIGGER_SCHEMA, async_get_triggers

TRIGGER_PLATFORM_TYPE = "device"

async def async_validate_trigger_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)
    return config

async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    if config[CONF_PLATFORM] != TRIGGER_PLATFORM_TYPE:
        return None

    from .trigger import async_attach_trigger as platform_attach

    return await platform_attach(hass, config, action, trigger_info) 