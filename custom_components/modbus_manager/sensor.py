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
        _LOGGER.info("Setup von Modbus Template Sensoren für %s", entry.data.get("prefix", "unbekannt"))
        
        # Daten aus der Konfiguration abrufen
        if entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("Keine Konfigurationsdaten für Entry %s gefunden", entry.entry_id)
            return
        
        config_data = hass.data[DOMAIN][entry.entry_id]
        registers = config_data.get("registers", [])
        prefix = config_data.get("prefix", "unknown")
        template_name = config_data.get("template", "unknown")
        
        _LOGGER.info("Konfigurationsdaten abgerufen: prefix=%s, template=%s, register=%d", 
                     prefix, template_name, len(registers))
        
        if not registers:
            _LOGGER.warning("Keine Register für Template %s gefunden", template_name)
            return
        
        _LOGGER.info("Erstelle %d Sensoren für Template %s mit Präfix %s", len(registers), template_name, prefix)
        
        # Entity Registry abrufen für Duplikat-Check
        registry = async_get_entity_registry(hass)
        existing_entities = {
            entity.entity_id for entity in registry.entities.values()
            if entity.entity_id.startswith(f"sensor.{prefix}_")
        }
        
        # Nur Sensor-Entitäten erstellen
        sensor_registers = [reg for reg in registers if reg.get("entity_type") == "sensor"]
        _LOGGER.info("Gefundene Sensor-Register: %d", len(sensor_registers))
        
        entities = []
        for reg in sensor_registers:
            try:
                # Unique_ID Format: {prefix}_{template_sensor_name}
                sensor_name = reg.get("name", "unknown")
                # Bereinige den Namen für den unique_id
                clean_name = sensor_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                unique_id = f"{prefix}_{clean_name}"
                entity_id = f"sensor.{prefix}_{clean_name}"
                
                # Prüfen ob Entity bereits existiert
                if entity_id in existing_entities:
                    _LOGGER.debug("Sensor %s existiert bereits, überspringe", entity_id)
                    continue
                
                _LOGGER.info("Erstelle Sensor: name=%s, prefix=%s, unique_id=%s", 
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
        
        if calculated_data:
            _LOGGER.info("Erstelle %d berechnete Sensoren für Template %s", len(calculated_data), template_name)
            
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
        
        # Add all entities (regular sensors + calculated sensors)
        all_entities = entities + calculated_entities
        
        if all_entities:
            async_add_entities(all_entities)
            _LOGGER.info("%d Modbus Template Sensoren und %d berechnete Sensoren erfolgreich erstellt", 
                         len(entities), len(calculated_entities))
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
        
        # Register properties
        self._name = register.get("name", "Unknown Sensor")
        self._address = register.get("address", 0)
        self._data_type = register.get("data_type", "uint16")
        
        # Auto-set count for 32-bit data types
        base_count = register.get("count", 1)
        if self._data_type in ["uint32", "int32", "float"]:
            self._count = 2  # 32-bit types always need 2 registers
            if base_count != 2:
                _LOGGER.debug("Auto-corrected count from %s to 2 for %s (%s)", 
                             base_count, self._name, self._data_type)
        else:
            self._count = base_count
        
        self._scale = register.get("scale", 1.0)
        self._offset = register.get("offset", 0.0)
        self._unit = register.get("unit_of_measurement", "")
        self._device_class = register.get("device_class")
        self._state_class = register.get("state_class")
        self._precision = register.get("precision", 0)
        self._swap = register.get("swap", False)
        
        # Modbus-specific properties
        self._input_type = register.get("input_type", "input")
        self._slave_id = register.get("device_address", 1)
        self._verify = register.get("verify", False)
        self._retries = register.get("retries", 3)
        
        # Value processing (map, flags, options)
        self._map = register.get("map", {})
        self._flags = register.get("flags", {})
        self._options = register.get("options", {})
        self._bitmask = register.get("bitmask", None)
        
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{prefix}_{template_name}")},
            name=f"{prefix} ({template_name})",
            manufacturer="Modbus Manager",
            model=template_name,
            via_device=(DOMAIN, entry.entry_id),
        )
        
        _LOGGER.info("Sensor %s initialized (Address: %d, Type: %s, Prefix: %s, Name: %s, Unique-ID: %s)", 
                     self._name, self._address, self._data_type, prefix, self._attr_name, unique_id)

    @property
    def template_name(self) -> str:
        """Return the template name."""
        return self._register.get("template", "unknown")

    async def async_update(self) -> None:
        """Update the sensor value."""
        try:
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
                _LOGGER.debug("Sensor %s updated: %s", self._name, processed_value)
            else:
                _LOGGER.warning("No data received for sensor %s", self._name)
                
        except Exception as e:
            _LOGGER.error("Error updating sensor %s: %s", self._name, str(e))

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
            
            # Sicherstellen, dass raw_value eine Liste ist
            if not isinstance(raw_value, list):
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
                
            elif self._data_type == "float":
                if len(raw_value) >= 2:
                    import struct
                    # Handle word swap if configured
                    if hasattr(self, '_swap') and self._swap == "word":
                        # Swap word order: [high_word, low_word] -> [low_word, high_word]
                        raw_bytes = struct.pack('>HH', int(raw_value[1]), int(raw_value[0]))
                    else:
                        # Standard order: [high_word, low_word]
                        raw_bytes = struct.pack('>HH', int(raw_value[0]), int(raw_value[1]))
                    value = struct.unpack('>f', raw_bytes)[0]
                else:
                    return None
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "string":
                if len(raw_value) > 0:
                    # String aus Registern extrahieren
                    string_value = ""
                    for reg in raw_value:
                        if reg == 0:  # Null-Terminator
                            break
                        reg_int = int(reg)
                        string_value += chr((reg_int >> 8) & 0xFF) + chr(reg_int & 0xFF)
                    value = string_value.strip('\x00')
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
            
            # Präzision anwenden
            if isinstance(processed_value, (int, float)) and self._precision > 0:
                processed_value = round(processed_value, self._precision)
            
            # Wertverarbeitung anwenden (map, flags, options, bitmask)
            processed_value = self._apply_value_processing(processed_value)
            
            return processed_value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Wertverarbeitung für %s: %s", self._name, str(e))
            _LOGGER.debug("Raw value: %s, data_type: %s, scale: %s, offset: %s", 
                         raw_value, self._data_type, self._scale, self._offset)
            return None

    def _apply_value_processing(self, value: Any) -> Any:
        """Apply value processing like map, flags, options, and bitmask."""
        try:
            if value is None:
                return None
            
            # 1. Bitmask anwenden (falls definiert)
            if self._bitmask is not None:
                if isinstance(value, (int, float)):
                    value = int(value) & self._bitmask
                    _LOGGER.debug("Applied bitmask 0x%X to %s: result = %s", 
                                 self._bitmask, value, value)
            
            # 2. Map anwenden (falls definiert)
            if self._map and isinstance(value, (int, float)):
                int_value = int(value)
                if int_value in self._map:
                    mapped_value = self._map[int_value]
                    _LOGGER.debug("Mapped value %s to '%s'", int_value, mapped_value)
                    return mapped_value
            
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
