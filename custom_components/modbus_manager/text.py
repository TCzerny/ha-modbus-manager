"""Modbus Manager Text Platform."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager text entities from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    hub_name = f"modbus_manager_{prefix}"

    entities = []

    for reg in registers:
        # Nur Text-Entities aus Registern mit data_type: "string" oder control: "text" erstellen
        if reg.get("data_type") == "string" or reg.get("control") == "text":
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
            
            entities.append(ModbusTemplateText(
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
        _LOGGER.info("%d Text-Entities für Template %s erstellt", len(entities), template_name)


class ModbusTemplateText(TextEntity):
    """Representation of a Modbus Template Text Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, hub_name: str, 
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the text entity."""
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._hub_name = hub_name
        self._slave_id = slave_id
        self._register_data = register_data
        self._attr_device_info = DeviceInfo(**device_info)
        
        # Register properties
        self._address = register_data.get("address", 0)
        self._data_type = register_data.get("data_type", "string")
        self._input_type = register_data.get("input_type", "holding")
        self._count = register_data.get("count", 1)
        self._swap = register_data.get("swap", False)
        
        # Text-Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class")
        self._attr_state_class = register_data.get("state_class")
        
        # Text-Validierung
        self._attr_native_min_value = register_data.get("min_length", 0)
        self._attr_native_max_value = register_data.get("max_length", 255)
        self._attr_pattern = register_data.get("pattern", None)
        self._attr_mode = register_data.get("text_mode", "text")
        
        # Group for aggregations
        self._group = register_data.get("group")
        if self._group:
            self._attr_extra_state_attributes = {"group": self._group}
        
        self._attr_native_value = ""

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return True

    async def async_update(self):
        """Update the text entity state."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Register lesen basierend auf input_type
            if self._input_type == "input":
                result = await hub.read_input_registers(self._address, self._count, unit=self._slave_id)
            else:
                result = await hub.read_holding_registers(self._address, self._count, unit=self._slave_id)
            
            if result.isError():
                _LOGGER.warning("Fehler beim Lesen von Register %s: %s", self._address, result)
                self._attr_native_value = ""
                return
            
            # String-Wert aus Registern extrahieren
            string_value = self._process_string_value(result.registers)
            
            if string_value is not None:
                self._attr_native_value = string_value
            else:
                self._attr_native_value = ""
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Text %s: %s", self.name, str(e))
            self._attr_native_value = ""

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # String in Register-Werte konvertieren
            register_values = self._string_to_registers(value)
            
            # Werte in Holding Register schreiben
            if len(register_values) == 1:
                result = await hub.write_register(self._address, register_values[0], unit=self._slave_id)
            else:
                result = await hub.write_registers(self._address, register_values, unit=self._slave_id)
            
            if result.isError():
                _LOGGER.error("Fehler beim Schreiben in Register %s: %s", self._address, result)
            else:
                _LOGGER.info("Text %s erfolgreich in Register %s geschrieben", value, self._address)
                self._attr_native_value = value
                self.async_write_ha_state()
                
        except Exception as e:
            _LOGGER.error("Fehler beim Setzen des Textes %s: %s", value, str(e))

    def _process_string_value(self, registers):
        """Verarbeite Register-Werte zu String."""
        try:
            if not registers:
                return None
            
            # Register-Werte zu Bytes konvertieren
            bytes_data = []
            for reg in registers:
                # 16-bit Register in 2 Bytes aufteilen
                bytes_data.append((reg >> 8) & 0xFF)  # High byte
                bytes_data.append(reg & 0xFF)          # Low byte
            
            # UTF-16 BE String dekodieren
            string_value = bytes(bytes_data).decode('utf-16-be', errors='ignore')
            
            # Null-Terminator entfernen
            string_value = string_value.rstrip('\x00')
            
            return string_value
            
        except Exception as e:
            _LOGGER.error("Fehler bei String-Verarbeitung: %s", str(e))
            return None

    def _string_to_registers(self, text_value):
        """Konvertiere String zu Register-Werten."""
        try:
            # String zu UTF-16 BE Bytes konvertieren
            bytes_data = text_value.encode('utf-16-be')
            
            # Bytes zu 16-bit Registern konvertieren
            registers = []
            for i in range(0, len(bytes_data), 2):
                if i + 1 < len(bytes_data):
                    # Zwei Bytes zu einem 16-bit Register kombinieren
                    high_byte = bytes_data[i]
                    low_byte = bytes_data[i + 1]
                    register_value = (high_byte << 8) | low_byte
                    registers.append(register_value)
                else:
                    # Letztes Byte mit Null auffüllen
                    register_value = (bytes_data[i] << 8) | 0
                    registers.append(register_value)
            
            return registers
            
        except Exception as e:
            _LOGGER.error("Fehler bei String-zu-Register-Konvertierung: %s", str(e))
            return [0] 