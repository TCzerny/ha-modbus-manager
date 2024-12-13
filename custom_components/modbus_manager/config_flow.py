import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
import os
from pathlib import Path
from .const import DOMAIN

def get_available_device_types():
    """Lädt die verfügbaren Gerätekonfigurationen aus dem device_definitions Verzeichner."""
    device_types = {
        # Sungrow SHRT Series (Hybrid Inverter)
        "sungrow_shrt": "Sungrow SH-RT (3-Phase with Battery)",
        "sungrow_shrt_3p": "Sungrow SH-RT (3-Phase)",
        "sungrow_shrt_1p_battery": "Sungrow SH-RT (1-Phase with Battery)",
        "sungrow_shrt_1p": "Sungrow SH-RT (1-Phase)",
        
        # Sungrow SGRT Series (Grid Inverter)
        "sungrow_sgrt": "Sungrow SG-RT (Base)",
        "sungrow_sgrt_single": "Sungrow SG-RT (1-Phase)",
        "sungrow_sgrt_three": "Sungrow SG-RT (3-Phase)",
        
        # Sungrow Battery
        "sungrow_battery": "Sungrow Battery System",
        
        # Compleo Charging Station
        "compleo_ebox_professional": "Compleo eBox Professional",
        
        # Common Definitions
        "common_entities": "Common Entities",
        "load_management": "Load Management System"
    }
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
        schema = {
            vol.Required("name"): str,
            vol.Required("host"): str,
            vol.Required("port", default=502): int,
            vol.Required("slave_id", default=1): int,
            vol.Required("scan_interval", default=30): int,
            vol.Required("device_type"): vol.In(device_types),
        }
        
        # Füge anlagengroesse_kw nur für PV-Anlagen hinzu
        if any(x in user_input.get("device_type", "") for x in ["shrt", "sgrt"]):
            schema[vol.Required("anlagengroesse_kw", default=5)] = vol.All(
                vol.Coerce(float), vol.Range(min=1, max=30)
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
        ) 