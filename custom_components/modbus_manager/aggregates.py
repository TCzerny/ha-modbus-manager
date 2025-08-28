from homeassistant.components.sensor import SensorEntity

class ModbusAggregateSensor(SensorEntity):
    def __init__(self, hass, name, group_tag, method="sum"):
        self._hass = hass
        self._attr_name = name
        self._group_tag = group_tag
        self._method = method
        self._state = None

    @property
    def state(self):
        return self._state

    async def async_update(self):
        # Finde alle Sensoren mit passendem group_tag
        sensors = [
            entity for entity in self._hass.states.async_all("sensor")
            if entity.attributes.get("group") == self._group_tag
        ]

        values = []
        for sensor in sensors:
            try:
                val = float(sensor.state)
                values.append(val)
            except (ValueError, TypeError):
                continue

        if self._method == "sum":
            self._state = sum(values)
        elif self._method == "average" and values:
            self._state = round(sum(values) / len(values), 2)
        else:
            self._state = None
