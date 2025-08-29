from homeassistant.helpers.template import Template
from homeassistant.helpers.entity import Entity

class CalculatedSensor(Entity):
    def __init__(self, hass, name, template_str, unit=None, device_class=None, state_class=None, group=None, prefix=None):
        self.hass = hass
        self._attr_name = name
        self._raw_template = template_str
        self._template = Template(self._inject_prefix(template_str, prefix), hass)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._group = group
        self._state = None

    def _inject_prefix(self, template_str, prefix):
        if prefix:
            return template_str.replace("{prefix}", prefix)
        return template_str

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {"group": self._group} if self._group else {}

    async def async_update(self):
        try:
            rendered = await self._template.async_render()
            self._state = round(float(rendered), 2)
        except Exception:
            self._state = None
