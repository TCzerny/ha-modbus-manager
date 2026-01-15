"""Coordinator-based Select entity for Modbus Manager."""

from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import create_device_info_dict, generate_unique_id
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


class ModbusCoordinatorSelect(CoordinatorEntity, SelectEntity):
    """Coordinator-based Select entity."""

    def __init__(
        self,
        coordinator: ModbusCoordinator,
        register_config: dict[str, Any],
        device_info: dict[str, Any],
    ):
        """Initialize the coordinator select."""
        super().__init__(coordinator)
        self.register_config = register_config
        self._attr_device_info = DeviceInfo(**device_info)

        # Set entity properties from register config
        self._attr_has_entity_name = True
        self._attr_name = register_config.get("name", "Unknown Select")
        self._attr_unique_id = register_config.get("unique_id", "unknown")
        default_entity_id = register_config.get("default_entity_id")
        if default_entity_id:
            if "." in default_entity_id:
                self._attr_entity_id = default_entity_id
            else:
                self._attr_entity_id = f"select.{default_entity_id}"
        self._attr_icon = register_config.get("icon")

        # Selects should appear under device controls
        self._attr_entity_category = EntityCategory.CONFIG

        # Select-specific properties
        self._attr_options = list(register_config.get("options", {}).values())
        self._attr_current_option = None

        # Debug: Log options loading
        _LOGGER.debug(
            "Select %s: Loaded options %s",
            self._attr_name,
            register_config.get("options", {}),
        )

        # Store template parameters for extra_state_attributes
        self._scale = register_config.get("scale", 1.0)
        self._offset = register_config.get("offset", 0.0)
        self._precision = register_config.get("precision")
        self._group = register_config.get("group")
        self._scan_interval = register_config.get("scan_interval")
        self._input_type = register_config.get("input_type")
        self._data_type = register_config.get("data_type")

        # Store all mapping parameters
        self._options = register_config.get("options", {})
        self._map = register_config.get("map", {})
        self._flags = register_config.get("flags", {})

        # Minimize extra_state_attributes - only include static/essential attributes
        # options, map, flags are static configuration - keep them
        self._attr_extra_state_attributes = {
            "register_address": register_config.get("address"),
            "data_type": register_config.get("data_type"),
            "slave_id": register_config.get("slave_id"),
            "input_type": self._input_type,
            # Static configuration values
            "scale": self._scale,
            "offset": self._offset,
            "precision": self._precision,
            "group": self._group,
            "scan_interval": self._scan_interval,
            "swap": register_config.get("swap"),
            # Mapping configuration (static)
            "options": self._options,
            "map": self._map,
            "flags": self._flags,
        }

        # Create register key for data lookup (after prefix is added)
        self.register_key = self._create_register_key(register_config)

        _LOGGER.debug(
            "ModbusCoordinatorSelect created: %s (key: %s)",
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
                    # Apply mapping to convert numeric value to option name
                    mapped_value = self._apply_value_mapping(processed_value)
                    self._attr_current_option = str(mapped_value)

                    _LOGGER.debug(
                        "Select %s updated: %s -> %s",
                        self._attr_name,
                        processed_value,
                        mapped_value,
                    )
                else:
                    self._attr_current_option = None
                    _LOGGER.debug("Select %s: No processed value", self._attr_name)
            else:
                self._attr_current_option = None
                _LOGGER.debug("Select %s: No register data found", self._attr_name)

            # Notify Home Assistant about the change
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Error updating select %s: %s", self._attr_name, str(e))
            self._attr_current_option = None

    def _apply_value_mapping(self, value: Any) -> Any:
        """Apply value processing like map, flags, and options (same as legacy code)."""
        try:
            if value is None:
                return None

            _LOGGER.debug(
                "Select %s: Processing value %s (type: %s)",
                self._attr_name,
                value,
                type(value),
            )

            # Only process numeric values
            if isinstance(value, (int, float)):
                int_value = int(value)

                # 1. Apply map (if defined)
                if self._map:
                    if int_value in self._map:
                        mapped_value = self._map[int_value]
                        _LOGGER.debug(
                            "Mapped value %s to '%s' for %s",
                            int_value,
                            mapped_value,
                            self._attr_name,
                        )
                        return mapped_value
                    elif str(int_value) in self._map:
                        # Fallback: check string key
                        mapped_value = self._map[str(int_value)]
                        _LOGGER.debug(
                            "Mapped value %s (as string) to '%s' for %s",
                            int_value,
                            mapped_value,
                            self._attr_name,
                        )
                        return mapped_value
                    else:
                        _LOGGER.debug(
                            "Value %s not found in map for %s",
                            int_value,
                            self._attr_name,
                        )

                # 2. Apply flags (if defined)
                if self._flags:
                    flag_list = []
                    for bit, flag_name in self._flags.items():
                        if int_value & (1 << int(bit)):
                            flag_list.append(flag_name)

                    if flag_list:
                        _LOGGER.debug(
                            "Extracted flags from %s: %s", int_value, flag_list
                        )
                        return ", ".join(flag_list)

                # 3. Apply options (if defined)
                if self._options:
                    if int_value in self._options:
                        option_value = self._options[int_value]
                        _LOGGER.debug(
                            "Found option for %s: '%s'", int_value, option_value
                        )
                        return option_value
                    elif str(int_value) in self._options:
                        option_value = self._options[str(int_value)]
                        _LOGGER.debug(
                            "Found option for %s: '%s'", int_value, option_value
                        )
                        return option_value
                    else:
                        _LOGGER.debug(
                            "Value %s not found in options for %s",
                            int_value,
                            self._attr_name,
                        )

            # No processing applied - return original value
            _LOGGER.debug(
                "No value processing applied for %s, returning original value: %s",
                self._attr_name,
                value,
            )
            return value

        except Exception as e:
            _LOGGER.error(
                "Error in value processing for %s: %s", self._attr_name, str(e)
            )
            return value

    def _find_numeric_value_for_option(self, option: str) -> Optional[int]:
        """Find the numeric value for a given option name."""
        try:
            # 1. Check map (highest priority)
            if self._map:
                for key, value in self._map.items():
                    if value == option:
                        # Convert hex strings to integers
                        if isinstance(key, str) and key.startswith("0x"):
                            try:
                                return int(key, 16)
                            except ValueError:
                                return int(key)
                        else:
                            return int(key)

            # 2. Check flags (if no map)
            if self._flags:
                for bit, flag_name in self._flags.items():
                    if flag_name == option:
                        return 1 << int(bit)

            # 3. Check options (if no map and no flags)
            if self._options:
                for key, value in self._options.items():
                    if value == option:
                        # Convert hex strings to integers
                        if isinstance(key, str) and key.startswith("0x"):
                            try:
                                return int(key, 16)
                            except ValueError:
                                return int(key)
                        else:
                            return int(key)

            return None

        except Exception as e:
            _LOGGER.error(
                "Error finding numeric value for option %s: %s", option, str(e)
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            # Get register configuration
            address = self.register_config.get("address")
            slave_id = self.register_config.get("slave_id", 1)
            options = self.register_config.get("options", {})

            # Find the numeric value for the selected option
            numeric_value = self._find_numeric_value_for_option(option)

            if numeric_value is None:
                _LOGGER.error(
                    "Option %s not found in mapping for %s", option, self._attr_name
                )
                return

            _LOGGER.debug(
                "Writing select %s: option=%s, numeric_value=%d",
                self._attr_name,
                option,
                numeric_value,
            )

            # Write to Modbus register
            from .modbus_utils import get_write_call_type

            # Check for custom write function code
            write_function_code = self.register_config.get("write_function_code")
            count = self.register_config.get("count", 1) or 1

            call_type = get_write_call_type(count, write_function_code)

            if write_function_code:
                _LOGGER.debug(
                    "Using custom write function code %d for register %d",
                    write_function_code,
                    address,
                )

            result = await self.coordinator.hub.async_pb_call(
                slave_id,
                address,
                numeric_value,
                call_type,
            )

            if result:
                _LOGGER.debug("Successfully set %s to %s", self._attr_name, option)
                # Trigger coordinator update to refresh all entities
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set %s to %s", self._attr_name, option)

        except Exception as e:
            _LOGGER.error(
                "Error setting select %s to %s: %s", self._attr_name, option, str(e)
            )

    @property
    def should_poll(self) -> bool:
        """Return False - coordinator handles updates."""
        return False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # CoordinatorEntity already handles listener registration, but we can add custom logic here if needed


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up coordinator-based selects."""
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

        # Get select controls from coordinator
        select_controls = await coordinator._collect_all_registers()
        select_controls = [
            reg for reg in select_controls if reg.get("type") == "select"
        ]

        # Filter by firmware version if specified
        firmware_version = entry.data.get("firmware_version")
        if firmware_version:
            from .coordinator import filter_by_firmware_version

            select_controls = filter_by_firmware_version(
                select_controls, firmware_version
            )

        if not select_controls:
            _LOGGER.debug("No select controls found in coordinator registers")
            return

        # Create coordinator selects (device_info provided by coordinator)
        coordinator_selects = []
        for control_config in select_controls:
            try:
                # Ensure options are properly loaded
                if "options" not in control_config:
                    _LOGGER.warning(
                        "Select entity %s has no options defined",
                        control_config.get("name", "unknown"),
                    )
                    continue

                # Get device info from control_config (provided by coordinator)
                device_info = control_config.get("device_info")
                if not device_info:
                    _LOGGER.error(
                        "Select control %s missing device_info. Please re-run the config flow to migrate.",
                        control_config.get("name", "unknown"),
                    )
                    continue

                coordinator_select = ModbusCoordinatorSelect(
                    coordinator=coordinator,
                    register_config=control_config,
                    device_info=device_info,
                )

                # Register the select with the coordinator for updates
                coordinator.async_add_listener(
                    coordinator_select._handle_coordinator_update
                )

                coordinator_selects.append(coordinator_select)

            except Exception as e:
                _LOGGER.error(
                    "Error creating coordinator select for %s: %s",
                    control_config.get("name", "unknown"),
                    str(e),
                )

        _LOGGER.debug(
            "Created %d coordinator selects",
            len(coordinator_selects),
        )

        async_add_entities(coordinator_selects)

    except Exception as e:
        _LOGGER.error("Error setting up coordinator selects: %s", str(e))
