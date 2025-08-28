from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    prefix = entry.data["prefix"]
    template_name = entry.data["template"]
    registers = entry.data["registers"]
    hub_name = f"{DOMAIN}_{prefix}"

    entities = []

    for reg in registers:
        sensor_name = f"{prefix}_{reg['name'].lower().replace(' ', '_')}"
        entities.append(ModbusTemplateSensor(
            name=sensor_name,
            hub=hub_name,
            slave_id=entry.data["slave_id"],
            address=reg["address"],
            unit=reg.get("unit", ""),
            scale=reg.get("scale", 1.0),
            group=reg.get("group", None)
        ))

    async_add_entities(entities)


class ModbusTemplateSensor(SensorEntity):
    def __init__(self, hass, name, hub, slave_id, reg):
        self.hass = hass
        self._attr_name = name
        self._hub = hub
        self._slave_id = slave_id
        self._address = reg["address"]
        self._unit = reg["unit"]
        self._scale = reg["scale"]
        self._group = reg["group"]
        self._device_class = reg["device_class"]
        self._state_class = reg["state_class"]
        self._state = None

    @property
    def native_unit_of_measurement(self):
        return self._unit

    @property
    def device_class(self):
        return self._device_class

    @property
    def state_class(self):
        return self._state_class

    @property
    def state(self):
        return self._state

    async def async_update(self):
        modbus = self.hass.data["modbus"][self._hub]
        result = await modbus.read_input_registers(self._address, 1, unit=self._slave_id)
        if result.isError():
            self._state = None
        else:
            raw = result.registers[0]
            self._state = raw * self._scale
