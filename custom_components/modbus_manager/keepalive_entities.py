"""Group switch, status sensor and floor numbers for keepalive groups (see keepalive.py)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .keepalive import FloorSetting, GroupState, KeepaliveManager


def _device_info(group: GroupState) -> DeviceInfo | None:
    if not group.device_info:
        return None
    return DeviceInfo(**group.device_info)


def add_keepalive_entities(
    coordinator: Any, async_add_entities: AddEntitiesCallback, platform: str
) -> int:
    """Create the keepalive entities of one platform for all groups of the hub.

    switch: one group switch per group; sensor: one status sensor per group;
    number: one floor number per control with ``clamp_floor``.
    """
    manager: KeepaliveManager | None = getattr(coordinator, "keepalive", None)
    if manager is None or not manager.groups:
        return 0
    by_subentry: dict[str | None, list] = {}
    for group in manager.groups.values():
        entities: list[Any]
        if platform == "switch":
            entities = [KeepaliveGroupSwitch(manager, group)]
        elif platform == "number":
            entities = [
                KeepaliveFloorNumber(manager, group, floor)
                for floor in group.floors.values()
            ]
        else:
            entities = [KeepaliveGroupStatusSensor(manager, group)]
        if entities:
            by_subentry.setdefault(group.config_subentry_id, []).extend(entities)
    count = 0
    for subentry_id, entities in by_subentry.items():
        count += len(entities)
        if subentry_id:
            async_add_entities(entities, config_subentry_id=subentry_id)
        else:
            async_add_entities(entities)
    return count


class _KeepaliveGroupEntity:
    """Shared listener handling."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: KeepaliveManager, group: GroupState) -> None:
        self._manager = manager
        self._group_id = group.group_id
        self._attr_device_info = _device_info(group)
        self._remove_listener = None

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self._manager.add_listener(
            self._group_id, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None


class KeepaliveGroupSwitch(_KeepaliveGroupEntity, SwitchEntity):
    """Turns cyclic writes of a group on or off. Always starts off."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:repeat"

    def __init__(self, manager: KeepaliveManager, group: GroupState) -> None:
        super().__init__(manager, group)
        self._attr_unique_id = group.group_id
        self._attr_name = group.name

    @property
    def is_on(self) -> bool:
        return self._manager.is_active(self._group_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._group_id not in self._manager.groups:
            raise HomeAssistantError(
                "Keepalive group no longer exists; reload the entry"
            )
        if not self._manager.is_active(self._group_id) and not self._manager.link_ok():
            raise HomeAssistantError(
                "Keepalive not started: Modbus link down or last poll failed"
            )
        # Starts a tracked round task; state updates arrive through the listener.
        self._manager.async_activate(self._group_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._manager.async_deactivate(self._group_id)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        # Without its switch a group could not be turned off any more.
        self._manager.stop_group(self._group_id, "group switch removed")
        await super().async_will_remove_from_hass()


class KeepaliveGroupStatusSensor(_KeepaliveGroupEntity, SensorEntity):
    """Shows whether a group is off, active or stopped, plus counters."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:repeat-variant"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["off", "active", "stopped"]
    # Counters and timestamps change every round; keep them out of the recorder.
    _unrecorded_attributes = frozenset(
        {
            "writes",
            "failed_writes",
            "mismatches",
            "consecutive_failures",
            "last_write",
            "setpoints",
        }
    )

    def __init__(self, manager: KeepaliveManager, group: GroupState) -> None:
        super().__init__(manager, group)
        self._attr_unique_id = f"{group.group_id}_status"
        self._attr_name = f"{group.name} status"

    @property
    def native_value(self) -> str | None:
        status = self._manager.status(self._group_id)
        return status.get("state")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = dict(self._manager.status(self._group_id))
        last_write = status.get("last_write")
        if last_write:
            status["last_write"] = datetime.fromtimestamp(
                last_write, tz=timezone.utc
            ).isoformat()
        status.pop("state", None)
        return status


class KeepaliveFloorNumber(_KeepaliveGroupEntity, RestoreNumber):
    """Lower bound for a clamped control (0 = off); restored after a restart.

    The control's max clamp (for example the SoC) does not pull the written
    value below this floor; the floor never lifts it above the setpoint.
    Changing it writes nothing; it applies from the next write.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:arrow-collapse-down"
    _attr_mode = NumberMode.BOX

    def __init__(
        self, manager: KeepaliveManager, group: GroupState, floor: FloorSetting
    ) -> None:
        super().__init__(manager, group)
        self._floor_id = floor.floor_id
        self._attr_unique_id = floor.floor_id
        self._attr_name = floor.name
        self._attr_native_min_value = floor.min
        self._attr_native_max_value = floor.max
        self._attr_native_step = floor.step
        self._attr_native_unit_of_measurement = floor.unit
        self._attr_entity_registry_enabled_default = floor.enabled_default

    @property
    def native_value(self) -> float | None:
        return self._manager.floor_value(self._floor_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._manager.set_floor(self._floor_id, last.native_value)

    async def async_set_native_value(self, value: float) -> None:
        if not math.isfinite(value):
            raise HomeAssistantError(f"Invalid floor value: {value}")
        if self._manager.set_floor(self._floor_id, value) is None:
            raise HomeAssistantError("Floor no longer exists; reload the entry")
        self.async_write_ha_state()
