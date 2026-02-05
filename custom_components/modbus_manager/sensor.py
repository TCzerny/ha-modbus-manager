"""Simplified sensor entity using ModbusCoordinator."""

from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import create_base_extra_state_attributes, is_coordinator_connected
from .logger import ModbusManagerLogger
from .template_loader import load_templates

_LOGGER = ModbusManagerLogger(__name__)


async def _handle_group_assignments(
    hass: HomeAssistant, sensors: list[ModbusCoordinatorSensor]
) -> None:
    """Handle group assignments for coordinator sensors."""
    try:
        registry = entity_registry.async_get(hass)

        for sensor in sensors:
            if hasattr(sensor, "_group") and sensor._group:
                # Get the entity registry entry
                entity_id = f"sensor.{sensor.entity_id}"
                entry = registry.async_get(entity_id)

                if entry:
                    # Update the entity registry entry with group information
                    registry.async_update_entity(
                        entity_id,
                        entity_category=None,  # Keep existing category
                        group=sensor._group,
                    )

    except Exception as e:
        _LOGGER.error("Error handling group assignments: %s", str(e))


class ModbusCoordinatorSensor(CoordinatorEntity, SensorEntity):
    """Simplified sensor that gets data from coordinator."""

    def __init__(
        self,
        coordinator: ModbusCoordinator,
        register_config: dict[str, Any],
        device_info: dict[str, Any],
    ):
        """Initialize the coordinator sensor."""
        super().__init__(coordinator)
        self.register_config = register_config
        self._attr_device_info = DeviceInfo(**device_info)

        # Determine if this is a string sensor
        # Only treat as string sensor if data_type is explicitly "string"
        # map and options are for display purposes only, not data type indication
        self.is_string_sensor = register_config.get("data_type") == "string"

        # Set entity properties from register config
        # unique_id is already processed by coordinator with prefix via _process_entities_with_prefix
        self._attr_has_entity_name = True
        self._attr_name = register_config.get("name", "Unknown Sensor")
        self._attr_unique_id = register_config.get("unique_id", "unknown")
        default_entity_id = register_config.get("default_entity_id")
        if default_entity_id:
            if isinstance(default_entity_id, str):
                default_entity_id = default_entity_id.lower()
            if "." in default_entity_id:
                self.entity_id = default_entity_id
            else:
                self.entity_id = f"sensor.{default_entity_id}"
        self._attr_native_unit_of_measurement = register_config.get(
            "unit_of_measurement", ""
        )
        self._attr_device_class = register_config.get("device_class")
        self._attr_state_class = register_config.get("state_class")

        # Set entity category - diagnostic for register info, None for primary sensors
        # Diagnostic sensors expose configuration/diagnostics but don't allow changing them
        entity_category_str = register_config.get("entity_category")
        if entity_category_str == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category_str == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            # Default: None for primary sensors (main data points)
            self._attr_entity_category = None

        # Store scaling and precision for value processing
        self._scale = register_config.get("scale", 1.0)
        self._offset = register_config.get("offset", 0.0)
        self._precision = register_config.get("precision")

        # Store additional template parameters
        self._group = register_config.get("group")
        self._scan_interval = register_config.get("scan_interval")
        self._input_type = register_config.get("input_type")
        self._data_type = register_config.get("data_type")

        # Store mapping flags for later use
        self._has_mapping = bool(
            register_config.get("map")
            or register_config.get("options")
            or register_config.get("flags")
        )
        # Distinguish between flags (bitwise operations) and map/options (string mapping)
        self._has_flags = bool(register_config.get("flags"))
        self._has_map_or_options = bool(
            register_config.get("map") or register_config.get("options")
        )

        # For string sensors and sensors with mapping, override properties to prevent HA numeric validation
        # Use the same strategy as the legacy code
        if self.is_string_sensor or self._has_mapping:
            self._attr_device_class = None
            self._attr_state_class = None
            self._attr_native_unit_of_measurement = None
            # Don't set precision for string/mapped values (causes HA errors)
            self._precision = None
        else:
            # Set suggested_display_precision only for numeric sensors
            # This controls how many decimal places are shown in the UI
            if self._precision is not None:
                self._attr_suggested_display_precision = self._precision

        # Minimize extra_state_attributes to reduce database size for frequently updating entities
        # Only include static/essential attributes, not frequently changing values
        # scale, offset, precision are static configuration - keep them
        # group, scan_interval, input_type are static - keep them
        # unit_of_measurement, device_class, state_class are already in entity properties - remove from attributes
        self._attr_extra_state_attributes = create_base_extra_state_attributes(
            unique_id=self._attr_unique_id,
            register_config=register_config,
            scan_interval=self._scan_interval,
        )

        self._attr_icon = register_config.get("icon")

        # Create register key for data lookup
        self.register_key = self._create_register_key(register_config)

    def _create_register_key(self, register_config: dict[str, Any]) -> str:
        """Create unique key for register data lookup."""
        return f"{register_config.get('unique_id', 'unknown')}_{register_config.get('address', 0)}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        try:
            # Get our specific register data from coordinator
            register_data = self.coordinator.get_register_data(self.register_key)

            if register_data:
                # Extract raw and processed values for debugging
                raw_value = register_data.get("raw_value")
                processed_value = register_data.get("processed_value")
                numeric_value = register_data.get("numeric_value")

                if processed_value is not None:
                    # Distinguish between flags (bitwise operations) and map/options (string mapping)
                    # - Flags (e.g., running_state): Use numeric value for template compatibility
                    # - Map/Options (e.g., cable_status): Use mapped string value for display
                    if self._has_flags and numeric_value is not None:
                        # For flags: Use numeric value as state (for bitwise operations in templates)
                        # Store formatted string (from flags) in attributes for display
                        self._attr_native_value = numeric_value
                        formatted_string = (
                            str(processed_value)
                            if isinstance(processed_value, str)
                            else processed_value
                        )
                        self._attr_extra_state_attributes = {
                            **self._attr_extra_state_attributes,
                            "raw_value": raw_value if raw_value is not None else "N/A",
                            "processed_value": processed_value,
                            "formatted_value": formatted_string,
                        }
                    elif self._has_map_or_options:
                        # For map/options: Use mapped string value as state
                        # This allows templates to check for string values like "no cable"
                        self._attr_native_value = (
                            str(processed_value)
                            if not isinstance(processed_value, str)
                            else processed_value
                        )
                        # Store numeric value in attributes for reference
                        if numeric_value is not None:
                            self._attr_extra_state_attributes = {
                                **self._attr_extra_state_attributes,
                                "raw_value": (
                                    raw_value if raw_value is not None else "N/A"
                                ),
                                "processed_value": processed_value,
                                "numeric_value": numeric_value,
                            }
                        else:
                            self._attr_extra_state_attributes = {
                                **self._attr_extra_state_attributes,
                                "raw_value": (
                                    raw_value if raw_value is not None else "N/A"
                                ),
                                "processed_value": processed_value,
                            }
                    elif self.is_string_sensor:
                        # For string sensors, always return string
                        self._attr_native_value = str(processed_value)
                        self._attr_extra_state_attributes = {
                            **self._attr_extra_state_attributes,
                            "raw_value": raw_value if raw_value is not None else "N/A",
                            "processed_value": processed_value,
                        }
                    else:
                        # Use the processed value directly (no mapping)
                        self._attr_native_value = processed_value
                        self._attr_extra_state_attributes = {
                            **self._attr_extra_state_attributes,
                            "raw_value": raw_value if raw_value is not None else "N/A",
                            "processed_value": processed_value,
                        }

                else:
                    self._attr_native_value = None
            else:
                self._attr_native_value = None

            # Notify Home Assistant about the change
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Error updating sensor %s: %s", self._attr_name, str(e))
            self._attr_native_value = None

    @property
    def should_poll(self) -> bool:
        """Return False - coordinator handles updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return is_coordinator_connected(self.coordinator) and super().available

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # CoordinatorEntity already handles listener registration, but we can add custom logic here if needed


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Modbus Sensors from a config entry."""
    try:
        # Get coordinator from hass.data
        if entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("No coordinator data found for entry %s", entry.entry_id)
            return

        coordinator_data = hass.data[DOMAIN][entry.entry_id]
        coordinator = coordinator_data.get("coordinator")

        if not coordinator:
            _LOGGER.error("No coordinator found for entry %s", entry.entry_id)
            return

        # Get regular sensors with addresses
        regular_sensors = await coordinator._collect_all_registers()
        regular_sensors = [
            reg for reg in regular_sensors if reg.get("type") == "sensor"
        ]

        # Get calculated entities separately
        calculated_sensors = await coordinator._collect_calculated_registers()
        calculated_sensors = [
            reg
            for reg in calculated_sensors
            if reg.get("type") in ["calculated", "sensor"]
        ]

        if not regular_sensors and not calculated_sensors:
            _LOGGER.warning("No sensors found in coordinator registers")
            return

        # All config entries should have devices array after migration
        devices = entry.data.get("devices")
        if not devices or not isinstance(devices, list):
            _LOGGER.error(
                "Config entry missing devices array. Please re-run the config flow to migrate."
            )
            return

        hub_config = entry.data.get("hub", {})
        host = hub_config.get("host") or entry.data.get("host", "unknown")
        port = hub_config.get("port") or entry.data.get("port", 502)

        coordinator_sensors = []
        calculated_entities = []

        # NEW STRUCTURE: device_info is already in register configs from coordinator

        # Create coordinator sensors (device_info already attached by coordinator)
        registry = entity_registry.async_get(hass)
        for sensor_config in regular_sensors:
            try:
                unique_id = sensor_config.get("unique_id")

                # Check if entity with same unique_id already exists from another integration
                entity_id = f"sensor.{unique_id}"
                existing_entity = registry.async_get(entity_id)

                if (
                    existing_entity
                    and existing_entity.config_entry_id != entry.entry_id
                ):
                    # Migrate entity to this config entry
                    _LOGGER.info(
                        "Migrating entity %s from %s to Modbus Manager",
                        entity_id,
                        existing_entity.config_entry_id,
                    )
                    registry.async_update_entity(
                        entity_id,
                        new_config_entry_id=entry.entry_id,
                    )

                # device_info is already in sensor_config from coordinator
                device_info = sensor_config.get("device_info")
                if not device_info:
                    _LOGGER.error(
                        "Sensor %s missing device_info. Coordinator should provide this.",
                        sensor_config.get("name"),
                    )
                    continue

                coordinator_sensor = ModbusCoordinatorSensor(
                    coordinator=coordinator,
                    register_config=sensor_config,
                    device_info=device_info,
                )

                coordinator.async_add_listener(
                    coordinator_sensor._handle_coordinator_update
                )

                coordinator_sensors.append(coordinator_sensor)

            except Exception as e:
                _LOGGER.error(
                    "Error creating coordinator sensor for %s: %s",
                    sensor_config.get("name", "unknown"),
                    str(e),
                )

        # Create calculated sensors (device_info already attached by coordinator)
        for calc_config in calculated_sensors:
            try:
                from .calculated import ModbusCalculatedSensor

                # Extract device info from calc_config
                device_info = calc_config.get("device_info", {})
                # Extract prefix from unique_id (format: PREFIX_sensor_name)
                unique_id = calc_config.get("unique_id", "")

                # Check if entity with same unique_id already exists from another integration
                entity_id = f"sensor.{unique_id}"
                existing_entity = registry.async_get(entity_id)

                if (
                    existing_entity
                    and existing_entity.config_entry_id != entry.entry_id
                ):
                    # Migrate entity to this config entry
                    _LOGGER.info(
                        "Migrating calculated entity %s from %s to Modbus Manager",
                        entity_id,
                        existing_entity.config_entry_id,
                    )
                    registry.async_update_entity(
                        entity_id,
                        new_config_entry_id=entry.entry_id,
                    )

                device_prefix = (
                    unique_id.split("_")[0] if "_" in unique_id else "unknown"
                )

                # Template name is in device_info model field
                template_name = device_info.get("model", "unknown")

                entity = ModbusCalculatedSensor(
                    hass=hass,
                    config=calc_config,
                    prefix=None,
                    template_name=template_name,
                    host=host,
                    port=port,
                    slave_id=calc_config.get("slave_id", 1),
                    config_entry_id=entry.entry_id,
                    device_prefix=device_prefix,
                )
                calculated_entities.append(entity)

            except Exception as e:
                _LOGGER.error(
                    "Error creating calculated sensor %s: %s",
                    calc_config.get("name", "unknown"),
                    str(e),
                )

        # Add all entities
        all_entities = coordinator_sensors + calculated_entities
        async_add_entities(all_entities)

        # Handle group assignments after entities are added
        await _handle_group_assignments(hass, coordinator_sensors)

    except Exception as e:
        _LOGGER.error("Error setting up coordinator sensors: %s", str(e))
