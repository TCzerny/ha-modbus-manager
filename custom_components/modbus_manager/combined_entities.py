"""Entities for cross-hub combined devices."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .combined_coordinator import CombinedDeviceCoordinator
from .const import DOMAIN


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
        sw_version="step1",
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
        combined_prefix = str(entry.data.get("combined_prefix", "combined")).lower()
        self._key = key
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = _combined_device_info(entry)
        self.entity_id = f"binary_sensor.{combined_prefix}_{key}"

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


class CombinedPairTypeSensor(
    CoordinatorEntity[CombinedDeviceCoordinator], SensorEntity
):
    """Sensor exposing selected combination type."""

    def __init__(
        self, coordinator: CombinedDeviceCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        combined_prefix = str(entry.data.get("combined_prefix", "combined")).lower()
        self._attr_has_entity_name = True
        self._attr_name = "Combination Type"
        self._attr_unique_id = f"{entry.entry_id}_combined_pair_type"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = _combined_device_info(entry)
        self.entity_id = f"sensor.{combined_prefix}_combined_pair_type"

    @property
    def native_value(self) -> str | None:
        """Return configured combination type."""
        data = self.coordinator.data or {}
        combination_type = data.get("combination_type")
        if combination_type is None:
            combination_type = self.coordinator.entry.data.get("combination_type")
        return str(combination_type) if combination_type else None
