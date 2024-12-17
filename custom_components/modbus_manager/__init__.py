"""The Modbus Manager integration."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
from homeassistant.helpers import entity_registry, device_registry
from .const import DOMAIN
from .modbus_hub import ModbusManagerHub
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger("init")

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Modbus Manager component."""
    _LOGGER.debug("Setting up Modbus Manager integration")
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Modbus Manager from a config entry."""
    _LOGGER.debug("Setting up config entry", entry_id=entry.entry_id, name=entry.data[CONF_NAME])
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave = entry.data[CONF_SLAVE]
    device_type = entry.data["device_type"]
    
    # Erstelle Hub-Instanz
    hub = ModbusManagerHub(name, host, port, slave, device_type, hass)
    hub.config_entry = entry  # Füge config_entry zum Hub hinzu
    
    if not await hub.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = hub
    
    # Forward setup to sensor and switch platforms
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch")
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a configuration entry and remove all associated components."""
    hub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        return True

    # Get registries
    ent_reg = entity_registry.async_get(hass)
    dev_reg = device_registry.async_get(hass)

    # Remove all entities belonging to this hub
    entity_entries = entity_registry.async_entries_for_device(
        ent_reg,
        device_id=(DOMAIN, hub.name),
        include_disabled_entities=True
    )
    
    _LOGGER.debug("Removing %d entities for %s", len(entity_entries), hub.name)
    
    for entity_entry in entity_entries:
        ent_reg.async_remove(entity_entry.entity_id)

    # Remove templates and helpers
    device_def = hub.get_device_definition(hub.device_type)
    if device_def:
        # Remove templates
        if 'helpers' in device_def and 'templates' in device_def['helpers']:
            for template_def in device_def['helpers']['templates']:
                template_name = f"{hub.name}_{template_def['name']}"
                template_entity_id = f"template.{template_name}"
                if ent_reg.async_get(template_entity_id):
                    _LOGGER.debug("Removing template: %s", template_name)
                    ent_reg.async_remove(template_entity_id)

        # Remove automations
        if 'automations' in device_def:
            for automation in device_def['automations']:
                automation_name = f"{hub.name}_{automation['name']}"
                automation_entity_id = f"automation.{automation_name}"
                if ent_reg.async_get(automation_entity_id):
                    _LOGGER.debug("Removing automation: %s", automation_name)
                    ent_reg.async_remove(automation_entity_id)

    # Unload platforms
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in ["sensor", "switch", "binary_sensor", "number"]
            ]
        )
    )

    if unload_ok:
        # Remove device from registry
        device_entry = dev_reg.async_get_device({(DOMAIN, hub.name)})
        if device_entry:
            _LOGGER.debug("Removing device: %s", hub.name)
            dev_reg.async_remove_device(device_entry.id)

        # Close connection and cleanup
        await hub.async_teardown()
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Successfully removed Modbus Manager integration for %s", hub.name)

    return unload_ok