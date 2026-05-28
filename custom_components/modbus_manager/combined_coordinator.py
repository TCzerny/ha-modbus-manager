"""Coordinator for virtual cross-hub combined devices."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


class CombinedDeviceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Cache-only coordinator that aggregates data from two source entries."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize combined device coordinator."""
        self.entry = entry
        self._is_unloading = False
        super().__init__(
            hass,
            _LOGGER,
            name=f"Combined Coordinator {entry.data.get('combined_prefix', entry.entry_id)}",
            update_interval=timedelta(seconds=5),
        )

    def mark_as_unloading(self) -> None:
        """Stop future refresh processing during unload."""
        self._is_unloading = True

    def _source_payload(self, source_entry_id: str | None) -> dict[str, Any]:
        """Return minimal runtime payload for one source entry."""
        if not source_entry_id:
            return {"entry_id": None, "available": False, "data": {}}

        source_data = self.hass.data.get(DOMAIN, {}).get(source_entry_id)
        if not isinstance(source_data, dict):
            return {"entry_id": source_entry_id, "available": False, "data": {}}

        source_coordinator = source_data.get("coordinator")
        if source_coordinator is None:
            return {"entry_id": source_entry_id, "available": False, "data": {}}

        coordinator_data = getattr(source_coordinator, "data", {}) or {}
        available = bool(coordinator_data)
        return {
            "entry_id": source_entry_id,
            "available": available,
            "data": coordinator_data,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Aggregate source coordinator snapshots without additional Modbus I/O."""
        if self._is_unloading:
            return self.data or {}

        source_a_id = self.entry.data.get("source_entry_id_a")
        source_b_id = self.entry.data.get("source_entry_id_b")
        source_a = self._source_payload(source_a_id)
        source_b = self._source_payload(source_b_id)

        return {
            "combined_prefix": self.entry.data.get("combined_prefix"),
            "combination_type": self.entry.data.get("combination_type"),
            "sources": {
                "a": source_a,
                "b": source_b,
            },
            "available": bool(source_a.get("available") or source_b.get("available")),
        }
