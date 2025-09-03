"""Config Flow for Modbus Manager."""
import voluptuous as vol
import voluptuous_serialize as vs
from typing import List
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .template_loader import get_template_names, get_template_by_name

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
                    if template_data:
                        self._templates[name] = template_data
                _LOGGER.debug("Templates geladen: %s", list(self._templates.keys()))
            
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
                    
                    # Check if this is an aggregates template
                    template_data = self._templates.get(self._selected_template, {})
                    if template_data.get("aggregates"):
                        return await self.async_step_aggregates_config()
                    else:
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

    async def async_step_aggregates_config(self, user_input: dict = None) -> FlowResult:
        """Configure aggregates for the selected template."""
        try:
            if not self._selected_template:
                return self.async_abort(reason="no_template_selected")
            
            template_data = self._templates.get(self._selected_template, {})
            available_aggregates = template_data.get("aggregates", [])
            
            if not available_aggregates:
                return self.async_abort(
                    reason="no_aggregates",
                    description_placeholders={
                        "template": self._selected_template
                    }
                )
            
            if user_input is not None:
                # Process selected aggregates
                selected_aggregates = user_input.get("selected_aggregates", [])
                
                if not selected_aggregates:
                    return self.async_show_form(
                        step_id="aggregates_config",
                        data_schema=self._get_aggregates_schema(available_aggregates),
                        errors={"base": "select_aggregates"}
                    )
                
                # Create final config with selected aggregates
                final_config = {
                    "template": self._selected_template,
                    "template_version": template_data.get("version", 1),
                    "prefix": user_input.get("prefix", "aggregates"),
                    "selected_aggregates": selected_aggregates,
                    "aggregates_config": user_input
                }
                
                return await self.async_step_final_config(final_config)
            
            # Show aggregates configuration form
            return self.async_show_form(
                step_id="aggregates_config",
                data_schema=self._get_aggregates_schema(available_aggregates),
                description_placeholders={
                    "template_name": self._selected_template,
                    "aggregate_count": str(len(available_aggregates))
                }
            )
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Aggregates-Konfiguration: %s", str(e))
            return self.async_abort(
                reason="aggregates_error",
                description_placeholders={"error": str(e)}
            )

    def _get_aggregates_schema(self, available_aggregates: List[dict]) -> vol.Schema:
        """Generate schema for aggregates configuration."""
        # Create options for aggregate selection
        aggregate_options = {}
        for i, aggregate in enumerate(available_aggregates):
            name = aggregate.get("name", f"Aggregate {i+1}")
            group = aggregate.get("group", "unknown")
            method = aggregate.get("method", "sum")
            aggregate_options[f"{i}"] = f"{name} ({group} - {method})"
        
        return vol.Schema({
            vol.Required("prefix", default="aggregates"): str,
            vol.Required("selected_aggregates"): vol.All(
                cv.multi_select(aggregate_options),
                vol.Length(min=1, msg="Mindestens eine Aggregation auswählen")
            )
        })

    async def async_step_device_config(self, user_input: dict = None) -> FlowResult:
        """Handle device configuration step."""
        if user_input is not None:
            return await self.async_step_final_config(user_input)

        # Check if this is a simple template
        template_data = self._templates.get(self._selected_template, {})
        if template_data.get("is_simple_template"):
            # Simple template - only requires prefix and name
            return self.async_show_form(
                step_id="device_config",
                data_schema=vol.Schema({
                    vol.Required("prefix"): str,
                    vol.Optional("name"): str,
                }),
                description_placeholders={
                    "template": self._selected_template,
                    "description": template_data.get("description", "Vereinfachtes Template")
                }
            )
        else:
            # Regular template - requires full Modbus configuration
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
            template_version = template_data.get("version", 1) if isinstance(template_data, dict) else 1
            
            # Check if this is an aggregates template
            if isinstance(template_data, dict) and template_data.get("aggregates"):
                # Handle aggregates template
                return self._create_aggregates_entry(user_input, template_data, template_version)
            else:
                # Handle regular template
                return self._create_regular_entry(user_input, template_data, template_version)
                
        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen der Konfiguration: %s", str(e))
            return self.async_abort(
                reason="config_error",
                description_placeholders={"error": str(e)}
            )

    def _create_aggregates_entry(self, user_input: dict, template_data: dict, template_version: int) -> FlowResult:
        """Create config entry for aggregates template."""
        try:
            # Get selected aggregates
            selected_aggregates = user_input.get("selected_aggregates", [])
            available_aggregates = template_data.get("aggregates", [])
            
            # Filter aggregates based on selection
            filtered_aggregates = []
            for i, aggregate in enumerate(available_aggregates):
                if str(i) in selected_aggregates:
                    filtered_aggregates.append(aggregate)
            
            if not filtered_aggregates:
                return self.async_abort(
                    reason="no_aggregates_selected",
                    description_placeholders={"error": "Keine Aggregationen ausgewählt"}
                )
            
            _LOGGER.debug("Aggregates Template %s (Version %s) mit %d ausgewählten Aggregationen", 
                        self._selected_template, template_version, len(filtered_aggregates))
            
            # Create config entry
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "aggregates": filtered_aggregates,
                    "selected_aggregates": selected_aggregates,
                    "is_aggregates_template": True
                }
            )
            
        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen der Aggregates-Konfiguration: %s", str(e))
            return self.async_abort(
                reason="aggregates_config_error",
                description_placeholders={"error": str(e)}
            )

    def _create_regular_entry(self, user_input: dict, template_data: dict, template_version: int) -> FlowResult:
        """Create config entry for regular template."""
        try:
            # Check if this is a simple template
            if template_data.get("is_simple_template"):
                return self._create_simple_template_entry(user_input, template_data, template_version)
            
            # Register aus Template extrahieren
            template_registers = template_data.get("sensors", []) if isinstance(template_data, dict) else template_data
            
            _LOGGER.debug("Template %s (Version %s) geladen mit %d Registern", 
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
                    "registers": template_registers,
                    "is_aggregates_template": False
                }
            )
            
        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen der regulären Konfiguration: %s", str(e))
            return self.async_abort(
                reason="regular_config_error",
                description_placeholders={"error": str(e)}
            )

    def _create_simple_template_entry(self, user_input: dict, template_data: dict, template_version: int) -> FlowResult:
        """Create config entry for simple template."""
        try:
            _LOGGER.debug("Erstelle vereinfachtes Template Entry: %s", self._selected_template)
            
            # Validate simple template input
            if not self._validate_simple_config(user_input):
                return self.async_abort(
                    reason="invalid_simple_config",
                    description_placeholders={"error": "Ungültige Konfiguration für vereinfachtes Template"}
                )
            
            # Config Entry erstellen für vereinfachtes Template
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "name": user_input.get("name", user_input["prefix"]),
                    "template_data": template_data,
                    "is_simple_template": True,
                    "is_aggregates_template": False
                }
            )
            
        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen der vereinfachten Template-Konfiguration: %s", str(e))
            return self.async_abort(
                reason="simple_config_error",
                description_placeholders={"error": str(e)}
            )

    def _validate_simple_config(self, user_input: dict) -> bool:
        """Validate simple template configuration."""
        try:
            # Pflichtfelder prüfen
            required_fields = ["prefix"]
            if not all(field in user_input for field in required_fields):
                return False
            
            # Prefix validieren (alphanumeric, lowercase, underscore)
            prefix = user_input.get("prefix", "")
            if not prefix or not prefix.replace("_", "").isalnum() or not prefix.islower():
                return False
            
            return True
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Validierung der vereinfachten Konfiguration: %s", str(e))
            return False

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
        return ModbusManagerOptionsFlow()


class ModbusManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Manager."""

    async def async_step_init(self, user_input: dict = None) -> FlowResult:
        """Manage the options."""
        # Check if this is an aggregates template
        is_aggregates_template = self.config_entry.data.get("is_aggregates_template", False)
        
        if is_aggregates_template:
            # Show aggregates selection options
            return await self.async_step_aggregates_options()
        
        if user_input is not None:
            if "update_template" in user_input and user_input["update_template"]:
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

                vol.Optional("update_template"): bool,
            }),
            description_placeholders={
                "template_name": template_name,
                "template_version": str(template_version)
            }
            )

    async def async_step_aggregates_options(self, user_input: dict = None) -> FlowResult:
        """Handle aggregates options for existing aggregate hubs."""
        try:
            # Get current template data
            template_name = self.config_entry.data.get("template", "Modbus Manager Aggregates")
            template_data = await get_template_by_name(template_name)
            
            if not template_data:
                return self.async_abort(
                    reason="template_not_found",
                    description_placeholders={"template_name": template_name}
                )
            
            available_aggregates = template_data.get("aggregates", [])
            if not available_aggregates:
                return self.async_abort(
                    reason="no_aggregates",
                    description_placeholders={"template_name": template_name}
                )
            
            # Get currently selected aggregates
            current_aggregates = self.config_entry.data.get("aggregates", [])
            current_selected = self.config_entry.data.get("selected_aggregates", [])
            
            if user_input is not None:
                # Update the configuration
                selected_aggregates = user_input.get("selected_aggregates", [])
                
                if not selected_aggregates:
                    return self.async_show_form(
                        step_id="aggregates_options",
                        data_schema=self._get_aggregates_options_schema(available_aggregates, current_selected),
                        errors={"base": "select_aggregates"}
                    )
                
                # Filter aggregates based on selection
                filtered_aggregates = []
                for i, aggregate in enumerate(available_aggregates):
                    if str(i) in selected_aggregates:
                        filtered_aggregates.append(aggregate)
                
                # Update config entry
                new_data = dict(self.config_entry.data)
                new_data["aggregates"] = filtered_aggregates
                new_data["selected_aggregates"] = selected_aggregates
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data
                )
                
                _LOGGER.debug("Aggregate-Optionen aktualisiert: %d von %d Aggregaten ausgewählt", 
                            len(filtered_aggregates), len(available_aggregates))
                
                return self.async_create_entry(title="", data={})
            
            # Show aggregates selection form
            return self.async_show_form(
                step_id="aggregates_options",
                data_schema=self._get_aggregates_options_schema(available_aggregates, current_selected),
                description_placeholders={
                    "template_name": template_name,
                    "template_version": str(self.config_entry.data.get("template_version", 1)),
                    "current_count": str(len(current_aggregates)),
                    "available_count": str(len(available_aggregates))
                }
            )
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Aggregate-Optionen-Konfiguration: %s", str(e))
            return self.async_abort(
                reason="aggregates_options_error",
                description_placeholders={"error": str(e)}
            )

    def _get_aggregates_options_schema(self, available_aggregates: List[dict], current_selected: List[str]) -> vol.Schema:
        """Generate schema for aggregates options configuration."""
        # Create options for aggregate selection
        aggregate_options = {}
        for i, aggregate in enumerate(available_aggregates):
            name = aggregate.get("name", f"Aggregate {i+1}")
            group = aggregate.get("group", "unknown")
            method = aggregate.get("method", "sum")
            aggregate_options[f"{i}"] = f"{name} ({group} - {method})"
        
        return vol.Schema({
            vol.Required("selected_aggregates", default=current_selected): vol.All(
                cv.multi_select(aggregate_options),
                vol.Length(min=1, msg="Mindestens eine Aggregation auswählen")
            )
        })

            
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
                
                _LOGGER.debug("Template %s aktualisiert: v%s → v%s", 
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
