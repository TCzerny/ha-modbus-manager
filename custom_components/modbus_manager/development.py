"""Development helpers for Modbus Manager."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Modbus Manager config entry."""
    _LOGGER.debug("Reloading Modbus Manager integration")
    
    await hass.config_entries.async_reload(entry.entry_id)
    _LOGGER.debug("Reload complete")

async def async_test_device_type(hass: HomeAssistant, device_type: str) -> None:
    """Test loading a specific device type."""
    from .config_flow import ModbusManagerConfigFlow
    
    flow = ModbusManagerConfigFlow()
    device_types = flow._get_available_device_types()
    
    _LOGGER.debug("Available device types: %s", device_types)
    if device_type in device_types:
        _LOGGER.debug("Device type '%s' found: %s", device_type, device_types[device_type])
    else:
        _LOGGER.error("Device type '%s' not found!", device_type) 