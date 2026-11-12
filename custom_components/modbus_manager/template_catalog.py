"""Group YAML templates by device category for the setup picker.

Today the UI is two steps: category, then manufacturer — model. Grouping by
manufacturer is already here so a later third step (Discussion #118) can sit
between those without changing template identity or unique_id.
"""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

_TRANSLATIONS = Path(__file__).parent / "translations"


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
    """UI language code. Any shipped translations file can match."""
    language = str(getattr(getattr(hass, "config", None), "language", "en") or "en")
    return language.split("-", 1)[0].lower()


@lru_cache(maxsize=8)
def _category_option_labels(language: str) -> dict[str, str]:
    """Labels from translations/<language>.json selector.device_category."""
    path = _TRANSLATIONS / f"{language}.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    raw = data.get("selector", {}).get("device_category", {}).get("options", {})
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(label) for key, label in raw.items() if isinstance(label, str)
    }


def category_option_label(hass: Any | None, key: str) -> str:
    """Translated category name for a description placeholder.

    The dropdown itself is translated by Home Assistant from the same
    selector key. This lookup is only for ``{category}`` in step text.
    """
    for language in (_language_code(hass), "en"):
        label = _category_option_labels(language).get(key)
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
