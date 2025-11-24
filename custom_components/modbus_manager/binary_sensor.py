"""Modbus Manager Coordinator Binary Sensor Platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import create_device_info_dict, generate_entity_id
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Modbus Manager coordinator binary sensors from a config entry."""
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

        # Get binary sensors from coordinator - use calculated registers collection
        all_calculated_registers = await coordinator._collect_calculated_registers()
        binary_sensor_configs = [
            reg
            for reg in all_calculated_registers
            if reg.get("type") == "binary_sensor"
        ]

        if not binary_sensor_configs:
            _LOGGER.debug("No binary sensor configs found in coordinator registers")
            return

        # Check if we have devices array structure
        devices = entry.data.get("devices")
        hub_config = entry.data.get("hub", {})
        host = hub_config.get("host") or entry.data.get("host", "unknown")
        port = hub_config.get("port") or entry.data.get("port", 502)

        entities = []

        if devices and isinstance(devices, list):
            # NEW STRUCTURE: Separate template-based and register-based binary sensors
            _LOGGER.info(
                "Using devices array structure with coordinator-provided device_info"
            )

            for config in binary_sensor_configs:
                try:
                    # Check if this is a template-based binary_sensor (has 'state' template, no 'address')
                    # or a register-based binary_sensor (has 'address')
                    has_state_template = config.get("state") is not None
                    has_address = (
                        config.get("address") is not None and config.get("address") > 0
                    )

                    if has_state_template and not has_address:
                        # Template-based binary sensor - use ModbusCalculatedBinarySensor
                        from .calculated import ModbusCalculatedBinarySensor

                        device_info = config.get("device_info", {})
                        unique_id = config.get("unique_id", "")
                        device_prefix = (
                            unique_id.split("_")[0] if "_" in unique_id else "unknown"
                        )

                        template_name = device_info.get("model", "unknown")

                        entity = ModbusCalculatedBinarySensor(
                            hass=hass,
                            config=config,
                            prefix=None,  # Already processed by coordinator
                            template_name=template_name,
                            host=host,
                            port=port,
                            slave_id=config.get("slave_id", 1),
                            config_entry_id=entry.entry_id,
                            device_prefix=device_prefix,
                        )
                        entities.append(entity)
                        _LOGGER.debug(
                            "Created calculated binary sensor: %s", config.get("name")
                        )

                    elif has_address:
                        # Register-based binary sensor - use ModbusCoordinatorBinarySensor
                        device_info = config.get("device_info")
                        if not device_info:
                            _LOGGER.warning(
                                "Binary sensor %s missing device_info from coordinator",
                                config.get("name"),
                            )
                            continue

                        entity = ModbusCoordinatorBinarySensor(
                            coordinator=coordinator,
                            register_config=config,
                            device_info=device_info,
                        )
                        entities.append(entity)
                        _LOGGER.debug(
                            "Created coordinator binary sensor: %s", config.get("name")
                        )

                    else:
                        _LOGGER.warning(
                            "Binary sensor %s has neither state template nor address, skipping",
                            config.get("name"),
                        )

                except Exception as e:
                    _LOGGER.error(
                        "Error creating binary sensor %s: %s",
                        config.get("name", "unknown"),
                        str(e),
                    )

        else:
            # LEGACY STRUCTURE: Single device from top-level config
            _LOGGER.info("Using legacy single-device structure")

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

            for config in binary_sensor_configs:
                try:
                    has_state_template = config.get("state") is not None
                    has_address = (
                        config.get("address") is not None and config.get("address") > 0
                    )

                    if has_state_template and not has_address:
                        # Template-based binary sensor
                        from .calculated import ModbusCalculatedBinarySensor

                        entity = ModbusCalculatedBinarySensor(
                            hass=hass,
                            config=config,
                            prefix=prefix,
                            template_name=template_name,
                            host=host,
                            port=port,
                            slave_id=config.get("slave_id", slave_id),
                            config_entry_id=entry.entry_id,
                            device_prefix=prefix,
                        )
                        entities.append(entity)
                    elif has_address:
                        # Register-based binary sensor
                        entity = ModbusCoordinatorBinarySensor(
                            coordinator=coordinator,
                            register_config=config,
                            device_info=device_info,
                        )
                        entities.append(entity)

                except Exception as e:
                    _LOGGER.error(
                        "Error creating binary sensor %s: %s",
                        config.get("name", "unknown"),
                        str(e),
                    )

        if entities:
            async_add_entities(entities)
            _LOGGER.debug("Created %d binary sensors", len(entities))
        else:
            _LOGGER.info("No binary sensors created")

    except Exception as e:
        _LOGGER.error("Error setting up coordinator binary sensors: %s", str(e))


class ModbusCoordinatorBinarySensor(BinarySensorEntity):
    """Representation of a Modbus Coordinator Binary Sensor."""

    def __init__(
        self,
        coordinator: ModbusCoordinator,
        register_config: dict[str, Any],
        device_info: dict[str, Any],
    ):
        """Initialize the coordinator binary sensor."""
        self._coordinator = coordinator
        self._register_config = register_config
        self._attr_device_info = DeviceInfo(**device_info)

        # Extract basic properties (already processed by coordinator)
        self._name = register_config.get("name", "Unknown Binary Sensor")
        self._unique_id = register_config.get("unique_id")
        self._address = register_config.get("address", 0)
        self._input_type = register_config.get("input_type", "holding")
        self._data_type = register_config.get("data_type", "uint16")
        self._scan_interval = register_config.get("scan_interval", 30)

        # Create register key for coordinator lookup
        self._register_key = f"{self._unique_id}_{self._address}"

        # Set entity properties
        self._attr_name = self._name
        self._attr_unique_id = generate_entity_id("binary_sensor", self._unique_id)

        # Set extra state attributes
        self._attr_extra_state_attributes = {
            "address": self._address,
            "input_type": self._input_type,
            "data_type": self._data_type,
            "scan_interval": self._scan_interval,
            "register_key": self._register_key,
            "template_name": coordinator.entry.data.get("template", "unknown"),
            "prefix": coordinator.entry.data.get("prefix", "modbus"),
            "host": coordinator.entry.data.get("host", "unknown"),
            "port": coordinator.entry.data.get("port", 502),
            "slave_id": coordinator.entry.data.get("slave_id", 1),
        }

        # Add template-specific attributes if present
        if "scale" in register_config:
            self._attr_extra_state_attributes["scale"] = register_config["scale"]
        if "offset" in register_config:
            self._attr_extra_state_attributes["offset"] = register_config["offset"]
        if "precision" in register_config:
            self._attr_extra_state_attributes["precision"] = register_config[
                "precision"
            ]
        if "unit_of_measurement" in register_config:
            self._attr_extra_state_attributes["unit_of_measurement"] = register_config[
                "unit_of_measurement"
            ]
        if "device_class" in register_config:
            self._attr_extra_state_attributes["device_class"] = register_config[
                "device_class"
            ]
        if "state_class" in register_config:
            self._attr_extra_state_attributes["state_class"] = register_config[
                "state_class"
            ]
        if "group" in register_config:
            self._attr_extra_state_attributes["group"] = register_config["group"]
        if "map" in register_config:
            self._attr_extra_state_attributes["map"] = register_config["map"]
        if "flags" in register_config:
            self._attr_extra_state_attributes["flags"] = register_config["flags"]
        if "options" in register_config:
            self._attr_extra_state_attributes["options"] = register_config["options"]
        if "swap" in register_config:
            self._attr_extra_state_attributes["swap"] = register_config["swap"]

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if not self._coordinator.data:
            return None

        register_data = self._coordinator.data.get(self._register_key)
        if register_data is None:
            return None

        # Extract the processed value
        processed_value = register_data.get("processed_value")
        if processed_value is None:
            return None

        # Convert to boolean based on data type and value
        if isinstance(processed_value, bool):
            return processed_value
        elif isinstance(processed_value, (int, float)):
            # For numeric values, consider 0 as False, anything else as True
            return bool(processed_value)
        elif isinstance(processed_value, str):
            # For string values, consider empty string as False, anything else as True
            return bool(processed_value.strip())
        else:
            return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
