import logging
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback
from .modbus_hub import ModbusManagerHub
from .const import DOMAIN
import struct
import asyncio
import time
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Modbus Manager sensors."""
    hub: ModbusManagerHub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        _LOGGER.error("ModbusManagerHub not found in hass.data")
        return

    # Ensure coordinator exists
    await hub.read_registers(hub.device_type)

    device_definitions = hub.get_device_definition(hub.device_type)
    if not device_definitions:
        _LOGGER.error("Keine Gerätekonfiguration gefunden für %s", hub.device_type)
        return

    _LOGGER.debug("Gefundene Gerätekonfiguration: %s", device_definitions)
    
    sensors = []
    read_registers = device_definitions.get('registers', {}).get('read', [])
    
    _LOGGER.info("Erstelle %d Sensoren aus der Konfiguration", len(read_registers))

    for reg in read_registers:
        try:
            sensor = ModbusSensor(hub, reg['name'], reg)
            sensors.append(sensor)
            _LOGGER.debug("Sensor erstellt: %s mit Konfiguration: %s", reg['name'], reg)
        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen des Sensors %s: %s", reg['name'], e)
            continue

    async_add_entities(sensors, True)

class ModbusSensor(CoordinatorEntity):
    """Repräsentiert einen einzelnen Modbus-Sensor."""
    
    # Konstanten an den Anfang der Klasse
    VALID_DATA_TYPES = {
        "uint16": (1, lambda x: x[0]),
        "uint32": (2, lambda x: (x[0] << 16) + x[1]),
        "int16": (1, lambda x: x[0] - 65536 if x[0] > 32767 else x[0]),
        "int32": (2, lambda x: ((x[0] << 16) + x[1]) - 4294967296 if ((x[0] << 16) + x[1]) > 2147483647 else ((x[0] << 16) + x[1])),
        "float": (2, lambda x: struct.unpack('>f', bytes(x))[0]),
        "string": (None, lambda x: ''.join([chr(i) for i in x]).strip('\x00')),
        "bool": (1, lambda x: bool(x[0]))
    }

    def __init__(self, hub: ModbusManagerHub, name: str, device_def: dict):
        """Initialisiert den Sensor."""
        if hub.name not in hub.coordinators:
            _LOGGER.error("Kein Coordinator für Hub %s gefunden", hub.name)
            raise ValueError(f"Kein Coordinator für Hub {hub.name} gefunden")
            
        super().__init__(hub.coordinators[hub.name])
        self._hub = hub
        self._name = name
        self._device_def = device_def
        self._state = None
        self._unit_of_measurement = device_def.get("unit_of_measurement")
        self._device_class = device_def.get("device_class")
        self._state_class = device_def.get("state_class")
        
        # Erstelle eine eindeutige ID basierend auf dem Hub-Namen und Sensor-Namen
        self._unique_id = f"{self._hub.name}_{self._name}"
        
        _LOGGER.debug("Sensor initialisiert: %s (ID: %s)", self.name, self._unique_id)

    @property
    def unique_id(self):
        """Eindeutige ID für den Sensor."""
        return self._unique_id

    @property
    def name(self):
        """Name des Sensors."""
        return f"{self._hub.name} {self._name}"

    @property
    def device_info(self):
        """Geräteinformationen für Device Registry."""
        return {
            "identifiers": {(DOMAIN, self._hub.name)},
            "name": self._hub.name,
            "manufacturer": "Sungrow",
            "model": self._hub.device_type,
            "via_device": (DOMAIN, self._hub.name),
        }

    @property
    def state(self):
        """Aktueller Zustand des Sensors."""
        return self._state

    @property
    def device_class(self):
        """Gerätekategorie des Sensors."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Einheit der Messung."""
        return self._unit_of_measurement

    @property
    def state_class(self):
        """Klasse des Zustands."""
        return self._state_class

    async def async_added_to_hass(self):
        """Wird aufgerufen, wenn die Entität zu Home Assistant hinzugefügt wird."""
        self.coordinator.async_add_listener(self.async_write_ha_state)
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self):
        """Behandelt aktualisierte Daten vom Coordinator."""
        if self.coordinator.data:
            register_data = self.coordinator.data.get(self._name)
            if register_data is not None:
                self._state = self._process_register_data(register_data, self._device_def.get("type"))
            else:
                _LOGGER.error("Keine Daten für %s gefunden", self._name)
                self._state = None
        else:
            self._state = None
        self.async_write_ha_state()

    def _process_register_data(self, data, data_type):
        """Verarbeitet die rohen Registerdaten basierend auf dem angegebenen Typ."""
        try:
            if data_type not in self.VALID_DATA_TYPES:
                _LOGGER.error("Unbekannter Datentyp: %s", data_type)
                return None
                
            _, processor = self.VALID_DATA_TYPES[data_type]
            value = processor(data)
            
            # Skalierung und Präzision anwenden
            scale = self._device_def.get("scale", 1)
            precision = self._device_def.get("precision")
            
            if scale != 1:
                value *= scale
                
            if precision is not None:
                value = round(value, precision)
                
            return value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Verarbeitung der Registerdaten für %s: %s", self._name, e)
            return None
            
    async def _batch_read_registers(self, registers):
        """Optimierte Batch-Lesung von Registern mit Performance-Tracking."""
        try:
            start_time = time.time()
            
            # Gruppiere Register nach Adressbereich
            register_groups = self._group_registers(registers)
            
            # Parallele Ausführung der Lesevorgänge
            tasks = []
            for group in register_groups:
                start_address = group[0]['address']
                count = group[-1]['address'] + group[-1].get('count', 1) - start_address
                tasks.append(self._read_register_group(start_address, count))
            
            # Warte auf alle Ergebnisse
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verarbeite Ergebnisse
            data = {}
            for group, result in zip(register_groups, results):
                if isinstance(result, Exception):
                    _LOGGER.error("Fehler beim Lesen der Register-Gruppe: %s", result)
                    continue
                    
                if result.isError():
                    _LOGGER.error("Modbus-Fehler bei Register-Gruppe: %s", result)
                    continue
                    
                offset = 0
                for reg in group:
                    count = reg.get('count', 1)
                    data[reg['name']] = result.registers[offset:offset + count]
                    offset += count
            
            # Performance-Metriken
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # ms
            
            self._update_metrics({
                'response_time': response_time,
                'success_rate': len(data) / len(registers) * 100,
                'timestamp': datetime.now().isoformat()
            })
            
            return data
            
        except Exception as e:
            _LOGGER.error("Fehler beim Batch-Lesen der Register: %s", e)
            self._update_metrics({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return None

    def _group_registers(self, registers):
        """Gruppiert Register für optimale Batch-Lesungen."""
        MAX_GROUP_SIZE = 125  # Modbus-Limit
        groups = []
        current_group = []
        
        for reg in sorted(registers, key=lambda x: x['address']):
            if not current_group:
                current_group.append(reg)
                continue
                
            last_reg = current_group[-1]
            current_size = reg['address'] + reg.get('count', 1) - current_group[0]['address']
            
            if (current_size <= MAX_GROUP_SIZE and 
                reg['address'] <= last_reg['address'] + last_reg.get('count', 1) + 5):
                current_group.append(reg)
            else:
                groups.append(current_group)
                current_group = [reg]
                
        if current_group:
            groups.append(current_group)
            
        return groups

    def _update_metrics(self, metrics):
        """Aktualisiert die Performance-Metriken."""
        self._attr_extra_state_attributes.update({
            'performance_metrics': metrics
        })