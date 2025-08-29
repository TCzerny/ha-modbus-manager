"""Modbus Manager Number Platform."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager number entities from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    hub_name = f"modbus_manager_{prefix}"

    # Entity Registry abrufen für Duplikat-Check
    registry = async_get_entity_registry(hass)
    existing_entities = {
        entity.entity_id for entity in registry.entities.values()
        if entity.entity_id.startswith(f"number.{prefix}_")
    }

    entities = []

    for reg in registers:
        # Nur Number-Entities aus Registern mit control: "number" erstellen
        if reg.get("control") == "number":
            # Unique_ID Format: {prefix}_{template_sensor_name}
            sensor_name = reg.get("name", "unknown")
            # Bereinige den Namen für den unique_id
            clean_name = sensor_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
            unique_id = f"{prefix}_{clean_name}"
            entity_id = f"number.{prefix}_{clean_name}"
            
            # Prüfen ob Entity bereits existiert
            if entity_id in existing_entities:
                _LOGGER.debug("Number Entity %s existiert bereits, überspringe", entity_id)
                continue
            
            entities.append(ModbusTemplateNumber(
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
        _LOGGER.info("%d Number-Entities für Template %s erstellt", len(entities), template_name)


class ModbusTemplateNumber(NumberEntity):
    """Representation of a Modbus Template Number Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, hub_name: str, 
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the number entity."""
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
        self._precision = register_data.get("precision", 0)
        self._swap = register_data.get("swap", False)
        
        # Neue Datenverarbeitungsoptionen
        self._offset = register_data.get("offset", 0.0)
        self._multiplier = register_data.get("multiplier", 1.0)
        
        # Number-Entity properties
        self._attr_native_unit_of_measurement = register_data.get("unit_of_measurement", "")
        self._attr_device_class = register_data.get("device_class")
        self._attr_state_class = register_data.get("state_class")
        
        # Min/Max/Step Werte
        self._attr_native_min_value = register_data.get("min_value", 0.0)
        self._attr_native_max_value = register_data.get("max_value", 100.0)
        self._attr_native_step = register_data.get("step", 1.0)
        
        # Mode (slider oder box)
        self._attr_mode = NumberMode.SLIDER if self._attr_native_step > 0 else NumberMode.BOX
        
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
        """Update the number entity state."""
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
                
                # Präzision anwenden
                if self._precision > 0:
                    final_value = round(final_value, self._precision)
                
                self._attr_native_value = final_value
            else:
                self._attr_native_value = None
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Number %s: %s", self.name, str(e))
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        try:
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                _LOGGER.error("Hub %s nicht gefunden", self._hub_name)
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Erweiterte Datenverarbeitung rückwärts anwenden
            final_value = self._apply_reverse_data_processing(value)
            
            # Wert in Holding Register schreiben
            result = await hub.write_register(self._address, int(final_value), unit=self._slave_id)
            
            if result.isError():
                _LOGGER.error("Fehler beim Schreiben in Holding Register %s: %s", self._address, result)
            else:
                _LOGGER.info("Number %s erfolgreich auf %s gesetzt", self.name, value)
                self._attr_native_value = value
                self.async_write_ha_state()
                
        except Exception as e:
            _LOGGER.error("Fehler beim Setzen des Number-Wertes %s: %s", value, str(e))

    def _process_register_value(self, registers):
        """Verarbeite Register-Werte basierend auf data_type."""
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
            else:
                return registers[0]
                
        except Exception as e:
            _LOGGER.error("Fehler bei Register-Verarbeitung: %s", str(e))
            return None

    def _apply_data_processing(self, value):
        """Wende erweiterte Datenverarbeitung an."""
        try:
            # Multiplier anwenden
            if self._multiplier != 1.0:
                value *= self._multiplier
            
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
            
            # Skalierung rückwärts anwenden
            if self._scale != 1.0:
                value /= self._scale
            
            # Multiplier rückwärts anwenden
            if self._multiplier != 1.0:
                value /= self._multiplier
            
            return value
            
        except Exception as e:
            _LOGGER.error("Fehler bei rückwärtiger Datenverarbeitung: %s", str(e))
            return value 