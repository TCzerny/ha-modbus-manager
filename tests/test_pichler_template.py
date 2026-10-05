"""Focused structural tests for the Pichler LG ES2020 template."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "custom_components/modbus_manager/device_templates/pichler_lg_es2020.yaml"
COMBINED = "external_combined_heating_cooling_water_coil"
CHILLED = "external_chilled_water_cooling_coil"
ELECTRIC_PREHEATER = "electric"


class PichlerTemplateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
        cls.entities = [
            entity
            for section in ("sensors", "binary_sensors", "controls")
            for entity in cls.data[section]
        ]

    def test_family_platform_identity_and_prefix(self):
        self.assertEqual(self.data["name"], "Pichler LG (ES2020)")
        self.assertEqual(self.data["display_name"], "Pichler LG (ES2020)")
        self.assertEqual(self.data["default_prefix"], "pichler_lg")
        self.assertIn("LG350", self.data["model"])
        self.assertIn("LG450", self.data["model"])
        self.assertIn("LG740", self.data["model"])
        self.assertIn("LG1000", self.data["model"])
        self.assertNotIn("valid_models", self.data["dynamic_config"])

    def test_unique_ids_are_unique(self):
        ids = [entity["unique_id"] for entity in self.entities]
        self.assertEqual(len(ids), len(set(ids)))
        generated = [f"{self.data['default_prefix']}_{unique_id}" for unique_id in ids]
        self.assertEqual(len(generated), len(set(generated)))

    def test_combined_coil_only_entities_are_conditioned(self):
        expected = {
            "heating_demand": ("binary_sensors", 17),
            "combined_coil_mixer_control_signal": ("sensors", 26),
        }
        condition = f"post_heating_cooling_type == '{COMBINED}'"
        for unique_id, (section, address) in expected.items():
            entity = next(item for item in self.data[section] if item["unique_id"] == unique_id)
            self.assertEqual(entity["address"], address)
            self.assertEqual(entity["condition"], condition)

        cooling_pump = next(
            item
            for item in self.data["binary_sensors"]
            if item["unique_id"] == "cooling_pump_running"
        )
        self.assertEqual(cooling_pump["address"], 28)
        self.assertIn(f"== '{CHILLED}'", cooling_pump["condition"])
        self.assertIn(f"== '{COMBINED}'", cooling_pump["condition"])

    def test_chilled_water_and_combined_coil_applicability_matrix(self):
        matrix = {
            "external_supply_air_temperature": (4, True, True),
            "cooling_coil_mixer_control_signal": (12, True, False),
            "heating_demand": (17, False, True),
            "cooling_demand": (18, True, True),
            "combined_coil_mixer_control_signal": (26, False, True),
            "cooling_pump_running": (28, True, True),
            "external_supply_air_temperature_sensor_fault": (70, True, True),
        }
        entities = {entity["unique_id"]: entity for entity in self.entities}
        for unique_id, (address, chilled, combined) in matrix.items():
            with self.subTest(entity=unique_id):
                entity = entities[unique_id]
                condition = entity["condition"]
                self.assertEqual(entity["address"], address)
                self.assertEqual(f"== '{CHILLED}'" in condition, chilled)
                self.assertEqual(f"== '{COMBINED}'" in condition, combined)

        ao2 = entities["cooling_coil_mixer_control_signal"]
        self.assertTrue(ao2.get("enabled_by_default", True))
        self.assertEqual(ao2["input_type"], "input")
        self.assertEqual(ao2["data_type"], "uint16")
        self.assertEqual(ao2["scale"], 0.01)
        self.assertEqual(ao2["unit_of_measurement"], "V")
        self.assertNotIn("write_function_code", ao2)

        self.assertNotIn("condition", entities["heating_pump_running"])

    def test_combined_coil_mixer_signal_is_enabled_and_unchanged(self):
        entity = next(
            item
            for item in self.data["sensors"]
            if item["unique_id"] == "combined_coil_mixer_control_signal"
        )
        self.assertTrue(entity.get("enabled_by_default", True))
        self.assertEqual(entity["address"], 26)
        self.assertEqual(entity["input_type"], "input")
        self.assertEqual(entity["data_type"], "uint16")
        self.assertEqual(entity["scale"], 0.01)
        self.assertEqual(entity["unit_of_measurement"], "V")
        self.assertEqual(entity["scan_interval"], 60)
        self.assertEqual(
            entity["condition"],
            f"post_heating_cooling_type == '{COMBINED}'",
        )

    def test_post_heating_cooling_type_is_the_only_current_equipment_field(self):
        config = self.data["dynamic_config"]
        self.assertNotIn("hvac_equipment", config)
        self.assertEqual(config["post_heating_cooling_type"]["default"], "none")
        self.assertEqual(
            set(config["post_heating_cooling_type"]["options"]),
            {"none", CHILLED, COMBINED},
        )

    def test_preheater_type_and_preheater_entities_are_independent(self):
        config = self.data["dynamic_config"]
        self.assertEqual(config["preheater_type"]["default"], "none")
        self.assertEqual(set(config["preheater_type"]["options"]), {"none", ELECTRIC_PREHEATER})
        condition = f"preheater_type == '{ELECTRIC_PREHEATER}'"
        expected = {
            "preheater_temperature": ("sensors", 34),
            "preheater_temperature_sensor_fault": ("binary_sensors", 69),
            "low_preheater_temperature_fault": ("binary_sensors", 76),
        }
        for unique_id, (section, address) in expected.items():
            entity = next(item for item in self.data[section] if item["unique_id"] == unique_id)
            self.assertEqual(entity["address"], address)
            self.assertEqual(entity["condition"], condition)

        relay = next(item for item in self.data["binary_sensors"] if item["unique_id"] == "preheater_relay")
        self.assertEqual(relay["address"], 16)
        self.assertNotIn("condition", relay)

    def test_all_preheater_and_post_heating_cooling_combinations(self):
        def included_ids(preheater_type, post_heating_cooling_type):
            values = {
                "preheater_type": preheater_type,
                "post_heating_cooling_type": post_heating_cooling_type,
            }
            result = set()
            for entity in self.entities:
                condition = entity.get("condition")
                if not condition:
                    result.add(entity["unique_id"])
                    continue
                if any(
                    values["post_heating_cooling_type"] == option
                    for option in (CHILLED, COMBINED)
                    if f"== '{option}'" in condition
                ) or (
                    values["preheater_type"] == ELECTRIC_PREHEATER
                    and f"== '{ELECTRIC_PREHEATER}'" in condition
                ):
                    result.add(entity["unique_id"])
            return result

        preheater = {
            "preheater_temperature",
            "preheater_temperature_sensor_fault",
            "low_preheater_temperature_fault",
        }
        combined_only = {
            "heating_demand",
            "combined_coil_mixer_control_signal",
        }
        shared_cooling = {
            "external_supply_air_temperature",
            "cooling_demand",
            "cooling_pump_running",
            "external_supply_air_temperature_sensor_fault",
        }
        chilled_only = {"cooling_coil_mixer_control_signal"}
        for preheater_type, post_type, expected_preheater, expected_chilled, expected_combined in (
            ("none", "none", False, False, False),
            (ELECTRIC_PREHEATER, "none", True, False, False),
            ("none", CHILLED, False, True, False),
            ("none", COMBINED, False, False, True),
            (ELECTRIC_PREHEATER, CHILLED, True, True, False),
            (ELECTRIC_PREHEATER, COMBINED, True, False, True),
        ):
            with self.subTest(preheater_type=preheater_type, post_type=post_type):
                included = included_ids(preheater_type, post_type)
                self.assertEqual(preheater <= included, expected_preheater)
                self.assertEqual(shared_cooling <= included, post_type in {CHILLED, COMBINED})
                self.assertEqual(chilled_only <= included, expected_chilled)
                self.assertEqual(combined_only <= included, expected_combined)
                self.assertIn("preheater_relay", included)

    def test_translation_keys_exist_in_both_languages(self):
        translations = [
            json.loads((ROOT / "custom_components/modbus_manager/translations/en.json").read_text()),
            json.loads((ROOT / "custom_components/modbus_manager/translations/de.json").read_text()),
        ]
        self.assertEqual(len(self.entities), 55)
        self.assertTrue(all("translation_key" in entity for entity in self.entities))
        keys = [entity["translation_key"] for entity in self.entities]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(key.startswith("pichler_lg_es2020_") for key in keys))
        self.assertFalse(any(key.startswith("pichler_lg350_") for key in keys))
        for section, platform in (
            ("sensors", "sensor"),
            ("binary_sensors", "binary_sensor"),
        ):
            for entity in self.data[section]:
                for translation in translations:
                    self.assertIn(entity["translation_key"], translation["entity"][platform])
        for entity in self.data["controls"]:
            platform = entity["type"]
            for translation in translations:
                self.assertIn(entity["translation_key"], translation["entity"][platform])

    def test_enabled_by_default_contract_is_unchanged(self):
        disabled = {
            "device_model",
            "controller_firmware_version",
            "preheater_temperature",
            "supply_airflow_setpoint",
            "extract_airflow_setpoint",
            "current_ventilation_level",
            "calculated_supply_air_temperature_setpoint",
            "heating_pump_running",
            "cooling_pump_running",
        }
        actual_disabled = {
            entity["unique_id"]
            for entity in self.entities
            if entity.get("enabled_by_default") is False
        }
        self.assertEqual(actual_disabled, disabled)

    def test_existing_writable_controls_are_unchanged(self):
        controls = {entity["unique_id"]: entity for entity in self.data["controls"]}
        ventilation_level = controls["ventilation_level"]
        self.assertEqual(ventilation_level["address"], 2)
        self.assertEqual(ventilation_level["type"], "select")
        self.assertEqual(
            ventilation_level["translation_key"], "pichler_lg_es2020_ventilation_level"
        )
        self.assertEqual(ventilation_level["write_function_code"], 6)
        self.assertEqual(
            ventilation_level["options"],
            {
                0: "Standby",
                1: "Level 1",
                2: "Level 2",
                3: "Level 3",
                4: "Basic ventilation",
            },
        )
        for unique_id, address in (
            ("level_1_airflow_setpoint", 9),
            ("level_2_airflow_setpoint", 10),
            ("level_3_airflow_setpoint", 11),
            ("basic_ventilation_airflow_setpoint", 12),
        ):
            self.assertEqual(controls[unique_id]["type"], "number")
            self.assertEqual(controls[unique_id]["address"], address)
            self.assertEqual(controls[unique_id]["write_function_code"], 6)

    def test_controls_survive_each_post_heating_cooling_choice(self):
        """Equipment filtering may not remove unconditioned write controls."""
        expected_controls = {
            "ventilation_level",
            "level_1_airflow_setpoint",
            "level_2_airflow_setpoint",
            "level_3_airflow_setpoint",
            "basic_ventilation_airflow_setpoint",
        }
        for post_type in (CHILLED, COMBINED):
            with self.subTest(post_heating_cooling_type=post_type):
                controls = {
                    entity["unique_id"]
                    for entity in self.data["controls"]
                    if "condition" not in entity
                    or f"== '{post_type}'" in entity["condition"]
                }
                self.assertTrue(expected_controls <= controls)


if __name__ == "__main__":
    unittest.main()
