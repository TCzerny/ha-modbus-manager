import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
import os
from pathlib import Path
from .const import DOMAIN
import re

def get_available_device_types():
    """Lädt die verfügbaren Gerätekonfigurationen aus dem device_definitions Verzeichner."""
    device_types = {
        # Sungrow Inverter
        "sungrow_shrt": "Sungrow SH-RT Hybrid Inverter",
        
        # Sungrow Battery
        "sungrow_battery": "Sungrow Battery System",
        
        # Common Definitions
        "common_entities": "Common Entities",
        "load_management": "Load Management System"
    }
    return device_types

def validate_input(data):
    """Validiert die Eingabedaten."""
    errors = {}
    
    # IP-Adresse/Hostname validieren
    if not re.match(r'^[a-zA-Z0-9.-]+$', data["host"]):
        errors["host"] = "invalid_host"
        
    # Port-Bereich prüfen
    if not 1 <= data["port"] <= 65535:
        errors["port"] = "invalid_port"
        
    # Slave-ID-Bereich prüfen
    if not 1 <= data["slave_id"] <= 247:
        errors["slave_id"] = "invalid_slave_id"
        
    # Scan-Intervall-Minimum
    if data["scan_interval"] < 5:
        errors["scan_interval"] = "interval_too_short"
        
    return errors

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
                await validate_input(user_input)
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
        if "shrt" in user_input.get("device_type", ""):
            schema[vol.Required("anlagengroesse_kw", default=5)] = vol.All(
                vol.Coerce(float), vol.Range(min=1, max=30)
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
        ) 