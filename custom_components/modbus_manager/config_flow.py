"""Config flow for Modbus Manager."""
from __future__ import annotations

import os
import yaml
from typing import Any
import voluptuous as vol
import aiofiles
import asyncio
from pathlib import Path

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE,
    CONF_DEVICE_TYPE,
)

class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Manager."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Erstelle eine eindeutige ID für den Config Entry
                unique_id = f"{user_input[CONF_HOST]}_{user_input[CONF_PORT]}_{user_input[CONF_SLAVE]}_{user_input[CONF_NAME]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input
                )
            except Exception as e:
                errors["base"] = str(e)

        # Lade die verfügbaren Device-Definitionen
        device_types = []
        device_defaults = {}
        definitions_path = Path(__file__).parent / "device_definitions"
        
        if definitions_path.exists():
            # Verwende asyncio.to_thread für das Auflisten der Dateien
            filenames = await asyncio.to_thread(lambda: [f.name for f in definitions_path.glob("*.yaml")])
            
            for filename in filenames:
                device_type = filename.replace(".yaml", "")
                device_types.append(device_type)
                
                # Lade die Default-Werte aus der Device-Definition
                try:
                    async with aiofiles.open(definitions_path / filename, mode='r') as f:
                        content = await f.read()
                        try:
                            config = yaml.safe_load(content)
                            if "device_config" in config:
                                device_defaults[device_type] = {
                                    "port": config["device_config"].get("port", 502),
                                    "slave": config["device_config"].get("slave", 1)
                                }
                        except yaml.YAMLError:
                            continue
                except Exception:
                    continue

        # Bestimme die Default-Werte basierend auf dem ausgewählten Device Type
        default_port = 502
        default_slave = 1
        if user_input and CONF_DEVICE_TYPE in user_input:
            device_type = user_input[CONF_DEVICE_TYPE]
            if device_type in device_defaults:
                default_port = device_defaults[device_type]["port"]
                default_slave = device_defaults[device_type]["slave"]

        # Zeige das Formular
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=default_port): int,
                    vol.Required(CONF_SLAVE, default=default_slave): int,
                    vol.Required(CONF_DEVICE_TYPE): vol.In(device_types),
                }
            ),
            errors=errors,
        )