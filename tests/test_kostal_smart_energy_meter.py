"""Contract tests for the read-only KOSTAL Smart Energy Meter template.

Raw register words were captured with FC03 from a KSEM G2 (HWv3, firmware 2.7.2)
on 08.11.2026.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = (
    REPO_ROOT
    / "custom_components/modbus_manager/device_templates/kostal_smart_energy_meter.yaml"
)

# address -> (raw words as read, expected value after scale)
CAPTURED = {
    0: ([0, 85], 8.5),  # active power import, 0.1 W
    26: ([0, 50004], 50.004),  # frequency, 0.001 Hz
    62: ([3, 40425], 237.033),  # L1 voltage, 0.001 V
    514: ([162, 16034], 1063286.6),  # lower 32 bits of uint64 energy import, 0.1 Wh
    518: ([1848, 11469], 12112199.7),  # lower 32 bits of uint64 energy export
    40984: ([65535, 64726], -810),  # battery power, int32, charging
}


def decode(words: list[int], data_type: str) -> int:
    value = 0
    for word in words:
        value = (value << 16) | word
    if data_type == "int32" and value >= 1 << 31:
        value -= 1 << 32
    return value


class KostalSmartEnergyMeterTemplateTest(unittest.TestCase):
    """Keep the verified encoding intact."""

    @classmethod
    def setUpClass(cls):
        cls.template = yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))
        cls.sensors = cls.template["sensors"]
        cls.by_address = {sensor["address"]: sensor for sensor in cls.sensors}

    def test_identity_and_unique_ids(self):
        self.assertEqual(self.template["manufacturer"], "KOSTAL")
        self.assertEqual(self.template["default_slave_id"], 1)
        unique_ids = [sensor["unique_id"] for sensor in self.sensors]
        self.assertEqual(len(unique_ids), len(set(unique_ids)))

    def test_template_is_read_only_and_big_endian(self):
        for key in ("controls", "numbers", "selects", "switches", "buttons"):
            self.assertNotIn(key, self.template)
        for sensor in self.sensors:
            with self.subTest(sensor=sensor["unique_id"]):
                self.assertEqual(sensor["input_type"], "holding")
                self.assertEqual(sensor["read_function_code"], 3)
                if sensor.get("count") == 2 and sensor["data_type"] != "string":
                    self.assertEqual(sensor["swap"], "none")

    def test_energy_counters_read_lower_words(self):
        for address in (514, 518):
            sensor = self.by_address[address]
            self.assertEqual(sensor["data_type"], "uint32")
            self.assertEqual(sensor["state_class"], "total_increasing")

    def test_captured_values_decode(self):
        for address, (words, expected) in CAPTURED.items():
            sensor = self.by_address[address]
            value = decode(words, sensor["data_type"]) * sensor.get("scale", 1)
            with self.subTest(address=address):
                self.assertAlmostEqual(value, expected, places=3)


if __name__ == "__main__":
    unittest.main()
