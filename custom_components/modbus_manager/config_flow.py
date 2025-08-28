import os
import yaml
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, TEMPLATE_DIR

def load_templates():
    templates = {}
    for filename in os.listdir(TEMPLATE_DIR):
        if filename.endswith(".yaml"):
            with open(os.path.join(TEMPLATE_DIR, filename), "r") as f:
                data = yaml.safe_load(f)
                templates[data["name"]] = data
    return templates

class ModbusManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        templates = load_templates()
        template_names = list(templates.keys())

        if user_input is not None:
            selected_template = templates[user_input["template"]]
            return self.async_create_entry(
                title=f"{user_input['prefix']} ({user_input['template']})",
                data={
                    "template": user_input["template"],
                    "prefix": user_input["prefix"],
                    "host": user_input["host"],
                    "port": user_input["port"],
                    "slave_id": user_input["slave_id"],
                    "registers": selected_template["registers"]
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("template"): vol.In(template_names),
                vol.Required("prefix"): str,
                vol.Required("host"): str,
                vol.Optional("port", default=502): int,
                vol.Optional("slave_id", default=1): int,
            })
        )
