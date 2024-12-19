"""Config flow for Modbus Manager."""
import os
import yaml
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    CONF_DEVICE_TYPE,
    CONF_FIRMWARE_VERSION,
)

from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger("config_flow")

class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    
    def __init__(self):
        """Initialize the config flow."""
        self.device_type = None
        self.device_config = None

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

    def _get_firmware_versions(self, device_type):
        """Get available firmware versions for the selected device type."""
        try:
            # Lade die Gerätedefinition
            definition_path = os.path.join(
                os.path.dirname(__file__),
                "device_definitions",
                f"{device_type}.yaml"
            )
            
            with open(definition_path, 'r') as f:
                device_def = yaml.safe_load(f)
                
            # Speichere die Gerätekonfiguration für späteren Gebrauch
            self.device_config = device_def
                
            # Hole die verfügbaren Firmware-Versionen
            versions = {}
            
            # Füge "Auto-Detect" Option hinzu, wenn konfiguriert
            if device_def.get("firmware", {}).get("auto_detect", False):
                versions["auto"] = "Auto-Detect"
                
            # Füge die definierten Firmware-Versionen hinzu
            if "firmware_versions" in device_def:
                for version in device_def["firmware_versions"].keys():
                    versions[version] = f"Version {version}"
                    
            # Wenn keine Versionen definiert sind, füge eine Standard-Version hinzu
            if not versions:
                versions["1.0.0"] = "Version 1.0.0 (Standard)"
                
            return versions
            
        except Exception as e:
            _LOGGER.error(f"Fehler beim Laden der Firmware-Versionen: {str(e)}")
            return {"1.0.0": "Version 1.0.0 (Standard)"}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.device_type = user_input[CONF_DEVICE_TYPE]
            # Speichere die Basis-Konfiguration
            self.base_config = user_input
            # Gehe zum nächsten Schritt (Firmware-Auswahl)
            return await self.async_step_firmware()

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

    async def async_step_firmware(self, user_input=None):
        """Handle the firmware selection step."""
        errors = {}

        if user_input is not None:
            # Kombiniere die Basis-Konfiguration mit der Firmware-Version
            config = {**self.base_config, **user_input}
            return self.async_create_entry(
                title=config[CONF_NAME],
                data=config
            )

        # Hole verfügbare Firmware-Versionen für den gewählten Gerätetyp
        firmware_versions = self._get_firmware_versions(self.device_type)

        return self.async_show_form(
            step_id="firmware",
            data_schema=vol.Schema({
                vol.Required(CONF_FIRMWARE_VERSION): vol.In(firmware_versions)
            }),
            errors=errors,
            description_placeholders={
                "device_type": self.device_type.replace('_', ' ').title()
            }
        )