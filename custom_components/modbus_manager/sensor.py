import logging
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback
from .modbus_hub import ModbusManagerHub
from .const import DOMAIN
from .logger import ModbusManagerLogger
import struct
import asyncio
import time
from datetime import datetime

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Modbus Manager sensors."""
    hub: ModbusManagerHub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        _LOGGER.error("ModbusManagerHub nicht in hass.data gefunden")
        return

    device_definitions = hub.get_device_definition(hub.device_type)
    if not device_definitions:
        _LOGGER.error(f"Keine Gerätekonfiguration gefunden für {hub.device_type}")
        return

    _LOGGER.debug(f"Gefundene Gerätekonfiguration: {device_definitions}")
    
    sensors = []
    read_registers = device_definitions.get('registers', {}).get('read', [])
    
    _LOGGER.info(f"Erstelle {len(read_registers)} Sensoren aus der Konfiguration")

    for reg in read_registers:
        try:
            sensor = ModbusSensor(hub, reg['name'], reg)
            sensors.append(sensor)
            _LOGGER.debug(f"Sensor erstellt: {reg['name']} mit Konfiguration: {reg}")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Erstellen des Sensors {reg['name']}: {e}")
            continue

    async_add_entities(sensors, True)

class ModbusSensor(CoordinatorEntity):
    """Repräsentiert einen einzelnen Modbus-Sensor."""
    
    VALID_DATA_TYPES = {
        "uint16": (1, lambda x: x[0]),
        "uint32": (2, lambda x: (x[0] << 16) + x[1]),
        "int16": (1, lambda x: x[0] - 65536 if x[0] > 32767 else x[0]),
        "int32": (2, lambda x: ((x[0] << 16) + x[1]) - 4294967296 if ((x[0] << 16) + x[1]) > 2147483647 else ((x[0] << 16) + x[1])),
        "float": (2, lambda x: struct.unpack('>f', bytes(x))[0]),
        "float32": (2, lambda x: struct.unpack('>f', bytes(x))[0]),
        "string": (None, lambda x: ''.join([chr(i) for i in x]).strip('\x00')),
        "bool": (1, lambda x: bool(x[0]))
    }

    def __init__(self, hub: ModbusManagerHub, name: str, device_def: dict):
        """Initialisiert den Sensor."""
        if hub.device_type not in hub.coordinators:
            _LOGGER.error(f"Kein Coordinator für Gerätetyp {hub.device_type} gefunden")
            raise ValueError(f"Kein Coordinator für Gerätetyp {hub.device_type} gefunden")
            
        super().__init__(hub.coordinators[hub.device_type])
        self._hub = hub
        self._name = name
        self._device_def = device_def
        self._state = None
        self._unit_of_measurement = device_def.get("unit_of_measurement")
        self._device_class = device_def.get("device_class")
        self._state_class = device_def.get("state_class")
        
        # Erstelle eine eindeutige ID basierend auf dem Hub-Namen und Sensor-Namen
        self._unique_id = f"{self._hub.name}_{self._name}"
        
        _LOGGER.debug(f"Sensor initialisiert: {self._name} (ID: {self._unique_id})")

    @property
    def unique_id(self):
        """Eindeutige ID des Sensors."""
        return self._unique_id

    @property
    def name(self):
        """Name des Sensors."""
        return self._name

    @property
    def state(self):
        """Zustand des Sensors."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Einheit des Sensors."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Geräteklasse des Sensors."""
        return self._device_class

    @property
    def state_class(self):
        """Statusklasse des Sensors."""
        return self._state_class

    async def async_added_to_hass(self):
        """Registriere das Update Callback beim Coordinator."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self):
        """Handle Coordinator Update."""
        try:
            register_values = self.coordinator.data.get(self._name)
            if register_values is None:
                _LOGGER.error(f"Keine Daten für Sensor {self._name} verfügbar")
                return

            data_type = self._device_def.get("type")
            if data_type not in self.VALID_DATA_TYPES:
                _LOGGER.error(f"Ungültiger Datentyp für {self._name}: {data_type}")
                return

            num_registers, parser = self.VALID_DATA_TYPES[data_type]
            if num_registers and len(register_values) < num_registers:
                _LOGGER.error(f"Nicht genügend Registerwerte für {self._name}")
                return

            parsed_value = parser(register_values[:num_registers] if num_registers else register_values)
            self._state = parsed_value
            _LOGGER.debug(f"Sensor {self._name} aktualisiert mit Wert: {self._state}")
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error(f"Fehler beim Aktualisieren des Sensors {self._name}: {e}")