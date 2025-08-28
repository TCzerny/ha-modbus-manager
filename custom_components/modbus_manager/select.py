"""Modbus Manager Select Platform."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager selects from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    hub_name = f"modbus_manager_{prefix}"

    entities = []

    for reg in registers:
        # Nur Select-Entities aus Registern mit control: "select" erstellen
        if reg.get("control") == "select":
            # Unique_ID Format: {prefix}_{template_sensor_name}
            sensor_name = reg.get("name", "unknown")
            unique_id = f"{prefix}_{sensor_name.lower().replace(' ', '_')}"
            
            entities.append(ModbusTemplateSelect(
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
        _LOGGER.info("%d Select-Entities für Template %s erstellt", len(entities), template_name)


class ModbusTemplateSelect(SelectEntity):
    """Representation of a Modbus Template Select Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, hub_name: str, 
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the select entity."""
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
        
        # Select-Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class")
        self._attr_state_class = register_data.get("state_class")
        
        # Options für Select-Entity
        self._options = register_data.get("options", {})
        self._attr_options = list(self._options.values())
        
        # Reverse mapping für Wert-zu-Text
        self._value_to_text = {v: k for k, v in self._options.items()}
        
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
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Holding Register lesen (read/write)
            result = await hub.read_holding_registers(self._address, self._count, unit=self._slave_id)
            
            if result.isError():
                _LOGGER.warning("Fehler beim Lesen von Holding Register %s: %s", self._address, result)
                self._attr_native_value = None
                return
            
            # Wert verarbeiten
            raw_value = self._process_register_value(result.registers)
            
            if raw_value is not None:
                # Erweiterte Datenverarbeitung anwenden
                processed_value = self._apply_data_processing(raw_value)
                
                # Skalierung anwenden
                scaled_value = processed_value * self._scale
                
                # Offset anwenden
                final_value = scaled_value + self._offset
                
                # Wert in Text konvertieren
                if final_value in self._value_to_text:
                    self._attr_native_value = self._value_to_text[final_value]
                else:
                    _LOGGER.warning("Unbekannter Wert %s für Select-Entity %s", final_value, self._attr_name)
                    self._attr_native_value = None
            else:
                self._attr_native_value = None
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Select-Entity %s: %s", self._attr_name, str(e))
            self._attr_native_value = None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            # Text in Wert konvertieren
            if option not in self._options.values():
                _LOGGER.error("Ungültige Option %s für Select-Entity %s", option, self._attr_name)
                return
            
            # Wert für diese Option finden
            option_value = None
            for value, text in self._options.items():
                if text == option:
                    option_value = value
                    break
            
            if option_value is None:
                _LOGGER.error("Wert für Option %s nicht gefunden", option)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Wert für Modbus vorbereiten
            # Offset abziehen
            modbus_value = option_value - self._offset
            
            # Skalierung rückgängig machen
            raw_value = modbus_value / self._scale
            
            # Multiplier anwenden
            raw_value = raw_value / self._multiplier
            
            # Wert in Register schreiben
            if self._count == 1:
                # 16-bit Wert
                register_value = int(raw_value)
                result = await hub.write_register(self._address, register_value, unit=self._slave_id)
            else:
                # 32-bit Wert (2 Register)
                if self._swap:
                    high_word = int(raw_value >> 16)
                    low_word = int(raw_value & 0xFFFF)
                    result = await hub.write_registers(self._address, [low_word, high_word], unit=self._slave_id)
                else:
                    high_word = int(raw_value >> 16)
                    low_word = int(raw_value & 0xFFFF)
                    result = await hub.write_registers(self._address, [high_word, low_word], unit=self._slave_id)
            
            if result.isError():
                _LOGGER.error("Fehler beim Schreiben in Register %s: %s", self._address, result)
            else:
                _LOGGER.info("Option %s (Wert %s) erfolgreich in Register %s geschrieben", option, option_value, self._address)
                # Sofort aktualisieren
                await self.async_update()
                
        except Exception as e:
            _LOGGER.error("Fehler beim Setzen der Option für Select-Entity %s: %s", self._attr_name, str(e))

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
            "scale": self._scale,
            "offset": self._offset,
            "multiplier": self._multiplier,
            "available_options": self._options
        }
        
        if self._group:
            attrs["group"] = self._group
            
        return attrs 