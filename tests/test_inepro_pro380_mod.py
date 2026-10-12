"""Focused contract tests for the inepro PRO380-Mod template."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from test_register_optimizer import ranges


TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components/modbus_manager/device_templates/inepro_pro380_mod.yaml"
)
TRANSLATION_PATHS = (
    Path(__file__).resolve().parents[1]
    / "custom_components/modbus_manager/translations/en.json",
    Path(__file__).resolve().parents[1]
    / "custom_components/modbus_manager/translations/de.json",
)

EXPECTED_REGISTER_DEFINITIONS = {
    "l1_voltage": (20482, 15, None),
    "l2_voltage": (20484, 15, None),
    "l3_voltage": (20486, 15, None),
    "grid_frequency": (20488, 30, None),
    "l1_current": (20492, 15, None),
    "l2_current": (20494, 15, None),
    "l3_current": (20496, 15, None),
    "total_active_power": (20498, 15, None),
    "l1_active_power": (20500, 15, None),
    "l2_active_power": (20502, 15, None),
    "l3_active_power": (20504, 15, None),
    "total_power_factor": (20522, 300, "pro380_pf_total"),
    "l1_power_factor": (20524, 60, "pro380_pf_phases"),
    "l2_power_factor": (20526, 60, "pro380_pf_phases"),
    "l3_power_factor": (20528, 60, "pro380_pf_phases"),
    "imported_energy": (24588, 60, None),
    "exported_energy": (24600, 60, None),
}


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
        self.assertEqual(set(unique_ids), set(EXPECTED_REGISTER_DEFINITIONS))

    def test_translation_keys_have_complete_en_and_de_coverage(self):
        keys = [sensor.get("translation_key") for sensor in self.sensors]
        self.assertEqual(len(self.sensors), 17)
        self.assertTrue(all(keys))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(
            set(keys),
            {f"inepro_pro380_{unique_id}" for unique_id in EXPECTED_REGISTER_DEFINITIONS},
        )

        for translation_path in TRANSLATION_PATHS:
            translations = json.loads(translation_path.read_text(encoding="utf-8"))
            sensor_translations = translations["entity"]["sensor"]
            for key in keys:
                with self.subTest(language=translation_path.name, key=key):
                    self.assertIn(key, sensor_translations)
                    self.assertTrue(sensor_translations[key].get("name", "").strip())

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

    def test_register_definitions_remain_hardware_validated(self):
        actual = {
            sensor["unique_id"]: (
                sensor["address"],
                sensor["scan_interval"],
                sensor.get("read_group"),
            )
            for sensor in self.sensors
        }
        self.assertEqual(actual, EXPECTED_REGISTER_DEFINITIONS)

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
