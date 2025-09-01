"""Aggregate Sensor Platform for Modbus Manager."""
from __future__ import annotations

from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .aggregates import ModbusAggregateSensor
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Modbus Aggregate Sensor platform."""
    try:
        # Get data from hass.data
        if entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("Keine Daten für Entry %s gefunden", entry.entry_id)
            return
        
        entry_data = hass.data[DOMAIN][entry.entry_id]
        aggregate_sensors = entry_data.get("aggregate_sensors", [])
        
        if aggregate_sensors:
            _LOGGER.info("Füge %d Aggregate-Sensoren hinzu", len(aggregate_sensors))
            async_add_entities(aggregate_sensors, update_before_add=True)
        else:
            _LOGGER.debug("Keine Aggregate-Sensoren zu hinzuzufügen")
            
    except Exception as e:
        _LOGGER.error("Fehler beim Setup der Aggregate-Sensor Plattform: %s", str(e))
