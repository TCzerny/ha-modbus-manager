"""Modbus Template Sensor for Modbus Manager."""
import asyncio
import logging
from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_DEVICE_CLASS
)
from homeassistant.components.sensor.const import CONF_STATE_CLASS

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Modbus Template Sensors from a config entry."""
    try:
        _LOGGER.info("Setup von Modbus Template Sensoren für %s", entry.data.get("prefix", "unbekannt"))
        
        # Daten aus der Konfiguration abrufen
        if entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("Keine Konfigurationsdaten für Entry %s gefunden", entry.entry_id)
            return
        
        config_data = hass.data[DOMAIN][entry.entry_id]
        registers = config_data.get("registers", [])
        prefix = config_data.get("prefix", "unknown")
        template_name = config_data.get("template", "unknown")
        
        _LOGGER.info("Konfigurationsdaten abgerufen: prefix=%s, template=%s, register=%d", 
                     prefix, template_name, len(registers))
        
        if not registers:
            _LOGGER.warning("Keine Register für Template %s gefunden", template_name)
            return
        
        _LOGGER.info("Erstelle %d Sensoren für Template %s mit Präfix %s", len(registers), template_name, prefix)
        
        # Nur Sensor-Entitäten erstellen
        sensor_registers = [reg for reg in registers if reg.get("entity_type") == "sensor"]
        _LOGGER.info("Gefundene Sensor-Register: %d", len(sensor_registers))
        
        entities = []
        for reg in sensor_registers:
            try:
                # Unique_ID Format: {prefix}_{template_sensor_name}
                sensor_name = reg.get("name", "unknown")
                # Bereinige den Namen für den unique_id
                clean_name = sensor_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                unique_id = f"{prefix}_{clean_name}"
                
                _LOGGER.info("Erstelle Sensor: name=%s, prefix=%s, unique_id=%s", 
                             sensor_name, prefix, unique_id)
                
                entities.append(ModbusTemplateSensor(
                    hass=hass,
                    entry=entry,
                    register=reg,
                    prefix=prefix,
                    unique_id=unique_id
                ))
                
            except Exception as e:
                _LOGGER.error("Fehler beim Erstellen des Sensors %s: %s", reg.get("name", "unbekannt"), str(e))
                continue
        
        if entities:
            async_add_entities(entities)
            _LOGGER.info("%d Modbus Template Sensoren erfolgreich erstellt", len(entities))
        else:
            _LOGGER.warning("Keine Sensoren erstellt")
            
    except Exception as e:
        _LOGGER.error("Fehler beim Setup der Modbus Template Sensoren: %s", str(e))
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())


class ModbusTemplateSensor(SensorEntity):
    """Representation of a Modbus Template Sensor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, register: dict, prefix: str, unique_id: str):
        """Initialize the Modbus Template Sensor."""
        self._hass = hass
        self._entry = entry
        self._register = register
        self._prefix = prefix
        self._unique_id = unique_id
        
        # Register-Eigenschaften
        self._name = register.get("name", "Unknown Sensor")
        self._address = register.get("address", 0)
        self._data_type = register.get("data_type", "uint16")
        self._count = register.get("count", 1)
        self._scale = register.get("scale", 1.0)
        self._offset = register.get("offset", 0.0)
        self._unit = register.get("unit_of_measurement", "")
        self._device_class = register.get("device_class")
        self._state_class = register.get("state_class")
        self._precision = register.get("precision", 0)
        
        # Modbus-spezifische Eigenschaften
        self._input_type = register.get("input_type", "input")
        self._slave_id = register.get("device_address", 1)
        
        # Entity-Attribute setzen
        self._attr_name = f"{prefix}_{self._name}"
        self._attr_unique_id = unique_id
        self._attr_device_class = self._device_class
        self._attr_state_class = self._state_class
        self._attr_native_unit_of_measurement = self._unit
        self._attr_should_poll = True
        
        # Für String-Sensoren device_class und state_class explizit auf None setzen
        if self._data_type == "string":
            self._attr_device_class = None
            self._attr_state_class = None
            # String-Sensoren sollten keine numerischen Werte haben
            self._attr_native_unit_of_measurement = None
        
        # Device-Info
        template_name = self._register.get("template", "unknown")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{prefix}_{template_name}")},
            name=f"{prefix} ({template_name})",
            manufacturer="Modbus Manager",
            model=template_name,
            via_device=(DOMAIN, entry.entry_id),
        )
        
        _LOGGER.info("Sensor %s initialisiert (Adresse: %d, Typ: %s, Präfix: %s, Name: %s, Unique-ID: %s)", 
                     self._name, self._address, self._data_type, prefix, self._attr_name, unique_id)

    @property
    def template_name(self) -> str:
        """Return the template name."""
        return self._register.get("template", "unknown")

    async def async_update(self) -> None:
        """Update the sensor value."""
        try:
            # Modbus-Hub aus der Konfiguration abrufen
            if self._entry.entry_id not in self._hass.data[DOMAIN]:
                _LOGGER.error("Keine Konfigurationsdaten für Entry %s gefunden", self._entry.entry_id)
                return
            
            config_data = self._hass.data[DOMAIN][self._entry.entry_id]
            hub = config_data.get("hub")
            
            if not hub:
                _LOGGER.error("Modbus-Hub nicht gefunden")
                return
            
            # Modbus-Operation basierend auf input_type
            if self._input_type == "input":
                # Input Register lesen
                result = await self._read_input_registers(hub)
            elif self._input_type == "holding":
                # Holding Register lesen
                result = await self._read_holding_registers(hub)
            elif self._input_type == "coil":
                # Coil lesen
                result = await self._read_coils(hub)
            elif self._input_type == "discrete":
                # Discrete Input lesen
                result = await self._read_discrete_inputs(hub)
            else:
                _LOGGER.warning("Unbekannter input_type: %s", self._input_type)
                return
            
            if result is not None:
                # Wert verarbeiten
                processed_value = self._process_value(result)
                self._attr_native_value = processed_value
                _LOGGER.debug("Sensor %s aktualisiert: %s", self._name, processed_value)
            else:
                _LOGGER.warning("Keine Daten für Sensor %s empfangen", self._name)
                
        except Exception as e:
            _LOGGER.error("Fehler beim Update von Sensor %s: %s", self._name, str(e))

    async def _read_input_registers(self, hub) -> Optional[Any]:
        """Read input registers from Modbus device."""
        try:
            # Verwende die korrekte Home Assistant Modbus API
            from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_INPUT
            
            # Modbus-Call über Standard API
            result = await hub.async_pb_call(
                self._slave_id,
                self._address,
                self._count,
                CALL_TYPE_REGISTER_INPUT
            )
            
            if result and hasattr(result, 'registers'):
                return result.registers
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Input-Register für %s: %s", self._name, str(e))
            return None

    async def _read_holding_registers(self, hub) -> Optional[Any]:
        """Read holding registers from Modbus device."""
        try:
            from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
            
            result = await hub.async_pb_call(
                self._slave_id,
                self._address,
                self._count,
                CALL_TYPE_REGISTER_HOLDING
            )
            
            if result and hasattr(result, 'registers'):
                return result.registers
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Holding-Register für %s: %s", self._name, str(e))
            return None

    async def _read_coils(self, hub) -> Optional[Any]:
        """Read coils from Modbus device."""
        try:
            from homeassistant.components.modbus.const import CALL_TYPE_COIL
            
            result = await hub.async_pb_call(
                self._slave_id,
                self._address,
                self._count,
                CALL_TYPE_COIL
            )
            
            if result and hasattr(result, 'bits'):
                return result.bits
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Coils für %s: %s", self._name, str(e))
            return None

    async def _read_discrete_inputs(self, hub) -> Optional[Any]:
        """Read discrete inputs from Modbus device."""
        try:
            from homeassistant.components.modbus.const import CALL_TYPE_DISCRETE
            
            result = await hub.async_pb_call(
                self._slave_id,
                self._address,
                self._count,
                CALL_TYPE_DISCRETE
            )
            
            if result and hasattr(result, 'bits'):
                return result.bits
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Discrete-Inputs für %s: %s", self._name, str(e))
            return None

    def _process_value(self, raw_value: Any) -> Any:
        """Process the raw Modbus value."""
        try:
            if raw_value is None:
                return None
            
            # Wert basierend auf data_type verarbeiten
            if self._data_type == "uint16":
                if isinstance(raw_value, list) and len(raw_value) > 0:
                    value = raw_value[0]
                else:
                    value = raw_value
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "int16":
                if isinstance(raw_value, list) and len(raw_value) > 0:
                    value = raw_value[0]
                    if value > 32767:  # Negative Zahl in 16-bit
                        value = value - 65536
                else:
                    value = raw_value
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "uint32":
                if isinstance(raw_value, list) and len(raw_value) >= 2:
                    value = (raw_value[0] << 16) | raw_value[1]
                else:
                    value = raw_value
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "int32":
                if isinstance(raw_value, list) and len(raw_value) >= 2:
                    value = (raw_value[0] << 16) | raw_value[1]
                    if value > 2147483647:  # Negative Zahl in 32-bit
                        value = value - 4294967296
                else:
                    value = raw_value
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "float":
                if isinstance(raw_value, list) and len(raw_value) >= 2:
                    import struct
                    # 32-bit Float aus zwei 16-bit Registern
                    raw_bytes = struct.pack('>HH', raw_value[0], raw_value[1])
                    value = struct.unpack('>f', raw_bytes)[0]
                else:
                    value = raw_value
                processed_value = (value * self._scale) + self._offset
                
            elif self._data_type == "string":
                if isinstance(raw_value, list):
                    # String aus Registern extrahieren
                    string_value = ""
                    for reg in raw_value:
                        if reg == 0:  # Null-Terminator
                            break
                        string_value += chr((reg >> 8) & 0xFF) + chr(reg & 0xFF)
                    value = string_value.strip('\x00')
                else:
                    value = str(raw_value)
                processed_value = value
                
                # Für String-Sensoren sicherstellen, dass der Wert ein String ist
                if not isinstance(processed_value, str):
                    processed_value = str(processed_value)
                
            elif self._data_type == "boolean":
                if isinstance(raw_value, list) and len(raw_value) > 0:
                    value = bool(raw_value[0])
                else:
                    value = bool(raw_value)
                processed_value = value
                
            else:
                # Fallback für unbekannte Typen
                if isinstance(raw_value, list) and len(raw_value) > 0:
                    value = raw_value[0]
                else:
                    value = raw_value
                processed_value = (value * self._scale) + self._offset
            
            # Präzision anwenden
            if isinstance(processed_value, (int, float)) and self._precision > 0:
                processed_value = round(processed_value, self._precision)
            
            return processed_value
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Wertverarbeitung für %s: %s", self._name, str(e))
            return None
