"""Modbus Manager Integration."""
import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.components.modbus import ModbusHub
from homeassistant.components.sensor.const import CONF_STATE_CLASS

from .const import DOMAIN, PLATFORMS
from .template_loader import get_template_by_name
from .aggregates import AggregationManager
from .register_optimizer import RegisterOptimizer
from .performance_monitor import PerformanceMonitor
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

PLATFORM = "modbus_manager"

async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Modbus Manager component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Manager from a config entry."""
    try:
        _LOGGER.debug("Setup of Modbus Manager started for %s", entry.data.get("prefix", "unknown"))
        
        # Check if this is an aggregates template
        is_aggregates_template = entry.data.get("is_aggregates_template", False)
        
        _LOGGER.debug("Setup Entry Debug: is_aggregates_template=%s, entry.data=%s", 
                     is_aggregates_template, entry.data)
        
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
        
        # Extract current version from template
        if isinstance(template_data, dict):
            current_version = template_data.get("version", 1)
        else:
            current_version = 1
        
        if not registers:
            _LOGGER.error("Template %s has no registers defined", template_name)
            return False
        
        # Template-Version prüfen
        stored_version = entry.data.get("template_version", 1)
        
        if current_version > stored_version:
            _LOGGER.debug("Template %s aktualisiert: v%s → v%s", template_name, stored_version, current_version)
            # Version in Config Entry aktualisieren - entry.data ist immutable, daher update_entry verwenden
            new_data = dict(entry.data)
            new_data["template_version"] = current_version
            hass.config_entries.async_update_entry(entry, data=new_data)
        
        _LOGGER.debug("Template %s geladen mit %d Registern, %d Controls", template_name, len(registers), len(controls))
        
        # Modbus-Hub über Standard Home Assistant API erstellen
        hub_name = f"modbus_manager_{entry.data['prefix']}"
        
        # Modbus-Konfiguration - HA Modbus Standard Parameter
        modbus_config = {
            "name": hub_name,           # ← ModbusHub erwartet 'name' Key!
            "type": "tcp",              # ← TCP-Verbindung
            "host": entry.data["host"], # ← Host-IP
            "port": entry.data.get("port", 502), # ← Port
            "delay": entry.data.get("delay", 0),      # ← HA Modbus Standard
            "timeout": entry.data.get("timeout", 5),   # ← HA Modbus Standard
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
        _LOGGER.debug("Präfix aus Config Entry: %s", prefix)
        _LOGGER.debug("Template: %s, Register: %d", template_name, len(registers))
        
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
        
        # Template-Daten global verfügbar machen für Controls
        hass.data[DOMAIN]["template_data"] = template_data
        
        _LOGGER.debug("Konfigurationsdaten gespeichert: prefix=%s, template=%s, controls=%d", prefix, template_name, len(controls))
        
        # Alle Plattformen einrichten (in separatem Task um Asyncio-Warnings zu vermeiden)
        try:
            platform_task = asyncio.create_task(hass.config_entries.async_forward_entry_setups(entry, PLATFORMS))
            await platform_task
            _LOGGER.debug("Alle Plattformen erfolgreich eingerichtet: %s", PLATFORMS)
        except Exception as e:
            _LOGGER.error("Fehler beim Einrichten der Plattformen: %s", str(e))
            return False
        
        # Performance-Monitor und Register-Optimizer initialisieren
        try:
            performance_monitor = PerformanceMonitor()
            register_optimizer = RegisterOptimizer(max_read_size=8)
            
            hass.data[DOMAIN][entry.entry_id]["performance_monitor"] = performance_monitor
            hass.data[DOMAIN][entry.entry_id]["register_optimizer"] = register_optimizer
            
            _LOGGER.debug("Performance-Monitor und Register-Optimizer initialisiert")
        except Exception as e:
            _LOGGER.warning("Performance-Monitor konnte nicht initialisiert werden: %s", str(e))
        
        # Aggregation-Manager initialisieren (nur für Template-basierte Aggregate-Sensoren)
        # Automatisch erstellte Aggregate-Sensoren sind deaktiviert - nur Template-basierte werden verwendet
        _LOGGER.debug("Aggregation-Manager deaktiviert - nur Template-basierte Aggregate-Sensoren werden verwendet")
        
        _LOGGER.debug("Modbus Manager erfolgreich eingerichtet für %s", entry.data.get("prefix", "unbekannt"))
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
        
        # Store aggregates data for sensor platform
        config_data = {
            "aggregates": aggregates,
            "prefix": prefix,
            "template": entry.data.get("template", "Modbus Manager Aggregates"),
            "template_version": entry.data.get("template_version", 1),
            "is_aggregates_template": True
        }
        
        _LOGGER.debug("Integration Debug: Speichere config_data=%s", config_data)
        hass.data[DOMAIN][entry.entry_id] = config_data
        
        # Forward to sensor platform (in separatem Task um Asyncio-Warnings zu vermeiden)
        sensor_task = asyncio.create_task(hass.config_entries.async_forward_entry_setups(entry, ["sensor"]))
        await sensor_task
        
        _LOGGER.debug("Aggregates Template erfolgreich eingerichtet")
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler beim Setup des Aggregates Templates: %s", str(e))
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        _LOGGER.debug("Unload von Modbus Manager für %s", entry.data.get("prefix", "unbekannt"))
        
        # Check if this is an aggregates template
        is_aggregates_template = entry.data.get("is_aggregates_template", False)
        
        if is_aggregates_template:
            # For aggregates templates, only unload sensor platform
            try:
                unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
                if unload_ok:
                    _LOGGER.debug("Sensor-Plattform für Aggregate-Template erfolgreich entladen")
                else:
                    _LOGGER.warning("Sensor-Plattform für Aggregate-Template konnte nicht entladen werden")
            except Exception as e:
                _LOGGER.error("Fehler beim Entladen der Sensor-Plattform für Aggregate-Template: %s", str(e))
        else:
            # Alle Plattformen entladen
            try:
                unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
                if unload_ok:
                    _LOGGER.debug("Alle Plattformen erfolgreich entladen: %s", PLATFORMS)
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
        
        _LOGGER.debug("Modbus Manager erfolgreich entladen für %s", entry.data.get("prefix", "unbekannt"))
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler beim Unload von Modbus Manager: %s", str(e))
        return False
