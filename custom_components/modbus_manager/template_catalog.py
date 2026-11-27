"""Group YAML templates by device category for the setup picker.

Today the UI is two steps: category, then manufacturer — model. Grouping by
manufacturer is already here so a later third step (Discussion #118) can sit
between those without changing template identity or unique_id.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

_DOMAIN = "modbus_manager"


DEVICE_CATEGORY_INVERTER = "inverter"
DEVICE_CATEGORY_BATTERY = "battery"
DEVICE_CATEGORY_EV_CHARGER = "ev_charger"
DEVICE_CATEGORY_ENERGY_METER = "energy_meter"
DEVICE_CATEGORY_ENERGY_MANAGER = "energy_manager"
DEVICE_CATEGORY_VENTILATION = "ventilation"
DEVICE_CATEGORY_HEATING = "heating"
DEVICE_CATEGORY_OTHER = "other"
DEVICE_CATEGORY_GENERIC = "generic"

# Display order. Generic is Add-device only and is prepended by the caller.
DEVICE_CATEGORIES: tuple[str, ...] = (
    DEVICE_CATEGORY_INVERTER,
    DEVICE_CATEGORY_BATTERY,
    DEVICE_CATEGORY_EV_CHARGER,
    DEVICE_CATEGORY_ENERGY_METER,
    DEVICE_CATEGORY_ENERGY_MANAGER,
    DEVICE_CATEGORY_VENTILATION,
    DEVICE_CATEGORY_HEATING,
    DEVICE_CATEGORY_OTHER,
)


def _language_code(hass: Any | None) -> str:
    """UI language code passed to Home Assistant's translation cache."""
    language = str(getattr(getattr(hass, "config", None), "language", "en") or "en")
    return language.split("-", 1)[0].lower() or "en"


def category_option_translation_key(key: str) -> str:
    """Flat selector key for one device-category option."""
    return f"component.{_DOMAIN}.selector.device_category.options.{key}"


def category_label_from_translations(
    translations: Mapping[str, Any], key: str
) -> str | None:
    """Return one selector label, or None when that option is absent."""
    label = translations.get(category_option_translation_key(key))
    if isinstance(label, str) and label:
        return label
    return None


async def async_category_option_label(hass: Any, key: str) -> str:
    """Translated category name for ``{category}`` in step text.

    The dropdown uses the same selector key. Step text takes the label
    from Home Assistant's translation cache.
    """
    from homeassistant.helpers.translation import async_get_translations

    languages = [_language_code(hass)]
    if languages[0] != "en":
        languages.append("en")
    for language in languages:
        translations = await async_get_translations(
            hass, language, "selector", {_DOMAIN}
        )
        label = category_label_from_translations(translations, key)
        if label:
            return label
    return key


# YAML `type:` (case-insensitive) → discovery category.
_TYPE_TO_CATEGORY: dict[str, str] = {
    "pv_hybrid_inverter": DEVICE_CATEGORY_INVERTER,
    "pv_inverter": DEVICE_CATEGORY_INVERTER,
    "inverter": DEVICE_CATEGORY_INVERTER,
    "battery": DEVICE_CATEGORY_BATTERY,
    "ev_charger": DEVICE_CATEGORY_EV_CHARGER,
    "electricity_meter": DEVICE_CATEGORY_ENERGY_METER,
    "energy_meter": DEVICE_CATEGORY_ENERGY_METER,
    "energy_manager": DEVICE_CATEGORY_ENERGY_MANAGER,
    "ventilation": DEVICE_CATEGORY_VENTILATION,
    "heating_control": DEVICE_CATEGORY_HEATING,
    "heating": DEVICE_CATEGORY_HEATING,
}


def template_device_category(template_data: dict[str, Any] | None) -> str:
    """Return a stable discovery category for a YAML template dict."""
    data = template_data or {}
    explicit = str(data.get("device_category") or "").strip().lower()
    if explicit in DEVICE_CATEGORIES:
        return explicit
    raw_type = str(data.get("type") or "").strip().lower()
    return _TYPE_TO_CATEGORY.get(raw_type, DEVICE_CATEGORY_OTHER)


def template_manufacturer(template_data: dict[str, Any] | None) -> str:
    """Manufacturer string from YAML, or empty."""
    return str((template_data or {}).get("manufacturer") or "").strip()


def template_picker_label(template_data: dict[str, Any] | None, name: str) -> str:
    """Label for the model dropdown: Manufacturer — Model."""
    data = template_data or {}
    manufacturer = template_manufacturer(data)
    model = str(data.get("model") or "").strip()
    display = str(data.get("display_name") or "").strip()
    model_part = model or display or name
    if manufacturer and model_part:
        if manufacturer.lower() in model_part.lower():
            return model_part
        return f"{manufacturer} — {model_part}"
    return model_part


def present_categories(templates: dict[str, dict[str, Any]]) -> list[str]:
    """Categories that have at least one template, in display order."""
    found = {template_device_category(data) for data in templates.values()}
    return [key for key in DEVICE_CATEGORIES if key in found]


def add_device_categories(templates: dict[str, dict[str, Any]]) -> list[str]:
    """Generic first, then categories that have a YAML template."""
    keys = [DEVICE_CATEGORY_GENERIC]
    seen = set(keys)
    for key in present_categories(templates):
        if key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def templates_in_category(
    templates: dict[str, dict[str, Any]],
    category: str,
) -> dict[str, str]:
    """Template YAML name → picker label, sorted, for one category."""
    rows: list[tuple[str, str]] = []
    for name, data in templates.items():
        if template_device_category(data) != category:
            continue
        rows.append((name, template_picker_label(data, name)))
    rows.sort(key=lambda item: item[1].lower())
    return {name: label for name, label in rows}


def templates_by_manufacturer(
    templates: dict[str, dict[str, Any]],
    category: str,
) -> dict[str, dict[str, str]]:
    """Manufacturer → {template name: label} for a later third picker step."""
    grouped: dict[str, dict[str, str]] = defaultdict(dict)
    for name, label in templates_in_category(templates, category).items():
        manufacturer = template_manufacturer(templates.get(name) or {}) or "Other"
        grouped[manufacturer][name] = label
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))
