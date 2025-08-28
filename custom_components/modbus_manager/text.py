"""Modbus Manager Text Platform."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT

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
        # Text-Entities aus Registern mit control: "text" erstellen
        if reg.get("control") == "text":
            # Unique_ID Format: {prefix}_{template_sensor_name}
            sensor_name = reg.get("name", "unknown")
            unique_id = f"{prefix}_{sensor_name.lower().replace(' ', '_')}"
            
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
        self._count = register_data.get("count", 10)  # Standard: 10 Register für String
        self._scale = register_data.get("scale", 1.0)
        self._swap = register_data.get("swap", False)
        
        # Text-Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class")
        self._attr_state_class = register_data.get("state_class")
        
        # Text-spezifische Eigenschaften
        self._attr_native_max = register_data.get("max_length", 20)  # Maximale Zeichenlänge
        self._attr_native_min = register_data.get("min_length", 0)   # Minimale Zeichenlänge
        self._attr_pattern = register_data.get("pattern", None)      # Regex-Pattern für Validierung
        self._attr_mode = register_data.get("mode", "text")          # text, password, url, email
        
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
            
            # Holding Register lesen (read/write)
            result = await hub.read_holding_registers(self._address, self._count, unit=self._slave_id)
            
            if result.isError():
                _LOGGER.warning("Fehler beim Lesen von Holding Register %s: %s", self._address, result)
                self._attr_native_value = ""
                return
            
            # String aus Registern extrahieren
            string_value = self._registers_to_string(result.registers)
            
            if string_value is not None:
                self._attr_native_value = string_value
            else:
                self._attr_native_value = ""
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Text-Entity %s: %s", self._attr_name, str(e))
            self._attr_native_value = ""

    async def async_set_value(self, value: str) -> None:
        """Set the value of the entity."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            # Validierung
            if len(value) > self._attr_native_max:
                _LOGGER.error("Text zu lang: %d Zeichen (Maximum: %d)", len(value), self._attr_native_max)
                return
                
            if len(value) < self._attr_native_min:
                _LOGGER.error("Text zu kurz: %d Zeichen (Minimum: %d)", len(value), self._attr_native_min)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # String in Register konvertieren
            registers = self._string_to_registers(value)
            
            if registers:
                # Register schreiben
                result = await hub.write_registers(self._address, registers, unit=self._slave_id)
                
                if result.isError():
                    _LOGGER.error("Fehler beim Schreiben in Register %s: %s", self._address, result)
                else:
                    _LOGGER.info("Text '%s' erfolgreich in Register %s geschrieben", value, self._address)
                    # Sofort aktualisieren
                    await self.async_update()
            else:
                _LOGGER.error("Fehler bei der String-zu-Register-Konvertierung")
                
        except Exception as e:
            _LOGGER.error("Fehler beim Setzen des Text-Wertes für Text-Entity %s: %s", self._attr_name, str(e))

    def _registers_to_string(self, registers):
        """Convert registers to string."""
        try:
            if not registers:
                return None
            
            # Bytes aus Registern extrahieren
            bytes_list = []
            for register in registers:
                # Jedes Register in 2 Bytes aufteilen
                high_byte = (register >> 8) & 0xFF
                low_byte = register & 0xFF
                bytes_list.extend([high_byte, low_byte])
            
            # Null-Terminator finden und String extrahieren
            string_bytes = bytearray()
            for i in range(0, len(bytes_list), 2):
                if i + 1 < len(bytes_list):
                    char_code = (bytes_list[i] << 8) | bytes_list[i + 1]
                    if char_code == 0:  # Null-Terminator
                        break
                    string_bytes.extend(char_code.to_bytes(2, 'big'))
            
            # String dekodieren (UTF-16 BE)
            try:
                return string_bytes.decode('utf-16-be').rstrip('\x00')
            except UnicodeDecodeError:
                # Fallback: ASCII
                return string_bytes.decode('ascii', errors='ignore').rstrip('\x00')
                
        except Exception as e:
            _LOGGER.error("Fehler bei String-Konvertierung: %s", str(e))
            return None

    def _string_to_registers(self, text: str):
        """Convert string to registers."""
        try:
            if not text:
                return [0] * self._count
            
            # String in UTF-16 BE Bytes konvertieren
            text_bytes = text.encode('utf-16-be')
            
            # Bytes in Register konvertieren
            registers = []
            for i in range(0, len(text_bytes), 2):
                if i + 1 < len(text_bytes):
                    char_code = (text_bytes[i] << 8) | text_bytes[i + 1]
                    registers.append(char_code)
                else:
                    # Ungerade Anzahl Bytes
                    registers.append(text_bytes[i] << 8)
            
            # Mit Null-Terminator auffüllen
            while len(registers) < self._count:
                registers.append(0)
            
            # Auf maximale Länge beschränken
            return registers[:self._count]
            
        except Exception as e:
            _LOGGER.error("Fehler bei Register-zu-String-Konvertierung: %s", str(e))
            return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {
            "register_address": self._address,
            "data_type": self._data_type,
            "input_type": self._input_type,
            "count": self._count,
            "max_length": self._attr_native_max,
            "min_length": self._attr_native_min,
            "mode": self._attr_mode
        }
        
        if self._attr_pattern:
            attrs["pattern"] = self._attr_pattern
            
        if self._group:
            attrs["group"] = self._group
            
        return attrs 