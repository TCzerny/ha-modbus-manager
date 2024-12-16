"""Config flow for Modbus Manager."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
import homeassistant.helpers.config_validation as cv
from typing import Any, Dict, Optional
import ipaddress
from pathlib import Path
import yaml

from .const import (
    DOMAIN,
    CONF_DEVICE_TYPE,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_NAME,
    MIN_SLAVE_ID,
    MAX_SLAVE_ID,
    ERROR_INVALID_HOST,
    ERROR_INVALID_PORT,
    ERROR_INVALID_SLAVE_ID,
    ERROR_CANNOT_CONNECT,
    ERROR_UNKNOWN,
)

class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Manager."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._device_definitions: Dict[str, Any] = {}
        self._errors: Dict[str, str] = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle the initial step."""
        self._errors = {}

        if user_input is not None:
            try:
                # Validate the input
                await self._validate_input(user_input)
                
                # Create entry
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input
                )
                
            except ValueError as err:
                self._errors["base"] = str(err)
            except Exception:  # pylint: disable=broad-except
                self._errors["base"] = ERROR_UNKNOWN

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self._get_config_schema()),
            errors=self._errors,
        )

    def _get_config_schema(self) -> Dict[str, Any]:
        """Get the configuration schema with available device types."""
        device_types = self._get_available_device_types()
        
        return {
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_SLAVE): cv.positive_int,
            vol.Required(CONF_DEVICE_TYPE): vol.In(device_types),
        }

    def _get_available_device_types(self) -> Dict[str, str]:
        """Get available device types from device definitions."""
        if not self._device_definitions:
            definitions_dir = Path(__file__).parent / "device_definitions"
            device_types = {}
            
            _LOGGER.debug("Scanning directory: %s", definitions_dir)
            
            for file_path in definitions_dir.glob("*.yaml"):
                _LOGGER.debug("Found file: %s", file_path.name)
                
                if file_path.stem in ["common_entities", "device_info"]:
                    _LOGGER.debug("Skipping file: %s", file_path.name)
                    continue
                    
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        definition = yaml.safe_load(f)
                        if "device_info" in definition:
                            device_types[file_path.stem] = definition["device_info"]["name"]
                            _LOGGER.debug("Added device type: %s -> %s", file_path.stem, definition["device_info"]["name"])
                        else:
                            _LOGGER.warning("No device_info found in %s", file_path.name)
                except Exception as e:
                    _LOGGER.warning("Error loading device definition %s: %s", file_path.name, e)
                    
            self._device_definitions = device_types
            _LOGGER.info("Available device types: %s", device_types)
            
        return self._device_definitions

    async def _validate_input(self, user_input: Dict[str, Any]) -> None:
        """Validate the user input."""
        # Validate host
        try:
            ipaddress.ip_address(user_input[CONF_HOST])
        except ValueError:
            self._errors[CONF_HOST] = ERROR_INVALID_HOST

        # Validate port
        if not 1 <= user_input[CONF_PORT] <= 65535:
            self._errors[CONF_PORT] = ERROR_INVALID_PORT

        # Validate slave ID
        if not MIN_SLAVE_ID <= user_input[CONF_SLAVE] <= MAX_SLAVE_ID:
            self._errors[CONF_SLAVE] = ERROR_INVALID_SLAVE_ID

        if self._errors:
            raise ValueError(next(iter(self._errors.values())))

class ModbusManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the Modbus Manager."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Update Firmware-Version und Register
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "firmware_version",
                    default=self.config_entry.options.get("firmware_version", "auto")
                ): str,
            })
        )