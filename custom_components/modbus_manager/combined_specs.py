"""Central specs for cross-hub combined device behavior."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .device_utils import entry_device_type_set

# Supported source type combinations
# Normalized source type set -> combination type id
COMBINATION_TYPE_SPECS: dict[frozenset[str], str] = {
    frozenset({"inverter"}): "inverter_inverter",
    frozenset({"inverter", "energy_manager"}): "inverter_ihm",
}


def resolve_combination_type(
    source_a: ConfigEntry | None,
    source_b: ConfigEntry | None,
) -> str | None:
    """Resolve supported combination type from two hub entries."""
    if source_a is None or source_b is None:
        return None
    pair_key = entry_device_type_set(source_a) | entry_device_type_set(source_b)
    return COMBINATION_TYPE_SPECS.get(frozenset(pair_key))


def combination_type_for_entry(
    hass: HomeAssistant, combined_entry: ConfigEntry
) -> str | None:
    """Resolve combination type from source hubs; sync config entry when corrected."""
    source_a_id = combined_entry.data.get("source_entry_id_a")
    source_b_id = combined_entry.data.get("source_entry_id_b")
    source_a = hass.config_entries.async_get_entry(source_a_id) if source_a_id else None
    source_b = hass.config_entries.async_get_entry(source_b_id) if source_b_id else None
    resolved = resolve_combination_type(source_a, source_b)
    stored = combined_entry.data.get("combination_type")
    if resolved and resolved != stored:
        hass.config_entries.async_update_entry(
            combined_entry,
            data={**combined_entry.data, "combination_type": resolved},
        )
    return resolved or stored


# Role names used in metric specs (resolved from config entry device types).
SOURCE_ROLE_INVERTER = "inverter"
SOURCE_ROLE_IHM = "ihm"

# SHx/SG + iHM consumed-energy balance (see GitHub issue #50).
# Total: grid import/export from iHM (GRID.CT); PV/battery from inverter.
_CONSUMED_FORMULA = "pv - export + import - battery_charge + battery_discharge"

_DAILY_CONSUMED_OPERANDS: dict[str, dict[str, Any]] = {
    "pv": {
        "source": SOURCE_ROLE_INVERTER,
        "candidates": ["daily_pv_generation"],
    },
    # Daily grid from persistent iHM total counters (utility_meter equivalent).
    "export": {
        "source": SOURCE_ROLE_IHM,
        "candidates": ["grid_export_energy"],
        "use_daily_meter": True,
        "daily_meter_key": "export",
    },
    "import": {
        "source": SOURCE_ROLE_IHM,
        "candidates": ["grid_import_energy"],
        "use_daily_meter": True,
        "daily_meter_key": "import",
    },
    "battery_charge": {
        "source": SOURCE_ROLE_INVERTER,
        "candidates": ["daily_battery_charge"],
    },
    "battery_discharge": {
        "source": SOURCE_ROLE_INVERTER,
        "candidates": ["daily_battery_discharge"],
    },
}

_TOTAL_CONSUMED_OPERANDS: dict[str, dict[str, Any]] = {
    "pv": {
        "source": SOURCE_ROLE_INVERTER,
        "candidates": ["total_pv_generation"],
    },
    "export": {
        "source": SOURCE_ROLE_IHM,
        "candidates": ["grid_export_energy"],
    },
    "import": {
        "source": SOURCE_ROLE_IHM,
        "candidates": ["grid_import_energy"],
    },
    "battery_charge": {
        "source": SOURCE_ROLE_INVERTER,
        "candidates": ["total_battery_charge"],
    },
    "battery_discharge": {
        "source": SOURCE_ROLE_INVERTER,
        "candidates": ["total_battery_discharge"],
    },
}

# Numeric sensor metrics per combination type.
COMBINED_SENSOR_METRIC_SPECS: dict[str, dict[str, dict[str, Any]]] = {
    "inverter_inverter": {
        "combined_total_active_power": {
            "name": "Combined Total Active Power",
            "source_candidates": [
                "total_active_power",
                "active_power",
                "meter_active_power",
            ],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_total_dc_power": {
            "name": "Combined Total DC Power",
            "source_candidates": ["total_dc_power"],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_daily_pv_generation": {
            "name": "Combined Daily PV Generation",
            "source_candidates": ["daily_pv_generation"],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_total_pv_generation": {
            "name": "Combined Total PV Generation",
            "source_candidates": [
                "total_pv_generation",
                "pv_power_total",
                "pv_total_power",
            ],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_daily_exported_energy": {
            "name": "Combined Daily Exported Energy",
            "source_candidates": ["daily_exported_energy"],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_total_exported_energy": {
            "name": "Combined Total Exported Energy",
            "source_candidates": ["total_exported_energy"],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_daily_imported_energy": {
            "name": "Combined Daily Imported Energy",
            "source_candidates": ["daily_imported_energy"],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_total_imported_energy": {
            "name": "Combined Total Imported Energy",
            "source_candidates": ["total_imported_energy"],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_daily_direct_energy_consumption": {
            "name": "Combined Daily Direct Energy Consumption",
            "source_candidates": ["daily_direct_energy_consumption"],
            "aggregation": "sum",
            "required_sources": "both",
        },
        "combined_inverter_temperature_max": {
            "name": "Combined Inverter Temperature Max",
            "source_candidates": ["inverter_temperature"],
            "aggregation": "max",
            "required_sources": "any",
        },
        "combined_grid_frequency_avg": {
            "name": "Combined Grid Frequency Avg",
            "source_candidates": ["grid_frequency"],
            "aggregation": "avg",
            "required_sources": "any",
        },
    },
    "inverter_ihm": {
        # --- Inverter (SH/SG): production and battery ---
        "combined_inverter_total_active_power": {
            "name": "Inverter Total Active Power",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["total_active_power"],
            "aggregation": "single",
        },
        "combined_inverter_total_dc_power": {
            "name": "Inverter Total DC Power",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["total_dc_power"],
            "aggregation": "single",
        },
        "combined_inverter_daily_pv_generation": {
            "name": "Inverter Daily PV Generation",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["daily_pv_generation"],
            "aggregation": "single",
        },
        "combined_inverter_total_pv_generation": {
            "name": "Inverter Total PV Generation",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["total_pv_generation"],
            "aggregation": "single",
        },
        "combined_inverter_daily_battery_charge": {
            "name": "Inverter Daily Battery Charge",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["daily_battery_charge"],
            "aggregation": "single",
        },
        "combined_inverter_daily_battery_discharge": {
            "name": "Inverter Daily Battery Discharge",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["daily_battery_discharge"],
            "aggregation": "single",
        },
        "combined_inverter_total_battery_charge": {
            "name": "Inverter Total Battery Charge",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["total_battery_charge"],
            "aggregation": "single",
        },
        "combined_inverter_total_battery_discharge": {
            "name": "Inverter Total Battery Discharge",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["total_battery_discharge"],
            "aggregation": "single",
        },
        "combined_inverter_battery_power": {
            "name": "Inverter Battery Power",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["battery_power"],
            "aggregation": "single",
        },
        "combined_inverter_battery_level": {
            "name": "Inverter Battery Level",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["battery_level"],
            "aggregation": "single",
        },
        "combined_inverter_load_power": {
            "name": "Inverter Load Power",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["load_power"],
            "aggregation": "single",
        },
        # --- iHomeManager: house grid (GRID.CT) ---
        "combined_ihm_meter_active_power": {
            "name": "iHM Grid Active Power",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["meter_active_power_raw"],
            "aggregation": "single",
        },
        "combined_ihm_import_power": {
            "name": "iHM Import Power",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["import_power"],
            "aggregation": "single",
        },
        "combined_ihm_export_power": {
            "name": "iHM Export Power",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["export_power"],
            "aggregation": "single",
        },
        "combined_ihm_load_power": {
            "name": "iHM Load Power",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["load_power"],
            "aggregation": "single",
        },
        "combined_ihm_grid_import_energy": {
            "name": "iHM Grid Import Energy",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["grid_import_energy"],
            "aggregation": "single",
        },
        "combined_ihm_grid_export_energy": {
            "name": "iHM Grid Export Energy",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["grid_export_energy"],
            "aggregation": "single",
        },
        "combined_ihm_battery_power": {
            "name": "iHM Battery Power",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["battery_power"],
            "aggregation": "single",
        },
        "combined_ihm_battery_level": {
            "name": "iHM Battery Level",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["battery_level"],
            "aggregation": "single",
        },
        "combined_ihm_total_active_power": {
            "name": "iHM Total Active Power",
            "source": SOURCE_ROLE_IHM,
            "source_candidates": ["total_active_power"],
            "aggregation": "single",
        },
        # Persistent daily grid totals derived from iHM cumulative energy (issue #50).
        "combined_ihm_grid_import_daily": {
            "name": "iHM Grid Import Daily",
            "aggregation": "daily_meter",
            "meter_key": "import",
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total",
            "precision": 3,
        },
        "combined_ihm_grid_export_daily": {
            "name": "iHM Grid Export Daily",
            "aggregation": "daily_meter",
            "meter_key": "export",
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total",
            "precision": 3,
        },
        # --- Cross-source consumed energy (issue #50) ---
        "combined_daily_consumed_energy": {
            "name": "Combined Daily Consumed Energy",
            "aggregation": "formula",
            "formula": _CONSUMED_FORMULA,
            "operands": _DAILY_CONSUMED_OPERANDS,
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total",
            "precision": 1,
            "notes": (
                "PV/battery from inverter; daily grid import/export from persistent "
                "iHM daily meters (GRID.CT)."
            ),
        },
        "combined_total_consumed_energy": {
            "name": "Combined Total Consumed Energy",
            "aggregation": "formula",
            "formula": _CONSUMED_FORMULA,
            "operands": _TOTAL_CONSUMED_OPERANDS,
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total",
            "precision": 1,
            "notes": (
                "Grid import/export from iHM (GRID.CT); PV/battery totals from inverter."
            ),
        },
    },
}


# Binary sensor metrics per combination type.
COMBINED_BINARY_METRIC_SPECS: dict[str, dict[str, dict[str, object]]] = {
    "inverter_inverter": {
        "combined_pv_generating_any": {
            "name": "PV Generating Any",
            "source_candidates": ["pv_generating"],
            "operation": "any",
            "required_sources": "any",
        }
    },
    "inverter_ihm": {
        "combined_pv_generating_any": {
            "name": "PV Generating Any",
            "source": SOURCE_ROLE_INVERTER,
            "source_candidates": ["pv_generating"],
            "operation": "any",
            "required_sources": "any",
        },
    },
}
