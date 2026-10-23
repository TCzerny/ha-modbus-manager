"""Unit tests for skipping HA-disabled entities in Modbus polls."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


def _load_poll_filter():
    root = Path(__file__).resolve().parents[1] / "custom_components" / "modbus_manager"
    pkg = types.ModuleType("modbus_manager")
    pkg.__path__ = [str(root)]
    sys.modules.setdefault("modbus_manager", pkg)
    from modbus_manager.poll_filter import registers_enabled_for_poll  # type: ignore

    return registers_enabled_for_poll


registers_enabled_for_poll = _load_poll_filter()


class PollFilterTests(unittest.TestCase):
    def test_disabled_unique_id_dropped(self) -> None:
        registers = [
            {"unique_id": "sg_ok", "address": 10},
            {"unique_id": "sg_bad", "address": 11},
            {"unique_id": "sg_ok2", "address": 12},
        ]
        kept = registers_enabled_for_poll(registers, {"sg_bad"})
        self.assertEqual([r["unique_id"] for r in kept], ["sg_ok", "sg_ok2"])

    def test_shared_address_kept_if_sibling_enabled(self) -> None:
        registers = [
            {"unique_id": "sg_a", "address": 50, "slave_id": 1},
            {"unique_id": "sg_b", "address": 50, "slave_id": 1},
        ]
        kept = registers_enabled_for_poll(registers, {"sg_a"})
        self.assertEqual([r["unique_id"] for r in kept], ["sg_b"])

    def test_missing_unique_id_kept(self) -> None:
        registers = [{"address": 1}, {"unique_id": "x", "address": 2}]
        kept = registers_enabled_for_poll(registers, {"x"})
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].get("address"), 1)

    def test_empty_disabled_set_keeps_all(self) -> None:
        registers = [{"unique_id": "a", "address": 1}]
        self.assertEqual(registers_enabled_for_poll(registers, set()), registers)

    def test_always_poll_keeps_disabled_unique_id(self) -> None:
        registers = [
            {"unique_id": "sg_ok", "address": 10},
            {"unique_id": "sg_month", "address": 11, "always_poll": True},
            {"unique_id": "sg_debug", "address": 12},
        ]
        kept = registers_enabled_for_poll(registers, {"sg_month", "sg_debug"})
        self.assertEqual([r["unique_id"] for r in kept], ["sg_ok", "sg_month"])


if __name__ == "__main__":
    unittest.main()
