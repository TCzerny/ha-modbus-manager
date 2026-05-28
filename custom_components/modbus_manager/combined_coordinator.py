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

    @staticmethod
    def _extract_metric_value(
        source_data: dict[str, Any], metric_candidates: list[str]
    ) -> float | None:
        """Extract first matching numeric metric from one source payload."""
        for register_data in source_data.values():
            if not isinstance(register_data, dict):
                continue
            register_config = register_data.get("register_config", {})
            if not isinstance(register_config, dict):
                continue
            register_unique_id = (
                str(register_config.get("unique_id", "")).strip().lower()
            )
            if not register_unique_id:
                continue
            if not any(
                register_unique_id.endswith(f"_{candidate}")
                for candidate in metric_candidates
            ):
                continue

            value = register_data.get(
                "numeric_value", register_data.get("processed_value")
            )
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Aggregate source coordinator snapshots without additional Modbus I/O."""
        if self._is_unloading:
            return self.data or {}

        source_a_id = self.entry.data.get("source_entry_id_a")
        source_b_id = self.entry.data.get("source_entry_id_b")
        source_a = self._source_payload(source_a_id)
        source_b = self._source_payload(source_b_id)
        metrics: dict[str, Any] = {}

        if self.entry.data.get("combination_type") == "inverter_inverter":
            source_a_data = (
                source_a.get("data", {})
                if isinstance(source_a.get("data"), dict)
                else {}
            )
            source_b_data = (
                source_b.get("data", {})
                if isinstance(source_b.get("data"), dict)
                else {}
            )

            active_power_candidates = [
                "total_active_power",
                "active_power",
                "meter_active_power",
            ]
            pv_power_candidates = [
                "total_pv_generation",
                "pv_power_total",
                "pv_total_power",
            ]

            source_a_active = self._extract_metric_value(
                source_a_data, active_power_candidates
            )
            source_b_active = self._extract_metric_value(
                source_b_data, active_power_candidates
            )
            source_a_pv = self._extract_metric_value(source_a_data, pv_power_candidates)
            source_b_pv = self._extract_metric_value(source_b_data, pv_power_candidates)

            if source_a_active is not None and source_b_active is not None:
                metrics["combined_total_active_power"] = round(
                    source_a_active + source_b_active, 3
                )
            if source_a_pv is not None and source_b_pv is not None:
                metrics["combined_total_pv_generation"] = round(
                    source_a_pv + source_b_pv, 3
                )

        return {
            "combined_prefix": self.entry.data.get("combined_prefix"),
            "combination_type": self.entry.data.get("combination_type"),
            "metrics": metrics,
            "sources": {
                "a": source_a,
                "b": source_b,
            },
            "available": bool(source_a.get("available") or source_b.get("available")),
        }
