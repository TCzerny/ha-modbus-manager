"""Device category labels live in translations, not a Python en/de map."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "custom_components/modbus_manager/template_catalog.py"
TRANSLATIONS = ROOT / "custom_components/modbus_manager/translations"


def _load_catalog():
    spec = importlib.util.spec_from_file_location(
        "template_catalog_under_test", CATALOG
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Config:
    def __init__(self, language: str) -> None:
        self.language = language


class _Hass:
    def __init__(self, language: str) -> None:
        self.config = _Config(language)


class CategoryTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = _load_catalog()

    def test_every_language_has_the_same_category_options(self) -> None:
        keys = set(self.catalog.DEVICE_CATEGORIES) | {
            self.catalog.DEVICE_CATEGORY_GENERIC
        }
        for language in ("en", "de", "it"):
            data = json.loads(
                (TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")
            )
            options = data["selector"]["device_category"]["options"]
            self.assertEqual(set(options), keys)
            self.assertTrue(
                all(isinstance(label, str) and label for label in options.values())
            )

    def test_description_label_follows_ui_language(self) -> None:
        label = self.catalog.category_option_label
        self.assertEqual(label(_Hass("de"), "inverter"), "Wechselrichter")
        self.assertEqual(label(_Hass("it"), "generic"), "Dispositivo Modbus generico")
        self.assertEqual(label(_Hass("fr"), "heating"), "Heating")
        self.assertEqual(label(_Hass("en"), "missing"), "missing")

    def test_add_device_puts_generic_first(self) -> None:
        templates = {
            "sungrow": {"type": "PV_Hybrid_Inverter"},
            "meter": {"device_category": "energy_meter"},
        }
        keys = self.catalog.add_device_categories(templates)
        self.assertEqual(keys[0], "generic")
        self.assertIn("inverter", keys)
        self.assertIn("energy_meter", keys)
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
