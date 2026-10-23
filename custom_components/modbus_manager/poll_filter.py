"""Skip Modbus polls for Home Assistant-disabled entities.

Registry rows and unique_id stay. Discussion #107.
YAML ``always_poll: true`` keeps a disabled row in the read list so enabled
calculated sensors can still use the value (coordinator lookup, not HA state).
"""

from __future__ import annotations

from typing import Any


def template_always_poll(register: dict[str, Any]) -> bool:
    """Whether a disabled register must still be read."""
    value = register.get("always_poll")
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def registers_enabled_for_poll(
    registers: list[dict[str, Any]],
    disabled_unique_ids: set[str],
) -> list[dict[str, Any]]:
    """Drop template rows whose unique_id is disabled in the entity registry.

    Another enabled entity on the same slave/address is kept, so that address
    is still read. Missing unique_id is kept (do not skip unknown rows).
    ``always_poll`` rows stay even when their unique_id is disabled.
    """
    if not registers or not disabled_unique_ids:
        return list(registers)
    kept: list[dict[str, Any]] = []
    for register in registers:
        unique_id = str(register.get("unique_id") or "").strip()
        if unique_id and unique_id in disabled_unique_ids:
            if template_always_poll(register):
                kept.append(register)
            continue
        kept.append(register)
    return kept
