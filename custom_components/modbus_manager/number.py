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
    # Daten aus hass.data holen, nicht aus entry.data
    domain_data = hass.data.get(DOMAIN, {})
    entry_data = domain_data.get(entry.entry_id, {})
    
    prefix = entry_data.get("prefix", entry.data["prefix"])
    template_name = entry_data.get("template", entry.data["template"])
    registers = entry_data.get("registers", [])
    controls = entry_data.get("controls", [])
    hub = entry_data.get("hub")
    
    _LOGGER.info("Number Setup: prefix=%s, template=%s, registers=%d, controls=%d", 
                prefix, template_name, len(registers), len(controls))
    _LOGGER.debug("Controls: %s", controls)
    
    if not hub:
        _LOGGER.error("Hub nicht gefunden für Entry %s", entry.entry_id)
        return

    # Entity Registry abrufen für Duplikat-Check
    registry = async_get_entity_registry(hass)
    existing_entities = {
        entity.entity_id for entity in registry.entities.values()
        if entity.entity_id.startswith(f"number.{prefix}_")
    }

    entities = []

    # Number-Entities aus Registern mit control: "number" erstellen
    for reg in registers:
        if reg.get("control") == "number":
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
            # Use same logic for entity_id
            if template_unique_id:
                entity_id = f"number.{prefix}_{template_unique_id}"
            else:
                entity_id = f"number.{prefix}_{clean_name}"
            
            # Prüfen ob Entity bereits existiert
            if entity_id in existing_entities:
                _LOGGER.debug("Number Entity %s existiert bereits, überspringe", entity_id)
                continue
            
            entities.append(ModbusTemplateNumber(
                hass=hass,
                name=sensor_name,
                unique_id=unique_id,
                hub=hub,
                slave_id=entry_data.get("slave_id", entry.data.get("slave_id", 1)),
                register_data=reg,
                device_info={
                    "identifiers": {(DOMAIN, f"{prefix}_{template_name}")},
                    "name": f"{prefix} {template_name}",
                    "manufacturer": "Modbus Manager",
                    "model": template_name
                }
            ))

    # Number-Entities aus Controls-Abschnitt erstellen
    _LOGGER.info("Verarbeite %d Controls für Number-Entities", len(controls))
    for control in controls:
        if control.get("type") == "number":
            control_name = control.get("name", "unknown")
            # Stelle sicher, dass der name den Prefix enthält
            if not control_name.startswith(f"{prefix} "):
                display_name = f"{prefix} {control_name}"
            else:
                display_name = control_name
            
            # Stelle sicher, dass der unique_id den Prefix enthält
            base_unique_id = control.get("unique_id", control_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', ''))
            # Wenn der unique_id bereits den Prefix hat, verwende ihn direkt
            if base_unique_id.startswith(f"{prefix}_"):
                unique_id = base_unique_id
            else:
                # Ansonsten füge den Prefix hinzu
                unique_id = f"{prefix}_{base_unique_id}"
            entity_id = f"number.{unique_id}"
            
            # Prüfen ob Entity bereits existiert
            if entity_id in existing_entities:
                _LOGGER.debug("Number Control Entity %s existiert bereits, überspringe", entity_id)
                continue
            
            entities.append(ModbusTemplateNumber(
                hass=hass,
                name=display_name,
                unique_id=unique_id,
                hub=hub,
                slave_id=entry_data.get("slave_id", entry.data.get("slave_id", 1)),
                register_data=control,
                device_info={
                    "identifiers": {(DOMAIN, f"{prefix}_{template_name}")},
                    "name": f"{prefix} {template_name}",
                    "manufacturer": "Modbus Manager",
                    "model": template_name,

                }
            ))

    if entities:
        async_add_entities(entities)
        _LOGGER.info("%d Number-Entities für Template %s erstellt", len(entities), template_name)


class ModbusTemplateNumber(NumberEntity):
    """Representation of a Modbus Template Number Entity."""

    def __init__(self, hass: HomeAssistant, name: str, unique_id: str, hub, 
                 slave_id: int, register_data: dict, device_info: dict):
        """Initialize the number entity."""
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._hub = hub
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
            if not self._hub:
                _LOGGER.error("Hub nicht verfügbar")
                return
            
            # Holding Register lesen (read/write) über den Hub
            if self._input_type == "holding":
                from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
                result = await self._hub.async_pb_call(
                    self._slave_id,
                    self._address,
                    self._count,
                    CALL_TYPE_REGISTER_HOLDING
                )
            else:
                from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_INPUT
                result = await self._hub.async_pb_call(
                    self._slave_id,
                    self._address,
                    self._count,
                    CALL_TYPE_REGISTER_INPUT
                )
            
            if not result or not hasattr(result, 'registers'):
                _LOGGER.warning("Fehler beim Lesen von Register %s: %s", self._address, result)
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
            if not self._hub:
                _LOGGER.error("Hub nicht verfügbar")
                return
            
            # Erweiterte Datenverarbeitung rückwärts anwenden
            final_value = self._apply_reverse_data_processing(value)
            
            # Wert in Holding Register schreiben über den Hub
            if self._input_type == "holding":
                from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
                result = await self._hub.async_pb_call(
                    self._slave_id,
                    self._address,
                    int(final_value),
                    CALL_TYPE_REGISTER_HOLDING,
                    write=True
                )
            else:
                _LOGGER.warning("Kann nicht in %s Register schreiben: %d", self._input_type, self._address)
                return
            
            if result.isError():
                _LOGGER.error("Fehler beim Schreiben in Register %s: %s", self._address, result)
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