"""Generic automation helpers for Modbus Manager."""
from typing import Dict, Any

class AutomationHelper:
    """Generic automation helper class."""

    @staticmethod
    def create_energy_storage_automation(device_name: str) -> Dict[str, Any]:
        """Create energy storage automation for statistics."""
        return {
            "id": f"{device_name}_energy_storage",
            "alias": f"{device_name} Energy Storage",
            "trigger": {
                "platform": "time",
                "at": "00:00:00"
            },
            "action": [
                {
                    "service": "input_number.set_value",
                    "target": {
                        "entity_id": f"input_number.{device_name}_daily_energy"
                    },
                    "data": {
                        "value": "{{ states('sensor.daily_energy')|float(0) }}"
                    }
                }
            ]
        }

    @staticmethod
    def create_error_notification_automation(device_name: str) -> Dict[str, Any]:
        """Create error notification automation."""
        return {
            "id": f"{device_name}_error_notification",
            "alias": f"{device_name} Error Notification",
            "trigger": {
                "platform": "state",
                "entity_id": f"sensor.{device_name}_error_code"
            },
            "condition": {
                "condition": "numeric_state",
                "entity_id": f"sensor.{device_name}_error_code",
                "above": 0
            },
            "action": {
                "service": "notify.notify",
                "data": {
                    "title": f"{device_name} Error",
                    "message": "Error code: {{ trigger.to_state.state }}"
                }
            }
        }