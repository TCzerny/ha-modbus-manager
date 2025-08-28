"""Modbus Manager Button Platform."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager buttons from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    hub_name = f"modbus_manager_{prefix}"

    entities = []

    for reg in registers:
        # Button-Entities aus Registern mit control: "button" erstellen
        if reg.get("control") == "button":
            # Unique_ID Format: {prefix}_{template_sensor_name}
            sensor_name = reg.get("name", "unknown")
            unique_id = f"{prefix}_{sensor_name.lower().replace(' ', '_')}"
            
            entities.append(ModbusTemplateButton(
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
        _LOGGER.info("%d Button-Entities für Template %s erstellt", len(entities), template_name)


class ModbusTemplateButton(ButtonEntity):
    """Representation of a Modbus Template Button Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, hub_name: str, 
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the button entity."""
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
        
        # Button-Konfiguration
        button_config = register_data.get("button", {})
        self._press_value = button_config.get("press", 1)
        self._reset_value = button_config.get("reset", 0)
        self._press_duration = button_config.get("duration", 0)  # in Sekunden
        
        # Neue Datenverarbeitungsoptionen
        self._offset = register_data.get("offset", 0.0)
        self._multiplier = register_data.get("multiplier", 1.0)
        
        # Button-Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class")
        self._attr_state_class = register_data.get("state_class")
        
        # Group for aggregations
        self._group = register_data.get("group")
        if self._group:
            self._attr_extra_state_attributes = {"group": self._group}

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Press-Wert in Register schreiben
            await self._write_button_value(self._press_value)
            
            # Wenn eine Dauer definiert ist, nach der Zeit den Reset-Wert schreiben
            if self._press_duration > 0:
                import asyncio
                await asyncio.sleep(self._press_duration)
                await self._write_button_value(self._reset_value)
                
            _LOGGER.info("Button %s erfolgreich gedrückt", self._attr_name)
                
        except Exception as e:
            _LOGGER.error("Fehler beim Drücken des Buttons %s: %s", self._attr_name, str(e))

    async def _write_button_value(self, value: int) -> None:
        """Write a value to the button register."""
        try:
            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Wert für Modbus vorbereiten
            # Offset abziehen
            modbus_value = value - self._offset
            
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
                _LOGGER.error("Fehler beim Schreiben in Button-Register %s: %s", self._address, result)
            else:
                _LOGGER.debug("Button-Wert %s erfolgreich in Register %s geschrieben", value, self._address)
                
        except Exception as e:
            _LOGGER.error("Fehler beim Schreiben des Button-Wertes: %s", str(e))

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
            "press_value": self._press_value,
            "reset_value": self._reset_value,
            "press_duration": self._press_duration
        }
        
        if self._group:
            attrs["group"] = self._group
            
        return attrs 