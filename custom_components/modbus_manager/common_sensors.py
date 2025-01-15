"""Common sensors for Modbus Manager."""
from datetime import timedelta
from typing import Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfPower, UnitOfEnergy
from homeassistant.helpers.entity import Entity

from .device import ModbusManagerDevice
from .logger import ModbusManagerLogger
from .helpers import EntityNameHelper, NameType

_LOGGER = ModbusManagerLogger(__name__)

class AggregationSensor(SensorEntity):
    """Sensor für aggregierte Werte mehrerer Geräte."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        config: dict,
        sensor_id: str,
        config_entry,
    ):
        """Initialisiere den Sensor."""
        self.hass = hass
        self.coordinator = coordinator
        self._config = config
        self._sensor_id = sensor_id
        
        # Verwende den EntityNameHelper für die Namen
        name_helper = EntityNameHelper(config_entry)
        self.entity_id = name_helper.convert(sensor_id, NameType.ENTITY_ID, domain="sensor")
        self._attr_unique_id = name_helper.convert(sensor_id, NameType.UNIQUE_ID)
        self._attr_name = name_helper.convert(sensor_id, NameType.DISPLAY_NAME)

    @property
    def native_value(self):
        """Aktueller Wert des Sensors."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_id)

    @property
    def native_unit_of_measurement(self) -> str:
        """Einheit des Sensors."""
        return self._config["unit_of_measurement"]

    @property
    def device_class(self) -> str:
        """Geräte-Klasse des Sensors."""
        return self._config["device_class"]

    @property
    def state_class(self) -> str:
        """Status-Klasse des Sensors."""
        return self._config["state_class"]

    @property
    def icon(self) -> str:
        """Icon des Sensors."""
        return self._config["icon"]

    @property
    def should_poll(self) -> bool:
        """Soll der Sensor aktiv abgefragt werden."""
        return False

    @property
    def available(self) -> bool:
        """Ist der Sensor verfügbar."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """Wenn der Sensor zu Home Assistant hinzugefügt wird."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

class AggregationDevice:
    """Gerät für die Aggregation von Werten mehrerer physischer Geräte."""
    
    def __init__(self, hass: HomeAssistant, category: str):
        """Initialisiere das Aggregations-Gerät."""
        self.hass = hass
        self.category = category
        self.name = f"modbus_manager_{category}_aggregation"
        self.devices: List[ModbusManagerDevice] = []
        self._sensors: Dict = {}
        self._setup_sensors_for_category()
        
        # Koordinator für regelmäßige Updates
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=self.name,
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=30),
        )

    def _setup_sensors_for_category(self):
        """Richtet die Sensor-Definitionen basierend auf der Kategorie ein."""
        if self.category == "inverter":
            self._sensors = {
                "total_pv_power": {
                    "name": "Gesamt PV Leistung",
                    "unique_id": "total_pv_power",
                    "unit_of_measurement": UnitOfPower.WATT,
                    "icon": "mdi:solar-power",
                    "device_class": SensorDeviceClass.POWER,
                    "state_class": "measurement",
                    "source_pattern": "*_pv_power",
                    "aggregation": "sum"
                },
                "total_daily_yield": {
                    "name": "Gesamt Tagesertrag",
                    "unique_id": "total_daily_yield",
                    "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                    "icon": "mdi:solar-power",
                    "device_class": SensorDeviceClass.ENERGY,
                    "state_class": "total_increasing",
                    "source_pattern": "*_daily_yield",
                    "aggregation": "sum"
                },
                "total_battery_power": {
                    "name": "Gesamt Batterie Leistung",
                    "unique_id": "total_battery_power",
                    "unit_of_measurement": UnitOfPower.WATT,
                    "icon": "mdi:battery",
                    "device_class": SensorDeviceClass.POWER,
                    "state_class": "measurement",
                    "source_pattern": "*_battery_power",
                    "aggregation": "sum"
                },
                "total_grid_power": {
                    "name": "Gesamt Netz Leistung",
                    "unique_id": "total_grid_power",
                    "unit_of_measurement": UnitOfPower.WATT,
                    "icon": "mdi:transmission-tower",
                    "device_class": SensorDeviceClass.POWER,
                    "state_class": "measurement",
                    "source_pattern": "*_grid_power",
                    "aggregation": "sum"
                }
            }
        elif self.category == "battery":
            self._sensors = {
                "total_battery_capacity": {
                    "name": "Gesamt Batterie Kapazität",
                    "unique_id": "total_battery_capacity",
                    "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                    "icon": "mdi:battery",
                    "device_class": SensorDeviceClass.ENERGY_STORAGE,
                    "state_class": "measurement",
                    "source_pattern": "*_battery_capacity",
                    "aggregation": "sum"
                }
            }

    async def add_device(self, device: ModbusManagerDevice):
        """Fügt ein neues Gerät zur Aggregation hinzu."""
        if device not in self.devices:
            self.devices.append(device)
            _LOGGER.info(
                "Gerät zur Aggregation hinzugefügt",
                extra={
                    "category": self.category,
                    "device": device.name
                }
            )
            await self.coordinator.async_refresh()

    async def remove_device(self, device: ModbusManagerDevice):
        """Entfernt ein Gerät aus der Aggregation."""
        if device in self.devices:
            self.devices.remove(device)
            _LOGGER.info(
                "Gerät aus Aggregation entfernt",
                extra={
                    "category": self.category,
                    "device": device.name
                }
            )
            await self.coordinator.async_refresh()

    async def _async_update_data(self):
        """Aktualisiert die aggregierten Daten."""
        data = {}
        for sensor_id, sensor_config in self._sensors.items():
            try:
                pattern = sensor_config["source_pattern"]
                aggregation = sensor_config["aggregation"]
                values = []
                
                for device in self.devices:
                    # Suche nach passenden Sensoren im Gerät
                    matching_sensors = [
                        entity for entity_id, entity in device.entities.items()
                        if pattern.replace("*", "") in entity_id
                    ]
                    for sensor in matching_sensors:
                        if hasattr(sensor, "native_value") and sensor.native_value is not None:
                            values.append(float(sensor.native_value))
                
                if values:
                    if aggregation == "sum":
                        data[sensor_id] = sum(values)
                    elif aggregation == "average":
                        data[sensor_id] = sum(values) / len(values)
                    elif aggregation == "min":
                        data[sensor_id] = min(values)
                    elif aggregation == "max":
                        data[sensor_id] = max(values)
            
            except Exception as e:
                _LOGGER.error(
                    "Fehler bei der Aggregation",
                    extra={
                        "sensor": sensor_id,
                        "error": str(e)
                    }
                )
                
        return data

    def get_sensors(self) -> List[Entity]:
        """Erstellt die Sensor-Entitäten für Home Assistant."""
        return [
            AggregationSensor(
                self.hass,
                self.coordinator,
                sensor_config,
                sensor_id,
                self
            )
            for sensor_id, sensor_config in self._sensors.items()
        ]
