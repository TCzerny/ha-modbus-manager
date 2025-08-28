"""Modbus Manager Binary Sensor Platform."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT

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
            unique_id = f"{prefix}_{sensor_name.lower().replace(' ', '_')}"
            
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
                _LOGGER.error("Unbekannter input_type: %s", self._input_type)
                return
            
            if result.isError():
                _LOGGER.warning("Fehler beim Lesen von Register %s: %s", self._address, result)
                return
            
            # Wert verarbeiten
            if self._input_type in ["coil", "discrete"]:
                # Direkte Boolean-Werte
                raw_value = result.bits[0] if result.bits else False
                self._attr_is_on = bool(raw_value)
            else:
                # Register-Werte verarbeiten
                raw_value = self._process_register_value(result.registers)
                
                if raw_value is not None:
                    # Erweiterte Datenverarbeitung anwenden
                    processed_value = self._apply_data_processing(raw_value)
                    
                    # Skalierung anwenden
                    scaled_value = processed_value * self._scale
                    
                    # Offset anwenden
                    final_value = scaled_value + self._offset
                    
                    # Boolean-Status bestimmen
                    if self._bits is not None:
                        # Bit-Mask anwenden
                        masked_value = final_value & ((1 << self._bits) - 1)
                        if self._bit_position >= 0:
                            # Spezifisches Bit prüfen
                            self._attr_is_on = bool(masked_value & (1 << self._bit_position))
                        else:
                            # Wert direkt als Boolean interpretieren
                            self._attr_is_on = bool(masked_value)
                    else:
                        # Direkter Wert-Vergleich
                        if abs(final_value - self._true_value) < 0.001:  # Float-Vergleich
                            self._attr_is_on = True
                        elif abs(final_value - self._false_value) < 0.001:  # Float-Vergleich
                            self._attr_is_on = False
                        else:
                            # Fallback: Nicht-Null als True
                            self._attr_is_on = bool(final_value)
                else:
                    self._attr_is_on = False
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Binary-Sensor %s: %s", self._attr_name, str(e))

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
            elif self._data_type == "int32":
                raw_value = raw_value if raw_value < 2147483648 else raw_value - 4294967296
            
            return raw_value
            
        except (IndexError, ValueError) as e:
            _LOGGER.error("Fehler bei der Verarbeitung der Register-Werte: %s", str(e))
            return None

    def _apply_data_processing(self, raw_value):
        """Apply data processing options."""
        try:
            processed_value = raw_value
            
            # Bit-Shift anwenden
            if self._shift_bits > 0 and isinstance(processed_value, int):
                processed_value = processed_value >> self._shift_bits
            
            # Multiplier anwenden
            processed_value = processed_value * self._multiplier
            
            return processed_value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Datenverarbeitung: %s", str(e))
            return raw_value

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {
            "register_address": self._address,
            "data_type": self._data_type,
            "input_type": self._input_type,
            "scale": self._scale,
            "offset": self._offset,
            "multiplier": self._multiplier,
            "shift_bits": self._shift_bits,
            "true_value": self._true_value,
            "false_value": self._false_value
        }
        
        if self._bits is not None:
            attrs["bits"] = self._bits
            attrs["bit_position"] = self._bit_position
            
        if self._group:
            attrs["group"] = self._group
            
        return attrs 