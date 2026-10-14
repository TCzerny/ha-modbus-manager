"""Hub-level Fast / Medium / Slow poll cadences for YAML registers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .const import (
    CONF_SCAN_GROUP,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_GROUP_SECONDS,
    MAX_SCAN_GROUP_SECONDS,
    MIN_SCAN_GROUP_SECONDS,
    SCAN_GROUP_CONF_KEYS,
    SCAN_GROUP_FAST,
    SCAN_GROUP_MEDIUM,
    SCAN_GROUP_SLOW,
    SCAN_GROUPS,
)

_ENTITY_BUCKETS = ("sensors", "controls", "calculated", "binary_sensors")


def clamp_scan_group_seconds(value: Any, default: int) -> int:
    """Clamp a poll interval to the allowed hub range."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(MIN_SCAN_GROUP_SECONDS, min(MAX_SCAN_GROUP_SECONDS, seconds))


def _has_scan_group_value(value: Any) -> bool:
    """Return True when a form/storage value should override a default."""
    return value is not None and value != ""


def scan_group_seconds_from_config(
    data: Mapping[str, Any] | None,
    options: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    """Read Fast/Medium/Slow seconds from hub entry data (defaults if absent)."""
    source = data or {}
    hub = source.get("hub") if isinstance(source.get("hub"), dict) else {}
    options = options or {}
    seconds: dict[str, int] = {}
    for group, conf_key in SCAN_GROUP_CONF_KEYS.items():
        default = DEFAULT_SCAN_GROUP_SECONDS[group]
        raw: Any = default
        if _has_scan_group_value(source.get(conf_key)):
            raw = source[conf_key]
        elif _has_scan_group_value(hub.get(conf_key)):
            raw = hub[conf_key]
        if _has_scan_group_value(options.get(conf_key)):
            raw = options[conf_key]
        seconds[group] = clamp_scan_group_seconds(raw, default)
    return seconds


def persist_scan_groups(
    entry_data: dict[str, Any],
    user_input: Mapping[str, Any] | None = None,
) -> None:
    """Write clamped scan-group seconds onto entry data and nested hub dict."""
    merged = dict(entry_data)
    if user_input:
        for conf_key in SCAN_GROUP_CONF_KEYS.values():
            if conf_key in user_input and _has_scan_group_value(user_input[conf_key]):
                merged[conf_key] = user_input[conf_key]
    seconds = scan_group_seconds_from_config(merged)
    for group, conf_key in SCAN_GROUP_CONF_KEYS.items():
        entry_data[conf_key] = seconds[group]
    hub = entry_data.get("hub")
    if isinstance(hub, dict):
        for group, conf_key in SCAN_GROUP_CONF_KEYS.items():
            hub[conf_key] = seconds[group]


def seconds_until_next_due(
    *,
    last_update_time: Mapping[str, float],
    scan_group_seconds: Mapping[str, int],
    populated_groups: Iterable[str],
    now: float,
    min_wait: float = 0.1,
) -> float:
    """Seconds to wait so the next Fast/Medium/Slow poll is not delayed by I/O."""
    waits: list[float] = []
    for group in populated_groups:
        interval = float(scan_group_seconds.get(group, 30))
        last = last_update_time.get(group)
        if last is None:
            return min_wait
        waits.append(interval - (now - last))
    if not waits:
        return 5.0
    return max(min_wait, min(waits))


def normalize_scan_group(register: Mapping[str, Any] | None) -> str:
    """Map a register to fast / medium / slow.

    Explicit ``scan_group`` wins. Legacy ``scan_interval`` maps 1–15 → fast,
    16–60 → medium, otherwise slow. Missing values are medium.
    """
    if not register:
        return SCAN_GROUP_MEDIUM
    raw = register.get(CONF_SCAN_GROUP)
    if isinstance(raw, str):
        key = raw.strip().lower()
        if key in SCAN_GROUPS:
            return key
    interval = register.get(CONF_SCAN_INTERVAL)
    if isinstance(interval, bool):
        return SCAN_GROUP_MEDIUM
    if isinstance(interval, (int, float)):
        if interval <= 15:
            return SCAN_GROUP_FAST
        if interval <= 60:
            return SCAN_GROUP_MEDIUM
        return SCAN_GROUP_SLOW
    return SCAN_GROUP_MEDIUM


def annotate_register_scan_timing(
    register: dict[str, Any],
    seconds: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Set scan_group and resolved scan_interval seconds on a register dict."""
    mapping = seconds or DEFAULT_SCAN_GROUP_SECONDS
    group = normalize_scan_group(register)
    register[CONF_SCAN_GROUP] = group
    register[CONF_SCAN_INTERVAL] = int(
        mapping.get(group, DEFAULT_SCAN_GROUP_SECONDS[SCAN_GROUP_MEDIUM])
    )
    return register


def annotate_entity_buckets(
    entities: dict[str, Any],
    seconds: Mapping[str, int],
) -> dict[str, Any]:
    """Shallow-copy entity rows and stamp hub scan-group seconds."""
    for bucket in _ENTITY_BUCKETS:
        rows = entities.get(bucket) or []
        entities[bucket] = [
            annotate_register_scan_timing(dict(row), seconds)
            if isinstance(row, dict)
            else row
            for row in rows
        ]
    return entities
