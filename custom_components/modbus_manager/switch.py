"""Modbus Manager Switch Platform."""
from __future__ import annotations
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager switch entities from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    hub_name = f"modbus_manager_{prefix}"

    entities = []

    for reg in registers:
        # Nur Switch-Entities aus Registern mit control: "switch" erstellen
        if reg.get("control") == "switch":
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
            
            entities.append(ModbusTemplateSwitch(
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
        
                }
            ))

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Modbus Manager: Created %d switch entities", len(entities))
        _LOGGER.debug("Created switch entities: %s", [e.entity_id for e in entities])


class ModbusTemplateSwitch(SwitchEntity):
    """Representation of a Modbus Template Switch Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, hub_name: str, 
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the switch entity."""
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
        self._input_type = register_data.get("input_type", "holding")
        self._count = register_data.get("count", 1)
        self._scale = register_data.get("scale", 1.0)
        self._swap = register_data.get("swap", False)
        
        # Neue Datenverarbeitungsoptionen
        self._offset = register_data.get("offset", 0.0)
        self._multiplier = register_data.get("multiplier", 1.0)
        
        # Value processing (map, flags, options) - same as sensors
        self._map = register_data.get("map", {})
        self._flags = register_data.get("flags", {})
        self._options = register_data.get("options", {})
        
        # Switch-Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class")
        self._attr_state_class = register_data.get("state_class")
        
        # Switch-Konfiguration
        self._on_value = register_data.get("on_value", 1)
        self._off_value = register_data.get("off_value", 0)
        
        # Group for aggregations
        self._group = register_data.get("group")
        if self._group:
            self._attr_extra_state_attributes = {"group": self._group}
        
        self._attr_is_on = False

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return True

    async def async_update(self):
        """Update the switch entity state."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Holding Register lesen (read/write)
            result = await hub.read_holding_registers(self._address, self._count, unit=self._slave_id)
            
            if result.isError():
                _LOGGER.warning("Fehler beim Lesen von Holding Register %s: %s", self._address, result)
                self._attr_is_on = False
                return
            
            # Wert verarbeiten
            raw_value = self._process_register_value(result.registers)
            
            if raw_value is not None:
                # Apply value processing (same logic as sensors: map -> flags -> options)
                processed_value = self._apply_value_processing(raw_value)
                
                if processed_value is not None:
                    # Erweiterte Datenverarbeitung anwenden
                    processed_value = self._apply_data_processing(processed_value)
                    
                    # Switch-Status bestimmen
                    self._attr_is_on = processed_value == self._on_value
                else:
                    self._attr_is_on = False
            else:
                self._attr_is_on = False
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Switch %s: %s", self.name, str(e))
            self._attr_is_on = False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Erweiterte Datenverarbeitung rückwärts anwenden
            final_value = self._apply_reverse_data_processing(self._on_value)
            
            # ON-Wert in Holding Register schreiben
            result = await hub.write_register(self._address, int(final_value), unit=self._slave_id)
            
            if result.isError():
                _LOGGER.error("Fehler beim Schreiben in Holding Register %s: %s", self._address, result)
            else:
                _LOGGER.debug("Switch %s erfolgreich eingeschaltet", self.name)
                self._attr_is_on = True
                self.async_write_ha_state()
                
        except Exception as e:
            _LOGGER.error("Fehler beim Einschalten von Switch %s: %s", self.name, str(e))

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Erweiterte Datenverarbeitung rückwärts anwenden
            final_value = self._apply_reverse_data_processing(self._off_value)
            
            # OFF-Wert in Holding Register schreiben
            result = await hub.write_register(self._address, int(final_value), unit=self._slave_id)
            
            if result.isError():
                _LOGGER.error("Fehler beim Schreiben in Holding Register %s: %s", self._address, result)
            else:
                _LOGGER.debug("Switch %s erfolgreich ausgeschaltet", self.name)
                self._attr_is_on = False
                self.async_write_ha_state()
                
        except Exception as e:
            _LOGGER.error("Fehler beim Ausschalten von Switch %s: %s", self.name, str(e))

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

    def _apply_value_processing(self, value: Any) -> Any:
        """Apply value processing like map, flags, and options (same as sensors)."""
        try:
            if value is None:
                return None
            
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
            if self._options and isinstance(value, (int, float)):
                int_value = int(value)
                if int_value in self._options:
                    option_value = self._options[int_value]
                    _LOGGER.debug("Found option for %s: '%s'", int_value, option_value)
                    return option_value
            
            # Keine Verarbeitung angewendet
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