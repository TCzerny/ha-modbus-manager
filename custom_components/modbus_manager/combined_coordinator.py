"""Coordinator for virtual cross-hub combined devices."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .combined_daily_meter import CombinedDailyMeterPair
from .combined_specs import (
    COMBINED_BINARY_METRIC_SPECS,
    COMBINED_SENSOR_METRIC_SPECS,
    SOURCE_ROLE_IHM,
    SOURCE_ROLE_INVERTER,
    combination_type_for_entry,
)
from .const import DOMAIN
from .device_utils import entry_device_type_set
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

_CONSUMED_FORMULA = "pv - export + import - battery_charge + battery_discharge"


class CombinedDeviceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Cache-only coordinator that aggregates data from two source entries."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize combined device coordinator."""
        self.entry = entry
        self._is_unloading = False
        self._daily_meters: CombinedDailyMeterPair | None = None
        self._daily_meters_loaded = False
        super().__init__(
            hass,
            _LOGGER,
            name=f"Combined Coordinator {entry.data.get('combined_prefix', entry.entry_id)}",
            update_interval=timedelta(seconds=5),
        )

    def mark_as_unloading(self) -> None:
        """Stop future refresh processing during unload."""
        self._is_unloading = True

    async def async_load_daily_meters(self) -> None:
        """Load persisted daily grid counters."""
        if self.entry.data.get("combination_type") != "inverter_ihm":
            return
        if self._daily_meters is None:
            self._daily_meters = CombinedDailyMeterPair(self.hass, self.entry.entry_id)
        if not self._daily_meters_loaded:
            await self._daily_meters.async_load()
            self._daily_meters_loaded = True

    async def async_remove_daily_meters(self) -> None:
        """Remove persisted daily counters for this combined entry."""
        if self._daily_meters is not None:
            await self._daily_meters.async_remove_entry()

    def _update_ihm_daily_meters(
        self, role_data: dict[str, dict[str, Any]]
    ) -> dict[str, float | None]:
        """Update persistent iHM import/export daily counters."""
        if self._daily_meters is None:
            return {}

        import_record = self._extract_metric_record(
            role_data.get(SOURCE_ROLE_IHM, {}),
            ["grid_import_energy"],
        )
        export_record = self._extract_metric_record(
            role_data.get(SOURCE_ROLE_IHM, {}),
            ["grid_export_energy"],
        )
        import_total = float(import_record["value"]) if import_record else None
        export_total = float(export_record["value"]) if export_record else None
        return self._daily_meters.update(
            import_total=import_total,
            export_total=export_total,
            now=dt_util.now(),
            import_unique_id=(
                import_record.get("unique_id") if import_record else None
            ),
            export_unique_id=(
                export_record.get("unique_id") if export_record else None
            ),
        )

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
        aggregation: str = "sum",
        required_sources: str = "both",
    ) -> tuple[float | None, dict[str, Any] | None]:
        """Combine one metric with source-template unit/precision metadata."""
        record_a = self._extract_metric_record(source_a_data, metric_candidates)
        record_b = self._extract_metric_record(source_b_data, metric_candidates)
        if required_sources == "both":
            if not record_a or not record_b:
                return None, None
        elif required_sources == "any":
            if not record_a and not record_b:
                return None, None
        else:
            return None, None

        output_unit = record_a.get("unit_of_measurement") or record_b.get(
            "unit_of_measurement"
        )
        value_a = float(record_a["value"]) if record_a else 0.0
        value_b = float(record_b["value"]) if record_b else 0.0

        unit_a = record_a.get("unit_of_measurement") if record_a else None
        unit_b = record_b.get("unit_of_measurement") if record_b else None
        if output_unit:
            if record_a and unit_a and unit_a != output_unit:
                converted_a = self._convert_unit(value_a, unit_a, output_unit)
                if converted_a is None:
                    return None, None
                value_a = converted_a
            if record_b and unit_b and unit_b != output_unit:
                converted_b = self._convert_unit(value_b, unit_b, output_unit)
                if converted_b is None:
                    return None, None
                value_b = converted_b

        precision = record_a.get("precision") if record_a else None
        if precision is None and record_b:
            precision = record_b.get("precision")

        values = []
        if record_a:
            values.append(value_a)
        if record_b:
            values.append(value_b)
        if not values:
            return None, None

        if aggregation == "sum":
            combined_value = sum(values)
        elif aggregation == "avg":
            combined_value = sum(values) / len(values)
        elif aggregation == "max":
            combined_value = max(values)
        elif aggregation == "min":
            combined_value = min(values)
        else:
            return None, None

        if isinstance(precision, int):
            combined_value = round(combined_value, precision)
        else:
            combined_value = round(combined_value, 3)

        metadata = {
            "unit_of_measurement": output_unit,
            "device_class": (record_a.get("device_class") if record_a else None)
            or (record_b.get("device_class") if record_b else None),
            "state_class": (record_a.get("state_class") if record_a else None)
            or (record_b.get("state_class") if record_b else None),
            "precision": precision,
            "source_a_unit": unit_a,
            "source_b_unit": unit_b,
            "source_a_unique_id": record_a.get("unique_id") if record_a else None,
            "source_b_unique_id": record_b.get("unique_id") if record_b else None,
            "aggregation": aggregation,
        }
        return combined_value, metadata

    def _resolve_role_source_data(
        self,
        source_a_id: str | None,
        source_b_id: str | None,
        source_a_data: dict[str, Any],
        source_b_data: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Map inverter/ihm roles to coordinator payloads (order-independent)."""
        role_data: dict[str, dict[str, Any]] = {}
        for entry_id, source_data in (
            (source_a_id, source_a_data),
            (source_b_id, source_b_data),
        ):
            if not entry_id:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            type_set = entry_device_type_set(entry)
            if "inverter" in type_set:
                role_data[SOURCE_ROLE_INVERTER] = source_data
            if "energy_manager" in type_set:
                role_data[SOURCE_ROLE_IHM] = source_data
        return role_data

    def _entry_id_for_role(
        self,
        source_a_id: str | None,
        source_b_id: str | None,
        role: str,
    ) -> str | None:
        """Return config entry id for a resolved role (inverter or ihm)."""
        for entry_id in (source_a_id, source_b_id):
            if not entry_id:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            if role in entry_device_type_set(entry):
                return entry_id
        return None

    def _single_metric(
        self,
        role_data: dict[str, dict[str, Any]],
        role: str,
        metric_candidates: list[str],
        target_unit: str | None = None,
    ) -> tuple[float | None, dict[str, Any] | None]:
        """Read one metric from a single resolved role."""
        source_data = role_data.get(role)
        if not isinstance(source_data, dict):
            return None, None

        record = self._extract_metric_record(source_data, metric_candidates)
        if not record:
            return None, None

        value = float(record["value"])
        unit = record.get("unit_of_measurement")
        if target_unit and unit and unit != target_unit:
            converted = self._convert_unit(value, unit, target_unit)
            if converted is None:
                return None, None
            value = converted
            unit = target_unit

        precision = record.get("precision")
        if isinstance(precision, int):
            value = round(value, precision)
        else:
            value = round(value, 3)

        metadata = {
            "unit_of_measurement": unit or target_unit,
            "device_class": record.get("device_class"),
            "state_class": record.get("state_class"),
            "precision": precision,
            "source_role": role,
            "source_unique_id": record.get("unique_id"),
            "aggregation": "single",
        }
        return value, metadata

    def _operand_record(
        self,
        role_data: dict[str, dict[str, Any]],
        operand_spec: dict[str, Any],
        target_unit: str | None,
        daily_meter_values: dict[str, float | None] | None = None,
    ) -> dict[str, Any] | None:
        """Resolve one formula operand from a role-specific source payload."""
        role = str(operand_spec.get("source", "")).strip().lower()
        candidates = operand_spec.get("candidates", [])
        if not role or not isinstance(candidates, list):
            return None

        if operand_spec.get("use_daily_meter"):
            meter_key = str(operand_spec.get("daily_meter_key", "")).strip().lower()
            if not meter_key or not daily_meter_values:
                return None
            daily_value = daily_meter_values.get(meter_key)
            if daily_value is None:
                return None
            source_data = role_data.get(role)
            record = None
            if isinstance(source_data, dict):
                record = self._extract_metric_record(
                    source_data, [str(candidate) for candidate in candidates]
                )
            return {
                "value": float(daily_value),
                "role": role,
                "unique_id": (f"{record.get('unique_id')}_daily" if record else None),
                "unit": target_unit or "kWh",
                "daily_meter": meter_key,
            }

        record = None
        source_data = role_data.get(role)
        if isinstance(source_data, dict):
            record = self._extract_metric_record(
                source_data, [str(candidate) for candidate in candidates]
            )

        fallback = operand_spec.get("fallback")
        if record is None and isinstance(fallback, dict):
            fallback_role = str(fallback.get("source", "")).strip().lower()
            fallback_candidates = fallback.get("candidates", [])
            fallback_data = role_data.get(fallback_role)
            if isinstance(fallback_data, dict) and isinstance(
                fallback_candidates, list
            ):
                record = self._extract_metric_record(
                    fallback_data,
                    [str(candidate) for candidate in fallback_candidates],
                )
                if record:
                    role = fallback_role

        if not record:
            return None

        value = float(record["value"])
        unit = record.get("unit_of_measurement")
        if target_unit and unit and unit != target_unit:
            converted = self._convert_unit(value, unit, target_unit)
            if converted is None:
                return None
            value = converted

        return {
            "value": value,
            "role": role,
            "unique_id": record.get("unique_id"),
            "unit": unit,
        }

    @staticmethod
    def _evaluate_consumed_formula(operand_values: dict[str, float]) -> float | None:
        """Evaluate consumed-energy balance used in SH/SG + iHM specs."""
        required = {
            "pv",
            "export",
            "import",
            "battery_charge",
            "battery_discharge",
        }
        if not required.issubset(operand_values):
            return None
        return (
            operand_values["pv"]
            - operand_values["export"]
            + operand_values["import"]
            - operand_values["battery_charge"]
            + operand_values["battery_discharge"]
        )

    def _formula_metric(
        self,
        role_data: dict[str, dict[str, Any]],
        metric_spec: dict[str, Any],
        daily_meter_values: dict[str, float | None] | None = None,
    ) -> tuple[float | None, dict[str, Any] | None]:
        """Compute one formula metric from role-resolved operands."""
        formula = str(metric_spec.get("formula", "")).strip()
        operands = metric_spec.get("operands", {})
        if formula != _CONSUMED_FORMULA or not isinstance(operands, dict):
            return None, None

        target_unit = metric_spec.get("unit_of_measurement")
        operand_values: dict[str, float] = {}
        operand_meta: dict[str, Any] = {}
        for operand_name, operand_spec in operands.items():
            if not isinstance(operand_spec, dict):
                return None, None
            record = self._operand_record(
                role_data,
                operand_spec,
                str(target_unit) if target_unit else None,
                daily_meter_values=daily_meter_values,
            )
            if not record:
                return None, None
            operand_values[str(operand_name)] = float(record["value"])
            operand_meta[str(operand_name)] = {
                "role": record.get("role"),
                "unique_id": record.get("unique_id"),
                "unit": record.get("unit"),
                "daily_meter": record.get("daily_meter"),
            }

        combined_value = self._evaluate_consumed_formula(operand_values)
        if combined_value is None:
            return None, None

        precision = metric_spec.get("precision")
        if isinstance(precision, int):
            combined_value = round(combined_value, precision)
        else:
            combined_value = round(combined_value, 3)

        metadata = {
            "unit_of_measurement": target_unit,
            "device_class": metric_spec.get("device_class"),
            "state_class": metric_spec.get("state_class"),
            "precision": precision,
            "aggregation": "formula",
            "formula": formula,
            "operands": operand_meta,
            "notes": metric_spec.get("notes"),
        }
        return combined_value, metadata

    @staticmethod
    def _extract_boolean_value(
        source_data: dict[str, Any], metric_candidates: list[str]
    ) -> bool | None:
        """Extract first matching boolean-like value from one source payload."""
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

            value = register_data.get("processed_value")
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"on", "true", "1", "yes"}:
                    return True
                if normalized in {"off", "false", "0", "no"}:
                    return False
        return None

    @staticmethod
    def _parse_boolean_state(state: str | None) -> bool | None:
        """Parse HA state string into a boolean."""
        if state is None:
            return None
        normalized = str(state).strip().lower()
        if normalized in {"on", "true", "1", "yes"}:
            return True
        if normalized in {"off", "false", "0", "no"}:
            return False
        return None

    def _extract_boolean_from_entity_registry(
        self,
        source_entry_id: str,
        metric_candidates: list[str],
    ) -> bool | None:
        """Read template/calculated binary sensors from the HA entity registry."""
        registry = er.async_get(self.hass)
        for entity_entry in registry.entities.values():
            if entity_entry.config_entry_id != source_entry_id:
                continue
            unique_id = str(entity_entry.unique_id or "").strip().lower()
            if not unique_id:
                continue
            if not any(
                unique_id.endswith(f"_{candidate}") for candidate in metric_candidates
            ):
                continue
            state = self.hass.states.get(entity_entry.entity_id)
            if state is None:
                continue
            parsed = self._parse_boolean_state(state.state)
            if parsed is not None:
                return parsed
        return None

    def _extract_boolean_for_source(
        self,
        source_data: dict[str, Any],
        source_entry_id: str | None,
        metric_candidates: list[str],
    ) -> bool | None:
        """Read boolean metric from Modbus cache or HA entity state."""
        value = self._extract_boolean_value(source_data, metric_candidates)
        if value is not None:
            return value
        if not source_entry_id:
            return None
        return self._extract_boolean_from_entity_registry(
            source_entry_id, metric_candidates
        )

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
        binary_metrics: dict[str, Any] = {}

        combination_type = combination_type_for_entry(self.hass, self.entry)
        metric_specs = COMBINED_SENSOR_METRIC_SPECS.get(combination_type, {})
        binary_specs = COMBINED_BINARY_METRIC_SPECS.get(combination_type, {})
        source_a_data = (
            source_a.get("data", {}) if isinstance(source_a.get("data"), dict) else {}
        )
        source_b_data = (
            source_b.get("data", {}) if isinstance(source_b.get("data"), dict) else {}
        )
        role_data = self._resolve_role_source_data(
            source_a_id, source_b_id, source_a_data, source_b_data
        )

        daily_meter_values: dict[str, float | None] = {}
        if combination_type == "inverter_ihm":
            if not self._daily_meters_loaded:
                await self.async_load_daily_meters()
            if self._daily_meters is not None:
                daily_meter_values = self._update_ihm_daily_meters(role_data)

        if metric_specs:
            for metric_key, metric_spec in metric_specs.items():
                aggregation = str(metric_spec.get("aggregation", "sum"))
                candidates = metric_spec.get("source_candidates", [])

                combined_value: float | None = None
                combined_meta: dict[str, Any] | None = None

                if aggregation == "daily_meter":
                    meter_key = str(metric_spec.get("meter_key", "")).strip().lower()
                    if not meter_key or self._daily_meters is None:
                        continue
                    daily_value = daily_meter_values.get(meter_key)
                    if daily_value is None:
                        continue
                    precision = metric_spec.get("precision")
                    combined_value = float(daily_value)
                    if isinstance(precision, int):
                        combined_value = round(combined_value, precision)
                    combined_meta = self._daily_meters.metadata(meter_key)
                    combined_meta["unit_of_measurement"] = metric_spec.get(
                        "unit_of_measurement", "kWh"
                    )
                    combined_meta["device_class"] = metric_spec.get("device_class")
                    combined_meta["state_class"] = metric_spec.get("state_class")
                    combined_meta["precision"] = precision
                elif aggregation == "formula":
                    combined_value, combined_meta = self._formula_metric(
                        role_data,
                        metric_spec,
                        daily_meter_values=daily_meter_values,
                    )
                elif aggregation == "single":
                    source_role = str(metric_spec.get("source", "")).strip().lower()
                    if not source_role or not isinstance(candidates, list):
                        continue
                    combined_value, combined_meta = self._single_metric(
                        role_data,
                        source_role,
                        [str(candidate) for candidate in candidates],
                        metric_spec.get("unit_of_measurement"),
                    )
                elif aggregation in {"sum", "avg", "max", "min"} and isinstance(
                    candidates, list
                ):
                    source_role = metric_spec.get("source")
                    if source_role:
                        combined_value, combined_meta = self._single_metric(
                            role_data,
                            str(source_role),
                            [str(candidate) for candidate in candidates],
                            metric_spec.get("unit_of_measurement"),
                        )
                    else:
                        required_sources = str(
                            metric_spec.get("required_sources", "both")
                        )
                        combined_value, combined_meta = self._combine_metric(
                            source_a_data=source_a_data,
                            source_b_data=source_b_data,
                            metric_candidates=[
                                str(candidate) for candidate in candidates
                            ],
                            aggregation=aggregation,
                            required_sources=required_sources,
                        )
                else:
                    continue

                if combined_value is None:
                    continue

                metrics[metric_key] = combined_value
                if combined_meta:
                    metric_meta[metric_key] = combined_meta

        if binary_specs:
            for metric_key, metric_spec in binary_specs.items():
                candidates = metric_spec.get("source_candidates", [])
                operation = str(metric_spec.get("operation", "any"))
                required_sources = str(metric_spec.get("required_sources", "any"))
                if not isinstance(candidates, list) or operation not in {"any", "all"}:
                    continue

                candidate_list = [str(candidate) for candidate in candidates]
                source_role = metric_spec.get("source")
                if source_role == SOURCE_ROLE_INVERTER:
                    inverter_entry_id = self._entry_id_for_role(
                        source_a_id, source_b_id, SOURCE_ROLE_INVERTER
                    )
                    inverter_data = role_data.get(SOURCE_ROLE_INVERTER, {})
                    source_a_value = self._extract_boolean_for_source(
                        inverter_data if isinstance(inverter_data, dict) else {},
                        inverter_entry_id,
                        candidate_list,
                    )
                    source_b_value = None
                elif source_role == SOURCE_ROLE_IHM:
                    source_a_value = None
                    source_b_value = None
                else:
                    source_a_value = self._extract_boolean_for_source(
                        source_a_data, source_a_id, candidate_list
                    )
                    source_b_value = self._extract_boolean_for_source(
                        source_b_data, source_b_id, candidate_list
                    )
                values = [
                    value
                    for value in [source_a_value, source_b_value]
                    if value is not None
                ]

                if required_sources == "both" and (
                    source_a_value is None or source_b_value is None
                ):
                    continue
                if not values:
                    continue

                if operation == "all":
                    binary_metrics[metric_key] = all(values)
                else:
                    binary_metrics[metric_key] = any(values)

        return {
            "combined_prefix": self.entry.data.get("combined_prefix"),
            "combination_type": combination_type,
            "metrics": metrics,
            "metric_meta": metric_meta,
            "binary_metrics": binary_metrics,
            "sources": {
                "a": source_a,
                "b": source_b,
            },
            "available": bool(source_a.get("available") or source_b.get("available")),
        }
