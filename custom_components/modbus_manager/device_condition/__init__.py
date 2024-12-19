"""ModbusManager Device Condition."""
from typing import Any

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .condition import CONDITION_SCHEMA, async_get_conditions

CONDITION_PLATFORM_TYPE = "device"

async def async_validate_condition_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    config = CONDITION_SCHEMA(config)
    return config

async def async_condition_from_config(hass: HomeAssistant, config: ConfigType) -> bool:
    """Test a device condition."""
    if config[CONF_PLATFORM] != CONDITION_PLATFORM_TYPE:
        return False

    from .condition import async_condition_from_config as platform_condition

    return await platform_condition(hass, config) 