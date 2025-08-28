"""Modbus Manager Sensor Platform."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager sensors from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    hub_name = f"modbus_manager_{prefix}"

    entities = []

    for reg in registers:
        # Unique_ID Format: {prefix}_{template_sensor_name}
        sensor_name = reg.get("name", "unknown")
        unique_id = f"{prefix}_{sensor_name.lower().replace(' ', '_')}"
        
        entities.append(ModbusTemplateSensor(
            hass=hass,
            name=sensor_name,
            unique_id=unique_id,
            hub_name=hub_name,
            slave_id=entry.data.get("slave_id", 1),
            register_data=reg,
            device_info={
                "identifiers": {(DOMAIN, f"{prefix}_{template_name}")},
                "name": f"{prefix} {template_name}",
                "manufacturer": "Modbus Manager",
                "model": template_name,
                "via_device": (DOMAIN, hub_name)
            }
        ))

    async_add_entities(entities)


class ModbusTemplateSensor(SensorEntity):
    """Representation of a Modbus Template Sensor."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, hub_name: str, 
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the sensor."""
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._hub_name = hub_name
        self._slave_id = slave_id
        self._register_data = register_data
        self._attr_device_info = DeviceInfo(**device_info)
        
        # Register properties
        self._address = register_data.get("address", 0)
        self._data_type = register_data.get("data_type", "uint16")
        self._input_type = register_data.get("input_type", "input")
        self._count = register_data.get("count", 1)
        self._scale = register_data.get("scale", 1.0)
        self._precision = register_data.get("precision", 0)
        self._swap = register_data.get("swap", False)
        
        # Neue Datenverarbeitungsoptionen aus modbus_connect
        self._offset = register_data.get("offset", 0.0)
        self._multiplier = register_data.get("multiplier", 1.0)
        self._sum_scale = register_data.get("sum_scale")
        self._shift_bits = register_data.get("shift_bits", 0)
        self._bits = register_data.get("bits")
        self._is_float = register_data.get("float", False)
        self._is_string = register_data.get("string", False)
        self._map = register_data.get("map", {})
        self._flags = register_data.get("flags", {})
        
        # Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class")
        self._attr_state_class = register_data.get("state_class")
        
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
        """Update the sensor state."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Standard Home Assistant Modbus API nutzen
            if self._input_type == "input":
                result = await hub.read_input_registers(self._address, self._count, unit=self._slave_id)
            else:
                result = await hub.read_holding_registers(self._address, self._count, unit=self._slave_id)
            
            if result.isError():
                _LOGGER.warning("Fehler beim Lesen von Register %s: %s", self._address, result)
                self._attr_native_value = None
                return
            
            # Wert verarbeiten basierend auf data_type
            raw_value = self._process_register_value(result.registers)
            
            # Erweiterte Datenverarbeitung anwenden
            if raw_value is not None:
                processed_value = self._apply_data_processing(raw_value)
                
                # Skalierung anwenden
                scaled_value = processed_value * self._scale
                
                # Offset anwenden
                final_value = scaled_value + self._offset
                
                # Präzision anwenden
                if self._precision > 0:
                    final_value = round(final_value, self._precision)
                
                self._attr_native_value = final_value
            else:
                self._attr_native_value = None
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Sensor %s: %s", self._attr_name, str(e))
            self._attr_native_value = None

    def _process_register_value(self, registers):
        """Process register value based on data type and count."""
        try:
            if self._count == 1:
                raw_value = registers[0]
            else:
                # Für 32-bit Werte (2 Register)
                if self._swap:
                    raw_value = (registers[1] << 16) | registers[0]
                else:
                    raw_value = (registers[0] << 16) | registers[1]
            
            # Konvertierung basierend auf data_type
            if self._data_type == "int16":
                raw_value = raw_value if raw_value < 32768 else raw_value - 65536
            elif self._data_type == "string":
                # String aus Registern extrahieren
                raw_value = self._registers_to_string(registers)
            elif self._data_type == "float":
                # Float aus Registern extrahieren
                raw_value = self._registers_to_float(registers)
            elif self._data_type == "boolean":
                # Boolean aus Register extrahieren
                raw_value = bool(raw_value)
            
            return raw_value
            
        except (IndexError, ValueError) as e:
            _LOGGER.error("Fehler bei der Verarbeitung der Register-Werte: %s", str(e))
            return None

    def _apply_data_processing(self, raw_value):
        """Apply advanced data processing options from modbus_connect."""
        try:
            processed_value = raw_value
            
            # Sum_scale anwenden (für mehrere Register)
            if self._sum_scale and isinstance(self._sum_scale, list):
                # Hier würden wir mehrere Register verarbeiten
                # Für jetzt verwenden wir den ersten Wert
                pass
            
            # Bit-Shift anwenden
            if self._shift_bits > 0:
                processed_value = processed_value >> self._shift_bits
            
            # Bit-Mask anwenden
            if self._bits is not None:
                processed_value = processed_value & ((1 << self._bits) - 1)
            
            # Multiplier anwenden
            processed_value = processed_value * self._multiplier
            
            # Map anwenden (Enum-Mapping)
            if self._map and processed_value in self._map:
                processed_value = self._map[processed_value]
            
            # Flags verarbeiten (Bit-Flags)
            if self._flags and isinstance(processed_value, (int, float)):
                flag_attributes = {}
                for bit, flag_name in self._flags.items():
                    if isinstance(bit, int) and bit >= 0:
                        flag_value = bool(processed_value & (1 << bit))
                        flag_attributes[f"flag_{flag_name}"] = flag_value
                
                if flag_attributes:
                    self._attr_extra_state_attributes = {
                        **(self._attr_extra_state_attributes or {}),
                        **flag_attributes
                    }
            
            return processed_value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Datenverarbeitung: %s", str(e))
            return raw_value

    def _registers_to_string(self, registers):
        """Convert registers to string."""
        try:
            # Jedes Register zu 2 ASCII-Zeichen konvertieren
            string_parts = []
            for reg in registers:
                high_byte = (reg >> 8) & 0xFF
                low_byte = reg & 0xFF
                if high_byte != 0:
                    string_parts.append(chr(high_byte))
                if low_byte != 0:
                    string_parts.append(chr(low_byte))
            return ''.join(string_parts).strip('\x00')
        except Exception as e:
            _LOGGER.error("Fehler bei String-Konvertierung: %s", str(e))
            return None

    def _registers_to_float(self, registers):
        """Convert registers to float (32-bit)."""
        try:
            if len(registers) < 2:
                return None
            
            # IEEE 754 Float aus 2 Registern
            if self._swap:
                raw_bytes = (registers[1] << 16) | registers[0]
            else:
                raw_bytes = (registers[0] << 16) | registers[1]
            
            # Float aus Bytes extrahieren
            import struct
            float_bytes = struct.pack('>I', raw_bytes)
            float_value = struct.unpack('>f', float_bytes)[0]
            
            return float_value
            
        except Exception as e:
            _LOGGER.error("Fehler bei Float-Konvertierung: %s", str(e))
            return None
