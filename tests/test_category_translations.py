"""Device category labels live in translations, not a Python en/de map."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
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

    def test_shipped_category_labels(self) -> None:
        de = json.loads((TRANSLATIONS / "de.json").read_text(encoding="utf-8"))
        it = json.loads((TRANSLATIONS / "it.json").read_text(encoding="utf-8"))
        en = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
        self.assertEqual(
            de["selector"]["device_category"]["options"]["inverter"],
            "Wechselrichter",
        )
        self.assertEqual(
            it["selector"]["device_category"]["options"]["generic"],
            "Dispositivo Modbus generico",
        )
        self.assertEqual(
            en["selector"]["device_category"]["options"]["heating"],
            "Heating",
        )

    def test_description_label_uses_translation_cache(self) -> None:
        calls: list[tuple[str, str, set[str]]] = []

        async def fake_get_translations(hass, language, category, integrations):
            calls.append((language, category, set(integrations)))
            if language == "de":
                return {
                    self.catalog.category_option_translation_key(
                        "inverter"
                    ): "Wechselrichter"
                }
            if language == "en":
                return {
                    self.catalog.category_option_translation_key("heating"): "Heating"
                }
            return {}

        helpers = types.ModuleType("homeassistant.helpers")
        translation = types.ModuleType("homeassistant.helpers.translation")
        translation.async_get_translations = fake_get_translations
        saved = {
            name: sys.modules.get(name)
            for name in (
                "homeassistant.helpers",
                "homeassistant.helpers.translation",
            )
        }
        sys.modules["homeassistant.helpers"] = helpers
        sys.modules["homeassistant.helpers.translation"] = translation
        try:
            label = asyncio.run(
                self.catalog.async_category_option_label(_Hass("de"), "inverter")
            )
            self.assertEqual(label, "Wechselrichter")
            self.assertEqual(calls, [("de", "selector", {"modbus_manager"})])

            calls.clear()
            label = asyncio.run(
                self.catalog.async_category_option_label(_Hass("fr"), "heating")
            )
            self.assertEqual(label, "Heating")
            self.assertEqual(
                calls,
                [
                    ("fr", "selector", {"modbus_manager"}),
                    ("en", "selector", {"modbus_manager"}),
                ],
            )

            calls.clear()
            label = asyncio.run(
                self.catalog.async_category_option_label(_Hass("en"), "missing")
            )
            self.assertEqual(label, "missing")
            self.assertEqual(calls, [("en", "selector", {"modbus_manager"})])
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

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
