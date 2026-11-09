"""Cyclic writes (keepalive) for controls whose device drops values after a timeout.

Some devices only follow a written value while they keep receiving writes, for
example external battery management registers that fall back to internal
control after a device-side timeout. A template opts in per control with a
``keepalive`` block that names a group from the template's
``keepalive_groups``.

Rules (see discussion in issue #145):

* Templates without ``keepalive`` stay write-once.
* A setpoint is stored only when the user sets the control. It is repeated only
  while the group's switch is on. Nothing is restored after a restart and the
  switch starts off.
* Cyclic writes use the coordinator write path (same encoding, same I/O lock)
  without the read-back verify of the number entity. Read-back mismatches are
  logged and counted; repeated failures stop the group.
* A stale or unavailable clamp source stops the group instead of writing a
  guessed value.
* Unload or a dropped link stops the writes. No final write is sent.
* Turning the switch off stops the writes; only controls with
  ``release: write`` get one release write.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Dict, Optional

from .logger import ModbusManagerLogger

try:  # pragma: no cover - exercised with Home Assistant installed
    from homeassistant.core import callback as _ha_callback
except ImportError:  # unit tests without Home Assistant

    def _ha_callback(func):
        func._hass_callback = True
        return func


_LOGGER = ModbusManagerLogger(__name__)

KEEPALIVE_KEY = "keepalive"
KEEPALIVE_GROUPS_KEY = "keepalive_groups"

MIN_INTERVAL_S = 5.0
DEFAULT_MIN_WRITE_SPACING_MS = 1000
DEFAULT_MAX_FAILURES = 3
DEFAULT_CLAMP_MAX_AGE_S = 60.0
KEEPALIVE_CONTROL_TYPES = frozenset({"number", "select", "switch"})
RELEASE_MODES = frozenset({"stop", "write"})
TICK_SECONDS = 1.0

STATE_OFF = "off"
STATE_ACTIVE = "active"
STATE_STOPPED = "stopped"


# ---------------------------------------------------------------------------
# Template validation
# ---------------------------------------------------------------------------


def _as_float(value: Any) -> Optional[float]:
    """Return a finite float, or None (bools, NaN and infinity are rejected)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value)
        except ValueError:
            return None
    else:
        return None
    return result if math.isfinite(result) else None


def validate_keepalive_groups(raw: Any, template_name: str) -> Dict[str, Dict[str, Any]]:
    """Return the valid ``keepalive_groups`` of a template; log and drop invalid ones."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        _LOGGER.error(
            "Template %s: keepalive_groups must be a mapping, ignoring it", template_name
        )
        return {}

    groups: Dict[str, Dict[str, Any]] = {}
    for group_key, cfg in raw.items():
        key = str(group_key).strip()
        if not key or not isinstance(cfg, dict):
            _LOGGER.error(
                "Template %s: keepalive group %r must be a mapping, ignoring it",
                template_name,
                group_key,
            )
            continue

        interval = _as_float(cfg.get("interval"))
        if interval is None or interval < MIN_INTERVAL_S:
            _LOGGER.error(
                "Template %s: keepalive group %s needs interval >= %s s, ignoring it",
                template_name,
                key,
                MIN_INTERVAL_S,
            )
            continue

        spacing = _as_float(cfg.get("min_write_spacing_ms", DEFAULT_MIN_WRITE_SPACING_MS))
        if spacing is None or spacing < 0:
            _LOGGER.error(
                "Template %s: keepalive group %s has an invalid min_write_spacing_ms, ignoring it",
                template_name,
                key,
            )
            continue

        max_failures = cfg.get("max_failures", DEFAULT_MAX_FAILURES)
        if isinstance(max_failures, bool) or not isinstance(max_failures, int) or max_failures < 1:
            _LOGGER.error(
                "Template %s: keepalive group %s needs max_failures >= 1, ignoring it",
                template_name,
                key,
            )
            continue

        if cfg.get("resume_after_restart"):
            _LOGGER.error(
                "Template %s: keepalive group %s sets resume_after_restart, which is not supported; "
                "the group always starts off",
                template_name,
                key,
            )

        groups[key] = {
            "name": str(cfg.get("name") or key),
            "interval": interval,
            "min_write_spacing_ms": spacing,
            "max_failures": max_failures,
        }
    return groups


def validate_control_keepalive(
    control: Dict[str, Any], groups: Dict[str, Dict[str, Any]], template_name: str
) -> Optional[Dict[str, Any]]:
    """Return a cleaned ``keepalive`` block for a control, or None if invalid."""
    raw = control.get(KEEPALIVE_KEY)
    label = control.get("unique_id") or control.get("name") or "unknown"
    if not isinstance(raw, dict):
        _LOGGER.error(
            "Template %s: keepalive on control %s must be a mapping; control stays write-once",
            template_name,
            label,
        )
        return None

    control_type = control.get("type")
    if control_type not in KEEPALIVE_CONTROL_TYPES:
        _LOGGER.error(
            "Template %s: keepalive is not supported on %s control %s; control stays write-once",
            template_name,
            control_type,
            label,
        )
        return None

    if str(control.get("input_type", "holding")).lower() != "holding":
        _LOGGER.error(
            "Template %s: keepalive control %s must be a holding register; control stays write-once",
            template_name,
            label,
        )
        return None

    group = str(raw.get("group") or "").strip()
    if group not in groups:
        _LOGGER.error(
            "Template %s: keepalive control %s refers to unknown group %r; control stays write-once",
            template_name,
            label,
            group,
        )
        return None

    release = str(raw.get("release", "stop")).lower()
    if release not in RELEASE_MODES:
        _LOGGER.error(
            "Template %s: keepalive control %s has invalid release %r; control stays write-once",
            template_name,
            label,
            raw.get("release"),
        )
        return None

    cleaned: Dict[str, Any] = {"group": group, "release": release}

    if release == "write":
        release_value = _as_float(raw.get("release_value"))
        if release_value is None:
            _LOGGER.error(
                "Template %s: keepalive control %s uses release: write without a numeric "
                "release_value; control stays write-once",
                template_name,
                label,
            )
            return None
        cleaned["release_value"] = release_value

    for clamp_key in ("clamp_max_to_register", "clamp_min_to_register"):
        source = raw.get(clamp_key)
        if source is None:
            continue
        if control_type != "number" or not isinstance(source, str) or not source.strip():
            _LOGGER.error(
                "Template %s: %s on control %s needs a number control and a unique_id string; "
                "control stays write-once",
                template_name,
                clamp_key,
                label,
            )
            return None
        cleaned[clamp_key] = source.strip()

    if "clamp_max_age" in raw:
        max_age = _as_float(raw.get("clamp_max_age"))
        if max_age is None or max_age <= 0:
            _LOGGER.error(
                "Template %s: keepalive control %s has an invalid clamp_max_age; control stays write-once",
                template_name,
                label,
            )
            return None
        cleaned["clamp_max_age"] = max_age

    if "mismatch_tolerance" in raw:
        tolerance = _as_float(raw.get("mismatch_tolerance"))
        if tolerance is None or tolerance < 0:
            _LOGGER.error(
                "Template %s: keepalive control %s has an invalid mismatch_tolerance; control stays write-once",
                template_name,
                label,
            )
            return None
        cleaned["mismatch_tolerance"] = tolerance

    return cleaned


def validate_template_keepalive(
    raw_groups: Any, controls: list, template_name: str
) -> Dict[str, Dict[str, Any]]:
    """Validate groups and the keepalive blocks of ``controls`` in place.

    Invalid control blocks are removed, so the control stays write-once.
    Returns the valid groups.
    """
    groups = validate_keepalive_groups(raw_groups, template_name)
    for control in controls or []:
        if not isinstance(control, dict) or KEEPALIVE_KEY not in control:
            continue
        cleaned = validate_control_keepalive(control, groups, template_name)
        if cleaned is None:
            control.pop(KEEPALIVE_KEY, None)
        else:
            control[KEEPALIVE_KEY] = cleaned
    return groups


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


@dataclass
class Setpoint:
    """A value the user set on a keepalive control."""

    register_key: str
    config: Dict[str, Any]
    value: float
    kind: str  # "number" (display value) or "raw" (select/switch register value)
    last_write_loop_time: Optional[float] = None
    last_written_value: Optional[float] = None
    mismatch_streak: int = 0


@dataclass
class GroupState:
    """Runtime state of one keepalive group."""

    group_id: str
    name: str
    interval: float
    min_write_spacing_ms: float
    max_failures: int
    prefix: str = ""
    device_info: Optional[Dict[str, Any]] = None
    config_subentry_id: Optional[str] = None
    state: str = STATE_OFF
    stop_reason: Optional[str] = None
    setpoints: Dict[str, Setpoint] = field(default_factory=dict)
    consecutive_failures: int = 0
    writes: int = 0
    failed_writes: int = 0
    mismatches: int = 0
    last_write: Optional[float] = None  # wall clock (time.time())
    last_round: Optional[float] = None  # loop time
    # Incremented on every activate/stop; work started under an older
    # generation must not send anything.
    generation: int = 0
    task: Optional[asyncio.Task] = None


class KeepaliveManager:
    """Repeats user-set values of keepalive controls per hub coordinator."""

    def __init__(
        self,
        coordinator: Any,
        *,
        loop_time: Optional[Callable[[], float]] = None,
        wall_time: Optional[Callable[[], float]] = None,
        sleep: Optional[Callable[[float], Any]] = None,
    ) -> None:
        self._coordinator = coordinator
        self._loop_time = loop_time or (lambda: asyncio.get_running_loop().time())
        self._wall_time = wall_time or time.time
        self._sleep = sleep or asyncio.sleep
        self._groups: Dict[str, GroupState] = {}
        self._listeners: Dict[str, list] = {}
        self._unsub_timer: Optional[Callable[[], None]] = None
        self._last_send: Optional[float] = None  # loop time of the last keepalive write
        # Serializes "wait for the gap -> send" across all groups of this hub.
        self._send_lock = asyncio.Lock()
        self._unsub_stop: Optional[Callable[[], None]] = None

    # -- registration -------------------------------------------------------

    @property
    def groups(self) -> Dict[str, GroupState]:
        return self._groups

    def register_groups(self, groups: Dict[str, Dict[str, Any]]) -> None:
        """Register the groups used by the hub's controls (idempotent)."""
        for group_id in list(self._groups):
            if group_id not in groups:
                self.stop_group(group_id, "removed")
                self._groups.pop(group_id, None)
        for group_id, info in groups.items():
            state = self._groups.get(group_id)
            if state is None:
                self._groups[group_id] = GroupState(
                    group_id=group_id,
                    name=info.get("name", group_id),
                    interval=float(info["interval"]),
                    min_write_spacing_ms=float(info["min_write_spacing_ms"]),
                    max_failures=int(info["max_failures"]),
                    prefix=info.get("prefix", ""),
                    device_info=info.get("device_info"),
                    config_subentry_id=info.get("config_subentry_id"),
                )
            else:
                state.name = info.get("name", group_id)
                state.interval = float(info["interval"])
                state.min_write_spacing_ms = float(info["min_write_spacing_ms"])
                state.max_failures = int(info["max_failures"])
                state.device_info = info.get("device_info", state.device_info)
                state.config_subentry_id = info.get(
                    "config_subentry_id", state.config_subentry_id
                )

    def add_listener(self, group_id: str, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.setdefault(group_id, []).append(callback)

        def _remove() -> None:
            listeners = self._listeners.get(group_id, [])
            if callback in listeners:
                listeners.remove(callback)

        return _remove

    def _notify(self, group_id: str) -> None:
        for callback in list(self._listeners.get(group_id, [])):
            try:
                callback()
            except Exception as err:  # pragma: no cover - defensive
                _LOGGER.debug("Keepalive listener for %s failed: %s", group_id, err)

    # -- state --------------------------------------------------------------

    def is_active(self, group_id: str) -> bool:
        state = self._groups.get(group_id)
        return bool(state and state.state == STATE_ACTIVE)

    def status(self, group_id: str) -> Dict[str, Any]:
        state = self._groups.get(group_id)
        if state is None:
            return {}
        return {
            "state": state.state,
            "stop_reason": state.stop_reason,
            "interval": state.interval,
            "writes": state.writes,
            "failed_writes": state.failed_writes,
            "mismatches": state.mismatches,
            "consecutive_failures": state.consecutive_failures,
            "last_write": state.last_write,
            "setpoints": {
                sp.config.get("unique_id", key): sp.value
                for key, sp in state.setpoints.items()
            },
        }

    def set_setpoint(
        self,
        group_id: str,
        register_key: str,
        config: Dict[str, Any],
        value: float,
        kind: str,
    ) -> None:
        """Store a value the user just wrote successfully.

        Replacing the object invalidates any in-flight write of the old value
        (the send guard checks object identity).
        """
        state = self._groups.get(group_id)
        if state is None:
            _LOGGER.warning(
                "Keepalive group %s is not registered; %s stays write-once",
                group_id,
                config.get("unique_id"),
            )
            return
        numeric = _as_float(value)
        if numeric is None:
            return
        state.setpoints[register_key] = Setpoint(
            register_key=register_key,
            config=config,
            value=numeric,
            kind=kind,
            last_write_loop_time=self._safe_loop_time(),
            last_written_value=numeric,
        )
        self._notify(group_id)

    def _safe_loop_time(self) -> Optional[float]:
        try:
            return self._loop_time()
        except RuntimeError:
            return None

    # -- activation ---------------------------------------------------------

    def async_activate(self, group_id: str) -> Optional[asyncio.Task]:
        """Turn a group on: start a tracked first round and then every interval.

        Idempotent while the group is active. Returns the round task, if any.
        """
        state = self._groups.get(group_id)
        if state is None or state.state == STATE_ACTIVE:
            return None
        if not self._link_ok():
            _LOGGER.warning(
                "Keepalive group %s not started: link down, last poll failed or unloading",
                group_id,
            )
            return None
        self._cancel_task(state)
        state.generation += 1
        state.state = STATE_ACTIVE
        state.stop_reason = None
        state.consecutive_failures = 0
        state.last_round = None
        for setpoint in state.setpoints.values():
            setpoint.mismatch_streak = 0
        self._ensure_timer()
        self._notify(group_id)
        return self._start_task(state, self.async_run_round(group_id, state.generation))

    def async_deactivate(self, group_id: str) -> Optional[asyncio.Task]:
        """Turn a group off: stop writes; release writes only for ``release: write``.

        Returns the tracked release task, if any.
        """
        state = self._groups.get(group_id)
        if state is None:
            return None
        if state.state != STATE_ACTIVE:
            # Already off or stopped: nothing to release. Keep values the user
            # set while the group was off.
            if state.state == STATE_STOPPED:
                state.state = STATE_OFF
                state.stop_reason = None
                self._notify(group_id)
            return None
        releases = [
            sp
            for sp in state.setpoints.values()
            if sp.config.get(KEEPALIVE_KEY, {}).get("release") == "write"
        ]
        self.stop_group(group_id, None, new_state=STATE_OFF)
        if not releases:
            return None
        return self._start_task(
            state, self._async_release(group_id, state.generation, releases)
        )

    def stop_group(
        self, group_id: str, reason: Optional[str], new_state: str = STATE_STOPPED
    ) -> None:
        """Stop a group without writing. Clears its setpoints."""
        state = self._groups.get(group_id)
        if state is None:
            return
        was_active = state.state == STATE_ACTIVE
        if was_active or new_state == STATE_OFF:
            state.state = new_state
        state.stop_reason = reason
        state.generation += 1  # invalidates queued writes of the old generation
        state.setpoints.clear()
        self._cancel_task(state)
        if was_active and reason:
            _LOGGER.warning("Keepalive group %s stopped: %s", group_id, reason)
        self._maybe_stop_timer()
        self._notify(group_id)

    def stop_all(self, reason: str) -> None:
        """Stop every group without writing (unload)."""
        for group_id, state in list(self._groups.items()):
            if state.state == STATE_ACTIVE:
                self.stop_group(group_id, reason)
            else:
                state.generation += 1
                self._cancel_task(state)
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_stop is not None:
            self._unsub_stop()
            self._unsub_stop = None

    # -- tasks and timer ----------------------------------------------------

    def _start_task(self, state: GroupState, coro: Any) -> asyncio.Task:
        hass = getattr(self._coordinator, "hass", None)
        if hass is not None:
            task = hass.async_create_background_task(
                coro, f"modbus_manager keepalive {state.group_id}"
            )
        else:
            task = asyncio.ensure_future(coro)
        state.task = task
        return task

    @staticmethod
    def _cancel_task(state: GroupState) -> None:
        task = state.task
        state.task = None
        if task is not None and not task.done() and task is not _current_task():
            task.cancel()

    def _ensure_timer(self) -> None:
        if self._unsub_timer is not None:
            return
        hass = getattr(self._coordinator, "hass", None)
        if hass is None:
            return
        from homeassistant.helpers.event import async_track_time_interval

        self._unsub_timer = async_track_time_interval(
            hass, self._handle_tick, timedelta(seconds=TICK_SECONDS)
        )
        if self._unsub_stop is None:
            from homeassistant.const import EVENT_HOMEASSISTANT_STOP

            self._unsub_stop = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._handle_hass_stop
            )

    @_ha_callback
    def _handle_hass_stop(self, _event: Any = None) -> None:
        # Home Assistant does not unload config entries on stop; stop writing here.
        self._unsub_stop = None  # a fired once-listener must not be removed again
        self.stop_all("Home Assistant stopping")

    def _maybe_stop_timer(self) -> None:
        if self._unsub_timer is None:
            return
        if any(s.state == STATE_ACTIVE for s in self._groups.values()):
            return
        self._unsub_timer()
        self._unsub_timer = None

    def due_groups(self) -> list:
        """Return active groups whose interval has elapsed and that are idle."""
        now = self._loop_time()
        due = []
        for group_id, state in self._groups.items():
            if state.state != STATE_ACTIVE:
                continue
            if state.task is not None and not state.task.done():
                continue
            if state.last_round is None or now - state.last_round >= state.interval:
                due.append(group_id)
        return due

    @_ha_callback
    def _handle_tick(self, _now: Any = None) -> None:
        for group_id in self.due_groups():
            state = self._groups[group_id]
            self._start_task(state, self.async_run_round(group_id, state.generation))

    # -- guards -------------------------------------------------------------

    def link_ok(self) -> bool:
        """Public form of the link check (used by the group switch)."""
        return self._link_ok()

    def _link_ok(self) -> bool:
        """False while unloading, after a failed poll, or with a disconnected hub."""
        coordinator = self._coordinator
        if getattr(coordinator, "_is_unloading", False):
            return False
        if getattr(coordinator, "last_update_success", True) is False:
            return False
        hub = getattr(coordinator, "hub", None)
        if hub is None:
            return True
        from .device_utils import hub_is_connected

        try:
            return bool(hub_is_connected(hub))
        except Exception:  # pragma: no cover - defensive
            return False

    def _round_guard(self, state: GroupState, generation: int, setpoint: Setpoint):
        """Checked under the I/O lock right before a cyclic write is sent."""

        def guard() -> bool:
            return (
                state.state == STATE_ACTIVE
                and state.generation == generation
                and state.setpoints.get(setpoint.register_key) is setpoint
                and self._link_ok()
            )

        return guard

    def _release_guard(self, state: GroupState, generation: int):
        def guard() -> bool:
            return (
                state.state != STATE_ACTIVE
                and state.generation == generation
                and self._link_ok()
            )

        return guard

    # -- rounds -------------------------------------------------------------

    async def async_run_round(self, group_id: str, generation: Optional[int] = None) -> None:
        """Write every setpoint of an active group once."""
        state = self._groups.get(group_id)
        if state is None or state.state != STATE_ACTIVE:
            return
        if generation is None:
            generation = state.generation
        if state.generation != generation:
            return
        state.last_round = self._loop_time()
        if not state.setpoints:
            return
        if not self._link_ok():
            self.stop_group(group_id, "link down or unloading")
            return

        # Read-back check of the previous round, based on the latest poll.
        for setpoint in list(state.setpoints.values()):
            if self._check_mismatch(state, setpoint):
                return

        round_failed = False
        for setpoint in list(state.setpoints.values()):
            if state.state != STATE_ACTIVE or state.generation != generation:
                return
            if state.setpoints.get(setpoint.register_key) is not setpoint:
                continue  # replaced by a newer user value; it is written next round

            value = setpoint.value
            if setpoint.kind == "number":
                clamped = self._apply_clamps(state, setpoint)
                if clamped is None:
                    return  # group stopped by the clamp check
                value = clamped

            result = await self._write(
                state, setpoint, value, self._round_guard(state, generation, setpoint)
            )
            if result is None:
                # Not sent: group stopped, link lost or setpoint replaced meanwhile.
                if state.state != STATE_ACTIVE or state.generation != generation:
                    return
                if not self._link_ok():
                    self.stop_group(group_id, "link down or unloading")
                    return
                continue
            if result:
                state.writes += 1
                state.last_write = self._wall_time()
                setpoint.last_write_loop_time = self._loop_time()
                setpoint.last_written_value = float(value)
            else:
                state.failed_writes += 1
                round_failed = True

        if state.state != STATE_ACTIVE or state.generation != generation:
            return
        if round_failed:
            state.consecutive_failures += 1
            _LOGGER.warning(
                "Keepalive group %s: write failed (%d/%d)",
                group_id,
                state.consecutive_failures,
                state.max_failures,
            )
            if state.consecutive_failures >= state.max_failures:
                self.stop_group(group_id, "repeated write failures")
                return
        else:
            state.consecutive_failures = 0
        self._notify(group_id)

    async def _async_release(
        self, group_id: str, generation: int, releases: list
    ) -> None:
        state = self._groups.get(group_id)
        if state is None:
            return
        for setpoint in releases:
            if state.generation != generation or not self._link_ok():
                return
            release_value = setpoint.config[KEEPALIVE_KEY]["release_value"]
            result = await self._write(
                state, setpoint, release_value, self._release_guard(state, generation)
            )
            if result is False:
                _LOGGER.warning(
                    "Keepalive group %s: release write for %s failed",
                    group_id,
                    setpoint.config.get("unique_id"),
                )

    def _check_mismatch(self, state: GroupState, setpoint: Setpoint) -> bool:
        """Count a read-back mismatch; return True if the group was stopped."""
        if setpoint.last_write_loop_time is None:
            return False
        data = self._coordinator.get_register_data(setpoint.register_key)
        if not data:
            return False
        timestamp = data.get("timestamp")
        if timestamp is None or timestamp <= setpoint.last_write_loop_time:
            return False  # no poll since our last write
        if setpoint.kind == "number":
            actual = data.get("processed_value")
        else:
            # select/switch repeat a raw register value; compare against the raw read.
            actual = None
            for key in ("raw_value", "numeric_value", "processed_value"):
                candidate = data.get(key)
                if isinstance(candidate, bool):
                    candidate = int(candidate)
                if _as_float(candidate) is not None:
                    actual = candidate
                    break
        actual_f = _as_float(actual)
        if actual_f is None:
            return False

        expected = (
            setpoint.last_written_value
            if setpoint.last_written_value is not None
            else setpoint.value
        )
        tolerance = setpoint.config.get(KEEPALIVE_KEY, {}).get("mismatch_tolerance")
        if tolerance is None:
            step = _as_float(setpoint.config.get("step")) or 0.0
            tolerance = max(abs(step) / 2.0, abs(expected) * 0.005, 1e-6)
        if math.isclose(actual_f, expected, abs_tol=tolerance):
            setpoint.mismatch_streak = 0
            return False

        state.mismatches += 1
        setpoint.mismatch_streak += 1
        _LOGGER.warning(
            "Keepalive group %s: %s reads %s, expected %s (%d/%d)",
            state.group_id,
            setpoint.config.get("unique_id"),
            actual_f,
            expected,
            setpoint.mismatch_streak,
            state.max_failures,
        )
        if setpoint.mismatch_streak >= state.max_failures:
            self.stop_group(state.group_id, "repeated read-back mismatches")
            return True
        return False

    # -- clamps -------------------------------------------------------------

    def _find_register_data(self, unique_id: str) -> Optional[Dict[str, Any]]:
        target = unique_id.lower()
        for data in self._coordinator.register_data.values():
            config = data.get("register_config") or {}
            if str(config.get("unique_id", "")).lower() == target:
                return data
        return None

    def _clamp_source_value(
        self, setpoint: Setpoint, key: str
    ) -> tuple[bool, Optional[float]]:
        """Return (ok, value) for a clamp source; ok=False means stale/unavailable."""
        keepalive = setpoint.config.get(KEEPALIVE_KEY, {})
        source = keepalive.get(f"{key}_source") or keepalive.get(key)
        if not source:
            return True, None
        data = self._find_register_data(source)
        if not data:
            return False, None
        max_age = keepalive.get("clamp_max_age", DEFAULT_CLAMP_MAX_AGE_S)
        timestamp = _as_float(data.get("timestamp"))
        if timestamp is None or self._loop_time() - timestamp > max_age:
            return False, None
        value = _as_float(data.get("processed_value"))
        if value is None:
            return False, None
        return True, value

    def _apply_clamps(self, state: GroupState, setpoint: Setpoint) -> Optional[float]:
        """Clamp the setpoint; stop the group (None) on bad or contradictory sources."""
        ok_max, max_v = self._clamp_source_value(setpoint, "clamp_max_to_register")
        ok_min, min_v = self._clamp_source_value(setpoint, "clamp_min_to_register")
        uid = setpoint.config.get("unique_id")
        if not (ok_max and ok_min):
            self.stop_group(state.group_id, f"clamp source for {uid} is stale or unavailable")
            return None
        if max_v is not None and min_v is not None and min_v > max_v:
            self.stop_group(state.group_id, f"clamp sources for {uid} contradict (min > max)")
            return None
        value = setpoint.value
        if max_v is not None:
            value = min(value, max_v)
        if min_v is not None:
            value = max(value, min_v)
        return value

    # -- writing ------------------------------------------------------------

    async def _write(
        self,
        state: GroupState,
        setpoint: Setpoint,
        value: float,
        guard: Callable[[], bool],
    ) -> Optional[bool]:
        """Send one write. Returns True/False, or None if the guard blocked it."""
        from .modbus_utils import encode_register_write_value, get_write_call_type

        config = setpoint.config
        try:
            if setpoint.kind == "number":
                scale = config.get("scale")
                if scale is None:
                    scale = config.get("multiplier")
                scale = float(scale) if scale not in (None, 0) else 1.0
                offset = float(config.get("offset", 0.0) or 0.0)
                payload_value: Any = (value - offset) / scale
            else:
                payload_value = int(value)
            payload, count = encode_register_write_value(payload_value, config)
            call_type = get_write_call_type(count, config.get("write_function_code"))
        except Exception as err:
            _LOGGER.warning(
                "Keepalive could not encode %s for %s: %s",
                value,
                config.get("unique_id"),
                err,
            )
            return False

        # The send runs shielded: cancelling a round or release task never
        # aborts a Modbus transaction mid-flight. A stopped group is still
        # caught by the guard, which is checked again under the I/O lock.
        return await asyncio.shield(
            self._send(state, config, payload, call_type, guard)
        )

    async def _send(
        self,
        state: GroupState,
        config: Dict[str, Any],
        payload: Any,
        call_type: Any,
        guard: Callable[[], bool],
    ) -> Optional[bool]:
        async with self._send_lock:
            # Minimum gap since the last keepalive write of this hub (any group).
            gap = state.min_write_spacing_ms / 1000.0
            if self._last_send is not None and gap > 0:
                wait = gap - (self._loop_time() - self._last_send)
                if wait > 0:
                    await self._sleep(wait)
            if not guard():
                return None

            blocked = False

            def checked_guard() -> bool:
                nonlocal blocked
                if guard():
                    return True
                blocked = True
                return False

            try:
                result = await self._coordinator.async_pb_write(
                    config.get("slave_id", 1),
                    config.get("address"),
                    payload,
                    call_type,
                    refresh=False,
                    guard=checked_guard,
                )
            except Exception as err:
                _LOGGER.warning(
                    "Keepalive write to %s failed: %s", config.get("unique_id"), err
                )
                self._last_send = self._loop_time()
                return False
            if blocked:
                return None
            self._last_send = self._loop_time()
            return bool(result)


def store_keepalive_setpoint(
    coordinator: Any,
    register_key: str,
    register_config: Dict[str, Any],
    value: Any,
    kind: str,
) -> None:
    """Store a successfully written value as setpoint if the control has keepalive."""
    keepalive = register_config.get(KEEPALIVE_KEY)
    if not isinstance(keepalive, dict) or not keepalive.get("group_id"):
        return
    manager = getattr(coordinator, "keepalive", None)
    if manager is None:
        return
    numeric = _as_float(value)
    if numeric is None:
        return
    manager.set_setpoint(keepalive["group_id"], register_key, register_config, numeric, kind)


def _current_task() -> Optional[asyncio.Task]:
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None
