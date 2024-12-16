"""Generic template helpers for Modbus Manager."""
from typing import Dict, Any
from datetime import datetime, timedelta
from ..const import STAT_TYPES

class TemplateHelper:
    """Generic template helper class."""

    @staticmethod
    def create_energy_statistics_template(device_name: str, source_entity: str) -> Dict[str, Any]:
        """Create energy statistics templates for a device."""
        templates = {}
        
        for stat_type in STAT_TYPES:
            template_name = f"{device_name}_{stat_type}_energy"
            templates[template_name] = {
                "unique_id": template_name,
                "name": f"{device_name} {stat_type.capitalize()} Energy",
                "unit_of_measurement": "kWh",
                "device_class": "energy",
                "state_class": "total_increasing",
                "value_template": (
                    f"{{% set current = states('{source_entity}')|float(0) %}}\n"
                    f"{{% set stored = state_attr('sensor.{device_name}_statistics', '{stat_type}_energy')|float(0) %}}\n"
                    "{{ (current + stored)|round(1) }}"
                )
            }
        
        return templates

    @staticmethod
    def create_power_flow_template(device_name: str) -> Dict[str, Any]:
        """Create power flow template for a device."""
        return {
            "unique_id": f"{device_name}_power_flow",
            "name": f"{device_name} Power Flow",
            "icon": "mdi:flash",
            "value_template": (
                f"{{% set pv = states('sensor.{device_name}_pv_power')|float(0) %}}\n"
                f"{{% set grid = states('sensor.{device_name}_grid_power')|float(0) %}}\n"
                f"{{% set battery = states('sensor.{device_name}_battery_power')|float(0) %}}\n"
                f"{{% set load = states('sensor.{device_name}_load_power')|float(0) %}}\n"
                "{{ {'pv': pv, 'grid': grid, 'battery': battery, 'load': load} | tojson }}"
            )
        }

    @staticmethod
    def create_efficiency_template(device_name: str) -> Dict[str, Any]:
        """Create efficiency calculation template."""
        return {
            "unique_id": f"{device_name}_efficiency",
            "name": f"{device_name} Efficiency",
            "unit_of_measurement": "%",
            "value_template": (
                f"{{% set input = states('sensor.{device_name}_dc_power')|float(0) %}}\n"
                f"{{% set output = states('sensor.{device_name}_ac_power')|float(0) %}}\n"
                "{{ ((output / input * 100) if input > 0 else 0)|round(1) }}"
            )
        }