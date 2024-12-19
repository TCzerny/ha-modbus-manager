import logging
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .modbus_hub import ModbusManagerHub
from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Modbus Manager switches."""
    hub: ModbusManagerHub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        _LOGGER.error("ModbusSungrowHub not found in hass.data")
        return

    # Ensure coordinator exists
    await hub.read_registers(hub.device_type)

    device_definitions = hub.get_device_definition(hub.device_type)
    if not device_definitions:
        _LOGGER.error(f"No device configuration found for {hub.device_type}")
        return

    switches = []
    write_registers = device_definitions.get('registers', {}).get('write', [])

    _LOGGER.debug(f"Creating {len(write_registers)} switches for {hub.name}")

    for reg in write_registers:
        switch = ModbusSwitch(hub, reg['name'], reg)
        switches.append(switch)
        _LOGGER.debug(f"Switch created: {reg['name']} with configuration: {reg}")

    async_add_entities(switches, True)

class ModbusSwitch(CoordinatorEntity):
    """Represents a single Modbus switch."""

    def __init__(self, hub: ModbusManagerHub, name: str, device_def: dict):
        """Initialize the switch."""
        if not hasattr(hub, "coordinators") or not hub.coordinators:
            _LOGGER.error(f"No coordinators found for hub {hub.name}")
            raise ValueError(f"No coordinators found for hub {hub.name}")
            
        coordinator = next(iter(hub.coordinators.values()))
        super().__init__(coordinator)
        
        self._hub = hub
        self._name = name
        self._device_def = device_def
        self._state = False
        
        # Create unique ID based on hub name and switch name
        self._unique_id = f"{self._hub.name}_{self._name}"
        
        _LOGGER.debug(f"Switch initialized: {self.name} (ID: {self._unique_id})")

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
                _LOGGER.error(f"Unsupported data type for switch: {data_type}")
                return

            response = await self._hub.client.write_registers(address, data, unit=unit)
            if response.isError():
                _LOGGER.error(f"Error writing switch {self._name}: {response}")
            else:
                _LOGGER.debug(f"Switch {self._name} set to {value}")
                self._state = value
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error writing switch: {e}") 