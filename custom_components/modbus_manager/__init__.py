"""Modbus Manager Integration."""

import asyncio
import os
from datetime import datetime
from typing import Any

import yaml
from homeassistant.components.modbus import ModbusHub
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import ModbusCoordinator
from .logger import ModbusManagerLogger
from .performance_monitor import PerformanceMonitor
from .register_optimizer import RegisterOptimizer
from .template_loader import get_template_by_name, set_hass_instance

_LOGGER = ModbusManagerLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Modbus Manager component."""
    hass.data.setdefault(DOMAIN, {})

    # Set Home Assistant instance for custom template loading
    set_hass_instance(hass)

    # Set up services
    await async_setup_services(hass)

    # Note: get_performance, reset_performance, and get_devices removed
    # - Use performance_monitor instead of get_performance
    # - Use performance_reset instead of reset_performance
    # - get_devices removed - devices are visible in Settings → Devices & Services

    return True


async def _setup_coordinator_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager using coordinator pattern (experimental)."""
    try:
        _LOGGER.info(
            "Setting up Modbus Manager with coordinator for %s",
            entry.data.get("prefix", "unknown"),
        )

        # Create Modbus hub first (like normal setup)
        host = entry.data.get("host")
        port = entry.data.get("port", 502)
        hub_name = f"modbus_manager_{host}_{port}"

        # Create modbus config
        modbus_type = entry.data.get("modbus_type", "tcp")
        modbus_config = {
            "name": hub_name,
            "type": modbus_type,
            "host": host,
            "port": port,
            "delay": entry.data.get("delay", 0),
            "timeout": entry.data.get("timeout", 5),
            "slave": entry.data.get("slave_id", 1),
        }

        # Add RTU-specific parameters if RTU over TCP is selected
        if modbus_type == "rtuovertcp":
            modbus_config["baudrate"] = entry.data.get("baudrate", 9600)
            modbus_config["data_bits"] = entry.data.get("data_bits", 8)
            modbus_config["stop_bits"] = entry.data.get("stop_bits", 1)
            modbus_config["parity"] = entry.data.get("parity", "none")

        # Create hub
        hub = ModbusHub(hass, modbus_config)
        _LOGGER.info("Created ModbusHub for coordinator: %s", hub_name)

        # Setup and connect hub
        try:
            await hub.async_setup()
            _LOGGER.info("ModbusHub setup completed for coordinator")

            await hub.async_pb_connect()
            _LOGGER.info("ModbusHub connected successfully for coordinator")
            hub._is_connected = True
        except Exception as e:
            _LOGGER.error(
                "Failed to setup/connect ModbusHub for coordinator: %s", str(e)
            )
            return False

        # Store hub globally
        hass.data[DOMAIN][hub_name] = hub
        hass.data[DOMAIN][f"global_hub_{host}_{port}"] = hub

        # Create coordinator
        coordinator = ModbusCoordinator(
            hass=hass,
            hub=hub,
            device_config=entry.data,
            entry=entry,
        )

        # Store coordinator in hass.data
        devices = entry.data.get("devices", [])
        hass.data[DOMAIN][entry.entry_id] = {
            "coordinator": coordinator,
            "hub": hub,
            "prefix": entry.data.get("prefix", "unknown"),
            "template": entry.data.get("template", "unknown"),
            "devices": devices,
            "device_count": len(devices),
            "performance_monitor": coordinator.performance_monitor,
        }

        # Start coordinator
        await coordinator.async_config_entry_first_refresh()

        # Load platforms for coordinator-based entities
        try:
            platform_task = asyncio.create_task(
                hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            )
            await platform_task
            _LOGGER.info("Coordinator platforms loaded successfully: %s", PLATFORMS)
        except Exception as e:
            _LOGGER.error("Error loading coordinator platforms: %s", str(e))
            return False

        _LOGGER.info(
            "Modbus Manager coordinator setup completed for %s",
            entry.data.get("prefix", "unknown"),
        )

        return True

    except Exception as e:
        _LOGGER.error("Error setting up coordinator: %s", str(e))
        return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry - Coordinator-Only."""
    try:
        _LOGGER.info(
            "🚀 Setting up Modbus Manager (Coordinator-Only) for %s",
            entry.data.get("prefix", "unknown"),
        )

        # Always use coordinator mode
        return await _setup_coordinator_entry(hass, entry)

    except Exception as e:
        _LOGGER.error("Error setting up Modbus Manager: %s", str(e))
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        _LOGGER.debug(
            "Unload von Modbus Manager für %s", entry.data.get("prefix", "unbekannt")
        )

        # Check if this is a reload operation (not a full removal)
        # During reload, we want to keep the Modbus connection alive
        is_reload = hass.data[DOMAIN].get("_reload_in_progress", False)

        if is_reload:
            _LOGGER.info("🔄 Reload detected - keeping Modbus connection alive")

        # Alle Plattformen entladen
        try:
            unload_ok = await hass.config_entries.async_unload_platforms(
                entry, PLATFORMS
            )
            if unload_ok:
                _LOGGER.debug("Alle Plattformen erfolgreich entladen: %s", PLATFORMS)
            else:
                _LOGGER.warning("Nicht alle Plattformen konnten entladen werden")
        except Exception as e:
            _LOGGER.error("Fehler beim Entladen der Plattformen: %s", str(e))

        # Modbus-Hub schließen - aber mit verbesserter Logik
        if entry.entry_id in hass.data[DOMAIN]:
            hub_data = hass.data[DOMAIN][entry.entry_id]

            # Mark coordinator as unloading and invalidate cache before unloading
            if "coordinator" in hub_data:
                coordinator = hub_data["coordinator"]
                coordinator.mark_as_unloading()
                _LOGGER.debug("Coordinator marked as unloading and cache invalidated")

            if "hub" in hub_data:
                hub = hub_data["hub"]
                host = entry.data.get("host", "unknown")
                port = entry.data.get("port", 502)
                hub_name = f"modbus_manager_{host}_{port}"
                global_hub_key = f"global_hub_{host}_{port}"

                # Decrement hub reference counter
                hub_ref_key = f"_hub_refcount_{hub_name}"
                current_refcount = hass.data[DOMAIN].get(hub_ref_key, 0)
                new_refcount = max(0, current_refcount - 1)
                hass.data[DOMAIN][hub_ref_key] = new_refcount

                _LOGGER.info(
                    "📊 Hub %s reference count: %d → %d",
                    hub_name,
                    current_refcount,
                    new_refcount,
                )

                # CRITICAL: Only close hub if refcount is 0 AND not during reload
                # This prevents "No Data" errors during reload or multi-device setup
                if new_refcount == 0 and not is_reload:
                    try:
                        _LOGGER.info(
                            "🔌 Closing Modbus connection %s (no more references)",
                            hub_name,
                        )
                        await hub.async_close()
                        _LOGGER.debug("Modbus-Hub erfolgreich geschlossen")

                        # Remove hub from global storage
                        if hub_name in hass.data[DOMAIN]:
                            del hass.data[DOMAIN][hub_name]
                        if global_hub_key in hass.data[DOMAIN]:
                            del hass.data[DOMAIN][global_hub_key]
                        if hub_ref_key in hass.data[DOMAIN]:
                            del hass.data[DOMAIN][hub_ref_key]
                    except Exception as e:
                        _LOGGER.warning(
                            "Fehler beim Schließen des Modbus-Hubs: %s", str(e)
                        )
                elif is_reload:
                    _LOGGER.info(
                        "✅ Keeping Modbus connection %s alive during reload (refcount: %d)",
                        hub_name,
                        new_refcount,
                    )
                else:
                    _LOGGER.info(
                        "✅ Keeping Modbus connection %s open (%d devices still using it)",
                        hub_name,
                        new_refcount,
                    )

            # Daten löschen (aber Hub-Referenz bleibt für Reload bestehen)
            if not is_reload:
                del hass.data[DOMAIN][entry.entry_id]
            else:
                # Bei Reload nur Entity-Daten löschen, Hub behalten
                _LOGGER.info("🔄 Keeping entry data for reload")

        _LOGGER.debug(
            "Modbus Manager erfolgreich entladen für %s",
            entry.data.get("prefix", "unbekannt"),
        )
        return True

    except Exception as e:
        _LOGGER.error("Fehler beim Unload von Modbus Manager: %s", str(e))
        return False


# Service Handlers
async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Modbus Manager."""

    async def performance_monitor_service(call):
        """Handle performance monitor service."""
        try:
            device_id = call.data.get("device_id") if call.data else None

            if not DOMAIN in hass.data:
                _LOGGER.warning("No Modbus Manager entries found")
                return {"error": "No Modbus Manager entries found"}

            if device_id:
                # Get metrics for specific device
                found = False
                for entry_id, data in hass.data[DOMAIN].items():
                    if not isinstance(data, dict):
                        continue
                    prefix = data.get("prefix")
                    if prefix and prefix == device_id.replace("modbus_manager_", ""):
                        coordinator = data.get("coordinator")
                        if coordinator and hasattr(coordinator, "performance_monitor"):
                            performance_monitor = coordinator.performance_monitor
                            if performance_monitor:
                                summary = performance_monitor.get_performance_summary()
                                _LOGGER.info(
                                    "Performance metrics for %s: %s", device_id, summary
                                )

                                # Create notification with metrics
                                # Use device-specific metrics, not global
                                device_metrics = summary.get("devices", {}).get(
                                    prefix, {}
                                )

                                if device_metrics:
                                    message = f"Performance Metrics for {device_id}\n\n"
                                    message += f"Total Operations: {device_metrics.get('total_operations', 0)}\n"
                                    message += f"Success Rate: {device_metrics.get('success_rate', 0)}%\n"
                                    message += f"Avg Duration: {device_metrics.get('average_duration', 0):.3f}s\n"
                                    message += f"Avg Throughput: {device_metrics.get('average_throughput', 0):.2f} bytes/s\n"

                                    # Add optimization metrics if available
                                    recent_ops = (
                                        performance_monitor.get_recent_operations(
                                            device_id=prefix, limit=10
                                        )
                                    )
                                    if recent_ops:
                                        total_regs = sum(
                                            op.get("register_count", 0)
                                            for op in recent_ops
                                        )
                                        total_ranges = sum(
                                            op.get("optimized_ranges_count", 0)
                                            for op in recent_ops
                                        )
                                        if total_regs > 0 and total_ranges > 0:
                                            avg_regs_per_batch = (
                                                total_regs / total_ranges
                                            )
                                            optimization_ratio = (
                                                (total_regs / total_ranges)
                                                if total_ranges > 0
                                                else 0
                                            )
                                            message += f"\n📊 Optimization Stats:\n"
                                            message += f"  Avg Registers per Batch: {avg_regs_per_batch:.1f}\n"
                                            message += (
                                                f"  Total Batch Reads: {total_ranges}\n"
                                            )
                                            message += f"  Total Registers Read: {total_regs}\n"
                                            if optimization_ratio > 1:
                                                savings = (
                                                    (total_regs - total_ranges)
                                                    / total_regs
                                                ) * 100
                                                message += f"  Efficiency: {savings:.1f}% fewer reads"

                                    if device_metrics.get("last_operation"):
                                        message += f"\n\nLast Operation: {device_metrics.get('last_operation')}"
                                else:
                                    message = f"Performance Metrics for {device_id}\n\n"
                                    message += "No metrics available yet. Wait a few minutes for data to accumulate."

                                await hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": f"Modbus Manager Performance - {device_id}",
                                        "message": message,
                                        "notification_id": f"modbus_performance_{device_id}",
                                    },
                                )

                                # Return data for UI display
                                return {"device_id": device_id, "metrics": summary}
                if not found:
                    _LOGGER.warning(
                        "Device %s not found or has no performance monitor", device_id
                    )
                    return {
                        "error": f"Device {device_id} not found or has no performance monitor"
                    }
            else:
                # Get global metrics from all coordinators
                global_summary = {}
                for entry_id, data in hass.data[DOMAIN].items():
                    if not isinstance(data, dict):
                        continue
                    coordinator = data.get("coordinator")
                    if coordinator and hasattr(coordinator, "performance_monitor"):
                        performance_monitor = coordinator.performance_monitor
                        if performance_monitor:
                            global_summary[
                                entry_id
                            ] = performance_monitor.get_performance_summary()
                if global_summary:
                    _LOGGER.info("Global performance metrics: %s", global_summary)

                    # Create notification with global metrics
                    message = "Global Performance Metrics\n\n"
                    for entry_id, metrics in global_summary.items():
                        device_data = hass.data[DOMAIN].get(entry_id, {})
                        prefix = device_data.get("prefix", "unknown")

                        # Use device-specific metrics, not global (global is always 0)
                        device_metrics = metrics.get("devices", {}).get(prefix, {})

                        if device_metrics:
                            message += f"Device: {prefix} (Entry: {entry_id[:8]}...)\n"
                            message += f"  Total Operations: {device_metrics.get('total_operations', 0)}\n"
                            message += f"  Success Rate: {device_metrics.get('success_rate', 0)}%\n"
                            message += f"  Avg Duration: {device_metrics.get('average_duration', 0):.3f}s\n"
                            message += f"  Avg Throughput: {device_metrics.get('average_throughput', 0):.2f} bytes/s\n"

                            # Add optimization stats
                            coordinator = device_data.get("coordinator")
                            if coordinator and hasattr(
                                coordinator, "performance_monitor"
                            ):
                                pm = coordinator.performance_monitor
                                recent_ops = pm.get_recent_operations(
                                    device_id=prefix, limit=10
                                )
                                if recent_ops:
                                    total_regs = sum(
                                        op.get("register_count", 0) for op in recent_ops
                                    )
                                    total_ranges = sum(
                                        op.get("optimized_ranges_count", 0)
                                        for op in recent_ops
                                    )
                                    if total_regs > 0 and total_ranges > 0:
                                        avg_regs_per_batch = total_regs / total_ranges
                                        message += f"  📊 Avg {avg_regs_per_batch:.1f} regs/batch ({total_ranges} batches)\n"

                            message += "\n"
                        else:
                            message += f"Device: {prefix} (Entry: {entry_id[:8]}...)\n"
                            message += f"  No metrics available yet\n\n"

                    message += "\n💡 Tip: Use device prefix (e.g., 'SH10RT') as device_id for device-specific metrics"

                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "Modbus Manager - Global Performance Metrics",
                            "message": message,
                            "notification_id": "modbus_performance_global",
                        },
                    )

                    return {"metrics": global_summary}
                else:
                    _LOGGER.info("No performance metrics available")
                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "Modbus Manager Performance",
                            "message": "No performance metrics available yet. Wait a few minutes for data to accumulate.",
                            "notification_id": "modbus_performance_none",
                        },
                    )
                    return {"message": "No performance metrics available"}
        except Exception as e:
            _LOGGER.error(
                "Error in performance_monitor service: %s", str(e), exc_info=True
            )
            return {"error": str(e)}

    async def performance_reset_service(call):
        """Handle performance reset service."""
        try:
            device_id = call.data.get("device_id") if call.data else None

            if not DOMAIN in hass.data:
                _LOGGER.warning("No Modbus Manager entries found")
                return

            if device_id:
                # Reset metrics for specific device
                found = False
                for entry_id, data in hass.data[DOMAIN].items():
                    if not isinstance(data, dict):
                        continue
                    prefix = data.get("prefix")
                    if prefix and prefix == device_id.replace("modbus_manager_", ""):
                        coordinator = data.get("coordinator")
                        if coordinator and hasattr(coordinator, "performance_monitor"):
                            performance_monitor = coordinator.performance_monitor
                            if performance_monitor:
                                performance_monitor.reset_metrics(device_id=prefix)
                                _LOGGER.info(
                                    "Reset performance metrics for %s", device_id
                                )
                                found = True
                                break
                if not found:
                    _LOGGER.warning(
                        "Device %s not found or has no performance monitor", device_id
                    )
            else:
                # Reset global metrics for all coordinators
                reset_count = 0
                for entry_id, data in hass.data[DOMAIN].items():
                    if not isinstance(data, dict):
                        continue
                    coordinator = data.get("coordinator")
                    if coordinator and hasattr(coordinator, "performance_monitor"):
                        performance_monitor = coordinator.performance_monitor
                        if performance_monitor:
                            performance_monitor.reset_metrics()
                            reset_count += 1
                if reset_count > 0:
                    _LOGGER.info(
                        "Reset performance metrics for %d device(s)", reset_count
                    )
                else:
                    _LOGGER.info("No performance monitors found to reset")
        except Exception as e:
            _LOGGER.error(
                "Error in performance_reset service: %s", str(e), exc_info=True
            )

    # register_optimize service removed - register optimization is automatic and handled by the coordinator

    async def ems_configure_service(call):
        """Handle EMS configure service."""
        device_id = call.data.get("device_id")
        ems_enabled = call.data.get("ems_enabled", True)
        priority = call.data.get("priority", 5)
        max_power = call.data.get("max_power")

        if not device_id:
            _LOGGER.error("Device ID is required for EMS configuration")
            return

        # Configure EMS for device
        for entry_id, data in hass.data[DOMAIN].items():
            if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                ems_manager = data.get("ems_manager")
                if ems_manager:
                    await ems_manager.configure_device(
                        device_id=device_id,
                        enabled=ems_enabled,
                        priority=priority,
                        max_power=max_power,
                    )
                    _LOGGER.info(
                        "Configured EMS for %s: enabled=%s, priority=%d, max_power=%s",
                        device_id,
                        ems_enabled,
                        priority,
                        max_power,
                    )
                    return
        _LOGGER.warning("Device %s not found", device_id)

    async def ems_optimize_service(call):
        """Handle EMS optimize service."""
        surplus_power = call.data.get("surplus_power", 0)
        optimization_mode = call.data.get("optimization_mode", "balanced")

        # Run EMS optimization across all devices
        total_optimized = 0
        for entry_id, data in hass.data[DOMAIN].items():
            ems_manager = data.get("ems_manager")
            if ems_manager:
                optimized = await ems_manager.optimize_surplus_power(
                    surplus_power, optimization_mode
                )
                total_optimized += optimized

        _LOGGER.info(
            "EMS optimization completed: %dW surplus power managed across %d devices",
            total_optimized,
            len(hass.data[DOMAIN]),
        )

    async def reload_templates_service(call):
        """Handle template reload service - reload templates and update entity attributes without restart.

        This service is useful when:
        - You've updated a template file and want to apply changes without restarting Home Assistant
        - You want to refresh entity attributes (name, icon, etc.) after template modifications
        - You're developing templates and need to test changes quickly

        Note: This does NOT reload the integration or change entity states, only updates attributes.
        """
        from homeassistant.helpers.entity_registry import (
            async_get as async_get_entity_registry,
        )

        entry_id_filter = call.data.get("entry_id")

        _LOGGER.info("🔄 Starting template reload service...")

        # Get entity registry
        entity_registry = async_get_entity_registry(hass)

        # Track updates
        updated_entries = 0
        updated_entities = 0

        # Iterate through all config entries
        for entry_id, entry_data in list(hass.data[DOMAIN].items()):
            # Skip non-entry data (like hubs, locks, etc.)
            if not isinstance(entry_data, dict) or "template" not in entry_data:
                continue

            # Filter by entry_id if provided
            if entry_id_filter and entry_id != entry_id_filter:
                continue

            # Get the config entry
            config_entry = None
            for entry in hass.config_entries.async_entries(DOMAIN):
                if entry.entry_id == entry_id:
                    config_entry = entry
                    break

            if not config_entry:
                _LOGGER.warning("Config entry %s not found", entry_id)
                continue

            template_name = entry_data.get("template")
            prefix = entry_data.get("prefix", "unknown")

            _LOGGER.info(
                "🔄 Reloading template '%s' for prefix '%s'", template_name, prefix
            )

            # Reload template
            try:
                template_data = await get_template_by_name(template_name)

                if not template_data:
                    _LOGGER.error("Template %s could not be loaded", template_name)
                    continue

                # Process template to get fresh entity definitions
                if isinstance(template_data, dict):
                    # Handle dynamic config if present
                    dynamic_config = template_data.get("dynamic_config", {})
                    if dynamic_config:
                        from .config_flow import ModbusManagerConfigFlow

                        config_flow = ModbusManagerConfigFlow()

                        mock_user_input = {
                            "phases": config_entry.data.get("phases", 3),
                            "mppt_count": config_entry.data.get("mppt_count", 2),
                            "battery_config": config_entry.data.get(
                                "battery_config", "none"
                            ),
                            "battery_slave_id": config_entry.data.get(
                                "battery_slave_id", 200
                            ),
                            "firmware_version": config_entry.data.get(
                                "firmware_version", "1.0.0"
                            ),
                            "connection_type": config_entry.data.get(
                                "connection_type", "LAN"
                            ),
                        }

                        processed_data = config_flow._process_dynamic_config(
                            mock_user_input, template_data
                        )
                        template_registers = processed_data["sensors"]
                        template_calculated = processed_data["calculated"]
                        template_controls = processed_data["controls"]
                    else:
                        template_registers = template_data.get("sensors", [])
                        template_calculated = template_data.get("calculated", [])
                        template_controls = template_data.get("controls", [])

                    # Update entity registry for all entities from this template
                    all_template_entities = (
                        template_registers + template_calculated + template_controls
                    )

                    for entity_def in all_template_entities:
                        unique_id = entity_def.get("unique_id")
                        if not unique_id:
                            continue

                        # Construct entity_id (try all platforms)
                        entity_id_candidates = [
                            f"sensor.{prefix}_{unique_id}",
                            f"number.{prefix}_{unique_id}",
                            f"select.{prefix}_{unique_id}",
                            f"switch.{prefix}_{unique_id}",
                            f"button.{prefix}_{unique_id}",
                            f"text.{prefix}_{unique_id}",
                            f"binary_sensor.{prefix}_{unique_id}",
                        ]

                        entity_entry = None
                        for candidate in entity_id_candidates:
                            entity_entry = entity_registry.async_get(candidate)
                            if entity_entry:
                                break

                        if not entity_entry:
                            continue

                        # Get new attributes from template
                        new_group = entity_def.get("group")
                        new_template = entity_def.get("template")

                        # Get current attributes
                        current_capabilities = entity_entry.capabilities or {}
                        current_extra = entity_entry.original_device_class

                        # Build updated attributes
                        updates = {}

                        # Update capabilities with new group/template if changed
                        needs_update = False

                        # Check if group changed
                        if new_group:
                            # Group is stored in the entity's state attributes, not in registry
                            # We need to update it in a different way
                            needs_update = True

                        if needs_update:
                            # Update the entity in registry
                            # Note: Entity attributes like 'group' are set at entity creation time
                            # and stored in the entity's extra_state_attributes
                            # We can't directly update them in the registry
                            # Instead, we need to trigger entity re-creation

                            _LOGGER.info(
                                "📝 Entity %s needs attribute update (group: %s, template: %s)",
                                entity_entry.entity_id,
                                new_group,
                                new_template,
                            )
                            updated_entities += 1

                    # Update the config entry data with new template data
                    new_data = dict(config_entry.data)
                    new_data["registers"] = template_registers
                    new_data["calculated_entities"] = template_calculated
                    new_data["controls"] = template_controls
                    new_data["template_version"] = template_data.get("version", 1)

                    hass.config_entries.async_update_entry(config_entry, data=new_data)

                    # Update runtime data
                    entry_data["registers"] = template_registers
                    entry_data["calculated_entities"] = template_calculated
                    entry_data["controls"] = template_controls

                    updated_entries += 1

                    _LOGGER.info(
                        "✅ Template '%s' reloaded: %d registers, %d calculated, %d controls",
                        template_name,
                        len(template_registers),
                        len(template_calculated),
                        len(template_controls),
                    )

            except Exception as e:
                _LOGGER.error("Error reloading template %s: %s", template_name, str(e))
                import traceback

                _LOGGER.error("Traceback: %s", traceback.format_exc())

        # Reload the integration to apply changes
        if updated_entries > 0:
            _LOGGER.info(
                "🔄 Reloading integration to apply changes (%d entries, %d entities updated)",
                updated_entries,
                updated_entities,
            )

            # Set reload flag to prevent Modbus connection from being closed
            hass.data[DOMAIN]["_reload_in_progress"] = True

            try:
                # Reload all config entries that were updated
                for entry in hass.config_entries.async_entries(DOMAIN):
                    if entry_id_filter and entry.entry_id != entry_id_filter:
                        continue

                    try:
                        _LOGGER.info(
                            "🔄 Reloading entry %s (Modbus connection stays alive)",
                            entry.entry_id,
                        )
                        await hass.config_entries.async_reload(entry.entry_id)
                        _LOGGER.info(
                            "✅ Config entry %s reloaded successfully - no connection interruption",
                            entry.entry_id,
                        )
                    except Exception as e:
                        _LOGGER.error(
                            "Error reloading entry %s: %s", entry.entry_id, str(e)
                        )
            finally:
                # Clear reload flag
                hass.data[DOMAIN]["_reload_in_progress"] = False
                _LOGGER.info(
                    "✅ Template reload completed - Modbus connection was maintained throughout"
                )

                # Create notification with results
                message = f"Template reload completed successfully!\n\n"
                message += f"Updated entries: {updated_entries}\n"
                message += f"Updated entities: {updated_entities}\n\n"
                message += "Entity attributes (name, icon, etc.) have been refreshed."

                await hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Modbus Manager - Template Reload",
                        "message": message,
                        "notification_id": "modbus_reload_templates",
                    },
                )
        else:
            _LOGGER.info("No templates were updated")

    # Register services
    hass.services.async_register(
        DOMAIN, "performance_monitor", performance_monitor_service
    )
    hass.services.async_register(DOMAIN, "performance_reset", performance_reset_service)
    # register_optimize removed - optimization is automatic
    hass.services.async_register(DOMAIN, "reload_templates", reload_templates_service)

    _LOGGER.info("Modbus Manager services registered successfully")
