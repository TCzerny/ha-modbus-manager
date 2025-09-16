"""Modbus Manager Integration."""
import asyncio
import logging
from typing import Any

from homeassistant.components.modbus import ModbusHub
from homeassistant.components.sensor.const import CONF_STATE_CLASS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from .aggregates import AggregationManager
from .const import DOMAIN, PLATFORMS
from .ems import EMSManager
from .logger import ModbusManagerLogger
from .performance_monitor import PerformanceMonitor
from .register_optimizer import RegisterOptimizer
from .template_loader import get_template_by_name

_LOGGER = ModbusManagerLogger(__name__)

PLATFORM = "modbus_manager"


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Modbus Manager component."""
    hass.data.setdefault(DOMAIN, {})

    # Register services
    async def async_optimize_registers(call):
        """Optimize registers for a specific device."""
        device_id = call.data.get("device_id")
        if not device_id:
            _LOGGER.error("Device ID is required for register optimization")
            return

        # Find the device in our data
        for entry_id, data in hass.data[DOMAIN].items():
            if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                register_optimizer = data.get("register_optimizer")
                if register_optimizer:
                    registers = data.get("registers", [])
                    optimized_ranges = register_optimizer.optimize_registers(registers)
                    _LOGGER.info(
                        "Optimized %d registers into %d ranges for device %s",
                        len(registers),
                        len(optimized_ranges),
                        device_id,
                    )
                    return
                else:
                    _LOGGER.error(
                        "Register optimizer not available for device %s", device_id
                    )
                    return

        _LOGGER.error("Device %s not found", device_id)

    async def async_get_performance(call):
        """Get performance metrics for a device or globally."""
        device_id = call.data.get("device_id")

        if device_id:
            # Get metrics for specific device
            for entry_id, data in hass.data[DOMAIN].items():
                if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                    performance_monitor = data.get("performance_monitor")
                    if performance_monitor:
                        metrics = performance_monitor.get_global_metrics()
                        _LOGGER.info(
                            "Performance metrics for %s: %s",
                            device_id,
                            metrics.__dict__,
                        )
                        return
                    else:
                        _LOGGER.error(
                            "Performance monitor not available for device %s", device_id
                        )
                        return

            _LOGGER.error("Device %s not found", device_id)
        else:
            # Get global metrics
            global_metrics = {}
            for entry_id, data in hass.data[DOMAIN].items():
                performance_monitor = data.get("performance_monitor")
                if performance_monitor:
                    global_metrics[
                        entry_id
                    ] = performance_monitor.get_global_metrics().__dict__

            _LOGGER.info("Global performance metrics: %s", global_metrics)

    async def async_reset_performance(call):
        """Reset performance metrics for a device or globally."""
        device_id = call.data.get("device_id")

        if device_id:
            # Reset metrics for specific device
            for entry_id, data in hass.data[DOMAIN].items():
                if data.get("prefix") == device_id.replace("modbus_manager_", ""):
                    performance_monitor = data.get("performance_monitor")
                    if performance_monitor:
                        performance_monitor.reset_metrics()
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
            # Reset global metrics
            for entry_id, data in hass.data[DOMAIN].items():
                performance_monitor = data.get("performance_monitor")
                if performance_monitor:
                    performance_monitor.reset_metrics()

            _LOGGER.info("Reset performance metrics for all devices")

    # Register the services
    hass.services.async_register(DOMAIN, "optimize_registers", async_optimize_registers)
    hass.services.async_register(DOMAIN, "get_performance", async_get_performance)
    hass.services.async_register(DOMAIN, "reset_performance", async_reset_performance)

    # Register static path for modbus manager panel
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path="/api/panel_custom/modbus_manager/modbus-manager-panel.js",
                path=hass.config.path(
                    "custom_components/modbus_manager/modbus-manager-panel.js"
                ),
                cache_headers=False,
            )
        ]
    )

    # Register the custom panel
    from homeassistant.components import panel_custom

    await panel_custom.async_register_panel(
        hass,
        "modbus-manager-panel",
        "modbus-manager-panel",
        module_url="/api/panel_custom/modbus_manager/modbus-manager-panel.js",
        sidebar_title="Modbus Manager",
        sidebar_icon="mdi:chart-line",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry."""
    try:
        _LOGGER.debug(
            "Setup of Modbus Manager started for %s",
            entry.data.get("prefix", "unknown"),
        )

        # Check if this is an aggregates template
        is_aggregates_template = entry.data.get("is_aggregates_template", False)

        _LOGGER.debug(
            "Setup Entry Debug: is_aggregates_template=%s, entry.data=%s",
            is_aggregates_template,
            entry.data,
        )

        if is_aggregates_template:
            # Handle aggregates template - no Modbus connection needed
            _LOGGER.debug("Aggregates Template detected - skipping Modbus connection")
            # Use asyncio.create_task to avoid blocking the event loop
            setup_task = asyncio.create_task(_setup_aggregates_entry(hass, entry))
            return await setup_task

        # Use registers from config entry (already filtered by dynamic config)
        registers = entry.data.get("registers", [])
        calculated_entities = entry.data.get("calculated_entities", [])
        controls = entry.data.get("controls", [])

        # Get template name for version checking
        template_name = entry.data.get("template")
        if not template_name:
            _LOGGER.error("No template found in configuration")
            return False

        # Load template for version checking only
        template_task = asyncio.create_task(get_template_by_name(template_name))
        template_data = await template_task

        if not template_data:
            _LOGGER.error("Template %s could not be loaded", template_name)
            return False

        # Apply firmware filtering for existing configurations
        # Get firmware version from template or use default
        template_firmware_version = (
            template_data.get("firmware_version", "1.0.0")
            if isinstance(template_data, dict)
            else "1.0.0"
        )
        firmware_version = entry.data.get("firmware_version", template_firmware_version)

        # Always apply firmware filtering if we have entities with firmware_min_version
        entities_with_firmware_req = [
            e
            for e in registers + calculated_entities + controls
            if e.get("firmware_min_version")
        ]
        if entities_with_firmware_req:
            _LOGGER.debug(
                "Applying firmware filtering for version: %s (found %d entities with firmware requirements)",
                firmware_version,
                len(entities_with_firmware_req),
            )
            registers = _filter_by_firmware_version(registers, firmware_version)
            calculated_entities = _filter_by_firmware_version(
                calculated_entities, firmware_version
            )
            controls = _filter_by_firmware_version(controls, firmware_version)
            _LOGGER.info(
                "Firmware filtering applied: %d registers, %d calculated, %d controls",
                len(registers),
                len(calculated_entities),
                len(controls),
            )

        # Extract current version from template
        if isinstance(template_data, dict):
            current_version = template_data.get("version", 1)
        else:
            current_version = 1

        # Check if template has changed and reload register data if necessary
        stored_version = entry.data.get("template_version", 1)
        template_changed = False

        # Check version change
        if current_version != stored_version:
            _LOGGER.info(
                "Template version changed from %d to %d",
                stored_version,
                current_version,
            )
            template_changed = True

            # Check if we need to reload due to processing logic changes
            # This happens when the template processing logic has been updated
            if not template_changed:
                # Check if any 32-bit registers have count=1 (old processing) vs count=2 (new processing)
                bit32_registers = [
                    r
                    for r in registers
                    if r.get("data_type") in ["uint32", "int32", "float", "float32"]
                ]
                if any(r.get("count", 1) == 1 for r in bit32_registers):
                    _LOGGER.debug(
                        "Detected 32-bit registers with count=1, reloading with updated processing logic"
                    )
                    template_changed = True

        if template_changed:
            _LOGGER.info("Reloading register data with updated template processing")

            # Reload template with current processing logic and apply dynamic filtering
            try:
                if isinstance(template_data, dict):
                    # Apply dynamic configuration filtering if the template supports it
                    dynamic_config = template_data.get("dynamic_config", {})
                    if dynamic_config:
                        _LOGGER.info(
                            "Applying dynamic config filtering during template reload"
                        )

                        # Use the same logic as in config_flow.py
                        from .config_flow import ModbusManagerConfigFlow

                        config_flow = ModbusManagerConfigFlow()

                        # Create a mock user_input with current configuration values
                        mock_user_input = {}

                        # Map config entry values back to user input format
                        phases = entry.data.get("phases", 3)
                        mppt_count = entry.data.get("mppt_count", 2)
                        battery_config = entry.data.get("battery_config", "none")
                        battery_slave_id = entry.data.get("battery_slave_id", 200)
                        firmware_version = entry.data.get("firmware_version", "1.0.0")
                        connection_type = entry.data.get("connection_type", "LAN")

                        # Use direct field names (same as config_flow)
                        mock_user_input["phases"] = phases
                        mock_user_input["mppt_count"] = mppt_count
                        mock_user_input["battery_config"] = battery_config
                        mock_user_input["battery_slave_id"] = battery_slave_id
                        mock_user_input["firmware_version"] = firmware_version
                        mock_user_input["connection_type"] = connection_type

                        _LOGGER.info(
                            "Dynamic config values: phases=%d, mppt=%d, battery=%s, fw=%s",
                            phases,
                            mppt_count,
                            battery_config,
                            firmware_version,
                        )

                        # Process template with dynamic config
                        processed_data = config_flow._process_dynamic_config(
                            mock_user_input, template_data
                        )

                        template_sensors = processed_data["sensors"]
                        template_calculated = processed_data["calculated"]
                        template_controls = processed_data["controls"]
                        template_binary_sensors = processed_data.get(
                            "binary_sensors", []
                        )

                        _LOGGER.info(
                            "Dynamic filtering applied: %d sensors, %d calculated, %d controls (from %d, %d, %d original)",
                            len(template_sensors),
                            len(template_calculated),
                            len(template_controls),
                            len(template_data.get("sensors", [])),
                            len(template_data.get("calculated", [])),
                            len(template_data.get("controls", [])),
                        )
                    else:
                        # No dynamic config, use template as-is
                        template_sensors = template_data.get("sensors", [])
                        template_calculated = template_data.get("calculated", [])
                        template_controls = template_data.get("controls", [])
                        template_binary_sensors = template_data.get(
                            "binary_sensors", []
                        )
                        _LOGGER.info("No dynamic config found, using full template")

                    if template_sensors:
                        # Update registers with new data
                        registers = template_sensors
                        calculated_entities = template_calculated
                        controls = template_controls
                        binary_sensors = template_binary_sensors
                        _LOGGER.info(
                            "Reloaded %d sensors, %d calculated, %d controls, %d binary_sensors from template",
                            len(registers),
                            len(calculated_entities),
                            len(controls),
                            len(binary_sensors),
                        )

                        # Update the config entry with new register data
                        new_data = dict(entry.data)
                        new_data["registers"] = registers
                        new_data["calculated_entities"] = calculated_entities
                        new_data["controls"] = controls
                        if binary_sensors:
                            new_data["binary_sensors"] = binary_sensors
                        new_data["template_version"] = current_version
                        hass.config_entries.async_update_entry(entry, data=new_data)
                        _LOGGER.info("Updated config entry with new template data")
                    else:
                        _LOGGER.warning("Template has no sensors section")
                else:
                    _LOGGER.warning("Template data is not a dictionary")
            except Exception as e:
                _LOGGER.error("Error reloading template data: %s", str(e))
                _LOGGER.warning("Failed to reload registers, using stored data")

        if not registers:
            # Try to load registers directly from template as fallback with dynamic filtering
            _LOGGER.warning(
                "No registers found in config entry, trying to load from template with dynamic filtering"
            )
            if isinstance(template_data, dict):
                try:
                    # Apply dynamic configuration filtering if available
                    dynamic_config = template_data.get("dynamic_config", {})
                    if dynamic_config:
                        _LOGGER.info("Applying dynamic config filtering in fallback")

                        # Use the same logic as above
                        from .config_flow import ModbusManagerConfigFlow

                        config_flow = ModbusManagerConfigFlow()

                        # Create mock user_input with current configuration values
                        phases = entry.data.get("phases", 3)
                        mppt_count = entry.data.get("mppt_count", 2)
                        battery_config = entry.data.get("battery_config", "none")
                        battery_slave_id = entry.data.get("battery_slave_id", 200)
                        firmware_version = entry.data.get("firmware_version", "1.0.0")
                        connection_type = entry.data.get("connection_type", "LAN")

                        mock_user_input = {
                            "phases": phases,
                            "mppt_count": mppt_count,
                            "battery_config": battery_config,
                            "battery_slave_id": battery_slave_id,
                            "firmware_version": firmware_version,
                            "connection_type": connection_type,
                        }

                        _LOGGER.info(
                            "Fallback dynamic config: phases=%d, mppt=%d, battery=%s, fw=%s",
                            phases,
                            mppt_count,
                            battery_config,
                            firmware_version,
                        )

                        # Process template with dynamic config
                        processed_data = config_flow._process_dynamic_config(
                            mock_user_input, template_data
                        )

                        registers = processed_data["sensors"]
                        calculated_entities = processed_data["calculated"]
                        controls = processed_data["controls"]
                        binary_sensors = processed_data.get("binary_sensors", [])

                        _LOGGER.info(
                            "Fallback dynamic filtering applied: %d sensors, %d calculated, %d controls, %d binary_sensors",
                            len(registers),
                            len(calculated_entities),
                            len(controls),
                            len(binary_sensors),
                        )
                    else:
                        # No dynamic config, use template as-is
                        registers = template_data.get("sensors", [])
                        calculated_entities = template_data.get("calculated", [])
                        controls = template_data.get("controls", [])
                        binary_sensors = template_data.get("binary_sensors", [])
                        _LOGGER.info("Fallback: No dynamic config, using full template")

                    if registers:
                        # Update config entry with filtered template data
                        new_data = dict(entry.data)
                        new_data["registers"] = registers
                        new_data["calculated_entities"] = calculated_entities
                        new_data["controls"] = controls
                        if binary_sensors:
                            new_data["binary_sensors"] = binary_sensors
                        hass.config_entries.async_update_entry(entry, data=new_data)
                        _LOGGER.info(
                            "Updated config entry with filtered template data as fallback"
                        )
                    else:
                        _LOGGER.error(
                            "Template %s has no sensors after filtering", template_name
                        )
                        return False

                except Exception as e:
                    _LOGGER.error("Error in fallback template processing: %s", str(e))
                    # Last resort: use template as-is without filtering
                    template_sensors = template_data.get("sensors", [])
                    if template_sensors:
                        registers = template_sensors
                        calculated_entities = template_data.get("calculated", [])
                        controls = template_data.get("controls", [])
                        _LOGGER.warning(
                            "Using unfiltered template as last resort: %d sensors",
                            len(registers),
                        )
                    else:
                        _LOGGER.error(
                            "Template %s has no sensors section", template_name
                        )
                        return False
            else:
                _LOGGER.error("Template %s has no registers defined", template_name)
                return False

        # Template-Version prüfen
        stored_version = entry.data.get("template_version", 1)

        if current_version > stored_version:
            _LOGGER.debug(
                "Template %s aktualisiert: v%s → v%s",
                template_name,
                stored_version,
                current_version,
            )
            # Version in Config Entry aktualisieren - entry.data ist immutable, daher update_entry verwenden
            new_data = dict(entry.data)
            new_data["template_version"] = current_version
            hass.config_entries.async_update_entry(entry, data=new_data)

        # Modbus-Hub über Standard Home Assistant API erstellen
        hub_name = f"modbus_manager_{entry.data['prefix']}"

        # Modbus-Konfiguration - HA Modbus Standard Parameter
        modbus_config = {
            "name": hub_name,  # ← ModbusHub erwartet 'name' Key!
            "type": "tcp",  # ← TCP-Verbindung
            "host": entry.data["host"],  # ← Host-IP
            "port": entry.data.get("port", 502),  # ← Port
            "delay": entry.data.get("delay", 0),  # ← HA Modbus Standard
            "timeout": entry.data.get("timeout", 5),  # ← HA Modbus Standard
        }

        _LOGGER.debug("Modbus-Konfiguration: %s", modbus_config)

        # Modbus-Hub direkt erstellen
        try:
            hub = ModbusHub(hass, modbus_config)
            _LOGGER.debug("Modbus-Hub %s erfolgreich erstellt", hub_name)

            # Modbus-Hub einrichten und verbinden
            try:
                await hub.async_setup()
                _LOGGER.debug("Modbus-Hub %s erfolgreich eingerichtet", hub_name)

                # Modbus-Hub verbinden
                try:
                    await hub.async_pb_connect()
                    _LOGGER.debug("Modbus-Hub %s erfolgreich verbunden", hub_name)
                except Exception as e:
                    _LOGGER.error("Fehler beim Verbinden des Modbus-Hubs: %s", str(e))
                    return False

            except Exception as e:
                _LOGGER.error("Fehler beim Einrichten des Modbus-Hubs: %s", str(e))
                return False

        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen des Modbus-Hubs: %s", str(e))
            return False

        # Daten für alle Plattformen vorbereiten
        prefix = entry.data["prefix"]

        # Device wird von der Sensor-Plattform erstellt

        hass.data[DOMAIN][entry.entry_id] = {
            "hub": hub,
            "registers": registers,
            "calculated_entities": calculated_entities,
            "controls": controls,
            "prefix": prefix,
            "template": template_name,
            "host": entry.data["host"],
            "port": entry.data.get("port", 502),
            "slave_id": entry.data.get("slave_id", 1),
            "aggregate_sensors": [],
        }

        # Hub auch unter Hub-Namen speichern für einheitlichen Zugriff
        hass.data[DOMAIN][hub_name] = hub

        # Template-Daten global verfügbar machen für Controls
        hass.data[DOMAIN]["template_data"] = template_data

        # Alle Plattformen einrichten (in separatem Task um Asyncio-Warnings zu vermeiden)
        try:
            platform_task = asyncio.create_task(
                hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            )
            await platform_task
            _LOGGER.debug("Alle Plattformen erfolgreich eingerichtet: %s", PLATFORMS)

            # Initialize EMS Manager if this is not an aggregates template
            if not entry.data.get("is_aggregates_template", False):
                await _initialize_ems_manager(hass, entry)

        except Exception as e:
            _LOGGER.error("Fehler beim Einrichten der Plattformen: %s", str(e))
            return False

        # Performance-Monitor und Register-Optimizer initialisieren
        try:
            performance_monitor = PerformanceMonitor()
            register_optimizer = RegisterOptimizer(max_read_size=8)

            hass.data[DOMAIN][entry.entry_id][
                "performance_monitor"
            ] = performance_monitor
            hass.data[DOMAIN][entry.entry_id]["register_optimizer"] = register_optimizer

            _LOGGER.debug("Performance-Monitor und Register-Optimizer initialisiert")
        except Exception as e:
            _LOGGER.warning(
                "Performance-Monitor konnte nicht initialisiert werden: %s", str(e)
            )

        # Aggregation-Manager initialisieren (nur für Template-basierte Aggregate-Sensoren)
        # Automatisch erstellte Aggregate-Sensoren sind deaktiviert - nur Template-basierte werden verwendet
        _LOGGER.debug(
            "Aggregation-Manager deaktiviert - nur Template-basierte Aggregate-Sensoren werden verwendet"
        )

        _LOGGER.debug(
            "Modbus Manager erfolgreich eingerichtet für %s",
            entry.data.get("prefix", "unbekannt"),
        )
        return True

    except Exception as e:
        _LOGGER.error("Fehler beim Setup von Modbus Manager: %s", str(e))
        import traceback

        _LOGGER.error("Traceback: %s", traceback.format_exc())
        return False


async def _setup_aggregates_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up aggregates template entry."""
    try:
        prefix = entry.data.get("prefix", "aggregates")
        aggregates = entry.data.get("aggregates", [])

        _LOGGER.debug("Setup Aggregates Template mit %d Aggregationen", len(aggregates))

        # Process aggregates to add prefix to unique_id and name
        processed_aggregates = []
        for aggregate in aggregates:
            processed_aggregate = aggregate.copy()

            # Add prefix to unique_id if it exists
            if "unique_id" in processed_aggregate:
                template_unique_id = processed_aggregate["unique_id"]
                processed_aggregate["unique_id"] = f"{prefix}_{template_unique_id}"
                _LOGGER.debug(
                    "Aggregate %s: Updated unique_id from %s to %s",
                    processed_aggregate.get("name", "unknown"),
                    template_unique_id,
                    processed_aggregate["unique_id"],
                )

            # Add prefix to name
            if "name" in processed_aggregate:
                original_name = processed_aggregate["name"]
                processed_aggregate["name"] = f"{prefix} {original_name}"
                _LOGGER.debug(
                    "Aggregate: Updated name from %s to %s",
                    original_name,
                    processed_aggregate["name"],
                )

            processed_aggregates.append(processed_aggregate)

        # Store aggregates data for sensor platform
        config_data = {
            "aggregates": processed_aggregates,
            "prefix": prefix,
            "template": entry.data.get("template", "Modbus Manager Aggregates"),
            "template_version": entry.data.get("template_version", 1),
            "is_aggregates_template": True,
        }

        _LOGGER.debug("Integration Debug: Speichere config_data=%s", config_data)
        hass.data[DOMAIN][entry.entry_id] = config_data

        # Forward to sensor platform (in separatem Task um Asyncio-Warnings zu vermeiden)
        sensor_task = asyncio.create_task(
            hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
        )
        await sensor_task

        _LOGGER.debug("Aggregates Template erfolgreich eingerichtet")
        return True

    except Exception as e:
        _LOGGER.error("Fehler beim Setup des Aggregates Templates: %s", str(e))
        return False


async def _initialize_ems_manager(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Initialize EMS Manager for the entry."""
    try:
        prefix = entry.data.get("prefix", "sg")

        # EMS configuration removed - EMS will be handled in panel only
        _LOGGER.debug("EMS initialization removed - handled in panel only")
        return

        # Create EMS Manager
        ems_manager = EMSManager(hass, prefix)

        # Initialize EMS system
        await ems_manager.initialize()

        # Add this device to EMS management
        await ems_manager.add_device(
            device_id=f"{prefix}_device",
            name=f"{prefix.upper()} Device",
            priority=2
            if "sg" in prefix.lower()
            else 1
            if "ebox" in prefix.lower()
            else 5,
            max_power=10000
            if "sg" in prefix.lower()
            else 11000
            if "ebox" in prefix.lower()
            else 5000,
            entity_id=f"switch.{prefix}_enable",
            auto_switch_entity=f"switch.{prefix}_ems_enable",
            power_sensor_entity=f"sensor.{prefix}_power",
            device_type="inverter"
            if "sg" in prefix.lower()
            else "ev_charger"
            if "ebox" in prefix.lower()
            else "device",
        )

        # Add default devices
        await _add_default_ems_devices(ems_manager)

        # Store EMS manager in hass data
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN][f"{prefix}_ems_manager"] = ems_manager

        _LOGGER.info(
            "EMS Manager initialized for prefix %s with EMS configuration", prefix
        )

    except Exception as e:
        _LOGGER.error("Failed to initialize EMS Manager: %s", str(e))


async def _add_default_ems_devices(ems_manager: EMSManager) -> None:
    """Add devices to EMS management based on existing entities."""
    try:
        prefix = ems_manager.prefix
        hass = ems_manager.hass

        # Get all existing entities
        all_states = hass.states.async_all()
        entity_ids = [state.entity_id for state in all_states]

        _LOGGER.debug(
            "Scanning %d entities for EMS devices with prefix %s",
            len(entity_ids),
            prefix,
        )

        # Find EV Chargers (Wallboxen)
        ev_chargers = await _find_ev_chargers(entity_ids, prefix, hass)
        for i, ev_data in enumerate(ev_chargers):
            await ems_manager.add_device(
                device_id=f"ev_charger_{i+1}",
                name=ev_data["name"],
                priority=1,
                max_power=ev_data["max_power"],
                entity_id=ev_data["enable_switch"],
                auto_switch_entity=ev_data["auto_switch"],
                power_sensor_entity=ev_data["power_sensor"],
                device_type="ev_charger",
            )

        # Find Inverters
        inverters = await _find_inverters(entity_ids, prefix)
        for i, inv_data in enumerate(inverters):
            await ems_manager.add_device(
                device_id=f"inverter_{i+1}",
                name=inv_data["name"],
                priority=2,
                max_power=inv_data["max_power"],
                entity_id=inv_data["enable_switch"],
                auto_switch_entity=inv_data["auto_switch"],
                power_sensor_entity=inv_data["power_sensor"],
                device_type="inverter",
            )

        # Find Heat Pumps
        heat_pumps = await _find_heat_pumps(entity_ids, prefix)
        for i, hp_data in enumerate(heat_pumps):
            await ems_manager.add_device(
                device_id=f"heat_pump_{i+1}",
                name=hp_data["name"],
                priority=3,
                max_power=hp_data["max_power"],
                entity_id=hp_data["enable_switch"],
                auto_switch_entity=hp_data["auto_switch"],
                power_sensor_entity=hp_data["power_sensor"],
                device_type="heat_pump",
            )

        # Find Water Heaters
        water_heaters = await _find_water_heaters(entity_ids, prefix)
        for i, wh_data in enumerate(water_heaters):
            await ems_manager.add_device(
                device_id=f"water_heater_{i+1}",
                name=wh_data["name"],
                priority=4,
                max_power=wh_data["max_power"],
                entity_id=wh_data["enable_switch"],
                auto_switch_entity=wh_data["auto_switch"],
                power_sensor_entity=wh_data["power_sensor"],
                device_type="water_heater",
            )

        # Find Pool Heaters
        pool_heaters = await _find_pool_heaters(entity_ids, prefix)
        for i, ph_data in enumerate(pool_heaters):
            await ems_manager.add_device(
                device_id=f"pool_heater_{i+1}",
                name=ph_data["name"],
                priority=5,
                max_power=ph_data["max_power"],
                entity_id=ph_data["enable_switch"],
                auto_switch_entity=ph_data["auto_switch"],
                power_sensor_entity=ph_data["power_sensor"],
                device_type="pool_heater",
            )

        _LOGGER.info(
            "Added %d devices to EMS: %d EV chargers, %d inverters, %d heat pumps, %d water heaters, %d pool heaters",
            len(ems_manager.priority_manager.devices),
            len(ev_chargers),
            len(inverters),
            len(heat_pumps),
            len(water_heaters),
            len(pool_heaters),
        )

    except Exception as e:
        _LOGGER.error("Failed to add EMS devices: %s", str(e))


async def _find_ev_chargers(entity_ids: list, prefix: str, hass: HomeAssistant) -> list:
    """Find EV charger entities."""
    ev_chargers = []

    # Look for wallbox entities
    wallbox_entities = [
        eid for eid in entity_ids if "wallbox" in eid.lower() and prefix in eid
    ]

    for entity_id in wallbox_entities:
        if entity_id.startswith("switch.") and "_enable" in entity_id:
            # Extract wallbox name
            wallbox_name = entity_id.replace("switch.", "").replace("_enable", "")

            # Look for related entities
            auto_switch = f"switch.{wallbox_name}_auto"
            power_sensor = f"sensor.{wallbox_name}_power"
            limit_number = f"number.{wallbox_name}_limit"

            # Check if related entities exist
            if (
                auto_switch in entity_ids
                and power_sensor in entity_ids
                and limit_number in entity_ids
            ):
                # Get max power from limit number
                max_power = 11000.0  # Default
                try:
                    limit_state = hass.states.get(limit_number)
                    if limit_state and limit_state.attributes.get("max"):
                        max_power = (
                            float(limit_state.attributes["max"]) * 230
                        )  # Convert A to W
                except (ValueError, TypeError):
                    pass

                ev_chargers.append(
                    {
                        "name": wallbox_name.replace("_", " ").title(),
                        "max_power": max_power,
                        "enable_switch": entity_id,
                        "auto_switch": auto_switch,
                        "power_sensor": power_sensor,
                    }
                )

    return ev_chargers


async def _find_inverters(entity_ids: list, prefix: str) -> list:
    """Find inverter entities."""
    inverters = []

    # Look for inverter entities
    inverter_entities = [
        eid for eid in entity_ids if "inverter" in eid.lower() and prefix in eid
    ]

    for entity_id in inverter_entities:
        if entity_id.startswith("switch.") and "_enable" in entity_id:
            # Extract inverter name
            inverter_name = entity_id.replace("switch.", "").replace("_enable", "")

            # Look for related entities
            auto_switch = f"switch.{inverter_name}_auto"
            power_sensor = f"sensor.{inverter_name}_total_active_power"

            # Check if related entities exist
            if auto_switch in entity_ids and power_sensor in entity_ids:
                # Get max power from inverter specs (default based on common models)
                max_power = 10000.0  # Default 10kW

                inverters.append(
                    {
                        "name": inverter_name.replace("_", " ").title(),
                        "max_power": max_power,
                        "enable_switch": entity_id,
                        "auto_switch": auto_switch,
                        "power_sensor": power_sensor,
                    }
                )

    return inverters


async def _find_heat_pumps(entity_ids: list, prefix: str) -> list:
    """Find heat pump entities."""
    heat_pumps = []

    # Look for heat pump entities
    hp_entities = [
        eid for eid in entity_ids if "heat_pump" in eid.lower() and prefix in eid
    ]

    for entity_id in hp_entities:
        if entity_id.startswith("switch.") and "_enable" in entity_id:
            # Extract heat pump name
            hp_name = entity_id.replace("switch.", "").replace("_enable", "")

            # Look for related entities
            auto_switch = f"switch.{hp_name}_auto"
            power_sensor = f"sensor.{hp_name}_power"

            # Check if related entities exist
            if auto_switch in entity_ids and power_sensor in entity_ids:
                max_power = 5000.0  # Default 5kW

                heat_pumps.append(
                    {
                        "name": hp_name.replace("_", " ").title(),
                        "max_power": max_power,
                        "enable_switch": entity_id,
                        "auto_switch": auto_switch,
                        "power_sensor": power_sensor,
                    }
                )

    return heat_pumps


async def _find_water_heaters(entity_ids: list, prefix: str) -> list:
    """Find water heater entities."""
    water_heaters = []

    # Look for water heater entities
    wh_entities = [
        eid for eid in entity_ids if "water_heater" in eid.lower() and prefix in eid
    ]

    for entity_id in wh_entities:
        if entity_id.startswith("switch.") and "_enable" in entity_id:
            # Extract water heater name
            wh_name = entity_id.replace("switch.", "").replace("_enable", "")

            # Look for related entities
            auto_switch = f"switch.{wh_name}_auto"
            power_sensor = f"sensor.{wh_name}_power"

            # Check if related entities exist
            if auto_switch in entity_ids and power_sensor in entity_ids:
                max_power = 3000.0  # Default 3kW

                water_heaters.append(
                    {
                        "name": wh_name.replace("_", " ").title(),
                        "max_power": max_power,
                        "enable_switch": entity_id,
                        "auto_switch": auto_switch,
                        "power_sensor": power_sensor,
                    }
                )

    return water_heaters


async def _find_pool_heaters(entity_ids: list, prefix: str) -> list:
    """Find pool heater entities."""
    pool_heaters = []

    # Look for pool heater entities
    ph_entities = [
        eid for eid in entity_ids if "pool_heater" in eid.lower() and prefix in eid
    ]

    for entity_id in ph_entities:
        if entity_id.startswith("switch.") and "_enable" in entity_id:
            # Extract pool heater name
            ph_name = entity_id.replace("switch.", "").replace("_enable", "")

            # Look for related entities
            auto_switch = f"switch.{ph_name}_auto"
            power_sensor = f"sensor.{ph_name}_power"

            # Check if related entities exist
            if auto_switch in entity_ids and power_sensor in entity_ids:
                max_power = 2000.0  # Default 2kW

                pool_heaters.append(
                    {
                        "name": ph_name.replace("_", " ").title(),
                        "max_power": max_power,
                        "enable_switch": entity_id,
                        "auto_switch": auto_switch,
                        "power_sensor": power_sensor,
                    }
                )

    return pool_heaters


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        _LOGGER.debug(
            "Unload von Modbus Manager für %s", entry.data.get("prefix", "unbekannt")
        )

        # Check if this is an aggregates template
        is_aggregates_template = entry.data.get("is_aggregates_template", False)

        if is_aggregates_template:
            # For aggregates templates, only unload sensor platform
            try:
                unload_ok = await hass.config_entries.async_unload_platforms(
                    entry, ["sensor"]
                )
                if unload_ok:
                    _LOGGER.debug(
                        "Sensor-Plattform für Aggregate-Template erfolgreich entladen"
                    )
                else:
                    _LOGGER.warning(
                        "Sensor-Plattform für Aggregate-Template konnte nicht entladen werden"
                    )
            except Exception as e:
                _LOGGER.error(
                    "Fehler beim Entladen der Sensor-Plattform für Aggregate-Template: %s",
                    str(e),
                )
        else:
            # Alle Plattformen entladen
            try:
                unload_ok = await hass.config_entries.async_unload_platforms(
                    entry, PLATFORMS
                )
                if unload_ok:
                    _LOGGER.debug(
                        "Alle Plattformen erfolgreich entladen: %s", PLATFORMS
                    )
                else:
                    _LOGGER.warning("Nicht alle Plattformen konnten entladen werden")
            except Exception as e:
                _LOGGER.error("Fehler beim Entladen der Plattformen: %s", str(e))

        # Modbus-Hub schließen
        if entry.entry_id in hass.data[DOMAIN]:
            hub_data = hass.data[DOMAIN][entry.entry_id]
            if "hub" in hub_data:
                try:
                    await hub_data["hub"].async_close()
                    _LOGGER.debug("Modbus-Hub erfolgreich geschlossen")
                except Exception as e:
                    _LOGGER.warning("Fehler beim Schließen des Modbus-Hubs: %s", str(e))

            # Daten löschen
            del hass.data[DOMAIN][entry.entry_id]

        _LOGGER.debug(
            "Modbus Manager erfolgreich entladen für %s",
            entry.data.get("prefix", "unbekannt"),
        )
        return True

    except Exception as e:
        _LOGGER.error("Fehler beim Unload von Modbus Manager: %s", str(e))
        return False


def _filter_by_firmware_version(entities: list, firmware_version: str) -> list:
    """Filter entities based on firmware version requirements."""
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
