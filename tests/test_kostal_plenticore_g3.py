"""Contract tests for the read-only KOSTAL PLENTICORE G3 template.

Raw register words were captured with FC03 from a PLENTICORE G3 M
(UI/FW 3.07.03.27599, byte order CDAB, BYD HVS, KSEM) on 08.11.2026.
"""

from __future__ import annotations

import importlib.util
import struct
import sys
import types
import unittest
from pathlib import Path

import yaml

from test_register_optimizer import ranges

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = (
    REPO_ROOT / "custom_components/modbus_manager/device_templates/kostal_plenticore_g3.yaml"
)
UTILS_PATH = REPO_ROOT / "custom_components/modbus_manager/modbus_utils.py"

# Undocumented ranges the inverter answered with exception 2 (illegal data address).
REJECTED_RANGES = ((71, 97), (300, 319), (592, 607))

# address -> (raw words as read, expected decoded value)
CAPTURED = {
    56: ([6, 0], 6),  # inverter state FeedIn (U32, CDAB)
    210: ([0, 16816], 22.0),  # SoC (Float32, CDAB)
    200: ([27708, 49206], -2.85),  # battery current, charging
    252: ([52429, 16756], 15.3),  # meter total active power
    512: ([0, 48], 48),  # battery gross capacity Ah (U32, high word first)
    529: ([0, 29200], 29200),  # battery work capacity Wh (U32, high word first)
    577: ([239, 27430], 15690534),  # generation energy Wh, matches total yield (320)
    1288: ([0, 60], 60),  # time until fallback s (U32, high word first)
    40164: ([11776, 16952], 46.045),  # heat sink temperature, SunSpec model 113 float (CDAB)
    40346: ([184, 53559], 12112183),  # total energy exported Wh
}


def load_modbus_utils():
    """Load modbus_utils with a stub for the Home Assistant constants."""
    for name in ("homeassistant", "homeassistant.components", "homeassistant.components.modbus"):
        sys.modules.setdefault(name, types.ModuleType(name))
    const = types.ModuleType("homeassistant.components.modbus.const")
    for attr in (
        "CALL_TYPE_REGISTER_HOLDING",
        "CALL_TYPE_REGISTER_INPUT",
        "CALL_TYPE_WRITE_REGISTERS",
        "CALL_TYPE_WRITE_REGISTER",
    ):
        setattr(const, attr, attr.lower())
    sys.modules["homeassistant.components.modbus.const"] = const
    spec = importlib.util.spec_from_file_location("kostal_test_modbus_utils", UTILS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODBUS_UTILS = load_modbus_utils()


class KostalPlenticoreG3TemplateTest(unittest.TestCase):
    """Keep the verified encoding and transaction plan intact."""

    @classmethod
    def setUpClass(cls):
        cls.template = yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))
        cls.sensors = cls.template["sensors"]
        cls.by_address = {sensor["address"]: sensor for sensor in cls.sensors}

    def test_identity_and_unique_ids(self):
        self.assertEqual(self.template["manufacturer"], "KOSTAL")
        self.assertEqual(self.template["default_slave_id"], 71)
        unique_ids = [sensor["unique_id"] for sensor in self.sensors]
        self.assertEqual(len(unique_ids), len(set(unique_ids)))

    def test_template_is_read_only(self):
        for key in ("controls", "numbers", "selects", "switches", "buttons"):
            self.assertNotIn(key, self.template)
        for sensor in self.sensors:
            with self.subTest(sensor=sensor["unique_id"]):
                self.assertEqual(sensor["input_type"], "holding")
                self.assertEqual(sensor["read_function_code"], 3)

    def test_reads_never_touch_rejected_ranges(self):
        planned = ranges([dict(sensor, slave_id=71) for sensor in self.sensors])
        self.assertTrue(planned)
        for start, end, count in planned:
            self.assertLessEqual(count, 64)
            self.assertIn(start, self.by_address)
            for low, high in REJECTED_RANGES:
                with self.subTest(range=(start, end), rejected=(low, high)):
                    self.assertTrue(end < low or start > high)

    def test_captured_values_decode(self):
        for address, (words, expected) in CAPTURED.items():
            sensor = self.by_address[address]
            raw = MODBUS_UTILS.registers_to_bytes(
                words, byte_order=sensor.get("byte_order", "big"), swap=sensor.get("swap", "none")
            )
            fmt = ">f" if sensor["data_type"] == "float32" else ">I"
            with self.subTest(address=address):
                self.assertAlmostEqual(struct.unpack(fmt, raw)[0], expected, places=2)

    def test_battery_bank_state_map(self):
        state = self.by_address[40437]  # SunSpec model 802 State, captured value 3
        self.assertEqual(state["map"][3], "CONNECTED")
        self.assertEqual(state["map"][99], "FAULT")
        events = self.by_address[40441]  # Evt1, uint32 high word first
        self.assertEqual(events["swap"], "none")
        self.assertEqual(events["flags"][0], "COMMUNICATION_ERROR")

    def test_captured_strings_decode(self):
        words = [16985, 17440, 8224, 8224, 8224, 8224, 8224, 8224]  # 517: "BYD" + spaces
        text = MODBUS_UTILS.registers_to_bytes(words).decode("latin1").strip()
        self.assertEqual(text, "BYD")
        self.assertEqual(self.by_address[517]["data_type"], "string")


if __name__ == "__main__":
    unittest.main()
