"""Template Loader for Modbus Manager."""
import asyncio
import os
import yaml
from typing import Dict, Any, List, Optional
from homeassistant.core import HomeAssistant
from homeassistant.util.async_ import run_callback_threadsafe
import logging
from .const import (
    DEFAULT_UPDATE_INTERVAL, DEFAULT_MAX_REGISTER_READ, DEFAULT_PRECISION,
    DEFAULT_MIN_VALUE, DEFAULT_MAX_VALUE, DataType, RegisterType, ControlType
)
from .logger import ModbusManagerLogger

_LOGGER = logging.getLogger(__name__)

# Template-Verzeichnis relativ zum Projekt-Root
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "device_templates")

# Pflichtfelder basierend auf modbus_connect und Sungrow-Format
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
    "group": None,
    # Neue Felder aus modbus_connect
    "offset": 0.0,
    "multiplier": 1.0,
    "sum_scale": None,
    "shift_bits": 0,
    "bits": None,
    "float": False,
    "string": False,
    "control": "none",
    "min_value": DEFAULT_MIN_VALUE,
    "max_value": DEFAULT_MAX_VALUE,
    "step": 1.0,
    "options": {},
    "map": {},
    "flags": {},
    "never_resets": False,
    "entity_category": None,
    "icon": None
}

async def load_templates() -> List[Dict[str, Any]]:
    """Load all template files asynchronously."""
    try:
        # Get template directory
        template_dir = os.path.join(os.path.dirname(__file__), "device_templates")
        if not os.path.exists(template_dir):
            _LOGGER.error("Template-Verzeichnis %s existiert nicht", template_dir)
            return []
        
        # List files in thread-safe way
        loop = asyncio.get_event_loop()
        filenames = await loop.run_in_executor(None, os.listdir, template_dir)
        
        templates = []
        for filename in filenames:
            if filename.endswith(('.yaml', '.yml')):
                template_path = os.path.join(template_dir, filename)
                template_data = await load_single_template(template_path)
                if template_data:
                    templates.append(template_data)
        
        _LOGGER.info("Insgesamt %d Templates geladen", len(templates))
        return templates
        
    except Exception as e:
        _LOGGER.error("Fehler beim Laden der Templates: %s", str(e))
        return []

async def load_single_template(template_path: str) -> Optional[Dict[str, Any]]:
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
        
        _LOGGER.info("Template %s wird verarbeitet", template_name)
        
        # Process sensors section
        raw_registers = data.get("sensors", [])
        if not raw_registers:
            _LOGGER.warning("Template %s has no sensors defined", template_name)
            return None
        
        _LOGGER.info("Template %s: %d sensors found", template_name, len(raw_registers))
        
        # Debug: Show first register
        if raw_registers:
            _LOGGER.debug("First register: %s", raw_registers[0])
        
        validated_registers = []
        for reg in raw_registers:
            validated_reg = validate_and_process_register(reg, template_name)
            if validated_reg:
                # Add template name to each register
                validated_reg["template"] = template_name
                validated_registers.append(validated_reg)
            else:
                _LOGGER.warning("Register %s in Template %s could not be validated", reg.get("name", "unknown"), template_name)
        
        if not validated_registers:
            _LOGGER.error("Template %s has no valid registers", template_name)
            return None
        
        _LOGGER.info("Template %s: %d valid registers processed", template_name, len(validated_registers))
        
        # Process calculated section if present
        calculated_entities = data.get("calculated", [])
        if calculated_entities:
            _LOGGER.info("Template %s: %d calculated entities found", template_name, len(calculated_entities))
        
        # Debug: Template structure
        _LOGGER.debug("Template %s structure: name=%s, sensors=%d, calculated=%d", 
                      template_name, template_name, len(validated_registers), len(calculated_entities))
        
        return {
            "name": template_name,
            "sensors": validated_registers,
            "calculated": calculated_entities
        }
        
    except yaml.YAMLError as e:
        _LOGGER.error("YAML-Fehler in Template %s: %s", template_path, str(e))
        return None
    except Exception as e:
        _LOGGER.error("Unerwarteter Fehler beim Laden von Template %s: %s", template_path, str(e))
        return None

def _read_template_file(template_path: str) -> Optional[Dict[str, Any]]:
    """Read template file synchronously (called in executor)."""
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        _LOGGER.error("Fehler beim Lesen von Template %s: %s", template_path, str(e))
        return None

def validate_and_process_register(reg: Dict[str, Any], template_name: str) -> Dict[str, Any]:
    """Validate and process a single register definition."""
    try:
        # Pflichtfelder prüfen
        if not all(field in reg for field in REQUIRED_FIELDS):
            missing_fields = REQUIRED_FIELDS - set(reg.keys())
            _LOGGER.warning("Register in Template %s fehlt Pflichtfelder: %s", template_name, missing_fields)
            return None
        
        # Standardwerte für optionale Felder setzen
        processed_reg = {}
        for field, default_value in OPTIONAL_FIELDS.items():
            processed_reg[field] = reg.get(field, default_value)
        
        # Pflichtfelder hinzufügen
        for field in REQUIRED_FIELDS:
            processed_reg[field] = reg[field]
        
        # Zusätzliche Felder aus dem Template übernehmen
        for field, value in reg.items():
            if field not in processed_reg:
                processed_reg[field] = value
        
        # Entity-Typ bestimmen
        processed_reg["entity_type"] = determine_entity_type(processed_reg)
        
        # Register validieren
        if not validate_register_data(processed_reg, template_name):
            return None
        
        return processed_reg
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Register-Verarbeitung in Template %s: %s", template_name, str(e))
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
        # Address validieren
        address = reg.get("address")
        if not isinstance(address, int) or address < 0:
            _LOGGER.error("Ungültige Adresse in Template %s: %s", template_name, address)
            return False
        
        # Data type validieren
        data_type = reg.get("data_type")
        valid_data_types = {"uint16", "int16", "uint32", "int32", "string", "float", "boolean"}
        if data_type not in valid_data_types:
            _LOGGER.error("Ungültiger data_type in Template %s: %s", template_name, data_type)
            return False
        
        # Count validieren
        count = reg.get("count")
        if not isinstance(count, int) or count < 1:
            _LOGGER.error("Ungültiger count in Template %s: %s", template_name, count)
            return False
        
        # Scale validieren
        scale = reg.get("scale")
        if not isinstance(scale, (int, float)) or scale <= 0:
            _LOGGER.error("Ungültiger scale in Template %s: %s", template_name, scale)
            return False
        
        # Scan interval validieren
        scan_interval = reg.get("scan_interval")
        if not isinstance(scan_interval, int) or scan_interval < 1:
            _LOGGER.error("Ungültiger scan_interval in Template %s: %s", template_name, scan_interval)
            return False
        
        # Control-spezifische Validierung
        if not validate_control_settings(reg, template_name):
            return False
        
        # Sum_scale Validierung
        sum_scale = reg.get("sum_scale")
        if sum_scale is not None:
            if not isinstance(sum_scale, list) or not all(isinstance(x, (int, float)) for x in sum_scale):
                _LOGGER.error("Ungültiger sum_scale in Template %s: %s", template_name, sum_scale)
                return False
        
        # Options Validierung für Select-Entitäten
        if reg.get("control") == "select":
            options = reg.get("options", {})
            if not isinstance(options, dict) or not options:
                _LOGGER.error("Select-Entität in Template %s benötigt gültige options", template_name)
                return False
        
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Datenvalidierung in Template %s: %s", template_name, str(e))
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
                    _LOGGER.error("Ungültige min/max Werte in Template %s: min=%s, max=%s", 
                                 template_name, min_val, max_val)
                    return False
        
        elif control == "switch":
            switch_config = reg.get("switch", {})
            if switch_config:
                on_val = switch_config.get("on", 1)
                off_val = switch_config.get("off", 0)
                if on_val == off_val:
                    _LOGGER.error("Switch on/off Werte müssen unterschiedlich sein in Template %s", template_name)
                    return False
        
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Control-Validierung in Template %s: %s", template_name, str(e))
        return False

async def get_template_names() -> List[str]:
    """Get list of available template names."""
    templates = await load_templates()
    return [template["name"] for template in templates]

async def get_template_by_name(template_name: str) -> List[Dict[str, Any]]:
    """Get a specific template by name."""
    templates = await load_templates()
    for template in templates:
        if template["name"] == template_name:
            # Return the full template data, not just registers
            # This allows access to both sensors and calculated sections
            return template
    return [] 