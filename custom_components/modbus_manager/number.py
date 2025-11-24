"""Coordinator-based Number entity for Modbus Manager."""

from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import create_device_info_dict, generate_entity_id
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


class ModbusCoordinatorNumber(CoordinatorEntity, NumberEntity):
    """Coordinator-based Number entity."""

    def __init__(
        self,
        coordinator: ModbusCoordinator,
        register_config: dict[str, Any],
        device_info: dict[str, Any],
    ):
        """Initialize the coordinator number."""
        super().__init__(coordinator)
        self.register_config = register_config
        self._attr_device_info = DeviceInfo(**device_info)

        # Set entity properties from register config
        self._attr_name = register_config.get("name", "Unknown Number")
        self._attr_unique_id = register_config.get("unique_id", "unknown")
        self._attr_native_unit_of_measurement = register_config.get(
            "unit_of_measurement", ""
        )
        self._attr_device_class = register_config.get("device_class")
        self._attr_icon = register_config.get("icon")

        # Number-specific properties
        self._attr_native_min_value = register_config.get("min_value", 0)
        self._attr_native_max_value = register_config.get("max_value", 100)
        self._attr_native_step = register_config.get("step", 1)
        self._attr_native_value = None

        # Store template parameters for extra_state_attributes
        self._scale = register_config.get("scale", 1.0)
        self._offset = register_config.get("offset", 0.0)
        self._precision = register_config.get("precision")
        self._group = register_config.get("group")
        self._scan_interval = register_config.get("scan_interval")
        self._input_type = register_config.get("input_type")
        self._data_type = register_config.get("data_type")

        # Set suggested_display_precision for Home Assistant UI
        if self._precision is not None:
            self._attr_suggested_display_precision = self._precision

        # Set extra_state_attributes
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
            "min_value": self._attr_native_min_value,
            "max_value": self._attr_native_max_value,
            "step": self._attr_native_step,
        }

        # Create register key for data lookup
        self.register_key = self._create_register_key(register_config)

        _LOGGER.debug(
            "ModbusCoordinatorNumber created: %s (key: %s)",
            self._attr_name,
            self.register_key,
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
                # Extract processed value
                processed_value = register_data.get("processed_value")

                if processed_value is not None:
                    # Convert to float for number entities
                    try:
                        self._attr_native_value = float(processed_value)
                    except (ValueError, TypeError):
                        self._attr_native_value = None

                    _LOGGER.debug(
                        "Number %s updated: %s",
                        self._attr_name,
                        self._attr_native_value,
                    )
                else:
                    self._attr_native_value = None
                    _LOGGER.debug("Number %s: No processed value", self._attr_name)
            else:
                self._attr_native_value = None
                _LOGGER.debug("Number %s: No register data found", self._attr_name)

            # Notify Home Assistant about the change
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Error updating number %s: %s", self._attr_name, str(e))
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        try:
            # Get register configuration
            address = self.register_config.get("address")
            slave_id = self.register_config.get("slave_id", 1)
            data_type = self.register_config.get("data_type", "uint16")

            # Convert value based on scaling
            multiplier = self.register_config.get("multiplier", 1.0)
            offset = self.register_config.get("offset", 0.0)
            raw_value = int((value - offset) / multiplier)

            # Write to Modbus register
            from homeassistant.components.modbus.const import CALL_TYPE_WRITE_REGISTERS

            result = await self.coordinator.hub.async_pb_call(
                slave_id,
                address,
                raw_value,
                CALL_TYPE_WRITE_REGISTERS,
            )

            if result:
                _LOGGER.info("Successfully set %s to %s", self._attr_name, value)
                # Trigger coordinator update to refresh all entities
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set %s to %s", self._attr_name, value)

        except Exception as e:
            _LOGGER.error(
                "Error setting number %s to %s: %s", self._attr_name, value, str(e)
            )

    @property
    def should_poll(self) -> bool:
        """Return False - coordinator handles updates."""
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "register_address": self.register_config.get("address"),
            "data_type": self.register_config.get("data_type"),
            "slave_id": self.register_config.get("slave_id"),
            "coordinator_mode": True,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up coordinator-based numbers."""
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

        # Get number controls from coordinator
        number_controls = await coordinator._collect_all_registers()
        number_controls = [
            reg for reg in number_controls if reg.get("type") == "number"
        ]

        # Filter by firmware version if specified
        firmware_version = entry.data.get("firmware_version")
        if firmware_version:
            from .coordinator import filter_by_firmware_version

            number_controls = filter_by_firmware_version(
                number_controls, firmware_version
            )

        if not number_controls:
            _LOGGER.debug("No number controls found in coordinator registers")
            return

        # Create coordinator numbers (device_info provided by coordinator)
        coordinator_numbers = []
        for control_config in number_controls:
            try:
                # Get device info from control_config (provided by coordinator)
                device_info = control_config.get("device_info")
                if not device_info:
                    # Fallback for legacy mode
                    prefix = entry.data.get("prefix", "unknown")
                    template_name = entry.data.get("template", "unknown")
                    host = entry.data.get("host", "unknown")
                    port = entry.data.get("port", 502)
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

                coordinator_number = ModbusCoordinatorNumber(
                    coordinator=coordinator,
                    register_config=control_config,
                    device_info=device_info,
                )

                # Register the number with the coordinator for updates
                coordinator.async_add_listener(
                    coordinator_number._handle_coordinator_update
                )

                coordinator_numbers.append(coordinator_number)

            except Exception as e:
                _LOGGER.error(
                    "Error creating coordinator number for %s: %s",
                    control_config.get("name", "unknown"),
                    str(e),
                )

        _LOGGER.info(
            "Created %d coordinator numbers",
            len(coordinator_numbers),
        )

        async_add_entities(coordinator_numbers)

    except Exception as e:
        _LOGGER.error("Error setting up coordinator numbers: %s", str(e))
