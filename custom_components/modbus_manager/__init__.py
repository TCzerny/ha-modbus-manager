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
from .template_loader import get_template_by_name

_LOGGER = ModbusManagerLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Modbus Manager component."""
    hass.data.setdefault(DOMAIN, {})

    # Set up services
    await async_setup_services(hass)

    # Register services
    async def async_get_performance(call):
        """Get performance metrics for a device or globally."""
        device_id = call.data.get("device_id")

        if device_id:
            # Get metrics for specific device
            for entry_id, data in hass.data[DOMAIN].items():
                if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                    performance_monitor = data.get("performance_monitor")
                    if performance_monitor:
                        # Get device-specific metrics
                        device_metrics = performance_monitor.get_device_metrics(
                            data.get("prefix", "unknown")
                        )
                        if device_metrics:
                            _LOGGER.info(
                                "Performance metrics for %s: %s",
                                device_id,
                                {
                                    "total_operations": device_metrics.total_operations,
                                    "successful_operations": device_metrics.successful_operations,
                                    "failed_operations": device_metrics.failed_operations,
                                    "success_rate": round(
                                        device_metrics.success_rate, 2
                                    ),
                                    "average_duration": round(
                                        device_metrics.average_duration, 3
                                    ),
                                    "average_throughput": round(
                                        device_metrics.average_throughput, 2
                                    ),
                                },
                            )
                        else:
                            _LOGGER.info(
                                "No performance metrics available yet for device %s",
                                device_id,
                            )
                        return
                    else:
                        _LOGGER.error(
                            "Performance monitor not available for device %s", device_id
                        )
                        return

            _LOGGER.error("Device %s not found", device_id)
        else:
            # Get global metrics from all coordinators
            global_summary = {}
            for entry_id, data in hass.data[DOMAIN].items():
                performance_monitor = data.get("performance_monitor")
                if performance_monitor:
                    global_summary[
                        entry_id
                    ] = performance_monitor.get_performance_summary()

            _LOGGER.info("Global performance metrics: %s", global_summary)

    async def async_reset_performance(call):
        """Reset performance metrics for a device or globally."""
        device_id = call.data.get("device_id")

        if device_id:
            # Reset metrics for specific device
            for entry_id, data in hass.data[DOMAIN].items():
                if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                    performance_monitor = data.get("performance_monitor")
                    if performance_monitor:
                        performance_monitor.reset_metrics(
                            device_id=data.get("prefix", "unknown")
                        )
                        _LOGGER.info(
                            "Reset performance metrics for device %s", device_id
                        )
                        return
                    else:
                        _LOGGER.error(
                            "Performance monitor not available for device %s", device_id
                        )
                        return

            _LOGGER.error("Device %s not found", device_id)
        else:
            # Reset global metrics for all coordinators
            for entry_id, data in hass.data[DOMAIN].items():
                performance_monitor = data.get("performance_monitor")
                if performance_monitor:
                    performance_monitor.reset_metrics()

            _LOGGER.info("Reset performance metrics for all devices")

    # Register the services
    hass.services.async_register(DOMAIN, "get_performance", async_get_performance)
    hass.services.async_register(DOMAIN, "reset_performance", async_reset_performance)

    async def async_get_devices(call):
        """Get all configured devices from config entries."""
        try:
            all_devices = []
            entries = hass.config_entries.async_entries(DOMAIN)

            for entry in entries:
                devices = entry.data.get("devices", [])
                _LOGGER.info(
                    "Found %d devices in entry %s", len(devices), entry.entry_id
                )

                # Add entry info to each device
                for device in devices:
                    device_info = {
                        **device,
                        "entry_id": entry.entry_id,
                        "entry_title": entry.title,
                        "hub_host": entry.data.get("hub", {}).get("host")
                        or entry.data.get("host", "unknown"),
                        "hub_port": entry.data.get("hub", {}).get("port")
                        or entry.data.get("port", 502),
                    }
                    all_devices.append(device_info)

            _LOGGER.info("Returning %d total devices", len(all_devices))
            return {"devices": all_devices}
        except Exception as e:
            _LOGGER.error("Error getting devices: %s", str(e))
            return {"devices": []}

    hass.services.async_register(DOMAIN, "get_devices", async_get_devices)

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
        modbus_config = {
            "name": hub_name,
            "type": "tcp",
            "host": host,
            "port": port,
            "delay": entry.data.get("delay", 0),
            "timeout": entry.data.get("timeout", 5),
            "slave": entry.data.get("slave_id", 1),
        }

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
        device_id = call.data.get("device_id")

        if device_id:
            # Get metrics for specific device
            for entry_id, data in hass.data[DOMAIN].items():
                if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                    performance_monitor = data.get("performance_monitor")
                    if performance_monitor:
                        summary = performance_monitor.get_performance_summary()
                        _LOGGER.info(
                            "Performance metrics for %s: %s", device_id, summary
                        )
                        return
            _LOGGER.warning("Device %s not found", device_id)
        else:
            # Get global metrics from all coordinators
            global_summary = {}
            for entry_id, data in hass.data[DOMAIN].items():
                performance_monitor = data.get("performance_monitor")
                if performance_monitor:
                    global_summary[
                        entry_id
                    ] = performance_monitor.get_performance_summary()
            _LOGGER.info("Global performance metrics: %s", global_summary)

    async def performance_reset_service(call):
        """Handle performance reset service."""
        device_id = call.data.get("device_id")

        if device_id:
            # Reset metrics for specific device
            for entry_id, data in hass.data[DOMAIN].items():
                if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                    performance_monitor = data.get("performance_monitor")
                    if performance_monitor:
                        performance_monitor.reset_metrics(
                            device_id=data.get("prefix", "unknown")
                        )
                        _LOGGER.info("Reset performance metrics for %s", device_id)
                        return
            _LOGGER.warning("Device %s not found", device_id)
        else:
            # Reset global metrics for all coordinators
            for entry_id, data in hass.data[DOMAIN].items():
                performance_monitor = data.get("performance_monitor")
                if performance_monitor:
                    performance_monitor.reset_metrics()
            _LOGGER.info("Reset global performance metrics")

    async def register_optimize_service(call):
        """Handle register optimize service."""
        device_id = call.data.get("device_id")
        optimization_level = call.data.get("optimization_level", 3)

        if not device_id:
            _LOGGER.error("Device ID is required for register optimization")
            return

        # Find device and optimize registers
        for entry_id, data in hass.data[DOMAIN].items():
            if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                register_optimizer = data.get("register_optimizer")
                if register_optimizer:
                    await register_optimizer.optimize_registers(optimization_level)
                    _LOGGER.info(
                        "Optimized registers for %s with level %d",
                        device_id,
                        optimization_level,
                    )
                    return
        _LOGGER.warning("Device %s not found", device_id)

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
        """Handle template reload service - reload templates and update entity attributes without restart."""
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
        else:
            _LOGGER.info("No templates were updated")

    # Register services
    hass.services.async_register(
        DOMAIN, "performance_monitor", performance_monitor_service
    )
    hass.services.async_register(DOMAIN, "performance_reset", performance_reset_service)
    hass.services.async_register(DOMAIN, "register_optimize", register_optimize_service)
    hass.services.async_register(DOMAIN, "reload_templates", reload_templates_service)

    _LOGGER.info("Modbus Manager services registered successfully")
