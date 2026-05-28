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
    def _extract_metric_record(
        source_data: dict[str, Any], metric_candidates: list[str]
    ) -> dict[str, Any] | None:
        """Extract first matching numeric metric and source metadata."""
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
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue

            return {
                "value": numeric_value,
                "unique_id": register_unique_id,
                "unit_of_measurement": register_config.get("unit_of_measurement"),
                "device_class": register_config.get("device_class"),
                "state_class": register_config.get("state_class"),
                "precision": register_config.get("precision"),
                "scale": register_config.get("scale"),
            }
        return None

    @staticmethod
    def _convert_unit(
        value: float, from_unit: str | None, to_unit: str | None
    ) -> float | None:
        """Convert value between a minimal set of compatible units."""
        if from_unit == to_unit:
            return value
        if not from_unit or not to_unit:
            return None

        normalized_from = str(from_unit).strip()
        normalized_to = str(to_unit).strip()
        conversions = {
            ("W", "kW"): 0.001,
            ("kW", "W"): 1000.0,
            ("Wh", "kWh"): 0.001,
            ("kWh", "Wh"): 1000.0,
        }
        factor = conversions.get((normalized_from, normalized_to))
        if factor is None:
            return None
        return value * factor

    def _combine_metric(
        self,
        source_a_data: dict[str, Any],
        source_b_data: dict[str, Any],
        metric_candidates: list[str],
    ) -> tuple[float | None, dict[str, Any] | None]:
        """Combine one metric with source-template unit/precision metadata."""
        record_a = self._extract_metric_record(source_a_data, metric_candidates)
        record_b = self._extract_metric_record(source_b_data, metric_candidates)
        if not record_a or not record_b:
            return None, None

        output_unit = record_a.get("unit_of_measurement") or record_b.get(
            "unit_of_measurement"
        )
        value_a = float(record_a["value"])
        value_b = float(record_b["value"])

        unit_a = record_a.get("unit_of_measurement")
        unit_b = record_b.get("unit_of_measurement")
        if output_unit:
            if unit_a and unit_a != output_unit:
                converted_a = self._convert_unit(value_a, unit_a, output_unit)
                if converted_a is None:
                    return None, None
                value_a = converted_a
            if unit_b and unit_b != output_unit:
                converted_b = self._convert_unit(value_b, unit_b, output_unit)
                if converted_b is None:
                    return None, None
                value_b = converted_b

        precision = record_a.get("precision")
        if precision is None:
            precision = record_b.get("precision")

        summed = value_a + value_b
        if isinstance(precision, int):
            summed = round(summed, precision)
        else:
            summed = round(summed, 3)

        metadata = {
            "unit_of_measurement": output_unit,
            "device_class": record_a.get("device_class")
            or record_b.get("device_class"),
            "state_class": record_a.get("state_class") or record_b.get("state_class"),
            "precision": precision,
            "source_a_unit": unit_a,
            "source_b_unit": unit_b,
            "source_a_unique_id": record_a.get("unique_id"),
            "source_b_unique_id": record_b.get("unique_id"),
        }
        return summed, metadata

    async def _async_update_data(self) -> dict[str, Any]:
        """Aggregate source coordinator snapshots without additional Modbus I/O."""
        if self._is_unloading:
            return self.data or {}

        source_a_id = self.entry.data.get("source_entry_id_a")
        source_b_id = self.entry.data.get("source_entry_id_b")
        source_a = self._source_payload(source_a_id)
        source_b = self._source_payload(source_b_id)
        metrics: dict[str, Any] = {}
        metric_meta: dict[str, Any] = {}

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

            combined_active, active_meta = self._combine_metric(
                source_a_data,
                source_b_data,
                active_power_candidates,
            )
            combined_pv, pv_meta = self._combine_metric(
                source_a_data,
                source_b_data,
                pv_power_candidates,
            )

            if combined_active is not None:
                metrics["combined_total_active_power"] = combined_active
                if active_meta:
                    metric_meta["combined_total_active_power"] = active_meta
            if combined_pv is not None:
                metrics["combined_total_pv_generation"] = combined_pv
                if pv_meta:
                    metric_meta["combined_total_pv_generation"] = pv_meta

        return {
            "combined_prefix": self.entry.data.get("combined_prefix"),
            "combination_type": self.entry.data.get("combination_type"),
            "metrics": metrics,
            "metric_meta": metric_meta,
            "sources": {
                "a": source_a,
                "b": source_b,
            },
            "available": bool(source_a.get("available") or source_b.get("available")),
        }
