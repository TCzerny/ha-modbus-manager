"""Modbus Manager Binary Sensor Platform."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .modbus_hub import ModbusManagerHub
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Richte die Modbus Manager Binary Sensoren ein."""
    _LOGGER.debug(
        "Binary Sensor Setup wird ausgeführt",
        extra={
            "entry_id": entry.entry_id
        }
    )
    return True  # Noch keine Binary Sensoren implementiert

class ModbusBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Modbus Manager Binary Sensor Klasse."""

    def __init__(
        self,
        hub: ModbusManagerHub,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_def: dict,
        polling_group: str,
    ):
        """Initialisiere den Binary Sensor."""
        super().__init__(coordinator)
        
        self._hub = hub
        self._name = name
        self._device_def = device_def
        self._polling_group = polling_group
        
        # Setze die Sensor-Attribute
        self._attr_name = f"{hub.name} {name}"
        self._attr_unique_id = f"{hub.name}_{name}"
        self._attr_device_class = device_def.get("device_class")
        
        # Setze die Geräte-Info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.name)},
            name=hub.name,
            manufacturer=device_def.get("manufacturer", "Unknown"),
            model=hub.device_type,
        )

    @property
    def is_on(self) -> bool:
        """Gib den aktuellen Zustand des Binary Sensors zurück."""
        if not self.coordinator.data:
            return False
            
        try:
            # Hole die Rohdaten für diesen Sensor
            raw_value = self.coordinator.data.get(self._name)
            if raw_value is None:
                return False
                
            return bool(raw_value[0])
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Verarbeiten des Binary Sensor Werts",
                extra={
                    "name": self._name,
                    "error": str(e)
                }
            )
            return False 