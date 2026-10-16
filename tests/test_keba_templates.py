"""KEBA register, transaction and calculated-state contracts without HA installed."""

from __future__ import annotations

import ast
import asyncio
import copy
import json
import logging
import os
import re
import struct
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment
from packaging import version

from test_register_optimizer import ranges
from test_scan_groups import normalize_scan_group  # Loads production constants.

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/modbus_manager"
COMMON_ADDRESSES = {
    "charging_state_raw": 1000,
    "cable_state_raw": 1004,
    "error_code": 1006,
    "current_l1": 1008,
    "current_l2": 1010,
    "current_l3": 1012,
    "serial_number": 1014,
    "product_type_and_features": 1016,
    "firmware_version_raw": 1018,
    "active_power": 1020,
    "total_energy": 1036,
    "voltage_l1": 1040,
    "voltage_l2": 1042,
    "voltage_l3": 1044,
    "power_factor": 1046,
    "maximum_charging_current": 1100,
    "supported_charging_current": 1110,
    "rfid_card_raw": 1500,
    "session_energy": 1502,
}
P40_ADDRESSES = {
    "fast_charging_status": 1200,
    "phase_switching_source": 1550,
    "phase_switching_state": 1552,
    "failsafe_current_setting": 1600,
    "failsafe_timeout_setting": 1602,
    "hardware_revision_device": 1700,
    "hardware_revision_ms10": 1702,
}


def load_production_definitions(filename, namespace, names=None, assignments=()):
    """Execute actual helper bodies, excluding HA imports and unrelated code."""
    tree = ast.parse((COMPONENT / filename).read_text(encoding="utf-8"))
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if names is None or node.name in names:
                selected.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in assignments
            for target in node.targets
        ):
            selected.append(node)
    source = ast.Module(selected, type_ignores=[])
    exec(compile(source, filename, "exec"), namespace)
    return namespace


def production_namespace():
    from modbus_manager.scan_groups import annotate_register_scan_timing

    namespace = dict(vars(sys.modules["modbus_manager.const"]))
    namespace.update(
        _LOGGER=logging.getLogger("keba_contract"),
        asyncio=asyncio,
        os=os,
        re=re,
        struct=struct,
        yaml=yaml,
        copy=copy,
        version=version,
        annotate_register_scan_timing=annotate_register_scan_timing,
        _template_cache={},
        _cache_file_mtimes={},
        _template_name_to_path={},
        _template_name_to_stem={},
    )
    load_production_definitions(
        "modbus_utils.py",
        namespace,
        {
            "is_valid_modbus_address",
            "_normalize_byte_order",
            "_is_word_swap_enabled",
            "registers_to_bytes",
        },
    )
    load_production_definitions(
        "template_loader.py",
        namespace,
        {
            "load_single_template",
            "_read_template_file",
            "_get_file_mtime",
            "_is_cache_valid",
            "_register_template_name_stem",
            "validate_and_process_register",
            "validate_register_data",
            "validate_control_settings",
            "determine_entity_type",
            "_evaluate_condition",
            "_evaluate_single_condition",
        },
        {"REQUIRED_FIELDS", "OPTIONAL_FIELDS"},
    )
    load_production_definitions(
        "device_utils.py",
        namespace,
        {
            "_parse_version_loose",
            "find_applicable_version",
            "collect_version_replacements",
            "apply_version_replacements",
            "resolve_firmware_profile_version",
            "entity_allowed_for_protocol",
        },
    )
    load_production_definitions(
        "dynamic_processing.py",
        namespace,
        {
            "migrate_legacy_battery_enabled",
            "resolve_battery_config_value",
            "process_dynamic_config",
            "_should_include_sensor",
            "_apply_firmware_modifications",
        },
    )
    load_production_definitions(
        "sensor.py", namespace, {"should_suppress_spurious_total_zero"}
    )
    load_production_definitions("value_processor.py", namespace)
    tree = ast.parse((COMPONENT / "coordinator.py").read_text(encoding="utf-8"))
    methods = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_process_register_value", "_extract_config_from_model"}
    ]
    exec(
        compile(ast.Module(methods, type_ignores=[]), "coordinator.py", "exec"),
        namespace,
    )
    return namespace


class KebaTemplatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.production = production_namespace()
        cls.templates = {
            model: yaml.safe_load(
                (COMPONENT / "device_templates" / f"keba_kecontact_{model}.yaml")
                .read_text(encoding="utf-8")
            )
            for model in ("p30", "p40")
        }

    def entity(self, model, unique_id):
        return next(
            entity
            for section in ("sensors", "calculated", "binary_sensors")
            for entity in self.templates[model][section]
            if entity["unique_id"] == unique_id
        )

    def render(self, model, unique_id, values, field="state"):
        environment = NativeEnvironment(undefined=StrictUndefined)
        environment.filters["is_number"] = lambda value: str(value).isdecimal()
        environment.globals["states"] = lambda marker: values.get(
            re.fullmatch(r"\[\[mm:sensor:\{PREFIX\}_(.+)\]\]", marker).group(1),
            "unavailable",
        )
        return environment.from_string(self.entity(model, unique_id)[field]).render()

    def translations(self, language):
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                self.assertNotIn(key, result, f"Duplicate {language} JSON key: {key}")
                result[key] = value
            return result

        return json.loads(
            (COMPONENT / "translations" / f"{language}.json").read_text(encoding="utf-8"),
            object_pairs_hook=unique_keys,
        )

    def test_localized_names_are_complete_shared_and_not_orphaned(self):
        for language in ("en", "de"):
            translations = self.translations(language)["entity"]
            expected = {"sensor": set(), "binary_sensor": set()}
            for model, template in self.templates.items():
                for section in ("sensors", "calculated", "binary_sensors"):
                    domain = "binary_sensor" if section == "binary_sensors" else "sensor"
                    for entity in template[section]:
                        with self.subTest(language=language, model=model, uid=entity["unique_id"]):
                            key = entity["translation_key"]
                            self.assertEqual(key, f"keba_{entity['unique_id']}")
                            self.assertTrue(translations[domain][key]["name"].strip())
                            expected[domain].add(key)
            for domain, keys in expected.items():
                self.assertEqual(
                    {key for key in translations[domain] if key.startswith("keba_")},
                    keys,
                )

    def test_localized_states_cover_exact_runtime_values_without_orphans(self):
        expected = {}
        for model, template in self.templates.items():
            for entity in template["sensors"]:
                if "map" in entity:
                    expected.setdefault(entity["translation_key"], set()).update(
                        entity["map"].values()
                    )
            for code in range(6):
                expected.setdefault("keba_charging_state", set()).add(
                    self.render(model, "charging_state", {"charging_state_raw": str(code)})
                )
            for product in ("4212311", "4222311"):
                for code in (0, 1, 3, 5, 7):
                    expected.setdefault("keba_cable_state", set()).add(
                        self.render(model, "cable_state", {
                            "cable_state_raw": str(code),
                            "product_type_and_features": product,
                        }).strip()
                    )
        for language in ("en", "de"):
            translations = self.translations(language)["entity"]
            actual = {
                key: set(value["state"])
                for key, value in translations["sensor"].items()
                if key.startswith("keba_") and "state" in value
            }
            self.assertEqual(actual, expected)
            for domain in ("sensor", "binary_sensor"):
                for key, value in translations[domain].items():
                    if not key.startswith("keba_"):
                        continue
                    if domain == "binary_sensor":
                        self.assertEqual(set(value["state"]), {"on", "off"})
                    for label in value.get("state", {}).values():
                        self.assertTrue(label.strip())

    def test_localized_configuration_fields_match_template_options(self):
        paths = (
            ("config", "dynamic_config"),
            ("options", "device"),
            ("config_subentries", "user"),
            ("config_subentries", "reconfigure"),
        )
        fields = {"connector_type", "rfid", "phase_switching_registers"}
        for language in ("en", "de"):
            translations = self.translations(language)
            for section, step in paths:
                labels = translations[section]["step"][step]["data"]
                for field in fields:
                    self.assertIn(field, self.templates["p40"]["dynamic_config"])
                    self.assertTrue(labels[field].strip())

    def test_empty_valid_model_override_uses_defaults_without_warning(self):
        process = self.production["process_dynamic_config"]
        logger = self.production["_LOGGER"]
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _Capture(level=logging.WARNING)
        logger.addHandler(handler)
        try:
            result = process(
                {"selected_model": "KeContact P30 c-series"},
                deepcopy(self.templates["p30"]),
            )
        finally:
            logger.removeHandler(handler)

        self.assertEqual(
            [
                record.getMessage()
                for record in records
                if "Model config not found" in record.getMessage()
            ],
            [],
        )
        self.assertEqual(
            result["config_values"]["selected_model"], "KeContact P30 c-series"
        )
        self.assertEqual(result["config_values"]["phases"], 3)
        self.assertEqual(
            result["config_values"]["dynamic_config"]["selected_model"],
            "KeContact P30 c-series",
        )

    def test_coordinator_accepts_existing_model_with_empty_config(self):
        template = deepcopy(self.templates["p30"])
        loader = AsyncMock(return_value=template)
        with patch.dict(self.production, get_template_by_name=loader):
            with self.assertNoLogs(self.production["_LOGGER"], level="WARNING"):
                result = asyncio.run(self.production["_extract_config_from_model"](
                    None, "KeContact P30 c-series", template["name"]
                ))
        self.assertEqual(result, {})
        loader.assert_awaited_once_with(template["name"])

    def test_coordinator_preserves_existing_populated_model_config(self):
        template = deepcopy(self.templates["p30"])
        model_config = {"phases": 3, "max_charge_power": 22000}
        template["dynamic_config"]["valid_models"]["KeContact P30 c-series"] = model_config
        loader = AsyncMock(return_value=template)
        with patch.dict(self.production, get_template_by_name=loader):
            with self.assertNoLogs(self.production["_LOGGER"], level="WARNING"):
                result = asyncio.run(self.production["_extract_config_from_model"](
                    None, "KeContact P30 c-series", template["name"]
                ))
        self.assertEqual(result, model_config)
        self.assertIsNot(result, model_config)
        loader.assert_awaited_once_with(template["name"])

    def test_coordinator_warns_for_missing_model(self):
        template = deepcopy(self.templates["p30"])
        loader = AsyncMock(return_value=template)
        with patch.dict(self.production, get_template_by_name=loader):
            with self.assertLogs(self.production["_LOGGER"], level="WARNING") as logs:
                result = asyncio.run(self.production["_extract_config_from_model"](
                    None, "Unknown KEBA model", template["name"]
                ))
        self.assertEqual(result, {})
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(
            logs.records[0].getMessage(),
            "Selected model Unknown KEBA model not found in valid_models "
            "for template KEBA KeContact P30",
        )
        loader.assert_awaited_once_with(template["name"])

    def test_actual_loader_accepts_every_sensor(self):
        for model, template in self.templates.items():
            path = COMPONENT / "device_templates" / f"keba_kecontact_{model}.yaml"
            loaded = asyncio.run(self.production["load_single_template"](str(path)))
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded["sensors"]), len(template["sensors"]))
            self.assertEqual(loaded["controls"], [])
            self.assertEqual(loaded["default_slave_id"], 255)
            for sensor in loaded["sensors"]:
                self.assertEqual(sensor["translation_key"], f"keba_{sensor['unique_id']}")
                self.assertEqual(sensor["entity_type"], "sensor")
                self.assertEqual(sensor["scan_group"], normalize_scan_group(sensor))

    def test_exact_register_map_and_wire_contract(self):
        for model, template in self.templates.items():
            expected = COMMON_ADDRESSES | (P40_ADDRESSES if model == "p40" else {})
            self.assertEqual(
                {item["unique_id"]: item["address"] for item in template["sensors"]},
                expected,
            )
            for sensor in template["sensors"]:
                with self.subTest(model=model, sensor=sensor["unique_id"]):
                    self.assertEqual(sensor["input_type"], "holding")
                    self.assertEqual(sensor["read_function_code"], 3)
                    self.assertEqual(sensor["data_type"], "uint32")
                    self.assertEqual(sensor["count"], 2)
                    self.assertEqual(sensor["byte_order"], "big")
                    self.assertEqual(sensor["swap"], "none")
                    self.assertNotIn("write_function_code", sensor)
                    self.assertLess(sensor["address"], 5000)

    def test_optimizer_never_merges_documented_values(self):
        for template in self.templates.values():
            sensors = deepcopy(template["sensors"])
            actual = ranges(sensors)
            expected = sorted(
                (item["address"], item["address"] + 1, 2) for item in sensors
            )
            self.assertEqual(actual, expected)
            self.assertTrue(all(count == 2 for _, _, count in actual))

    def test_entity_ids_and_registry_references(self):
        generated = []
        for template in self.templates.values():
            entities = sum(
                (template[section] for section in
                 ("sensors", "calculated", "binary_sensors")),
                [],
            )
            ids = [item["unique_id"] for item in entities]
            self.assertEqual(len(ids), len(set(ids)))
            generated.extend(f"{template['default_prefix']}_{uid}" for uid in ids)
            source_ids = {item["unique_id"] for item in template["sensors"]}
            for entity in entities:
                for field in ("state", "availability"):
                    text = entity.get(field, "")
                    refs = re.findall(r"\[\[mm:sensor:\{PREFIX\}_(.+?)\]\]", text)
                    self.assertTrue(set(refs) <= source_ids)
                    if field == "state" and text:
                        self.assertTrue(entity.get("availability"))
        self.assertEqual(len(generated), len(set(generated)))

    def test_conditions_exclude_optional_registers_by_default(self):
        evaluate = self.production["_evaluate_condition"]
        for model, template in self.templates.items():
            defaults = {
                key: value["default"]
                for key, value in template["dynamic_config"].items()
                if "default" in value
            }
            for uid in ("rfid_card_raw", "rfid_uid_prefix", "plug_locked"):
                condition = self.entity(model, uid)["condition"]
                self.assertFalse(evaluate(condition, defaults))
            self.assertTrue(evaluate(
                self.entity(model, "plug_locked")["condition"],
                defaults | {"connector_type": "socket"},
            ))
            for uid in ("rfid_card_raw", "rfid_uid_prefix"):
                self.assertTrue(evaluate(
                    self.entity(model, uid)["condition"],
                    defaults | {"rfid": "enabled"},
                ))
        for uid in ("phase_switching_source", "phase_switching_state"):
            condition = self.entity("p40", uid)["condition"]
            self.assertFalse(evaluate(condition, {"phase_switching_registers": "unavailable"}))
            self.assertTrue(evaluate(condition, {"phase_switching_registers": "confirmed"}))

    def test_real_uint32_decoding_and_documented_measurements(self):
        decode = self.production["_process_register_value"]
        examples = (
            ("current_l1", 645, 0.645),
            ("current_l2", 1011, 1.011),
            ("active_power", 98661, 98.661),
            ("voltage_l1", 230, 230),
            ("power_factor", 928, 92.8),
            ("maximum_charging_current", 10000, 10),
            ("serial_number", 18416854, 18416854),
        )
        for model in self.templates:
            for uid, raw, expected in examples:
                with self.subTest(model=model, uid=uid):
                    actual = decode(None, [raw >> 16, raw & 65535], self.entity(model, uid))
                    self.assertAlmostEqual(actual, expected)

    def test_energy_firmware_boundary_and_statistics(self):
        apply = self.production["apply_version_replacements"]
        replacements = self.production["collect_version_replacements"](
            self.templates["p40"]["dynamic_config"]
        )
        process = self.production["process_register_value"]
        for uid, raw in (("total_energy", 38101), ("session_energy", 165)):
            self.assertAlmostEqual(
                process(raw, self.entity("p30", uid)), raw * 0.001
            )
            for firmware, scale in (
                ("1.0.0", 0.001), ("1.2.0", 0.001),
                ("1.2.1", 0.0001), ("1.3.0", 0.0001),
            ):
                entity = apply(self.entity("p40", uid), firmware, replacements)
                self.assertAlmostEqual(process(raw, entity), raw * scale)
            for model in self.templates:
                entity = self.entity(model, uid)
                self.assertEqual(entity["device_class"], "energy")
                self.assertEqual(entity["unit_of_measurement"], "kWh")
                self.assertEqual(entity["state_class"], "total_increasing")

    def test_p40_stored_profile_normalization_and_final_scaling(self):
        """Exercise the coordinator's normalization-before-replacement order."""
        template = self.templates["p40"]
        resolve = self.production["resolve_firmware_profile_version"]
        apply = self.production["apply_version_replacements"]
        replacements = self.production["collect_version_replacements"](
            template["dynamic_config"]
        )
        decode = self.production["_process_register_value"]
        # Stored value -> normalized profile -> raw-to-kWh scale and precision.
        cases = (
            ("1.0.0", "1.0.0", 0.001, 3),
            ("1.2.0", "1.2.1", 0.0001, 4),
            ("1.2.1", "1.2.1", 0.0001, 4),
            ("1.3.0", "1.2.1", 0.0001, 4),
            (None, "1.2.1", 0.0001, 4),
        )
        for stored, expected_profile, scale, precision in cases:
            with self.subTest(stored=stored, profile=expected_profile, scale=scale):
                profile = resolve(stored, template)
                self.assertEqual(profile, expected_profile)
                for uid, raw in (("total_energy", 38101), ("session_energy", 165)):
                    with self.subTest(entity=uid):
                        entity = apply(self.entity("p40", uid), profile, replacements)
                        self.assertEqual(entity["scale"], scale)
                        self.assertEqual(entity["precision"], precision)
                        self.assertEqual(entity["state_class"], "total_increasing")
                        actual = decode(None, [raw >> 16, raw & 65535], entity)
                        self.assertAlmostEqual(actual, raw * scale)

    def test_session_energy_reset_is_not_suppressed(self):
        """Session resets are valid zero readings, not negative consumption."""
        decode = self.production["_process_register_value"]
        suppress = self.production["should_suppress_spurious_total_zero"]
        for model in self.templates:
            with self.subTest(model=model):
                entity = self.entity(model, "session_energy")
                self.assertEqual(entity["state_class"], "total_increasing")
                self.assertNotIn("last_reset", entity)
                scale = entity["scale"]
                raw_values = (10000, 12000, 0, 1000)
                values = [
                    decode(None, [raw >> 16, raw & 65535], entity)
                    for raw in raw_values
                ]
                for actual, raw in zip(values, raw_values):
                    self.assertAlmostEqual(actual, raw * scale)
                self.assertFalse(
                    suppress(entity["state_class"], values[2], values[1])
                )

    def test_plug_lock_and_vehicle_truth_table(self):
        for model in self.templates:
            self.assertNotIn("device_class", self.entity(model, "plug_locked"))
            for code in (0, 1, 3, 5, 7):
                values = {"cable_state_raw": str(code)}
                self.assertTrue(self.render(model, "plug_locked", values, "availability"))
                self.assertEqual(self.render(model, "plug_locked", values), code in (3, 7))
                self.assertEqual(
                    self.render(model, "vehicle_connected", values), code in (5, 7)
                )

    def test_charging_and_error_are_not_inferred_from_stale_error_code(self):
        for model in self.templates:
            for code in range(6):
                values = {"charging_state_raw": str(code), "error_code": "99"}
                self.assertEqual(
                    self.render(model, "charging_active", values), code == 3
                )
                self.assertEqual(
                    self.render(model, "error_present", values), code == 4
                )
                self.assertTrue(self.render(model, "charging_state", values, "availability"))
                self.assertIsInstance(self.render(model, "charging_state", values), str)

    def test_unavailable_and_unknown_codes_do_not_become_false_healthy_states(self):
        for model, template in self.templates.items():
            for entity in template["binary_sensors"] + template["calculated"]:
                uid = entity["unique_id"]
                self.assertFalse(self.render(model, uid, {}, "availability"))
                for invalid in ("unknown", "unavailable", "999", "-1"):
                    values = {"charging_state_raw": invalid, "cable_state_raw": invalid}
                    self.assertFalse(self.render(model, uid, values, "availability"))

    def test_p40_firmware_rfid_and_attached_cable(self):
        self.assertEqual(
            self.render("p40", "firmware_version", {"firmware_version_raw": "10000"}),
            "1.0.0",
        )
        self.assertEqual(
            self.render("p40", "firmware_version", {"firmware_version_raw": "10201"}),
            "1.2.1",
        )
        for model in self.templates:
            self.assertEqual(
                self.render(model, "rfid_uid_prefix", {"rfid_card_raw": "3570234960"}),
                "D4CD7650",
            )
            self.assertFalse(self.render(
                model, "rfid_uid_prefix", {"rfid_card_raw": "0"}, "availability"
            ))
        for code, expected in ((3, "Station connected"), (7, "Vehicle connected")):
            self.assertEqual(
                self.render("p40", "cable_state", {
                    "cable_state_raw": str(code), "product_type_and_features": "4212311"
                }).strip(),
                expected,
            )

    def test_p30_ambiguous_firmware_is_raw_and_opt_in(self):
        self.assertFalse(
            self.entity("p30", "firmware_version_raw")["enabled_by_default"]
        )
        self.assertNotIn(
            "firmware_version",
            {item["unique_id"] for item in self.templates["p30"]["calculated"]},
        )


if __name__ == "__main__":
    unittest.main()
