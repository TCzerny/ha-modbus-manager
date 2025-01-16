"""Config flow for Modbus Manager."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_get_available_device_definitions() -> dict[str, str]:
    """Liest die verfügbaren Gerätedefinitionen aus dem device_definitions Verzeichnis."""
    definitions = {}
    definition_dir = os.path.join(os.path.dirname(__file__), "device_definitions")
    
    try:
        # Verwende aiofiles.os für asynchrones Auflisten der Dateien
        filenames = await aiofiles.os.listdir(definition_dir)
        
        for filename in filenames:
            if filename.endswith(".yaml"):
                device_type = filename[:-5]  # Entferne .yaml
                # Lade die YAML-Datei um den Anzeigenamen zu erhalten
                try:
                    async with aiofiles.open(os.path.join(definition_dir, filename), mode='r', encoding='utf-8') as f:
                        content = await f.read()
                        device_config = yaml.safe_load(content)
                        display_name = device_config.get("device_info", {}).get("name", device_type)
                        definitions[device_type] = display_name
                except Exception:
                    definitions[device_type] = device_type.replace("_", " ").title()
    except Exception:
        pass
    
    return definitions

class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Manager."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors = {}

        # Hole die verfügbaren Gerätedefinitionen
        device_definitions = await async_get_available_device_definitions()
        
        if not device_definitions:
            errors["base"] = "no_device_definitions"
            return self.async_abort(reason="no_device_definitions")

        if user_input is not None:
            # Prüfe ob der Name bereits existiert
            device_registry = dr.async_get(self.hass)
            existing_devices = dr.async_entries_for_config_entry(
                device_registry, self.context.get("entry_id", "")
            )
            
            # Prüfe auch andere Config Entries für den gleichen Namen
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data.get(CONF_NAME) == user_input[CONF_NAME]:
                    errors["name"] = "device_exists"
                    break
            
            # Prüfe auch das Geräteregister
            for device in existing_devices:
                if device.name == user_input[CONF_NAME]:
                    errors["name"] = "device_exists"
                    break

            if not errors:
                try:
                    # Erstelle eine eindeutige ID aus Name und Host
                    await self.async_set_unique_id(f"{user_input[CONF_NAME]}_{user_input[CONF_HOST]}")
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input,
                    )
                    
                except Exception:
                    errors["base"] = "unknown"

        # Erstelle das Schema für das Formular
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): int,
                vol.Required(CONF_DEVICE_TYPE): vol.In(device_definitions),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )