"""Modbus Manager Coordinator Button Platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
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
    """Set up Modbus Manager coordinator button entities from a config entry."""
    coordinator: ModbusCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Get all processed registers from coordinator
    registers = await coordinator._collect_all_registers()

    # Filter for button controls
    button_controls = [reg for reg in registers if reg.get("type") == "button"]

    entities = []

    for register_config in button_controls:
        try:
            entity = ModbusCoordinatorButton(coordinator, register_config)
            entities.append(entity)
            _LOGGER.debug(
                "ModbusCoordinatorButton created: %s (key: %s)",
                entity.name,
                entity._register_key,
            )
        except Exception as e:
            _LOGGER.error(
                "Error creating button entity %s: %s",
                register_config.get("name", "unknown"),
                str(e),
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.debug("Created %d coordinator button entities", len(entities))
    else:
        _LOGGER.info("No coordinator button entities created")


class ModbusCoordinatorButton(ButtonEntity):
    """Representation of a Modbus Coordinator Button Entity."""

    def __init__(self, coordinator: ModbusCoordinator, register_config: dict[str, Any]):
        """Initialize the coordinator button entity."""
        self._coordinator = coordinator
        self._register_config = register_config

        # Extract basic properties
        self._name = register_config.get("name", "Unknown Button")
        self._unique_id = register_config.get("unique_id")
        self._address = register_config.get("address", 0)
        self._input_type = register_config.get("input_type", "holding")
        self._data_type = register_config.get("data_type", "uint16")
        self._scan_interval = register_config.get("scan_interval", 30)

        # Button-specific properties
        self._button_press_value = register_config.get("button_press_value", 1)
        self._button_press_duration = register_config.get("button_press_duration", 0)

        # Create register key for coordinator lookup
        self._register_key = f"{self._unique_id}_{self._address}"

        # Set entity properties
        self._attr_name = self._name
        self._attr_unique_id = self._unique_id

        # Get device info from register_config (provided by coordinator)
        device_info = register_config.get("device_info")
        if not device_info:
            _LOGGER.error(
                "Button %s missing device_info. Please re-run the config flow to migrate.",
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
            "button_press_value": self._button_press_value,
            "button_press_duration": self._button_press_duration,
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
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._coordinator.last_update_success

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            # Write the button press value to the register
            if self._input_type == "holding":
                await self._coordinator._hub.write_register(
                    self._address,
                    self._button_press_value,
                    self._coordinator._entry.data.get("slave_id", 1),
                )
                _LOGGER.debug(
                    "Button pressed: wrote value %d to register %d",
                    self._button_press_value,
                    self._address,
                )

                # If there's a duration specified, reset the value after that time
                if self._button_press_duration > 0:
                    import asyncio

                    await asyncio.sleep(self._button_press_duration)
                    await self._coordinator._hub.write_register(
                        self._address,
                        0,  # Reset to 0
                        self._coordinator._entry.data.get("slave_id", 1),
                    )
                    _LOGGER.debug(
                        "Button reset: wrote value 0 to register %d after %d seconds",
                        self._address,
                        self._button_press_duration,
                    )
            else:
                _LOGGER.warning("Cannot write to read-only register %d", self._address)

        except Exception as e:
            _LOGGER.error("Error pressing button %s: %s", self._name, str(e))

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
