"""Diagnostics support for Modbus Manager."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from typing import Any

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = hass.data["modbus_manager"][entry.entry_id]
    
    diagnostics_data = {
        "config": {
            k: v for k, v in entry.data.items() 
            if k not in ("username", "password")
        },
        "device_info": hub.device_info,
        "performance_metrics": {
            "response_times": hub.response_times,
            "error_rates": hub.error_rates,
            "last_successful_read": hub.last_successful_read,
        },
        "register_stats": {
            "total_reads": hub.total_reads,
            "failed_reads": hub.failed_reads,
            "average_response_time": hub.average_response_time,
        },
        "connection_info": {
            "connected": hub.is_connected,
            "last_connect_attempt": hub.last_connect_attempt,
            "reconnect_count": hub.reconnect_count,
        }
    }
    
    return diagnostics_data 