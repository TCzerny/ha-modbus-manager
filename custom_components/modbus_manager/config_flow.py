import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
from .const import DOMAIN
from .modbus_hub import ModbusManagerHub  # Updated import if needed

class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Manager."""

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