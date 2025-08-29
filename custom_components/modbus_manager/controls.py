from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.button import ButtonEntity

# Modbus Number Control
class ModbusNumberEntity(NumberEntity):
    def __init__(self, hass, name, hub, slave_id, control):
        self.hass = hass
        self._attr_name = name
        self._hub = hub
        self._slave_id = slave_id
        self._address = control["address"]
        self._scale = control.get("scale", 1.0)
        self._attr_native_unit_of_measurement = control.get("unit", "")
        self._attr_native_min_value = control.get("min", 0)
        self._attr_native_max_value = control.get("max", 100)
        self._attr_native_step = control.get("step", 1)
        self._group = control.get("group")
        self._value = None

    @property
    def native_value(self):
        return self._value

    @property
    def extra_state_attributes(self):
        return {"group": self._group} if self._group else {}

    async def async_set_native_value(self, value):
        scaled = int(value / self._scale)
        modbus = self.hass.data["modbus"][self._hub]
        await modbus.write_register(self._address, scaled, unit=self._slave_id)
        self._value = value
        self.async_write_ha_state()

# Modbus Select Control
class ModbusSelectEntity(SelectEntity):
    def __init__(self, hass, name, hub, slave_id, control):
        self.hass = hass
        self._attr_name = name
        self._hub = hub
        self._slave_id = slave_id
        self._address = control["address"]
        self._options_map = control.get("options", {})
        self._attr_options = list(self._options_map.keys())
        self._current_option = None
        self._group = control.get("group")

    @property
    def current_option(self):
        return self._current_option

    @property
    def extra_state_attributes(self):
        return {"group": self._group} if self._group else {}

    async def async_select_option(self, option):
        value = self._options_map.get(option)
        if value is not None:
            modbus = self.hass.data["modbus"][self._hub]
            await modbus.write_register(self._address, value, unit=self._slave_id)
            self._current_option = option
            self.async_write_ha_state()

# Modbus Button Control
class ModbusButtonEntity(ButtonEntity):
    def __init__(self, hass, name, hub, slave_id, control):
        self.hass = hass
        self._attr_name = name
        self._hub = hub
        self._slave_id = slave_id
        self._address = control["address"]
        self._value = control.get("value", 1)
        self._group = control.get("group")

    @property
    def extra_state_attributes(self):
        return {"group": self._group} if self._group else {}

    async def async_press(self):
        modbus = self.hass.data["modbus"][self._hub]
        await modbus.write_register(self._address, self._value, unit=self._slave_id)
