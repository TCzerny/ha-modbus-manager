"""Modbus Manager Integration."""

import asyncio
import os
from datetime import datetime
from types import MappingProxyType
from typing import Any

import yaml
from homeassistant.components.modbus import ModbusHub
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, PLATFORMS
from .coordinator import ModbusCoordinator
from .logger import ModbusManagerLogger
from .performance_monitor import PerformanceMonitor
from .register_optimizer import RegisterOptimizer
from .template_loader import get_template_by_name, set_hass_instance

_LOGGER = ModbusManagerLogger(__name__)


def _build_device_entry_id(device: dict[str, Any]) -> str:
    """Build stable logical device id."""
    prefix = str(device.get("prefix", "device")).strip() or "device"
    slave_id = str(device.get("slave_id", 1)).strip() or "1"
    template = str(device.get("template", "template")).strip() or "template"
    return f"{prefix}_{slave_id}_{template}"


def _normalize_device_record(device: dict[str, Any]) -> dict[str, Any]:
    """Normalize device shape for subentry sync."""
    normalized = dict(device)
    if not normalized.get("type"):
        normalized["type"] = "inverter"
    normalized["device_entry_id"] = normalized.get(
        "device_entry_id", _build_device_entry_id(normalized)
    )
    return normalized


async def _sync_device_subentries(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Sync config subentries from entry.data['devices'].

    Keeps true HA subentries aligned with the current devices list.
    """
    devices = entry.data.get("devices", [])
    if not isinstance(devices, list):
        return

    normalized_devices = [
        _normalize_device_record(device)
        for device in devices
        if isinstance(device, dict)
    ]
    existing_device_subentries = {
        subentry.subentry_id: subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "device"
    }
    existing_by_unique_id = {
        subentry.unique_id: subentry
        for subentry in existing_device_subentries.values()
        if subentry.unique_id
    }

    # Mark setup as initialized once we have at least one persisted device subentry.
    subentries_initialized = bool(entry.data.get("device_subentries_initialized"))
    if existing_by_unique_id and not subentries_initialized:
        subentries_initialized = True

    new_data = dict(entry.data)
    data_changed = False

    pending_device_id = entry.data.get("pending_subentry_device_id")

    # After initialization, treat subentries as source of truth for device existence.
    # If a user deletes a subentry in HA UI, prune the matching device record from devices[]
    # so it doesn't come back on next restart.
    #
    # Exception: keep one pending device id from add flow until its subentry exists
    # to avoid races between async_update_entry + async_schedule_reload + subentry persist.
    if subentries_initialized:
        existing_ids = set(existing_by_unique_id.keys())
        filtered_devices = [
            device
            for device in normalized_devices
            if (
                device.get("device_entry_id") in existing_ids
                or device.get("device_entry_id") == pending_device_id
            )
        ]
        if len(filtered_devices) != len(normalized_devices):
            _LOGGER.info(
                "Pruned %d device(s) removed via subentry delete for entry %s",
                len(normalized_devices) - len(filtered_devices),
                entry.entry_id,
            )
            normalized_devices = filtered_devices
            new_data["devices"] = normalized_devices
            data_changed = True

    wanted_ids = {device.get("device_entry_id") for device in normalized_devices}

    for device in normalized_devices:
        device_id = device.get("device_entry_id")
        if not device_id:
            continue

        title = (
            f"{device.get('prefix', 'unknown')} | "
            f"slave {device.get('slave_id', '?')} | "
            f"{device.get('template', 'unknown')}"
        )
        data = {
            "device_entry_id": device_id,
            "type": device.get("type", "inverter"),
            "template": device.get("template"),
            "prefix": device.get("prefix"),
            "slave_id": device.get("slave_id"),
            "selected_model": device.get("selected_model"),
            "firmware_version": device.get("firmware_version"),
            "connection_type": device.get("connection_type"),
            "meter_type": device.get("meter_type"),
        }

        existing_subentry = existing_by_unique_id.get(device_id)
        if existing_subentry:
            hass.config_entries.async_update_subentry(
                entry=entry,
                subentry=existing_subentry,
                title=title,
                data=data,
                unique_id=device_id,
            )
        elif not subentries_initialized:
            # Bootstrap only once. After initialization, missing subentries mean
            # the corresponding device was intentionally deleted.
            hass.config_entries.async_add_subentry(
                entry=entry,
                subentry=ConfigSubentry(
                    data=MappingProxyType(data),
                    subentry_type="device",
                    title=title,
                    unique_id=device_id,
                ),
            )

    # Remove stale device subentries no longer present in devices[]
    for subentry in existing_device_subentries.values():
        if subentry.unique_id and subentry.unique_id not in wanted_ids:
            hass.config_entries.async_remove_subentry(
                entry=entry, subentry_id=subentry.subentry_id
            )

    # Clear pending add marker once subentry exists (or no longer relevant).
    if pending_device_id:
        if (
            pending_device_id in existing_by_unique_id
            or pending_device_id not in wanted_ids
        ):
            new_data.pop("pending_subentry_device_id", None)
            data_changed = True

    if not entry.data.get("device_subentries_initialized"):
        new_data["device_subentries_initialized"] = True
        data_changed = True

    if data_changed:
        hass.config_entries.async_update_entry(entry, data=new_data)


async def _relink_entities_to_device_subentries(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Assign existing entities to matching device subentries by prefix.

    This migrates previously created entities (without subentry link) so they no
    longer appear under "devices not assigned to a subentry".
    """
    try:
        entity_registry = er.async_get(hass)
        devices = entry.data.get("devices", [])
        if not isinstance(devices, list):
            return

        # Build mapping from prefix -> subentry_id using device_entry_id(unique_id)
        prefix_to_subentry_id: dict[str, str] = {}
        for device in devices:
            if not isinstance(device, dict):
                continue
            normalized = _normalize_device_record(device)
            device_entry_id = normalized.get("device_entry_id")
            prefix = str(normalized.get("prefix", "")).strip().lower()
            if not device_entry_id or not prefix:
                continue
            for subentry in entry.subentries.values():
                if (
                    subentry.subentry_type == "device"
                    and subentry.unique_id == device_entry_id
                ):
                    prefix_to_subentry_id[prefix] = subentry.subentry_id
                    break

        if not prefix_to_subentry_id:
            return

        updated = 0
        for reg_entry in list(entity_registry.entities.values()):
            if reg_entry.config_entry_id != entry.entry_id:
                continue
            unique_id = reg_entry.unique_id or ""
            if "_" not in unique_id:
                continue
            entity_prefix = unique_id.split("_", 1)[0].strip().lower()
            target_subentry_id = prefix_to_subentry_id.get(entity_prefix)
            if not target_subentry_id:
                continue
            if reg_entry.config_subentry_id == target_subentry_id:
                continue
            entity_registry.async_update_entity(
                reg_entry.entity_id, config_subentry_id=target_subentry_id
            )
            updated += 1

        if updated:
            _LOGGER.info(
                "Assigned %d existing entities to device subentries for entry %s",
                updated,
                entry.entry_id,
            )
    except Exception as e:
        _LOGGER.warning("Could not relink entities to subentries: %s", str(e))


async def _relink_devices_to_subentries(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Relink device registry entries from legacy (None) to concrete subentries."""
    try:
        device_registry = dr.async_get(hass)
        devices = entry.data.get("devices", [])
        if not isinstance(devices, list):
            return

        hub_config = entry.data.get("hub", {})
        host = hub_config.get("host") or entry.data.get("host", "unknown")
        port = hub_config.get("port") or entry.data.get("port", 502)

        moved = 0
        for device in devices:
            if not isinstance(device, dict):
                continue
            normalized = _normalize_device_record(device)
            device_entry_id = normalized.get("device_entry_id")
            slave_id = normalized.get("slave_id", 1)
            if not device_entry_id:
                continue

            target_subentry_id = None
            for subentry in entry.subentries.values():
                if (
                    subentry.subentry_type == "device"
                    and subentry.unique_id == device_entry_id
                ):
                    target_subentry_id = subentry.subentry_id
                    break
            if not target_subentry_id:
                continue

            identifier = f"modbus_manager_{host}_{port}_slave_{slave_id}"
            device_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, identifier)}
            )
            if not device_entry:
                continue

            # Ensure device is linked to the concrete subentry.
            device_registry.async_update_device(
                device_entry.id,
                add_config_entry_id=entry.entry_id,
                add_config_subentry_id=target_subentry_id,
            )
            # Remove legacy unassigned link for this entry to avoid duplicate UI groups.
            device_registry.async_update_device(
                device_entry.id,
                remove_config_entry_id=entry.entry_id,
                remove_config_subentry_id=None,
            )
            moved += 1

        if moved:
            _LOGGER.info(
                "Relinked %d device registry entries to concrete subentries for %s",
                moved,
                entry.entry_id,
            )
    except Exception as e:
        _LOGGER.warning("Could not relink device registry entries: %s", str(e))


async def _cleanup_stale_registry_entities(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: ModbusCoordinator
) -> None:
    """Remove stale entities no longer present in current coordinator entity set."""
    try:
        entity_registry = er.async_get(hass)
        managed_domains = {
            "sensor",
            "number",
            "select",
            "switch",
            "button",
            "text",
            "binary_sensor",
        }

        entities_dict = await coordinator._collect_all_registers()
        expected_unique_ids = {
            entity.get("unique_id")
            for category in ["sensors", "controls", "calculated", "binary_sensors"]
            for entity in entities_dict.get(category, [])
            if entity.get("unique_id")
        }
        normalized_expected = {
            str(unique_id).strip().lower()
            for unique_id in expected_unique_ids
            if unique_id
        }

        if not normalized_expected:
            return

        def _matches_expected(registry_unique_id: str) -> bool:
            normalized_registry = str(registry_unique_id).strip().lower()
            if not normalized_registry:
                return False
            return normalized_registry in normalized_expected

        removed = 0
        for reg_entry in list(entity_registry.entities.values()):
            if reg_entry.config_entry_id != entry.entry_id:
                continue
            domain = reg_entry.entity_id.split(".", 1)[0]
            if domain not in managed_domains:
                continue
            unique_id = reg_entry.unique_id or ""
            if _matches_expected(unique_id):
                continue
            entity_registry.async_remove(reg_entry.entity_id)
            removed += 1

        if removed:
            _LOGGER.info(
                "Removed %d stale registry entities for entry %s after dynamic filtering",
                removed,
                entry.entry_id,
            )
    except Exception as e:
        _LOGGER.warning("Could not cleanup stale registry entities: %s", str(e))


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a config entry to the latest version.

    Home Assistant calls this function during setup when entry.version is older.
    """
    try:
        from .config_flow import ModbusManagerConfigFlow

        flow = ModbusManagerConfigFlow()
        _LOGGER.info(
            "Running integration migration handler for entry %s (version %d -> %d)",
            entry.entry_id,
            entry.version,
            flow.VERSION,
        )
        return await flow.async_migrate_entry(hass, entry)
    except Exception as e:
        _LOGGER.error(
            "Integration migration failed for entry %s: %s", entry.entry_id, str(e)
        )
        return False


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
        # Support both modbus_type (new) and type (legacy) for backward compatibility
        modbus_type = entry.data.get("modbus_type") or entry.data.get("type", "tcp")
        modbus_config = {
            "name": hub_name,
            "type": modbus_type,
            "host": host,
            "port": port,
            "delay": entry.data.get("delay", 0),
            "message_wait_milliseconds": entry.data.get(
                "message_wait_milliseconds",
                entry.data.get("request_delay", 100),
            ),
            "timeout": entry.data.get("timeout", 5),
            "slave": entry.data.get("slave_id", 1),
        }

        # Create hub
        hub = ModbusHub(hass, modbus_config)
        _LOGGER.debug("Created ModbusHub for coordinator: %s", hub_name)

        # Setup hub, then attempt a best-effort connect
        try:
            await hub.async_setup()
            _LOGGER.debug("ModbusHub setup completed for coordinator")
        except Exception as e:
            _LOGGER.error("Failed to setup ModbusHub for coordinator: %s", str(e))
            return False

        # Avoid blocking setup on unreachable hosts
        connect_timeout = entry.data.get("timeout", 5)
        try:
            await asyncio.wait_for(hub.async_pb_connect(), timeout=connect_timeout)
            _LOGGER.info("ModbusHub connected successfully for coordinator")
            hub._is_connected = True
        except Exception as e:
            _LOGGER.warning("ModbusHub connect failed (continuing offline): %s", str(e))
            hub._is_connected = False

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

        # Start coordinator refresh fully in background (Option A).
        # Do not block entry setup on initial Modbus roundtrips.
        initial_refresh_task = asyncio.create_task(
            coordinator.async_config_entry_first_refresh()
        )

        def _log_initial_refresh_result(task: asyncio.Task) -> None:
            try:
                task.result()
            except Exception as err:
                _LOGGER.debug(
                    "Coordinator initial background refresh finished with error: %s",
                    str(err),
                )

        initial_refresh_task.add_done_callback(_log_initial_refresh_result)

        # Keep registry consistent with current dynamic filtering output.
        await _cleanup_stale_registry_entities(hass, entry, coordinator)

        # Load platforms for coordinator-based entities
        try:
            platform_task = asyncio.create_task(
                hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            )
            await platform_task
            _LOGGER.debug("Coordinator platforms loaded successfully: %s", PLATFORMS)
        except Exception as e:
            _LOGGER.error("Error loading coordinator platforms: %s", str(e))
            return False

        # Normalize binary_sensor entity_ids to include device prefix (case-insensitive)
        await _normalize_binary_sensor_entity_ids(hass, entry)

        _LOGGER.info(
            "Modbus Manager coordinator setup completed for %s",
            entry.data.get("prefix", "unknown"),
        )

        return True

    except Exception as e:
        _LOGGER.error("Error setting up coordinator: %s", str(e))
        return False


def _get_unprefixed_subentry_ids(entry: ConfigEntry) -> set:
    """Return config_subentry_ids for devices with entity_ids_without_prefix=yes."""
    unprefixed_ids = set()
    devices = entry.data.get("devices", [])
    if not isinstance(devices, list):
        return unprefixed_ids
    for device in devices:
        if not isinstance(device, dict):
            continue
        if device.get("entity_ids_without_prefix") != "yes":
            continue
        device_entry_id = device.get("device_entry_id")
        if not device_entry_id:
            continue
        for subentry in entry.subentries.values():
            if (
                subentry.subentry_type == "device"
                and subentry.unique_id == device_entry_id
            ):
                unprefixed_ids.add(subentry.subentry_id)
                break
    return unprefixed_ids


async def _normalize_binary_sensor_entity_ids(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Ensure binary_sensor entity_ids include the device prefix.

    Skips entities from devices with entity_ids_without_prefix=yes (entity_ids stay unprefixed).
    """
    try:
        entity_registry = er.async_get(hass)
        unprefixed_subentry_ids = _get_unprefixed_subentry_ids(entry)
        updated = 0

        for entity_entry in list(entity_registry.entities.values()):
            if entity_entry.config_entry_id != entry.entry_id:
                continue
            if entity_entry.platform != "binary_sensor":
                continue
            if not entity_entry.device_id:
                continue
            if entity_entry.config_subentry_id in unprefixed_subentry_ids:
                continue

            devices = entry.data.get("devices", [])
            prefix = None
            if isinstance(devices, list):
                for subentry in entry.subentries.values():
                    if (
                        subentry.subentry_type == "device"
                        and subentry.subentry_id == entity_entry.config_subentry_id
                    ):
                        device_entry_id = subentry.unique_id
                        for dev in devices:
                            if (
                                isinstance(dev, dict)
                                and dev.get("device_entry_id") == device_entry_id
                            ):
                                prefix = dev.get("prefix")
                                break
                        break
            if not prefix:
                prefix = entry.data.get("prefix")
            if not prefix:
                continue

            prefix_lower = prefix.lower()
            current_entity_id = entity_entry.entity_id
            if current_entity_id.startswith(f"binary_sensor.{prefix_lower}_"):
                continue

            object_id = current_entity_id.split(".", 1)[1]
            if object_id.startswith(f"{prefix_lower}_"):
                continue

            new_entity_id = f"binary_sensor.{prefix_lower}_{object_id}"
            if entity_registry.async_get(new_entity_id):
                _LOGGER.warning(
                    "Skipping binary_sensor rename due to conflict: %s -> %s",
                    current_entity_id,
                    new_entity_id,
                )
                continue

            entity_registry.async_update_entity(
                current_entity_id, new_entity_id=new_entity_id
            )
            updated += 1

        if updated:
            _LOGGER.debug(
                "Normalized %d binary_sensor entity_id(s) to include prefix", updated
            )
    except Exception as e:
        _LOGGER.warning("Failed to normalize binary_sensor entity_ids: %s", str(e))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry - Coordinator-Only."""
    try:
        _LOGGER.info(
            "🚀 Setting up Modbus Manager (Coordinator-Only) for %s",
            entry.data.get("prefix", "unknown"),
        )

        # Fallback migration check (Home Assistant should call migration automatically,
        # but this ensures migration happens even if automatic migration fails)
        from .config_flow import ModbusManagerConfigFlow

        flow = ModbusManagerConfigFlow()
        if entry.version < flow.VERSION or not entry.data.get("devices"):
            _LOGGER.info(
                "Config entry needs migration from version %d to %d (fallback migration)",
                entry.version,
                flow.VERSION,
            )
            migration_result = await flow.async_migrate_entry(hass, entry)
            if not migration_result:
                _LOGGER.error("Migration failed for entry %s", entry.entry_id)
                return False
            _LOGGER.info("Fallback migration completed successfully")

        # Keep true config subentries in sync with current devices[] records.
        await _sync_device_subentries(hass, entry)
        relink_completed = bool(entry.data.get("device_registry_relink_completed"))
        pending_relink = bool(entry.data.get("pending_registry_relink"))
        if pending_relink or not relink_completed:
            await _relink_devices_to_subentries(hass, entry)
            await _relink_entities_to_device_subentries(hass, entry)
            new_data = dict(entry.data)
            new_data["device_registry_relink_completed"] = True
            new_data.pop("pending_registry_relink", None)
            hass.config_entries.async_update_entry(entry, data=new_data)
        else:
            _LOGGER.debug(
                "Skipping registry relink for %s (already completed)",
                entry.entry_id,
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
            "Unloading Modbus Manager for %s", entry.data.get("prefix", "unknown")
        )

        # Check if this is a reload operation (not a full removal)
        # During reload, we want to keep the Modbus connection alive
        is_reload = hass.data[DOMAIN].get("_reload_in_progress", False)

        if is_reload:
            _LOGGER.debug("🔄 Reload detected - keeping Modbus connection alive")

        # Unload all platforms
        try:
            unload_ok = await hass.config_entries.async_unload_platforms(
                entry, PLATFORMS
            )
            if unload_ok:
                _LOGGER.debug("All platforms successfully unloaded: %s", PLATFORMS)
            else:
                _LOGGER.warning("Not all platforms could be unloaded")
        except Exception as e:
            _LOGGER.error("Error unloading platforms: %s", str(e))

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

                _LOGGER.debug(
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
                        _LOGGER.debug("Modbus hub successfully closed")

                        # Remove hub from global storage
                        if hub_name in hass.data[DOMAIN]:
                            del hass.data[DOMAIN][hub_name]
                        if global_hub_key in hass.data[DOMAIN]:
                            del hass.data[DOMAIN][global_hub_key]
                        if hub_ref_key in hass.data[DOMAIN]:
                            del hass.data[DOMAIN][hub_ref_key]
                    except Exception as e:
                        _LOGGER.warning("Error closing Modbus hub: %s", str(e))
                elif is_reload:
                    _LOGGER.debug(
                        "✅ Keeping Modbus connection %s alive during reload (refcount: %d)",
                        hub_name,
                        new_refcount,
                    )
                else:
                    _LOGGER.debug(
                        "✅ Keeping Modbus connection %s open (%d devices still using it)",
                        hub_name,
                        new_refcount,
                    )

            # Delete data (but hub reference remains for reload)
            if not is_reload:
                del hass.data[DOMAIN][entry.entry_id]
            else:
                # Bei Reload nur Entity-Daten löschen, Hub behalten
                _LOGGER.debug("🔄 Keeping entry data for reload")

        _LOGGER.debug(
            "Modbus Manager successfully unloaded for %s",
            entry.data.get("prefix", "unknown"),
        )
        return True

    except Exception as e:
        _LOGGER.error("Error unloading Modbus Manager: %s", str(e))
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
                                _LOGGER.debug(
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
                    _LOGGER.debug("Global performance metrics: %s", global_summary)

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
                    _LOGGER.debug("No performance metrics available")
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
                                _LOGGER.debug(
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
                    _LOGGER.debug(
                        "Reset performance metrics for %d device(s)", reset_count
                    )
                else:
                    _LOGGER.debug("No performance monitors found to reset")
        except Exception as e:
            _LOGGER.error(
                "Error in performance_reset service: %s", str(e), exc_info=True
            )

    # register_optimize service removed - register optimization is automatic and handled by the coordinator

    async def add_entity_prefix_service(call):
        """Add prefix to entity_ids (after migration from unprefixed entity_ids).

        Use after running with entity_ids_without_prefix=yes to add prefix to entity_ids.
        entity_id: sensor.battery_level -> sensor.sg_battery_level)
        Home Assistant migrates history when entity_id is renamed.

        Service data:
        - entry_id: Config entry ID (required)
        - device_entry_id: Device subentry unique_id (optional, for multi-device hubs)
        """
        try:
            entry_id = call.data.get("entry_id") if call.data else None
            device_entry_id = call.data.get("device_entry_id") if call.data else None

            if not entry_id:
                _LOGGER.error("add_entity_prefix requires entry_id")
                return

            config_entry = None
            for entry in hass.config_entries.async_entries(DOMAIN):
                if entry.entry_id == entry_id:
                    config_entry = entry
                    break

            if not config_entry:
                _LOGGER.error("Config entry %s not found", entry_id)
                return

            entity_registry = er.async_get(hass)
            devices = config_entry.data.get("devices", [])
            if not isinstance(devices, list):
                _LOGGER.error("No devices in entry %s", entry_id)
                return

            # Build device_entry_id -> (prefix, config_subentry_id) for migration devices
            targets = {}
            for device in devices:
                if not isinstance(device, dict):
                    continue
                if device.get("entity_ids_without_prefix") != "yes":
                    continue
                dev_id = device.get("device_entry_id")
                prefix = device.get("prefix")
                if not dev_id or not prefix:
                    continue
                if device_entry_id and dev_id != device_entry_id:
                    continue
                subentry_id = None
                for subentry in config_entry.subentries.values():
                    if (
                        subentry.subentry_type == "device"
                        and subentry.unique_id == dev_id
                    ):
                        subentry_id = subentry.subentry_id
                        break
                if subentry_id:
                    targets[dev_id] = (prefix.lower(), subentry_id)

            if not targets:
                _LOGGER.warning(
                    "No devices with entity_ids_without_prefix=yes found for entry %s",
                    entry_id,
                )
                return

            updated = 0
            for reg_entry in list(entity_registry.entities.values()):
                if reg_entry.config_entry_id != entry_id:
                    continue
                subentry_id = reg_entry.config_subentry_id
                if not subentry_id:
                    continue
                prefix_info = None
                for dev_id, (prefix_lower, sid) in targets.items():
                    if sid == subentry_id:
                        prefix_info = (prefix_lower, dev_id)
                        break
                if not prefix_info:
                    continue
                prefix_lower, _ = prefix_info
                domain, object_id = reg_entry.entity_id.split(".", 1)
                if object_id.startswith(f"{prefix_lower}_"):
                    continue
                new_entity_id = f"{domain}.{prefix_lower}_{object_id}"
                if entity_registry.async_get(new_entity_id):
                    _LOGGER.warning(
                        "Skipping rename due to conflict: %s -> %s",
                        reg_entry.entity_id,
                        new_entity_id,
                    )
                    continue
                entity_registry.async_update_entity(
                    reg_entry.entity_id, new_entity_id=new_entity_id
                )
                updated += 1

            _LOGGER.info(
                "add_entity_prefix: renamed %d entity(ies) for entry %s",
                updated,
                entry_id,
            )
        except Exception as e:
            _LOGGER.error(
                "Error in add_entity_prefix service: %s", str(e), exc_info=True
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

                            _LOGGER.debug(
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
            _LOGGER.debug("No templates were updated")

    # Register services
    hass.services.async_register(
        DOMAIN, "performance_monitor", performance_monitor_service
    )
    hass.services.async_register(DOMAIN, "performance_reset", performance_reset_service)
    # register_optimize removed - optimization is automatic
    hass.services.async_register(DOMAIN, "add_entity_prefix", add_entity_prefix_service)
    hass.services.async_register(DOMAIN, "reload_templates", reload_templates_service)

    _LOGGER.debug("Modbus Manager services registered successfully")
