"""Generic template helpers for Modbus Manager."""

from datetime import datetime, timedelta
from typing import Any, Dict

from custom_components.modbus_manager.const import DOMAIN, STAT_TYPES

from homeassistant.components.sensor.const import (
    DEVICE_CLASS_STATE_CLASSES,
    SensorDeviceClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.components.template.sensor import SensorTemplate
from homeassistant.helpers.template import Template
from homeassistant.helpers.entity_platform import AddEntitiesCallback


class TemplateHelper:
    """Generic template helper class."""

    async def setup_template(
        self, hass: HomeAssistant, template_id: str, template_config: Dict[str, Any]
    ) -> None:
        """Setup a template entity in Home Assistant."""
        try:
            # Hole die Registries
            entity_registry = er.async_get(hass)

            # Erstelle eine eindeutige Entity-ID
            unique_id = template_config.get("unique_id", template_id)
            entity_id = f"sensor.{template_id}"

            # Erstelle die Template-Sensor-Konfiguration
            name = template_config.get("name", template_id)
            value_template = Template(template_config.get("value_template", ""), "")
            icon = Template(template_config.get("icon", "mdi:flash"), hass)

            # Erstelle den Template-Sensor
            sensor = SensorTemplate(
                hass=hass,
                unique_id=unique_id,
                config={
                    "fallback_name": name,
                    "unique_id": unique_id,
                    "state": value_template,
                    "unit_of_measurement": template_config.get("unit_of_measurement"),
                    "device_class": template_config.get("device_class"),
                    "state_class": template_config.get("state_class"),
                    "icon": icon,
                    "attributes": template_config.get("attributes", {}),
                }
            )

            # Füge den Sensor zum Entity Registry hinzu
            entity_registry.async_get_or_create(
                domain="sensor",
                platform="template",
                unique_id=unique_id,
                config_entry=None,
                device_id=None,
                original_name=name,
                suggested_object_id=template_id,
                original_device_class=template_config.get("device_class"),
                unit_of_measurement=template_config.get("unit_of_measurement"),
                capabilities={
                    "state_class": template_config.get("state_class"),
                    "unit_of_measurement": template_config.get("unit_of_measurement"),
                    "device_class": template_config.get("device_class"),
                },
                disabled_by=None
            )

            # Initialisiere den Sensor
            await sensor.async_added_to_hass()
            await sensor.async_update()

        except Exception as e:
            raise Exception(f"Fehler beim Setup des Templates {template_id}: {str(e)}")

    @staticmethod
    def create_energy_statistics_template(
        device_name: str, source_entity: str
    ) -> Dict[str, Any]:
        """Create energy statistics templates for a device."""
        templates = {}

        for stat_type in STAT_TYPES:
            template_name = f"{device_name}_{stat_type}_energy"
            templates[template_name] = {
                "unique_id": template_name,
                "name": f"{device_name} {stat_type.capitalize()} Energy",
                "unit_of_measurement": "kWh",
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": "total_increasing",
                "value_template": (
                    f"{{% set current = states('{source_entity}')|float(0) %}}\n"
                    f"{{% set stored = state_attr('sensor.{device_name}_statistics', '{stat_type}_energy')|float(0) %}}\n"
                    "{{ (current + stored)|round(1) }}"
                ),
                "icon": "mdi:lightning-bolt",
            }

        return templates

    @staticmethod
    def create_power_flow_template(device_name: str) -> Dict[str, Any]:
        """Create power flow template for a device."""
        return {
            "unique_id": f"{device_name}_power_flow",
            "name": f"{device_name} Power Flow",
            "icon": "mdi:flash",
            "unit_of_measurement": "W",
            "device_class": SensorDeviceClass.POWER,
            "state_class": "measurement",
            "value_template": (
                f"{{% set pv = states('sensor.{device_name}_pv_power')|float(0) %}}\n"
                f"{{% set grid = states('sensor.{device_name}_grid_power')|float(0) %}}\n"
                f"{{% set battery = states('sensor.{device_name}_battery_power')|float(0) %}}\n"
                f"{{% set load = states('sensor.{device_name}_load_power')|float(0) %}}\n"
                "{{ {'pv': pv, 'grid': grid, 'battery': battery, 'load': load} | tojson }}"
            ),
        }

    @staticmethod
    def create_efficiency_template(device_name: str) -> Dict[str, Any]:
        """Create efficiency calculation template."""
        return {
            "unique_id": f"{device_name}_efficiency",
            "name": f"{device_name} Efficiency",
            "unit_of_measurement": PERCENTAGE,
            "state_class": "measurement",
            "icon": "mdi:percent",
            "value_template": (
                f"{{% set input = states('sensor.{device_name}_dc_power')|float(0) %}}\n"
                f"{{% set output = states('sensor.{device_name}_ac_power')|float(0) %}}\n"
                "{{ ((output / input * 100) if input > 0 else 0)|round(1) }}"
            ),
        }
