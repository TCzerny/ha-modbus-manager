"""Modbus Coordinator for centralized data management."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

                device_info = create_device_info_dict(
                    hass=self.hass,
                    host=host,
                    port=port,
                    slave_id=slave_id,
                    prefix=prefix,
                    template_name=template_name,
                    config_entry_id=self.entry.entry_id,
                )

                # Add type field, device info, and combine
                for register in processed_registers:
                    register["type"] = "sensor"
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
                    all_registers.append(register)

                for register in processed_controls:
                    register["slave_id"] = slave_id
                    register["device_info"] = device_info
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

                device_info = create_device_info_dict(
                    hass=self.hass,
                    host=host,
                    port=port,
                    slave_id=slave_id,
                    prefix=prefix,
                    template_name=template_name,
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

            # Extract all configuration values
            config = {
                "modules": model_config.get("modules"),
                "mppt_count": model_config.get("mppt_count"),
                "string_count": model_config.get("string_count"),
                "phases": model_config.get("phases"),
                "type_code": model_config.get("type_code"),
            }

            _LOGGER.debug(
                "Extracted config from model %s: modules=%s, mppt=%s, strings=%s, phases=%s",
                selected_model,
                config.get("modules"),
                config.get("mppt_count"),
                config.get("string_count"),
                config.get("phases"),
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
                template_name_value = entity.get("name")
                if template_name_value:
                    if not template_name_value.startswith(f"{prefix} "):
                        processed_entity["name"] = f"{prefix} {template_name_value}"
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
                    numeric_patterns = [
                        rf"{base_name}(\d+)",  # mppt1, mppt2
                        rf"{base_name}_(\d+)",  # mppt_1, mppt_2, module_1
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

                # Process name - avoid double prefixes
                template_name_value = entity.get("name")
                if template_name_value:
                    if not template_name_value.startswith(f"{entity_prefix} "):
                        processed_entity[
                            "name"
                        ] = f"{entity_prefix} {template_name_value}"
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
            call_type = (
                CALL_TYPE_REGISTER_INPUT
                if register_type == "input"
                else CALL_TYPE_REGISTER_HOLDING
            )

            # Get slave ID from first register
            slave_id = range_obj.registers[0].get("slave_id", 1)

            _LOGGER.debug(
                "Reading registers %d-%d (slave_id: %d, type: %s)",
                range_obj.start_address,
                range_obj.end_address,
                slave_id,
                register_type,
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

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down ModbusCoordinator")
        # Cancel any pending updates
        if hasattr(self, "_update_task") and self._update_task:
            self._update_task.cancel()
        # Clear data
        self.register_data.clear()
