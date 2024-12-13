import logging
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback
from .modbus_sungrow import ModbusSungrowHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Richtet die Modbus Manager Sensoren ein."""
    hub: ModbusSungrowHub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        _LOGGER.error("ModbusSungrowHub nicht in hass.data gefunden")
        return

    # Stelle sicher, dass der Coordinator existiert
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

    def __init__(self, hub: ModbusSungrowHub, name: str, device_def: dict):
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
            # Basis-Wert aus den Registern extrahieren
            if data_type == "uint16":
                value = data[0]
            elif data_type == "uint32":
                value = (data[0] << 16) + data[1]
            elif data_type == "int16":
                value = data[0]
                if value > 32767:
                    value -= 65536
            elif data_type == "int32":
                value = (data[0] << 16) + data[1]
                if value > 2147483647:
                    value -= 4294967296
            elif data_type == "float":
                import struct
                value = struct.unpack('>f', bytes(data))[0]
            elif data_type == "string":
                return ''.join([chr(i) for i in data]).strip('\x00')
            elif data_type == "bool":
                return bool(data[0])
            else:
                _LOGGER.error("Unbekannter Datentyp: %s", data_type)
                return None

            # Skalierungsfaktor anwenden
            scale = self._device_def.get("scale", 1)
            if scale != 1:
                value = value * scale
                _LOGGER.debug("Skalierter Wert für %s: %f (Faktor: %f)", self._name, value, scale)

            # Präzision anwenden
            precision = self._device_def.get("precision")
            if precision is not None:
                value = round(value, precision)
                _LOGGER.debug("Gerundeter Wert für %s: %f (Präzision: %d)", self._name, value, precision)

            return value
        except Exception as e:
            _LOGGER.error("Fehler bei der Verarbeitung der Registerdaten für %s: %s", self._name, e)
            return None
            