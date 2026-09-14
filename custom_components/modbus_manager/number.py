"""Coordinator-based Number entity for Modbus Manager."""

from __future__ import annotations

import asyncio
import math
from typing import Any, Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import (
    create_base_extra_state_attributes,
    get_entity_mm_group,
    is_coordinator_connected,
    is_register_dependency_met,
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
                self.entity_id = default_entity_id
            else:
                self.entity_id = f"number.{default_entity_id}"

        # Write each update to the state machine, even if the data is the same.
        self._attr_force_update = register_config.get("force_update", False)
        self._attr_native_unit_of_measurement = register_config.get(
            "unit_of_measurement", ""
        )
        self._attr_device_class = register_config.get("device_class")
        self._attr_icon = register_config.get("icon")

        # Set entity category:
        # - None (default): Primary sensors that represent main data points.
        # - diagnostic: Used for read-only information about the device’s health or status.
        # - config: Used for entities that change how a device behaves.
        # An entity with a category will:
        # - Not be exposed to cloud, Alexa, or Google Assistant components.
        # - Not be included in indirect service calls to devices or areas.
        entity_category_str = register_config.get("entity_category")
        if entity_category_str == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category_str == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = None

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

        # Register dependency: Check if this entity depends on another register value
        # Format: {"register_unique_id": "reactive_power_adjustment_mode", "required_value": 0xA1}
        self._register_dependency = register_config.get("depends_on_register")

        # Dynamic max/min from register: Value is read from another register at runtime
        # Format: "{PREFIX}_battery_charge_discharge_limit" or "battery_charge_discharge_limit" (substring match)
        # Dict: {"register_unique_id": "{PREFIX}_...", "fallback": 100} - {PREFIX} replaced in coordinator
        self._max_value_from_register = register_config.get("max_value_from_register")
        self._min_value_from_register = register_config.get("min_value_from_register")
        max_cfg = self._max_value_from_register
        min_cfg = self._min_value_from_register
        self._fallback_max_value = self._attr_native_max_value
        self._fallback_min_value = self._attr_native_min_value
        if isinstance(max_cfg, dict) and "fallback" in max_cfg:
            try:
                self._fallback_max_value = float(max_cfg["fallback"])
            except (ValueError, TypeError):
                pass
        if isinstance(min_cfg, dict) and "fallback" in min_cfg:
            try:
                self._fallback_min_value = float(min_cfg["fallback"])
            except (ValueError, TypeError):
                pass

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
        self._mm_group = get_entity_mm_group(register_config)
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
        # True when the last write/read-back (or a None processed value) missed.
        # Ignore coordinator last-good until a newer timestamp arrives.
        self._register_value_missing = False
        self._stale_before_ts: float | None = None

    def _create_register_key(self, register_config: dict[str, Any]) -> str:
        """Create unique key for register data lookup."""
        return f"{register_config.get('unique_id', 'unknown')}_{register_config.get('address', 0)}"

    def _get_value_from_referenced_register(
        self, config: str | dict[str, Any]
    ) -> Optional[float]:
        """Get processed value from a register referenced by unique_id.

        config: Either a string (unique_id, use {PREFIX}_xxx in template for clarity)
                or dict with register_unique_id, fallback. {PREFIX} is replaced in coordinator.
        Returns the processed_value (display value with scale) or None if unavailable.
        Matching is case-insensitive to handle PREFIX formatting differences.
        """
        if not config:
            return None
        if isinstance(config, str):
            register_unique_id = config
            fallback = None
        elif isinstance(config, dict):
            register_unique_id = config.get("register_unique_id")
            fallback = config.get("fallback")
            if not register_unique_id:
                return None
        else:
            return None

        register_data_source = self.coordinator.register_data
        if not register_data_source:
            return fallback

        # Match case-insensitively (PREFIX may be lowercased in template, keys use original case)
        register_unique_id_lower = register_unique_id.lower()
        for register_key, data in register_data_source.items():
            if register_unique_id_lower in register_key.lower():
                processed_value = data.get("processed_value")
                if processed_value is not None:
                    try:
                        return float(processed_value)
                    except (ValueError, TypeError):
                        pass
                break
        return fallback

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
                    data_ts = register_data.get("timestamp")
                    if (
                        self._register_value_missing
                        and self._stale_before_ts is not None
                        and (data_ts is None or data_ts <= self._stale_before_ts)
                    ):
                        self._attr_native_value = None
                    else:
                        try:
                            self._attr_native_value = float(processed_value)
                            self._register_value_missing = False
                            self._stale_before_ts = None
                        except (ValueError, TypeError):
                            self._attr_native_value = None
                            self._register_value_missing = True

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
                    self._register_value_missing = True
            elif not self._register_value_missing:
                self._attr_native_value = None

            # Update dynamic max_value from referenced register (e.g. battery limit)
            if self._max_value_from_register:
                dynamic_max = self._get_value_from_referenced_register(
                    self._max_value_from_register
                )
                if dynamic_max is not None and dynamic_max > 0:
                    self._attr_native_max_value = self._coerce_numeric(
                        dynamic_max, self._fallback_max_value, "max_value_from_register"
                    )
                    self._attr_extra_state_attributes = {
                        **self._attr_extra_state_attributes,
                        "max_value": self._attr_native_max_value,
                    }
                elif self._attr_native_max_value != self._fallback_max_value:
                    # Revert to fallback when source unavailable
                    self._attr_native_max_value = self._fallback_max_value

            # Update dynamic min_value from referenced register
            if self._min_value_from_register:
                dynamic_min = self._get_value_from_referenced_register(
                    self._min_value_from_register
                )
                if dynamic_min is not None:
                    self._attr_native_min_value = self._coerce_numeric(
                        dynamic_min, self._fallback_min_value, "min_value_from_register"
                    )
                    self._attr_extra_state_attributes = {
                        **self._attr_extra_state_attributes,
                        "min_value": self._attr_native_min_value,
                    }
                elif self._attr_native_min_value != self._fallback_min_value:
                    self._attr_native_min_value = self._fallback_min_value

            # Notify Home Assistant about the change
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Error updating number %s: %s", self._attr_name, str(e))
            self._attr_native_value = None
            self._register_value_missing = True

    def _display_values_match(self, requested: float, actual: float) -> bool:
        """Compare display units after a write, allowing one scale/step tick."""
        try:
            requested_f = float(requested)
            actual_f = float(actual)
        except (TypeError, ValueError):
            return False
        abs_tol = abs(float(self._scale or 0)) or 1e-6
        step = self._attr_native_step
        if step is not None:
            try:
                abs_tol = max(abs_tol, abs(float(step)))
            except (TypeError, ValueError):
                pass
        return math.isclose(requested_f, actual_f, rel_tol=0.0, abs_tol=abs_tol + 1e-9)

    def _mark_register_unavailable(self) -> None:
        """Stop showing last-good when the live register cannot be trusted."""
        self._register_value_missing = True
        try:
            self._stale_before_ts = asyncio.get_running_loop().time()
        except RuntimeError:
            self._stale_before_ts = None
        self._attr_native_value = None
        if self.hass is not None:
            self.async_write_ha_state()

    def _write_error(
        self, translation_key: str, placeholders: dict[str, str]
    ) -> HomeAssistantError:
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )

    async def async_set_native_value(self, value: float) -> None:
        """Write the number and confirm the device accepted it."""
        name = str(self.name or self._attr_unique_id)
        requested = float(value)
        failed_placeholders = {"name": name, "value": str(requested)}
        try:
            address = self.register_config.get("address")
            slave_id = self.register_config.get("slave_id", 1)

            # Convert value based on scaling
            # Use scale if available, otherwise fall back to multiplier
            # scale and multiplier are inverse operations:
            # - Reading: display_value = raw_value * scale
            # - Writing: raw_value = display_value / scale
            scale = self.register_config.get("scale")
            multiplier = self.register_config.get("multiplier")

            if scale is not None:
                scale_factor = scale
            elif multiplier is not None:
                scale_factor = multiplier
            else:
                scale_factor = 1.0

            offset = self.register_config.get("offset", 0.0)
            scaled_value = (requested - offset) / scale_factor

            from .modbus_utils import encode_register_write_value, get_write_call_type

            write_value, count = encode_register_write_value(
                scaled_value, self.register_config
            )
            write_function_code = self.register_config.get("write_function_code")
            call_type = get_write_call_type(count, write_function_code)

            before = self.coordinator.get_register_data(self.register_key)
            before_ts = (before or {}).get("timestamp")

            result = await self.coordinator.async_pb_write(
                slave_id,
                address,
                write_value,
                call_type,
            )

            if not result:
                _LOGGER.error("Failed to set %s to %s", name, requested)
                self._mark_register_unavailable()
                raise self._write_error("number_write_failed", failed_placeholders)

            after = self.coordinator.get_register_data(self.register_key)
            after_ts = (after or {}).get("timestamp")
            actual = (after or {}).get("processed_value")
            if after is None or after_ts == before_ts or actual is None:
                _LOGGER.error(
                    "Wrote %s to %s but could not read the register back",
                    name,
                    requested,
                )
                self._mark_register_unavailable()
                raise self._write_error(
                    "number_write_verify_unread", failed_placeholders
                )

            try:
                actual_f = float(actual)
            except (TypeError, ValueError):
                self._mark_register_unavailable()
                raise self._write_error(
                    "number_write_verify_unread", failed_placeholders
                ) from None

            if not self._display_values_match(requested, actual_f):
                _LOGGER.error(
                    "Device rejected %s write: requested %s, register is %s",
                    name,
                    requested,
                    actual_f,
                )
                raise self._write_error(
                    "number_write_verify_mismatch",
                    {
                        "name": name,
                        "requested": str(requested),
                        "actual": str(actual_f),
                    },
                )

        except HomeAssistantError:
            raise
        except Exception as err:
            _LOGGER.error(
                "Error setting number %s to %s: %s", name, requested, str(err)
            )
            self._mark_register_unavailable()
            raise self._write_error("number_write_failed", failed_placeholders) from err

    @property
    def should_poll(self) -> bool:
        """Return False - coordinator handles updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        if self._register_value_missing:
            return False
        if not is_coordinator_connected(self.coordinator) or not super().available:
            return False
        return is_register_dependency_met(
            self.coordinator.data, self._register_dependency
        )

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

        # Get all entities from coordinator (structured dict)
        entities_dict = await coordinator._collect_all_registers()

        # Get controls and filter for number type
        controls = entities_dict.get("controls", [])
        number_controls = [c for c in controls if c.get("type") == "number"]

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
        entities_by_subentry: dict[str | None, list] = {}
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
                # CoordinatorEntity auto-registers _handle_coordinator_update in async_added_to_hass

                subentry_id = control_config.get("config_subentry_id")
                entities_by_subentry.setdefault(subentry_id, []).append(
                    coordinator_number
                )

            except Exception as e:
                _LOGGER.error(
                    "Error creating coordinator number for %s: %s",
                    control_config.get("name", "unknown"),
                    str(e),
                )

        for subentry_id, entities in entities_by_subentry.items():
            if not entities:
                continue
            if subentry_id:
                async_add_entities(entities, config_subentry_id=subentry_id)
            else:
                async_add_entities(entities)

    except Exception as e:
        _LOGGER.error("Error setting up coordinator numbers: %s", str(e))
