"""Entities for cross-hub combined devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .combined_coordinator import CombinedDeviceCoordinator
from .const import DOMAIN
from .device_utils import generate_unique_id


def _combined_prefix(entry: ConfigEntry) -> str:
    """Return configured combined prefix (legacy-compatible casing)."""
    return str(entry.data.get("combined_prefix", "")).strip() or entry.entry_id


def _combined_unique_id(entry: ConfigEntry, metric_key: str) -> str:
    """Build registry unique_id like hub devices: ``{prefix}_{metric_key}``."""
    return generate_unique_id(_combined_prefix(entry), metric_key)


def _combined_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Build shared device info for combined entities."""
    combined_prefix = entry.data.get("combined_prefix", entry.entry_id)
    source_a = entry.data.get("source_entry_id_a", "unknown")
    source_b = entry.data.get("source_entry_id_b", "unknown")
    return DeviceInfo(
        identifiers={(DOMAIN, f"combined_{entry.entry_id}")},
        name=f"Combined {combined_prefix}",
        manufacturer="Modbus Manager",
        model="Cross-hub Combined Device",
        sw_version="1.0.20",
        configuration_url=None,
        serial_number=f"{source_a[:8]}-{source_b[:8]}",
    )


class CombinedAvailabilityBinarySensor(
    CoordinatorEntity[CombinedDeviceCoordinator], BinarySensorEntity
):
    """Binary sensor showing one combined availability flag."""

    def __init__(
        self,
        coordinator: CombinedDeviceCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_translation_key = key
        self._attr_unique_id = _combined_unique_id(entry, key)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = _combined_device_info(entry)

    @property
    def is_on(self) -> bool | None:
        """Return binary state from coordinator payload."""
        data = self.coordinator.data or {}
        sources = data.get("sources", {})
        source_a = bool(sources.get("a", {}).get("available"))
        source_b = bool(sources.get("b", {}).get("available"))
        if self._key == "combined_source_a_available":
            return source_a
        if self._key == "combined_source_b_available":
            return source_b
        if self._key == "combined_any_source_available":
            return source_a or source_b
        return None

    @property
    def available(self) -> bool:
        """Combined availability entities stay available while coordinator runs."""
        return super().available


class CombinedComputedBinarySensor(
    CoordinatorEntity[CombinedDeviceCoordinator], BinarySensorEntity
):
    """Binary sensor computed by combined coordinator binary metrics."""

    def __init__(
        self,
        coordinator: CombinedDeviceCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_translation_key = key
        self._attr_unique_id = _combined_unique_id(entry, key)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = _combined_device_info(entry)

    @property
    def is_on(self) -> bool | None:
        """Return computed binary metric state."""
        data = self.coordinator.data or {}
        metrics = data.get("binary_metrics", {})
        value = metrics.get(self._key)
        if value is None:
            return None
        return bool(value)


class CombinedPairTypeSensor(
    CoordinatorEntity[CombinedDeviceCoordinator], SensorEntity
):
    """Sensor exposing selected combination type."""

    def __init__(
        self,
        coordinator: CombinedDeviceCoordinator,
        entry: ConfigEntry,
        name: str = "Combination Type",
    ) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_translation_key = "combined_pair_type"
        self._attr_unique_id = _combined_unique_id(entry, "combined_pair_type")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = _combined_device_info(entry)

    @property
    def native_value(self) -> str | None:
        """Return configured combination type."""
        data = self.coordinator.data or {}
        combination_type = data.get("combination_type")
        if combination_type is None:
            combination_type = self.coordinator.entry.data.get("combination_type")
        return str(combination_type) if combination_type else None


class CombinedSumSensor(CoordinatorEntity[CombinedDeviceCoordinator], SensorEntity):
    """Numeric sensor for combined power sums."""

    def __init__(
        self,
        coordinator: CombinedDeviceCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unit: str = "W",
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_translation_key = key
        self._attr_unique_id = _combined_unique_id(entry, key)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = _combined_device_info(entry)
        self._attr_native_unit_of_measurement = unit

    def _metric_meta(self) -> dict[str, Any]:
        """Return metadata extracted from source template registers."""
        data = self.coordinator.data or {}
        metric_meta = data.get("metric_meta", {})
        if not isinstance(metric_meta, dict):
            return {}
        meta = metric_meta.get(self._key, {})
        return meta if isinstance(meta, dict) else {}

    @property
    def native_value(self) -> float | None:
        """Return summed metric value."""
        data = self.coordinator.data or {}
        metrics = data.get("metrics", {})
        value = metrics.get(self._key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Use unit from source template metadata when available."""
        return (
            self._metric_meta().get("unit_of_measurement")
            or self._attr_native_unit_of_measurement
        )

    @property
    def device_class(self) -> str | None:
        """Use device class from source template metadata."""
        return self._metric_meta().get("device_class")

    @property
    def state_class(self) -> str | None:
        """Use state class from source template metadata."""
        return self._metric_meta().get("state_class")

    @property
    def suggested_display_precision(self) -> int | None:
        """Use precision from source template metadata."""
        precision = self._metric_meta().get("precision")
        return precision if isinstance(precision, int) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose metric source metadata for transparency/debugging."""
        meta = self._metric_meta()
        if not meta:
            return None
        attributes: dict[str, Any] = {}
        if meta.get("aggregation") == "formula":
            attributes["formula"] = meta.get("formula")
            attributes["operands"] = meta.get("operands")
            if meta.get("notes"):
                attributes["notes"] = meta.get("notes")
        elif meta.get("aggregation") == "daily_meter":
            attributes["source_unique_id"] = meta.get("source_unique_id")
            attributes["meter_day"] = meta.get("meter_day")
        elif meta.get("aggregation") == "single":
            attributes["source_role"] = meta.get("source_role")
            attributes["source_unique_id"] = meta.get("source_unique_id")
        else:
            attributes["source_a_unique_id"] = meta.get("source_a_unique_id")
            attributes["source_b_unique_id"] = meta.get("source_b_unique_id")
            attributes["source_a_unit"] = meta.get("source_a_unit")
            attributes["source_b_unit"] = meta.get("source_b_unit")
        return attributes or None
