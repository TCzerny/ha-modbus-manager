"""Group YAML templates by device category for the setup picker.

Today the UI is two steps: category, then manufacturer — model. Grouping by
manufacturer is already here so a later third step (Discussion #118) can sit
between those without changing template identity or unique_id.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _ui_language(hass: Any | None) -> str:
    """Home Assistant UI language, limited to catalogs we ship (en/de)."""
    language = str(getattr(getattr(hass, "config", None), "language", "en") or "en")
    language = language.split("-", 1)[0].lower()
    if language not in ("de", "en"):
        return "en"
    return language


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

DEVICE_CATEGORY_LABELS = {
    "en": {
        DEVICE_CATEGORY_INVERTER: "Inverter",
        DEVICE_CATEGORY_BATTERY: "Battery storage",
        DEVICE_CATEGORY_EV_CHARGER: "EV charger",
        DEVICE_CATEGORY_ENERGY_METER: "Energy meter",
        DEVICE_CATEGORY_ENERGY_MANAGER: "Energy manager",
        DEVICE_CATEGORY_VENTILATION: "Ventilation",
        DEVICE_CATEGORY_HEATING: "Heating",
        DEVICE_CATEGORY_OTHER: "Other",
        DEVICE_CATEGORY_GENERIC: "Generic Modbus Device",
    },
    "de": {
        DEVICE_CATEGORY_INVERTER: "Wechselrichter",
        DEVICE_CATEGORY_BATTERY: "Batteriespeicher",
        DEVICE_CATEGORY_EV_CHARGER: "Wallbox / EV-Ladegerät",
        DEVICE_CATEGORY_ENERGY_METER: "Energiezähler",
        DEVICE_CATEGORY_ENERGY_MANAGER: "Energy Manager",
        DEVICE_CATEGORY_VENTILATION: "Lüftung",
        DEVICE_CATEGORY_HEATING: "Heizung",
        DEVICE_CATEGORY_OTHER: "Sonstiges",
        DEVICE_CATEGORY_GENERIC: "Generisches Modbus-Gerät",
    },
}

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


def category_labels(
    hass: Any | None,
    categories: list[str],
) -> dict[str, str]:
    """vol.In mapping of category key → UI label (en/de)."""
    language = _ui_language(hass)
    catalog = DEVICE_CATEGORY_LABELS.get(language) or DEVICE_CATEGORY_LABELS["en"]
    return {key: catalog.get(key, key) for key in categories}


def present_categories(templates: dict[str, dict[str, Any]]) -> list[str]:
    """Categories that have at least one template, in display order."""
    found = {template_device_category(data) for data in templates.values()}
    return [key for key in DEVICE_CATEGORIES if key in found]


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
