"""Group switch and status sensor for keepalive groups (see keepalive.py)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .keepalive import GroupState, KeepaliveManager


def _device_info(group: GroupState) -> DeviceInfo | None:
    if not group.device_info:
        return None
    return DeviceInfo(**group.device_info)


def add_keepalive_entities(
    coordinator: Any, async_add_entities: AddEntitiesCallback, platform: str
) -> int:
    """Create one switch or status sensor per keepalive group of the hub."""
    manager: KeepaliveManager | None = getattr(coordinator, "keepalive", None)
    if manager is None or not manager.groups:
        return 0
    by_subentry: dict[str | None, list] = {}
    for group in manager.groups.values():
        entity: Any
        if platform == "switch":
            entity = KeepaliveGroupSwitch(manager, group)
        else:
            entity = KeepaliveGroupStatusSensor(manager, group)
        by_subentry.setdefault(group.config_subentry_id, []).append(entity)
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
        # Starts a tracked round task; state updates arrive through the listener.
        self._manager.async_activate(self._group_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._manager.async_deactivate(self._group_id)
        self.async_write_ha_state()


class KeepaliveGroupStatusSensor(_KeepaliveGroupEntity, SensorEntity):
    """Shows whether a group is off, active or stopped, plus counters."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:repeat-variant"

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
