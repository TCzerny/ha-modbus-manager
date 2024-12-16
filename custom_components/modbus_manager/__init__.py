"""Die Modbus Manager Integration."""

import asyncio
from datetime import timedelta
import logging
import os
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SLAVE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import template, discovery

from .const import CONF_DEVICE_TYPE, DEFAULT_SLAVE_ID, DOMAIN
from .logger import ModbusManagerLogger
from .modbus_hub import ModbusManagerHub
from .helpers.templates import TemplateHelper
from .helpers.automations import AutomationHelper
from .helpers.entity_helper import EntityHelper

_LOGGER = ModbusManagerLogger(__name__)

# Nur die tatsächlich implementierten Plattformen auflisten
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Richte die Modbus Manager Integration ein."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def setup_helpers(hass: HomeAssistant, entry: ConfigEntry, device_def: dict) -> None:
    """Richte Templates, Automationen und Entities ein."""
    device_name = entry.data[CONF_NAME]
    
    # Initialisiere Helper
    template_helper = TemplateHelper()
    automation_helper = AutomationHelper()
    entity_helper = EntityHelper(hass.config.config_dir)
    
    try:
        # Lade gemeinsame Entities
        common_entities = await hass.async_add_executor_job(entity_helper.load_common_entities)
        if common_entities:
            _LOGGER.debug(
                "Gemeinsame Entities geladen",
                extra={
                    "entry_id": entry.entry_id,
                    "count": len(common_entities)
                }
            )
            
            # Erstelle die Entities
            for platform, entities in common_entities.items():
                for entity in entities:
                    # Füge Gerätenamen zu Entity-IDs hinzu
                    if "entity_id" in entity:
                        entity["entity_id"] = f"{entity['entity_id']}_{device_name}"
                    
                    # Registriere die Entity
                    await discovery.async_load_platform(
                        hass,
                        platform,
                        DOMAIN,
                        {"config": entity},
                        entry.data
                    )
        
        # Erstelle Templates basierend auf der Gerätedefinition
        if device_def.get("supports_energy_monitoring", False):
            templates = template_helper.create_energy_statistics_template(
                device_name,
                f"sensor.{device_name}_energy"
            )
            for template_id, template_config in templates.items():
                await template.async_setup_template_entity(
                    hass,
                    template_id,
                    template_config
                )
        
        if device_def.get("supports_power_flow", False):
            power_flow = template_helper.create_power_flow_template(device_name)
            await template.async_setup_template_entity(
                hass,
                power_flow["unique_id"],
                power_flow
            )
        
        if device_def.get("supports_efficiency", False):
            efficiency = template_helper.create_efficiency_template(device_name)
            await template.async_setup_template_entity(
                hass,
                efficiency["unique_id"],
                efficiency
            )
        
        # Erstelle Automationen basierend auf der Gerätedefinition
        if device_def.get("supports_energy_storage", False):
            automation = automation_helper.create_energy_storage_automation(device_name)
            await hass.services.async_call(
                "automation",
                "reload",
                {
                    "entity_id": f"automation.{automation['id']}"
                }
            )
        
        if device_def.get("supports_error_notification", False):
            automation = automation_helper.create_error_notification_automation(device_name)
            await hass.services.async_call(
                "automation",
                "reload",
                {
                    "entity_id": f"automation.{automation['id']}"
                }
            )
            
        _LOGGER.info(
            "Helper erfolgreich eingerichtet",
            extra={
                "entry_id": entry.entry_id,
                "name": device_name
            }
        )
            
    except Exception as e:
        _LOGGER.error(
            "Fehler beim Einrichten der Helper",
            extra={
                "entry_id": entry.entry_id,
                "error": str(e)
            }
        )
        raise


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richte die Modbus Manager Integration ein."""
    _LOGGER.debug(
        "Setup Entry wird ausgeführt",
        extra={
            "entry_id": entry.entry_id,
            "data": entry.data
        }
    )

    # Stelle sicher, dass DOMAIN in hass.data existiert
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    try:
        # Erstelle den Hub
        hub = ModbusManagerHub(
            name=entry.data[CONF_NAME],
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            slave=entry.data.get(CONF_SLAVE, DEFAULT_SLAVE_ID),
            device_type=entry.data[CONF_DEVICE_TYPE],
            hass=hass,
            config_entry=entry,
        )

        # Speichere den Hub in hass.data
        hass.data[DOMAIN][entry.entry_id] = hub
        
        _LOGGER.debug(
            "Hub erstellt und gespeichert",
            extra={
                "entry_id": entry.entry_id,
                "hub_name": hub.name
            }
        )

        if not await hub.async_setup():
            _LOGGER.error(
                "Hub Setup fehlgeschlagen",
                extra={
                    "entry_id": entry.entry_id,
                    "host": entry.data[CONF_HOST],
                    "port": entry.data[CONF_PORT]
                }
            )
            raise ConfigEntryNotReady(
                f"Fehler beim Verbindungsaufbau zu {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
            )

        # Hole die Gerätedefinition
        device_def = await hub.get_device_definition(hub.device_type)
        if not device_def:
            _LOGGER.error(
                "Keine Gerätekonfiguration gefunden",
                extra={
                    "entry_id": entry.entry_id,
                    "device_type": hub.device_type
                }
            )
            return False

        # Richte Helper ein
        await setup_helpers(hass, entry, device_def)

        # Lade die Plattformen
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        _LOGGER.info(
            "Integration erfolgreich eingerichtet",
            extra={
                "entry_id": entry.entry_id,
                "name": hub.name
            }
        )

        return True

    except Exception as e:
        _LOGGER.error(
            "Fehler beim Setup der Integration",
            extra={
                "entry_id": entry.entry_id,
                "error": str(e)
            }
        )
        raise


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entlade einen Config Entry."""
    _LOGGER.debug(
        "Entlade Entry",
        extra={
            "entry_id": entry.entry_id
        }
    )

    try:
        # Prüfe ob der Hub existiert
        if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.warning(
                "Hub nicht gefunden beim Entladen",
                extra={
                    "entry_id": entry.entry_id
                }
            )
            return True

        hub: ModbusManagerHub = hass.data[DOMAIN][entry.entry_id]

        # Entlade alle Plattformen
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        if unload_ok:
            # Beende den Hub
            await hub.async_teardown()
            hass.data[DOMAIN].pop(entry.entry_id)
            _LOGGER.info(
                "Integration erfolgreich entladen",
                extra={
                    "entry_id": entry.entry_id
                }
            )

        return unload_ok

    except Exception as e:
        _LOGGER.error(
            "Fehler beim Entladen der Integration",
            extra={
                "entry_id": entry.entry_id,
                "error": str(e)
            }
        )
        return False
