# Combined Device (Cross-Hub)

> **Integration version:** 1.0.21+

The **Combined Device** is an opt-in virtual Modbus Manager config entry that aggregates data from **two existing hub entries** without additional Modbus I/O. It is intended for setups where physically separate devices (e.g. Sungrow inverter + iHomeManager) should be viewed as one logical unit in Home Assistant.

---

## Supported combinations

| Combination type       | Source devices                         | Typical use case                          |
|------------------------|----------------------------------------|-------------------------------------------|
| `inverter_ihm`         | Inverter + iHomeManager (`energy_manager`) | House grid at iHM GRID.CT + PV/battery at inverter |
| `inverter_inverter`    | Two inverters                          | Dual inverter / parallel strings          |

Sources can be on **different Modbus hubs** (different `host:port`). The combined entry only reads cached coordinator data from both hubs.

---

## Setup (Config Flow)

1. Ensure both source hubs are already configured and running in Modbus Manager.
2. **Settings → Devices & services → Modbus Manager → Add integration**.
3. On the template selection step, choose **Combined Device (cross-hub)**.
4. Select **Source A** and **Source B** (order does not matter for metrics; roles are resolved by device type).
5. Set a unique **Combined prefix** (device name and registry identity; see [Entity IDs and naming](#entity-ids-and-naming)).
6. Finish the flow.

### Eligibility

An existing entry appears in the source list if it contains at least one device of type `inverter` or `energy_manager`. Combined entries themselves are excluded.

### Validation errors

| Error / abort              | Meaning |
|----------------------------|---------|
| `no_eligible_sources`      | Fewer than two eligible hub entries exist |
| `same_source_selected`     | Source A and B are the same entry |
| `source_not_found`         | Selected entry was removed |
| `invalid_pair`             | Device types do not form a supported pair |
| `already_configured`       | Combined prefix is already used |

---

## Config entry data model

```yaml
entry_type: combined_device
source_entry_id_a: "<hub entry_id>"
source_entry_id_b: "<hub entry_id>"
combination_type: inverter_ihm | inverter_inverter
combined_prefix: "<unique_prefix>"
```

- **No Modbus connection** is opened for the combined entry.
- Source hub entries remain unchanged; combined entities live on a separate HA device.

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│  Hub entry A        │     │  Hub entry B        │
│  ModbusCoordinator  │     │  ModbusCoordinator  │
│  (cache)            │     │  (cache)            │
└──────────┬──────────┘     └──────────┬──────────┘
           │                             │
           └──────────┬──────────────────┘
                      ▼
           ┌─────────────────────┐
           │ CombinedDevice      │
           │ Coordinator         │
           │ (5 s refresh)       │
           └──────────┬──────────┘
                      ▼
           ┌─────────────────────┐
           │ Combined sensors /  │
           │ binary_sensors      │
           └─────────────────────┘
```

### Key modules

| File | Role |
|------|------|
| `combined_specs.py` | Metric definitions per `combination_type` |
| `combined_coordinator.py` | Aggregation, formulas, role resolution |
| `combined_daily_meter.py` | Persistent daily grid counters (`inverter_ihm`) |
| `combined_entities.py` | HA sensor / binary_sensor entities |
| `config_flow.py` | Combined Device setup flow |

Metric definitions are centralized in `COMBINED_SENSOR_METRIC_SPECS` and `COMBINED_BINARY_METRIC_SPECS`. To add or change metrics, edit `combined_specs.py` and add matching translation keys in `translations/en.json` and `translations/de.json`.

---

## Role resolution (`inverter_ihm`)

Config Flow stores sources as **A** and **B**, but metrics use **roles**:

- **`inverter`** — entry whose `devices[]` includes `type: inverter` (Sungrow SHx / SG templates).
- **`ihm`** — entry whose `devices[]` includes `type: energy_manager` (iHomeManager template).

Passthrough and formula operands always read from the correct role, regardless of A/B order.

---

## Entities overview

### Diagnostic (all combination types)

| Entity | Description |
|--------|-------------|
| `combined_pair_type` | Shows `inverter_ihm` or `inverter_inverter` |
| `combined_source_a_available` | Source A coordinator has data |
| `combined_source_b_available` | Source B coordinator has data |
| `combined_any_source_available` | At least one source is available |

### `inverter_inverter` — aggregated metrics

Numeric values are combined from **both** inverters (sum / max / avg as specified):

- Power: `combined_total_active_power`, `combined_total_dc_power`
- Energy: daily/total PV, import, export, direct consumption
- Other: `combined_inverter_temperature_max`, `combined_grid_frequency_avg`
- Binary: `combined_pv_generating_any` (on if either inverter reports PV generating)

Units and precision are taken from source register metadata when possible (including W↔kW, Wh↔kWh conversion).

### `inverter_ihm` — passthrough + cross-source formulas

**Inverter passthrough** (prefix `combined_inverter_*`):
e.g. `combined_inverter_daily_pv_generation`, `combined_inverter_battery_power`, `combined_inverter_load_power`.

**iHomeManager passthrough** (prefix `combined_ihm_*`):
Grid power: `combined_ihm_meter_active_power`, `combined_ihm_import_power`, `combined_ihm_export_power`.
Grid energy totals: `combined_ihm_grid_import_energy`, `combined_ihm_grid_export_energy`.
Also load, battery, and `combined_ihm_total_active_power` where present in the iHM template.

**Persistent daily grid** (iHM GRID.CT, no HA `utility_meter` helper required):

| Entity | Description |
|--------|-------------|
| `combined_ihm_grid_import_daily` | Daily import energy derived from `grid_import_energy` |
| `combined_ihm_grid_export_daily` | Daily export energy derived from `grid_export_energy` |

**Consumed energy** ([GitHub issue #50](https://github.com/TCzerny/ha-modbus-manager/issues/50)):

| Entity | Formula (concept) | Data sources |
|--------|-------------------|--------------|
| `combined_total_consumed_energy` | `PV − export + import − batt_charge + batt_discharge` | PV/battery **totals** from inverter; import/export **totals** from iHM |
| `combined_daily_consumed_energy` | Same balance for daily values | PV/battery **daily** from inverter; import/export **daily** from persistent iHM daily meters |

Template sensors on a **single** inverter (`daily_consumed_energy` / `total_consumed_energy` in SHx/SG YAML) only use that inverter’s prefix. They do **not** include iHM grid data. The combined entry is the supported way to get a WR+iHM house-level balance in Modbus Manager.

Formula sensors expose attributes: `formula`, `operands`, and `notes` for transparency.

**Binary:** `combined_pv_generating_any` (from inverter only).

---

## Persistent daily meters (`inverter_ihm`)

The iHomeManager exposes **cumulative** grid energies (`grid_import_energy`, `grid_export_energy`), not native daily registers. The integration implements an internal daily counter (similar to Home Assistant’s `utility_meter` logic):

- Accumulates deltas from the cumulative totals
- Resets at **local midnight** (Home Assistant time zone)
- Handles **counter resets** (e.g. meter replacement) by adding the new reading
- Persists state across restarts in:

  `.storage/modbus_manager.combined_daily_meters`

State is **removed** when the combined config entry is deleted.

Entity attributes `meter_day` and `source_unique_id` help verify which source register is used.

---

## Availability

- Combined coordinator refreshes every **5 seconds** (cache-only).
- If a source hub coordinator has no data, that source is marked unavailable.
- Metrics requiring both sources (`required_sources: both` on `inverter_inverter` sums) become unavailable if either side is missing.
- Passthrough metrics for one role only need that role’s hub to be available.

After source hubs recover, combined entities recover automatically; no manual reload is required (entity registry may still cache old names until reload if the combined entry was recreated).

---

## Entity IDs and naming

Combined entities follow the same approach as hub devices with **`entity_id_strategy: ha_generated`** (see [ENTITY_ID_STRATEGY.md](ENTITY_ID_STRATEGY.md)):

- **`entity_id`**: Assigned by **Home Assistant** from the combined device name and entity name (not forced to `sensor.<prefix>_<metric>`). This supports device rename and “recreate entity IDs” flows on current HA versions.
- **`unique_id`**: Prefixed style like hub Modbus entities — `{combined_prefix}_{metric_key}` with **configured prefix casing** (e.g. `SG_IHM_combined_total_consumed_energy`), via the same `generate_unique_id()` rules as `legacy_prefixed` / `ha_generated` hubs. Re-adding a combined entry with the same prefix reuses registry rows when `unique_id` matches.
- **Device name**: `Combined <combined_prefix>` — the prefix is for identification in the UI, not a guaranteed `entity_id` slug.
- **Source hubs**: Their `entity_id_strategy` (`ha_generated`, `legacy_prefixed`, …) applies only to Modbus template entities on those hubs; it does **not** change combined-entity IDs.
- **Translations**: `entity.sensor.<metric_key>.name` in `en.json` / `de.json`; entities use `has_entity_name: true` with explicit names for correct UI labels.

**Note:** Combined entries created before `ha_generated` behaviour may still show old forced `entity_id` values in the registry until the combined entry is removed and re-added (or entities are renamed in HA).

---

## Changing source hub IP or port

Combined entries store **source hub config entry IDs only** (`source_entry_id_a` / `source_entry_id_b`), not `host`/`port`.

When you change the Modbus endpoint of a source hub:

1. Open **Settings → Devices & services → Modbus Manager → Hub → Configure** (options).
2. Update **IP address / hostname** and **port**, then save.
3. The integration migrates device registry identifiers on that hub and reloads the hub.
4. Any **Combined Device** that references this hub is **reloaded automatically** (metrics may be briefly `unavailable`).

You do **not** need to recreate the combined entry. Daily grid counters in `.storage` are keyed by the combined entry ID and are kept.

---

## Troubleshooting

| Symptom | Checks |
|---------|--------|
| Combined entry missing in add flow | Need ≥2 hubs with inverter and/or iHomeManager devices |
| Combination Type shows inverter+inverter for SG+iHM | iHM hub may have been stored as `type: inverter`; reload integration after update (template `sungrow_ihomemanager` is detected as `energy_manager`). Recreate combined entry once if old `inverter_inverter` entities remain. |
| `invalid_pair` | Pair must be inverter+inverter or inverter+energy_manager. A **battery** on the inverter hub is supported from **1.0.12** (ignored for pairing); on 1.0.11 remove battery was a workaround — update and reload, do not remove the battery device |
| Many entities `unavailable` | Verify both source hubs are loaded; check diagnostic availability sensors |
| `combined_daily_consumed_energy` unavailable | Requires iHM grid totals + inverter daily PV/battery; SG without `daily_battery_*` may block the formula |
| `combined_pv_generating_any` always unknown | Source `pv_generating` is a **template** binary sensor (not Modbus cache). From 1.0.11+ the combined device reads it from the HA entity registry; ensure `binary_sensor.<prefix>_pv_generating` exists and is not `unavailable` on each source hub |
| Daily grid stuck at 0 | Confirm `combined_ihm_grid_import_energy` / `_export_energy` update on the iHM hub |
| Wrong consumed energy vs. iSolarCloud | Confirm GRID.CT is on iHM; compare `combined_total_consumed_energy` with cloud; WR-only template sensors are expected to differ |
| Stale entity names after changes | Reload combined integration or recreate the combined entry |

---

## Limitations (current)

- No user-selectable metric subset (`enabled_entities` is reserved for future use).
- No combined entry reconfigure flow; delete and recreate to change sources.
- `inverter_inverter` consumed-energy formulas are not provided (only sums of individual registers).
- Daily meters depend on regular updates of iHM cumulative sensors (scan interval on source hub applies).
- Binary and diagnostic entities are categorized as diagnostic.

---

## References

- [Issue #50 — daily/total consumed energy with iHomeManager](https://github.com/TCzerny/ha-modbus-manager/issues/50)
- Templates: `device_templates/sungrow_shx_dynamic.yaml`, `sungrow_sg_dynamic.yaml`, `sungrow_ihomemanager.yaml`
