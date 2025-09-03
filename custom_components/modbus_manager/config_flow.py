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
            # Templates nur einmal laden (caching)
            if not self._templates:
                _LOGGER.debug("Loading templates for the first time...")
                template_names = await get_template_names()
                self._templates = {}
                for name in template_names:
                    template_data = await get_template_by_name(name)
                    if template_data:
                        self._templates[name] = template_data
                        _LOGGER.debug("Loaded template %s: has_dynamic_config=%s", 
                                   name, "dynamic_config" in template_data)
                _LOGGER.debug("Templates loaded: %s", list(self._templates.keys()))
            else:
                _LOGGER.debug("Using cached templates: %s", list(self._templates.keys()))
            
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
                    _LOGGER.debug("Selected template: %s", self._selected_template)
                    
                    # Check if this is an aggregates template
                    template_data = self._templates.get(self._selected_template, {})
                    _LOGGER.debug("Template data for %s: keys=%s, has_dynamic_config=%s", 
                               self._selected_template, list(template_data.keys()), 
                               "dynamic_config" in template_data)
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
            # Check if this is a SunSpec Standard Configuration template
            if "SunSpec Standard Configuration" in self._selected_template:
                # SunSpec Standard Configuration - requires model addresses
                return self.async_show_form(
                    step_id="device_config",
                    data_schema=vol.Schema({
                        vol.Required("prefix"): str,
                        vol.Optional("name"): str,
                        vol.Required("common_model_address", default=40001): int,
                        vol.Required("inverter_model_address", default=40069): int,
                        vol.Optional("storage_model_address"): int,
                        vol.Optional("meter_model_address"): int,
                    }),
                    description_placeholders={
                        "template": self._selected_template,
                        "description": "SunSpec Standard - Modell-Adressen angeben"
                    }
                )
            else:
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
            # Check if this template supports dynamic configuration
            _LOGGER.debug("Template data keys: %s", list(template_data.keys()))
            _LOGGER.debug("Has dynamic_config: %s", "dynamic_config" in template_data)
            _LOGGER.debug("Template name: %s", template_data.get("name", "Unknown"))
            
            schema_fields = {
                vol.Required("prefix"): str,
                vol.Required("host"): str,
                vol.Optional("port", default=502): int,
                vol.Optional("slave_id", default=1): int,
                vol.Optional("timeout", default=5): int,
                vol.Optional("delay", default=0): int,
            }
            
            # Add dynamic template parameters if supported
            if self._supports_dynamic_config(template_data):
                _LOGGER.debug("Template supports dynamic config, adding schema fields")
                dynamic_schema = self._get_dynamic_config_schema(template_data)
                _LOGGER.debug("Dynamic schema fields: %s", list(dynamic_schema.keys()))
                schema_fields.update(dynamic_schema)
            else:
                _LOGGER.debug("Template does not support dynamic config")
            
            return self.async_show_form(
                step_id="device_config",
                data_schema=vol.Schema(schema_fields),
                description_placeholders={
                    "template": self._selected_template
                }
            )

    def _supports_dynamic_config(self, template_data: dict) -> bool:
        """Check if template supports dynamic configuration."""
        # Check if template has dynamic_config section
        has_dynamic = "dynamic_config" in template_data
        _LOGGER.info("_supports_dynamic_config: template_data keys=%s, has_dynamic=%s", 
                     list(template_data.keys()), has_dynamic)
        return has_dynamic

    def _get_dynamic_config_schema(self, template_data: dict) -> dict:
        """Generate dynamic configuration schema based on template."""
        dynamic_config = template_data.get("dynamic_config", {})
        _LOGGER.debug("_get_dynamic_config_schema: dynamic_config keys=%s", list(dynamic_config.keys()))
        schema_fields = {}
        
        # Phase configuration
        if "phases" in dynamic_config:
            _LOGGER.debug("Adding phases field to schema")
            schema_fields[vol.Optional("phases", description="Anzahl Phasen (1 oder 3)", default=1)] = vol.In([1, 3])
        
        # MPPT configuration
        if "mppt_count" in dynamic_config:
            mppt_options = dynamic_config["mppt_count"].get("options", [1, 2, 3])
            _LOGGER.debug("Adding mppt_count field to schema with options: %s", mppt_options)
            schema_fields[vol.Optional("mppt_count", description="Anzahl MPPT-Tracker", default=1)] = vol.In(mppt_options)
        
        # Battery configuration
        if "battery" in dynamic_config:
            _LOGGER.debug("Adding battery_enabled field to schema")
            schema_fields[vol.Optional("battery_enabled", description="Batterie-Unterstützung aktiviert", default=False)] = bool
        
        # Firmware version
        if "firmware_version" in dynamic_config:
            _LOGGER.debug("Adding firmware_version field to schema")
            default_firmware = dynamic_config["firmware_version"].get("default", "1.0.0")
            schema_fields[vol.Optional("firmware_version", description="Firmware-Version", default=default_firmware)] = str
        
        # String count - removed as no string-specific sensors exist in current templates
        
        # Connection type
        if "connection_type" in dynamic_config:
            conn_options = dynamic_config["connection_type"].get("options", ["LAN", "WINET"])
            _LOGGER.debug("Adding connection_type field to schema with options: %s", conn_options)
            schema_fields[vol.Optional("connection_type", description="Verbindungstyp", default="LAN")] = vol.In(conn_options)
        
        _LOGGER.debug("Final schema fields: %s", list(schema_fields.keys()))
        return schema_fields

    def _process_dynamic_config(self, user_input: dict, template_data: dict) -> dict:
        """Process template based on dynamic configuration parameters."""
        original_sensors = template_data.get("sensors", [])
        original_calculated = template_data.get("calculated", [])
        original_controls = template_data.get("controls", [])
        dynamic_config = template_data.get("dynamic_config", {})
        
        processed_sensors = []
        processed_calculated = []
        processed_controls = []
        
        # Get user configuration
        phases = user_input.get("phases", 1)
        mppt_count = user_input.get("mppt_count", 1)
        battery_enabled = user_input.get("battery_enabled", False)
        firmware_version = user_input.get("firmware_version", "1.0.0")
        connection_type = user_input.get("connection_type", "LAN")
        
        _LOGGER.info("Processing dynamic config: phases=%d, mppt=%d, battery=%s, fw=%s, conn=%s", 
                     phases, mppt_count, battery_enabled, firmware_version, connection_type)
        
        # Process sensors
        for sensor in original_sensors:
            # Check if sensor should be included based on configuration
            if self._should_include_sensor(sensor, phases, mppt_count, battery_enabled, firmware_version, connection_type, dynamic_config):
                # Apply firmware-specific modifications
                modified_sensor = self._apply_firmware_modifications(sensor, firmware_version, dynamic_config)
                processed_sensors.append(modified_sensor)
        
        # Process calculated sensors
        for calculated in original_calculated:
            # Check if calculated sensor should be included based on configuration
            if self._should_include_sensor(calculated, phases, mppt_count, battery_enabled, firmware_version, connection_type, dynamic_config):
                processed_calculated.append(calculated)
        
        # Process controls
        for control in original_controls:
            # Check if control should be included based on configuration
            if self._should_include_sensor(control, phases, mppt_count, battery_enabled, firmware_version, connection_type, dynamic_config):
                processed_controls.append(control)
        
        _LOGGER.info("Processed %d sensors, %d calculated, %d controls from %d original sensors, %d calculated, %d controls", 
                     len(processed_sensors), len(processed_calculated), len(processed_controls),
                     len(original_sensors), len(original_calculated), len(original_controls))
        
        # Return processed template data
        return {
            "sensors": processed_sensors,
            "calculated": processed_calculated,
            "controls": processed_controls
        }

    def _should_include_sensor(self, sensor: dict, phases: int, mppt_count: int, battery_enabled: bool, 
                               firmware_version: str, connection_type: str, dynamic_config: dict) -> bool:
        """Check if sensor should be included based on configuration."""
        sensor_name = sensor.get("name", "").lower()
        unique_id = sensor.get("unique_id", "").lower()
        
        # Check both sensor_name and unique_id for filtering
        search_text = f"{sensor_name} {unique_id}".lower()
        
        # Debug: Log what we're checking
        _LOGGER.debug("Checking sensor: name='%s', unique_id='%s', search_text='%s'", 
                     sensor_name, unique_id, search_text)
        
        # Phase-specific sensors
        if phases == 1:
            # Exclude phase B and C sensors for single phase
            if any(phase in search_text for phase in ["phase_b", "phase_c", "phase b", "phase c"]):
                _LOGGER.info("Excluding sensor due to single phase config: %s (unique_id: %s)", 
                             sensor.get("name", "unknown"), sensor.get("unique_id", "unknown"))
                return False
        elif phases == 3:
            # Include all phase sensors
            pass
        
        # MPPT-specific sensors
        if "mppt" in search_text:
            # Extract MPPT number from sensor name or unique_id
            mppt_number = self._extract_mppt_number(search_text)
            if mppt_number and mppt_number > mppt_count:
                _LOGGER.info("Excluding sensor due to MPPT count config: %s (unique_id: %s, MPPT %d > %d)", 
                             sensor.get("name", "unknown"), sensor.get("unique_id", "unknown"), mppt_number, mppt_count)
                return False
        
        # Battery-specific sensors
        if not battery_enabled:
            battery_keywords = ["battery", "bms", "soc", "charge", "discharge", "backup"]
            if any(keyword in search_text for keyword in battery_keywords):
                _LOGGER.info("Excluding sensor due to battery disabled: %s (unique_id: %s)", 
                             sensor.get("name", "unknown"), sensor.get("unique_id", "unknown"))
                return False
        
        # String-specific sensors - removed as no string sensors exist in current templates
        
        # Connection type specific sensors
        connection_config = dynamic_config.get("connection_type", {}).get("sensor_availability", {})
        if connection_type == "LAN":
            # Exclude WINET-only sensors
            winet_only_sensors = connection_config.get("winet_only_sensors", [])
            if unique_id in winet_only_sensors:
                _LOGGER.info("Excluding sensor due to LAN connection: %s (unique_id: %s)", 
                             sensor.get("name", "unknown"), sensor.get("unique_id", "unknown"))
                return False
        elif connection_type == "WINET":
            # Exclude LAN-only sensors
            lan_only_sensors = connection_config.get("lan_only_sensors", [])
            if unique_id in lan_only_sensors:
                _LOGGER.info("Excluding sensor due to WINET connection: %s (unique_id: %s)", 
                             sensor.get("name", "unknown"), sensor.get("unique_id", "unknown"))
                return False
        
        return True

    def _extract_mppt_number(self, search_text: str) -> int:
        """Extract MPPT number from sensor name or unique_id."""
        import re
        match = re.search(r'mppt(\d+)', search_text.lower())
        return int(match.group(1)) if match else None

    # _extract_string_number function removed - no string sensors exist in current templates

    def _apply_firmware_modifications(self, sensor: dict, firmware_version: str, dynamic_config: dict) -> dict:
        """Apply firmware-specific modifications to sensor based on unique_id."""
        modified_sensor = sensor.copy()
        
        # Get sensor replacements configuration
        sensor_replacements = dynamic_config.get("firmware_version", {}).get("sensor_replacements", {})
        
        # Get sensor unique_id
        unique_id = sensor.get("unique_id", "")
        
        # Check if this sensor has firmware-specific replacements
        if unique_id in sensor_replacements:
            replacements = sensor_replacements[unique_id]
            
            # Find the highest firmware version that matches or is lower than current
            applicable_version = self._find_applicable_firmware_version(firmware_version, replacements.keys())
            
            if applicable_version:
                replacement_config = replacements[applicable_version]
                _LOGGER.debug("Applying firmware %s replacement for sensor %s", applicable_version, unique_id)
                
                # Apply all replacement parameters
                for param, value in replacement_config.items():
                    if param != "description":  # Skip description, it's just for documentation
                        modified_sensor[param] = value
                        _LOGGER.debug("Replaced %s=%s for sensor %s (firmware %s)", 
                                     param, value, unique_id, applicable_version)
        
        return modified_sensor

    def _find_applicable_firmware_version(self, current_version: str, available_versions: list) -> str:
        """Find the highest firmware version that matches or is lower than current version."""
        from packaging import version
        
        try:
            # Try to parse as semantic version first
            current_ver = version.parse(current_version)
            applicable_versions = []
            
            for ver_str in available_versions:
                try:
                    ver = version.parse(ver_str)
                    if ver <= current_ver:
                        applicable_versions.append(ver)
                except version.InvalidVersion:
                    # Skip invalid semantic versions
                    continue
            
            if applicable_versions:
                # Return the highest applicable version
                return str(max(applicable_versions))
            
        except version.InvalidVersion:
            # For non-semantic versions (like SAPPHIRE-H_03011.95.01), 
            # try exact match first, then fallback to string comparison
            _LOGGER.debug("Non-semantic firmware version format detected: %s", current_version)
            
            # Check for exact match
            if current_version in available_versions:
                return current_version
            
            # Try string comparison for similar formats
            for ver_str in available_versions:
                if ver_str == current_version:
                    return ver_str
                # For similar formats, we could add more sophisticated comparison logic here
        
        return None

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
            _LOGGER.error("Error creating configuration: %s", str(e))
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
                    description_placeholders={"error": "No aggregates selected"}
                )
            
            _LOGGER.debug("Aggregates Template %s (Version %s) with %d selected aggregates", 
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
            _LOGGER.error("Error creating aggregates configuration: %s", str(e))
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
            
            # Process dynamic configuration if supported
            if self._supports_dynamic_config(template_data):
                processed_data = self._process_dynamic_config(user_input, template_data)
                template_registers = processed_data.get("sensors", [])
                template_calculated = processed_data.get("calculated", [])
                template_controls = processed_data.get("controls", [])
            else:
                # Extract registers from template
                template_registers = template_data.get("sensors", []) if isinstance(template_data, dict) else template_data
                template_calculated = template_data.get("calculated", []) if isinstance(template_data, dict) else []
                template_controls = template_data.get("controls", []) if isinstance(template_data, dict) else []
            
            _LOGGER.debug("Template %s (Version %s) loaded with %d registers", 
                        self._selected_template, 
                        template_version,
                        len(template_registers) if template_registers else 0)
            
            # Validate template data
            if not template_registers:
                _LOGGER.error("Template %s has no registers", self._selected_template)
                return self.async_abort(
                    reason="no_registers",
                    description_placeholders={"error": f"Template {self._selected_template} has no registers"}
                )
            
            # Debug: Show template structure
            _LOGGER.debug("Template structure: %s", template_registers[:2] if template_registers else "No registers")
            
            # Validate configuration
            if not self._validate_config(user_input):
                return self.async_abort(
                    reason="invalid_config",
                    description_placeholders={"error": "Invalid configuration"}
                )

            # Create config entry
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "host": user_input["host"],
                    "port": user_input.get("port", 502),
                    "slave_id": user_input.get("slave_id", 1),
                    "timeout": user_input.get("timeout", 5),
                    "delay": user_input.get("delay", 0),
                    "registers": template_registers,
                    "calculated_entities": template_calculated,
                    "controls": template_controls,
                    "is_aggregates_template": False
                }
            )
            
        except Exception as e:
            _LOGGER.error("Error creating regular configuration: %s", str(e))
            return self.async_abort(
                reason="regular_config_error",
                description_placeholders={"error": str(e)}
            )

    def _create_simple_template_entry(self, user_input: dict, template_data: dict, template_version: int) -> FlowResult:
        """Create config entry for simple template."""
        try:
            _LOGGER.debug("Creating simple template entry: %s", self._selected_template)
            
            # Check if this is a SunSpec Standard Configuration template
            if "SunSpec Standard Configuration" in self._selected_template:
                return self._create_sunspec_config_entry(user_input, template_data, template_version)
            
            # Validate simple template input
            if not self._validate_simple_config(user_input):
                return self.async_abort(
                    reason="invalid_simple_config",
                    description_placeholders={"error": "Invalid configuration for simple template"}
                )
            
            # Create config entry for simple template
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
            _LOGGER.error("Error creating simple template configuration: %s", str(e))
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

    def _create_sunspec_config_entry(self, user_input: dict, template_data: dict, template_version: int) -> FlowResult:
        """Create config entry for SunSpec Standard Configuration template."""
        try:
            _LOGGER.debug("Erstelle SunSpec Standard Configuration Entry: %s", self._selected_template)
            
            # Validate SunSpec configuration input
            if not self._validate_sunspec_config(user_input):
                return self.async_abort(
                    reason="invalid_sunspec_config",
                    description_placeholders={"error": "Ungültige SunSpec-Konfiguration"}
                )
            
            # Build model addresses from user input
            model_addresses = {
                "common_model": user_input["common_model_address"],
                "inverter_model": user_input["inverter_model_address"],
            }
            
            # Add optional model addresses
            if user_input.get("storage_model_address"):
                model_addresses["storage_model"] = user_input["storage_model_address"]
            
            if user_input.get("meter_model_address"):
                model_addresses["meter_model"] = user_input["meter_model_address"]
            
            # Config Entry erstellen für SunSpec Standard Configuration
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({self._selected_template})",
                data={
                    "template": self._selected_template,
                    "template_version": template_version,
                    "prefix": user_input["prefix"],
                    "name": user_input.get("name", user_input["prefix"]),
                    "template_data": template_data,
                    "model_addresses": model_addresses,
                    "is_simple_template": True,
                    "is_sunspec_config": True,
                    "is_aggregates_template": False
                }
            )
            
        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen der SunSpec-Konfiguration: %s", str(e))
            return self.async_abort(
                reason="sunspec_config_error",
                description_placeholders={"error": str(e)}
            )

    def _validate_sunspec_config(self, user_input: dict) -> bool:
        """Validate SunSpec Standard Configuration."""
        try:
            # Pflichtfelder prüfen
            required_fields = ["prefix", "common_model_address", "inverter_model_address"]
            if not all(field in user_input for field in required_fields):
                return False
            
            # Prefix validieren (alphanumeric, lowercase, underscore)
            prefix = user_input.get("prefix", "")
            if not prefix or not prefix.replace("_", "").isalnum() or not prefix.islower():
                return False
            
            # Modell-Adressen validieren
            common_addr = user_input.get("common_model_address")
            inverter_addr = user_input.get("inverter_model_address")
            
            if not isinstance(common_addr, int) or common_addr < 1 or common_addr > 65535:
                return False
            
            if not isinstance(inverter_addr, int) or inverter_addr < 1 or inverter_addr > 65535:
                return False
            
            # Optional: Storage und Meter Adressen validieren
            if "storage_model_address" in user_input and user_input["storage_model_address"]:
                storage_addr = user_input["storage_model_address"]
                if not isinstance(storage_addr, int) or storage_addr < 1 or storage_addr > 65535:
                    return False
            
            if "meter_model_address" in user_input and user_input["meter_model_address"]:
                meter_addr = user_input["meter_model_address"]
                if not isinstance(meter_addr, int) or meter_addr < 1 or meter_addr > 65535:
                    return False
            
            return True
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Validierung der SunSpec-Konfiguration: %s", str(e))
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
            
            # Delay validieren
            delay = user_input.get("delay", 0)
            if not isinstance(delay, int) or delay < 0:
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
                    default=self.config_entry.data.get("timeout", 5)
                ): int,
                vol.Optional(
                    "delay",
                    default=self.config_entry.data.get("delay", 0)
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
