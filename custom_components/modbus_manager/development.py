"""Development helpers for Modbus Manager."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger("development")

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Modbus Manager config entry."""
    _LOGGER.debug("Reloading Modbus Manager integration", entry_id=entry.entry_id)
    
    try:
        await hass.config_entries.async_reload(entry.entry_id)
        _LOGGER.info("Reload complete", entry_id=entry.entry_id)
    except Exception as err:
        _LOGGER.error("Failed to reload integration", error=err, entry_id=entry.entry_id)

async def async_test_device_type(hass: HomeAssistant, device_type: str) -> None:
    """Test loading a specific device type."""
    from .config_flow import ModbusManagerConfigFlow
    
    _LOGGER.debug("Testing device type", device_type=device_type)
    
    try:
        flow = ModbusManagerConfigFlow()
        device_types = flow._get_available_device_types()
        
        _LOGGER.debug("Available device types", types=device_types)
        if device_type in device_types:
            _LOGGER.info(
                "Device type found", 
                device_type=device_type, 
                display_name=device_types[device_type]
            )
        else:
            _LOGGER.error("Device type not found", device_type=device_type)
            
    except Exception as err:
        _LOGGER.error("Error testing device type", error=err, device_type=device_type) 