"""Config flow for Modbus Manager."""
from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
)
from homeassistant.components.modbus.const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    MODBUS_DOMAIN,
)
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_DEVICE_TYPE,
    DEFAULT_TIMEOUT,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): int,
        vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): int,
        vol.Required(CONF_DEVICE_TYPE): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
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
            # Erstelle zuerst den Standard Modbus Hub
            modbus_data = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_SLAVE: user_input[CONF_SLAVE],
                CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            }

            # Erstelle den Standard Modbus Hub
            modbus_entry = await self.hass.config_entries.flow.async_init(
                MODBUS_DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=modbus_data,
            )

            if modbus_entry.type == config_entries.RESULT_TYPE_CREATE_ENTRY:
                # Speichere die Modbus Entry ID für spätere Referenz
                user_input["modbus_entry_id"] = modbus_entry.entry_id
                
                await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_NAME]}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )