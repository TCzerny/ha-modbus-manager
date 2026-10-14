"""Unit tests for Fast / Medium / Slow scan groups."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


def _install_ha_stubs() -> None:
    if "homeassistant" in sys.modules:
        return

    def _mod(name: str) -> types.ModuleType:
        module = types.ModuleType(name)
        sys.modules[name] = module
        return module

    ha = _mod("homeassistant")
    const = _mod("homeassistant.const")
    const.Platform = types.SimpleNamespace(
        SENSOR="sensor",
        NUMBER="number",
        SWITCH="switch",
        SELECT="select",
        BUTTON="button",
        BINARY_SENSOR="binary_sensor",
        TEXT="text",
    )
    ha.const = const
    _mod("homeassistant.core")


def _load_scan_groups():
    _install_ha_stubs()
    root = Path(__file__).resolve().parents[1] / "custom_components" / "modbus_manager"
    pkg = types.ModuleType("modbus_manager")
    pkg.__path__ = [str(root)]
    sys.modules.setdefault("modbus_manager", pkg)
    from modbus_manager.scan_groups import (  # type: ignore
        normalize_scan_group,
        persist_scan_groups,
        scan_group_seconds_from_config,
        seconds_until_next_due,
    )

    return (
        persist_scan_groups,
        scan_group_seconds_from_config,
        normalize_scan_group,
        seconds_until_next_due,
    )


(
    persist_scan_groups,
    scan_group_seconds_from_config,
    normalize_scan_group,
    seconds_until_next_due,
) = _load_scan_groups()


class ScanGroupTests(unittest.TestCase):
    def test_normalize_explicit_and_legacy_interval(self) -> None:
        self.assertEqual(normalize_scan_group({"scan_group": "fast"}), "fast")
        self.assertEqual(normalize_scan_group({"scan_interval": 10}), "fast")
        self.assertEqual(normalize_scan_group({"scan_interval": 30}), "medium")
        self.assertEqual(normalize_scan_group({"scan_interval": 600}), "slow")
        self.assertEqual(normalize_scan_group({}), "medium")

    def test_persist_survives_on_entry_and_hub(self) -> None:
        data = {"hub": {"host": "1.2.3.4"}}
        persist_scan_groups(data, {"scan_group_fast": 2, "scan_group_medium": 30})
        self.assertEqual(data["scan_group_fast"], 2)
        self.assertEqual(data["scan_group_medium"], 30)
        self.assertEqual(data["scan_group_slow"], 600)
        self.assertEqual(data["hub"]["scan_group_fast"], 2)
        again = scan_group_seconds_from_config(data)
        self.assertEqual(again["fast"], 2)
        self.assertEqual(again["slow"], 600)

    def test_missing_keys_use_defaults(self) -> None:
        seconds = scan_group_seconds_from_config({})
        self.assertEqual(seconds["fast"], 10)
        self.assertEqual(seconds["medium"], 30)
        self.assertEqual(seconds["slow"], 600)

    def test_io_time_is_not_added_on_top_of_interval(self) -> None:
        wait = seconds_until_next_due(
            last_update_time={"fast": 100.0},
            scan_group_seconds={"fast": 5, "medium": 30, "slow": 600},
            populated_groups=["fast"],
            now=104.0,
        )
        self.assertAlmostEqual(wait, 1.0)

    def test_overrun_polls_immediately(self) -> None:
        wait = seconds_until_next_due(
            last_update_time={"fast": 100.0},
            scan_group_seconds={"fast": 5},
            populated_groups=["fast"],
            now=108.0,
        )
        self.assertEqual(wait, 0.1)


if __name__ == "__main__":
    unittest.main()
