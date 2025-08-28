"""Modbus Manager Switch Platform."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager switches from a config entry."""
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
            unique_id = f"{prefix}_{sensor_name.lower().replace(' ', '_')}"
            
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
                    "via_device": (DOMAIN, hub_name)
                }
            ))

    if entities:
        async_add_entities(entities)
        _LOGGER.info("%d Switch-Entities für Template %s erstellt", len(entities), template_name)


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
        
        # Switch-Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class", "switch")
        self._attr_state_class = register_data.get("state_class")
        
        # Switch-Konfiguration
        switch_config = register_data.get("switch", {})
        self._on_value = switch_config.get("on", 1)
        self._off_value = switch_config.get("off", 0)
        
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
                
                # Switch-Status bestimmen
                if abs(final_value - self._on_value) < 0.001:  # Float-Vergleich
                    self._attr_is_on = True
                elif abs(final_value - self._off_value) < 0.001:  # Float-Vergleich
                    self._attr_is_on = False
                else:
                    _LOGGER.warning("Unbekannter Wert %s für Switch-Entity %s", final_value, self._attr_name)
                    self._attr_is_on = False
            else:
                self._attr_is_on = False
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Switch-Entity %s: %s", self._attr_name, str(e))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._set_switch_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._set_switch_state(False)

    async def _set_switch_state(self, turn_on: bool) -> None:
        """Set the switch state."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Wert für gewünschten Zustand bestimmen
            target_value = self._on_value if turn_on else self._off_value
            
            # Wert für Modbus vorbereiten
            # Offset abziehen
            modbus_value = target_value - self._offset
            
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
                state_text = "EIN" if turn_on else "AUS"
                _LOGGER.info("Switch %s erfolgreich auf %s gesetzt (Wert %s)", self._attr_name, state_text, target_value)
                # Sofort aktualisieren
                await self.async_update()
                
        except Exception as e:
            _LOGGER.error("Fehler beim Setzen des Switch-Zustands für %s: %s", self._attr_name, str(e))

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
            "on_value": self._on_value,
            "off_value": self._off_value
        }
        
        if self._group:
            attrs["group"] = self._group
            
        return attrs 