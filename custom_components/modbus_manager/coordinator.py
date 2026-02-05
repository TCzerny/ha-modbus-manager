"""Modbus Coordinator for centralized data management."""

from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .device_utils import (
    create_device_info_dict,
    generate_unique_id,
    replace_template_placeholders,
)
from .logger import ModbusManagerLogger
from .performance_monitor import PerformanceMonitor
from .register_optimizer import RegisterOptimizer
from .sunspec_utils import (
    calculate_sunspec_register_address,
    detect_sunspec_model_addresses,
)
from .template_loader import _evaluate_condition, get_template_by_name
from .value_processor import process_register_value

_LOGGER = ModbusManagerLogger(__name__)


def filter_by_firmware_version(entities: list, firmware_version: str) -> list:
    """Filter entities based on firmware version requirements.

    This function filters entities based on firmware version requirements.
    Entities with firmware_min_version that is higher than the current firmware
    version will be excluded.

    Args:
        entities: List of entities to filter
        firmware_version: Current firmware version string

    Returns:
        Filtered list of entities
    """
    try:
        from packaging import version

        filtered_entities = []
        for entity in entities:
            firmware_min_version = entity.get("firmware_min_version")
            if firmware_min_version:
                try:
                    # Compare firmware versions
                    current_ver = version.parse(firmware_version)
                    min_ver = version.parse(firmware_min_version)
                    if current_ver < min_ver:
                        _LOGGER.debug(
                            "Excluding entity due to firmware version: %s (requires: %s, current: %s)",
                            entity.get("name", "unknown"),
                            firmware_min_version,
                            firmware_version,
                        )
                        continue
                except version.InvalidVersion:
                    # Fallback to string comparison for non-semantic versions
                    if firmware_version < firmware_min_version:
                        _LOGGER.debug(
                            "Excluding entity due to firmware version (string): %s (requires: %s, current: %s)",
                            entity.get("name", "unknown"),
                            firmware_min_version,
                            firmware_version,
                        )
                        continue

            filtered_entities.append(entity)

        return filtered_entities

    except Exception as e:
        _LOGGER.error("Error in firmware filtering: %s", str(e))
        return entities


class ModbusCoordinator(DataUpdateCoordinator):
    """Central coordinator for all Modbus data."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub,
        device_config: Dict[str, Any],
        entry: ConfigEntry,
    ):
        """Initialize the Modbus coordinator."""
        self.hub = hub
        self.device_config = device_config
        self.entry = entry
        self.register_data = {}
        self.template_processor = None
        self.register_optimizer = RegisterOptimizer()
        self.performance_monitor = PerformanceMonitor()

        # Cache for processed entities (loaded once at startup, reused on every update)
        # Structured dict: {"sensors": [...], "controls": [...], "calculated": [...], "binary_sensors": [...]}
        self._cached_entities = None
        self._cached_registers_by_interval = {}  # Register grouped by scan_interval
        self._cache_initialized = False

        # Track when each interval group was last updated
        self._last_update_time = {}

        # Connection retry state (avoid log spam)
        self._next_connect_attempt = 0.0
        self._connect_retry_interval = 60.0
        self._connect_failure_logged = False

        # Flag to indicate if coordinator is being unloaded
        self._is_unloading = False

        # Start with a short interval - will be adjusted after register analysis
        # Use 5 seconds as base to ensure we can update frequently
        update_interval = timedelta(seconds=5)

        super().__init__(
            hass,
            _LOGGER,
            name=f"Modbus Coordinator {entry.data.get('prefix', 'unknown')}",
            update_interval=update_interval,
        )

        _LOGGER.debug(
            "ModbusCoordinator initialized for %s with update interval %s",
            entry.data.get("prefix", "unknown"),
            update_interval,
        )

    def invalidate_cache(self):
        """Invalidate the entity cache (e.g., when template is reloaded)."""
        _LOGGER.info("Invalidating entity cache")
        self._cached_entities = None
        self._cached_registers_by_interval = {}
        self._last_update_time = {}
        self._cache_initialized = False

    def mark_as_unloading(self):
        """Mark coordinator as unloading to stop further updates."""
        _LOGGER.debug("Marking coordinator as unloading")
        self._is_unloading = True
        self.invalidate_cache()

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch register data with respect to individual scan intervals."""
        # Stop updates if coordinator is being unloaded
        if self._is_unloading:
            _LOGGER.debug("Coordinator is unloading, skipping update")
            return self.register_data

        operation_id = None
        try:
            # Ensure hub is connected (HA standard: UpdateFailed when offline)
            if not getattr(self.hub, "_is_connected", False):
                now = asyncio.get_event_loop().time()
                if now >= self._next_connect_attempt:
                    self._next_connect_attempt = now + self._connect_retry_interval
                    try:
                        connect_timeout = self.entry.data.get("timeout", 5)
                        await asyncio.wait_for(
                            self.hub.async_pb_connect(), timeout=connect_timeout
                        )
                        self.hub._is_connected = True
                        self._connect_failure_logged = False
                        _LOGGER.info("Modbus hub reconnected successfully")
                    except Exception as e:
                        if not self._connect_failure_logged:
                            _LOGGER.info(
                                "Modbus hub not connected; entities will be unavailable until reconnected"
                            )
                            self._connect_failure_logged = True
                        _LOGGER.debug("Failed to reconnect hub: %s", str(e))
                        raise UpdateFailed("Modbus hub not connected")
                else:
                    raise UpdateFailed("Modbus hub not connected")

            # Start performance monitoring
            operation_id = self.performance_monitor.start_operation(
                device_id=self.entry.data.get("prefix", "unknown"),
                operation_type="coordinator_update",
            )

            # 1. Group registers by scan_interval if not cached
            if not self._cached_registers_by_interval:
                entities_dict = await self._collect_all_registers()
                # Only use sensors and controls (they have addresses for Modbus reading)
                all_registers = entities_dict.get("sensors", []) + entities_dict.get(
                    "controls", []
                )
                if all_registers:
                    # Group registers by their scan_interval
                    self._cached_registers_by_interval = (
                        self._group_registers_by_interval(all_registers)
                    )

                    # Update coordinator to use the minimum interval
                    # Set coordinator to update every 1 second to catch all intervals
                    coordinator_interval = 5
                    self._update_coordinator_interval(coordinator_interval)

            # 2. Determine which registers need to be read based on their scan_interval
            registers_to_read = self._get_registers_due_for_update()

            # Update operation with register count
            total_registers = len(registers_to_read) if registers_to_read else 0
            device_id = self.entry.data.get("prefix", "unknown")
            device_metrics = self.performance_monitor.devices.get(device_id)
            if device_metrics and device_metrics.operations:
                # Update the last operation (the one we just started)
                for op in reversed(device_metrics.operations):
                    if op.end_time is None:  # Still running
                        op.register_count = total_registers
                        break

            if not registers_to_read:
                _LOGGER.debug("No registers due for update at this time")
                self.performance_monitor.end_operation(
                    device_id=self.entry.data.get("prefix", "unknown"),
                    operation_id=operation_id,
                    success=True,
                )
                return self.register_data

            # 3. Optimize reading (group consecutive registers)
            optimized_ranges = self.register_optimizer.optimize_registers(
                registers_to_read
            )

            # Calculate total bytes that will be transferred (2 bytes per register)
            total_bytes = sum(
                range_obj.register_count * 2 for range_obj in optimized_ranges
            )

            _LOGGER.debug(
                "Reading %d registers in %d optimized ranges",
                len(registers_to_read),
                len(optimized_ranges),
            )

            # 4. Read all data in minimal calls
            for range_obj in optimized_ranges:
                try:
                    data = await self._read_register_range(range_obj)
                    if data:
                        self._distribute_data(data, range_obj)
                except Exception as e:
                    _LOGGER.error(
                        "Error reading register range %d-%d: %s",
                        range_obj.start_address,
                        range_obj.end_address,
                        str(e),
                    )

            # 5. Update last_update_time for each interval
            current_time = asyncio.get_event_loop().time()
            for register in registers_to_read:
                interval = register.get("scan_interval", 30)
                self._last_update_time[interval] = current_time

            # 5.5. Update device firmware from register if available
            await self._update_device_firmware_from_register()

            # 6. Update performance metrics with optimization stats
            # Update the operation with optimization metrics before ending
            device_metrics = self.performance_monitor.devices.get(device_id)
            if device_metrics and device_metrics.operations:
                # Find the last operation that's still running
                for op in reversed(device_metrics.operations):
                    if op.end_time is None:  # Still running
                        op.bytes_transferred = total_bytes
                        op.optimized_ranges_count = len(optimized_ranges)
                        break

            self.performance_monitor.end_operation(
                device_id=device_id,
                operation_id=operation_id,
                success=True,
            )

            _LOGGER.debug(
                "Coordinator update completed. Data keys: %s",
                list(self.register_data.keys()),
            )

            return self.register_data

        except UpdateFailed:
            # UpdateFailed is handled by DataUpdateCoordinator; avoid extra log spam here
            if operation_id is not None:
                self.performance_monitor.end_operation(
                    device_id=self.entry.data.get("prefix", "unknown"),
                    operation_id=operation_id,
                    success=False,
                    error_message="update_failed",
                )
            raise
        except Exception as e:
            _LOGGER.error("Error in coordinator update: %s", str(e))
            if operation_id is not None:
                self.performance_monitor.end_operation(
                    device_id=self.entry.data.get("prefix", "unknown"),
                    operation_id=operation_id,
                    success=False,
                    error_message=str(e),
                )
            raise UpdateFailed(f"Error updating coordinator: {e}")

    async def _collect_all_registers(self) -> Dict[str, List[Dict[str, Any]]]:
        """Collect all entities using devices array structure.

        Returns a structured dict with entity categories:
        {
            "sensors": [...],           # type="sensor", address > 0
            "controls": [...],          # type in ["number", "select", "switch", "button", "text"], address > 0
            "calculated": [...],        # type="calculated", kein address
            "binary_sensors": [...]      # type="binary_sensor", kein address
        }
        """
        try:
            # Use cached entities if already initialized (massive performance improvement!)
            if self._cache_initialized and self._cached_entities is not None:
                total_entities = (
                    len(self._cached_entities.get("sensors", []))
                    + len(self._cached_entities.get("controls", []))
                    + len(self._cached_entities.get("calculated", []))
                    + len(self._cached_entities.get("binary_sensors", []))
                )
                _LOGGER.debug(
                    "Using cached entities (%d total entities)", total_entities
                )
                return self._cached_entities

            # First time or cache invalidated - load and process templates
            devices = self.entry.data.get("devices")

            if not devices or not isinstance(devices, list):
                # Convert legacy structure to devices array format
                if not self._cache_initialized:
                    _LOGGER.debug(
                        "Converting legacy configuration to devices array format"
                    )
                devices = self._convert_legacy_to_devices_array()
                if not devices:
                    _LOGGER.error("Failed to convert legacy configuration")
                    return {
                        "sensors": [],
                        "controls": [],
                        "calculated": [],
                        "binary_sensors": [],
                    }

            if not self._cache_initialized:
                _LOGGER.debug("Initializing entity cache for %d devices", len(devices))
            entities = await self._collect_registers_from_devices(devices)

            # Cache the results
            self._cached_entities = entities
            self._cache_initialized = True
            total_entities = (
                len(entities.get("sensors", []))
                + len(entities.get("controls", []))
                + len(entities.get("calculated", []))
                + len(entities.get("binary_sensors", []))
            )
            _LOGGER.debug(
                "Entity cache initialized with %d total entities (sensors: %d, controls: %d, calculated: %d, binary_sensors: %d)",
                total_entities,
                len(entities.get("sensors", [])),
                len(entities.get("controls", [])),
                len(entities.get("calculated", [])),
                len(entities.get("binary_sensors", [])),
            )

            return entities

        except Exception as e:
            _LOGGER.error("Error collecting entities: %s", str(e))
            return {
                "sensors": [],
                "controls": [],
                "calculated": [],
                "binary_sensors": [],
            }

    async def _collect_registers_from_devices(
        self, devices: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Collect registers from devices array structure.

        Returns a structured dict with entity categories:
        {
            "sensors": [...],           # type="sensor", address > 0
            "controls": [...],          # type in ["number", "select", "switch", "button", "text"], address > 0
            "calculated": [...],        # type="calculated", kein address
            "binary_sensors": [...]      # type="binary_sensor", kein address
        }
        """
        try:
            # Initialize structured entity collections
            all_sensors = []
            all_controls = []
            all_calculated = []
            all_binary_sensors = []

            # Check if there's an SBR Battery device in the devices array
            # This is needed for backward compatibility with existing configurations
            has_sbr_battery = False
            for device in devices:
                template_name = device.get("template", "").lower()
                device_type = device.get("type", "").lower()
                if (
                    "sbr" in template_name
                    or "battery" in template_name
                    or device_type == "battery"
                ):
                    has_sbr_battery = True
                    _LOGGER.debug(
                        "Found SBR Battery device: %s (type: %s)",
                        template_name,
                        device_type,
                    )
                    break

            device_count = len(devices)
            for device in devices:
                device_type = device.get("type", "inverter")
                template_name = device.get("template")
                prefix = device.get("prefix", "unknown")
                slave_id = device.get("slave_id", 1)
                selected_model = device.get("selected_model")
                if not selected_model and device_count == 1:
                    selected_model = self.entry.data.get("selected_model")
                    if selected_model:
                        _LOGGER.debug(
                            "Using selected_model from entry data for legacy device: %s",
                            selected_model,
                        )

                # Extract configuration from selected model if available
                model_config = await self._extract_config_from_model(
                    selected_model, template_name
                )

                if not template_name:
                    _LOGGER.warning(
                        "Device missing template name, skipping: %s", device
                    )
                    continue

                _LOGGER.debug(
                    "Processing device: %s (type: %s, prefix: %s, slave_id: %s, model: %s, fw: %s)",
                    template_name,
                    device_type,
                    prefix,
                    slave_id,
                    selected_model,
                    device.get("firmware_version", "unknown"),
                )

                # Load template
                template = await get_template_by_name(template_name)
                if not template:
                    _LOGGER.error("Template %s not found for device", template_name)
                    continue

                # Build dynamic_config dict dynamically from template's dynamic_config section
                # This automatically includes ALL fields defined in the template (e.g., dual_channel_meter)
                template_dynamic_config = template.get("dynamic_config", {})
                dynamic_config = {}

                # 1. Load all available field names from template's dynamic_config section
                for field_name in template_dynamic_config.keys():
                    # Skip internal fields that are not user-configurable
                    if field_name in [
                        "valid_models",
                        "firmware_version",
                        "connection_type",
                        "battery_slave_id",
                    ]:
                        continue

                    # 2. Check device config first (most specific)
                    if field_name in device:
                        dynamic_config[field_name] = device[field_name]
                    # 3. Check entry.data for backward compatibility
                    elif field_name in self.entry.data:
                        dynamic_config[field_name] = self.entry.data.get(field_name)
                    # 4. Use default from template if available
                    elif isinstance(template_dynamic_config[field_name], dict):
                        default_value = template_dynamic_config[field_name].get(
                            "default"
                        )
                        if default_value is not None:
                            dynamic_config[field_name] = default_value

                # Add model_config values (from valid_models)
                dynamic_config.update(model_config)
                if selected_model:
                    dynamic_config["selected_model"] = selected_model

                # Add explicitly handled fields that might not be in template's dynamic_config
                for key in ["battery_config", "connection_type", "firmware_version"]:
                    if key in device:
                        dynamic_config[key] = device[key]
                    elif key in self.entry.data:
                        dynamic_config[key] = self.entry.data.get(key)

                # Calculate battery_enabled from battery_config for condition filtering
                battery_config = dynamic_config.get("battery_config", "none")
                # If battery_config is not set but we have an SBR Battery device, enable battery
                if battery_config == "none" and has_sbr_battery:
                    battery_config = "sbr_battery"
                    dynamic_config["battery_config"] = "sbr_battery"
                    _LOGGER.debug(
                        "Auto-detected SBR Battery - setting battery_enabled=True for device %s",
                        template_name,
                    )
                dynamic_config["battery_enabled"] = battery_config != "none"

                _LOGGER.debug(
                    "Built dynamic_config for %s: %s",
                    template_name,
                    {
                        k: v
                        for k, v in dynamic_config.items()
                        if k not in ["valid_models"]
                    },
                )

                # Extract registers from template
                registers = template.get("sensors", [])
                controls = template.get("controls", [])
                calculated = template.get("calculated", [])
                binary_sensors = template.get("binary_sensors", [])

                # Apply firmware version filtering if specified (firmware_min_version parameter)
                firmware_version = device.get("firmware_version")
                if firmware_version:
                    registers = filter_by_firmware_version(registers, firmware_version)
                    controls = filter_by_firmware_version(controls, firmware_version)
                    calculated = filter_by_firmware_version(
                        calculated, firmware_version
                    )
                    binary_sensors = filter_by_firmware_version(
                        binary_sensors, firmware_version
                    )

                # Apply generic model-based filtering (phases, mppt_count)
                if model_config:
                    _LOGGER.debug(
                        "Applying model-based filtering for %s with config: %s",
                        template_name,
                        {k: v for k, v in model_config.items() if v is not None},
                    )
                    registers = self._filter_by_model_config(registers, model_config)
                    controls = self._filter_by_model_config(controls, model_config)
                    calculated = self._filter_by_model_config(calculated, model_config)
                    binary_sensors = self._filter_by_model_config(
                        binary_sensors, model_config
                    )

                # Apply condition-based filtering (e.g., dual_channel_meter == true)
                # Filter using dynamic_config (automatically includes all template fields)
                registers = self._filter_by_conditions(registers, dynamic_config)
                controls = self._filter_by_conditions(controls, dynamic_config)
                calculated = self._filter_by_conditions(calculated, dynamic_config)
                binary_sensors = self._filter_by_conditions(
                    binary_sensors, dynamic_config
                )

                # Calculate SunSpec addresses if template has SunSpec enabled
                sunspec_model_addresses = {}
                if template.get("sunspec_enabled"):
                    sunspec_models = template.get("sunspec_models", {})
                    if sunspec_models:
                        # Get user-provided SunSpec addresses from dynamic_config
                        user_sunspec_config = dynamic_config.get(
                            "sunspec_model_addresses", {}
                        )

                        # Determine input_type for SunSpec detection
                        # Check first register to determine if using input or holding registers
                        input_type = "holding"  # Default
                        if registers:
                            first_reg = registers[0]
                            reg_input_type = first_reg.get("input_type", "holding")
                            if reg_input_type == "input":
                                input_type = "input"

                        # Detect SunSpec model addresses
                        sunspec_model_addresses = await detect_sunspec_model_addresses(
                            hub=self.hub,
                            slave_id=slave_id,
                            sunspec_models=sunspec_models,
                            user_config=user_sunspec_config,
                            input_type=input_type,
                        )

                        _LOGGER.info(
                            "Detected SunSpec model addresses for %s: %s",
                            template_name,
                            sunspec_model_addresses,
                        )

                        # Calculate SunSpec addresses for registers
                        for reg in registers:
                            sunspec_model = reg.get("sunspec_model")
                            sunspec_offset = reg.get("sunspec_offset")

                            if sunspec_model is not None and sunspec_offset is not None:
                                # Get model start address
                                model_start_address = sunspec_model_addresses.get(
                                    sunspec_model
                                )
                                if model_start_address:
                                    # Calculate actual address
                                    calculated_address = (
                                        calculate_sunspec_register_address(
                                            base_address=model_start_address,
                                            sunspec_offset=sunspec_offset,
                                            register_address=reg.get("address"),
                                        )
                                    )
                                    reg["address"] = calculated_address
                                    _LOGGER.debug(
                                        "Calculated SunSpec address for %s: Model %d, offset %d -> address %d",
                                        reg.get("name", "unknown"),
                                        sunspec_model,
                                        sunspec_offset,
                                        calculated_address,
                                    )
                                else:
                                    _LOGGER.warning(
                                        "SunSpec Model %d not found for register %s, using fallback address %d",
                                        sunspec_model,
                                        reg.get("name", "unknown"),
                                        reg.get("address"),
                                    )

                # Process entities with device-specific prefix
                processed_registers = self._process_entities_with_prefix(
                    registers, prefix, template_name
                )
                processed_controls = self._process_entities_with_prefix(
                    controls, prefix, template_name
                )
                processed_calculated = self._process_entities_with_prefix(
                    calculated, prefix, template_name
                )
                processed_binary_sensors = self._process_entities_with_prefix(
                    binary_sensors, prefix, template_name
                )

                # Create device info dict for this device
                hub_config = self.entry.data.get("hub", {})
                host = hub_config.get("host") or self.entry.data.get("host", "unknown")
                port = hub_config.get("port") or self.entry.data.get("port", 502)

                # Get firmware version from device config (fallback to template default)
                device_firmware_version = firmware_version or template.get(
                    "firmware_version", "1.0.0"
                )

                device_info = create_device_info_dict(
                    hass=self.hass,
                    host=host,
                    port=port,
                    slave_id=slave_id,
                    prefix=prefix,
                    template_name=template_name,
                    firmware_version=device_firmware_version,
                    config_entry_id=self.entry.entry_id,
                )

                # Add type field, device info, and categorize entities
                # Sensors: registers with address > 0, type="sensor"
                for register in processed_registers:
                    register["type"] = "sensor"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    # Only add if it has a valid address (for Modbus reading)
                    if (
                        register.get("address") is not None
                        and register.get("address", 0) > 0
                    ):
                        all_sensors.append(register)

                # Controls: registers with address > 0, type in ["number", "select", "switch", "button", "text"]
                for register in processed_controls:
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    # Type field should come from template and never be changed
                    if "type" not in register:
                        _LOGGER.error(
                            "Control %s (unique_id: %s) missing type field from template. This is a template error.",
                            register.get("name", "unknown"),
                            register.get("unique_id", "unknown"),
                        )
                        continue  # Skip this control as it's invalid

                    # Replace placeholders in max_value/min_value using both model_config and dynamic_config
                    # Supports: {{max_charge_power}}, {{max_discharge_power}}, {{max_ac_output_power}}
                    # Also supports dynamic_config values: {{max_current}}, {{phases}}, etc.
                    # Also supports calculations: {{max_charge_power * 0.5}} or {{max_current * 2}}
                    max_value = register.get("max_value")
                    min_value = register.get("min_value")

                    # Combine model_config and dynamic_config for placeholder replacement
                    # model_config contains values from valid_models (e.g., max_charge_power)
                    # dynamic_config contains all dynamic config values (e.g., max_current, phases)
                    placeholder_values = {}
                    if model_config:
                        placeholder_values.update(model_config)
                    if dynamic_config:
                        # Only add numeric values from dynamic_config (skip strings, booleans, etc.)
                        for key, value in dynamic_config.items():
                            if isinstance(value, (int, float)):
                                placeholder_values[key] = value

                    # Process max_value if it contains placeholders
                    if (
                        max_value
                        and isinstance(max_value, str)
                        and "{{" in max_value
                        and "}}" in max_value
                    ):
                        try:
                            # Extract expression inside {{ }}
                            pattern = r"\{\{([^}]+)\}\}"
                            match = re.search(pattern, max_value)

                            if match:
                                expression = match.group(1).strip()
                                unit = register.get("unit_of_measurement", "").lower()

                                # Replace placeholder keys in expression
                                # e.g., "max_charge_power * 0.5" -> "10600 * 0.5"
                                # e.g., "max_current" -> "16"
                                processed_expression = expression
                                for key, value in placeholder_values.items():
                                    if isinstance(value, (int, float)):
                                        # Replace whole word matches only (to avoid partial replacements)
                                        processed_expression = re.sub(
                                            r"\b" + re.escape(key) + r"\b",
                                            str(value),
                                            processed_expression,
                                        )

                                # Evaluate expression safely (only math operations allowed)
                                # Use a restricted eval environment for safety
                                allowed_names = {
                                    "__builtins__": {},
                                    "abs": abs,
                                    "round": round,
                                    "int": int,
                                    "float": float,
                                    "min": min,
                                    "max": max,
                                }
                                result = eval(  # nosec B307
                                    processed_expression, allowed_names
                                )

                                # Convert to appropriate unit if needed
                                # Power values in model_config are in W, but controls might be in kW
                                if unit == "kw" and any(
                                    k in expression
                                    for k in [
                                        "max_charge_power",
                                        "max_discharge_power",
                                        "max_ac_output_power",
                                    ]
                                ):
                                    # If original value was in W, convert to kW
                                    register["max_value"] = float(result) / 1000.0
                                else:
                                    register["max_value"] = float(result)

                                # Determine source for logging
                                source = "dynamic_config"
                                if model_config and any(
                                    k in expression for k in model_config.keys()
                                ):
                                    source = "model_config"

                                _LOGGER.debug(
                                    "Replaced placeholder {{%s}} with %.1f %s for %s (from %s)",
                                    expression,
                                    register["max_value"],
                                    unit,
                                    register.get("name", "unknown"),
                                    source,
                                )
                        except Exception as e:
                            _LOGGER.warning(
                                "Error replacing placeholder {{%s}} in max_value for %s: %s",
                                max_value,
                                register.get("name", "unknown"),
                                str(e),
                            )

                    # Process min_value if it contains placeholders
                    if (
                        min_value
                        and isinstance(min_value, str)
                        and "{{" in min_value
                        and "}}" in min_value
                    ):
                        try:
                            # Extract expression inside {{ }}
                            pattern = r"\{\{([^}]+)\}\}"
                            match = re.search(pattern, min_value)

                            if match:
                                expression = match.group(1).strip()

                                # Replace placeholder keys in expression
                                processed_expression = expression
                                for key, value in placeholder_values.items():
                                    if isinstance(value, (int, float)):
                                        processed_expression = re.sub(
                                            r"\b" + re.escape(key) + r"\b",
                                            str(value),
                                            processed_expression,
                                        )

                                # Evaluate expression safely
                                allowed_names = {
                                    "__builtins__": {},
                                    "abs": abs,
                                    "round": round,
                                    "int": int,
                                    "float": float,
                                    "min": min,
                                    "max": max,
                                }
                                result = eval(  # nosec B307
                                    processed_expression, allowed_names
                                )
                                register["min_value"] = float(result)

                                _LOGGER.debug(
                                    "Replaced placeholder {{%s}} in min_value with %.1f for %s",
                                    expression,
                                    register["min_value"],
                                    register.get("name", "unknown"),
                                )
                        except Exception as e:
                            _LOGGER.warning(
                                "Error replacing placeholder {{%s}} in min_value for %s: %s",
                                min_value,
                                register.get("name", "unknown"),
                                str(e),
                            )

                    # Only add if it has a valid address (for Modbus reading)
                    if (
                        register.get("address") is not None
                        and register.get("address", 0) > 0
                    ):
                        all_controls.append(register)

                # Calculated: entities without address, type="calculated"
                for register in processed_calculated:
                    register["type"] = "calculated"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    # Replace placeholders in calculated entity templates (state, availability)
                    for field in ["state", "availability", "template"]:
                        if field in register and isinstance(register[field], str):
                            register[field] = replace_template_placeholders(
                                register[field], prefix, slave_id, 0
                            )
                    all_calculated.append(register)

                # Binary sensors: entities without address, type="binary_sensor"
                for register in processed_binary_sensors:
                    register["type"] = "binary_sensor"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    # Replace placeholders in binary sensor templates (state, availability)
                    for field in ["state", "availability", "template"]:
                        if field in register and isinstance(register[field], str):
                            register[field] = replace_template_placeholders(
                                register[field], prefix, slave_id, 0
                            )
                    all_binary_sensors.append(register)

                _LOGGER.debug(
                    "Added %d entities for device %s (sensors: %d, controls: %d, calculated: %d, binary_sensors: %d)",
                    len(processed_registers)
                    + len(processed_controls)
                    + len(processed_calculated)
                    + len(processed_binary_sensors),
                    template_name,
                    len(processed_registers),
                    len(processed_controls),
                    len(processed_calculated),
                    len(processed_binary_sensors),
                )

            # Return structured dict with all entity categories
            return {
                "sensors": all_sensors,
                "controls": all_controls,
                "calculated": all_calculated,
                "binary_sensors": all_binary_sensors,
            }

        except Exception as e:
            _LOGGER.error("Error collecting registers from devices: %s", str(e))
            return {
                "sensors": [],
                "controls": [],
                "calculated": [],
                "binary_sensors": [],
            }

    def _convert_legacy_to_devices_array(self) -> List[Dict[str, Any]]:
        """Convert legacy configuration structure to devices array format.

        This allows us to use the same processing logic for both old and new configs.
        """
        try:
            devices = []

            # Extract main device configuration
            prefix = self.entry.data.get("prefix", "unknown")
            template = self.entry.data.get("template")
            slave_id = self.entry.data.get("slave_id", 1)
            battery_template = self.entry.data.get("battery_template")
            battery_prefix = self.entry.data.get("battery_prefix", "SBR")
            battery_slave_id = self.entry.data.get("battery_slave_id", 200)

            # Add main device (inverter)
            if template:
                main_device = {
                    "prefix": prefix,
                    "template": template,
                    "slave_id": slave_id,
                    "type": "inverter",
                }

                # Add dynamic config fields if present
                for field in [
                    "phases",
                    "mppt_count",
                    "string_count",
                    "modules",
                    "firmware_version",
                    "connection_type",
                    "selected_model",
                    "dual_channel_meter",
                    "battery_config",
                ]:
                    if field in self.entry.data:
                        main_device[field] = self.entry.data.get(field)

                devices.append(main_device)

            # Add battery device if configured
            if battery_template:
                battery_device = {
                    "prefix": battery_prefix,
                    "template": battery_template,
                    "slave_id": battery_slave_id,
                    "type": "battery",
                }

                # Add battery-specific config
                if "battery_modules" in self.entry.data:
                    battery_device["modules"] = self.entry.data.get("battery_modules")
                if "firmware_version" in self.entry.data:
                    battery_device["firmware_version"] = self.entry.data.get(
                        "firmware_version"
                    )

                devices.append(battery_device)

            if not devices:
                _LOGGER.error("No devices found in legacy configuration")
                return []

            _LOGGER.info(
                "Converted legacy configuration to %d devices (main: %s, battery: %s)",
                len(devices),
                template or "none",
                battery_template or "none",
            )

            return devices

        except Exception as e:
            _LOGGER.error("Error converting legacy configuration: %s", str(e))
            return []

    async def _collect_calculated_registers(self) -> List[Dict[str, Any]]:
        """Collect calculated registers and binary sensors from cached entities.

        Returns combined list of calculated entities and binary sensors.
        """
        try:
            # Ensure cache is initialized by calling _collect_all_registers()
            entities_dict = await self._collect_all_registers()

            # Combine calculated and binary_sensors from cached entities
            calculated = entities_dict.get("calculated", [])
            binary_sensors = entities_dict.get("binary_sensors", [])
            combined = calculated + binary_sensors

            _LOGGER.debug(
                "Returning %d calculated entities (%d calculated, %d binary_sensors)",
                len(combined),
                len(calculated),
                len(binary_sensors),
            )

            return combined

        except Exception as e:
            _LOGGER.error("Error collecting calculated registers: %s", str(e))
            return []

    def _filter_battery_template_by_modules(
        self, entities: List[Dict[str, Any]], module_count: int
    ) -> List[Dict[str, Any]]:
        """Filter battery template entities based on module count."""
        try:
            filtered_entities = []
            filtered_count = 0

            for entity in entities:
                # Check if entity should be included based on module count
                if self._is_entity_for_selected_modules(entity, module_count):
                    filtered_entities.append(entity)
                else:
                    filtered_count += 1

            return filtered_entities

        except Exception as e:
            _LOGGER.error("Error filtering battery template by modules: %s", str(e))
            return entities

    async def _extract_config_from_model(
        self, selected_model: str, template_name: str
    ) -> dict:
        """Extract configuration from selected model (modules, mppt_count, string_count, phases, etc)."""
        try:
            if not selected_model or not template_name:
                return {}

            # Load template to get valid_models (use await instead of asyncio.run!)
            template = await get_template_by_name(template_name)
            if not template:
                _LOGGER.warning(
                    "Template %s not found for config extraction", template_name
                )
                return {}

            # Check if template has valid_models configuration
            dynamic_config = template.get("dynamic_config", {})
            valid_models = dynamic_config.get("valid_models", {})

            if not valid_models:
                _LOGGER.debug("No valid_models found in template %s", template_name)
                return {}

            # Look up the selected model
            model_config = valid_models.get(selected_model)
            if not model_config:
                _LOGGER.warning(
                    "Selected model %s not found in valid_models for template %s",
                    selected_model,
                    template_name,
                )
                return {}

            # GENERIC: Extract ALL configuration values from model_config
            # This automatically includes any new fields added to templates in the future:
            # - phases, mppt_count, string_count, modules, type_code (existing)
            # - max_charge_power, max_discharge_power, max_ac_output_power (power limits)
            # - any future fields added by template authors
            config = dict(model_config)

            _LOGGER.debug(
                "Extracted config from model %s: %s",
                selected_model,
                {k: v for k, v in config.items() if v is not None},
            )

            return config

        except Exception as e:
            _LOGGER.error(
                "Error extracting config from model %s: %s", selected_model, str(e)
            )
            return {}

    def _process_entities_with_prefix(
        self, entities: List[Dict[str, Any]], prefix: str, template_name: str
    ) -> List[Dict[str, Any]]:
        """Process entities with a single prefix (for devices array structure)."""
        try:
            processed_entities = []

            for entity in entities:
                processed_entity = entity.copy()

                # entity.copy() preserves all fields including "type"

                # Process unique_id using centralized function
                template_unique_id = entity.get("unique_id")
                name = entity.get("name", "unknown")
                processed_entity["unique_id"] = generate_unique_id(
                    prefix, template_unique_id, name
                )

                # Ensure default_entity_id is set (used to force entity_id)
                if "default_entity_id" not in processed_entity:
                    default_entity_id = processed_entity.get("unique_id")
                    processed_entity["default_entity_id"] = (
                        default_entity_id.lower()
                        if isinstance(default_entity_id, str)
                        else default_entity_id
                    )

                # Process name
                # With has_entity_name=True, entity.name should not include the prefix
                template_name_value = entity.get("name")
                if template_name_value:
                    if template_name_value.startswith(f"{prefix} "):
                        processed_entity["name"] = template_name_value[
                            len(f"{prefix} ") :
                        ]
                    else:
                        processed_entity["name"] = template_name_value

                processed_entities.append(processed_entity)

            return processed_entities

        except Exception as e:
            _LOGGER.error("Error processing entities with prefix: %s", str(e))
            return entities

    def _filter_by_model_config(
        self, entities: List[Dict[str, Any]], model_config: dict
    ) -> List[Dict[str, Any]]:
        """
        Generic filtering based on model configuration parameters.

        Filters entities based on ANY parameter from valid_models that ends with '_count' or matches patterns.
        Examples:
        - mppt_count: 2 → filters mppt1, mppt2 (not mppt3)
        - phases: 3 → filters phase_a, phase_b, phase_c (not phase_d)
        - connectors: 2 → filters connector1, connector2 (not connector3)
        - modules: 5 → filters module_1 to module_5 (not module_6+)

        Supports both numeric patterns (name_1, name_2) and letter patterns (name_a, name_b).
        """
        try:
            if not model_config:
                return entities  # No filtering needed

            filtered_entities = []

            for entity in entities:
                unique_id = entity.get("unique_id", "").lower()
                name = entity.get("name", "").lower()
                should_keep = True

                # Iterate through all config parameters
                for param_name, param_value in model_config.items():
                    if param_value is None:
                        continue

                    # Determine the base name for filtering
                    # e.g., "mppt_count" -> "mppt", "phases" -> "phase"
                    if param_name.endswith("_count"):
                        base_name = param_name.replace("_count", "")
                    elif param_name == "phases":
                        base_name = "phase"
                    elif param_name == "modules":
                        base_name = "module"
                    else:
                        # Skip parameters that don't represent countable entities
                        continue

                    # Check numeric pattern: base_name1, base_name2, base_name_1, base_name_2
                    # Also check patterns like "max_current_phase_1" where phase is in the middle
                    numeric_patterns = [
                        rf"{base_name}(\d+)",  # mppt1, mppt2
                        rf"{base_name}_(\d+)",  # mppt_1, mppt_2, module_1, phase_1
                        rf"_{base_name}_(\d+)",  # max_current_phase_1, connector_phase_2
                    ]

                    for pattern in numeric_patterns:
                        match = re.search(pattern, unique_id)
                        if match:
                            entity_num = int(match.group(1))
                            if entity_num > param_value:
                                _LOGGER.debug(
                                    "Filtering out %s%d (max %s: %d): %s",
                                    base_name,
                                    entity_num,
                                    param_name,
                                    param_value,
                                    unique_id,
                                )
                                should_keep = False
                                break

                    if not should_keep:
                        break

                    # Check letter pattern for phases: phase_a, phase_b, phase_c
                    if base_name == "phase":
                        letter_pattern = rf"{base_name}_([a-z])"
                        match = re.search(letter_pattern, unique_id)
                        if match:
                            letter = match.group(1)
                            letter_num = ord(letter) - ord("a") + 1
                            if letter_num > param_value:
                                _LOGGER.debug(
                                    "Filtering out %s_%s (max %s: %d): %s",
                                    base_name,
                                    letter.upper(),
                                    param_name,
                                    param_value,
                                    unique_id,
                                )
                                should_keep = False
                                break

                if should_keep:
                    filtered_entities.append(entity)

            _LOGGER.debug(
                "Filtered entities by model config: %d -> %d (config: %s)",
                len(entities),
                len(filtered_entities),
                {k: v for k, v in model_config.items() if v is not None},
            )

            return filtered_entities

        except Exception as e:
            _LOGGER.error("Error filtering by model config: %s", str(e))
            return entities

    def _filter_by_conditions(
        self, entities: List[Dict[str, Any]], dynamic_config: dict
    ) -> List[Dict[str, Any]]:
        """
        Filter entities based on condition statements (e.g., dual_channel_meter == true).

        This method dynamically handles ALL fields from the template's dynamic_config section.
        No code changes needed when new fields are added to the template.

        Args:
            entities: List of entities to filter
            dynamic_config: Dictionary containing all dynamic config values (automatically built from template)
            firmware_version: Firmware version for firmware_min_version filtering

        Returns:
            Filtered list of entities
        """
        try:
            filtered_entities = []

            for entity in entities:
                sensor_name = entity.get("name", "") or ""
                unique_id = entity.get("unique_id", "") or ""

                # Check condition filter first
                condition = entity.get("condition")
                if condition:
                    if not _evaluate_condition(condition, dynamic_config):
                        _LOGGER.debug(
                            "Excluding entity due to condition '%s': %s (unique_id: %s)",
                            condition,
                            entity.get("name", "unknown"),
                            entity.get("unique_id", "unknown"),
                        )
                        continue

                # Entity passed all filters
                filtered_entities.append(entity)

            if len(filtered_entities) != len(entities):
                _LOGGER.debug(
                    "Condition filtering: %d -> %d entities",
                    len(entities),
                    len(filtered_entities),
                )

            return filtered_entities

        except Exception as e:
            _LOGGER.error("Error filtering by conditions: %s", str(e))
            return entities  # Return unfiltered on error

    def _evaluate_single_condition(self, condition: str, dynamic_config: dict) -> bool:
        """Evaluate a single condition (no AND/OR).

        Supports:
        - "variable == value" (string, int, bool)
        - "variable != value" (string, int, bool)
        - "variable >= value" (int)
        - "variable in [value1, value2]" (string list)
        """
        condition = condition.strip()

        if " not in " in condition:
            try:
                parts = condition.split(" not in ")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_values_str = parts[1].strip()

                    actual_value = dynamic_config.get(variable_name)

                    if required_values_str.startswith(
                        "["
                    ) and required_values_str.endswith("]"):
                        required_values_str = required_values_str[1:-1]
                    required_values = [
                        value.strip().strip("'\"")
                        for value in required_values_str.split(",")
                        if value.strip()
                    ]

                    if isinstance(actual_value, (list, tuple, set)):
                        actual_values = {str(value) for value in actual_value}
                        result = not any(
                            value in actual_values for value in required_values
                        )
                    else:
                        result = str(actual_value) not in required_values

                    _LOGGER.debug(
                        "Evaluating condition '%s': variable=%s, required=%s, actual=%s, result=%s",
                        condition,
                        variable_name,
                        required_values,
                        actual_value,
                        result,
                    )
                    return result
            except (ValueError, IndexError) as e:
                _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
                return False
        elif " in " in condition:
            try:
                parts = condition.split(" in ")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_values_str = parts[1].strip()

                    actual_value = dynamic_config.get(variable_name)

                    if required_values_str.startswith(
                        "["
                    ) and required_values_str.endswith("]"):
                        required_values_str = required_values_str[1:-1]
                    required_values = [
                        value.strip().strip("'\"")
                        for value in required_values_str.split(",")
                        if value.strip()
                    ]

                    if isinstance(actual_value, (list, tuple, set)):
                        actual_values = {str(value) for value in actual_value}
                        result = any(
                            value in actual_values for value in required_values
                        )
                    else:
                        result = str(actual_value) in required_values

                    _LOGGER.debug(
                        "Evaluating condition '%s': variable=%s, required=%s, actual=%s, result=%s",
                        condition,
                        variable_name,
                        required_values,
                        actual_value,
                        result,
                    )
                    return result
            except (ValueError, IndexError) as e:
                _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
                return False
        elif "!=" in condition:
            try:
                parts = condition.split("!=")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip().strip("'\"")

                    actual_value = dynamic_config.get(variable_name)

                    if required_value_str.lower() in ["true", "false"]:
                        required_value = required_value_str.lower() == "true"
                        actual_value = (
                            bool(actual_value) if actual_value is not None else False
                        )
                    else:
                        try:
                            required_value = int(required_value_str)
                            actual_value = (
                                int(actual_value) if actual_value is not None else 0
                            )
                        except (ValueError, TypeError):
                            required_value = required_value_str
                            actual_value = (
                                str(actual_value) if actual_value is not None else ""
                            )

                    result = actual_value != required_value
                    _LOGGER.debug(
                        "Evaluating condition '%s': variable=%s, required=%s, actual=%s, result=%s",
                        condition,
                        variable_name,
                        required_value,
                        actual_value,
                        result,
                    )
                    return result
            except (ValueError, IndexError) as e:
                _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
                return False
        elif "==" in condition:
            try:
                parts = condition.split("==")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip().strip("'\"")

                    actual_value = dynamic_config.get(variable_name)

                    if required_value_str.lower() in ["true", "false"]:
                        required_value = required_value_str.lower() == "true"
                        actual_value = (
                            bool(actual_value) if actual_value is not None else False
                        )
                    else:
                        try:
                            required_value = int(required_value_str)
                            actual_value = (
                                int(actual_value) if actual_value is not None else 0
                            )
                        except (ValueError, TypeError):
                            required_value = required_value_str
                            actual_value = (
                                str(actual_value) if actual_value is not None else ""
                            )

                    result = actual_value == required_value
                    _LOGGER.debug(
                        "Evaluating condition '%s': variable=%s, required=%s, actual=%s, result=%s",
                        condition,
                        variable_name,
                        required_value,
                        actual_value,
                        result,
                    )
                    return result
            except (ValueError, IndexError) as e:
                _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
                return False
        elif ">=" in condition:
            try:
                parts = condition.split(">=")
                if len(parts) == 2:
                    variable_name = parts[0].strip()
                    required_value_str = parts[1].strip()

                    try:
                        required_value = int(required_value_str)
                        actual_value = dynamic_config.get(variable_name, 0)
                        if isinstance(actual_value, str):
                            actual_value = int(actual_value)
                        return actual_value >= required_value
                    except ValueError:
                        return False
            except (ValueError, IndexError) as e:
                _LOGGER.warning("Invalid condition '%s': %s", condition, str(e))
                return False

        _LOGGER.warning("Unknown condition format '%s', including entity", condition)
        return True

    async def _read_register_range(self, range_obj) -> Optional[List[int]]:
        """Read a range of registers from Modbus."""
        try:
            # Ensure hub is connected (handled by coordinator update)
            if not getattr(self.hub, "_is_connected", False):
                return None

            # Determine register type - check all registers in range
            # If mixed types, we need to handle them separately
            register_types = set()
            for register in range_obj.registers:
                register_types.add(register.get("input_type", "holding"))

            if len(register_types) > 1:
                _LOGGER.warning(
                    "Mixed register types in range %d-%d: %s. Using first type: %s",
                    range_obj.start_address,
                    range_obj.end_address,
                    register_types,
                    range_obj.registers[0].get("input_type", "holding"),
                )

            register_type = range_obj.registers[0].get("input_type", "holding")

            # Check for custom read function code
            read_function_code = range_obj.registers[0].get("read_function_code")
            if read_function_code:
                from .modbus_utils import get_read_call_type

                call_type = get_read_call_type(register_type, read_function_code)
                _LOGGER.debug(
                    "Using custom read function code %d for register range %d-%d",
                    read_function_code,
                    range_obj.start_address,
                    range_obj.end_address,
                )
            else:
                # Auto-detect based on input_type
                call_type = (
                    CALL_TYPE_REGISTER_INPUT
                    if register_type == "input"
                    else CALL_TYPE_REGISTER_HOLDING
                )

            # Get slave ID from first register
            slave_id = range_obj.registers[0].get("slave_id", 1)

            # Safety check: verify all registers in range have the same slave_id
            slave_ids = set(reg.get("slave_id", 1) for reg in range_obj.registers)
            if len(slave_ids) > 1:
                _LOGGER.warning(
                    "Mixed slave_ids in range %d-%d: %s. Using slave_id: %d from first register. "
                    "This should not happen - register optimizer should group by slave_id.",
                    range_obj.start_address,
                    range_obj.end_address,
                    slave_ids,
                    slave_id,
                )

            # Read registers
            result = await self.hub.async_pb_call(
                slave_id,
                range_obj.start_address,
                range_obj.register_count,
                call_type,
            )

            if not result or not hasattr(result, "registers"):
                # Check if coordinator is being unloaded/reloaded
                # If so, this is expected and we should log at debug level
                if (
                    self._is_unloading
                    or not self._cache_initialized
                    or not self._cached_registers_by_interval
                ):
                    # Coordinator is being reloaded/unloaded, suppress warning
                    _LOGGER.debug(
                        "Failed to read registers %d-%d (coordinator reloading/unloading)",
                        range_obj.start_address,
                        range_obj.end_address,
                    )
                else:
                    _LOGGER.warning(
                        "Failed to read registers %d-%d",
                        range_obj.start_address,
                        range_obj.end_address,
                    )
                return None

            return result.registers

        except Exception as e:
            _LOGGER.error(
                "Error reading register range %d-%d: %s",
                range_obj.start_address,
                range_obj.end_address,
                str(e),
            )
            return None

    def _distribute_data(self, raw_data: List[int], range_obj) -> None:
        """Distribute raw register data to individual registers."""
        try:
            for register in range_obj.registers:
                try:
                    # Extract value for this register
                    processed_value = self.register_optimizer.get_register_value(
                        register, raw_data, range_obj.start_address
                    )

                    # Create unique key for this register
                    register_key = self._create_register_key(register)

                    # Process value with mapping (for display)
                    mapped_value = self._process_register_value(
                        processed_value, register
                    )

                    # For registers with flags/mapping, also keep numeric value
                    # This allows templates to use bitwise operations on the numeric value
                    has_mapping = bool(
                        register.get("map")
                        or register.get("options")
                        or register.get("flags")
                    )
                    numeric_value = None
                    if has_mapping and isinstance(processed_value, (int, float)):
                        # Calculate numeric value before mapping (with scale/offset/precision but without mapping)
                        # Use process_register_value but stop before mapping
                        from .value_processor import process_register_value

                        # Create a copy of register config without mapping
                        numeric_config = register.copy()
                        numeric_config.pop("map", None)
                        numeric_config.pop("flags", None)
                        numeric_config.pop("options", None)
                        numeric_value = process_register_value(
                            processed_value, numeric_config, apply_precision=True
                        )

                    # Store processed data
                    register_data = {
                        "raw_value": processed_value,
                        "processed_value": mapped_value,
                        "register_config": register,
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                    if numeric_value is not None:
                        register_data["numeric_value"] = numeric_value
                    self.register_data[register_key] = register_data

                except Exception as e:
                    _LOGGER.error(
                        "Error processing register %s: %s",
                        register.get("name", "unknown"),
                        str(e),
                    )

        except Exception as e:
            _LOGGER.error("Error distributing data: %s", str(e))

    def _create_register_key(self, register: Dict[str, Any]) -> str:
        """Create unique key for register."""
        return f"{register.get('unique_id', 'unknown')}_{register.get('address', 0)}"

    def _process_register_value(self, raw_value: Any, register: Dict[str, Any]) -> Any:
        """Process register value according to register configuration."""
        try:
            if raw_value is None:
                return None

            # Apply data type conversion
            data_type = register.get("data_type", "uint16")
            processed_value = None

            # Handle all data types
            if isinstance(raw_value, list):
                # Multi-register values
                if data_type in ["uint32", "int32"]:
                    # 32-bit integer (2 registers)
                    if len(raw_value) >= 2:
                        # Check for byte swapping
                        swap = register.get("swap", "none")
                        if swap == "word":
                            # Swap word order: [high_word, low_word] -> [low_word, high_word]
                            combined = (raw_value[1] << 16) | raw_value[0]
                        else:
                            # Default: [high_word, low_word]
                            combined = (raw_value[0] << 16) | raw_value[1]

                        if data_type == "int32" and combined >= 0x80000000:
                            combined -= 0x100000000
                        processed_value = combined
                    else:
                        processed_value = raw_value[0] if raw_value else 0

                elif data_type in ["float", "float32"]:
                    # 32-bit float (2 registers)
                    if len(raw_value) >= 2:
                        import struct

                        # Check for byte swapping
                        swap = register.get("swap", "none")
                        if swap == "word":
                            # Swap word order for float
                            bytes_data = struct.pack(">HH", raw_value[1], raw_value[0])
                        else:
                            # Default order
                            bytes_data = struct.pack(">HH", raw_value[0], raw_value[1])

                        processed_value = struct.unpack(">f", bytes_data)[0]
                    else:
                        processed_value = float(raw_value[0]) if raw_value else 0.0

                elif data_type == "float64":
                    # 64-bit float (4 registers)
                    if len(raw_value) >= 4:
                        import struct

                        bytes_data = struct.pack(
                            ">HHHH",
                            raw_value[0],
                            raw_value[1],
                            raw_value[2],
                            raw_value[3],
                        )
                        processed_value = struct.unpack(">d", bytes_data)[0]
                    else:
                        processed_value = float(raw_value[0]) if raw_value else 0.0

                elif data_type == "string":
                    # String conversion
                    string_bytes = []
                    for reg_val in raw_value:
                        string_bytes.extend([reg_val >> 8, reg_val & 0xFF])
                    processed_value = (
                        bytes(string_bytes)
                        .decode("utf-8", errors="ignore")
                        .rstrip("\x00")
                    )

                else:
                    # Default: return first value for single-register types
                    processed_value = raw_value[0] if raw_value else 0

            else:
                # Single register values
                if data_type in ["int16"]:
                    # 16-bit signed integer
                    if raw_value >= 0x8000:
                        processed_value = raw_value - 0x10000
                    else:
                        processed_value = raw_value

                elif data_type in ["uint16", "uint32"]:
                    # Unsigned integers
                    processed_value = raw_value

                elif data_type in ["float", "float32", "float64"]:
                    # Float conversion
                    processed_value = float(raw_value)

                elif data_type == "string":
                    # String conversion
                    processed_value = str(raw_value)

                else:
                    # Default: return as-is
                    processed_value = raw_value

            # Use centralized value processing (handles scale, offset, bit ops, precision, mapping)
            # Note: For select entities, skip mapping as they need raw numeric values
            apply_mapping = register.get("type") != "select"

            if apply_mapping:
                # Full processing: scale, offset, bit ops, precision, mapping
                processed_value = process_register_value(
                    processed_value, register, apply_precision=True
                )
            else:
                # For select: only scale, offset, precision (no mapping, no bit ops)
                scale = register.get("scale", 1.0)
                offset = register.get("offset", 0.0)
                if isinstance(processed_value, (int, float)):
                    processed_value = (processed_value * scale) + offset

                precision = register.get("precision")
                if precision is not None and isinstance(processed_value, (int, float)):
                    processed_value = round(processed_value, precision)

            return processed_value

        except Exception as e:
            _LOGGER.error(
                "Error processing value for register %s (data_type: %s, raw_value: %s): %s",
                register.get("name", "unknown"),
                data_type,
                raw_value,
                str(e),
            )
            return None

    def get_register_data(self, register_key: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific register."""
        return self.register_data.get(register_key)

    def get_all_register_data(self) -> Dict[str, Any]:
        """Get all register data."""
        return self.register_data.copy()

    def _group_registers_by_interval(
        self, registers: List[Dict[str, Any]]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Group registers by their scan_interval."""
        grouped = {}
        for register in registers:
            # Get scan_interval from register, default to 30 seconds
            interval = register.get("scan_interval", 30)
            if not isinstance(interval, (int, float)):
                interval = 30

            interval = int(interval)  # Ensure it's an integer

            if interval not in grouped:
                grouped[interval] = []
            grouped[interval].append(register)

        return grouped

    def _get_registers_due_for_update(self) -> List[Dict[str, Any]]:
        """Get registers that are due for update based on their scan_interval."""
        try:
            if not self._cached_registers_by_interval:
                return []

            current_time = asyncio.get_event_loop().time()
            registers_to_read = []

            # Track which intervals are being updated
            intervals_to_update = []

            for interval, registers in self._cached_registers_by_interval.items():
                last_update = self._last_update_time.get(interval, 0)
                time_since_update = current_time - last_update

                # Check if this interval group is due for update
                if time_since_update >= interval:
                    registers_to_read.extend(registers)
                    intervals_to_update.append((interval, len(registers)))

            return registers_to_read

        except Exception as e:
            _LOGGER.error("Error determining registers due for update: %s", str(e))
            # Fallback: return all registers
            return [
                reg
                for regs in self._cached_registers_by_interval.values()
                for reg in regs
            ]

    def _update_coordinator_interval(self, interval: int) -> None:
        """Update the coordinator's update interval to match minimum scan_interval."""
        try:
            new_interval = timedelta(seconds=interval)
            current_interval = self.update_interval

            # Only update if the new interval is different
            if new_interval != current_interval:
                self.update_interval = new_interval
                _LOGGER.debug(
                    "Updated coordinator update interval to %s",
                    new_interval,
                )

        except Exception as e:
            _LOGGER.error("Error updating coordinator interval: %s", str(e))

    async def _update_device_firmware_from_register(self) -> None:
        """Update device firmware version from inverter_firmware_info register if available."""
        try:
            # Track if we've already updated firmware to avoid repeated updates
            if not hasattr(self, "_firmware_updated"):
                self._firmware_updated = False

            # Only try once per coordinator lifecycle
            if self._firmware_updated:
                return

            # Look for inverter_firmware_info register data
            firmware_key = None
            for key in self.register_data.keys():
                if "inverter_firmware_info" in key.lower():
                    firmware_key = key
                    break

            if not firmware_key:
                return

            firmware_value = self.register_data.get(firmware_key)
            if not firmware_value or firmware_value in [
                "unknown",
                "unavailable",
                None,
                "",
            ]:
                return

            # Extract processed_value if firmware_value is a dictionary
            if isinstance(firmware_value, dict):
                firmware_value = firmware_value.get("processed_value")
                if not firmware_value:
                    return

            # Clean up firmware string (remove null bytes, strip whitespace)
            if isinstance(firmware_value, str):
                firmware_value = firmware_value.replace("\x00", "").strip()
                if not firmware_value:
                    return

            # Get device identifier
            hub_config = self.entry.data.get("hub", {})
            host = hub_config.get("host") or self.entry.data.get("host", "unknown")
            port = hub_config.get("port") or self.entry.data.get("port", 502)

            # Get devices from config entry
            devices = self.entry.data.get("devices", [])
            if not devices:
                return

            # Find matching device by host/port/slave_id
            for device in devices:
                device_slave_id = device.get("slave_id", 1)
                device_identifier = (
                    f"modbus_manager_{host}_{port}_slave_{device_slave_id}"
                )

                # Update device registry
                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_identifier)}
                )

                if device_entry:
                    # Update firmware version
                    device_registry.async_update_device(
                        device_entry.id,
                        sw_version=f"Firmware: {firmware_value}",
                    )
                    self._firmware_updated = True
                    break

        except Exception as e:
            _LOGGER.debug(
                "Could not update device firmware from register (this is normal if register is not available): %s",
                str(e),
            )

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down ModbusCoordinator")
        # Cancel any pending updates
        if hasattr(self, "_update_task") and self._update_task:
            self._update_task.cancel()
        # Clear data
        self.register_data.clear()
