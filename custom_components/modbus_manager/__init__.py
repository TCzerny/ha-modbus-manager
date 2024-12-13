from homeassistant.core import HomeAssistant
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import template, entity_registry, device_registry
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.script import Script
from homeassistant.const import CONF_NAME
from .const import DOMAIN
from .modbus_sungrow import ModbusSungrowHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Richtet den Modbus Manager aus einem Konfigurationseintrag ein."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave = entry.data[CONF_SLAVE]
    device_type = entry.data["device_type"]
    
    hub = ModbusSungrowHub(name, host, port, slave, device_type, hass)
    await hub.async_setup()
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    
    # Weiterleitung der Einrichtung an Sensor- und Schalterplattformen
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch")
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Entlädt einen Konfigurationseintrag und entfernt alle zugehörigen Komponenten."""
    hub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        return True

    # Hole die Registries
    ent_reg = entity_registry.async_get(hass)
    dev_reg = device_registry.async_get(hass)

    # Entferne alle Entitäten, die zu diesem Hub gehören
    entity_entries = entity_registry.async_entries_for_device(
        ent_reg,
        device_id=(DOMAIN, hub.name),
        include_disabled_entities=True
    )
    
    _LOGGER.debug("Entferne %d Entitäten für %s", len(entity_entries), hub.name)
    
    for entity_entry in entity_entries:
        ent_reg.async_remove(entity_entry.entity_id)

    # Entferne Templates
    device_def = hub.get_device_definition(hub.device_type)
    if device_def and 'helpers' in device_def and 'templates' in device_def['helpers']:
        for template_def in device_def['helpers']['templates']:
            template_name = f"{hub.name}_{template_def['name']}"
            template_entity_id = f"template.{template_name}"
            if ent_reg.async_get(template_entity_id):
                _LOGGER.debug("Entferne Template: %s", template_name)
                ent_reg.async_remove(template_entity_id)

    # Entferne Automatisierungen
    if device_def and 'automations' in device_def:
        for automation in device_def['automations']:
            automation_name = f"{hub.name}_{automation['name']}"
            automation_entity_id = f"automation.{automation_name}"
            if ent_reg.async_get(automation_entity_id):
                _LOGGER.debug("Entferne Automation: %s", automation_name)
                ent_reg.async_remove(automation_entity_id)

    # Entlade die Plattformen
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in ["sensor", "switch"]
            ]
        )
    )

    # Entferne das Gerät aus der Registry
    device_entry = dev_reg.async_get_device({(DOMAIN, hub.name)})
    if device_entry:
        _LOGGER.debug("Entferne Gerät: %s", hub.name)
        dev_reg.async_remove_device(device_entry.id)

    # Beende die Modbus-Verbindung
    if unload_ok:
        await hub.async_teardown()
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Modbus Manager Integration für %s erfolgreich entfernt", hub.name)

    return unload_ok