"""Core-style nan_value: decoded match becomes unknown before scale."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "custom_components" / "modbus_manager"
SHX = ROOT / "device_templates" / "sungrow_shx_dynamic.yaml"

NAN_REGISTERS = {
    "meter_active_power_raw",
    "meter_phase_a_active_power_raw",
    "meter_phase_b_active_power_raw",
    "meter_phase_c_active_power_raw",
    "meter_channel_2_total_active_power_raw",
    "meter_channel_2_phase_a_active_power_raw",
    "meter_channel_2_phase_b_active_power_raw",
    "meter_channel_2_phase_c_active_power_raw",
    "load_power",
    "export_power_raw",
}


def _load_nan_helpers():
    pkg = types.ModuleType("modbus_manager")
    pkg.__path__ = [str(ROOT)]
    sys.modules.setdefault("modbus_manager", pkg)

    const = types.ModuleType("modbus_manager.const")
    const.MAX_ENTITY_STATE_LENGTH = 255
    sys.modules.setdefault("modbus_manager.const", const)

    logger = types.ModuleType("modbus_manager.logger")

    class _Logger:
        def __init__(self, *_args):
            pass

        def debug(self, *_args):
            pass

        def warning(self, *_args):
            pass

        def error(self, *_args):
            pass

    logger.ModbusManagerLogger = _Logger
    sys.modules.setdefault("modbus_manager.logger", logger)

    from modbus_manager.value_processor import matches_nan_value, parse_nan_value

    return matches_nan_value, parse_nan_value


matches_nan_value, parse_nan_value = _load_nan_helpers()


class NanValueTests(unittest.TestCase):
    def test_hex_and_int_parse_to_the_same_sentinel(self) -> None:
        self.assertEqual(parse_nan_value("0x7FFFFFFF"), 2147483647)
        self.assertEqual(parse_nan_value(0x7FFFFFFF), 2147483647)
        self.assertEqual(parse_nan_value(0), 0)

    def test_invalid_nan_value_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_nan_value("nope")
        with self.assertRaises(ValueError):
            parse_nan_value(None)

    def test_match_is_before_scale_and_includes_negation(self) -> None:
        self.assertTrue(matches_nan_value(2147483647, "0x7FFFFFFF"))
        self.assertTrue(matches_nan_value(-2147483647, 0x7FFFFFFF))
        self.assertFalse(matches_nan_value(214748364.7, "0x7FFFFFFF"))
        self.assertFalse(matches_nan_value(0, None))
        self.assertFalse(matches_nan_value("2147483647", "0x7FFFFFFF"))

    def test_zero_sentinel_matches_zero(self) -> None:
        self.assertTrue(matches_nan_value(0, 0))
        self.assertFalse(matches_nan_value(1, 0))

    def test_shx_power_registers_declare_the_sentinel(self) -> None:
        data = yaml.safe_load(SHX.read_text(encoding="utf-8"))
        found = {
            row["unique_id"]: row.get("nan_value")
            for row in data["sensors"]
            if isinstance(row, dict) and row.get("unique_id") in NAN_REGISTERS
        }
        self.assertEqual(set(found), NAN_REGISTERS)
        self.assertTrue(all(value == 2147483647 for value in found.values()))

    def test_shx_calculated_sensors_do_not_treat_unknown_as_zero(self) -> None:
        text = SHX.read_text(encoding="utf-8")
        for uid in NAN_REGISTERS:
            leaked = f"not is_state('[[mm:sensor:{{PREFIX}}_{uid}]]', 'unavailable')"
            self.assertNotIn(leaked, text)
            guarded = (
                f"states('[[mm:sensor:{{PREFIX}}_{uid}]]') "
                "not in ['unknown', 'unavailable', 'none']"
            )
            self.assertIn(guarded, text)


if __name__ == "__main__":
    unittest.main()
