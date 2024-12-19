"""Modbus Manager Sensor Platform."""
import logging
from datetime import timedelta
import struct
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
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
_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Richte die Modbus Manager Sensoren ein."""
    _LOGGER.debug(
        "Sensor Setup wird ausgeführt",
        extra={
            "entry_id": entry.entry_id
        }
    )

    # Prüfe ob die Domain existiert
    if DOMAIN not in hass.data:
        _LOGGER.error(
            "Domain nicht in hass.data gefunden",
            extra={
                "entry_id": entry.entry_id
            }
        )
        return False

    # Prüfe ob der Hub existiert
    if entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error(
            "Hub nicht gefunden",
            extra={
                "entry_id": entry.entry_id
            }
        )
        return False

    hub: ModbusManagerHub = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug(
        "Hub gefunden",
        extra={
            "entry_id": entry.entry_id,
            "hub_name": hub.name
        }
    )

    try:
        # Hole die Gerätedefinition
        device_def = await hub.get_device_definition(hub.device_type)
        if not device_def:
            _LOGGER.error(
                "Keine Gerätekonfiguration gefunden",
                extra={
                    "entry_id": entry.entry_id,
                    "device_type": hub.device_type
                }
            )
            return False

        _LOGGER.debug(
            "Gerätekonfiguration geladen",
            extra={
                "entry_id": entry.entry_id,
                "device_type": hub.device_type
            }
        )
        
        # Erstelle die Sensoren
        sensors = []
        read_registers = device_def.get('registers', {}).get('read', [])
        polling_config = device_def.get('polling', {})
        
        _LOGGER.info(
            "Erstelle Sensoren",
            extra={
                "entry_id": entry.entry_id,
                "sensor_count": len(read_registers)
            }
        )

        # Erstelle einen Coordinator für jede Polling-Gruppe
        for group_name, group_config in polling_config.items():
            interval = group_config.get('interval', 30)
            registers = group_config.get('registers', [])
            
            if not registers:
                continue
                
            coordinator = DataUpdateCoordinator(
                hass,
                _LOGGER,
                name=f"{hub.name}_{group_name}",
                update_method=lambda: hub.read_registers(hub.device_type),
                update_interval=timedelta(seconds=interval),
            )
            
            # Speichere den Coordinator im Hub
            if hub.device_type not in hub.coordinators:
                hub.coordinators[hub.device_type] = {}
            hub.coordinators[hub.device_type][group_name] = coordinator
            
            _LOGGER.debug(
                "Coordinator erstellt",
                extra={
                    "entry_id": entry.entry_id,
                    "group": group_name,
                    "interval": interval
                }
            )
            
            # Erstelle Sensoren für diese Gruppe
            for reg_name in registers:
                reg_def = next((r for r in read_registers if r['name'] == reg_name), None)
                if reg_def:
                    try:
                        sensor = ModbusSensor(
                            hub=hub,
                            coordinator=coordinator,
                            name=reg_name,
                            device_def=reg_def,
                            polling_group=group_name
                        )
                        sensors.append(sensor)
                        _LOGGER.debug(
                            "Sensor erstellt",
                            extra={
                                "entry_id": entry.entry_id,
                                "name": reg_name,
                                "group": group_name
                            }
                        )
                    except Exception as e:
                        _LOGGER.error(
                            "Fehler beim Erstellen des Sensors",
                            extra={
                                "entry_id": entry.entry_id,
                                "name": reg_name,
                                "error": str(e)
                            }
                        )

        if sensors:
            async_add_entities(sensors)
            _LOGGER.info(
                "Sensoren erfolgreich hinzugefügt",
                extra={
                    "entry_id": entry.entry_id,
                    "count": len(sensors)
                }
            )
            return True

        return False

    except Exception as e:
        _LOGGER.error(
            "Fehler beim Setup der Sensoren",
            extra={
                "entry_id": entry.entry_id,
                "error": str(e)
            }
        )
        return False

class ModbusSensor(CoordinatorEntity, SensorEntity):
    """Modbus Manager Sensor Klasse."""

    def __init__(
        self,
        hub: ModbusManagerHub,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_def: dict,
        polling_group: str,
    ):
        """Initialisiere den Sensor."""
        super().__init__(coordinator)
        
        self._hub = hub
        self._name = name
        self._device_def = device_def
        self._polling_group = polling_group
        
        # Setze die Sensor-Attribute
        self._attr_name = f"{hub.name} {name}"
        self._attr_unique_id = f"{hub.name}_{name}"
        self._attr_native_unit_of_measurement = device_def.get("unit_of_measurement")
        self._attr_device_class = device_def.get("device_class")
        self._attr_state_class = device_def.get("state_class")
        
        # Setze die Geräte-Info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.name)},
            name=hub.name,
            manufacturer=device_def.get("manufacturer", "Unknown"),
            model=hub.device_type,
        )
        
        _LOGGER.debug(
            f"Sensor initialisiert: {self._name} "
            f"(ID: {self._attr_unique_id}, "
            f"Polling-Gruppe: {self._polling_group})"
        )

    @property
    def native_value(self) -> Any:
        """Gib den aktuellen Zustand des Sensors zurück."""
        if not self.coordinator.data:
            return None
            
        try:
            # Hole die Rohdaten für diesen Sensor
            raw_value = self.coordinator.data.get(self._name)
            if raw_value is None:
                return None
                
            # Konvertiere die Daten basierend auf dem Datentyp
            data_type = self._device_def.get("type", "uint16")
            value = self._convert_value(raw_value, data_type)
            
            # Wende Skalierung an
            scale = self._device_def.get("scale", 1)
            if scale != 1:
                value = value * scale
                
            # Runde den Wert, falls erforderlich
            precision = self._device_def.get("precision")
            if precision is not None:
                value = round(value, precision)
                
            return value
            
        except Exception as e:
            _LOGGER.error(f"Fehler beim Verarbeiten des Sensorwerts {self._name}: {e}")
            return None

    def _convert_value(self, raw_value: Any, data_type: str) -> Any:
        """Konvertiere den Rohwert in den korrekten Datentyp."""
        try:
            if not isinstance(raw_value, (list, tuple)):
                raw_value = [raw_value]
                
            if data_type == "uint16":
                return raw_value[0]
            elif data_type == "int16":
                value = raw_value[0]
                return value - 65536 if value > 32767 else value
            elif data_type == "uint32":
                if len(raw_value) < 2:
                    return None
                return (raw_value[0] << 16) + raw_value[1]
            elif data_type == "int32":
                if len(raw_value) < 2:
                    return None
                value = (raw_value[0] << 16) + raw_value[1]
                return value - 4294967296 if value > 2147483647 else value
            elif data_type in ["float", "float32"]:
                if len(raw_value) < 2:
                    return None
                return struct.unpack('>f', struct.pack('>HH', raw_value[0], raw_value[1]))[0]
            elif data_type == "string":
                return ''.join([chr(x) for x in raw_value]).strip('\x00')
            elif data_type == "bool":
                return bool(raw_value[0])
            else:
                _LOGGER.warning(f"Unbekannter Datentyp: {data_type}")
                return None
                
        except Exception as e:
            _LOGGER.error(f"Fehler bei der Datenkonvertierung für {self._name}: {e}")
            return None