"""Modbus Manager Binary Sensor Platform."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager binary sensors from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    hub_name = f"modbus_manager_{prefix}"

    entities = []

    for reg in registers:
        # Binary-Sensor-Entities aus Registern mit data_type: "boolean" oder control: "switch" erstellen
        if reg.get("data_type") == "boolean" or reg.get("control") == "switch":
            # Unique_ID Format: {prefix}_{template_sensor_name}
            sensor_name = reg.get("name", "unknown")
            # Bereinige den Namen für den unique_id
            clean_name = sensor_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
            unique_id = f"{prefix}_{clean_name}"
            
            entities.append(ModbusTemplateBinarySensor(
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

    if entities:
        async_add_entities(entities)
        _LOGGER.info("%d Binary-Sensor-Entities für Template %s erstellt", len(entities), template_name)


class ModbusTemplateBinarySensor(BinarySensorEntity):
    """Representation of a Modbus Template Binary Sensor Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, hub_name: str, 
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the binary sensor entity."""
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._hub_name = hub_name
        self._slave_id = slave_id
        self._register_data = register_data
        self._attr_device_info = DeviceInfo(**device_info)
        
        # Register properties
        self._address = register_data.get("address", 0)
        self._data_type = register_data.get("data_type", "boolean")
        self._input_type = register_data.get("input_type", "input")
        self._count = register_data.get("count", 1)
        self._scale = register_data.get("scale", 1.0)
        self._swap = register_data.get("swap", False)
        
        # Neue Datenverarbeitungsoptionen
        self._offset = register_data.get("offset", 0.0)
        self._multiplier = register_data.get("multiplier", 1.0)
        self._shift_bits = register_data.get("shift_bits", 0)
        self._bits = register_data.get("bits")
        
        # Binary-Sensor properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class", "problem")
        self._attr_state_class = register_data.get("state_class")
        
        # Boolean-Konfiguration
        self._true_value = register_data.get("true_value", 1)
        self._false_value = register_data.get("false_value", 0)
        
        # Bit-spezifische Konfiguration
        self._bit_position = register_data.get("bit_position", 0)
        
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
        """Update the binary sensor entity state."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Register lesen basierend auf input_type
            if self._input_type == "input":
                result = await hub.read_input_registers(self._address, self._count, unit=self._slave_id)
            elif self._input_type == "holding":
                result = await hub.read_holding_registers(self._address, self._count, unit=self._slave_id)
            elif self._input_type == "coil":
                result = await hub.read_coils(self._address, self._count, unit=self._slave_id)
            elif self._input_type == "discrete":
                result = await hub.read_discrete_inputs(self._address, self._count, unit=self._slave_id)
            else:
                _LOGGER.warning("Unbekannter input_type: %s", self._input_type)
                return
            
            if result.isError():
                _LOGGER.warning("Fehler beim Lesen von Register %s: %s", self._address, result)
                self._attr_is_on = False
                return
            
            # Wert verarbeiten
            raw_value = self._process_register_value(result.registers)
            
            if raw_value is not None:
                # Erweiterte Datenverarbeitung anwenden
                processed_value = self._apply_data_processing(raw_value)
                
                # Boolean-Wert bestimmen
                if self._bits:
                    # Bit-spezifische Auswertung
                    bit_value = (processed_value >> self._bit_position) & 1
                    self._attr_is_on = bit_value == 1
                else:
                    # Standard Boolean-Auswertung
                    self._attr_is_on = processed_value == self._true_value
            else:
                self._attr_is_on = False
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Binary Sensor %s: %s", self.name, str(e))
            self._attr_is_on = False

    def _process_register_value(self, registers):
        """Verarbeite Register-Werte basierend auf data_type."""
        try:
            if not registers:
                return None
                
            if self._data_type == "boolean":
                # Boolean-Wert aus Register extrahieren
                value = registers[0]
                if self._swap and len(registers) > 1:
                    # Byte-Swap für 32-bit Werte
                    value = (registers[1] << 16) | registers[0]
                return value
            else:
                # Standard-Register-Verarbeitung
                return self._process_standard_register(registers)
                
        except Exception as e:
            _LOGGER.error("Fehler bei Register-Verarbeitung: %s", str(e))
            return None

    def _process_standard_register(self, registers):
        """Standard-Register-Verarbeitung."""
        try:
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
            else:
                return registers[0]
                
        except Exception as e:
            _LOGGER.error("Fehler bei Standard-Register-Verarbeitung: %s", str(e))
            return None

    def _apply_data_processing(self, value):
        """Wende erweiterte Datenverarbeitung an."""
        try:
            # Multiplier anwenden
            if self._multiplier != 1.0:
                value *= self._multiplier
            
            # Offset anwenden
            if self._offset != 0.0:
                value += self._offset
            
            # Bit-Shifting
            if self._shift_bits != 0:
                if self._shift_bits > 0:
                    value >>= self._shift_bits
                else:
                    value <<= abs(self._shift_bits)
            
            return value
            
        except Exception as e:
            _LOGGER.error("Fehler bei Datenverarbeitung: %s", str(e))
            return value 