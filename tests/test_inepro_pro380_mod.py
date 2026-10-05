"""Focused contract tests for the inepro PRO380-Mod template."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from test_register_optimizer import ranges


TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components/modbus_manager/device_templates/inepro_pro380_mod.yaml"
)


class IneproPro380ModTemplateTest(unittest.TestCase):
    """Keep the validated register map and PF transaction plan intact."""

    @classmethod
    def setUpClass(cls):
        cls.template = yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))
        cls.sensors = cls.template["sensors"]

    def test_template_identity_and_unique_ids(self):
        self.assertEqual(self.template["name"], "inepro PRO380-Mod")
        self.assertEqual(self.template["manufacturer"], "inepro")
        self.assertEqual(self.template["model"], "PRO380-Mod")
        self.assertEqual(self.template["default_prefix"], "inepro_pro380")
        unique_ids = [sensor["unique_id"] for sensor in self.sensors]
        self.assertEqual(len(unique_ids), len(set(unique_ids)))

    def test_all_measurements_are_documented_fc03_float32_values(self):
        for sensor in self.sensors:
            with self.subTest(sensor=sensor["unique_id"]):
                self.assertEqual(sensor["input_type"], "holding")
                self.assertEqual(sensor["read_function_code"], 3)
                self.assertEqual(sensor["data_type"], "float32")
                self.assertEqual(sensor["count"], 2)
                self.assertEqual(sensor["byte_order"], "big")
                self.assertEqual(sensor["swap"], "none")
                self.assertIsInstance(sensor["address"], int)
                self.assertGreaterEqual(sensor["scan_interval"], 0)

    def test_power_factor_layout_and_transaction_boundaries(self):
        pf = [sensor for sensor in self.sensors if "Power Factor" in sensor["name"]]
        self.assertEqual(
            [(sensor["address"], sensor["scan_interval"], sensor["read_group"]) for sensor in pf],
            [
                (0x502A, 300, "pro380_pf_total"),
                (0x502C, 60, "pro380_pf_phases"),
                (0x502E, 60, "pro380_pf_phases"),
                (0x5030, 60, "pro380_pf_phases"),
            ],
        )
        self.assertEqual(ranges(pf), [(0x502A, 0x502B, 2), (0x502C, 0x5031, 6)])

    def test_no_solar_log_technical_identity_remains(self):
        serialized = yaml.safe_dump(self.template).lower()
        self.assertNotIn("solar_log", serialized)
        self.assertNotIn("solar-log", serialized)


if __name__ == "__main__":
    unittest.main()
