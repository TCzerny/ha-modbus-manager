"""Modbus Manager Coordinator Switch Platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Modbus Manager coordinator switches from a config entry."""
    coordinator: ModbusCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Get switches from coordinator
    switch_controls = await coordinator._collect_calculated_registers()
    switch_controls = [reg for reg in switch_controls if reg.get("type") == "switch"]

    entities = []

    for register_config in switch_controls:
        try:
            entity = ModbusCoordinatorSwitch(coordinator, register_config)
            entities.append(entity)
            _LOGGER.debug(
                "ModbusCoordinatorSwitch created: %s (key: %s)",
                entity.name,
                entity._register_key,
            )
        except Exception as e:
            _LOGGER.error(
                "Error creating switch %s: %s",
                register_config.get("name", "unknown"),
                str(e),
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Created %d coordinator switches", len(entities))
    else:
        _LOGGER.info("No coordinator switches created")


class ModbusCoordinatorSwitch(SwitchEntity):
    """Representation of a Modbus Coordinator Switch."""

    def __init__(self, coordinator: ModbusCoordinator, register_config: dict[str, Any]):
        """Initialize the coordinator switch."""
        self._coordinator = coordinator
        self._register_config = register_config

        # Extract basic properties
        self._name = register_config.get("name", "Unknown Switch")
        self._unique_id = register_config.get("unique_id")
        self._address = register_config.get("address", 0)
        self._input_type = register_config.get("input_type", "holding")
        self._data_type = register_config.get("data_type", "uint16")
        self._scan_interval = register_config.get("scan_interval", 30)

        # Create register key for coordinator lookup
        self._register_key = f"{self._unique_id}_{self._address}"

        # Set entity properties
        self._attr_name = self._name
        self._attr_unique_id = self._unique_id

        # Get device info from register_config (provided by coordinator)
        device_info = register_config.get("device_info")
        if device_info:
            self._attr_device_info = DeviceInfo(**device_info)
        else:
            # Fallback for legacy mode
            prefix = coordinator.entry.data.get("prefix", "unknown")
            template_name = coordinator.entry.data.get("template", "unknown")
            host = coordinator.entry.data.get("host", "unknown")
            port = coordinator.entry.data.get("port", 502)
            slave_id = coordinator.entry.data.get("slave_id", 1)

            device_info = create_device_info_dict(
                hass=coordinator.hass,
                host=host,
                port=port,
                slave_id=slave_id,
                prefix=prefix,
                template_name=template_name,
                config_entry_id=coordinator.entry.entry_id,
            )
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
        """Return the state of the switch."""
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            # Get the write value from register config
            write_value = self._register_config.get("write_value", 1)

            # Write to Modbus register
            await self._write_register(write_value)

        except Exception as e:
            _LOGGER.error("Error turning on switch %s: %s", self._name, str(e))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            # Get the write value from register config
            write_value = self._register_config.get("write_value_off", 0)

            # Write to Modbus register
            await self._write_register(write_value)

        except Exception as e:
            _LOGGER.error("Error turning off switch %s: %s", self._name, str(e))

    async def _write_register(self, value: int) -> None:
        """Write value to Modbus register."""
        try:
            from homeassistant.components.modbus.const import (
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_REGISTER_INPUT,
            )

            # Determine register type
            register_type = self._register_config.get("input_type", "holding")
            call_type = (
                CALL_TYPE_REGISTER_INPUT
                if register_type == "input"
                else CALL_TYPE_REGISTER_HOLDING
            )

            # Get slave ID
            slave_id = self._register_config.get("slave_id", 1)

            # Write to register
            await self._coordinator.hub.async_pb_call(
                slave_id,
                self._address,
                value,
                call_type,
            )

            _LOGGER.debug(
                "Wrote value %d to register %d (slave_id: %d)",
                value,
                self._address,
                slave_id,
            )

        except Exception as e:
            _LOGGER.error(
                "Error writing to register %d: %s",
                self._address,
                str(e),
            )
            raise

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
