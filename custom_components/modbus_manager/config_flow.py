import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
import os
from pathlib import Path
from .const import DOMAIN
import re
import logging
import yaml

_LOGGER = logging.getLogger(__name__)

def get_available_device_types() -> dict:
    """Lädt die verfügbaren Gerätekonfigurationen dynamisch aus dem device_definitions Verzeichnis."""
    device_types = {}
    definitions_dir = Path(__file__).parent / "device_definitions"
    
    try:
        for file in definitions_dir.glob("*.yaml"):
            if file.stem not in ["common_entities", "load_management"]:
                with open(file, "r") as f:
                    config = yaml.safe_load(f)
                    if config and "device_info" in config:
                        device_types[file.stem] = config["device_info"]["name"]
    except Exception as e:
        _LOGGER.error("Fehler beim Laden der Gerätedefinitionen: %s", e)
    
    return device_types

async def validate_input(data: dict) -> dict:
    """Validiert die Eingabedaten."""
    errors = {}
    
    # IP-Adresse/Hostname validieren
    if not re.match(r'^[a-zA-Z0-9.-]+$', data.get("host", "")):
        errors["host"] = "invalid_host"
        
    # Port-Bereich prüfen
    port = data.get("port")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        errors["port"] = "invalid_port"
        
    # Slave-ID-Bereich prüfen
    slave_id = data.get("slave_id")
    if not isinstance(slave_id, int) or not 1 <= slave_id <= 247:
        errors["slave_id"] = "invalid_slave_id"
        
    # Scan-Intervall-Minimum
    scan_interval = data.get("scan_interval")
    if not isinstance(scan_interval, int) or scan_interval < 5:
        errors["scan_interval"] = "interval_too_short"
        
    return errors

@config_entries.HANDLERS.register(DOMAIN)
class ModbusManagerHubConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Modbus Manager Hub."""

    VERSION = 2

    async def async_step_user(self, user_input: dict = None):
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
            errors = await validate_input(user_input)
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(self.get_schema(device_types, user_input)),
                    errors=errors
                )
            else:
                # Store configuration data
                return self.async_create_entry(title=user_input["name"], data=user_input)

        # Show configuration form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.get_schema(device_types)),
            errors=errors,
        ) 

    def get_schema(self, device_types: dict, user_input: dict = None) -> dict:
        """Erweiterte Konfigurationsoptionen."""
        schema = {
            vol.Required("name"): str,
            vol.Required("host"): str,
            vol.Required("port", default=502): vol.All(int, vol.Range(min=1, max=65535)),
            vol.Required("slave_id", default=1): vol.All(int, vol.Range(min=1, max=247)),
            vol.Required("scan_interval", default=30): vol.All(int, vol.Range(min=5)),
            vol.Required("device_type"): vol.In(device_types),
            vol.Optional("tcp_timeout", default=3): vol.All(int, vol.Range(min=1, max=60)),
            vol.Optional("retries", default=3): vol.All(int, vol.Range(min=0, max=10)),
            vol.Optional("retry_delay", default=0.1): vol.All(float, vol.Range(min=0.1, max=5.0)),
            vol.Optional("use_local_time", default=True): bool,
        }
        
        # Gerätespezifische Optionen
        if user_input and "device_type" in user_input:
            device_config = self._load_device_config(user_input["device_type"])
            if device_config and "config_options" in device_config:
                schema.update(device_config["config_options"])
        
        return schema

    def _load_device_config(self, device_type: str) -> dict:
        """Lädt die Konfiguration für ein bestimmtes Gerät."""
        definitions_dir = Path(__file__).parent / "device_definitions"
        config_file = definitions_dir / f"{device_type}.yaml"
        
        if not config_file.exists():
            return None
        
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
            return config