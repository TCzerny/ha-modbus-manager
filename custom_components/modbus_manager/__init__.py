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
        _LOGGER.info("Setup von Modbus Manager gestartet für %s", entry.data.get("prefix", "unbekannt"))
        
        # Template-Register laden
        template_name = entry.data.get("template")
        if not template_name:
            _LOGGER.error("Kein Template in der Konfiguration gefunden")
            return False
        
        registers = await get_template_by_name(template_name)
        if not registers:
            _LOGGER.error("Template %s konnte nicht geladen werden", template_name)
            return False
        
        _LOGGER.info("Template %s geladen mit %d Registern", template_name, len(registers))
        
        # Modbus-Hub über Standard Home Assistant API erstellen
        hub_name = f"modbus_manager_{entry.data['prefix']}"
        
        # Modbus-Konfiguration - alle erforderlichen Parameter
        modbus_config = {
            "name": hub_name,           # ← ModbusHub erwartet 'name' Key!
            "type": "tcp",              # ← TCP-Verbindung
            "host": entry.data["host"], # ← Host-IP
            "port": entry.data.get("port", 502), # ← Port
            "delay": 0,                 # ← Erforderlich: Verzögerung zwischen Anfragen
            "timeout": 10,              # ← Erforderlich: Timeout in Sekunden
        }
        
        _LOGGER.info("Modbus-Konfiguration: %s", modbus_config)
        
        # Modbus-Hub direkt erstellen
        try:
            hub = ModbusHub(hass, modbus_config)
            _LOGGER.info("Modbus-Hub %s erfolgreich erstellt", hub_name)
            
            # Modbus-Hub einrichten und verbinden
            try:
                await hub.async_setup()
                _LOGGER.info("Modbus-Hub %s erfolgreich eingerichtet", hub_name)
                
                # Modbus-Hub verbinden
                try:
                    await hub.async_pb_connect()
                    _LOGGER.info("Modbus-Hub %s erfolgreich verbunden", hub_name)
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
        _LOGGER.info("Präfix aus Config Entry: %s", prefix)
        _LOGGER.info("Template: %s, Register: %d", template_name, len(registers))
        
        hass.data[DOMAIN][entry.entry_id] = {
            "hub": hub,
            "registers": registers,
            "prefix": prefix,
            "template": template_name,
            "host": entry.data["host"],
            "port": entry.data.get("port", 502),
            "slave_id": entry.data.get("slave_id", 1),
        }
        
        _LOGGER.info("Konfigurationsdaten gespeichert: prefix=%s, template=%s", prefix, template_name)
        
        # Alle Plattformen einrichten
        try:
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            _LOGGER.info("Alle Plattformen erfolgreich eingerichtet: %s", PLATFORMS)
        except Exception as e:
            _LOGGER.error("Fehler beim Einrichten der Plattformen: %s", str(e))
            return False
        
        # Performance-Monitor und Register-Optimizer initialisieren
        try:
            performance_monitor = PerformanceMonitor()
            register_optimizer = RegisterOptimizer(registers)
            
            hass.data[DOMAIN][entry.entry_id]["performance_monitor"] = performance_monitor
            hass.data[DOMAIN][entry.entry_id]["register_optimizer"] = register_optimizer
            
            _LOGGER.info("Performance-Monitor und Register-Optimizer initialisiert")
        except Exception as e:
            _LOGGER.warning("Performance-Monitor konnte nicht initialisiert werden: %s", str(e))
        
        # Aggregation-Manager initialisieren
        try:
            aggregation_manager = AggregationManager(hass, entry.data["prefix"])
            hass.data[DOMAIN][entry.entry_id]["aggregation_manager"] = aggregation_manager
            
            # Bestehende Gruppen entdecken
            await aggregation_manager.discover_existing_groups()
            _LOGGER.info("Aggregation-Manager initialisiert")
        except Exception as e:
            _LOGGER.warning("Aggregation-Manager konnte nicht initialisiert werden: %s", str(e))
        
        _LOGGER.info("Modbus Manager erfolgreich eingerichtet für %s", entry.data.get("prefix", "unbekannt"))
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler beim Setup von Modbus Manager: %s", str(e))
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        _LOGGER.info("Unload von Modbus Manager für %s", entry.data.get("prefix", "unbekannt"))
        
        # Alle Plattformen entladen
        try:
            await hass.config_entries.async_forward_entry_unloads(entry, PLATFORMS)
            _LOGGER.info("Alle Plattformen erfolgreich entladen: %s", PLATFORMS)
        except Exception as e:
            _LOGGER.error("Fehler beim Entladen der Plattformen: %s", str(e))
        
        # Modbus-Hub schließen
        if entry.entry_id in hass.data[DOMAIN]:
            hub_data = hass.data[DOMAIN][entry.entry_id]
            if "hub" in hub_data:
                try:
                    await hub_data["hub"].async_close()
                    _LOGGER.info("Modbus-Hub erfolgreich geschlossen")
                except Exception as e:
                    _LOGGER.warning("Fehler beim Schließen des Modbus-Hubs: %s", str(e))
            
            # Daten löschen
            del hass.data[DOMAIN][entry.entry_id]
        
        _LOGGER.info("Modbus Manager erfolgreich entladen für %s", entry.data.get("prefix", "unbekannt"))
        return True
        
    except Exception as e:
        _LOGGER.error("Fehler beim Unload von Modbus Manager: %s", str(e))
        return False
