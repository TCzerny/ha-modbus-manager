"""Simplified sensor entity using ModbusCoordinator."""

from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import create_device_info_dict, generate_unique_id
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

                    _LOGGER.debug(
                        "Assigned sensor %s to group %s",
                        sensor._attr_name,
                        sensor._group,
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
        self._attr_name = register_config.get("name", "Unknown Sensor")
        self._attr_unique_id = register_config.get("unique_id", "unknown")
        self._attr_native_unit_of_measurement = register_config.get(
            "unit_of_measurement", ""
        )
        self._attr_device_class = register_config.get("device_class")
        self._attr_state_class = register_config.get("state_class")

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

        self._attr_extra_state_attributes = {
            "register_address": register_config.get("address"),
            "data_type": register_config.get("data_type"),
            "slave_id": register_config.get("slave_id"),
            "coordinator_mode": True,
            "scale": self._scale,
            "offset": self._offset,
            "precision": self._precision,
            "group": self._group,
            "scan_interval": self._scan_interval,
            "input_type": self._input_type,
            "unit_of_measurement": register_config.get("unit_of_measurement"),
            "device_class": register_config.get("device_class"),
            "state_class": register_config.get("state_class"),
            "swap": register_config.get("swap"),
        }

        self._attr_icon = register_config.get("icon")

        # Create register key for data lookup
        self.register_key = self._create_register_key(register_config)

        _LOGGER.debug(
            "ModbusCoordinatorSensor created: %s (key: %s, string_sensor: %s)",
            self._attr_name,
            self.register_key,
            self.is_string_sensor,
        )

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

                    _LOGGER.debug(
                        "Sensor %s updated: raw=%s, processed=%s (type: %s, scale: %s, precision: %s)",
                        self._attr_name,
                        raw_value,
                        processed_value,
                        type(processed_value).__name__,
                        self._scale,
                        self._precision,
                    )
                else:
                    self._attr_native_value = None
                    _LOGGER.debug("Sensor %s: No processed value", self._attr_name)
            else:
                self._attr_native_value = None
                _LOGGER.debug("Sensor %s: No register data found", self._attr_name)

            # Notify Home Assistant about the change
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Error updating sensor %s: %s", self._attr_name, str(e))
            self._attr_native_value = None

    @property
    def should_poll(self) -> bool:
        """Return False - coordinator handles updates."""
        return False


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

        # Check if we have devices array structure
        devices = entry.data.get("devices")
        hub_config = entry.data.get("hub", {})
        host = hub_config.get("host") or entry.data.get("host", "unknown")
        port = hub_config.get("port") or entry.data.get("port", 502)

        coordinator_sensors = []
        calculated_entities = []

        if devices and isinstance(devices, list):
            # NEW STRUCTURE: device_info is already in register configs from coordinator
            _LOGGER.debug(
                "Using devices array structure with coordinator-provided device_info"
            )

            # Create coordinator sensors (device_info already attached by coordinator)
            for sensor_config in regular_sensors:
                try:
                    _LOGGER.debug(
                        "Creating sensor: name=%s, unique_id=%s",
                        sensor_config.get("name"),
                        sensor_config.get("unique_id"),
                    )

                    # device_info is already in sensor_config from coordinator
                    device_info = sensor_config.get("device_info")
                    if not device_info:
                        _LOGGER.warning(
                            "Sensor %s missing device_info from coordinator",
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

        else:
            # LEGACY STRUCTURE: Single device from top-level config
            _LOGGER.debug("Using legacy single-device structure")

            prefix = entry.data.get("prefix", "unknown")
            template_name = entry.data.get("template", "unknown")
            slave_id = entry.data.get("slave_id", 1)

            device_info = create_device_info_dict(
                hass=hass,
                host=host,
                port=port,
                slave_id=slave_id,
                prefix=prefix,
                template_name=template_name,
                config_entry_id=entry.entry_id,
            )

            # Create coordinator sensors (regular sensors with addresses)
            for sensor_config in regular_sensors:
                try:
                    _LOGGER.debug(
                        "Creating sensor: name=%s, unique_id=%s",
                        sensor_config.get("name"),
                        sensor_config.get("unique_id"),
                    )

                    if "slave_id" not in sensor_config:
                        sensor_config["slave_id"] = entry.data.get("slave_id", 1)

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

            # Create calculated sensors for legacy structure
            for calc_config in calculated_sensors:
                try:
                    from .calculated import ModbusCalculatedSensor

                    entity = ModbusCalculatedSensor(
                        hass=hass,
                        config=calc_config,
                        prefix=None,
                        template_name=template_name,
                        host=host,
                        port=port,
                        slave_id=calc_config.get("slave_id", slave_id),
                        config_entry_id=entry.entry_id,
                        device_prefix=prefix,
                    )
                    calculated_entities.append(entity)

                except Exception as e:
                    _LOGGER.error(
                        "Error creating calculated sensor %s: %s",
                        calc_config.get("name", "unknown"),
                        str(e),
                    )

        _LOGGER.debug(
            "Created %d coordinator sensors and %d calculated sensors",
            len(coordinator_sensors),
            len(calculated_entities),
        )

        # Add all entities
        all_entities = coordinator_sensors + calculated_entities
        async_add_entities(all_entities)

        # Handle group assignments after entities are added
        await _handle_group_assignments(hass, coordinator_sensors)

    except Exception as e:
        _LOGGER.error("Error setting up coordinator sensors: %s", str(e))
