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

# Template-Verzeichnisse relativ zum Projekt-Root
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "device_templates")
BASE_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, "base_templates")
MAPPING_DIR = os.path.join(TEMPLATE_DIR, "manufacturer_mappings")

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
    "byte_order": "big",  # Standard-Byte-Reihenfolge (big endian)
    "group": None,
    # Neue Felder aus modbus_connect
    "offset": 0.0,
    "multiplier": 1.0,
    "sum_scale": None,
    "shift_bits": 0,
    "bits": None,
    "bitmask": None,           # Bitmaske (z.B. 0xFF für die unteren 8 Bits)
    "bit_position": None,      # Einzelnes Bit an Position extrahieren (0-31)
    "bit_shift": 0,            # Bits nach links/rechts verschieben (positiv=links, negativ=rechts)
    "bit_rotate": 0,           # Bits rotieren (positiv=links, negativ=rechts)
    "bit_range": None,         # Bereich von Bits extrahieren [start, end]
    "float": False,
    "string": False,
    "encoding": "utf-8",     # String-Encoding (utf-8, ascii, latin1, etc.)
    "max_length": None,      # Maximale String-Länge (None = unbegrenzt)
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
        # Load base templates first
        base_templates = await load_base_templates()
        
        # Get device template directory
        if not os.path.exists(TEMPLATE_DIR):
            _LOGGER.error("Template-Verzeichnis %s existiert nicht", TEMPLATE_DIR)
            return []
        
        # List files in thread-safe way
        loop = asyncio.get_event_loop()
        filenames = await loop.run_in_executor(None, os.listdir, TEMPLATE_DIR)
        
        templates = []
        for filename in filenames:
            if filename.endswith(('.yaml', '.yml')):
                # Skip directories
                if os.path.isdir(os.path.join(TEMPLATE_DIR, filename)):
                    continue
                    
                template_path = os.path.join(TEMPLATE_DIR, filename)
                template_data = await load_single_template(template_path, base_templates)
                if template_data:
                    templates.append(template_data)
        
        # Load manufacturer mappings
        if os.path.exists(MAPPING_DIR):
            mapping_files = await loop.run_in_executor(None, os.listdir, MAPPING_DIR)
            for filename in mapping_files:
                if filename.endswith(('.yaml', '.yml')):
                    mapping_path = os.path.join(MAPPING_DIR, filename)
                    mapping_data = await load_mapping_template(mapping_path, base_templates)
                    if mapping_data:
                        templates.append(mapping_data)
        
        _LOGGER.debug("Insgesamt %d Templates geladen (inkl. %d BASE-Templates)", 
                     len(templates), len(base_templates))
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
            if filename.endswith(('.yaml', '.yml')):
                template_path = os.path.join(BASE_TEMPLATE_DIR, filename)
                template_data = await load_single_template(template_path, {})
                if template_data:
                    base_name = template_data.get("name")
                    if base_name:
                        base_templates[base_name] = template_data
                        _LOGGER.debug("BASE-Template %s geladen", base_name)
        
        _LOGGER.debug("Insgesamt %d BASE-Templates geladen", len(base_templates))
        return base_templates
        
    except Exception as e:
        _LOGGER.error("Fehler beim Laden der BASE-Templates: %s", str(e))
        return {}

def process_sunspec_model_structure(base_template: Dict[str, Any], model_addresses: Dict[str, int]) -> List[Dict[str, Any]]:
    """Process SunSpec model structure with offsets and model base addresses."""
    try:
        processed_registers = []
        
        # Process each model in the base template
        for model_key, model_data in base_template.items():
            if not isinstance(model_data, dict) or "registers" not in model_data:
                continue
                
            # Get the base address for this model
            model_base_address = model_addresses.get(model_key)
            if model_base_address is None:
                _LOGGER.warning("Keine Basisadresse für Modell %s gefunden", model_key)
                continue
                
            _LOGGER.debug("Verarbeite Modell %s mit Basisadresse %d", model_key, model_base_address)
            
            # Process registers in this model
            for reg in model_data.get("registers", []):
                # Create a copy of the register
                processed_reg = dict(reg)
                
                # Calculate absolute address from offset and base address
                offset = reg.get("offset", 0)
                absolute_address = model_base_address + offset
                processed_reg["address"] = absolute_address
                
                # Add model information
                processed_reg["model"] = model_key
                processed_reg["model_offset"] = offset
                
                # Add to processed registers
                processed_registers.append(processed_reg)
                
                _LOGGER.debug("Register %s: Offset %d + Basis %d = Adresse %d", 
                             reg.get("name"), offset, model_base_address, absolute_address)
        
        _LOGGER.debug("SunSpec-Modellstruktur verarbeitet: %d Register erstellt", len(processed_registers))
        return processed_registers
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Verarbeitung der SunSpec-Modellstruktur: %s", str(e))
        return []

def validate_sunspec_template(template_data: Dict[str, Any], template_name: str) -> bool:
    """Validate SunSpec template structure and data."""
    try:
        _LOGGER.debug("Validiere SunSpec-Template %s", template_name)
        
        # Check if template extends SunSpec Standard
        extends_name = template_data.get("extends")
        if not extends_name or "SunSpec" not in extends_name:
            _LOGGER.error("Template %s muss 'SunSpec Standard' erweitern", template_name)
            return False
        
        # Check for required model_addresses
        model_addresses = template_data.get("model_addresses")
        if not model_addresses:
            _LOGGER.error("Template %s muss model_addresses definieren", template_name)
            return False
        
        # Validate model addresses
        required_models = ["common_model", "inverter_model"]
        for model in required_models:
            if model not in model_addresses:
                _LOGGER.warning("Template %s definiert nicht alle erforderlichen Modelle: %s fehlt", 
                               template_name, model)
        
        # Validate address values
        for model_name, address in model_addresses.items():
            if not isinstance(address, int) or address < 1:
                _LOGGER.error("Template %s: Ungültige Adresse für Modell %s: %s", 
                             template_name, model_name, address)
                return False
        
        # Validate custom registers if present
        custom_registers = template_data.get("custom_registers", [])
        for reg in custom_registers:
            if not validate_custom_register(reg, template_name):
                return False
        
        # Validate custom controls if present
        custom_controls = template_data.get("custom_controls", [])
        for ctrl in custom_controls:
            if not validate_custom_control(ctrl, template_name):
                return False
        
        _LOGGER.debug("Template %s erfolgreich validiert", template_name)
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Validierung von Template %s: %s", template_name, str(e))
        return False

def validate_custom_register(reg: Dict[str, Any], template_name: str) -> bool:
    """Validate a custom register in a SunSpec template."""
    try:
        # Required fields
        required_fields = ["name", "unique_id", "address"]
        for field in required_fields:
            if field not in reg:
                _LOGGER.error("Template %s: Custom Register fehlt Pflichtfeld %s", template_name, field)
                return False
        
        # Validate address
        address = reg.get("address")
        if not isinstance(address, int) or address < 1:
            _LOGGER.error("Template %s: Ungültige Adresse für Register %s: %s", 
                         template_name, reg.get("name"), address)
            return False
        
        # Validate data type
        data_type = reg.get("data_type")
        valid_data_types = {"uint16", "int16", "uint32", "int32", "string", "float", "float64", "boolean"}
        if data_type not in valid_data_types:
            _LOGGER.error("Template %s: Ungültiger data_type für Register %s: %s", 
                         template_name, reg.get("name"), data_type)
            return False
        
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Validierung des Custom Registers in Template %s: %s", 
                     template_name, str(e))
        return False

def validate_custom_control(ctrl: Dict[str, Any], template_name: str) -> bool:
    """Validate a custom control in a SunSpec template."""
    try:
        # Required fields
        required_fields = ["type", "name", "address"]
        for field in required_fields:
            if field not in ctrl:
                _LOGGER.error("Template %s: Custom Control fehlt Pflichtfeld %s", template_name, field)
                return False
        
        # Validate control type
        ctrl_type = ctrl.get("type")
        valid_control_types = {"select", "number", "button", "switch"}
        if ctrl_type not in valid_control_types:
            _LOGGER.error("Template %s: Ungültiger Control-Typ für %s: %s", 
                         template_name, ctrl.get("name"), ctrl_type)
            return False
        
        # Validate address
        address = ctrl.get("address")
        if not isinstance(address, int) or address < 1:
            _LOGGER.error("Template %s: Ungültige Adresse für Control %s: %s", 
                         template_name, ctrl.get("name"), address)
            return False
        
        # Type-specific validation
        if ctrl_type == "select":
            options = ctrl.get("options", {})
            if not isinstance(options, dict) or not options:
                _LOGGER.error("Template %s: Select-Control %s benötigt gültige options", 
                             template_name, ctrl.get("name"))
                return False
        
        elif ctrl_type == "number":
            min_val = ctrl.get("min_value")
            max_val = ctrl.get("max_value")
            if min_val is not None and max_val is not None:
                if min_val >= max_val:
                    _LOGGER.error("Template %s: Ungültige min/max Werte für Control %s: min=%s, max=%s", 
                                 template_name, ctrl.get("name"), min_val, max_val)
                    return False
        
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Validierung des Custom Controls in Template %s: %s", 
                     template_name, str(e))
        return False

def process_simple_template(template_data: Dict[str, Any], base_template: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
    """Process a simple template that only requires prefix and name."""
    try:
        _LOGGER.debug("Verarbeite vereinfachtes Template: %s", template_data.get("name"))
        
        # Extract required fields from user configuration
        prefix = user_config.get("prefix")
        device_name = user_config.get("name", prefix)  # Use prefix as fallback
        
        if not prefix:
            _LOGGER.error("Prefix ist erforderlich für vereinfachte Templates")
            return {}
        
        # Get model addresses from template
        model_addresses = template_data.get("model_addresses", {})
        if not model_addresses:
            _LOGGER.error("Template muss model_addresses definieren")
            return {}
        
        # Process SunSpec model structure
        model_registers = process_sunspec_model_structure(base_template, model_addresses)
        
        # Get auto-generated sensor configuration
        auto_config = template_data.get("auto_generated_sensors", {})
        
        # Filter registers based on auto-generated configuration
        filtered_registers = []
        for reg in model_registers:
            model_key = reg.get("model")
            if model_key in auto_config:
                model_config = auto_config[model_key]
                if model_config.get("enabled", True):
                    # Add prefix to unique_id
                    reg_name = reg.get("name", "").lower()
                    reg["unique_id"] = f"{prefix}_{reg_name}"
                    
                    # Add groups from auto-config
                    groups = model_config.get("groups", [])
                    if groups:
                        reg["group"] = groups[0]  # Use first group as primary
                        reg["groups"] = groups  # Store all groups for later use
                    
                    filtered_registers.append(reg)
        
        # Process calculated sensors
        calculated_sensors = template_data.get("calculated_sensors", [])
        for calc_sensor in calculated_sensors:
            # Replace {PREFIX} placeholder with actual prefix
            if "state" in calc_sensor:
                calc_sensor["state"] = calc_sensor["state"].replace("{PREFIX}", prefix)
            
            # Add prefix to unique_id
            calc_name = calc_sensor.get("name", "").lower().replace(" ", "_")
            calc_sensor["unique_id"] = f"{prefix}_{calc_name}"
        
        # Process controls
        controls = template_data.get("controls", [])
        for control in controls:
            # Add prefix to unique_id
            ctrl_name = control.get("name", "").lower().replace(" ", "_")
            control["unique_id"] = f"{prefix}_{ctrl_name}"
        
        # Create final template data
        processed_template = {
            "name": device_name,
            "prefix": prefix,
            "sensors": filtered_registers,
            "calculated_sensors": calculated_sensors,
            "controls": controls,
            "template_info": template_data.get("template_info", {}),
            "model_addresses": model_addresses,
            "auto_generated_sensors": auto_config
        }
        
        _LOGGER.debug("Vereinfachtes Template verarbeitet: %d Sensoren, %d berechnete Sensoren, %d Steuerelemente", 
                     len(filtered_registers), len(calculated_sensors), len(controls))
        
        return processed_template
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Verarbeitung des vereinfachten Templates: %s", str(e))
        return {}

async def process_simple_template_with_config(template_info: Dict[str, Any], user_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process a simple template with user configuration."""
    try:
        template_data = template_info.get("template_data")
        base_template = template_info.get("base_template")
        
        if not template_data or not base_template:
            _LOGGER.error("Ungültige Template-Informationen für vereinfachtes Template")
            return None
        
        # Check if this is a SunSpec Standard Configuration
        if template_data.get("name") == "SunSpec Standard Configuration":
            return await process_sunspec_config_template(template_data, base_template, user_config)
        
        # Process the simple template with user config
        processed_template = process_simple_template(template_data, base_template, user_config)
        
        if not processed_template:
            _LOGGER.error("Fehler bei der Verarbeitung des vereinfachten Templates")
            return None
        
        # Validate and process registers
        validated_registers = []
        for reg in processed_template.get("sensors", []):
            validated_reg = validate_and_process_register(reg, processed_template.get("name"))
            if validated_reg:
                validated_reg["template"] = processed_template.get("name")
                validated_registers.append(validated_reg)
        
        # Update processed template with validated registers
        processed_template["sensors"] = validated_registers
        
        _LOGGER.debug("Vereinfachtes Template erfolgreich verarbeitet: %s", processed_template.get("name"))
        return processed_template
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Verarbeitung des vereinfachten Templates mit Konfiguration: %s", str(e))
        return None

async def process_sunspec_config_template(template_data: Dict[str, Any], base_template: Dict[str, Any], user_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process SunSpec Standard Configuration template."""
    try:
        _LOGGER.debug("Verarbeite SunSpec Standard Configuration Template")
        
        # Extract required fields from user configuration
        prefix = user_config.get("prefix")
        device_name = user_config.get("name", prefix)
        
        if not prefix:
            _LOGGER.error("Prefix ist erforderlich für SunSpec-Konfiguration")
            return None
        
        # Get model addresses from user config
        model_addresses = {
            "common_model": user_config.get("common_model_address"),
            "inverter_model": user_config.get("inverter_model_address"),
        }
        
        # Add optional model addresses
        if user_config.get("storage_model_address"):
            model_addresses["storage_model"] = user_config["storage_model_address"]
        
        if user_config.get("meter_model_address"):
            model_addresses["meter_model"] = user_config["meter_model_address"]
        
        # Validate model addresses
        for model_name, address in model_addresses.items():
            if not address or not isinstance(address, int) or address < 1:
                _LOGGER.error("Ungültige Adresse für Modell %s: %s", model_name, address)
                return None
        
        # Process SunSpec model structure
        model_registers = process_sunspec_model_structure(base_template, model_addresses)
        
        # Get auto-generated sensor configuration
        auto_config = template_data.get("auto_generated_sensors", {})
        
        # Filter registers based on auto-generated configuration
        filtered_registers = []
        for reg in model_registers:
            model_key = reg.get("model")
            if model_key in auto_config:
                model_config = auto_config[model_key]
                if model_config.get("enabled", True):
                    # Add prefix to unique_id
                    reg_name = reg.get("name", "").lower()
                    reg["unique_id"] = f"{prefix}_{reg_name}"
                    
                    # Add groups from auto-config
                    groups = model_config.get("groups", [])
                    if groups:
                        reg["group"] = groups[0]  # Use first group as primary
                        reg["groups"] = groups  # Store all groups for later use
                    
                    filtered_registers.append(reg)
        
        # Process calculated sensors
        calculated_sensors = template_data.get("calculated_sensors", [])
        for calc_sensor in calculated_sensors:
            # Replace {PREFIX} placeholder with actual prefix
            if "state" in calc_sensor:
                calc_sensor["state"] = calc_sensor["state"].replace("{PREFIX}", prefix)
            
            # Add prefix to unique_id
            calc_name = calc_sensor.get("name", "").lower().replace(" ", "_")
            calc_sensor["unique_id"] = f"{prefix}_{calc_name}"
        
        # Process controls
        controls = template_data.get("controls", [])
        for control in controls:
            # Replace address placeholders
            if "address" in control:
                address = control["address"]
                if "{STORAGE_MODEL_ADDRESS_PLUS_2}" in str(address):
                    if "storage_model" in model_addresses:
                        storage_addr = model_addresses["storage_model"]
                        control["address"] = storage_addr + 2
                    else:
                        _LOGGER.warning("Storage Model nicht verfügbar, Control %s wird übersprungen", control.get("name"))
                        continue
                
                if "{STORAGE_MODEL_ADDRESS_PLUS_3}" in str(address):
                    if "storage_model" in model_addresses:
                        storage_addr = model_addresses["storage_model"]
                        control["address"] = storage_addr + 3
                    else:
                        _LOGGER.warning("Storage Model nicht verfügbar, Control %s wird übersprungen", control.get("name"))
                        continue
            
            # Add prefix to unique_id
            ctrl_name = control.get("name", "").lower().replace(" ", "_")
            control["unique_id"] = f"{prefix}_{ctrl_name}"
        
        # Create final template data
        processed_template = {
            "name": device_name,
            "prefix": prefix,
            "sensors": filtered_registers,
            "calculated_sensors": calculated_sensors,
            "controls": controls,
            "template_info": template_data.get("template_info", {}),
            "model_addresses": model_addresses,
            "auto_generated_sensors": auto_config,
            "is_sunspec_config": True
        }
        
        _LOGGER.debug("SunSpec Standard Configuration verarbeitet: %d Sensoren, %d berechnete Sensoren, %d Steuerelemente", 
                     len(filtered_registers), len(calculated_sensors), len(controls))
        
        return processed_template
        
    except Exception as e:
        _LOGGER.error("Fehler bei der Verarbeitung der SunSpec-Konfiguration: %s", str(e))
        return None

async def load_single_template(template_path: str, base_templates: Dict[str, Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
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
        
        _LOGGER.debug("Template %s wird verarbeitet", template_name)
        
        # Check if template extends a base template
        extends_name = data.get("extends")
        if extends_name and base_templates and extends_name in base_templates:
            # Extend from base template
            base_template = base_templates[extends_name]
            _LOGGER.debug("Template %s erweitert BASE-Template %s", template_name, extends_name)
            
            # Check if this is a simple template (requires only prefix and name)
            if "required_fields" in data and "auto_generated_sensors" in data:
                _LOGGER.debug("Template %s ist ein vereinfachtes Template", template_name)
                # Simple templates are processed later when user config is available
                # For now, just return the template data for later processing
                return {
                    "name": template_name,
                    "template_data": data,
                    "base_template": base_template,
                    "is_simple_template": True
                }
            
            # Validate SunSpec template if it extends SunSpec Standard
            if "SunSpec" in extends_name:
                if not validate_sunspec_template(data, template_name):
                    _LOGGER.error("Template %s konnte nicht validiert werden", template_name)
                    return None
            
            # Check if this is a SunSpec template with model structure
            if "model_addresses" in data:
                _LOGGER.debug("Template %s verwendet SunSpec-Modellstruktur", template_name)
                
                # Process SunSpec model structure
                model_registers = process_sunspec_model_structure(base_template, data["model_addresses"])
                
                # Apply register mappings if present
                register_mapping = data.get("register_mapping", {})
                if register_mapping:
                    _LOGGER.debug("Wende Register-Mappings für Template %s an", template_name)
                    for reg in model_registers:
                        reg_name = reg.get("name")
                        if reg_name in register_mapping:
                            mapped_address = register_mapping[reg_name]
                            _LOGGER.debug("Mapping register %s von Adresse %s zu %s", 
                                         reg_name, reg.get("address"), mapped_address)
                            reg["address"] = mapped_address
                
                # Use the processed model registers
                raw_registers = model_registers
                
            else:
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
                        _LOGGER.debug("Mapping register %s from address %s to %s", 
                                     reg_name, mapped_reg.get("address"), mapped_address)
                        mapped_reg["address"] = mapped_address
                    
                    mapped_registers.append(mapped_reg)
                
                # Use the combined registers
                raw_registers = mapped_registers
            
            # Add custom registers if present
            custom_registers = data.get("custom_registers", [])
            if custom_registers:
                _LOGGER.debug("Adding %d custom registers to template %s", 
                            len(custom_registers), template_name)
                raw_registers.extend(custom_registers)
            
            # Include calculated entities from base template
            base_calculated = base_template.get("calculated", [])
            custom_calculated = data.get("calculated", [])
            
            # Combine calculated entities, avoiding duplicates by unique_id
            calculated_entities = list(base_calculated)  # Make a copy to avoid modifying the original
            custom_calculated_ids = {calc.get("unique_id") for calc in custom_calculated if "unique_id" in calc}
            
            # Remove base calculated entities that are overridden by custom ones
            calculated_entities = [calc for calc in calculated_entities 
                                 if "unique_id" not in calc or calc["unique_id"] not in custom_calculated_ids]
            
            # Add custom calculated entities
            calculated_entities.extend(custom_calculated)
            
            # Include controls from base template
            base_controls = base_template.get("controls", [])
            custom_controls = data.get("custom_controls", [])
            
            # Combine controls, avoiding duplicates by name
            controls = list(base_controls)  # Make a copy to avoid modifying the original
            custom_control_names = {ctrl.get("name") for ctrl in custom_controls if "name" in ctrl}
            
            # Remove base controls that are overridden by custom ones
            controls = [ctrl for ctrl in controls 
                      if "name" not in ctrl or ctrl["name"] not in custom_control_names]
            
            # Add custom controls
            controls.extend(custom_controls)
            
        else:
            # Standard template processing
            raw_registers = data.get("sensors", [])
            if not raw_registers:
                # Allow empty base templates and aggregate-only templates
                if "type" in data and data["type"] == "base_template":
                    _LOGGER.debug("Template %s is base template (no sensors expected)", template_name)
                    raw_registers = []
                elif "aggregates" in data and data["aggregates"]:
                    _LOGGER.debug("Template %s is aggregate-only template (no sensors expected)", template_name)
                    raw_registers = []
                elif template_name in ["SunSpec Standard", "Modbus Manager Aggregates"]:
                    _LOGGER.debug("Template %s is special template (no sensors expected)", template_name)
                    raw_registers = []
                else:
                    _LOGGER.warning("Template %s has no sensors defined", template_name)
                    return None
                
            calculated_entities = data.get("calculated", [])
            controls = data.get("controls", [])
        
        _LOGGER.debug("Template %s: %d sensors found", template_name, len(raw_registers))
        
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
        
        # For base templates and aggregate-only templates, allow empty register lists
        if not validated_registers and not ("type" in data and data["type"] == "base_template") and not ("aggregates" in data and data["aggregates"]):
            _LOGGER.error("Template %s has no valid registers", template_name)
            return None
        
        _LOGGER.debug("Template %s: %d valid registers processed", template_name, len(validated_registers))
        
        # Process calculated section if present
        if calculated_entities:
            _LOGGER.debug("Template %s: %d calculated entities found", template_name, len(calculated_entities))
        
        # Process controls section if present
        if controls:
            _LOGGER.debug("Template %s: %d controls found", template_name, len(controls))
        
        # Debug: Template structure
        _LOGGER.debug("Template %s structure: name=%s, sensors=%d, calculated=%d, controls=%d", 
                     template_name, template_name, len(validated_registers), 
                     len(calculated_entities), len(controls))
        
        # Process aggregates section if present
        aggregates = data.get("aggregates", [])
        if aggregates:
            _LOGGER.debug("Template %s: %d aggregates found", template_name, len(aggregates))
        
        # Include all template metadata
        result = {
            "name": template_name,
            "sensors": validated_registers,
            "calculated": calculated_entities,
            "controls": controls,
            "aggregates": aggregates,
            "type": data.get("type", "device_template"),
            "version": data.get("version", 1),
            "description": data.get("description", ""),
            "manufacturer": data.get("manufacturer", ""),
            "model": data.get("model", "")
        }
        
        # Add extends information if present
        if extends_name:
            result["extends"] = extends_name
            
        return result
        
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
        
        # Auto-set count for Float types (before validation)
        count = processed_reg.get("count")
        data_type = processed_reg.get("data_type")
        
        if count is None:
            if data_type in ["float", "float32"]:
                processed_reg["count"] = 2
                _LOGGER.debug("Auto-set count=2 for %s in Template %s", data_type, template_name)
            elif data_type == "float64":
                processed_reg["count"] = 4
                _LOGGER.debug("Auto-set count=4 for %s in Template %s", data_type, template_name)
            else:
                processed_reg["count"] = 1
                _LOGGER.debug("Auto-set count=1 for %s in Template %s", data_type, template_name)
        
        # Validate register
        if not validate_register_data(processed_reg, template_name):
            return None
        
        return processed_reg
        
    except Exception as e:
        _LOGGER.error("Error processing register in Template %s: %s", template_name, str(e))
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
        valid_data_types = {"uint16", "int16", "uint32", "int32", "string", "float", "float32", "float64", "boolean"}
        if data_type not in valid_data_types:
            _LOGGER.error("Invalid data_type in Template %s: %s", template_name, data_type)
            return False
        
        # Validate count
        count = reg.get("count")
        if not isinstance(count, int) or count < 1:
            _LOGGER.error("Invalid count in Template %s: %s", template_name, count)
            return False
            
        # Float-specific validation
        if data_type in ["float", "float32", "float64"]:
            # Float type requires at least 2 registers for 32-bit and 4 registers for 64-bit
            min_count = 2 if data_type in ["float", "float32"] else 4
            if count < min_count:
                _LOGGER.error("Float type %s in Template %s requires at least %d registers, but count=%d", 
                             data_type, template_name, min_count, count)
                return False
        
        # Validate scale
        scale = reg.get("scale")
        if not isinstance(scale, (int, float)) or scale <= 0:
            _LOGGER.error("Invalid scale in Template %s: %s", template_name, scale)
            return False
        
        # Validate scan interval
        scan_interval = reg.get("scan_interval")
        if not isinstance(scan_interval, int) or scan_interval < 0:
            _LOGGER.error("Invalid scan_interval in Template %s: %s", template_name, scan_interval)
            return False
        
        # Control-specific validation
        if not validate_control_settings(reg, template_name):
            return False
        
        # Validate sum_scale
        sum_scale = reg.get("sum_scale")
        if sum_scale is not None:
            if not isinstance(sum_scale, list) or not all(isinstance(x, (int, float)) for x in sum_scale):
                _LOGGER.error("Invalid sum_scale in Template %s: %s", template_name, sum_scale)
                return False
        
        # Validate options for Select entities
        if reg.get("control") == "select":
            options = reg.get("options", {})
            if not isinstance(options, dict) or not options:
                _LOGGER.error("Select entity in Template %s requires valid options", template_name)
                return False
        
        return True
        
    except Exception as e:
        _LOGGER.error("Error in data validation in Template %s: %s", template_name, str(e))
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
                    _LOGGER.error("Invalid min/max values in Template %s: min=%s, max=%s", 
                                 template_name, min_val, max_val)
                    return False
        
        elif control == "switch":
            switch_config = reg.get("switch", {})
            if switch_config:
                on_val = switch_config.get("on", 1)
                off_val = switch_config.get("off", 0)
                if on_val == off_val:
                    _LOGGER.error("Switch on/off values must be different in Template %s", template_name)
                    return False
        
        return True
        
    except Exception as e:
        _LOGGER.error("Error in control validation in Template %s: %s", template_name, str(e))
        return False

async def get_template_names() -> List[str]:
    """Get list of available template names."""
    templates = await load_templates()
    return [template["name"] for template in templates]

async def load_mapping_template(mapping_path: str, base_templates: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Load a manufacturer mapping template file."""
    try:
        # Use the standard template loader with base templates
        mapping_data = await load_single_template(mapping_path, base_templates)
        
        if mapping_data and "extends" in mapping_data:
            _LOGGER.debug("Loaded mapping template %s extending %s", 
                        mapping_data.get("name"), mapping_data.get("extends"))
            return mapping_data
        else:
            _LOGGER.warning("Mapping template %s does not extend a base template", mapping_path)
            return None
    
    except Exception as e:
        _LOGGER.error("Error loading mapping template %s: %s", mapping_path, str(e))
        return None

async def get_template_by_name(template_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific template by name."""
    templates = await load_templates()
    for template in templates:
        if template["name"] == template_name:
            # Return the full template data, not just registers
            # This allows access to both sensors and calculated sections
            return template
    return None

async def get_base_template_by_name(base_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific base template by name."""
    base_templates = await load_base_templates()
    return base_templates.get(base_name) 