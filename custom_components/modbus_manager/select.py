"""Modbus Manager Select Platform."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager select entities from a config entry."""
    # Daten aus hass.data holen, nicht aus entry.data
    domain_data = hass.data.get(DOMAIN, {})
    entry_data = domain_data.get(entry.entry_id, {})
    
    prefix = entry_data.get("prefix", entry.data["prefix"])
    template_name = entry_data.get("template", entry.data["template"])
    registers = entry_data.get("registers", [])
    controls = entry_data.get("controls", [])
    hub_name = f"modbus_manager_{prefix}"
    
    _LOGGER.debug("Select Setup: prefix=%s, template=%s, registers=%d, controls=%d", 
                prefix, template_name, len(registers), len(controls))
    _LOGGER.debug("Controls: %s", controls)

    # Entity Registry abrufen für Duplikat-Check
    registry = async_get_entity_registry(hass)
    existing_entities = {
        entity.entity_id for entity in registry.entities.values()
        if entity.entity_id.startswith(f"select.{prefix}_")
    }

    entities = []

    # Select-Entities aus Registern mit control: "select" erstellen
    for reg in registers:
        if reg.get("control") == "select":
            # Unique_ID Format: {prefix}_{template_sensor_name}
            sensor_name = reg.get("name", "unknown")
            # Use unique_id from template if available, otherwise use cleaned name
            template_unique_id = reg.get("unique_id")
            if template_unique_id:
                # Check if template_unique_id already has prefix
                if template_unique_id.startswith(f"{prefix}_"):
                    unique_id = template_unique_id
                else:
                    unique_id = f"{prefix}_{template_unique_id}"
            else:
                # Fallback: Bereinige den Namen für den unique_id
                clean_name = sensor_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                unique_id = f"{prefix}_{clean_name}"
            # Use same logic for entity_id
            if template_unique_id:
                if template_unique_id.startswith(f"{prefix}_"):
                    entity_id = f"select.{template_unique_id}"
                else:
                    entity_id = f"select.{prefix}_{template_unique_id}"
            else:
                entity_id = f"select.{prefix}_{clean_name}"
            
            # Prüfen ob Entity bereits existiert
            if entity_id in existing_entities:
                _LOGGER.debug("Select Entity %s existiert bereits, überspringe", entity_id)
                continue
            
            entities.append(ModbusTemplateSelect(
                hass=hass,
                name=sensor_name,
                unique_id=unique_id,
                entry=entry,
                slave_id=entry.data.get("slave_id", 1),
                register_data=reg,
                device_info={
                    "identifiers": {(DOMAIN, f"{prefix}_{template_name}")},
                    "name": f"{prefix} {template_name}",
                    "manufacturer": "Modbus Manager",
                    "model": template_name,
                    "sw_version": f"Firmware: {entry.data.get('firmware_version', '1.0.0')}",
                }
            ))

    # Select-Entities aus Controls-Abschnitt erstellen
    _LOGGER.debug("Verarbeite %d Controls für Select-Entities", len(controls))
    for control in controls:
        # Auto-detect select controls based on properties
        has_select_properties = (
            "map" in control or 
            "options" in control or 
            "flags" in control
        )
        is_explicit_select = control.get("type") == "select"
        
        if is_explicit_select or has_select_properties:
            control_name = control.get("name", "unknown")
            # Stelle sicher, dass der name den Prefix enthält
            if not control_name.startswith(f"{prefix} "):
                display_name = f"{prefix} {control_name}"
            else:
                display_name = control_name
            
            # Stelle sicher, dass der unique_id den Prefix enthält
            base_unique_id = control.get("unique_id", control_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', ''))
            # Wenn der unique_id bereits den Prefix hat, verwende ihn direkt
            if base_unique_id.startswith(f"{prefix}_"):
                unique_id = base_unique_id
            else:
                # Ansonsten füge den Prefix hinzu
                unique_id = f"{prefix}_{base_unique_id}"
            entity_id = f"select.{unique_id}"
            
            # Prüfen ob Entity bereits existiert
            if entity_id in existing_entities:
                _LOGGER.debug("Select Control Entity %s existiert bereits, überspringe", entity_id)
                continue
            
            entities.append(ModbusTemplateSelect(
                hass=hass,
                name=display_name,
                unique_id=unique_id,
                entry=entry,
                slave_id=entry_data.get("slave_id", entry.data.get("slave_id", 1)),
                register_data=control,
                device_info={
                    "identifiers": {(DOMAIN, f"{prefix}_{template_name}")},
                    "name": f"{prefix} {template_name}",
                    "manufacturer": "Modbus Manager",
                    "model": template_name,
                    "sw_version": f"Firmware: {entry.data.get('firmware_version', '1.0.0')}",
                }
            ))

    if entities:
        async_add_entities(entities)
        _LOGGER.debug("Modbus Manager: Created %d select entities", len(entities))
        _LOGGER.debug("Created select entities: %s", [e.entity_id for e in entities])
    else:
        _LOGGER.warning("No select entities created!")


class ModbusTemplateSelect(SelectEntity):
    """Representation of a Modbus Template Select Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, entry: ConfigEntry,
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._slave_id = slave_id
        _LOGGER.debug("Select %s: Initialized with entry_id=%s", name, entry.entry_id)
        self._register_data = register_data
        self._attr_device_info = DeviceInfo(**device_info)
        
        # Register properties
        self._address = register_data.get("address", 0)
        self._data_type = register_data.get("data_type", "uint16")
        self._input_type = register_data.get("input_type", "holding")
        
        # Always set correct count based on data type, regardless of template
        if self._data_type in ["uint32", "int32", "float", "float32"]:
            self._count = 2  # 32-bit types need 2 registers
        elif self._data_type == "float64":
            self._count = 4  # 64-bit types need 4 registers
        else:
            # For other types, use template count or default to 1
            template_count = register_data.get("count")
            self._count = template_count if template_count is not None else 1
        
        self._scale = register_data.get("scale", 1.0)
        self._swap = register_data.get("swap", False)
        
        # Neue Datenverarbeitungsoptionen
        self._offset = register_data.get("offset", 0.0)
        self._multiplier = register_data.get("multiplier", 1.0)
        
        # Select-Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class")
        self._attr_state_class = register_data.get("state_class")
        
        # Value processing (map, flags, options) - same as sensors
        self._map = register_data.get("map", {})
        self._flags = register_data.get("flags", {})
        self._options = register_data.get("options", {})
        
        # Create options list and value mapping (same priority as sensors: map -> flags -> options)
        self._value_to_text = {}
        
        # 1. Map (highest priority)
        if self._map:
            self._attr_options = list(self._map.values())
            for k, v in self._map.items():
                # Convert hex strings to integers
                if isinstance(k, str) and k.startswith('0x'):
                    try:
                        int_key = int(k, 16)
                        self._value_to_text[int_key] = v
                    except ValueError:
                        self._value_to_text[k] = v
                else:
                    self._value_to_text[k] = v
        # 2. Flags (if no map)
        elif self._flags:
            # For flags, create options from flag values
            flag_options = []
            for bit, flag_name in self._flags.items():
                flag_options.append(flag_name)
                self._value_to_text[flag_name] = flag_name
            self._attr_options = flag_options
        # 3. Options (if no map and no flags)
        elif self._options:
            self._attr_options = list(self._options.values())
            for k, v in self._options.items():
                # Convert hex strings to integers
                if isinstance(k, str) and k.startswith('0x'):
                    try:
                        int_key = int(k, 16)
                        self._value_to_text[int_key] = v
                    except ValueError:
                        self._value_to_text[k] = v
                else:
                    self._value_to_text[k] = v
        
        # Group for aggregations
        self._group = register_data.get("group")
        if self._group:
            self._attr_extra_state_attributes = {"group": self._group}
        
        self._attr_native_value = None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return True

    async def async_update(self):
        """Update the select entity state."""
        try:
            _LOGGER.debug("Select %s: Starting update", self.name)
            
            # Get Modbus-Hub from configuration (same as sensors)
            if self._entry.entry_id not in self.hass.data[DOMAIN]:
                _LOGGER.error("Select %s: No configuration data found for Entry %s", self.name, self._entry.entry_id)
                return
            
            config_data = self.hass.data[DOMAIN][self._entry.entry_id]
            hub = config_data.get("hub")
            
            if not hub:
                _LOGGER.error("Select %s: Modbus-Hub not found", self.name)
                return
            
            # Register-Wert lesen (gleiche Logik wie Sensoren)
            if self._input_type == "holding":
                from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
                result = await hub.async_pb_call(
                    self._slave_id,
                    self._address,
                    self._count,
                    CALL_TYPE_REGISTER_HOLDING
                )
            elif self._input_type == "input":
                from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_INPUT
                result = await hub.async_pb_call(
                    self._slave_id,
                    self._address,
                    self._count,
                    CALL_TYPE_REGISTER_INPUT
                )
            elif self._input_type == "coil":
                from homeassistant.components.modbus.const import CALL_TYPE_COIL
                result = await hub.async_pb_call(
                    self._slave_id,
                    self._address,
                    1,
                    CALL_TYPE_COIL
                )
            elif self._input_type == "discrete":
                from homeassistant.components.modbus.const import CALL_TYPE_DISCRETE
                result = await hub.async_pb_call(
                    self._slave_id,
                    self._address,
                    1,
                    CALL_TYPE_DISCRETE
                )
            else:
                _LOGGER.error("Unbekannter input_type: %s", self._input_type)
                return
            
            if not result or not hasattr(result, 'registers'):
                _LOGGER.warning("Select %s: Fehler beim Lesen von Register %s: %s", self.name, self._address, result)
                self._attr_current_option = None
                return
            
            # Wert verarbeiten (gleiche Logik wie Sensoren)
            processed_value = self._process_value(result.registers)
            _LOGGER.debug("Select %s: Raw value aus Register: %s", self.name, processed_value)
            
            if processed_value is not None:
                # Apply value processing (same logic as sensors: map -> flags -> options)
                _LOGGER.debug("Select %s: Before value processing: map=%s, flags=%s, options=%s", 
                             self.name, bool(self._map), bool(self._flags), bool(self._options))
                final_value = self._apply_value_processing(processed_value)
                
                if final_value is not None:
                    self._attr_current_option = str(final_value)
                    _LOGGER.debug("Select %s: Wert %s -> Verarbeiteter Wert %s", self.name, processed_value, final_value)
                else:
                    # If value processing returns None, use original value
                    self._attr_current_option = str(processed_value)
                    _LOGGER.debug("Select %s: Wert %s -> Keine Verarbeitung, verwende %s", self.name, processed_value, self._attr_current_option)
            else:
                self._attr_current_option = None
                _LOGGER.debug("Select %s: Kein Wert gelesen", self.name)
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Select %s: %s", self.name, str(e))
            self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Set the select option."""
        try:
            # Get Modbus-Hub from configuration (same as sensors)
            if self._entry.entry_id not in self.hass.data[DOMAIN]:
                _LOGGER.error("Select %s: No configuration data found for Entry %s", self.name, self._entry.entry_id)
                return
            
            config_data = self.hass.data[DOMAIN][self._entry.entry_id]
            hub = config_data.get("hub")
            
            if not hub:
                _LOGGER.error("Select %s: Modbus-Hub not found", self.name)
                return
            
            # Text-Wert zu numerischem Wert konvertieren (same priority as sensors: map -> flags -> options)
            numeric_value = None
            
            # 1. Map (highest priority)
            if self._map:
                for key, value in self._map.items():
                    if value == option:
                        # Convert hex strings to integers for writing
                        if isinstance(key, str) and key.startswith('0x'):
                            try:
                                numeric_value = int(key, 16)
                            except ValueError:
                                numeric_value = key
                        else:
                            numeric_value = key
                        break
            # 2. Flags (if no map)
            elif self._flags:
                # For flags, we need to find the bit position
                for bit, flag_name in self._flags.items():
                    if flag_name == option:
                        numeric_value = 1 << int(bit)
                        break
            # 3. Options (if no map and no flags)
            elif self._options:
                for key, value in self._options.items():
                    if value == option:
                        # Convert hex strings to integers for writing
                        if isinstance(key, str) and key.startswith('0x'):
                            try:
                                numeric_value = int(key, 16)
                            except ValueError:
                                numeric_value = key
                        else:
                            numeric_value = key
                        break
            
            if numeric_value is None:
                _LOGGER.error("Unbekannte Option: %s. Verfügbare Optionen: %s", option, list(self._options.values()))
                return
            
            # Erweiterte Datenverarbeitung rückwärts anwenden
            final_value = self._apply_reverse_data_processing(numeric_value)
            
            # Wert in Holding Register schreiben über den Hub
            if self._input_type == "holding":
                from homeassistant.components.modbus.const import CALL_TYPE_WRITE_REGISTERS
                result = await hub.async_pb_call(
                    self._slave_id,
                    self._address,
                    [int(final_value)],
                    CALL_TYPE_WRITE_REGISTERS
                )
                
                if result.isError():
                    _LOGGER.error("Fehler beim Schreiben in Holding Register %s: %s", self._address, result)
                else:
                    _LOGGER.debug("Option %s erfolgreich in Register %s geschrieben", option, self._address)
                    self._attr_current_option = option
                    self.async_write_ha_state()
            else:
                _LOGGER.warning("Kann nicht in %s Register schreiben: %d", self._input_type, self._address)
                return
                
        except Exception as e:
            _LOGGER.error("Fehler beim Setzen der Option %s: %s", option, str(e))

    def _process_register_value(self, registers):
        """Process register values based on data_type."""
        try:
            if not registers:
                return None
                
            if self._data_type == "uint16":
                return registers[0]
            elif self._data_type == "int16":
                value = registers[0]
                if value > 32767:
                    value -= 65536
                return value
            elif self._data_type == "uint32":
                if len(registers) >= 2:
                    if self._swap:
                        return (registers[1] << 16) | registers[0]
                    else:
                        return (registers[0] << 16) | registers[1]
            elif self._data_type == "int32":
                if len(registers) >= 2:
                    value = (registers[0] << 16) | registers[1]
                    if value > 2147483647:
                        value -= 4294967296
                    return value
            elif self._data_type in ["float", "float32"]:
                # Float32 conversion (2 registers)
                if len(registers) >= 2:
                    import struct
                    # Combine two 16-bit registers into 32-bit float
                    if self._swap:
                        # Swap byte order if needed
                        combined = (registers[1] << 16) | registers[0]
                    else:
                        combined = (registers[0] << 16) | registers[1]
                    
                    # Convert to float using struct
                    try:
                        # Pack as 32-bit unsigned integer, then unpack as float
                        packed = struct.pack('>I', combined)
                        value = struct.unpack('>f', packed)[0]
                        _LOGGER.debug("Float32 conversion for %s: byte_order=%s, raw=%s, value=%s",
                                    self.name, "big" if not self._swap else "little", 
                                    [registers[0], registers[1]], value)
                        return value
                    except Exception as e:
                        _LOGGER.error("Error in float32 conversion for %s: %s", self.name, str(e))
                        return None
                else:
                    _LOGGER.error("float32 requires at least 2 registers, got %d for %s",
                                len(registers), self.name)
                    return None
            elif self._data_type == "float64":
                # Float64 conversion (4 registers)
                if len(registers) >= 4:
                    import struct
                    # Combine four 16-bit registers into 64-bit float
                    if self._swap:
                        # Swap byte order if needed
                        combined = ((registers[3] << 48) | (registers[2] << 32) | 
                                  (registers[1] << 16) | registers[0])
                    else:
                        combined = ((registers[0] << 48) | (registers[1] << 32) | 
                                  (registers[2] << 16) | registers[3])
                    
                    # Convert to float using struct
                    try:
                        # Pack as 64-bit unsigned integer, then unpack as double
                        packed = struct.pack('>Q', combined)
                        value = struct.unpack('>d', packed)[0]
                        _LOGGER.debug("Float64 conversion for %s: byte_order=%s, raw=%s, value=%s",
                                    self.name, "big" if not self._swap else "little", 
                                    registers, value)
                        return value
                    except Exception as e:
                        _LOGGER.error("Error in float64 conversion for %s: %s", self.name, str(e))
                        return None
                else:
                    _LOGGER.error("float64 requires at least 4 registers, got %d for %s",
                                len(registers), self.name)
                    return None
            else:
                return registers[0]
                
        except Exception as e:
            _LOGGER.error("Error in register processing: %s", str(e))
            return None

    def _process_value(self, raw_value):
        """Process the raw Modbus value (same logic as sensors)."""
        try:
            if raw_value is None:
                return None
            
            # For other data types, ensure it's a list
            if not isinstance(raw_value, list):
                raw_value = [raw_value]
            
            # Process based on data_type
            if self._data_type == "uint16":
                if len(raw_value) > 0:
                    value = int(raw_value[0])
                else:
                    return None
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "int16":
                if len(raw_value) > 0:
                    value = int(raw_value[0])
                    if value > 32767:  # Negative Zahl in 16-bit
                        value = value - 65536
                else:
                    return None
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "uint32":
                if len(raw_value) >= 2:
                    # Handle word swap if configured
                    if self._swap:
                        value = (int(raw_value[1]) << 16) | int(raw_value[0])
                    else:
                        value = (int(raw_value[0]) << 16) | int(raw_value[1])
                else:
                    _LOGGER.error("uint32 requires at least 2 registers, got %d for %s", 
                                 len(raw_value), self.name)
                    return None
                
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "int32":
                if len(raw_value) >= 2:
                    # Handle word swap if configured
                    if self._swap:
                        value = (int(raw_value[1]) << 16) | int(raw_value[0])
                    else:
                        value = (int(raw_value[0]) << 16) | int(raw_value[1])
                    
                    if value > 2147483647:  # Negative Zahl in 32-bit
                        value = value - 4294967296
                else:
                    _LOGGER.error("int32 requires at least 2 registers, got %d for %s", 
                                 len(raw_value), self.name)
                    return None
                
                processed_value = (value * self._scale) + self._offset
                
            else:
                # Fallback für unbekannte Typen
                if len(raw_value) > 0:
                    value = int(raw_value[0])
                else:
                    return None
                processed_value = (value * self._scale) + self._offset
            
            return processed_value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Wertverarbeitung für %s: %s", self.name, str(e))
            return None

    def _apply_value_processing(self, value: Any) -> Any:
        """Apply value processing like map, flags, and options (same as sensors)."""
        try:
            if value is None:
                return None
            
            _LOGGER.debug("Select %s: Processing value %s (type: %s)", self.name, value, type(value))
            
            # Nur numerische Werte verarbeiten
            if isinstance(value, (int, float)):
                int_value = int(value)
            
            # 1. Map anwenden (falls definiert)
            if self._map:
                if isinstance(value, (int, float)):
                    # Numerische Werte - prüfe sowohl int als auch string keys
                    int_value = int(value)
                    if int_value in self._map:
                        mapped_value = self._map[int_value]
                        _LOGGER.debug("Mapped value %s to '%s' for %s", int_value, mapped_value, self.name)
                        return mapped_value
                    elif str(int_value) in self._map:
                        # Fallback: prüfe string key
                        mapped_value = self._map[str(int_value)]
                        _LOGGER.debug("Mapped value %s (as string) to '%s' for %s", int_value, mapped_value, self.name)
                        return mapped_value
                    else:
                        _LOGGER.debug("Value %s not found in map for %s", int_value, self.name)
                elif isinstance(value, str):
                    # String-Werte - prüfe sowohl string als auch int keys
                    if value in self._map:
                        mapped_value = self._map[value]
                        _LOGGER.debug("Mapped string '%s' to '%s' for %s", value, mapped_value, self.name)
                        return mapped_value
                    elif value.isdigit() and int(value) in self._map:
                        # Fallback: prüfe int key
                        mapped_value = self._map[int(value)]
                        _LOGGER.debug("Mapped string '%s' (as int) to '%s' for %s", value, mapped_value, self.name)
                        return mapped_value
                    else:
                        _LOGGER.debug("String '%s' not found in map for %s", value, self.name)
            
            # 2. Flags anwenden (falls definiert)
            if self._flags and isinstance(value, (int, float)):
                int_value = int(value)
                flag_list = []
                for bit, flag_name in self._flags.items():
                    if int_value & (1 << int(bit)):
                        flag_list.append(flag_name)
                
                if flag_list:
                    _LOGGER.debug("Extracted flags from %s: %s", int_value, flag_list)
                    return ", ".join(flag_list)
            
            # 3. Options anwenden (falls definiert)
            if self._value_to_text and isinstance(value, (int, float)):
                int_value = int(value)
                # Prüfe sowohl int als auch string keys
                if int_value in self._value_to_text:
                    option_value = self._value_to_text[int_value]
                    _LOGGER.debug("Found option for %s: '%s'", int_value, option_value)
                    return option_value
                elif str(int_value) in self._value_to_text:
                    option_value = self._value_to_text[str(int_value)]
                    _LOGGER.debug("Found option for %s: '%s'", int_value, option_value)
                    return option_value
                else:
                    _LOGGER.debug("Value %s not found in options for %s", int_value, self.name)
            
            # Keine Verarbeitung angewendet - return original value
            _LOGGER.debug("No value processing applied for %s, returning original value: %s", self.name, value)
            return value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Wertverarbeitung für %s: %s", self.name, str(e))
            return value

    def _apply_data_processing(self, value):
        """Wende erweiterte Datenverarbeitung an."""
        try:
            # Multiplier anwenden
            if self._multiplier != 1.0:
                value *= self._multiplier
            
            # Offset anwenden
            if self._offset != 0.0:
                value += self._offset
            
            return value
            
        except Exception as e:
            _LOGGER.error("Fehler bei Datenverarbeitung: %s", str(e))
            return value

    def _apply_reverse_data_processing(self, value):
        """Wende erweiterte Datenverarbeitung rückwärts an."""
        try:
            # Offset rückwärts anwenden
            if self._offset != 0.0:
                value -= self._offset
            
            # Multiplier rückwärts anwenden
            if self._multiplier != 1.0:
                value /= self._multiplier
            
            return value
            
        except Exception as e:
            _LOGGER.error("Fehler bei rückwärtiger Datenverarbeitung: %s", str(e))
            return value 