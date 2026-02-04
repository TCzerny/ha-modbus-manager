"""Coordinator-based Number entity for Modbus Manager."""

from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import (
    create_base_extra_state_attributes,
    generate_entity_id,
    is_coordinator_connected,
)
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


class ModbusCoordinatorNumber(CoordinatorEntity, NumberEntity):
    """Coordinator-based Number entity."""

    def _coerce_numeric(self, value: Any, default: float, field_name: str) -> float:
        """Coerce config values to float with a safe fallback."""
        if value is None:
            return float(default)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Invalid %s value for number entity %s: %r. Using default %s.",
                    field_name,
                    self._attr_unique_id,
                    value,
                    default,
                )
                return float(default)
        _LOGGER.warning(
            "Unexpected %s type for number entity %s: %r. Using default %s.",
            field_name,
            self._attr_unique_id,
            value,
            default,
        )
        return float(default)

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
        # unique_id is already processed by coordinator with prefix via _process_entities_with_prefix
        self._attr_has_entity_name = True
        self._attr_name = register_config.get("name", "Unknown Number")
        self._attr_unique_id = register_config.get("unique_id", "unknown")
        default_entity_id = register_config.get("default_entity_id")
        if default_entity_id:
            if isinstance(default_entity_id, str):
                default_entity_id = default_entity_id.lower()
            if "." in default_entity_id:
                self._attr_entity_id = default_entity_id
            else:
                self._attr_entity_id = f"number.{default_entity_id}"
        self._attr_native_unit_of_measurement = register_config.get(
            "unit_of_measurement", ""
        )
        self._attr_device_class = register_config.get("device_class")
        self._attr_icon = register_config.get("icon")

        # Numbers allow changing device configuration - ALWAYS CONFIG category
        # Controls (switches, numbers, selects, buttons, text) should NEVER be DIAGNOSTIC
        self._attr_entity_category = EntityCategory.CONFIG

        # Number-specific properties
        raw_min_value = register_config.get("min_value", 0)
        raw_max_value = register_config.get("max_value", 100)
        self._attr_native_min_value = self._coerce_numeric(
            raw_min_value, 0, "min_value"
        )
        self._attr_native_max_value = self._coerce_numeric(
            raw_max_value, 100, "max_value"
        )
        self._attr_native_step = register_config.get("step", 1)
        self._attr_native_value = None

        # Set mode (slider or box) - defaults to box for precise input
        mode_str = register_config.get("mode", "box").lower()
        if mode_str == "slider":
            self._attr_mode = NumberMode.SLIDER
        else:
            self._attr_mode = NumberMode.BOX

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

        # Minimize extra_state_attributes - only include static/essential attributes
        self._attr_extra_state_attributes = create_base_extra_state_attributes(
            unique_id=self._attr_unique_id,
            register_config=register_config,
            scan_interval=self._scan_interval,
            additional_attributes={
                "min_value": self._attr_native_min_value,
                "max_value": self._attr_native_max_value,
                "step": self._attr_native_step,
            },
        )

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
                # Extract raw and processed values for attributes
                raw_value = register_data.get("raw_value")
                processed_value = register_data.get("processed_value")
                numeric_value = register_data.get("numeric_value")

                if processed_value is not None:
                    # Convert to float for number entities
                    try:
                        self._attr_native_value = float(processed_value)
                    except (ValueError, TypeError):
                        self._attr_native_value = None

                    # Update extra_state_attributes with raw/processed/numeric values
                    self._attr_extra_state_attributes = {
                        **self._attr_extra_state_attributes,
                        "raw_value": raw_value if raw_value is not None else "N/A",
                        "processed_value": processed_value,
                    }
                    if numeric_value is not None:
                        self._attr_extra_state_attributes[
                            "numeric_value"
                        ] = numeric_value

                else:
                    self._attr_native_value = None
            else:
                self._attr_native_value = None

            # Notify Home Assistant about the change
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Error updating number %s: %s", self._attr_name, str(e))
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        try:
            # Safety check: Validate battery power limits against battery capacity
            unique_id = self.register_config.get("unique_id", "")
            if "battery_max" in unique_id.lower() and "power" in unique_id.lower():
                # Try to get battery capacity from coordinator's hass state
                try:
                    from homeassistant.core import State
                    from homeassistant.helpers import entity_registry as er

                    # Get device identifier to find battery capacity sensor
                    device_id = self._attr_device_info.get("identifiers")
                    if device_id:
                        # Find battery capacity sensor for this device
                        entity_registry = er.async_get(self.coordinator.hass)
                        device_entities = er.async_entries_for_device(
                            entity_registry, list(device_id)[0][1]
                        )

                        battery_capacity_entity = None
                        for entity in device_entities:
                            if (
                                entity.unique_id
                                and "battery_capacity" in entity.unique_id.lower()
                            ):
                                battery_capacity_entity = entity.entity_id
                                break

                        if battery_capacity_entity:
                            battery_capacity_state = self.coordinator.hass.states.get(
                                battery_capacity_entity
                            )
                            if (
                                battery_capacity_state
                                and battery_capacity_state.state
                                not in ["unknown", "unavailable", None]
                            ):
                                try:
                                    battery_capacity_kwh = float(
                                        battery_capacity_state.state
                                    )
                                    # Calculate safe limit: 0.5C rate for charging, 1C for discharging
                                    if "charge" in unique_id.lower():
                                        max_safe_power_kw = (
                                            battery_capacity_kwh * 0.5
                                        )  # 0.5C charging rate
                                    else:  # discharging
                                        max_safe_power_kw = (
                                            battery_capacity_kwh * 1.0
                                        )  # 1C discharging rate

                                    # Convert to same unit as value (W or kW)
                                    if self._attr_native_unit_of_measurement == "kW":
                                        max_safe_power = max_safe_power_kw
                                    else:  # W
                                        max_safe_power = max_safe_power_kw * 1000

                                    if value > max_safe_power:
                                        _LOGGER.warning(
                                            "⚠️ SAFETY WARNING: Attempted to set %s to %.1f %s, but battery capacity (%.2f kWh) limits safe maximum to %.1f %s (0.5C/1C rate). Value will be limited.",
                                            self._attr_name,
                                            value,
                                            self._attr_native_unit_of_measurement,
                                            battery_capacity_kwh,
                                            max_safe_power,
                                            self._attr_native_unit_of_measurement,
                                        )
                                        value = min(value, max_safe_power)
                                except (ValueError, TypeError):
                                    # Ignore if battery capacity cannot be parsed
                                    _LOGGER.debug(
                                        "Could not parse battery capacity for %s",
                                        self._attr_name,
                                    )
                except Exception as e:
                    # Ignore any errors when trying to validate battery power limits
                    _LOGGER.debug(
                        "Error validating battery power limits for %s: %s",
                        self._attr_name,
                        str(e),
                    )

            # Get register configuration
            address = self.register_config.get("address")
            slave_id = self.register_config.get("slave_id", 1)
            data_type = self.register_config.get("data_type", "uint16")

            # Convert value based on scaling
            # Use scale if available, otherwise fall back to multiplier
            # scale and multiplier are inverse operations:
            # - Reading: display_value = raw_value * scale
            # - Writing: raw_value = display_value / scale
            scale = self.register_config.get("scale")
            multiplier = self.register_config.get("multiplier")

            # Use scale if available, otherwise use multiplier (default: 1.0)
            if scale is not None:
                scale_factor = scale
            elif multiplier is not None:
                scale_factor = multiplier
            else:
                scale_factor = 1.0

            offset = self.register_config.get("offset", 0.0)
            raw_value = int((value - offset) / scale_factor)

            # Write to Modbus register
            from .modbus_utils import get_write_call_type

            # Check for custom write function code
            write_function_code = self.register_config.get("write_function_code")
            count = self.register_config.get("count", 1) or 1

            call_type = get_write_call_type(count, write_function_code)

            result = await self.coordinator.hub.async_pb_call(
                slave_id,
                address,
                raw_value,
                call_type,
            )

            if result:
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
            return

        # Create coordinator numbers (device_info provided by coordinator)
        coordinator_numbers = []
        for control_config in number_controls:
            try:
                # Get device info from control_config (provided by coordinator)
                device_info = control_config.get("device_info")
                if not device_info:
                    _LOGGER.error(
                        "Number control %s missing device_info. Coordinator should provide this.",
                        control_config.get("name", "unknown"),
                    )
                    continue

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

        async_add_entities(coordinator_numbers)

    except Exception as e:
        _LOGGER.error("Error setting up coordinator numbers: %s", str(e))
