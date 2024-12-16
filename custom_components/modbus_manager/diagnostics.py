"""Diagnostics support for Modbus Manager."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from typing import Any
from .const import DOMAIN
from .modbus_hub import ModbusManagerHub

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub: ModbusManagerHub = hass.data[DOMAIN][entry.entry_id]
    
    try:
        diagnostics_data = {
            "config": {
                k: v for k, v in entry.data.items() 
                if k not in ("username", "password")
            },
            "device_info": getattr(hub, "device_info", {}),
            "performance_metrics": {
                "response_times": getattr(hub, "response_times", []),
                "error_rates": getattr(hub, "error_rates", {}),
                "last_successful_read": getattr(hub, "last_successful_read", None),
            },
            "register_stats": {
                "total_reads": getattr(hub, "total_reads", 0),
                "failed_reads": getattr(hub, "failed_reads", 0),
                "average_response_time": getattr(hub, "average_response_time", 0),
            },
            "connection_info": {
                "connected": getattr(hub, "is_connected", False),
                "last_connect_attempt": getattr(hub, "last_connect_attempt", None),
                "reconnect_count": getattr(hub, "reconnect_count", 0),
            }
        }
    except Exception as e:
        diagnostics_data = {
            "error": f"Failed to collect diagnostics: {str(e)}",
            "config": {
                k: v for k, v in entry.data.items() 
                if k not in ("username", "password")
            }
        }
    
    return diagnostics_data 