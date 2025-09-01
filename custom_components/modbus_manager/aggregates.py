"""Aggregations Module for Modbus Manager."""
from __future__ import annotations

from typing import Dict, List, Any, Optional
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class ModbusAggregateSensor(SensorEntity):
    """Representation of a Modbus Aggregate Sensor."""

    def __init__(self, hass: HomeAssistant, name: str = None, unique_id: str = None, 
                 group_tag: str = None, method: str = None, device_info: dict = None, 
                 prefix: str = "", aggregate_config: dict = None):
        """Initialize the aggregate sensor.
        
        Args:
            hass: Home Assistant instance
            name: Sensor name (for auto-created sensors)
            unique_id: Unique ID (for auto-created sensors)
            group_tag: Group tag (for auto-created sensors)
            method: Aggregation method (for auto-created sensors)
            device_info: Device info (for auto-created sensors)
            prefix: Device prefix
            aggregate_config: Configuration dict (for template-based sensors)
        """
        self.hass = hass
        self._prefix = prefix
        
        # Support both auto-created and template-based sensors
        if aggregate_config:
            # Template-based sensor
            self._name = aggregate_config.get("name", "Unknown Aggregate")
            self._group_tag = aggregate_config.get("group", "")
            self._method = aggregate_config.get("method", "sum")
            self._unit = aggregate_config.get("unit_of_measurement", "")
            self._device_class = aggregate_config.get("device_class")
            self._state_class = aggregate_config.get("state_class")
            self._icon = aggregate_config.get("icon")
            
            # Generate unique ID and entity ID with better naming
            clean_name = self._name.lower().replace(' ', '_').replace('-', '_')
            self._attr_unique_id = f"MM_aggregate_{clean_name}"
            
            # Better name: remove prefixes and make it shorter
            display_name = self._name
            if display_name.startswith("Total "):
                display_name = display_name[6:]  # Remove "Total "
            if display_name.startswith("Average "):
                display_name = display_name[8:]  # Remove "Average "
            if display_name.startswith("Max "):
                display_name = display_name[4:]  # Remove "Max "
            if display_name.startswith("Min "):
                display_name = display_name[4:]  # Remove "Min "
            
            self._attr_name = display_name
            
            # Device info for template-based sensors
            device_info = {
                "identifiers": {(DOMAIN, f"modbus_manager_aggregate_{clean_name}")},
                "name": f"Modbus Manager Aggregate {display_name}",
                "manufacturer": "Modbus Manager",
                "model": "Aggregation Sensor"
            }
            
        else:
            # Auto-created sensor
            self._name = name
            self._group_tag = group_tag
            self._method = method
            self._unit = ""
            self._device_class = None
            self._state_class = "measurement"
            self._icon = None
            
            # Generate proper entity_id with meaningful prefix
            clean_name = name.lower().replace(' ', '_').replace('-', '_')
            self._attr_name = name
            self._attr_unique_id = unique_id
        
        self._attr_device_info = DeviceInfo(**device_info)
        
        # Entity properties
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = self._unit
        self._attr_device_class = self._device_class
        self._attr_state_class = self._state_class
        if self._icon:
            self._attr_icon = self._icon
        
        # Tracking
        self._tracked_entities = []
        self._unsubscribe = None
        self._tracking_setup = False

    def _setup_tracking(self):
        """Setup state change tracking for entities in this group."""
        try:
            # Find all entities with matching group tag
            self._find_group_entities()
            
            if not self._tracked_entities:
                _LOGGER.warning("Keine Entitäten für Gruppe %s gefunden", self._group_tag)
                return
            
            # Setup state change tracking using STANDARD Home Assistant API
            self._unsubscribe = async_track_state_change(
                self.hass,
                self._tracked_entities,
                self._state_changed
            )
            
            _LOGGER.info("Tracking für %d Entitäten in Gruppe %s eingerichtet", 
                        len(self._tracked_entities), self._group_tag)
            self._tracking_setup = True
            
        except Exception as e:
            _LOGGER.error("Fehler beim Einrichten des Trackings für Gruppe %s: %s", 
                         self._group_tag, str(e))

    def _find_group_entities(self):
        """Find all entities that belong to this group across all Modbus Manager devices."""
        try:
            all_states = self.hass.states.async_all()
            modbus_prefixes = self._get_modbus_prefixes()
            
            _LOGGER.debug("Suche nach Entitäten für Gruppe %s mit Präfixen: %s", 
                         self._group_tag, modbus_prefixes)
            
            for state in all_states:
                if state.domain == "sensor":
                    attributes = state.attributes
                    group_attr = attributes.get("group")
                    
                    if group_attr == self._group_tag:
                        _LOGGER.debug("Gefunden: %s mit Gruppe '%s'", state.entity_id, group_attr)
                        
                        # Check if it's a Modbus Manager entity (case insensitive)
                        is_modbus_entity = any(
                            prefix.lower() in state.entity_id.lower() or 
                            f"sensor.{prefix.lower()}_" in state.entity_id.lower()
                            for prefix in modbus_prefixes
                        )
                        
                        _LOGGER.debug("Prüfe %s: is_modbus_entity=%s, prefixes=%s", 
                                     state.entity_id, is_modbus_entity, modbus_prefixes)
                        
                        if is_modbus_entity:
                            # Don't track aggregate sensors themselves
                            if not any(f"{prefix}_aggregate_" in state.entity_id for prefix in modbus_prefixes):
                                self._tracked_entities.append(state.entity_id)
                                _LOGGER.debug("Hinzugefügt zu Tracking: %s", state.entity_id)
                            else:
                                _LOGGER.debug("Überspringe %s - ist Aggregate-Sensor", state.entity_id)
                        else:
                            _LOGGER.debug("Überspringe %s - kein Modbus Manager Entity", state.entity_id)
            
            _LOGGER.info("Gefundene Entitäten für Gruppe %s: %s", self._group_tag, self._tracked_entities)
            
        except Exception as e:
            _LOGGER.error("Fehler beim Finden der Gruppen-Entitäten: %s", str(e))
    
    def _get_modbus_prefixes(self) -> List[str]:
        """Get all Modbus Manager prefixes from config entries."""
        try:
            prefixes = []
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                prefix = entry.data.get("prefix", "")
                if prefix:
                    prefixes.append(prefix)
            return prefixes
        except Exception as e:
            _LOGGER.error("Fehler beim Abrufen der Modbus-Präfixe: %s", str(e))
            return []

    @callback
    def _state_changed(self, entity_id: str, old_state, new_state):
        """Handle state changes of tracked entities."""
        try:
            if new_state is None:
                return
            
            # Update aggregate value
            self._update_aggregate_value()
            
            # Notify Home Assistant about the change
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error("Fehler bei State-Change für Gruppe %s: %s", 
                         self._group_tag, str(e))

    def _update_aggregate_value(self):
        """Update the aggregate value based on current entity states."""
        try:
            values = []
            valid_entities = 0
            
            for entity_id in self._tracked_entities:
                state = self.hass.states.get(entity_id)
                if state is None or state.state in ["unavailable", "unknown"]:
                    continue
                
                try:
                    value = float(state.state)
                    values.append(value)
                    valid_entities += 1
                except (ValueError, TypeError):
                    _LOGGER.debug("Entität %s hat keinen gültigen numerischen Wert: %s", 
                                 entity_id, state.state)
                    continue
            
            if not values:
                self._attr_native_value = None
                return
            
            # Calculate aggregate value based on method
            if self._method == "sum":
                result = sum(values)
                self._attr_native_unit_of_measurement = self._get_common_unit()
                
            elif self._method == "average":
                result = sum(values) / len(values)
                self._attr_native_unit_of_measurement = self._get_common_unit()
                
            elif self._method == "max":
                result = max(values)
                self._attr_native_unit_of_measurement = self._get_common_unit()
                
            elif self._method == "min":
                result = min(values)
                self._attr_native_unit_of_measurement = self._get_common_unit()
                
            elif self._method == "count":
                result = valid_entities
                self._attr_native_unit_of_measurement = ""
                
            else:
                _LOGGER.warning("Unbekannte Aggregations-Methode: %s", self._method)
                result = None
            
            # Apply precision if needed
            if result is not None and self._method != "count":
                if self._method == "average":
                    result = round(result, 2)
                else:
                    result = round(result, 3)
            
            self._attr_native_value = result
            
            _LOGGER.debug("Aggregat %s aktualisiert: %s = %s (aus %d Entitäten)", 
                         self._attr_name, self._method, result, valid_entities)
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Aggregat-Berechnung für Gruppe %s: %s", 
                         self._group_tag, str(e))
            self._attr_native_value = None

    def _get_common_unit(self) -> str:
        """Get the most common unit of measurement from tracked entities."""
        try:
            units = {}
            for entity_id in self._tracked_entities:
                state = self.hass.states.get(entity_id)
                if state and hasattr(state, 'attributes'):
                    unit = state.attributes.get('unit_of_measurement', '')
                    if unit:
                        units[unit] = units.get(unit, 0) + 1
            
            if units:
                # Return most common unit
                return max(units, key=units.get)
            
            return ""
            
        except Exception as e:
            _LOGGER.error("Fehler beim Ermitteln der Einheit: %s", str(e))
            return ""

    async def async_added_to_hass(self):
        """Entity added to hass."""
        await super().async_added_to_hass()
        
        # Setup tracking after being added to hass
        if not self._tracking_setup:
            self._setup_tracking()
        
        # Initial update
        self._update_aggregate_value()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Entity will be removed from hass."""
        if self._unsubscribe:
            self._unsubscribe()
        await super().async_will_remove_from_hass()

    @property
    def should_poll(self) -> bool:
        """Return False as this entity is updated via state change tracking."""
        return False

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "group": self._group_tag,
            "method": self._method,
            "tracked_entities": self._tracked_entities,
            "entity_count": len(self._tracked_entities)
        }


class AggregationManager:
    """Manager for creating and managing aggregate sensors."""
    
    def __init__(self, hass: HomeAssistant, prefix: str):
        """Initialize the aggregation manager."""
        self.hass = hass
        self.prefix = prefix
        self._aggregate_sensors = {}
        self._group_discovery_done = False
    
    async def discover_groups(self) -> List[str]:
        """Discover all available groups from existing sensors across all Modbus Manager devices."""
        try:
            groups = set()
            all_states = self.hass.states.async_all()
            
            for state in all_states:
                if state.domain == "sensor":
                    attributes = state.attributes
                    group = attributes.get("group")
                    if group:
                        # Only include sensors from Modbus Manager devices
                        if state.entity_id.startswith("sensor.") and any(
                            prefix in state.entity_id for prefix in self._get_modbus_prefixes()
                        ):
                            groups.add(group)
            
            discovered_groups = list(groups)
            _LOGGER.info("Entdeckte Gruppen über alle Modbus Manager Geräte: %s", discovered_groups)
            
            self._group_discovery_done = True
            return discovered_groups
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Gruppen-Entdeckung: %s", str(e))
            return []
    
    def _get_modbus_prefixes(self) -> List[str]:
        """Get all Modbus Manager prefixes from config entries."""
        try:
            prefixes = []
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                prefix = entry.data.get("prefix", "")
                if prefix:
                    prefixes.append(prefix)
            return prefixes
        except Exception as e:
            _LOGGER.error("Fehler beim Abrufen der Modbus-Präfixe: %s", str(e))
            return []
    
    async def discover_existing_groups(self) -> List[str]:
        """Discover existing groups (alias for discover_groups)."""
        return await self.discover_groups()
    
    async def create_aggregate_sensors(self, group_tag: str, methods: List[str] = None) -> List[ModbusAggregateSensor]:
        """Create aggregate sensors for a specific group."""
        if methods is None:
            methods = ["sum", "average", "max", "min"]
        
        try:
            sensors = []
            
            for method in methods:
                sensor_name = f"ModbusManager_{group_tag}_{method}"
                unique_id = f"modbus_manager_aggregate_{group_tag}_{method}"  # Global unique ID with meaningful prefix
                
                device_info = {
                    "identifiers": {(DOMAIN, f"modbus_manager_aggregate_{group_tag}")},
                    "name": f"Modbus Manager Aggregate {group_tag}",
                    "manufacturer": "Modbus Manager",
                    "model": "Aggregation Sensor"
                }
                
                sensor = ModbusAggregateSensor(
                    hass=self.hass,
                    name=sensor_name,
                    unique_id=unique_id,
                    group_tag=group_tag,
                    method=method,
                    device_info=device_info,
                    prefix=self.prefix
                )
                
                sensors.append(sensor)
                self._aggregate_sensors[unique_id] = sensor
            
            _LOGGER.info("Aggregat-Sensoren für Gruppe %s erstellt: %s", 
                        group_tag, [s.name for s in sensors])
            
            return sensors
            
        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen der Aggregat-Sensoren für Gruppe %s: %s", 
                         group_tag, str(e))
            return []
    
    def get_aggregate_sensors(self) -> List[ModbusAggregateSensor]:
        """Get all created aggregate sensors."""
        return list(self._aggregate_sensors.values())
    
    def remove_aggregate_sensor(self, unique_id: str):
        """Remove a specific aggregate sensor."""
        if unique_id in self._aggregate_sensors:
            sensor = self._aggregate_sensors[unique_id]
            sensor.async_remove()
            del self._aggregate_sensors[unique_id]
            _LOGGER.info("Aggregat-Sensor %s entfernt", unique_id)
