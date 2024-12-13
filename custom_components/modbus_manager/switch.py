import logging
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .modbus_sungrow import ModbusSungrowHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Modbus Manager switches."""
    hub: ModbusSungrowHub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        _LOGGER.error("ModbusSungrowHub not found in hass.data")
        return

    # Ensure coordinator exists
    await hub.read_registers(hub.device_type)

    device_definitions = hub.get_device_definition(hub.device_type)
    if not device_definitions:
        _LOGGER.error("No device configuration found for %s", hub.device_type)
        return

    switches = []
    write_registers = device_definitions.get('registers', {}).get('write', [])

    _LOGGER.debug("Creating %d switches for %s", len(write_registers), hub.name)

    for reg in write_registers:
        switch = ModbusSwitch(hub, reg['name'], reg)
        switches.append(switch)
        _LOGGER.debug("Switch created: %s with configuration: %s", reg['name'], reg)

    async_add_entities(switches, True)

class ModbusSwitch(CoordinatorEntity):
    """Represents a single Modbus switch."""

    def __init__(self, hub: ModbusSungrowHub, name: str, device_def: dict):
        """Initialize the switch."""
        if hub.name not in hub.coordinators:
            _LOGGER.error("No coordinator found for hub %s", hub.name)
            raise ValueError(f"No coordinator found for hub {hub.name}")
            
        super().__init__(hub.coordinators[hub.name])
        self._hub = hub
        self._name = name
        self._device_def = device_def
        self._state = False
        
        # Create unique ID based on hub name and switch name
        self._unique_id = f"{self._hub.name}_{self._name}"
        
        _LOGGER.debug("Switch initialized: %s (ID: %s)", self.name, self._unique_id)

    @property
    def unique_id(self):
        """Unique ID for the switch."""
        return self._unique_id

    @property
    def name(self):
        """Name of the switch."""
        return f"{self._hub.name} {self._name}"

    @property
    def device_info(self):
        """Device information for Device Registry."""
        return {
            "identifiers": {(DOMAIN, self._hub.name)},
            "name": self._hub.name,
            "manufacturer": "Sungrow",
            "model": self._hub.device_type,
            "via_device": (DOMAIN, self._hub.name),
        }

    @property
    def is_on(self):
        """Return whether the switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._write_register(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._write_register(False)

    async def _write_register(self, value):
        """Write a value to the Modbus register."""
        try:
            address = self._device_def.get("address")
            data_type = self._device_def.get("type")
            unit = self._device_def.get("unit", 1)

            if data_type == "bool":
                data = [1] if value else [0]
            elif data_type == "uint16":
                data = [1] if value else [0]
            else:
                _LOGGER.error("Unsupported data type for switch: %s", data_type)
                return

            response = await self._hub.client.write_registers(address, data, unit=unit)
            if response.isError():
                _LOGGER.error(f"Error writing switch {self._name}: {response}")
            else:
                _LOGGER.debug(f"Switch {self._name} set to {value}")
                self._state = value
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error writing switch: %s", e) 