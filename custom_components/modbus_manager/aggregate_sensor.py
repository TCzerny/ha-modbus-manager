"""Aggregate Sensor for Modbus Manager."""
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

    def __init__(self, hass: HomeAssistant, aggregate_config: dict, prefix: str):
        """Initialize the aggregate sensor."""
        self.hass = hass
        self._prefix = prefix
        self._aggregate_config = aggregate_config
        
        # Extract configuration
        self._name = aggregate_config.get("name", "Unknown Aggregate")
        self._group = aggregate_config.get("group", "")
        self._method = aggregate_config.get("method", "sum")
        self._unit = aggregate_config.get("unit_of_measurement", "")
        self._device_class = aggregate_config.get("device_class")
        self._state_class = aggregate_config.get("state_class")
        self._icon = aggregate_config.get("icon")
        
        # Generate unique ID and entity ID with better naming
        clean_name = self._name.lower().replace(' ', '_').replace('-', '_')
        self._attr_unique_id = f"MM_aggregate_{clean_name}"
        
        # Better name: remove "Total" prefix and make it shorter
        display_name = self._name
        if display_name.startswith("Total "):
            display_name = display_name[6:]  # Remove "Total "
        if display_name.startswith("Average "):
            display_name = display_name[8:]  # Remove "Average "
        if display_name.startswith("Max "):
            display_name = display_name[4:]  # Remove "Max "
        if display_name.startswith("Min "):
            display_name = display_name[4:]  # Remove "Min "
        
        # Add method suffix for clarity
        if self._method == "sum":
            display_name = f"{display_name} (Sum)"
        elif self._method == "average":
            display_name = f"{display_name} (Avg)"
        elif self._method == "max":
            display_name = f"{display_name} (Max)"
        elif self._method == "min":
            display_name = f"{display_name} (Min)"
        elif self._method == "count":
            display_name = f"{display_name} (Count)"
        
        self._attr_name = f"MM_{display_name}"
        
        # Entity properties
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = self._unit
        self._attr_device_class = self._device_class
        self._attr_state_class = self._state_class
        self._attr_icon = self._icon
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "MM_aggregates")},
            name="MM Modbus Manager Aggregates",
            manufacturer="Modbus Manager",
            model="Aggregation Hub"
        )
        
        # Tracking
        self._tracked_entities = []
        self._unsubscribe = None
        self._tracking_setup = False
        
        _LOGGER.debug("Aggregate sensor %s initialized (Group: %s, Method: %s)", 
                     self._name, self._group, self._method)

    def _setup_tracking(self):
        """Setup state change tracking for entities in this group."""
        try:
            # Find all entities with matching group tag
            self._find_group_entities()
            
            if not self._tracked_entities:
                _LOGGER.warning("Keine Entitäten für Gruppe %s gefunden", self._group)
                return
            
            # Setup state change tracking
            self._unsubscribe = async_track_state_change(
                self.hass,
                self._tracked_entities,
                self._state_changed
            )
            
            _LOGGER.info("Tracking für %d Entitäten in Gruppe %s eingerichtet", 
                        len(self._tracked_entities), self._group)
            self._tracking_setup = True
            
        except Exception as e:
            _LOGGER.error("Fehler beim Einrichten des Trackings für Gruppe %s: %s", 
                         self._group, str(e))

    def _find_group_entities(self):
        """Find all entities that belong to this group across all Modbus Manager devices."""
        try:
            all_states = self.hass.states.async_all()
            modbus_prefixes = self._get_modbus_prefixes()
            
            _LOGGER.debug("Suche nach Gruppe '%s' in %d Entitäten", self._group, len(all_states))
            _LOGGER.debug("Modbus-Präfixe: %s", modbus_prefixes)
            
            for state in all_states:
                if state.domain == "sensor":
                    attributes = state.attributes
                    group_attr = attributes.get("group")
                    
                    # Debug: Zeige alle Sensoren mit group Attribut (reduziert)
                    if group_attr:
                        _LOGGER.debug("Sensor mit Gruppe gefunden: %s -> Gruppe '%s'", state.entity_id, group_attr)
                    
                    if group_attr == self._group:
                        _LOGGER.debug("Gefunden: %s mit Gruppe '%s'", state.entity_id, group_attr)
                        
                        # Only include sensors from Modbus Manager devices
                        # Check if entity_id contains any of the modbus prefixes (case insensitive)
                        # Also check for entity_id pattern like "sensor.prefix_name"
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
            
            _LOGGER.info("Gefundene Entitäten für Gruppe %s: %s", self._group, self._tracked_entities)
            
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
            
            _LOGGER.info("State-Change erkannt: %s von %s zu %s", 
                        entity_id, old_state.state if old_state else "None", new_state.state)
            
            # Update aggregate value
            self._update_aggregate_value()
            
            # Notify Home Assistant about the change
            self.async_write_ha_state()
            
            _LOGGER.info("Aggregate-Sensor %s aktualisiert: %s", self._attr_name, self._attr_native_value)
            
        except Exception as e:
            _LOGGER.error("Fehler bei State-Change für Gruppe %s: %s", 
                         self._group, str(e))

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
                
            elif self._method == "average":
                result = sum(values) / len(values)
                
            elif self._method == "max":
                result = max(values)
                
            elif self._method == "min":
                result = min(values)
                
            elif self._method == "count":
                result = valid_entities
                
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
                         self._name, self._method, result, valid_entities)
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Aggregat-Berechnung für Gruppe %s: %s", 
                         self._group, str(e))
            self._attr_native_value = None

    async def async_added_to_hass(self):
        """Entity added to hass."""
        await super().async_added_to_hass()
        
        # Setup tracking after being added to hass
        if not self._tracking_setup:
            self._setup_tracking()
        
        # Initial update
        self._update_aggregate_value()
        self.async_write_ha_state()
        
        _LOGGER.debug("Aggregate-Sensor %s zu Home Assistant hinzugefügt", self._attr_name)

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
            "group": self._group,
            "method": self._method,
            "tracked_entities": self._tracked_entities,
            "entity_count": len(self._tracked_entities)
        }
