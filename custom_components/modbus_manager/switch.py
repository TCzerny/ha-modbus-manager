import logging
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .modbus_sungrow import ModbusSungrowHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Richtet die Modbus Manager Schalter ein."""
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

    switches = []
    write_registers = device_definitions.get('registers', {}).get('write', [])

    _LOGGER.debug("Erstelle %d Schalter für %s", len(write_registers), hub.name)

    for reg in write_registers:
        switch = ModbusSwitch(hub, reg['name'], reg)
        switches.append(switch)
        _LOGGER.debug("Schalter erstellt: %s mit Konfiguration: %s", reg['name'], reg)

    async_add_entities(switches, True)

class ModbusSwitch(CoordinatorEntity):
    """Repräsentiert einen einzelnen Modbus-Schalter."""

    def __init__(self, hub: ModbusSungrowHub, name: str, device_def: dict):
        """Initialisiert den Schalter."""
        if hub.name not in hub.coordinators:
            _LOGGER.error("Kein Coordinator für Hub %s gefunden", hub.name)
            raise ValueError(f"Kein Coordinator für Hub {hub.name} gefunden")
            
        super().__init__(hub.coordinators[hub.name])
        self._hub = hub
        self._name = name
        self._device_def = device_def
        self._state = False
        
        # Erstelle eine eindeutige ID basierend auf dem Hub-Namen und Schalter-Namen
        self._unique_id = f"{self._hub.name}_{self._name}"
        
        _LOGGER.debug("Switch initialisiert: %s (ID: %s)", self.name, self._unique_id)

    @property
    def unique_id(self):
        """Eindeutige ID für den Schalter."""
        return self._unique_id

    @property
    def name(self):
        """Name des Schalters."""
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
    def is_on(self):
        """Gibt an, ob der Schalter eingeschaltet ist."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Schaltet den Schalter ein."""
        await self._write_register(True)

    async def async_turn_off(self, **kwargs):
        """Schaltet den Schalter aus."""
        await self._write_register(False)

    async def _write_register(self, value):
        """Schreibt einen Wert in das Modbus-Register."""
        try:
            address = self._device_def.get("address")
            data_type = self._device_def.get("type")
            unit = self._device_def.get("unit", 1)

            if data_type == "bool":
                data = [1] if value else [0]
            elif data_type == "uint16":
                data = [1] if value else [0]
            else:
                _LOGGER.error("Nicht unterstützter Datentyp für Schalter: %s", data_type)
                return

            response = await self._hub.client.write_registers(address, data, unit=unit)
            if response.isError():
                _LOGGER.error(f"Fehler beim Schreiben des Schalters {self._name}: {response}")
            else:
                _LOGGER.debug(f"Schalter {self._name} gesetzt auf {value}")
                self._state = value
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Fehler beim Schreiben des Schalters: %s", e) 