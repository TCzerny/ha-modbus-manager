"""Contract tests for shared template entity display handling.

The lightweight repository test environment does not install Home Assistant.
The tests compile and execute the production helper itself, rather than
reimplementing its branching logic in a fake helper.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEVICE_UTILS = ROOT / "custom_components/modbus_manager/device_utils.py"
PLATFORMS = (
    "sensor.py",
    "binary_sensor.py",
    "number.py",
    "select.py",
    "switch.py",
    "button.py",
    "text.py",
    "calculated.py",
)


def _load_display_helper():
    """Load the production helper without importing Home Assistant."""
    tree = ast.parse(DEVICE_UTILS.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {"template_enabled_by_default", "apply_template_entity_display"}
    ]
    namespace = {"Any": Any}
    exec(
        compile(ast.Module(functions, type_ignores=[]), str(DEVICE_UTILS), "exec"),
        namespace,
    )
    return namespace["apply_template_entity_display"]


class _Entity:
    """Minimal attribute carrier for exercising the production helper."""


class _EntityWithClassName:
    """Carrier that models an Entity class-level default attribute."""

    _attr_name = "class-level default"


class TemplateEntityDisplayContractTest(unittest.TestCase):
    """Guard the Home Assistant entity-name translation contract."""

    @classmethod
    def setUpClass(cls):
        cls.apply_display = staticmethod(_load_display_helper())

    def test_keyed_entity_reaches_translation_lookup(self):
        entity = _Entity()
        entity._attr_name = "stale name"

        self.apply_display(
            entity,
            {"translation_key": "example_temperature"},
            fallback_name="English fallback",
        )

        self.assertTrue(entity._attr_has_entity_name)
        self.assertEqual(entity._attr_translation_key, "example_temperature")
        self.assertFalse(hasattr(entity, "_attr_name"))

    def test_keyed_entity_removes_only_an_instance_name(self):
        entity = _EntityWithClassName()
        entity._attr_name = "stale instance name"

        self.apply_display(
            entity,
            {"translation_key": "example_temperature"},
            fallback_name="English fallback",
        )

        self.assertNotIn("_attr_name", vars(entity))
        self.assertEqual(_EntityWithClassName._attr_name, "class-level default")

    def test_unkeyed_entity_keeps_its_explicit_yaml_name(self):
        entity = _Entity()

        self.apply_display(entity, {}, fallback_name="English fallback")

        self.assertTrue(entity._attr_has_entity_name)
        self.assertFalse(hasattr(entity, "_attr_translation_key"))
        self.assertEqual(entity._attr_name, "English fallback")

    def test_all_template_platforms_use_the_shared_helper(self):
        component = ROOT / "custom_components/modbus_manager"
        for filename in PLATFORMS:
            with self.subTest(platform=filename):
                source = (component / filename).read_text(encoding="utf-8")
                self.assertIn("apply_template_entity_display(", source)
                self.assertIn("_attr_has_entity_name = True", source)

    def test_select_never_reads_attr_name_after_display_helper(self):
        """Translated selects must not depend on the intentionally absent name."""
        select_source = (
            ROOT / "custom_components/modbus_manager/select.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(select_source)
        attr_name_reads = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr == "_attr_name"
        ]
        self.assertEqual(attr_name_reads, [])
        self.assertIn("self._log_label", select_source)


if __name__ == "__main__":
    unittest.main()
