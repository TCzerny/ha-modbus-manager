"""Config flow for Modbus Manager."""
import os
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    CONF_DEVICE_TYPE,
)

class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def _get_available_device_types(self):
        """Get list of available device types from device_definitions folder."""
        definitions_dir = os.path.join(os.path.dirname(__file__), "device_definitions")
        device_types = {}
        
        # Durchsuche den device_definitions Ordner nach .yaml Dateien
        if os.path.exists(definitions_dir):
            for filename in os.listdir(definitions_dir):
                if filename.endswith(".yaml"):
                    # Entferne .yaml Endung für device_type
                    device_type = filename[:-5]
                    # Konvertiere snake_case zu Title Case für die Anzeige
                    display_name = device_type.replace('_', ' ').title()
                    device_types[device_type] = display_name

        return device_types

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input
            )

        # Hole verfügbare Gerätetypen
        device_types = self._get_available_device_types()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE_ID): int,
                vol.Required(CONF_DEVICE_TYPE): vol.In(device_types)
            }),
            errors=errors
        )