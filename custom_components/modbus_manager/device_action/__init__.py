"""ModbusManager Device Action."""
from typing import Any

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .action import ACTION_SCHEMA, async_get_actions

ACTION_PLATFORM_TYPE = "device"

async def async_validate_action_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    config = ACTION_SCHEMA(config)
    return config

async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    if config[CONF_PLATFORM] != ACTION_PLATFORM_TYPE:
        return None

    from .action import async_call_action_from_config as platform_action

    await platform_action(hass, config, variables, context)

__all__ = ["async_get_actions", "async_call_action_from_config"] 