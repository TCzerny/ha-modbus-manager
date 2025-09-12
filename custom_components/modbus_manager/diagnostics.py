"""Diagnostics for Modbus Manager."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"password", "token", "secret"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    # Get the integration data
    data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {})

    # Get performance monitor if available
    performance_monitor = data.get("performance_monitor")
    performance_data = {}
    if performance_monitor:
        performance_data = {
            "global_metrics": performance_monitor.get_global_metrics().__dict__,
            "device_metrics": {
                device_id: device_metrics.__dict__
                for device_id, device_metrics in performance_monitor.devices.items()
            },
            "recent_operations": performance_monitor.get_recent_operations(limit=20),
            "performance_summary": performance_monitor.get_performance_summary(),
        }

    # Get register optimizer if available
    register_optimizer = data.get("register_optimizer")
    optimization_data = {}
    if register_optimizer:
        # Get registers from config
        registers = config_entry.data.get("registers", [])
        if registers:
            optimization_data = {
                "max_read_size": register_optimizer.max_read_size,
                "optimization_stats": register_optimizer.calculate_optimization_stats(
                    registers
                ),
                "optimized_ranges": [
                    {
                        "start_address": range_obj.start_address,
                        "end_address": range_obj.end_address,
                        "register_count": range_obj.register_count,
                        "registers": [
                            reg.get("name", "unknown") for reg in range_obj.registers
                        ],
                    }
                    for range_obj in register_optimizer.optimize_registers(registers)
                ],
            }

    # Get template information
    template_data = {
        "template_name": config_entry.data.get("template"),
        "template_version": config_entry.data.get("template_version"),
        "prefix": config_entry.data.get("prefix"),
        "total_registers": len(config_entry.data.get("registers", [])),
        "total_calculated": len(config_entry.data.get("calculated_entities", [])),
        "total_aggregates": len(config_entry.data.get("aggregates", [])),
        "has_dynamic_config": "dynamic_config" in config_entry.data,
    }

    # Compile diagnostics
    diagnostics = {
        "config_entry": async_redact_data(config_entry.data, TO_REDACT),
        "template_info": template_data,
        "performance_data": performance_data,
        "optimization_data": optimization_data,
        "integration_data_keys": list(data.keys()) if data else [],
    }

    return diagnostics
