"""Modbus Coordinator for centralized data management."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .device_utils import (
    generate_unique_id,
    process_template_entities_with_prefix,
    replace_template_placeholders,
)
from .logger import ModbusManagerLogger
from .performance_monitor import PerformanceMonitor
from .register_optimizer import RegisterOptimizer
from .template_loader import get_template_by_name
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

        # Cache for processed registers (loaded once at startup, reused on every update)
        self._cached_registers = None
        self._cached_calculated = None
        self._cached_registers_by_interval = {}  # Register grouped by scan_interval
        self._cache_initialized = False

        # Track when each interval group was last updated
        self._last_update_time = {}

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
        """Invalidate the register cache (e.g., when template is reloaded)."""
        _LOGGER.info("Invalidating register cache")
        self._cached_registers = None
        self._cached_calculated = None
        self._cached_registers_by_interval = {}
        self._last_update_time = {}
        self._cache_initialized = False
        # Force re-collection on next update
        self._cached_registers = None

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

        try:
            # Start performance monitoring
            operation_id = self.performance_monitor.start_operation(
                device_id=self.entry.data.get("prefix", "unknown"),
                operation_type="coordinator_update",
            )

            # 1. Group registers by scan_interval if not cached
            if not self._cached_registers_by_interval:
                all_registers = await self._collect_all_registers()
                if all_registers:
                    # Group registers by their scan_interval
                    self._cached_registers_by_interval = (
                        self._group_registers_by_interval(all_registers)
                    )

                    # Calculate minimum interval and update coordinator if needed
                    min_interval = (
                        min(self._cached_registers_by_interval.keys())
                        if self._cached_registers_by_interval
                        else 10
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
            device_id = self.entry.data.get("prefix", "unknown")
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

        except Exception as e:
            _LOGGER.error("Error in coordinator update: %s", str(e))
            self.performance_monitor.end_operation(
                device_id=self.entry.data.get("prefix", "unknown"),
                operation_id=operation_id,
                success=False,
                error_message=str(e),
            )
            raise UpdateFailed(f"Error updating coordinator: {e}")

    async def _collect_all_registers(self) -> List[Dict[str, Any]]:
        """Collect all registers that need to be read using devices array structure."""
        try:
            # Use cached registers if already initialized (massive performance improvement!)
            if self._cache_initialized and self._cached_registers is not None:
                _LOGGER.debug(
                    "Using cached registers (%d registers)", len(self._cached_registers)
                )
                return self._cached_registers

            # First time or cache invalidated - load and process templates
            devices = self.entry.data.get("devices")

            if devices and isinstance(devices, list):
                if not self._cache_initialized:
                    _LOGGER.info(
                        "Initializing register cache for %d devices", len(devices)
                    )
                registers = await self._collect_registers_from_devices(devices)
            else:
                # Fallback to legacy structure for backward compatibility
                if not self._cache_initialized:
                    _LOGGER.info("Initializing register cache (legacy structure)")
                registers = await self._collect_registers_legacy()

            # Cache the results
            self._cached_registers = registers
            self._cache_initialized = True
            _LOGGER.info("Register cache initialized with %d registers", len(registers))

            return registers

        except Exception as e:
            _LOGGER.error("Error collecting registers: %s", str(e))
            return []

    async def _collect_registers_from_devices(
        self, devices: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Collect registers from devices array structure."""
        try:
            all_registers = []

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

            for device in devices:
                device_type = device.get("type", "inverter")
                template_name = device.get("template")
                prefix = device.get("prefix", "unknown")
                slave_id = device.get("slave_id", 1)
                selected_model = device.get("selected_model")

                # Extract configuration from selected model if available
                model_config = await self._extract_config_from_model(
                    selected_model, template_name
                )
                modules = model_config.get("modules")
                mppt_count = model_config.get("mppt_count")
                string_count = model_config.get("string_count")
                phases = model_config.get("phases")

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

                # Apply firmware version filtering if specified
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

                # Apply generic model-based filtering (works for any device type)
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
                # Get firmware_version for firmware filtering (separate from condition filtering)
                firmware_version = device.get("firmware_version") or template.get(
                    "firmware_version", "1.0.0"
                )

                # Filter using dynamic_config (automatically includes all template fields)
                registers = self._filter_by_conditions(
                    registers, dynamic_config, firmware_version
                )
                controls = self._filter_by_conditions(
                    controls, dynamic_config, firmware_version
                )
                calculated = self._filter_by_conditions(
                    calculated, dynamic_config, firmware_version
                )
                binary_sensors = self._filter_by_conditions(
                    binary_sensors, dynamic_config, firmware_version
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
                from .device_utils import create_device_info_dict

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

                # Add type field, device info, and combine
                for register in processed_registers:
                    register["type"] = "sensor"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    all_registers.append(register)

                # Replace model-specific placeholders in controls (e.g., {{max_charge_power}})
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

                    # Replace placeholders in max_value if model_config is available
                    # Supports: {{max_charge_power}}, {{max_discharge_power}}, {{max_ac_output_power}}
                    # Also supports calculations: {{max_charge_power * 0.5}}
                    if selected_model and model_config:
                        max_value = register.get("max_value")
                        if (
                            max_value
                            and isinstance(max_value, str)
                            and "{{" in max_value
                            and "}}" in max_value
                        ):
                            try:
                                # Extract expression inside {{ }}
                                import re

                                pattern = r"\{\{([^}]+)\}\}"
                                match = re.search(pattern, max_value)

                                if match:
                                    expression = match.group(1).strip()
                                    unit = register.get(
                                        "unit_of_measurement", ""
                                    ).lower()

                                    # Replace model_config keys in expression
                                    # e.g., "max_charge_power * 0.5" -> "10600 * 0.5"
                                    processed_expression = expression
                                    for key, value in model_config.items():
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

                                    _LOGGER.debug(
                                        "Replaced placeholder {{%s}} with %.1f %s for %s (model: %s)",
                                        expression,
                                        register["max_value"],
                                        unit,
                                        register.get("name", "unknown"),
                                        selected_model,
                                    )
                            except Exception as e:
                                _LOGGER.warning(
                                    "Error replacing placeholder {{%s}} in max_value for %s: %s",
                                    max_value,
                                    register.get("name", "unknown"),
                                    str(e),
                                )

                    all_registers.append(register)

                for register in processed_calculated:
                    register["type"] = "calculated"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    all_registers.append(register)

                for register in processed_binary_sensors:
                    register["type"] = "binary_sensor"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    all_registers.append(register)

                _LOGGER.debug(
                    "Added %d registers for device %s",
                    len(processed_registers)
                    + len(processed_controls)
                    + len(processed_calculated)
                    + len(processed_binary_sensors),
                    template_name,
                )

            return all_registers

        except Exception as e:
            _LOGGER.error("Error collecting registers from devices: %s", str(e))
            return []

    async def _collect_registers_legacy(self) -> List[Dict[str, Any]]:
        """Legacy method for backward compatibility."""
        try:
            # Get template name from entry
            template_name = self.entry.data.get("template")
            if not template_name:
                _LOGGER.error("No template specified in entry")
                return []

            # Load main template
            template = await get_template_by_name(template_name)
            if not template:
                _LOGGER.error("Template %s not found", template_name)
                return []

            # Extract registers from main template and set type based on section
            registers = template.get("sensors", [])
            controls = template.get("controls", [])
            calculated = template.get("calculated", [])
            binary_sensors = template.get("binary_sensors", [])

            # Check if battery template is configured
            battery_template_name = self.entry.data.get("battery_template")
            if battery_template_name:
                _LOGGER.info("Loading battery template: %s", battery_template_name)
                battery_template = await get_template_by_name(battery_template_name)
                if battery_template:
                    # Add battery registers with battery prefix
                    battery_registers = battery_template.get("sensors", [])
                    battery_controls = battery_template.get("controls", [])
                    battery_calculated = battery_template.get("calculated", [])
                    battery_binary_sensors = battery_template.get("binary_sensors", [])

                    # Add battery registers to main lists
                    registers.extend(battery_registers)
                    controls.extend(battery_controls)
                    calculated.extend(battery_calculated)
                    binary_sensors.extend(battery_binary_sensors)

                    _LOGGER.info(
                        "Added battery template registers: %d sensors, %d controls, %d calculated, %d binary",
                        len(battery_registers),
                        len(battery_controls),
                        len(battery_calculated),
                        len(battery_binary_sensors),
                    )

            # Combine all register types and set type field
            all_registers = []

            # Add sensors (no type field needed - they are sensors by default)
            for register in registers:
                register["type"] = "sensor"
                all_registers.append(register)

            # Add controls with their specific types
            for register in controls:
                # Controls already have type field set in template
                all_registers.append(register)

            # Add calculated entities
            for register in calculated:
                register["type"] = "calculated"
                all_registers.append(register)

            # Add binary sensors
            for register in binary_sensors:
                register["type"] = "binary_sensor"
                all_registers.append(register)

            # Process all registers with prefix handling
            prefix = self.entry.data.get("prefix", "unknown")
            slave_id = self.entry.data.get("slave_id", 1)
            battery_slave_id = self.entry.data.get("battery_slave_id", 200)

            # Filter battery template based on module count if specified
            if self.entry.data.get("battery_modules"):
                module_count = self.entry.data.get("battery_modules")
                registers = self._filter_battery_template_by_modules(
                    registers, module_count
                )
                controls = self._filter_battery_template_by_modules(
                    controls, module_count
                )
                calculated = self._filter_battery_template_by_modules(
                    calculated, module_count
                )
                binary_sensors = self._filter_battery_template_by_modules(
                    binary_sensors, module_count
                )

            # Process each register type with appropriate prefix
            battery_prefix = self.entry.data.get("battery_prefix", "SBR")
            processed_registers = self._process_entities_with_dual_prefix(
                registers, prefix, battery_prefix, template_name
            )
            processed_controls = self._process_entities_with_dual_prefix(
                controls, prefix, battery_prefix, template_name
            )
            processed_calculated = self._process_entities_with_dual_prefix(
                calculated, prefix, battery_prefix, template_name
            )
            processed_binary_sensors = self._process_entities_with_dual_prefix(
                binary_sensors, prefix, battery_prefix, template_name
            )

            # Replace placeholders in all processed entities
            all_processed_entities = (
                processed_registers
                + processed_controls
                + processed_calculated
                + processed_binary_sensors
            )

            for entity in all_processed_entities:
                # Replace placeholders in name and other string fields
                for field in ["name", "template", "unit_of_measurement"]:
                    if field in entity and isinstance(entity[field], str):
                        entity[field] = replace_template_placeholders(
                            entity[field], prefix, slave_id, battery_slave_id
                        )

                # Note: slave_id is now set from device config, not from template
                # Template slave_id values (including placeholders) are ignored

            # Update all_registers with processed data
            all_registers = (
                processed_registers
                + processed_controls
                + processed_calculated
                + processed_binary_sensors
            )

            # Separate registers with addresses from calculated entities
            valid_registers = []
            calculated_registers = []

            for reg in all_registers:
                address = reg.get("address")
                if address is not None and address > 0:
                    valid_registers.append(reg)
                else:
                    # Keep calculated entities for later processing
                    calculated_registers.append(reg)
                    _LOGGER.debug(
                        "Found calculated entity without address: %s",
                        reg.get("name", "unknown"),
                    )

            _LOGGER.debug(
                "Filtered %d valid registers from %d total registers",
                len(valid_registers),
                len(all_registers),
            )
            all_registers = valid_registers

            # Filter by firmware version if specified
            firmware_version = self.entry.data.get("firmware_version")
            if firmware_version:
                all_registers = filter_by_firmware_version(
                    all_registers, firmware_version
                )

            # Only return registers with addresses for Modbus reading
            # Calculated registers are handled separately by their respective platforms
            return valid_registers

        except Exception as e:
            _LOGGER.error("Error collecting registers: %s", str(e))
            return []

    async def _collect_calculated_registers(self) -> List[Dict[str, Any]]:
        """Collect calculated registers using devices array structure."""
        try:
            # Use cached calculated registers if already initialized
            if self._cache_initialized and self._cached_calculated is not None:
                _LOGGER.debug(
                    "Using cached calculated registers (%d registers)",
                    len(self._cached_calculated),
                )
                return self._cached_calculated

            # First time or cache invalidated - load and process templates
            devices = self.entry.data.get("devices")
            if devices and isinstance(devices, list):
                calculated = await self._collect_calculated_from_devices(devices)
            else:
                # Fallback to legacy structure for backward compatibility
                if not self._cache_initialized:
                    _LOGGER.info(
                        "Initializing calculated registers cache (legacy structure)"
                    )
                calculated = await self._collect_calculated_legacy()

            # Cache the results
            self._cached_calculated = calculated
            _LOGGER.info(
                "Calculated registers cache initialized with %d registers",
                len(calculated),
            )

            return calculated

        except Exception as e:
            _LOGGER.error("Error collecting calculated registers: %s", str(e))
            return []

    async def _collect_calculated_from_devices(
        self, devices: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Collect calculated registers from devices array structure."""
        try:
            all_calculated_registers = []

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

            for device in devices:
                device_type = device.get("type", "inverter")
                template_name = device.get("template")
                prefix = device.get("prefix", "unknown")
                slave_id = device.get("slave_id", 1)
                selected_model = device.get("selected_model")

                # Extract configuration from selected model if available
                model_config = await self._extract_config_from_model(
                    selected_model, template_name
                )
                modules = model_config.get("modules")
                mppt_count = model_config.get("mppt_count")
                string_count = model_config.get("string_count")
                phases = model_config.get("phases")

                if not template_name:
                    _LOGGER.warning(
                        "Device missing template name, skipping: %s", device
                    )
                    continue

                _LOGGER.debug(
                    "Processing calculated registers for device: %s (prefix: %s, model: %s, fw: %s)",
                    template_name,
                    prefix,
                    selected_model,
                    device.get("firmware_version", "unknown"),
                )

                # Load template
                template = await get_template_by_name(template_name)
                if not template:
                    _LOGGER.error("Template %s not found for device", template_name)
                    continue

                # Build dynamic_config dict dynamically from template's dynamic_config section
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

                # Add explicitly handled fields
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
                        "Auto-detected SBR Battery - setting battery_enabled=True for calculated device %s",
                        template_name,
                    )
                dynamic_config["battery_enabled"] = battery_config != "none"

                # Extract calculated registers from template
                calculated = template.get("calculated", [])
                binary_sensors = template.get("binary_sensors", [])

                # Apply firmware version filtering if specified
                firmware_version = device.get("firmware_version")
                if firmware_version:
                    calculated = filter_by_firmware_version(
                        calculated, firmware_version
                    )
                    binary_sensors = filter_by_firmware_version(
                        binary_sensors, firmware_version
                    )

                # Apply generic model-based filtering (works for any device type)
                if model_config:
                    _LOGGER.debug(
                        "Applying model-based filtering for calculated in %s with config: %s",
                        template_name,
                        {k: v for k, v in model_config.items() if v is not None},
                    )
                    calculated = self._filter_by_model_config(calculated, model_config)
                    binary_sensors = self._filter_by_model_config(
                        binary_sensors, model_config
                    )

                # Apply condition-based filtering (e.g., dual_channel_meter == true)
                firmware_version = device.get("firmware_version") or template.get(
                    "firmware_version", "1.0.0"
                )
                calculated = self._filter_by_conditions(
                    calculated, dynamic_config, firmware_version
                )
                binary_sensors = self._filter_by_conditions(
                    binary_sensors, dynamic_config, firmware_version
                )

                # Process entities with device-specific prefix
                processed_calculated = self._process_entities_with_prefix(
                    calculated, prefix, template_name
                )
                processed_binary_sensors = self._process_entities_with_prefix(
                    binary_sensors, prefix, template_name
                )

                # Replace placeholders in calculated entity templates (state, availability)
                for entity in processed_calculated + processed_binary_sensors:
                    for field in ["state", "availability", "template"]:
                        if field in entity and isinstance(entity[field], str):
                            entity[field] = replace_template_placeholders(
                                entity[field], prefix, slave_id, 0
                            )

                # Create device info dict for this device
                from .device_utils import create_device_info_dict

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

                # Add type field, device info, and combine
                for register in processed_calculated:
                    register["type"] = "calculated"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    all_calculated_registers.append(register)

                for register in processed_binary_sensors:
                    register["type"] = "binary_sensor"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    all_calculated_registers.append(register)

                _LOGGER.debug(
                    "Added %d calculated registers for device %s",
                    len(processed_calculated) + len(processed_binary_sensors),
                    template_name,
                )

            return all_calculated_registers

        except Exception as e:
            _LOGGER.error(
                "Error collecting calculated registers from devices: %s", str(e)
            )
            return []

    async def _collect_calculated_legacy(self) -> List[Dict[str, Any]]:
        """Legacy method for collecting calculated registers."""
        try:
            # Get template name from entry
            template_name = self.entry.data.get("template")
            if not template_name:
                _LOGGER.error("No template specified in entry")
                return []

            # Load template
            template = await get_template_by_name(template_name)
            if not template:
                _LOGGER.error("Template %s not found", template_name)
                return []

            # Extract calculated registers from template
            calculated = template.get("calculated", [])
            binary_sensors = template.get("binary_sensors", [])

            # Check if battery template is configured
            battery_template_name = self.entry.data.get("battery_template")
            if battery_template_name:
                _LOGGER.info(
                    "Loading battery calculated registers from: %s",
                    battery_template_name,
                )
                battery_template = await get_template_by_name(battery_template_name)
                if battery_template:
                    # Add battery calculated registers
                    battery_calculated = battery_template.get("calculated", [])
                    battery_binary_sensors = battery_template.get("binary_sensors", [])

                    calculated.extend(battery_calculated)
                    binary_sensors.extend(battery_binary_sensors)

                    _LOGGER.info(
                        "Added battery calculated registers: %d calculated, %d binary",
                        len(battery_calculated),
                        len(battery_binary_sensors),
                    )

            # Combine calculated registers and set type field
            calculated_registers = []

            # Add calculated entities
            for register in calculated:
                register["type"] = "calculated"
                calculated_registers.append(register)

            # Add binary sensors
            for register in binary_sensors:
                register["type"] = "binary_sensor"
                calculated_registers.append(register)

            # Process calculated registers with prefix handling
            prefix = self.entry.data.get("prefix", "unknown")
            slave_id = self.entry.data.get("slave_id", 1)
            battery_slave_id = self.entry.data.get("battery_slave_id", 200)

            # Filter battery template based on module count if specified
            if self.entry.data.get("battery_modules"):
                module_count = self.entry.data.get("battery_modules")
                calculated_registers = self._filter_battery_template_by_modules(
                    calculated_registers, module_count
                )

            # Process calculated registers with appropriate prefix
            battery_prefix = self.entry.data.get("battery_prefix", "SBR")
            processed_calculated_registers = self._process_entities_with_dual_prefix(
                calculated_registers, prefix, battery_prefix, template_name
            )

            _LOGGER.debug(
                "Processed %d calculated/binary registers with prefix '%s'",
                len(processed_calculated_registers),
                prefix,
            )

            # Replace placeholders in calculated entities
            for entity in processed_calculated_registers:
                # Replace placeholders in name and other string fields
                for field in ["state", "availability", "template"]:
                    if field in entity and isinstance(entity[field], str):
                        entity[field] = replace_template_placeholders(
                            entity[field], prefix, slave_id, battery_slave_id
                        )

                # Note: slave_id is now set from device config, not from template
                # Template slave_id values (including placeholders) are ignored

            calculated_registers = processed_calculated_registers

            return calculated_registers

        except Exception as e:
            _LOGGER.error("Error collecting calculated registers: %s", str(e))
            return []

    def _filter_battery_template_by_modules(
        self, entities: List[Dict[str, Any]], module_count: int
    ) -> List[Dict[str, Any]]:
        """Filter battery template entities based on module count."""
        try:
            import re

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

                # Process unique_id
                template_unique_id = entity.get("unique_id")
                if template_unique_id:
                    if not template_unique_id.startswith(f"{prefix}_"):
                        processed_entity["unique_id"] = f"{prefix}_{template_unique_id}"
                else:
                    name = entity.get("name", "unknown")
                    clean_name = (
                        name.lower()
                        .replace(" ", "_")
                        .replace("-", "_")
                        .replace("(", "")
                        .replace(")", "")
                    )
                    processed_entity["unique_id"] = f"{prefix}_{clean_name}"

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

            import re

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
        self,
        entities: List[Dict[str, Any]],
        dynamic_config: dict,
        firmware_version: str,
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
            import re

            filtered_entities = []

            for entity in entities:
                sensor_name = entity.get("name", "") or ""
                unique_id = entity.get("unique_id", "") or ""

                # Check condition filter first
                condition = entity.get("condition")
                if condition:
                    # Parse condition like "modules >= 5", "phases == 3", or "dual_channel_meter == true"
                    if "==" in condition:
                        try:
                            parts = condition.split("==")
                            if len(parts) == 2:
                                variable_name = parts[0].strip()
                                required_value_str = parts[1].strip()

                                # Get actual value from dynamic_config
                                actual_value = dynamic_config.get(variable_name)

                                # Try to convert to bool first (for true/false)
                                if required_value_str.lower() in ["true", "false"]:
                                    required_value = (
                                        required_value_str.lower() == "true"
                                    )
                                    actual_value = (
                                        bool(actual_value)
                                        if actual_value is not None
                                        else False
                                    )
                                else:
                                    # Try to convert to int, then string
                                    try:
                                        required_value = int(required_value_str)
                                        actual_value = (
                                            int(actual_value)
                                            if actual_value is not None
                                            else 0
                                        )
                                    except (ValueError, TypeError):
                                        required_value = required_value_str
                                        actual_value = (
                                            str(actual_value)
                                            if actual_value is not None
                                            else ""
                                        )

                                _LOGGER.debug(
                                    "Checking condition '%s' for entity %s: required=%s, actual=%s",
                                    condition,
                                    entity.get("name", "unknown"),
                                    required_value,
                                    actual_value,
                                )

                                if actual_value != required_value:
                                    _LOGGER.debug(
                                        "Excluding entity due to condition '%s': %s (unique_id: %s, required: %s, actual: %s)",
                                        condition,
                                        entity.get("name", "unknown"),
                                        entity.get("unique_id", "unknown"),
                                        required_value,
                                        actual_value,
                                    )
                                    continue  # Skip this entity
                        except (ValueError, IndexError) as e:
                            _LOGGER.warning(
                                "Invalid condition '%s' for entity %s: %s",
                                condition,
                                entity.get("name", "unknown"),
                                str(e),
                            )
                    elif ">=" in condition:
                        try:
                            parts = condition.split(">=")
                            if len(parts) == 2:
                                variable_name = parts[0].strip()
                                required_value_str = parts[1].strip()

                                # Get actual value from dynamic_config
                                actual_value = dynamic_config.get(variable_name, 0)

                                try:
                                    required_value = int(required_value_str)
                                    actual_value = (
                                        int(actual_value)
                                        if actual_value is not None
                                        else 0
                                    )

                                    if actual_value < required_value:
                                        _LOGGER.debug(
                                            "Excluding entity due to condition '%s': %s (unique_id: %s, required: %s, actual: %s)",
                                            condition,
                                            entity.get("name", "unknown"),
                                            entity.get("unique_id", "unknown"),
                                            required_value,
                                            actual_value,
                                        )
                                        continue  # Skip this entity
                                except (ValueError, TypeError):
                                    _LOGGER.warning(
                                        "Invalid condition '%s' for entity %s: cannot parse values",
                                        condition,
                                        entity.get("name", "unknown"),
                                    )
                        except (ValueError, IndexError) as e:
                            _LOGGER.warning(
                                "Invalid condition '%s' for entity %s: %s",
                                condition,
                                entity.get("name", "unknown"),
                                str(e),
                            )

                # Check firmware_min_version filter
                sensor_firmware_min = entity.get("firmware_min_version")
                if sensor_firmware_min and firmware_version:
                    try:
                        from packaging import version

                        current_ver = version.parse(firmware_version)
                        min_ver = version.parse(sensor_firmware_min)
                        if current_ver < min_ver:
                            _LOGGER.debug(
                                "Excluding entity due to firmware version: %s (unique_id: %s, requires: %s, current: %s)",
                                entity.get("name", "unknown"),
                                entity.get("unique_id", "unknown"),
                                sensor_firmware_min,
                                firmware_version,
                            )
                            continue  # Skip this entity
                    except Exception:  # nosec B110
                        # If comparison fails, include the entity (better safe than sorry)
                        pass

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

    def _process_entities_with_dual_prefix(
        self,
        entities: List[Dict[str, Any]],
        inverter_prefix: str,
        battery_prefix: str,
        template_name: str,
    ) -> List[Dict[str, Any]]:
        """Process entities with appropriate prefix based on whether they are battery entities."""
        try:
            processed_entities = []

            for entity in entities:
                # Determine if this is a battery entity
                is_battery_entity = self._is_battery_entity(entity)

                # Use appropriate prefix
                entity_prefix = battery_prefix if is_battery_entity else inverter_prefix

                # Process with the determined prefix
                processed_entity = entity.copy()

                # Process unique_id
                template_unique_id = entity.get("unique_id")
                if template_unique_id:
                    if not template_unique_id.startswith(f"{entity_prefix}_"):
                        processed_entity[
                            "unique_id"
                        ] = f"{entity_prefix}_{template_unique_id}"
                else:
                    name = entity.get("name", "unknown")
                    clean_name = (
                        name.lower()
                        .replace(" ", "_")
                        .replace("-", "_")
                        .replace("(", "")
                        .replace(")", "")
                    )
                    processed_entity["unique_id"] = f"{entity_prefix}_{clean_name}"

                # Process name
                # With has_entity_name=True, entity.name should not include the prefix
                template_name_value = entity.get("name")
                if template_name_value:
                    if template_name_value.startswith(f"{entity_prefix} "):
                        processed_entity["name"] = template_name_value[
                            len(f"{entity_prefix} ") :
                        ]
                    else:
                        processed_entity["name"] = template_name_value

                processed_entities.append(processed_entity)

            return processed_entities

        except Exception as e:
            _LOGGER.error("Error processing entities with dual prefix: %s", str(e))
            return entities

    def _is_battery_entity(self, entity: Dict[str, Any]) -> bool:
        """Check if an entity belongs to the battery template."""
        try:
            # Check if entity has battery-specific patterns
            unique_id = entity.get("unique_id", "").lower()
            name = entity.get("name", "").lower()

            # Battery-specific patterns
            battery_patterns = [
                "battery",
                "module_",
                "cell_",
                "sbr",
                "charge",
                "discharge",
                "soc",
                "soh",
            ]

            for pattern in battery_patterns:
                if pattern in unique_id or pattern in name:
                    return True

            # Check register ranges (Sungrow SBR specific)
            register = entity.get("register")
            if register is not None:
                # Battery register ranges
                battery_register_ranges = [
                    (10720, 10729),  # Battery status registers
                    (10740, 10745),  # Battery configuration registers
                    (10747, 10747),  # Battery control register
                    (10756, 10763),  # Battery module 1 registers
                    (10764, 10771),  # Battery module 2 registers
                    (10772, 10779),  # Battery module 3 registers
                    (10780, 10787),  # Battery module 4 registers
                    (10788, 10788),  # Battery module 5 registers
                    (10821, 10829),  # Battery module 6 registers
                    (10830, 10838),  # Battery module 7 registers
                    (10839, 10847),  # Battery module 8 registers
                    (10848, 10856),  # Battery module 9 registers
                    (10857, 10865),  # Battery module 10 registers
                    (10866, 10874),  # Battery module 11 registers
                    (10875, 10883),  # Battery module 12 registers
                    (10884, 10892),  # Battery module 13 registers
                ]

                for start, end in battery_register_ranges:
                    if start <= register <= end:
                        return True

            return False

        except Exception as e:
            _LOGGER.error("Error checking if entity is battery entity: %s", str(e))
            return False

    async def _read_register_range(self, range_obj) -> Optional[List[int]]:
        """Read a range of registers from Modbus."""
        try:
            from homeassistant.components.modbus.const import (
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_REGISTER_INPUT,
            )

            # Ensure hub is connected
            if not getattr(self.hub, "_is_connected", False):
                _LOGGER.warning("Hub not connected, attempting to connect...")
                try:
                    await self.hub.async_pb_connect()
                    self.hub._is_connected = True
                    _LOGGER.info("Hub reconnected successfully")
                except Exception as e:
                    _LOGGER.error("Failed to reconnect hub: %s", str(e))
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
