"""Modbus Template Sensor for Modbus Manager."""
import asyncio
import logging
from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.const import (
    CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_DEVICE_CLASS
)
from homeassistant.components.sensor.const import CONF_STATE_CLASS

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Modbus Template Sensors from a config entry."""
    try:
        _LOGGER.debug("Setup von Modbus Template Sensoren für %s", entry.data.get("prefix", "unbekannt"))
        
        # Daten aus der Konfiguration abrufen
        if entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("Keine Konfigurationsdaten für Entry %s gefunden", entry.entry_id)
            return
        
        config_data = hass.data[DOMAIN][entry.entry_id]
        registers = config_data.get("registers", [])
        prefix = config_data.get("prefix", "unknown")
        template_name = config_data.get("template", "unknown")
        is_aggregates_template = config_data.get("is_aggregates_template", False)
        
        _LOGGER.debug("Konfigurationsdaten abgerufen: prefix=%s, template=%s, register=%d, is_aggregates=%s", 
                     prefix, template_name, len(registers), is_aggregates_template)
        
        if not registers and not is_aggregates_template:
            _LOGGER.warning("Keine Register für Template %s gefunden", template_name)
            return
        
        if is_aggregates_template:
            _LOGGER.debug("Aggregates Template erkannt - überspringe normale Sensor-Erstellung")
        else:
            _LOGGER.debug("Erstelle %d Sensoren für Template %s mit Präfix %s", len(registers), template_name, prefix)
        
        # Entity Registry abrufen für Duplikat-Check
        registry = async_get_entity_registry(hass)
        existing_entities = {
            entity.entity_id for entity in registry.entities.values()
            if entity.entity_id.startswith(f"sensor.{prefix}_")
        }
        
        # Nur Sensor-Entitäten erstellen (nicht für Aggregates Templates)
        entities = []
        if not is_aggregates_template:
            sensor_registers = [reg for reg in registers if reg.get("entity_type") == "sensor"]
            _LOGGER.debug("Gefundene Sensor-Register: %d", len(sensor_registers))
            
            for reg in sensor_registers:
                try:
                    # Unique_ID Format: {prefix}_{template_sensor_name}
                    sensor_name = reg.get("name", "unknown")
                    # Use unique_id from template if available, otherwise use cleaned name
                    template_unique_id = reg.get("unique_id")
                    if template_unique_id:
                        unique_id = f"{prefix}_{template_unique_id}"
                    else:
                        # Fallback: Bereinige den Namen für den unique_id
                        clean_name = sensor_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                        unique_id = f"{prefix}_{clean_name}"
                    # Use same logic for entity_id
                    if template_unique_id:
                        entity_id = f"sensor.{prefix}_{template_unique_id}"
                    else:
                        entity_id = f"sensor.{prefix}_{clean_name}"
                    
                    # Prüfen ob Entity bereits existiert
                    if entity_id in existing_entities:
                        _LOGGER.debug("Sensor %s existiert bereits, überspringe", entity_id)
                        continue
                    
                    _LOGGER.debug("Erstelle Sensor: name=%s, prefix=%s, unique_id=%s", 
                                 sensor_name, prefix, unique_id)
                    
                    entities.append(ModbusTemplateSensor(
                        hass=hass,
                        entry=entry,
                        register=reg,
                        prefix=prefix,
                        unique_id=unique_id
                    ))
                
                except Exception as e:
                    _LOGGER.error("Fehler beim Erstellen des Sensors %s: %s", reg.get("name", "unbekannt"), str(e))
                    continue
        
        # Create calculated entities if available
        calculated_entities = []
        calculated_data = config_data.get("calculated_entities", [])
        
        # Debug: calculated_data aus config_data (reduziert)
        _LOGGER.debug("calculated_data aus config_data: %d items", len(calculated_data))
        
        if calculated_data:
            _LOGGER.debug("Erstelle %d berechnete Sensoren für Template %s", len(calculated_data), template_name)
        
        # Debug: Zeige Gruppen der berechneten Sensoren
        groups = set()
        for calc_config in calculated_data:
            group = calc_config.get("group")
            if group:
                groups.add(group)
        if groups:
            _LOGGER.debug("Berechnete Sensoren haben Gruppen: %s", list(groups))
        else:
            _LOGGER.debug("Berechnete Sensoren haben keine expliziten Gruppen (verwenden Standard-Gruppe)")
        
        # Erstelle berechnete Sensoren (immer, unabhängig von Gruppen)
        for calc_config in calculated_data:
            try:
                # Create calculated sensor using the same logic as calculated.py
                from .calculated import ModbusCalculatedSensor
                
                entity = ModbusCalculatedSensor(
                    hass=hass,
                    config=calc_config,
                    prefix=prefix,
                    template_name=template_name
                )
                calculated_entities.append(entity)
                
            except Exception as e:
                _LOGGER.error("Fehler beim Erstellen des berechneten Sensors %s: %s", 
                             calc_config.get("name", "unbekannt"), str(e))
                continue
        
        # Add aggregate sensors if available (from template aggregates section)
        aggregate_entities = []
        aggregates_config = config_data.get("aggregates", [])
        is_aggregates_template = config_data.get("is_aggregates_template", False)
        
        _LOGGER.debug("Sensor Platform Debug: aggregates_config=%s, is_aggregates_template=%s", 
                     len(aggregates_config) if aggregates_config else "None", is_aggregates_template)
        
        if aggregates_config:
            _LOGGER.debug("Erstelle %d Aggregate-Sensoren aus Template", len(aggregates_config))
            
            for aggregate_config in aggregates_config:
                try:
                    from .aggregates import ModbusAggregateSensor
                    
                    entity = ModbusAggregateSensor(
                        hass=hass,
                        aggregate_config=aggregate_config,
                        prefix=prefix
                    )
                    aggregate_entities.append(entity)
                    
                except Exception as e:
                    _LOGGER.error("Fehler beim Erstellen des Aggregate-Sensors %s: %s", 
                                 aggregate_config.get("name", "unbekannt"), str(e))
                    continue
        
        # For aggregates-only templates, only add aggregate entities
        if is_aggregates_template:
            all_entities = aggregate_entities
            _LOGGER.debug("Aggregates-only Template: %d Aggregate-Sensoren erstellt", len(aggregate_entities))
        else:
            # Regular template: add all entities
            all_entities = entities + calculated_entities + aggregate_entities
        
        # Legacy: Add aggregate sensors from config data (for backward compatibility)
        if not is_aggregates_template:
            legacy_aggregate_sensors = config_data.get("aggregate_sensors", [])
            if legacy_aggregate_sensors:
                _LOGGER.debug("Füge %d Legacy Aggregate-Sensoren hinzu", len(legacy_aggregate_sensors))
                all_entities.extend(legacy_aggregate_sensors)
        
        if all_entities:
            async_add_entities(all_entities)
            _LOGGER.info("Modbus Manager: Created %d sensors, %d calculated sensors, %d aggregate sensors", 
                         len(entities), len(calculated_entities), len(aggregate_entities))
            
            # Debug: List all created entities
            if entities:
                _LOGGER.debug("Created sensors: %s", [e.entity_id for e in entities])
            if calculated_entities:
                _LOGGER.debug("Created calculated sensors: %s", [e.entity_id for e in calculated_entities])
            if aggregate_entities:
                _LOGGER.debug("Created aggregate sensors: %s", [e.entity_id for e in aggregate_entities])
        else:
            _LOGGER.warning("Keine Sensoren erstellt")
            
    except Exception as e:
        _LOGGER.error("Fehler beim Setup der Modbus Template Sensoren: %s", str(e))
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())


class ModbusTemplateSensor(SensorEntity):
    """Representation of a Modbus Template Sensor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, register: dict, prefix: str, unique_id: str):
        """Initialize the Modbus Template Sensor."""
        self._hass = hass
        self._entry = entry
        self._register = register
        self._prefix = prefix
        self._unique_id = unique_id
        
        # Smart error handling - stop trying after multiple failures
        self._consecutive_failures = 0
        self._max_failures = 5  # Stop trying after 5 consecutive failures
        self._disabled = False
        
        # Register properties
        self._name = register.get("name", "Unknown Sensor")
        self._address = register.get("address", 0)
        self._data_type = register.get("data_type", "uint16")
        
        # Always set correct count based on data type, regardless of template
        if self._data_type in ["uint32", "int32", "float", "float32"]:
            self._count = 2  # 32-bit types need 2 registers
        elif self._data_type == "float64":
            self._count = 4  # 64-bit types need 4 registers
        else:
            # For other types, use template count or default to 1
            template_count = register.get("count")
            self._count = template_count if template_count is not None else 1
        
        self._scale = register.get("scale", 1.0)
        self._offset = register.get("offset", 0.0)
        self._unit = register.get("unit_of_measurement", "")
        self._device_class = register.get("device_class")
        self._state_class = register.get("state_class")
        self._precision = register.get("precision", 0)
        self._swap = register.get("swap", False)
        self._byte_order = register.get("byte_order", "big")
        
        # String-spezifische Parameter
        self._encoding = register.get("encoding", "utf-8")
        self._max_length = register.get("max_length", None)
        
        # Modbus-specific properties
        self._input_type = register.get("input_type", "input")
        self._slave_id = register.get("device_address", 1)
        self._verify = register.get("verify", False)
        
        # Value processing (map, flags, options)
        self._map = register.get("map", {})
        self._flags = register.get("flags", {})
        self._options = register.get("options", {})
        
        
        # Group attribute for aggregation
        self._group = register.get("group", None)
        
        # Bit-Operationen
        self._bitmask = register.get("bitmask", None)
        self._bit_position = register.get("bit_position", None)
        self._bit_shift = register.get("bit_shift", 0)
        self._bit_rotate = register.get("bit_rotate", 0)
        self._bit_range = register.get("bit_range", None)
        
        # Set entity attributes
        self._attr_name = f"{prefix}_{self._name}"
        self._attr_unique_id = unique_id
        self._attr_device_class = self._device_class
        self._attr_state_class = self._state_class
        self._attr_native_unit_of_measurement = self._unit
        self._attr_should_poll = True
        
        # For string sensors and sensors with map/flags/options, set device_class and state_class to None
        if (self._data_type == "string" or 
            self._map or 
            self._flags or 
            self._options):
            self._attr_device_class = None
            self._attr_state_class = None
            # These sensors should not have numeric values
            self._attr_native_unit_of_measurement = None
        
        # Device-Info
        template_name = self._register.get("template", "unknown")
        
        # Get firmware version from config entry
        firmware_version = self._entry.data.get("firmware_version", "1.0.0")
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{prefix}_{template_name}")},
            name=f"{prefix} ({template_name})",
            manufacturer="Modbus Manager",
            model=template_name,
            sw_version=f"Firmware: {firmware_version}",
        )
        
                # _LOGGER.debug("Sensor %s initialized (Address: %d, Type: %s, Count: %d, Prefix: %s, Name: %s, Unique-ID: %s, Group: %s)", 
        #                self._name, self._address, self._data_type, self._count, prefix, self._attr_name, unique_id, self._group)

    @property
    def template_name(self) -> str:
        """Return the template name."""
        return self._register.get("template", "unknown")
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attributes = {}
        if self._group:
            attributes["group"] = self._group
        return attributes

    async def async_update(self) -> None:
        """Update the sensor value."""
        try:
            # Skip update if sensor is disabled due to repeated failures
            if self._disabled:
                return
            
            # Get Modbus-Hub from configuration
            if self._entry.entry_id not in self._hass.data[DOMAIN]:
                _LOGGER.error("No configuration data found for Entry %s", self._entry.entry_id)
                return
            
            config_data = self._hass.data[DOMAIN][self._entry.entry_id]
            hub = config_data.get("hub")
            
            if not hub:
                _LOGGER.error("Modbus-Hub not found")
                return
            
            # Modbus operation based on input_type
            if self._input_type == "input":
                # Read input registers
                result = await self._read_input_registers(hub)
            elif self._input_type == "holding":
                # Read holding registers
                result = await self._read_holding_registers(hub)
            elif self._input_type == "coil":
                # Read coils
                result = await self._read_coils(hub)
            elif self._input_type == "discrete":
                # Read discrete inputs
                result = await self._read_discrete_inputs(hub)
            else:
                _LOGGER.warning("Unknown input_type: %s", self._input_type)
                return
            
            if result is not None:
                # Process value
                processed_value = self._process_value(result)
                self._attr_native_value = processed_value
                # Reset failure counter on successful read
                self._consecutive_failures = 0
                # _LOGGER.debug("Sensor %s updated: %s", self._name, processed_value)
            else:
                self._consecutive_failures += 1
                _LOGGER.warning("No data received for sensor %s (failure %d/%d)", 
                              self._name, self._consecutive_failures, self._max_failures)
                
                # Disable sensor after too many consecutive failures
                if self._consecutive_failures >= self._max_failures:
                    self._disabled = True
                    _LOGGER.warning("Sensor %s disabled after %d consecutive failures - register may not be available", 
                                  self._name, self._consecutive_failures)
                
        except Exception as e:
            self._consecutive_failures += 1
            _LOGGER.error("Error updating sensor %s: %s (failure %d/%d)", 
                         self._name, str(e), self._consecutive_failures, self._max_failures)
            
            # Disable sensor after too many consecutive failures
            if self._consecutive_failures >= self._max_failures:
                self._disabled = True
                _LOGGER.warning("Sensor %s disabled after %d consecutive failures", 
                              self._name, self._consecutive_failures)

    async def _read_input_registers(self, hub) -> Optional[Any]:
        """Read input registers from Modbus device."""
        try:
            # Verwende die korrekte Home Assistant Modbus API
            from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_INPUT
            
            # Modbus-Call über Standard API
            result = await hub.async_pb_call(
                self._slave_id,
                self._address,
                self._count,
                CALL_TYPE_REGISTER_INPUT
            )
            
            if result and hasattr(result, 'registers'):
                # For string data type, return all registers as list
                if self._data_type == "string":
                    return result.registers
                else:
                    # For other data types, return single value or list as appropriate
                    if len(result.registers) == 1:
                        return result.registers[0]
                    else:
                        return result.registers
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Input-Register für %s: %s", self._name, str(e))
            return None

    async def _read_holding_registers(self, hub) -> Optional[Any]:
        """Read holding registers from Modbus device."""
        try:
            from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
            
            result = await hub.async_pb_call(
                self._slave_id,
                self._address,
                self._count,
                CALL_TYPE_REGISTER_HOLDING
            )
            
            if result and hasattr(result, 'registers'):
                # For string data type, return all registers as list
                if self._data_type == "string":
                    return result.registers
                else:
                    # For other data types, return single value or list as appropriate
                    if len(result.registers) == 1:
                        return result.registers[0]
                    else:
                        return result.registers
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Holding-Register für %s: %s", self._name, str(e))
            return None

    async def _read_coils(self, hub) -> Optional[Any]:
        """Read coils from Modbus device."""
        try:
            from homeassistant.components.modbus.const import CALL_TYPE_COIL
            
            result = await hub.async_pb_call(
                self._slave_id,
                self._address,
                self._count,
                CALL_TYPE_COIL
            )
            
            if result and hasattr(result, 'bits'):
                return result.bits
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Coils für %s: %s", self._name, str(e))
            return None

    async def _read_discrete_inputs(self, hub) -> Optional[Any]:
        """Read discrete inputs from Modbus device."""
        try:
            from homeassistant.components.modbus.const import CALL_TYPE_DISCRETE
            
            result = await hub.async_pb_call(
                self._slave_id,
                self._address,
                self._count,
                CALL_TYPE_DISCRETE
            )
            
            if result and hasattr(result, 'bits'):
                return result.bits
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Discrete-Inputs für %s: %s", self._name, str(e))
            return None

    def _process_value(self, raw_value: Any) -> Any:
        """Process the raw Modbus value."""
        try:
            if raw_value is None:
                return None
            
            
            # For string data type, raw_value should already be a list of registers
            # For other data types, ensure it's a list
            if self._data_type != "string" and not isinstance(raw_value, list):
                raw_value = [raw_value]
            
            # Wert basierend auf data_type verarbeiten
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
                    if hasattr(self, '_swap') and self._swap == "word":
                        # Swap word order: [high_word, low_word] -> [low_word, high_word]
                        value = (int(raw_value[1]) << 16) | int(raw_value[0])
                    else:
                        # Standard order: [high_word, low_word]
                        value = (int(raw_value[0]) << 16) | int(raw_value[1])
                else:
                    _LOGGER.error("uint32 requires at least 2 registers, got %d for %s", 
                                 len(raw_value), self._name)
                    return None
                
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "int32":
                if len(raw_value) >= 2:
                    # Handle word swap if configured
                    if hasattr(self, '_swap') and self._swap == "word":
                        # Swap word order: [high_word, low_word] -> [low_word, high_word]
                        value = (int(raw_value[1]) << 16) | int(raw_value[0])
                    else:
                        # Standard order: [high_word, low_word]
                        value = (int(raw_value[0]) << 16) | int(raw_value[1])
                    
                    if value > 2147483647:  # Negative Zahl in 32-bit
                        value = value - 4294967296
                else:
                    _LOGGER.error("int32 requires at least 2 registers, got %d for %s", 
                                 len(raw_value), self._name)
                    return None
                
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type in ["float", "float32"]:
                if len(raw_value) >= 2:
                    import struct
                    
                    # Byte-Reihenfolge bestimmen
                    byte_order = self._byte_order if hasattr(self, '_byte_order') else "big"
                    
                    
                    # Format-String für struct basierend auf Byte-Reihenfolge
                    if byte_order == "big":
                        # ABCD - Standard Big Endian
                        raw_bytes = struct.pack('>HH', int(raw_value[0]), int(raw_value[1]))
                        value = struct.unpack('>f', raw_bytes)[0]
                    elif byte_order == "little":
                        # DCBA - Little Endian
                        raw_bytes = struct.pack('<HH', int(raw_value[1]), int(raw_value[0]))
                        value = struct.unpack('<f', raw_bytes)[0]
                    elif byte_order == "big_swap":
                        # BADC - Big Endian mit Wortvertauschung
                        raw_bytes = struct.pack('>HH', int(raw_value[1]), int(raw_value[0]))
                        value = struct.unpack('>f', raw_bytes)[0]
                    elif byte_order == "little_swap":
                        # CDAB - Little Endian mit Wortvertauschung
                        raw_bytes = struct.pack('<HH', int(raw_value[0]), int(raw_value[1]))
                        value = struct.unpack('<f', raw_bytes)[0]
                    else:
                        # Fallback auf alte Logik mit swap
                        if hasattr(self, '_swap') and self._swap == "word":
                            # Swap word order: [high_word, low_word] -> [low_word, high_word]
                            raw_bytes = struct.pack('>HH', int(raw_value[1]), int(raw_value[0]))
                        else:
                            # Standard order: [high_word, low_word]
                            raw_bytes = struct.pack('>HH', int(raw_value[0]), int(raw_value[1]))
                        value = struct.unpack('>f', raw_bytes)[0]
                    
                    _LOGGER.debug("Float conversion for %s: byte_order=%s, raw=%s, value=%s", 
                                 self._name, byte_order, raw_value, value)
                else:
                    return None
                
                
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "float64":
                if len(raw_value) >= 4:
                    import struct
                    
                    # Byte-Reihenfolge bestimmen
                    byte_order = self._byte_order if hasattr(self, '_byte_order') else "big"
                    
                    # Format-String für struct basierend auf Byte-Reihenfolge
                    if byte_order == "big":
                        # ABCDEFGH - Standard Big Endian
                        raw_bytes = struct.pack('>HHHH', 
                                              int(raw_value[0]), int(raw_value[1]),
                                              int(raw_value[2]), int(raw_value[3]))
                        value = struct.unpack('>d', raw_bytes)[0]
                    elif byte_order == "little":
                        # HGFEDCBA - Little Endian
                        raw_bytes = struct.pack('<HHHH', 
                                              int(raw_value[3]), int(raw_value[2]),
                                              int(raw_value[1]), int(raw_value[0]))
                        value = struct.unpack('<d', raw_bytes)[0]
                    elif byte_order == "big_swap":
                        # BADCFEHG - Big Endian mit Wortvertauschung
                        raw_bytes = struct.pack('>HHHH', 
                                              int(raw_value[1]), int(raw_value[0]),
                                              int(raw_value[3]), int(raw_value[2]))
                        value = struct.unpack('>d', raw_bytes)[0]
                    elif byte_order == "little_swap":
                        # GHEFCDAB - Little Endian mit Wortvertauschung
                        raw_bytes = struct.pack('<HHHH', 
                                              int(raw_value[2]), int(raw_value[3]),
                                              int(raw_value[0]), int(raw_value[1]))
                        value = struct.unpack('<d', raw_bytes)[0]
                    else:
                        # Fallback auf alte Logik mit swap
                        if hasattr(self, '_swap') and self._swap == "word":
                            # Swap word order for 64-bit float
                            raw_bytes = struct.pack('>HHHH', 
                                                  int(raw_value[3]), int(raw_value[2]),
                                                  int(raw_value[1]), int(raw_value[0]))
                        else:
                            # Standard order for 64-bit float
                            raw_bytes = struct.pack('>HHHH', 
                                                  int(raw_value[0]), int(raw_value[1]),
                                                  int(raw_value[2]), int(raw_value[3]))
                        value = struct.unpack('>d', raw_bytes)[0]
                    
                    _LOGGER.debug("Float64 conversion for %s: byte_order=%s, raw=%s, value=%s", 
                                 self._name, byte_order, raw_value, value)
                else:
                    _LOGGER.error("float64 requires at least 4 registers, got %d for %s", 
                                 len(raw_value), self._name)
                    return None
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "string":
                if len(raw_value) > 0:
                    
                    # String-Encoding bestimmen (Standard: UTF-8)
                    encoding = getattr(self, '_encoding', 'utf-8')
                    max_length = getattr(self, '_max_length', None)
                    
                    # String aus Registern extrahieren
                    string_value = ""
                    bytes_array = bytearray()
                    
                    for reg in raw_value:
                        if reg == 0:  # Null-Terminator
                            break
                        reg_int = int(reg)
                        # Zwei Bytes pro Register (Big-Endian)
                        bytes_array.extend([(reg_int >> 8) & 0xFF, reg_int & 0xFF])
                    
                    _LOGGER.debug("String processing for %s: bytes_array=%s", 
                                 self._name, bytes_array.hex())
                    
                    try:
                        # String dekodieren
                        string_value = bytes_array.decode(encoding, errors='replace')
                        
                        # Null-Bytes und Whitespace am Ende entfernen
                        string_value = string_value.strip('\x00').rstrip()
                        
                        # Länge begrenzen, falls erforderlich
                        if max_length and len(string_value) > max_length:
                            string_value = string_value[:max_length]
                            _LOGGER.debug("String for %s truncated to %d characters", 
                                         self._name, max_length)
                    except Exception as e:
                        _LOGGER.error("Error decoding string for %s: %s", self._name, str(e))
                        string_value = ""
                    
                    value = string_value
                else:
                    value = ""
                processed_value = value
                
            elif self._data_type == "boolean":
                if len(raw_value) > 0:
                    value = bool(int(raw_value[0]))
                else:
                    return None
                processed_value = value
                
            else:
                # Fallback für unbekannte Typen
                if len(raw_value) > 0:
                    value = int(raw_value[0])
                else:
                    return None
                processed_value = (value * self._scale) + self._offset
            
            # Bit-Operationen anwenden (vor der Präzision)
            if isinstance(processed_value, (int, float)) and (self._bitmask is not None or self._bit_position is not None or self._bit_range is not None or self._bit_shift != 0 or self._bit_rotate != 0):
                int_value = int(processed_value)
                
                # Bit-Position extrahieren (einzelnes Bit)
                if self._bit_position is not None:
                    bit_pos = int(self._bit_position)
                    if 0 <= bit_pos <= 31:
                        int_value = (int_value >> bit_pos) & 1
                
                # Bit-Bereich extrahieren
                elif self._bit_range is not None:
                    if isinstance(self._bit_range, list) and len(self._bit_range) == 2:
                        start_bit, end_bit = self._bit_range
                        if 0 <= start_bit <= end_bit <= 31:
                            mask = ((1 << (end_bit - start_bit + 1)) - 1) << start_bit
                            int_value = (int_value & mask) >> start_bit
                
                # Bitmask anwenden
                if self._bitmask is not None:
                    int_value = int_value & self._bitmask
                
                # Bit-Shift anwenden
                if self._bit_shift != 0:
                    if self._bit_shift > 0:
                        int_value = int_value << self._bit_shift
                    else:
                        int_value = int_value >> abs(self._bit_shift)
                
                # Bit-Rotation anwenden
                if self._bit_rotate != 0:
                    bits = 32
                    rotate_amount = self._bit_rotate % bits
                    if rotate_amount > 0:
                        int_value = ((int_value << rotate_amount) | (int_value >> (bits - rotate_amount))) & ((1 << bits) - 1)
                    elif rotate_amount < 0:
                        rotate_amount = abs(rotate_amount)
                        int_value = ((int_value >> rotate_amount) | (int_value << (bits - rotate_amount))) & ((1 << bits) - 1)
                
                processed_value = int_value
            
            # Präzision anwenden (nach den Bit-Operationen)
            if isinstance(processed_value, (int, float)) and self._precision > 0:
                # Stelle sicher, dass der Wert als Float behandelt wird
                if isinstance(processed_value, int):
                    processed_value = float(processed_value)
                processed_value = round(processed_value, self._precision)
            
            # Wertverarbeitung anwenden (nur map, flags, options)
            processed_value = self._apply_value_processing(processed_value)
            
            return processed_value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Wertverarbeitung für %s: %s", self._name, str(e))
            return None

    def _apply_value_processing(self, value: Any) -> Any:
        """Apply value processing like map, flags, and options."""
        try:
            if value is None:
                return None
            
            # Nur numerische Werte verarbeiten
            if isinstance(value, (int, float)):
                int_value = int(value)
            
            # 2. Map anwenden (falls definiert)
            if self._map:
                if isinstance(value, (int, float)):
                    # Numerische Werte - prüfe sowohl int als auch string keys
                    int_value = int(value)
                    if int_value in self._map:
                        mapped_value = self._map[int_value]
                        _LOGGER.debug("Mapped value %s to '%s' for %s", int_value, mapped_value, self._name)
                        return mapped_value
                    elif str(int_value) in self._map:
                        # Fallback: prüfe string key
                        mapped_value = self._map[str(int_value)]
                        _LOGGER.debug("Mapped value %s (as string) to '%s' for %s", int_value, mapped_value, self._name)
                        return mapped_value
                    else:
                        _LOGGER.debug("Value %s not found in map for %s", int_value, self._name)
                elif isinstance(value, str):
                    # String-Werte - prüfe sowohl string als auch int keys
                    if value in self._map:
                        mapped_value = self._map[value]
                        _LOGGER.debug("Mapped string '%s' to '%s' for %s", value, mapped_value, self._name)
                        return mapped_value
                    elif value.isdigit() and int(value) in self._map:
                        # Fallback: prüfe int key
                        mapped_value = self._map[int(value)]
                        _LOGGER.debug("Mapped string '%s' (as int) to '%s' for %s", value, mapped_value, self._name)
                        return mapped_value
                    else:
                        _LOGGER.debug("String '%s' not found in map for %s", value, self._name)
            
            # 3. Flags anwenden (falls definiert)
            if self._flags and isinstance(value, (int, float)):
                int_value = int(value)
                flag_list = []
                for bit, flag_name in self._flags.items():
                    if int_value & (1 << int(bit)):
                        flag_list.append(flag_name)
                
                if flag_list:
                    _LOGGER.debug("Extracted flags from %s: %s", int_value, flag_list)
                    return ", ".join(flag_list)
            
            # 4. Options anwenden (falls definiert)
            if self._options and isinstance(value, (int, float)):
                int_value = int(value)
                if int_value in self._options:
                    option_value = self._options[int_value]
                    _LOGGER.debug("Found option for %s: '%s'", int_value, option_value)
                    return option_value
            
            # Keine Verarbeitung angewendet
            return value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Wertverarbeitung für %s: %s", self._name, str(e))
            return value
