"""Device registry helpers that stay quiet on HA 2026.8+."""

from __future__ import annotations

from typing import Any

# Distinguishes "attribute missing" from ``config_entry_id is None``.
_UNSET = object()


def device_belongs_to_config_entry(device_entry: Any, config_entry_id: str) -> bool:
    """True if this registry device is owned by ``config_entry_id``.

    Home Assistant 2026.8+: ``config_entry_id`` (do not read deprecated
    ``config_entries``). Older cores: membership in ``config_entries``.
    """
    current_entry_id = getattr(device_entry, "config_entry_id", _UNSET)
    if current_entry_id is not _UNSET:
        return current_entry_id == config_entry_id
    entries = getattr(device_entry, "config_entries", None) or ()
    return config_entry_id in entries


def device_subentry_ids_for_entry(
    device_entry: Any, config_entry_id: str
) -> set[str | None]:
    """Return subentry ids linked to a device for one config entry.

    Home Assistant 2026.8+ : one device, one entry — ``config_entry_id`` and
    ``config_subentry_id`` (do not read deprecated
    ``config_entries_subentries``). Older cores: the per-entry subentry map.
    """
    current_entry_id = getattr(device_entry, "config_entry_id", _UNSET)
    if current_entry_id is not _UNSET:
        if current_entry_id != config_entry_id:
            return set()
        return {getattr(device_entry, "config_subentry_id", None)}
    mapping = getattr(device_entry, "config_entries_subentries", None) or {}
    return set(mapping.get(config_entry_id, set()))
