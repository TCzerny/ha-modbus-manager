"""Config Flow for Modbus Manager."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN
from .template_loader import get_template_names, get_template_by_name
from .aggregates import AggregationManager
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Manager."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self._templates = {}
        self._selected_template = None

    async def async_step_user(self, user_input: dict = None) -> FlowResult:
        """Handle the initial step."""
        try:
            # Templates laden
            if not self._templates:
                template_names = await get_template_names()
                self._templates = {}
                for name in template_names:
                    template_data = await get_template_by_name(name)
                    self._templates[name] = template_data
                _LOGGER.info("Templates geladen: %s", list(self._templates.keys()))
            
            if not self._templates:
                return self.async_abort(
                    reason="no_templates",
                    description_placeholders={
                        "error": "Keine Templates gefunden. Bitte stellen Sie sicher, dass Templates im device_templates Verzeichnis vorhanden sind."
                    }
                )

            if user_input is not None:
                # Template auswählen
                if "template" in user_input:
                    self._selected_template = user_input["template"]
                    return await self.async_step_device_config()
                
                # Geräte-Konfiguration
                return await self.async_step_final_config(user_input)

            # Template-Auswahl anzeigen
            template_names = list(self._templates.keys())
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("template"): vol.In(template_names),
                }),
                description_placeholders={
                    "template_count": str(len(template_names)),
                    "template_list": ", ".join(template_names)
                }
            )

        except Exception as e:
            _LOGGER.error("Fehler im Config Flow: %s", str(e))
            return self.async_abort(
                reason="unknown_error",
                description_placeholders={"error": str(e)}
            )

    async def async_step_device_config(self, user_input: dict = None) -> FlowResult:
        """Handle device configuration step."""
        if user_input is not None:
            return await self.async_step_final_config(user_input)

        return self.async_show_form(
            step_id="device_config",
            data_schema=vol.Schema({
                vol.Required("prefix"): str,
                vol.Required("host"): str,
                vol.Optional("port", default=502): int,
                vol.Optional("slave_id", default=1): int,
                vol.Optional("timeout", default=3): int,
                vol.Optional("retries", default=3): int,
                vol.Optional("delay", default=0): int,
                vol.Optional("close_comm_on_error", default=True): bool,
                vol.Optional("reconnect_delay", default=10): int,
                vol.Optional("message_wait", default=0): int,
            }),
            description_placeholders={
                "template": self._selected_template
            }
        )

    async def async_step_final_config(self, user_input: dict) -> FlowResult:
        """Handle final configuration and create entry."""
        try:
            # Template-Daten abrufen
            template_data = self._templates[self._selected_template]
            template_registers = template_data.get("sensors", []) if isinstance(template_data, dict) else template_data
            template_version = template_data.get("version", 1) if isinstance(template_data, dict) else 1
            _LOGGER.info("Template %s (Version %s) geladen mit %d Registern", 
                        self._selected_template, 
                        template_version,
                        len(template_registers) if template_registers else 0)
            
            # Template-Daten validieren
            if not template_registers:
                _LOGGER.error("Template %s hat keine Register", self._selected_template)
                return self.async_abort(
                    reason="no_registers",
                    description_placeholders={"error": f"Template {self._selected_template} hat keine Register"}
                )
            
            # Debug: Template-Struktur anzeigen
            _LOGGER.debug("Template-Struktur: %s", template_registers[:2] if template_registers else "Keine Register")
            
            # Konfiguration validieren
            if not self._validate_config(user_input):
                return self.async_abort(
                    reason="invalid_config",
                    description_placeholders={"error": "Ungültige Konfiguration"}
                )

            # Config Entry erstellen
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "host": user_input["host"],
                    "port": user_input.get("port", 502),
                    "slave_id": user_input.get("slave_id", 1),
                    "timeout": user_input.get("timeout", 3),
                    "retries": user_input.get("retries", 3),
                    "delay": user_input.get("delay", 0),
                    "close_comm_on_error": user_input.get("close_comm_on_error", True),
                    "reconnect_delay": user_input.get("reconnect_delay", 10),
                    "message_wait": user_input.get("message_wait", 0),
                    "registers": template_registers
                }
            )

        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen der Konfiguration: %s", str(e))
            return self.async_abort(
                reason="config_error",
                description_placeholders={"error": str(e)}
            )

    def _validate_config(self, user_input: dict) -> bool:
        """Validate user input configuration."""
        try:
            # Pflichtfelder prüfen
            required_fields = ["prefix", "host"]
            if not all(field in user_input for field in required_fields):
                return False
            
            # Port validieren
            port = user_input.get("port", 502)
            if not isinstance(port, int) or port < 1 or port > 65535:
                return False
            
            # Slave ID validieren
            slave_id = user_input.get("slave_id", 1)
            if not isinstance(slave_id, int) or slave_id < 1 or slave_id > 255:
                return False
            
            # Timeout validieren
            timeout = user_input.get("timeout", 3)
            if not isinstance(timeout, int) or timeout < 1:
                return False
            
            # Retries validieren
            retries = user_input.get("retries", 3)
            if not isinstance(retries, int) or retries < 0:
                return False
            
            # Delay validieren
            delay = user_input.get("delay", 0)
            if not isinstance(delay, int) or delay < 0:
                return False
            
            # Reconnect delay validieren
            reconnect_delay = user_input.get("reconnect_delay", 10)
            if not isinstance(reconnect_delay, int) or reconnect_delay < 0:
                return False
            
            # Message wait validieren
            message_wait = user_input.get("message_wait", 0)
            if not isinstance(message_wait, int) or message_wait < 0:
                return False
            
            return True
            
        except Exception:
            return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ModbusManagerOptionsFlow(config_entry)


class ModbusManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Manager."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self._aggregation_manager = None

    async def async_step_init(self, user_input: dict = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if "configure_aggregations" in user_input:
                return await self.async_step_aggregation_config()
            elif "update_template" in user_input and user_input["update_template"]:
                return await self.async_step_update_template()
            else:
                # Update basic settings
                return self.async_create_entry(title="", data=user_input)

        # Template-Informationen für Anzeige vorbereiten
        template_name = self.config_entry.data.get("template", "Unbekannt")
        template_version = self.config_entry.data.get("template_version", 1)
        
        # Basic options form
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "timeout",
                    default=self.config_entry.data.get("timeout", 3)
                ): int,
                vol.Optional(
                    "retries",
                    default=self.config_entry.data.get("retries", 3)
                ): int,
                vol.Optional(
                    "delay",
                    default=self.config_entry.data.get("delay", 0)
                ): int,
                vol.Optional(
                    "close_comm_on_error",
                    default=self.config_entry.data.get("close_comm_on_error", True)
                ): bool,
                vol.Optional(
                    "reconnect_delay",
                    default=self.config_entry.data.get("reconnect_delay", 10)
                ): int,
                vol.Optional(
                    "message_wait",
                    default=self.config_entry.data.get("message_wait", 0)
                ): int,
                vol.Optional("configure_aggregations"): bool,
                vol.Optional("update_template"): bool,
            }),
            description_placeholders={
                "template_name": template_name,
                "template_version": str(template_version)
            }
            )

    async def async_step_aggregation_config(self, user_input: dict = None) -> FlowResult:
        """Configure aggregations for discovered groups."""
        try:
            if not self._aggregation_manager:
                prefix = self.config_entry.data.get("prefix", "unknown")
                self._aggregation_manager = AggregationManager(self.hass, prefix)
            
            # Discover available groups
            available_groups = await self._aggregation_manager.discover_groups()
            
            if not available_groups:
                return self.async_show_form(
                    step_id="aggregation_config",
                    data_schema=vol.Schema({}),
                    description_placeholders={
                        "message": "Keine Gruppen gefunden. Stellen Sie sicher, dass Sensoren mit group-Tags konfiguriert sind."
                    }
                )

            if user_input is not None:
                # Create aggregate sensors for selected groups
                selected_group = user_input.get("groups")
                selected_method = user_input.get("methods", "sum")
                
                created_sensors = []
                if selected_group:
                    sensors = await self._aggregation_manager.create_aggregate_sensors(selected_group, [selected_method])
                    created_sensors.extend(sensors)
                    
                    # Add sensors to Home Assistant
                    self.hass.data[DOMAIN][self.config_entry.entry_id]["aggregate_sensors"] = sensors
                    
                    # Add sensors to Home Assistant entity registry
                    try:
                        # Get the entity registry
                        from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
                        registry = async_get_entity_registry(self.hass)
                        
                        # Get the device registry to find the Modbus Manager device
                        from homeassistant.helpers.device_registry import async_get as async_get_device_registry
                        device_registry = async_get_device_registry(self.hass)
                        
                        # Find the Modbus Manager device for this config entry
                        modbus_device = None
                        for device in device_registry.devices.values():
                            if device.config_entries and self.config_entry.entry_id in device.config_entries:
                                modbus_device = device
                                break
                        
                        if not modbus_device:
                            _LOGGER.warning("Modbus Manager Gerät nicht gefunden für Config Entry %s", self.config_entry.entry_id)
                        
                        # Add each sensor to the registry
                        for sensor in sensors:
                            try:
                                # Add entity to registry with correct device_id
                                registry.async_get_or_create(
                                    domain="sensor",
                                    platform=DOMAIN,
                                    unique_id=sensor.unique_id,
                                    suggested_object_id=sensor.unique_id.replace("aggregate_", ""),
                                    config_entry=self.config_entry,
                                    device_id=modbus_device.id if modbus_device else None,
                                    disabled_by=None
                                )
                                _LOGGER.info("Aggregate-Sensor %s zur Entity Registry hinzugefügt (Device: %s)", 
                                            sensor.unique_id, modbus_device.id if modbus_device else "None")
                            except Exception as e:
                                _LOGGER.error("Fehler beim Hinzufügen des Sensors %s: %s", sensor.unique_id, str(e))
                        
                        _LOGGER.info("Aggregate-Sensoren zur Entity Registry hinzugefügt")
                    except Exception as e:
                        _LOGGER.error("Fehler beim Hinzufügen der Aggregate-Sensoren zur Registry: %s", str(e))
                
                if created_sensors:
                    _LOGGER.info("%d Aggregat-Sensoren erstellt", len(created_sensors))
                
                return self.async_create_entry(
                    title="",
                    data={
                        "aggregations_configured": True,
                        "groups": [selected_group] if selected_group else [],
                        "methods": [selected_method]
                    }
                )

            # Show aggregation configuration form
            return self.async_show_form(
                step_id="aggregation_config",
                data_schema=vol.Schema({
                    vol.Required("groups"): vol.In(available_groups),
                    vol.Optional("methods", default=["sum", "average"]): vol.In(["sum", "average", "max", "min", "count"]),
                }),
                description_placeholders={
                    "available_groups": ", ".join(available_groups),
                    "group_count": str(len(available_groups))
                }
            )

        except Exception as e:
            _LOGGER.error("Fehler bei der Aggregations-Konfiguration: %s", str(e))
            return self.async_abort(
                reason="aggregation_error",
                description_placeholders={"error": str(e)}
            )
            
    async def async_step_update_template(self, user_input: dict = None) -> FlowResult:
        """Update the template to the latest version."""
        try:
            # Aktuelle Template-Informationen abrufen
            template_name = self.config_entry.data.get("template", "Unbekannt")
            stored_version = self.config_entry.data.get("template_version", 1)
            
            # Neues Template laden
            template_data = await get_template_by_name(template_name)
            if not template_data:
                return self.async_abort(
                    reason="template_not_found",
                    description_placeholders={"template_name": template_name}
                )
            
            # Template-Version und Register extrahieren
            if isinstance(template_data, dict):
                current_version = template_data.get("version", 1)
                template_registers = template_data.get("sensors", [])
                calculated_entities = template_data.get("calculated", [])
            else:
                current_version = 1
                template_registers = template_data
                calculated_entities = []
            
            if not template_registers:
                return self.async_abort(
                    reason="no_registers",
                    description_placeholders={"template_name": template_name}
                )
            
            if user_input is not None:
                # Template aktualisieren
                new_data = dict(self.config_entry.data)
                new_data["template_version"] = current_version
                new_data["registers"] = template_registers
                
                # Wenn das neue Template calculated_entities hat, diese auch aktualisieren
                if calculated_entities:
                    new_data["calculated_entities"] = calculated_entities
                
                # Config Entry aktualisieren
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data
                )
                
                _LOGGER.info("Template %s aktualisiert: v%s → v%s", 
                            template_name, stored_version, current_version)
                
                # Zurück zur Hauptansicht
                return self.async_create_entry(title="", data={})
            
            # Bestätigungsdialog anzeigen
            return self.async_show_form(
                step_id="update_template",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "template_name": template_name,
                    "stored_version": str(stored_version),
                    "current_version": str(current_version)
                }
            )
            
        except Exception as e:
            _LOGGER.error("Fehler beim Aktualisieren des Templates: %s", str(e))
            return self.async_abort(
                reason="update_error",
                description_placeholders={"error": str(e)}
            )
