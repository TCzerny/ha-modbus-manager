"""The Modbus Manager integration."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SLAVE
from homeassistant.helpers import entity_registry, device_registry
from .const import DOMAIN, CONF_DEVICE_TYPE
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
    _LOGGER.debug("Setting up config entry", extra={"entry_id": entry.entry_id, "name": entry.data[CONF_NAME]})
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave = entry.data[CONF_SLAVE]
    device_type = entry.data[CONF_DEVICE_TYPE]
    
    # Erstelle Hub-Instanz
    hub = ModbusManagerHub(name, host, port, slave, device_type, hass)
    hub.config_entry = entry  # Füge config_entry zum Hub hinzu
    
    if not await hub.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = hub
    
    # Forward setup zu sensor und switch Plattformen
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch")
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Entlade einen Konfigurationseintrag und entferne alle zugehörigen Komponenten."""
    hub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        return True

    # Hole Registries
    ent_reg = entity_registry.async_get(hass)
    dev_reg = device_registry.async_get(hass)

    # Entferne alle Entitäten, die zu diesem Hub gehören
    device_entry = dev_reg.async_get_device(identifiers={(DOMAIN, hub.name)})
    if device_entry:
        ent_reg.async_remove(device_entry.id)

    # Entferne Templates und Automationen
    device_def = hub.get_device_definition(hub.device_type)
    if device_def:
        # Entferne Templates
        if 'helpers' in device_def and 'templates' in device_def['helpers']:
            for template_def in device_def['helpers']['templates']:
                template_name = f"{hub.name}_{template_def['name']}"
                template_entity_id = f"template.{template_name}"
                if ent_reg.async_get(template_entity_id):
                    _LOGGER.debug("Entferne Template: %s", template_name)
                    ent_reg.async_remove(template_entity_id)

        # Entferne Automationen
        if 'automations' in device_def:
            for automation in device_def['automations']:
                automation_name = f"{hub.name}_{automation['name']}"
                automation_entity_id = f"automation.{automation_name}"
                if ent_reg.async_get(automation_entity_id):
                    _LOGGER.debug("Entferne Automation: %s", automation_name)
                    ent_reg.async_remove(automation_entity_id)

    # Entlade Plattformen
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in ["sensor", "switch", "binary_sensor", "number"]
            ]
        )
    )

    if unload_ok:
        # Entferne Gerät aus dem Registry
        device_entry = dev_reg.async_get_device(identifiers={(DOMAIN, hub.name)})
        if device_entry:
            _LOGGER.debug("Entferne Gerät: %s", hub.name)
            dev_reg.async_remove_device(device_entry.id)

        # Schließe Verbindung und bereinige
        await hub.async_teardown()
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Modbus Manager Integration für %s erfolgreich entfernt", hub.name)

    return unload_ok