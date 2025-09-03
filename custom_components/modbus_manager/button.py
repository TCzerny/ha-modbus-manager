"""Modbus Manager Button Platform."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
import asyncio

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Modbus Manager button entities from a config entry."""
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data.get("registers", [])
    hub_name = f"modbus_manager_{prefix}"

    # Entity Registry abrufen für Duplikat-Check
    registry = async_get_entity_registry(hass)
    existing_entities = {
        entity.entity_id for entity in registry.entities.values()
        if entity.entity_id.startswith(f"button.{prefix}_")
    }

    entities = []

    for reg in registers:
        # Nur Button-Entities aus Registern mit control: "button" erstellen
        if reg.get("control") == "button":
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
            # Use same logic for entity_id
            if template_unique_id:
                if template_unique_id.startswith(f"{prefix}_"):
                    entity_id = f"button.{template_unique_id}"
                else:
                    entity_id = f"button.{prefix}_{template_unique_id}"
            else:
                entity_id = f"button.{prefix}_{clean_name}"
            
            # Prüfen ob Entity bereits existiert
            if entity_id in existing_entities:
                _LOGGER.debug("Button Entity %s existiert bereits, überspringe", entity_id)
                continue
            
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
                }
            ))

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Modbus Manager Buttons erstellt: %d Button-Entities", len(entities))
        _LOGGER.debug("Erstellte Button-Entities: %s", [e.entity_id for e in entities])


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
        
        # Button-Konfiguration
        self._press_value = register_data.get("press_value", 1)
        self._reset_value = register_data.get("reset_value", 0)
        self._duration = register_data.get("duration", 0)  # in Sekunden
        
        # Neue Datenverarbeitungsoptionen
        self._offset = register_data.get("offset", 0.0)
        self._multiplier = register_data.get("multiplier", 1.0)
        
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
            
            # Erweiterte Datenverarbeitung rückwärts anwenden
            final_value = self._apply_reverse_data_processing(self._press_value)
            
            # Press-Wert in Holding Register schreiben
            result = await hub.write_register(self._address, int(final_value), unit=self._slave_id)
            
            if result.isError():
                _LOGGER.error("Fehler beim Schreiben in Holding Register %s: %s", self._address, result)
            else:
                _LOGGER.debug("Button %s erfolgreich gedrückt", self.name)
                
                # Optional: Nach duration Sekunden zurücksetzen
                if self._duration > 0:
                    asyncio.create_task(self._reset_after_duration())
                
        except Exception as e:
            _LOGGER.error("Fehler beim Drücken von Button %s: %s", self.name, str(e))

    async def _reset_after_duration(self):
        """Reset the button value after the specified duration."""
        try:
            await asyncio.sleep(self._duration)
            
            if self._hub_name not in self.hass.data.get(DOMAIN, {}):
                return

            hub = self.hass.data[DOMAIN][self._hub_name]
            
            # Erweiterte Datenverarbeitung rückwärts anwenden
            final_value = self._apply_reverse_data_processing(self._reset_value)
            
            # Reset-Wert in Holding Register schreiben
            result = await hub.write_register(self._address, int(final_value), unit=self._slave_id)
            
            if result.isError():
                _LOGGER.error("Fehler beim Zurücksetzen von Button %s: %s", self.name, result)
            else:
                _LOGGER.debug("Button %s erfolgreich zurückgesetzt", self.name)
                
        except Exception as e:
            _LOGGER.error("Fehler beim Zurücksetzen von Button %s: %s", self.name, str(e))

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