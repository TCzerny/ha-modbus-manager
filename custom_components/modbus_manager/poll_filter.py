"""Skip Modbus polls for Home Assistant-disabled entities.

Registry rows and unique_id stay. Discussion #107.
"""

from __future__ import annotations

from typing import Any


def registers_enabled_for_poll(
    registers: list[dict[str, Any]],
    disabled_unique_ids: set[str],
) -> list[dict[str, Any]]:
    """Drop template rows whose unique_id is disabled in the entity registry.

    Another enabled entity on the same slave/address is kept, so that address
    is still read. Missing unique_id is kept (do not skip unknown rows).
    """
    if not registers or not disabled_unique_ids:
        return list(registers)
    kept: list[dict[str, Any]] = []
    for register in registers:
        unique_id = str(register.get("unique_id") or "").strip()
        if unique_id and unique_id in disabled_unique_ids:
            continue
        kept.append(register)
    return kept
