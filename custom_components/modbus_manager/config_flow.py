import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
import os
from pathlib import Path
from .const import DOMAIN

def get_available_device_types():
    """Lädt die verfügbaren Gerätekonfigurationen aus dem device_definitions Verzeichner."""
    device_types = {}
    definitions_path = Path(__file__).parent / "device_definitions"
    
    if definitions_path.exists() and definitions_path.is_dir():
        for file in definitions_path.glob("*.yaml"):
            # Entferne .yaml Endung und konvertiere zu einem lesbaren Namen
            key = file.stem  # z.B. "sungrow_sh10rt"
            # Konvertiere zu einem benutzerfreundlichen Namen
            name = key.replace("_", " ").title()  # z.B. "Sungrow Sh10Rt"
            device_types[key] = name
    
    return device_types

@config_entries.HANDLERS.register(DOMAIN)
class ModbusManagerConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Modbus Manager."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        # Lade verfügbare Gerätekonfigurationen
        device_types = get_available_device_types()
        
        if not device_types:
            errors["base"] = "no_device_types"
            return self.async_show_form(
                step_id="user",
                errors=errors,
                data_schema=vol.Schema({}),
                description_placeholders={
                    "error": "Keine Gerätekonfigurationen gefunden"
                }
            )

        if user_input is not None:
            try:
                # Validate the data can be used to set up a connection
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "invalid_host"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Store configuration data
                return self.async_create_entry(title=user_input["name"], data=user_input)

        # Show configuration form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("host"): str,
                    vol.Required("port", default=502): int,
                    vol.Required("slave_id", default=1): int,
                    vol.Required("scan_interval", default=30): int,
                    vol.Required("device_type"): vol.In(
                        [
                            "sungrow_sh3k6",
                            "sungrow_sh5k6",
                            "sungrow_sh8rt",
                            "sungrow_sh10rt",
                            "sungrow_sh15rt",
                            "sungrow_sg3rt",
                            "sungrow_sg5rt",
                            "sungrow_sg8rt",
                            "sungrow_sg10rt",
                            "compleo_ebox_professional"
                        ]
                    ),
                    vol.Required("anlagengroesse_kw", default=5): vol.All(
                        vol.Coerce(float), vol.Range(min=1, max=30)
                    ),
                }
            ),
            errors=errors,
        ) 