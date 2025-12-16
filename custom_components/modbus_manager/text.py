"""Modbus Manager Coordinator Text Platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import create_device_info_dict
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Modbus Manager coordinator text entities from a config entry."""
    coordinator: ModbusCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Get all processed registers from coordinator
    registers = await coordinator._collect_all_registers()

    # Filter for text controls
    text_controls = [reg for reg in registers if reg.get("type") == "text"]

    entities = []

    for register_config in text_controls:
        try:
            entity = ModbusCoordinatorText(coordinator, register_config)
            entities.append(entity)
            _LOGGER.debug(
                "ModbusCoordinatorText created: %s (key: %s)",
                entity.name,
                entity._register_key,
            )
        except Exception as e:
            _LOGGER.error(
                "Error creating text entity %s: %s",
                register_config.get("name", "unknown"),
                str(e),
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.debug("Created %d coordinator text entities", len(entities))
    else:
        _LOGGER.info("No coordinator text entities created")


class ModbusCoordinatorText(TextEntity):
    """Representation of a Modbus Coordinator Text Entity."""

    def __init__(self, coordinator: ModbusCoordinator, register_config: dict[str, Any]):
        """Initialize the coordinator text entity."""
        self._coordinator = coordinator
        self._register_config = register_config

        # Extract basic properties
        self._name = register_config.get("name", "Unknown Text Entity")
        self._unique_id = register_config.get("unique_id")
        self._address = register_config.get("address", 0)
        self._input_type = register_config.get("input_type", "holding")
        self._data_type = register_config.get("data_type", "string")
        self._scan_interval = register_config.get("scan_interval", 30)

        # Text-specific properties
        self._min_length = register_config.get("min_length", 0)
        self._max_length = register_config.get("max_length", 255)
        self._pattern = register_config.get("pattern", None)
        self._mode = register_config.get("mode", "text")

        # Create register key for coordinator lookup
        self._register_key = f"{self._unique_id}_{self._address}"

        # Set entity properties
        self._attr_name = self._name
        self._attr_unique_id = self._unique_id

        # Set text entity properties
        self._attr_native_min = self._min_length
        self._attr_native_max = self._max_length
        self._attr_pattern = self._pattern
        self._attr_mode = self._mode

        # Get device info from register_config (provided by coordinator)
        device_info = register_config.get("device_info")
        if not device_info:
            _LOGGER.error(
                "Text entity %s missing device_info. Please re-run the config flow to migrate.",
                self._name,
            )
            # Create minimal device info to prevent errors
            device_info = {
                "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
                "name": "Modbus Device",
            }
        self._attr_device_info = DeviceInfo(**device_info)

        # Set extra state attributes
        self._attr_extra_state_attributes = {
            "address": self._address,
            "input_type": self._input_type,
            "data_type": self._data_type,
            "scan_interval": self._scan_interval,
            "register_key": self._register_key,
            "template_name": coordinator.entry.data.get("template", "unknown"),
            "prefix": coordinator.entry.data.get("prefix", "unknown"),
            "host": coordinator.entry.data.get("host", "unknown"),
            "port": coordinator.entry.data.get("port", 502),
            "slave_id": coordinator.entry.data.get("slave_id", 1),
            "min_length": self._min_length,
            "max_length": self._max_length,
            "pattern": self._pattern,
            "mode": self._mode,
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
    def native_value(self) -> str | None:
        """Return the current value of the text entity."""
        if not self._coordinator.data:
            return None

        register_data = self._coordinator.data.get(self._register_key)
        if register_data is None:
            return None

        # Extract the processed value
        processed_value = register_data.get("processed_value")
        if processed_value is None:
            return None

        # Convert to string
        if isinstance(processed_value, str):
            return processed_value
        else:
            return str(processed_value)

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._coordinator.last_update_success

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        # For text entities, we typically write to holding registers
        if self._input_type == "holding":
            try:
                # Convert string to appropriate format for Modbus write
                # This is a simplified implementation - in practice you might need
                # more sophisticated string-to-register conversion
                await self._coordinator._hub.write_register(
                    self._address,
                    value.encode("utf-8"),
                    self._coordinator._entry.data.get("slave_id", 1),
                )
                _LOGGER.debug(
                    "Text value written to register %d: %s", self._address, value
                )
            except Exception as e:
                _LOGGER.error(
                    "Error writing text value to register %d: %s", self._address, str(e)
                )
        else:
            _LOGGER.warning("Cannot write to read-only register %d", self._address)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
