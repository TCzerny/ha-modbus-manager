"""Template Loader for Modbus Manager."""

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

import yaml
from homeassistant.core import HomeAssistant
from homeassistant.util.async_ import run_callback_threadsafe

# Global reference to Home Assistant instance for custom template loading
_hass_instance: Optional[HomeAssistant] = None


def set_hass_instance(hass: HomeAssistant) -> None:
    """Set the Home Assistant instance for custom template loading."""
    global _hass_instance
    _hass_instance = hass


from .const import (
    DEFAULT_MAX_REGISTER_READ,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_PRECISION,
    DEFAULT_UPDATE_INTERVAL,
    ControlType,
    DataType,
    RegisterType,
)
from .logger import ModbusManagerLogger

_LOGGER = logging.getLogger(__name__)

# Template-Verzeichnisse relativ zum Projekt-Root
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "device_templates")
BASE_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, "base_templates")
MAPPING_DIR = os.path.join(TEMPLATE_DIR, "manufacturer_mappings")

REQUIRED_FIELDS = {"name", "address"}
OPTIONAL_FIELDS = {
    "unique_id": "",
    "device_address": 1,
    "input_type": "input",
    "data_type": "uint16",
    "count": 1,
    "scan_interval": DEFAULT_UPDATE_INTERVAL,
    "precision": DEFAULT_PRECISION,
    "unit_of_measurement": "",
    "device_class": None,
    "state_class": None,
    "scale": 1.0,
    "swap": False,
    "byte_order": "big",  # Standard-Byte-Reihenfolge (big endian)
    "group": None,
    # Neue Felder aus modbus_connect
    "offset": 0.0,
    "multiplier": 1.0,
    "sum_scale": None,
    "shift_bits": 0,
    "bits": None,
    "bitmask": None,  # Bitmaske (z.B. 0xFF für die unteren 8 Bits)
    "bit_position": None,  # Einzelnes Bit an Position extrahieren (0-31)
    "bit_shift": 0,  # Bits nach links/rechts verschieben (positiv=links, negativ=rechts)
    "bit_rotate": 0,  # Bits rotieren (positiv=links, negativ=rechts)
    "bit_range": None,  # Bereich von Bits extrahieren [start, end]
    "float": False,
    "string": False,
    "encoding": "utf-8",  # String-Encoding (utf-8, ascii, latin1, etc.)
    "max_length": None,  # Maximale String-Länge (None = unbegrenzt)
    "control": "none",
    "min_value": DEFAULT_MIN_VALUE,
    "max_value": DEFAULT_MAX_VALUE,
    "step": 1.0,
    "options": {},
    "map": {},
    "flags": {},
    "never_resets": False,
    "entity_category": None,
    "icon": None,
    "read_function_code": None,  # Optional: Modbus function code for read (3, 4, or None for auto)
    "write_function_code": None,  # Optional: Modbus function code for write (6, 16, or None for auto)
}


async def get_custom_template_dir() -> Optional[str]:
    """Get custom template directory from Home Assistant config folder."""
    global _hass_instance
    if not _hass_instance:
        return None

    try:
        config_dir = _hass_instance.config.config_dir
        custom_dir = os.path.join(config_dir, "modbus_manager", "templates")
        if os.path.exists(custom_dir):
            return custom_dir
        return None
    except Exception as e:
        _LOGGER.debug("Could not get custom template directory: %s", str(e))
        return None


async def load_templates_from_dir(
    template_dir: str, base_templates: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Load templates from a specific directory."""
    templates = []
    try:
        loop = asyncio.get_event_loop()
        filenames = await loop.run_in_executor(None, os.listdir, template_dir)

        for filename in filenames:
            if filename.endswith((".yaml", ".yml")):
                # Skip directories
                if os.path.isdir(os.path.join(template_dir, filename)):
                    continue

                template_path = os.path.join(template_dir, filename)
                template_data = await load_single_template(
                    template_path, base_templates
                )
                if template_data:
                    # Mark as custom template
                    template_data["_is_custom"] = True
                    template_data["_custom_path"] = template_path
                    templates.append(template_data)
                    _LOGGER.debug(
                        "Loaded template from %s: %s",
                        template_dir,
                        template_data.get("name"),
                    )

    except Exception as e:
        _LOGGER.error("Error loading templates from %s: %s", template_dir, str(e))

    return templates


async def load_templates() -> List[Dict[str, Any]]:
    """Load all template files asynchronously.

    Priority:
    1. Built-in templates (from device_templates directory)
    2. Custom templates (from config/modbus_manager/templates/)
       Custom templates can override built-in templates with the same name.
    """
    try:
        # Load base templates first
        base_templates = await load_base_templates()

        # Dictionary to track templates by name (for override detection)
        templates_dict: Dict[str, Dict[str, Any]] = {}

        # 1. Load built-in templates first (PRIORITY 1)
        if not os.path.exists(TEMPLATE_DIR):
            _LOGGER.error("Template-Verzeichnis %s existiert nicht", TEMPLATE_DIR)
        else:
            loop = asyncio.get_event_loop()
            filenames = await loop.run_in_executor(None, os.listdir, TEMPLATE_DIR)

            for filename in filenames:
                if filename.endswith((".yaml", ".yml")):
                    # Skip directories
                    if os.path.isdir(os.path.join(TEMPLATE_DIR, filename)):
                        continue

                    template_path = os.path.join(TEMPLATE_DIR, filename)
                    template_data = await load_single_template(
                        template_path, base_templates
                    )
                    if template_data:
                        template_name = template_data.get("name")
                        if template_name:
                            templates_dict[template_name] = template_data
                            _LOGGER.debug("Loaded built-in template: %s", template_name)

            # Load manufacturer mappings
            if os.path.exists(MAPPING_DIR):
                mapping_files = await loop.run_in_executor(
                    None, os.listdir, MAPPING_DIR
                )
                for filename in mapping_files:
                    if filename.endswith((".yaml", ".yml")):
                        mapping_path = os.path.join(MAPPING_DIR, filename)
                        mapping_data = await load_mapping_template(
                            mapping_path, base_templates
                        )
                        if mapping_data:
                            template_name = mapping_data.get("name")
                            if template_name:
                                templates_dict[template_name] = mapping_data
                                _LOGGER.debug(
                                    "Loaded built-in mapping template: %s",
                                    template_name,
                                )

        # 2. Load custom templates (PRIORITY 2 - can override built-in)
        custom_dir = await get_custom_template_dir()
        if custom_dir:
            custom_templates = await load_templates_from_dir(custom_dir, base_templates)
            for template_data in custom_templates:
                template_name = template_data.get("name")
                if template_name:
                    if template_name in templates_dict:
                        _LOGGER.info(
                            "Custom template '%s' overrides built-in template",
                            template_name,
                        )
                    templates_dict[template_name] = template_data
                    _LOGGER.debug("Loaded custom template: %s", template_name)
        else:
            _LOGGER.debug("No custom template directory found")

        templates = list(templates_dict.values())

        _LOGGER.debug(
            "Loaded %d templates total (%d built-in, %d custom)",
            len(templates),
            len([t for t in templates if not t.get("_is_custom", False)]),
            len([t for t in templates if t.get("_is_custom", False)]),
        )
        return templates

    except Exception as e:
        _LOGGER.error("Fehler beim Laden der Templates: %s", str(e))
        return []


async def load_base_templates() -> Dict[str, Dict[str, Any]]:
    """Load all base template files asynchronously."""
    try:
        # Create base templates directory if it doesn't exist
        if not os.path.exists(BASE_TEMPLATE_DIR):
            os.makedirs(BASE_TEMPLATE_DIR)
            _LOGGER.debug("BASE-Template-Verzeichnis %s erstellt", BASE_TEMPLATE_DIR)
            return {}

        # List files in thread-safe way
        loop = asyncio.get_event_loop()
        filenames = await loop.run_in_executor(None, os.listdir, BASE_TEMPLATE_DIR)

        base_templates = {}
        for filename in filenames:
            if filename.endswith((".yaml", ".yml")):
                template_path = os.path.join(BASE_TEMPLATE_DIR, filename)
                template_data = await load_single_template(template_path, {})
                if template_data:
                    base_name = template_data.get("name")
                    if base_name:
                        base_templates[base_name] = template_data
                        # BASE-Template loaded

        # BASE-Templates loaded
        return base_templates

    except Exception as e:
        _LOGGER.error("Fehler beim Laden der BASE-Templates: %s", str(e))
        return {}


def validate_custom_register(reg: Dict[str, Any], template_name: str) -> bool:
    """Validate a custom register in a template."""
    try:
        # Required fields
        required_fields = ["name", "unique_id", "address"]
        for field in required_fields:
            if field not in reg:
                _LOGGER.error(
                    "Template %s: Custom Register fehlt Pflichtfeld %s",
                    template_name,
                    field,
                )
                return False

        # Validate address
        address = reg.get("address")
        if not isinstance(address, int) or address < 1:
            _LOGGER.error(
                "Template %s: Ungültige Adresse für Register %s: %s",
                template_name,
                reg.get("name"),
                address,
            )
            return False

        # Validate data type
        data_type = reg.get("data_type")
        valid_data_types = {
            "uint16",
            "int16",
            "uint32",
            "int32",
            "string",
            "float",
            "float64",
            "boolean",
        }
        if data_type not in valid_data_types:
            _LOGGER.error(
                "Template %s: Ungültiger data_type für Register %s: %s",
                template_name,
                reg.get("name"),
                data_type,
            )
            return False

        return True

    except Exception as e:
        _LOGGER.error(
            "Fehler bei der Validierung des Custom Registers in Template %s: %s",
            template_name,
            str(e),
        )
        return False


def validate_custom_control(ctrl: Dict[str, Any], template_name: str) -> bool:
    """Validate a custom control in a template."""
    try:
        # Required fields
        required_fields = ["type", "name", "address"]
        for field in required_fields:
            if field not in ctrl:
                _LOGGER.error(
                    "Template %s: Custom Control fehlt Pflichtfeld %s",
                    template_name,
                    field,
                )
                return False

        # Validate control type
        ctrl_type = ctrl.get("type")
        valid_control_types = {"select", "number", "button", "switch"}
        if ctrl_type not in valid_control_types:
            _LOGGER.error(
                "Template %s: Ungültiger Control-Typ für %s: %s",
                template_name,
                ctrl.get("name"),
                ctrl_type,
            )
            return False

        # Validate address
        address = ctrl.get("address")
        if not isinstance(address, int) or address < 1:
            _LOGGER.error(
                "Template %s: Ungültige Adresse für Control %s: %s",
                template_name,
                ctrl.get("name"),
                address,
            )
            return False

        # Type-specific validation
        if ctrl_type == "select":
            options = ctrl.get("options", {})
            if not isinstance(options, dict) or not options:
                _LOGGER.error(
                    "Template %s: Select-Control %s benötigt gültige options",
                    template_name,
                    ctrl.get("name"),
                )
                return False

        elif ctrl_type == "number":
            min_val = ctrl.get("min_value")
            max_val = ctrl.get("max_value")
            if min_val is not None and max_val is not None:
                if min_val >= max_val:
                    _LOGGER.error(
                        "Template %s: Ungültige min/max Werte für Control %s: min=%s, max=%s",
                        template_name,
                        ctrl.get("name"),
                        min_val,
                        max_val,
                    )
                    return False

        return True

    except Exception as e:
        _LOGGER.error(
            "Fehler bei der Validierung des Custom Controls in Template %s: %s",
            template_name,
            str(e),
        )
        return False


def process_simple_template(
    template_data: Dict[str, Any],
    base_template: Dict[str, Any],
    user_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Process a simple template that only requires prefix and name."""
    try:
        _LOGGER.debug(
            "Verarbeite vereinfachtes Template: %s", template_data.get("name")
        )

        # Extract required fields from user configuration
        prefix = user_config.get("prefix")
        device_name = user_config.get("name", prefix)  # Use prefix as fallback

        if not prefix:
            _LOGGER.error("Prefix ist erforderlich für vereinfachte Templates")
            return {}

        # Regular template processing
        # Use sensors directly from template_data

        # Process sensors from template_data
        processed_sensors = []
        for sensor in template_data.get("sensors", []):
            # Create a copy and add prefix to unique_id
            processed_sensor = dict(sensor)
            sensor_name = processed_sensor.get("name", "").lower().replace(" ", "_")
            if "unique_id" not in processed_sensor:
                processed_sensor["unique_id"] = f"{prefix}_{sensor_name}"
            elif not processed_sensor["unique_id"].startswith(f"{prefix}_"):
                processed_sensor[
                    "unique_id"
                ] = f"{prefix}_{processed_sensor['unique_id']}"
            if "default_entity_id" not in processed_sensor:
                default_entity_id = processed_sensor.get("unique_id")
                processed_sensor["default_entity_id"] = (
                    default_entity_id.lower()
                    if isinstance(default_entity_id, str)
                    else default_entity_id
                )
            processed_sensors.append(processed_sensor)

        filtered_registers = processed_sensors

        # Process calculated sensors
        calculated_sensors = template_data.get("calculated_sensors", [])
        for calc_sensor in calculated_sensors:
            # Replace {PREFIX} placeholder with actual prefix
            if "state" in calc_sensor:
                calc_sensor["state"] = calc_sensor["state"].replace("{PREFIX}", prefix)

            # Add prefix to unique_id using generate_unique_id for consistency
            from .device_utils import generate_unique_id

            calc_sensor["unique_id"] = generate_unique_id(
                prefix=prefix,
                template_unique_id=calc_sensor.get("unique_id"),
                name=calc_sensor.get("name", ""),
            )
            if "default_entity_id" not in calc_sensor:
                default_entity_id = calc_sensor.get("unique_id")
                calc_sensor["default_entity_id"] = (
                    default_entity_id.lower()
                    if isinstance(default_entity_id, str)
                    else default_entity_id
                )

        # Process sensors for placeholder replacement
        sensors = template_data.get("sensors", [])
        for sensor in sensors:
            # Replace {BATTERY_SLAVE_ID} placeholder with connection slave_id
            if "slave_id" in sensor and "{BATTERY_SLAVE_ID}" in str(sensor["slave_id"]):
                connection_slave_id = user_config.get("slave_id", 1)
                sensor["slave_id"] = sensor["slave_id"].replace(
                    "{BATTERY_SLAVE_ID}", str(connection_slave_id)
                )

        # Process controls
        controls = template_data.get("controls", [])
        for control in controls:
            # Add prefix to unique_id using generate_unique_id for consistency
            from .device_utils import generate_unique_id

            control["unique_id"] = generate_unique_id(
                prefix=prefix,
                template_unique_id=control.get("unique_id"),
                name=control.get("name", ""),
            )
            if "default_entity_id" not in control:
                default_entity_id = control.get("unique_id")
                control["default_entity_id"] = (
                    default_entity_id.lower()
                    if isinstance(default_entity_id, str)
                    else default_entity_id
                )

        # Create final template data
        processed_template = {
            "name": device_name,
            "prefix": prefix,
            "sensors": filtered_registers,
            "calculated_sensors": calculated_sensors,
            "controls": controls,
            "template_info": template_data.get("template_info", {}),
        }

        _LOGGER.debug(
            "Vereinfachtes Template verarbeitet: %d Sensoren, %d berechnete Sensoren, %d Steuerelemente",
            len(filtered_registers),
            len(calculated_sensors),
            len(controls),
        )

        return processed_template

    except Exception as e:
        _LOGGER.error(
            "Fehler bei der Verarbeitung des vereinfachten Templates: %s", str(e)
        )
        return {}


async def process_simple_template_with_config(
    template_info: Dict[str, Any], user_config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Process a simple template with user configuration."""
    try:
        template_data = template_info.get("template_data")
        base_template = template_info.get("base_template")

        if not template_data or not base_template:
            _LOGGER.error("Ungültige Template-Informationen für vereinfachtes Template")
            return None

        # Process the simple template with user config
        processed_template = process_simple_template(
            template_data, base_template, user_config
        )

        if not processed_template:
            _LOGGER.error("Fehler bei der Verarbeitung des vereinfachten Templates")
            return None

        # Validate and process registers
        validated_registers = []
        for reg in processed_template.get("sensors", []):
            validated_reg = validate_and_process_register(
                reg, processed_template.get("name")
            )
            if validated_reg:
                validated_reg["template"] = processed_template.get("name")
                validated_registers.append(validated_reg)

        # Update processed template with validated registers
        processed_template["sensors"] = validated_registers

        _LOGGER.debug(
            "Vereinfachtes Template erfolgreich verarbeitet: %s",
            processed_template.get("name"),
        )
        return processed_template

    except Exception as e:
        _LOGGER.error(
            "Fehler bei der Verarbeitung des vereinfachten Templates mit Konfiguration: %s",
            str(e),
        )
        return None


async def load_single_template(
    template_path: str, base_templates: Dict[str, Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Load a single template file asynchronously."""
    try:
        # Read file in thread-safe way
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _read_template_file, template_path)

        if not data:
            _LOGGER.error("Template %s ist leer", template_path)
            return None

        # Template-Metadaten extrahieren
        template_name = data.get("name")
        if not template_name:
            _LOGGER.error("Template %s hat keinen Namen", template_path)
            return None

        # _LOGGER.debug("Processing template %s", template_name)

        # Check if template extends a base template
        extends_name = data.get("extends")
        if extends_name and base_templates and extends_name in base_templates:
            # Extend from base template
            base_template = base_templates[extends_name]
            # _LOGGER.debug("Template %s erweitert BASE-Template %s", template_name, extends_name)

            # Check if this is a simple template (requires only prefix and name)
            if "required_fields" in data and "auto_generated_sensors" in data:
                # _LOGGER.debug("Template %s ist ein vereinfachtes Template", template_name)
                # Simple templates are processed later when user config is available
                # For now, just return the template data for later processing
                return {
                    "name": template_name,
                    "template_data": data,
                    "base_template": base_template,
                    "is_simple_template": True,
                }

                # Process register mappings if present (legacy approach)
                register_mapping = data.get("register_mapping", {})

                # Start with base template registers
                base_registers = base_template.get("sensors", [])

                # Apply mappings to base registers
                mapped_registers = []
                for reg in base_registers:
                    # Create a copy of the register to avoid modifying the original
                    mapped_reg = dict(reg)

                    # Apply address mapping if present
                    reg_name = reg.get("name")
                    if reg_name in register_mapping:
                        mapped_address = register_mapping[reg_name]
                        _LOGGER.debug(
                            "Mapping register %s from address %s to %s",
                            reg_name,
                            mapped_reg.get("address"),
                            mapped_address,
                        )
                        mapped_reg["address"] = mapped_address

                    mapped_registers.append(mapped_reg)

                # Use the combined registers
                raw_registers = mapped_registers

            # Add custom registers if present
            custom_registers = data.get("custom_registers", [])
            if custom_registers:
                _LOGGER.debug(
                    "Adding %d custom registers to template %s",
                    len(custom_registers),
                    template_name,
                )
                raw_registers.extend(custom_registers)

            # Include calculated entities from base template
            base_calculated = base_template.get("calculated", [])
            custom_calculated = data.get("calculated", [])

            # Combine calculated entities, avoiding duplicates by unique_id
            calculated_entities = list(
                base_calculated
            )  # Make a copy to avoid modifying the original
            custom_calculated_ids = {
                calc.get("unique_id")
                for calc in custom_calculated
                if "unique_id" in calc
            }

            # Remove base calculated entities that are overridden by custom ones
            calculated_entities = [
                calc
                for calc in calculated_entities
                if "unique_id" not in calc
                or calc["unique_id"] not in custom_calculated_ids
            ]

            # Add custom calculated entities
            calculated_entities.extend(custom_calculated)

            # Include controls from base template
            base_controls = base_template.get("controls", [])
            custom_controls = data.get("custom_controls", [])

            # Combine controls, avoiding duplicates by name
            controls = list(
                base_controls
            )  # Make a copy to avoid modifying the original
            custom_control_names = {
                ctrl.get("name") for ctrl in custom_controls if "name" in ctrl
            }

            # Remove base controls that are overridden by custom ones
            controls = [
                ctrl
                for ctrl in controls
                if "name" not in ctrl or ctrl["name"] not in custom_control_names
            ]

            # Add custom controls
            controls.extend(custom_controls)

        else:
            # Standard template processing
            raw_registers = data.get("sensors", [])
            calculated_entities = data.get("calculated", [])
            controls = data.get("controls", [])
            if not raw_registers:
                # Allow empty base templates
                if "type" in data and data["type"] == "base_template":
                    _LOGGER.debug(
                        "Template %s is base template (no sensors expected)",
                        template_name,
                    )
                    raw_registers = []
                else:
                    _LOGGER.warning("Template %s has no sensors defined", template_name)
                    return None

        # _LOGGER.debug("Template %s: %d sensors found", template_name, len(raw_registers))

        validated_registers = []
        for reg in raw_registers:
            validated_reg = validate_and_process_register(reg, template_name)
            if validated_reg:
                # Add template name to each register
                validated_reg["template"] = template_name
                validated_registers.append(validated_reg)
            else:
                _LOGGER.warning(
                    "Register %s in Template %s could not be validated",
                    reg.get("name", "unknown"),
                    template_name,
                )

        # For base templates, allow empty register lists
        if not validated_registers and not (
            "type" in data and data["type"] == "base_template"
        ):
            _LOGGER.error("Template %s has no valid registers", template_name)
            return None

        # _LOGGER.debug("Template %s: %d valid registers processed", template_name, len(validated_registers))

        # Process calculated section if present
        if calculated_entities:
            pass  # _LOGGER.debug("Template %s: %d calculated entities found", template_name, len(calculated_entities))

        # Process controls section if present
        # Controls processed

        # Process binary sensors if present
        binary_sensors = data.get("binary_sensors", [])

        # Template structure summary (only log if there are issues)
        template_type = data.get("type", "device_template")
        is_base_template = template_type == "base_template"

        if (
            len(validated_registers) == 0
            and len(calculated_entities) == 0
            and len(binary_sensors) == 0
            and len(controls) == 0
            and not is_base_template
        ):
            _LOGGER.warning("Template %s: No entities found", template_name)

        result = {
            "name": template_name,
            "sensors": validated_registers,
            "calculated": calculated_entities,
            "binary_sensors": binary_sensors,
            "controls": controls,
            "type": data.get("type", "device_template"),
            "version": data.get("version", 1),
            "description": data.get("description", ""),
            "manufacturer": data.get("manufacturer", ""),
            "model": data.get("model", ""),
            "default_prefix": data.get("default_prefix", "device"),
            "firmware_version": data.get("firmware_version", "1.0.0"),
            "available_firmware_versions": data.get("available_firmware_versions", []),
        }

        # Include dynamic_config if present
        if "dynamic_config" in data:
            result["dynamic_config"] = data["dynamic_config"]
            _LOGGER.debug("Template %s includes dynamic_config", template_name)

        # Add extends information if present
        if extends_name:
            result["extends"] = extends_name

        return result

    except yaml.YAMLError as e:
        _LOGGER.error("YAML-Fehler in Template %s: %s", template_path, str(e))
        return None
    except Exception as e:
        _LOGGER.error(
            "Unerwarteter Fehler beim Laden von Template %s: %s", template_path, str(e)
        )
        return None


def _read_template_file(template_path: str) -> Optional[Dict[str, Any]]:
    """Read template file synchronously (called in executor)."""
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        _LOGGER.error("Fehler beim Lesen von Template %s: %s", template_path, str(e))
        return None


async def process_template_registers(
    template_data: Dict[str, Any], dynamic_config: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """Process template registers with current processing logic."""
    try:
        # Validate template_data is a dictionary
        if not isinstance(template_data, dict):
            _LOGGER.error(
                "Template data is not a dictionary, got type: %s", type(template_data)
            )
            return []

        template_name = template_data.get("name", "unknown")
        _LOGGER.debug("Processing template registers for %s", template_name)

        # Get registers from template
        registers = template_data.get("sensors", [])
        if not registers:
            _LOGGER.warning("No registers found in template %s", template_name)
            return []

        # Apply dynamic config filtering if dynamic_config is provided
        if dynamic_config:
            _LOGGER.debug(
                "Applying dynamic config filtering to %d registers", len(registers)
            )
            filtered_registers = []

            # Extract dynamic config parameters - now generic for any field
            phases = dynamic_config.get("phases", 3)
            mppt_count = dynamic_config.get("mppt_count", 2)
            modules = dynamic_config.get("modules", 0)
            string_count = dynamic_config.get("string_count", 0)
            battery_config = dynamic_config.get("battery_config", "none")
            battery_enabled = battery_config != "none"
            battery_type = battery_config
            # Use connection slave_id instead of separate battery_slave_id
            battery_slave_id = dynamic_config.get("slave_id", 1)
            firmware_version = dynamic_config.get(
                "firmware_version", "SAPPHIRE-H_03011.95.01"
            )
            connection_type = dynamic_config.get("connection_type", "LAN")

            # Log all dynamic config values for debugging
            config_items = []
            for key, value in dynamic_config.items():
                if key not in [
                    "firmware_version",
                    "connection_type",
                    "meter_type",  # Logged separately below
                ]:  # Skip verbose ones
                    config_items.append(f"{key}={value}")

            meter_type = dynamic_config.get("meter_type", "not_set")
            _LOGGER.info(
                "Dynamic config: %s, fw=%s, conn=%s, meter_type=%s",
                ", ".join(config_items),
                firmware_version,
                connection_type,
                meter_type,
            )

            # Apply filtering logic (same as in config_flow.py)
            for reg in registers:
                if _should_include_sensor(
                    reg,
                    phases,
                    mppt_count,
                    battery_enabled,
                    battery_type,
                    battery_slave_id,
                    firmware_version,
                    connection_type,
                    dynamic_config,
                    string_count,
                ):
                    filtered_registers.append(reg)

            _LOGGER.info(
                "Dynamic config filtering: %d registers passed filter from %d original",
                len(filtered_registers),
                len(registers),
            )
            registers = filtered_registers

        # Process each register with current validation logic
        processed_registers = []
        for reg in registers:
            processed_reg = validate_and_process_register(reg, template_name)
            if processed_reg:
                processed_registers.append(processed_reg)

        _LOGGER.info(
            "Processed %d registers for template %s",
            len(processed_registers),
            template_name,
        )
        return processed_registers

    except Exception as e:
        _LOGGER.error("Error processing template registers: %s", str(e))
        return []


def _should_include_sensor(
    sensor: dict,
    phases: int,
    mppt_count: int,
    battery_enabled: bool,
    battery_type: str,
    battery_slave_id: int,
    firmware_version: str,
    connection_type: str,
    dynamic_config: dict,
    string_count: int = 0,
) -> bool:
    """Check if sensor should be included based on configuration."""
    sensor_name = sensor.get("name", "")
    unique_id = sensor.get("unique_id", "").lower()

    # Check if name contains module number and compare with actual modules
    if "module" in sensor_name.lower():
        # Extract module number from name like "Battery 1 Max Cell Voltage of Module 5"
        module_match = re.search(r"module\s+(\d+)", sensor_name.lower())
        if module_match:
            module_number = int(module_match.group(1))
            actual_modules = dynamic_config.get("modules", 0)

            _LOGGER.debug(
                "Checking module number from name '%s': module=%d, actual_modules=%d",
                sensor_name,
                module_number,
                actual_modules,
            )

            if module_number > actual_modules:
                _LOGGER.info(
                    "Excluding sensor due to module number in name: %s (module=%d, actual_modules=%d)",
                    sensor_name,
                    module_number,
                    actual_modules,
                )
                return False

    # Check condition filter first
    condition = sensor.get("condition")
    if condition:
        # Support AND conditions: "battery_enabled == true and meter_type != 'iHomeManager'"
        if " and " in condition:
            # Split by " and " and evaluate each part - ALL must be true
            condition_parts = [part.strip() for part in condition.split(" and ")]
            condition_met = True
            for part in condition_parts:
                if not _evaluate_single_condition(part, dynamic_config):
                    condition_met = False
                    break
            if not condition_met:
                _LOGGER.info(
                    "Excluding sensor due to AND condition '%s': %s (unique_id: %s)",
                    condition,
                    sensor.get("name", "unknown"),
                    sensor.get("unique_id", "unknown"),
                )
                return False
        # Support OR conditions: "meter_type == 'DTSU666' or meter_type == 'DTSU666-20'"
        elif " or " in condition:
            # Split by " or " and evaluate each part
            condition_parts = [part.strip() for part in condition.split(" or ")]
            condition_met = False
            for part in condition_parts:
                if _evaluate_single_condition(part, dynamic_config):
                    condition_met = True
                    break
            if not condition_met:
                _LOGGER.info(
                    "Excluding sensor due to OR condition '%s': %s (unique_id: %s)",
                    condition,
                    sensor.get("name", "unknown"),
                    sensor.get("unique_id", "unknown"),
                )
                return False
        else:
            # Single condition evaluation
            if not _evaluate_single_condition(condition, dynamic_config):
                _LOGGER.info(
                    "Excluding sensor due to condition '%s': %s (unique_id: %s)",
                    condition,
                    sensor.get("name", "unknown"),
                    sensor.get("unique_id", "unknown"),
                )
                return False

    # Legacy condition parsing (kept for backward compatibility with old format)
    # This handles old conditions that don't use the new _evaluate_single_condition function
    # Can be removed once all templates are migrated
    condition_legacy = sensor.get("condition")
    if condition_legacy and " or " not in condition_legacy:
        # Parse condition like "modules >= 5", "phases == 3", or "dual_channel_meter == true"
        # Extract variable name and operator
        if "==" in condition_legacy:
            try:
                parts = condition.split("==")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip()

                    # Get actual value from dynamic_config
                    actual_value = dynamic_config.get(variable_name)

                    # Try to convert to bool first (for true/false)
                    if required_value_str.lower() in ["true", "false"]:
                        required_value = required_value_str.lower() == "true"
                        actual_value = (
                            bool(actual_value) if actual_value is not None else False
                        )
                    else:
                        # Try to convert to int, then string
                        try:
                            required_value = int(required_value_str)
                            actual_value = (
                                int(actual_value) if actual_value is not None else 0
                            )
                        except (ValueError, TypeError):
                            required_value = required_value_str
                            actual_value = (
                                str(actual_value) if actual_value is not None else ""
                            )

                    _LOGGER.debug(
                        "Checking condition '%s' for sensor %s: required=%s, actual=%s",
                        condition,
                        sensor.get("name", "unknown"),
                        required_value,
                        actual_value,
                    )

                    if actual_value != required_value:
                        _LOGGER.info(
                            "Excluding sensor due to condition '%s': %s (unique_id: %s, required: %s, actual: %s)",
                            condition,
                            sensor.get("name", "unknown"),
                            sensor.get("unique_id", "unknown"),
                            required_value,
                            actual_value,
                        )
                        return False
            except (ValueError, IndexError) as e:
                _LOGGER.warning(
                    "Invalid condition '%s' for sensor %s: %s",
                    condition,
                    sensor.get("name", "unknown"),
                    str(e),
                )
        elif ">=" in condition:
            try:
                parts = condition.split(">=")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip()

                    # Try to convert to int first, if that fails try as string
                    try:
                        required_value = int(required_value_str)
                        actual_value = dynamic_config.get(variable_name, 0)
                        # Ensure actual_value is also int for comparison
                        if isinstance(actual_value, str):
                            actual_value = int(actual_value)
                    except ValueError:
                        # If conversion to int fails, treat as string comparison
                        required_value = required_value_str
                        actual_value = str(dynamic_config.get(variable_name, ""))

                    _LOGGER.debug(
                        "Checking condition '%s' for sensor %s: required=%s, actual=%s",
                        condition,
                        sensor.get("name", "unknown"),
                        required_value,
                        actual_value,
                    )

                    if actual_value < required_value:
                        _LOGGER.info(
                            "Excluding sensor due to condition '%s': %s (unique_id: %s, required: %s, actual: %s)",
                            condition,
                            sensor.get("name", "unknown"),
                            sensor.get("unique_id", "unknown"),
                            required_value,
                            actual_value,
                        )
                        return False
            except (ValueError, IndexError) as e:
                _LOGGER.warning(
                    "Invalid condition '%s' for sensor %s: %s",
                    condition,
                    sensor.get("name", "unknown"),
                    str(e),
                )

    # Check both sensor_name and unique_id for filtering
    search_text = f"{sensor_name.lower()} {unique_id}".lower()

    # Debug: Log what we're checking
    _LOGGER.debug(
        "Checking sensor: name='%s', unique_id='%s', search_text='%s'",
        sensor_name,
        unique_id,
        search_text,
    )

    # Phase-specific sensors
    if phases == 1:
        # Exclude phase B and C sensors for single phase
        if any(
            phase in search_text
            for phase in ["phase_b", "phase_c", "phase b", "phase c"]
        ):
            _LOGGER.info(
                "Excluding sensor due to single phase config: %s (unique_id: %s)",
                sensor.get("name", "unknown"),
                sensor.get("unique_id", "unknown"),
            )
            return False
    elif phases == 3:
        # Include all phase sensors
        pass

    # MPPT-specific sensors
    if "mppt" in search_text:
        # Extract MPPT number from sensor name or unique_id
        mppt_number = _extract_mppt_number(search_text)
        if mppt_number and mppt_number > mppt_count:
            _LOGGER.info(
                "Excluding sensor due to MPPT count config: %s (unique_id: %s, MPPT %d > %d)",
                sensor.get("name", "unknown"),
                sensor.get("unique_id", "unknown"),
                mppt_number,
                mppt_count,
            )
            return False

    # String-specific sensors
    if "string" in search_text:
        # Extract string number from sensor name or unique_id
        string_number = _extract_string_number(search_text)
        if string_number and string_number > string_count:
            _LOGGER.info(
                "Excluding sensor due to string count config: %s (unique_id: %s, String %d > %d)",
                sensor.get("name", "unknown"),
                sensor.get("unique_id", "unknown"),
                string_number,
                string_count,
            )
            return False

    # Battery-specific sensors (general keywords)
    if not battery_enabled:
        battery_keywords = ["battery", "bms", "soc", "charge", "discharge", "backup"]
        if any(keyword in search_text for keyword in battery_keywords):
            _LOGGER.info(
                "Excluding sensor due to battery disabled: %s (unique_id: %s)",
                sensor.get("name", "unknown"),
                sensor.get("unique_id", "unknown"),
            )
            return False

    # Battery type specific sensors (SBR Battery)
    sensor_group = sensor.get("group", "")
    if battery_type == "none":
        # No battery selected - exclude all battery sensors (already handled by battery_enabled check above)
        pass
    elif battery_type == "standard_battery":
        # Standard Battery selected - exclude battery sensors (they are now separate)
        if sensor_group in ["battery", "battery_cells"]:
            _LOGGER.info(
                "Excluding sensor due to standard battery selected: %s (unique_id: %s)",
                sensor.get("name", "unknown"),
                sensor.get("unique_id", "unknown"),
            )
            return False

    # Firmware version specific sensors
    sensor_firmware_min = sensor.get("firmware_min_version")
    if sensor_firmware_min:
        from packaging import version

        try:
            # Compare firmware versions
            current_ver = version.parse(firmware_version)
            min_ver = version.parse(sensor_firmware_min)
            if current_ver < min_ver:
                _LOGGER.info(
                    "Excluding sensor due to firmware version: %s (unique_id: %s, requires: %s, current: %s)",
                    sensor.get("name", "unknown"),
                    sensor.get("unique_id", "unknown"),
                    sensor_firmware_min,
                    firmware_version,
                )
                return False
        except version.InvalidVersion:
            # Fallback to string comparison for non-semantic versions
            if firmware_version < sensor_firmware_min:
                _LOGGER.info(
                    "Excluding sensor due to firmware version (string): %s (unique_id: %s, requires: %s, current: %s)",
                    sensor.get("name", "unknown"),
                    sensor.get("unique_id", "unknown"),
                    sensor_firmware_min,
                    firmware_version,
                )
                return False

    # Connection type specific sensors
    connection_config = dynamic_config.get("connection_type", {}).get(
        "sensor_availability", {}
    )
    if connection_type == "LAN":
        # Exclude WINET-only sensors
        winet_only_sensors = connection_config.get("winet_only_sensors", [])
        if unique_id in winet_only_sensors:
            _LOGGER.info(
                "Excluding sensor due to LAN connection: %s (unique_id: %s)",
                sensor.get("name", "unknown"),
                sensor.get("unique_id", "unknown"),
            )
            return False
    elif connection_type == "WINET":
        # Exclude LAN-only sensors
        lan_only_sensors = connection_config.get("lan_only_sensors", [])
        if unique_id in lan_only_sensors:
            _LOGGER.info(
                "Excluding sensor due to WINET connection: %s (unique_id: %s)",
                sensor.get("name", "unknown"),
                sensor.get("unique_id", "unknown"),
            )
            return False

    return True


def _evaluate_single_condition(condition: str, dynamic_config: dict) -> bool:
    """Evaluate a single condition (without OR/AND support).

    Supports:
    - "variable == value" (string, int, bool)
    - "variable != value" (string, int, bool)
    - "variable >= value" (int)
    - "variable in [value1, value2]" (string list)
    """
    condition = condition.strip()

    if " not in " in condition:
        try:
            parts = condition.split(" not in ")
            if len(parts) == 2:
                variable_name = parts[0].strip()
                required_values_str = parts[1].strip()

                actual_value = dynamic_config.get(variable_name)

                if required_values_str.startswith("[") and required_values_str.endswith(
                    "]"
                ):
                    required_values_str = required_values_str[1:-1]
                required_values = [
                    value.strip().strip("'\"")
                    for value in required_values_str.split(",")
                    if value.strip()
                ]

                if isinstance(actual_value, (list, tuple, set)):
                    actual_values = {str(value) for value in actual_value}
                    result = not any(
                        value in actual_values for value in required_values
                    )
                else:
                    result = str(actual_value) not in required_values

                _LOGGER.debug(
                    "Evaluating condition '%s': variable=%s, required=%s, actual=%s, result=%s",
                    condition,
                    variable_name,
                    required_values,
                    actual_value,
                    result,
                )
                return result
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
            return False
    elif " in " in condition:
        try:
            parts = condition.split(" in ")
            if len(parts) == 2:
                variable_name = parts[0].strip()
                required_values_str = parts[1].strip()

                actual_value = dynamic_config.get(variable_name)

                if required_values_str.startswith("[") and required_values_str.endswith(
                    "]"
                ):
                    required_values_str = required_values_str[1:-1]
                required_values = [
                    value.strip().strip("'\"")
                    for value in required_values_str.split(",")
                    if value.strip()
                ]

                if isinstance(actual_value, (list, tuple, set)):
                    actual_values = {str(value) for value in actual_value}
                    result = any(value in actual_values for value in required_values)
                else:
                    result = str(actual_value) in required_values

                _LOGGER.debug(
                    "Evaluating condition '%s': variable=%s, required=%s, actual=%s, result=%s",
                    condition,
                    variable_name,
                    required_values,
                    actual_value,
                    result,
                )
                return result
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
            return False
    elif "!=" in condition:
        try:
            parts = condition.split("!=")
            if len(parts) == 2:
                variable_name = parts[0].strip()
                required_value_str = parts[1].strip().strip("'\"")  # Remove quotes

                # Get actual value from dynamic_config
                actual_value = dynamic_config.get(variable_name)

                # Try to convert to bool first (for true/false)
                if required_value_str.lower() in ["true", "false"]:
                    required_value = required_value_str.lower() == "true"
                    actual_value = (
                        bool(actual_value) if actual_value is not None else False
                    )
                else:
                    # Try to convert to int, then string
                    try:
                        required_value = int(required_value_str)
                        actual_value = (
                            int(actual_value) if actual_value is not None else 0
                        )
                    except (ValueError, TypeError):
                        required_value = required_value_str
                        actual_value = (
                            str(actual_value) if actual_value is not None else ""
                        )

                result = actual_value != required_value
                _LOGGER.debug(
                    "Evaluating condition '%s': variable=%s, required=%s, actual=%s, result=%s",
                    condition,
                    variable_name,
                    required_value,
                    actual_value,
                    result,
                )
                return result
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
            return False
    elif "==" in condition:
        try:
            parts = condition.split("==")
            if len(parts) == 2:
                variable_name = parts[0].strip()
                required_value_str = parts[1].strip().strip("'\"")  # Remove quotes

                # Get actual value from dynamic_config
                actual_value = dynamic_config.get(variable_name)

                # Try to convert to bool first (for true/false)
                if required_value_str.lower() in ["true", "false"]:
                    required_value = required_value_str.lower() == "true"
                    actual_value = (
                        bool(actual_value) if actual_value is not None else False
                    )
                else:
                    # Try to convert to int, then string
                    try:
                        required_value = int(required_value_str)
                        actual_value = (
                            int(actual_value) if actual_value is not None else 0
                        )
                    except (ValueError, TypeError):
                        required_value = required_value_str
                        actual_value = (
                            str(actual_value) if actual_value is not None else ""
                        )

                result = actual_value == required_value
                _LOGGER.debug(
                    "Evaluating condition '%s': variable=%s, required=%s, actual=%s, result=%s",
                    condition,
                    variable_name,
                    required_value,
                    actual_value,
                    result,
                )
                return result
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
            return False

    elif ">=" in condition:
        try:
            parts = condition.split(">=")
            if len(parts) == 2:
                variable_name = parts[0].strip()
                required_value_str = parts[1].strip()

                try:
                    required_value = int(required_value_str)
                    actual_value = dynamic_config.get(variable_name, 0)
                    if isinstance(actual_value, str):
                        actual_value = int(actual_value)
                    return actual_value >= required_value
                except ValueError:
                    return False
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
            return False

    # Unknown condition format - return True to be safe (include sensor)
    _LOGGER.warning("Unknown condition format '%s', including sensor", condition)
    return True


def _extract_mppt_number(search_text: str) -> int:
    """Extract MPPT number from sensor name or unique_id."""
    import re

    match = re.search(r"mppt(\d+)", search_text.lower())
    return int(match.group(1)) if match else None


def _extract_string_number(search_text: str) -> int:
    """Extract string number from sensor name or unique_id."""
    import re

    match = re.search(r"string(\d+)", search_text.lower())
    return int(match.group(1)) if match else None


def validate_and_process_register(
    reg: Dict[str, Any], template_name: str
) -> Dict[str, Any]:
    """Validate and process a single register definition."""
    try:
        # Pflichtfelder prüfen
        if not all(field in reg for field in REQUIRED_FIELDS):
            missing_fields = REQUIRED_FIELDS - set(reg.keys())
            _LOGGER.warning(
                "Register in Template %s fehlt Pflichtfelder: %s",
                template_name,
                missing_fields,
            )
            return None

        # Pflichtfelder hinzufügen
        processed_reg = {}
        for field in REQUIRED_FIELDS:
            processed_reg[field] = reg[field]

        # Handle count parameter: only use template value if explicitly set
        data_type = reg.get("data_type")
        template_count = reg.get("count")

        if template_count is not None:
            # Use count from template if explicitly set
            processed_reg["count"] = template_count
            # Using count from template
        else:
            # Don't set count here - let sensor init handle defaults based on data_type
            # This allows the sensor to determine the correct count based on data_type
            processed_reg["count"] = None
            # No count specified - will use data_type-based defaults in sensor init

        # Standardwerte für optionale Felder setzen (skip count - handled above)
        for field, default_value in OPTIONAL_FIELDS.items():
            if field not in processed_reg and field != "count":
                processed_reg[field] = reg.get(field, default_value)

        # Zusätzliche Felder aus dem Template übernehmen
        for field, value in reg.items():
            if field not in processed_reg:
                processed_reg[field] = value

        # Entity-Typ bestimmen
        processed_reg["entity_type"] = determine_entity_type(processed_reg)

        # Validate register
        if not validate_register_data(processed_reg, template_name):
            return None

        return processed_reg

    except Exception as e:
        _LOGGER.error(
            "Error processing register in Template %s: %s", template_name, str(e)
        )
        return None


def determine_entity_type(register_data: Dict[str, Any]) -> str:
    """Determine the appropriate entity type based on register configuration."""
    control = register_data.get("control", "none")

    if control == "number":
        return "number"
    elif control == "select":
        return "select"
    elif control == "switch":
        return "switch"
    elif control == "button":
        return "button"
    elif control == "text":
        return "text"
    elif register_data.get("data_type") == "boolean":
        return "binary_sensor"
    else:
        return "sensor"


def validate_register_data(reg: Dict[str, Any], template_name: str) -> bool:
    """Validate register data for consistency."""
    try:
        # Validate address
        address = reg.get("address")
        if not isinstance(address, int) or address < 0:
            _LOGGER.error("Invalid address in Template %s: %s", template_name, address)
            return False

        # Validate data type
        data_type = reg.get("data_type")
        valid_data_types = {
            "uint16",
            "int16",
            "uint32",
            "int32",
            "string",
            "float",
            "float32",
            "float64",
            "boolean",
        }
        if data_type not in valid_data_types:
            _LOGGER.error(
                "Invalid data_type in Template %s: %s", template_name, data_type
            )
            return False

        # Validate count (allow None for sensor init to handle defaults)
        count = reg.get("count")
        if count is not None and (not isinstance(count, int) or count < 1):
            _LOGGER.error("Invalid count in Template %s: %s", template_name, count)
            return False

        # Float-specific validation (only if count is specified)
        if data_type in ["float", "float32", "float64"] and count is not None:
            # Float type requires at least 2 registers for 32-bit and 4 registers for 64-bit
            min_count = 2 if data_type in ["float", "float32"] else 4
            if count < min_count:
                _LOGGER.error(
                    "Float type %s in Template %s requires at least %d registers, but count=%d",
                    data_type,
                    template_name,
                    min_count,
                    count,
                )
                return False

        # Validate scale
        scale = reg.get("scale")
        if not isinstance(scale, (int, float)) or scale <= 0:
            _LOGGER.error("Invalid scale in Template %s: %s", template_name, scale)
            return False

        # Validate scan interval
        scan_interval = reg.get("scan_interval")
        if not isinstance(scan_interval, int) or scan_interval < 0:
            _LOGGER.error(
                "Invalid scan_interval in Template %s: %s", template_name, scan_interval
            )
            return False

        # Validate scan interval range (0 = never update, 1-3600 = normal range)
        register_name = reg.get("name", "unknown")

        # Control-specific validation
        if not validate_control_settings(reg, template_name):
            return False

        # Validate sum_scale
        sum_scale = reg.get("sum_scale")
        if sum_scale is not None:
            if not isinstance(sum_scale, list) or not all(
                isinstance(x, (int, float)) for x in sum_scale
            ):
                _LOGGER.error(
                    "Invalid sum_scale in Template %s: %s", template_name, sum_scale
                )
                return False

        # Validate options for Select entities
        if reg.get("control") == "select":
            options = reg.get("options", {})
            if not isinstance(options, dict) or not options:
                _LOGGER.error(
                    "Select entity in Template %s requires valid options", template_name
                )
                return False

        return True

    except Exception as e:
        _LOGGER.error(
            "Error in data validation in Template %s: %s", template_name, str(e)
        )
        return False


def validate_control_settings(reg: Dict[str, Any], template_name: str) -> bool:
    """Validate control-specific settings."""
    try:
        control = reg.get("control", "none")

        if control == "number":
            min_val = reg.get("min_value")
            max_val = reg.get("max_value")
            if min_val is not None and max_val is not None:
                if min_val >= max_val:
                    _LOGGER.error(
                        "Invalid min/max values in Template %s: min=%s, max=%s",
                        template_name,
                        min_val,
                        max_val,
                    )
                    return False

        elif control == "switch":
            switch_config = reg.get("switch", {})
            if switch_config:
                on_val = switch_config.get("on", 1)
                off_val = switch_config.get("off", 0)
                if on_val == off_val:
                    _LOGGER.error(
                        "Switch on/off values must be different in Template %s",
                        template_name,
                    )
                    return False

        return True

    except Exception as e:
        _LOGGER.error(
            "Error in control validation in Template %s: %s", template_name, str(e)
        )
        return False


async def get_template_names() -> List[str]:
    """Get list of available template names."""
    templates = await load_templates()
    return [template["name"] for template in templates]


async def load_mapping_template(
    mapping_path: str, base_templates: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Load a manufacturer mapping template file."""
    try:
        # Use the standard template loader with base templates
        mapping_data = await load_single_template(mapping_path, base_templates)

        if mapping_data and "extends" in mapping_data:
            _LOGGER.debug(
                "Loaded mapping template %s extending %s",
                mapping_data.get("name"),
                mapping_data.get("extends"),
            )
            return mapping_data
        else:
            _LOGGER.warning(
                "Mapping template %s does not extend a base template", mapping_path
            )
            return None

    except Exception as e:
        _LOGGER.error("Error loading mapping template %s: %s", mapping_path, str(e))
        return None


async def get_template_by_name(template_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific template by name - optimized to load only the needed template.

    Priority:
    1. Check custom templates first (can override built-in)
    2. Check built-in templates
    3. Check manufacturer mappings
    """
    try:
        # Load base templates first
        base_templates = await load_base_templates()

        # 1. Check custom templates first (highest priority)
        custom_dir = await get_custom_template_dir()
        if custom_dir:
            custom_templates = await load_templates_from_dir(custom_dir, base_templates)
            for template_data in custom_templates:
                if template_data.get("name") == template_name:
                    _LOGGER.debug("Loaded custom template: %s", template_name)
                    return template_data

        # 2. Check built-in templates
        if os.path.exists(TEMPLATE_DIR):
            loop = asyncio.get_event_loop()
            filenames = await loop.run_in_executor(None, os.listdir, TEMPLATE_DIR)

            for filename in filenames:
                if filename.endswith((".yaml", ".yml")):
                    # Skip directories
                    if os.path.isdir(os.path.join(TEMPLATE_DIR, filename)):
                        continue

                    template_path = os.path.join(TEMPLATE_DIR, filename)
                    template_data = await load_single_template(
                        template_path, base_templates
                    )
                    if template_data and template_data.get("name") == template_name:
                        _LOGGER.debug(
                            "Loaded specific built-in template: %s", template_name
                        )
                        return template_data

        # 3. Check manufacturer mappings if not found in device templates
        if os.path.exists(MAPPING_DIR):
            loop = asyncio.get_event_loop()
            mapping_files = await loop.run_in_executor(None, os.listdir, MAPPING_DIR)
            for filename in mapping_files:
                if filename.endswith((".yaml", ".yml")):
                    mapping_path = os.path.join(MAPPING_DIR, filename)
                    mapping_data = await load_mapping_template(
                        mapping_path, base_templates
                    )
                    if mapping_data and mapping_data.get("name") == template_name:
                        _LOGGER.debug(
                            "Loaded specific mapping template: %s", template_name
                        )
                        return mapping_data

        _LOGGER.warning("Template %s not found", template_name)
        return None

    except Exception as e:
        _LOGGER.error("Error loading template %s: %s", template_name, str(e))
        return None


async def get_base_template_by_name(base_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific base template by name."""
    base_templates = await load_base_templates()
    return base_templates.get(base_name)
