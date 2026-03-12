# unique_id Comparison: Modbus Manager SH Template vs mkaiser

This document validates the entity ID compatibility between the Modbus Manager SH template (with prefix `sg`) and the [mkaiser modbus_sungrow.yaml](https://raw.githubusercontent.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant/refs/heads/main/modbus_sungrow.yaml).

## Important: How entity_id is Generated

| Integration | entity_id Source | Example |
|-------------|------------------|---------|
| **mkaiser (built-in Modbus)** | From **entity name** (slugified) | Name "MPPT1 voltage" → `sensor.mppt1_voltage` |
| **Modbus Manager** | From **unique_id** (with prefix) | unique_id `mppt1_voltage` + prefix `sg` → `sensor.sg_mppt1_voltage` |

**Conclusion:** mkaiser entity_ids typically do **not** include the `sg_` prefix (they come from the display name). Modbus Manager entity_ids **always** include the prefix. Therefore, **entity_ids will generally NOT match** between the two integrations, even when using prefix `sg`.

---

## Why Does This Difference Exist?

### Built-in Modbus Integration (mkaiser)

The Home Assistant built-in Modbus integration uses the **entity name** to generate `entity_id`:

- **Historical design:** The Modbus integration was created before `unique_id` was widely used for entity identification. Entity IDs were traditionally derived from the "friendly name" (slugified: lowercase, spaces → underscores).
- **unique_id role:** `unique_id` was added later (HA core PR #64634) for **entity registry stability**—to track entities across configuration changes. It does not change how `entity_id` is generated.
- **Result:** mkaiser sensors like "MPPT1 voltage" or "Sungrow inverter serial" become `sensor.mppt1_voltage` and `sensor.sungrow_inverter_serial`—no `sg_` prefix in the entity_id.

### Modbus Manager

Modbus Manager uses **unique_id** (with prefix) for `entity_id`:

- **Multi-device support:** Each device can have multiple entities. The prefix (e.g. `sg`, `sbr`) ensures uniqueness when several devices share the same hub (e.g. inverter + battery).
- **Consistency:** `unique_id` is the single source of truth for both registry identity and entity_id; no mismatch between name and entity_id.
- **Result:** With prefix `sg`, entities become `sensor.sg_mppt1_voltage`, `number.sg_battery_min_soc`, etc.

---

## How to Make Migration Easier

### Option A: Use "mkaiser entity_id compatibility" mode (future feature)

**Idea:** Add a device-level option when adding the SH device: **"Use mkaiser entity_id format"** (or **"Entity ID prefix: none"**).

- **Behavior:** When enabled, use the template `unique_id` **without** prefix for `entity_id` (e.g. `sensor.mppt1_voltage` instead of `sensor.sg_mppt1_voltage`).
- **Registry:** Keep `unique_id` with prefix (e.g. `sg_mppt1_voltage`) for registry stability.
- **Pros:** Entity IDs match mkaiser; history and automations can stay unchanged.
- **Cons:** Only safe when there is **one** SH device per hub. With multiple devices (e.g. two inverters), entity_ids would collide.

**Implementation:** Add a config option (e.g. `entity_id_prefix: ""` or `mkaiser_entity_id_compat: true`) and, when set, use `template_unique_id` instead of `prefix_template_unique_id` for `default_entity_id` in `process_template_entities_with_prefix`.

### Option A2: Use template `default_entity_id` parameter

**Existing feature:** Templates can define `default_entity_id` per entity. If set, it overrides the auto-derived entity_id.

- **Current behavior:** If template has `default_entity_id: "battery_level"`, the entity gets `sensor.battery_level`. But this is used for **all** devices—with prefix `sg` we'd still get `sensor.battery_level` (no prefix applied to template default_entity_id). That would cause **collisions** when multiple SH devices exist on the same hub.
- **Gap:** `default_entity_id` does **not** go through `replace_template_placeholders`—no `{PREFIX}` support. So we cannot have `default_entity_id: "{PREFIX}_battery_level"` to get `sg_battery_level` in normal mode.
- **How it could help:** When combined with Option A (mkaiser compat mode): in mkaiser mode, use template `default_entity_id` if present (for entities where our `unique_id` differs from mkaiser, e.g. `meter_active_power_raw` → `meter_active_power`), else use `template_unique_id`. In normal mode, ignore template `default_entity_id` and use `prefix_unique_id`.
- **Template changes:** Add `default_entity_id` only for entities that don't match mkaiser (e.g. `meter_active_power_raw` gets `default_entity_id: "meter_active_power"`). For the bulk, `template_unique_id` suffices in mkaiser mode.

### Option B: Manual entity rename after migration

- **Flow:** Migrate as usual (prefix `sg`), then manually rename entities in **Settings → Devices & Services → Entities** to remove the `sg_` prefix (e.g. `sensor.sg_mppt1_voltage` → `sensor.mppt1_voltage`).
- **Pros:** No code changes; works with existing setup.
- **Cons:** Tedious for many entities; history still does not carry over unless the entity_id matches exactly.

### Option C: Update automations and dashboards

- **Flow:** Migrate as usual and update all references to the new entity_ids.
- **Pros:** Works for any number of devices; clear and consistent.
- **Cons:** Requires manual updates; history is lost.

### Recommendation

- **Short term:** Use Option C (update references) and document it clearly.
- **Future:** Add Option A as an optional "mkaiser compatibility" mode for single-device setups, with a clear warning about multi-device conflicts.

---

## 1. unique_id Comparison (Modbus Manager prefix `sg` vs mkaiser)

### 1.1 Sensors – Match (same unique_id after prefix)

| mkaiser unique_id | Modbus Manager (prefix sg) | Match |
|-------------------|----------------------------|-------|
| sg_mppt1_voltage | sg_mppt1_voltage | ✓ |
| sg_mppt1_current | sg_mppt1_current | ✓ |
| sg_mppt2_voltage | sg_mppt2_voltage | ✓ |
| sg_mppt2_current | sg_mppt2_current | ✓ |
| sg_mppt3_voltage | sg_mppt3_voltage | ✓ |
| sg_mppt3_current | sg_mppt3_current | ✓ |
| sg_mppt4_voltage | sg_mppt4_voltage | ✓ |
| sg_mppt4_current | sg_mppt4_current | ✓ |
| sg_total_dc_power | sg_total_dc_power | ✓ |
| sg_phase_a_voltage | sg_phase_a_voltage | ✓ |
| sg_phase_b_voltage | sg_phase_b_voltage | ✓ |
| sg_phase_c_voltage | sg_phase_c_voltage | ✓ |
| sg_reactive_power | sg_reactive_power | ✓ |
| sg_power_factor | sg_power_factor | ✓ |
| sg_daily_pv_gen_battery_discharge | sg_daily_pv_gen_battery_discharge | ✓ |
| sg_total_pv_gen_battery_discharge | sg_total_pv_gen_battery_discharge | ✓ |
| sg_inverter_temperature | sg_inverter_temperature | ✓ |
| sg_battery_power | sg_battery_power | ✓ |
| sg_grid_frequency | sg_grid_frequency | ✓ |
| sg_meter_active_power | sg_meter_active_power_raw | ✗ (suffix `_raw`) |
| sg_meter_phase_a_active_power | sg_meter_phase_a_active_power_raw | ✗ |
| sg_meter_phase_b_active_power | sg_meter_phase_b_active_power_raw | ✗ |
| sg_meter_phase_c_active_power | sg_meter_phase_c_active_power_raw | ✗ |
| sg_bdc_rated_power | sg_bdc_rated_power | ✓ |
| sg_battery_current | sg_battery_current | ✓ |
| sg_bms_max_charging_current | sg_bms_max_charging_current | ✓ |
| sg_bms_max_discharging_current | sg_bms_max_discharging_current | ✓ |
| sg_backup_phase_a_power | sg_backup_phase_a_power | ✓ |
| sg_backup_phase_b_power | sg_backup_phase_b_power | ✓ |
| sg_backup_phase_c_power | sg_backup_phase_c_power | ✓ |
| sg_total_backup_power | sg_total_backup_power | ✓ |
| sg_meter_phase_a_voltage | sg_meter_phase_a_voltage | ✓ |
| sg_meter_phase_b_voltage | sg_meter_phase_b_voltage | ✓ |
| sg_meter_phase_c_voltage | sg_meter_phase_c_voltage | ✓ |
| sg_meter_phase_a_current | sg_meter_phase_a_current | ✓ |
| sg_meter_phase_b_current | sg_meter_phase_b_current | ✓ |
| sg_meter_phase_c_current | sg_meter_phase_c_current | ✓ |
| sg_daily_pv_generation | sg_daily_pv_generation | ✓ |
| sg_total_pv_generation | sg_total_pv_generation | ✓ |
| sg_daily_exported_energy_from_PV | sg_daily_exported_energy_from_PV | ✓ |
| sg_total_exported_energy_from_pv | sg_total_exported_energy_from_pv | ✓ |
| sg_load_power | sg_load_power | ✓ |
| sg_battery_export_power_raw | sg_export_power_raw | ✗ (different name) |
| sg_daily_battery_charge_from_pv | sg_daily_battery_charge_from_pv | ✓ |
| sg_total_battery_charge_from_pv | sg_total_battery_charge_from_pv | ✓ |
| sg_daily_direct_energy_consumption | sg_daily_direct_energy_consumption | ✓ |
| sg_total_direct_energy_consumption | sg_total_direct_energy_consumption | ✓ |
| sg_battery_voltage | sg_battery_voltage | ✓ |
| sg_battery_level | sg_battery_level | ✓ |
| sg_battery_state_of_health | sg_battery_state_of_health | ✓ |
| sg_battery_temperature | sg_battery_temperature | ✓ |
| sg_daily_battery_discharge | sg_daily_battery_discharge | ✓ |
| sg_total_battery_discharge | sg_total_battery_discharge | ✓ |
| sg_phase_a_current | sg_phase_a_current | ✓ |
| sg_phase_b_current | sg_phase_b_current | ✓ |
| sg_phase_c_current | sg_phase_c_current | ✓ |
| sg_total_active_power | sg_total_active_power | ✓ |
| sg_daily_imported_energy | sg_daily_imported_energy | ✓ |
| sg_total_imported_energy | sg_total_imported_energy | ✓ |
| sg_daily_battery_charge | sg_daily_battery_charge | ✓ |
| sg_total_battery_charge | sg_total_battery_charge | ✓ |
| sg_daily_exported_energy | sg_daily_exported_energy | ✓ |
| sg_total_exported_energy | sg_total_exported_energy | ✓ |

### 1.2 Sensors – Mismatch or Different Structure

| mkaiser | Modbus Manager | Notes |
|---------|----------------|-------|
| sg_version_1, sg_version_2, sg_version_3, sg_version_4_battery | inverter_firmware_info (combined) | mkaiser: 4 separate firmware strings; we: single combined firmware |
| sg_protocol_version | sg_protocol_version_raw | Different suffix |
| sg_arm_software | sg_certification_version_arm_software | Different name |
| sg_dsp_software | sg_certification_version_dsp_software | Different name |
| sg_inverter_serial | sg_inverter_serial | ✓ |
| sg_dev_code | sg_sungrow_device_type_code | Different name |
| sg_inverter_rated_output | sg_nominal_output_power | Different name |
| uid_battery_capacity_high_precision | sg_battery_capacity | Different (we use battery_capacity) |
| uid_sg_running_state_raw | sg_system_state | Different (we have system_state + running_state) |
| uid_power_flow_status | sg_running_state | Different (power flow vs running state) |
| sg_load_adjustment_mode_selection_raw | sg_load_adjustment_mode_selection_raw | ✓ |
| sg_load_adjustment_mode_enable_raw | sg_load_adjustment_mode_on_off_selection_raw | Different (different register semantics) |
| sg_ems_mode_selection_raw | sg_ems_mode_selection_raw | ✓ |
| sg_battery_forced_charge_discharge_cmd_raw | (in controls) | ✓ |
| sg_battery_forced_charge_discharge_power | (in controls) | ✓ |
| uid_sg_battery_max_soc | sg_max_export_power_limit_value (or battery max SoC control) | Different structure |
| uid_sg_battery_min_soc | sg_min_export_power_limit_value (or battery min SoC control) | Different structure |
| sg_export_power_limit | sg_export_power_limit | ✓ |
| sg_backup_mode_raw | sg_backup_mode_raw | ✓ |
| sg_export_power_limit_mode_raw | sg_export_power_limit_mode_raw | ✓ |
| sg_battery_reserved_soc_for_backup | sg_battery_reserved_soc_for_backup | ✓ |
| sg_inverter_firmware_version | sg_inverter_firmware_info | Different name |
| sg_communication_module_firmware_version | sg_communication_module_firmware_info | Different name |
| sg_battery_firmware_version | sg_battery_firmware_info | Different name |
| sg_battery_max_charge_power | sg_battery_max_charge_power | ✓ |
| sg_battery_max_discharge_power | sg_battery_max_discharge_power | ✓ |
| sg_battery_charging_start_power | sg_battery_charging_start_power | ✓ |
| sg_battery_discharging_start_power | sg_battery_discharging_start_power | ✓ |

### 1.3 mkaiser Template Entities (binary_sensor, sensor, number, select, switch, button)

mkaiser uses **template** platforms (template:, sensor:, etc.) with entity **names** like "PV generating", "Battery Min Soc". Entity IDs are derived from those names, e.g. `binary_sensor.pv_generating`, `number.battery_min_soc`.

Modbus Manager uses **unique_id with prefix**, e.g. `binary_sensor.sg_pv_generating`, `number.sg_battery_min_soc`.

| mkaiser (from name) | Modbus Manager (prefix sg) | Match |
|---------------------|----------------------------|-------|
| binary_sensor.pv_generating | binary_sensor.sg_pv_generating | ✗ |
| binary_sensor.battery_charging | binary_sensor.sg_battery_charging | ✗ |
| binary_sensor.battery_discharging | binary_sensor.sg_battery_discharging | ✗ |
| sensor.mppt1_power | sensor.sg_mppt1_power | ✗ |
| number.battery_min_soc | number.sg_battery_min_soc | ✗ |
| number.export_power_limit | number.sg_export_power_limit | ✗ |
| select.ems_mode | select.sg_ems_mode | ✗ |
| switch.backup_mode | switch.sg_backup_mode | ✗ |

**Note:** mkaiser template entities reference modbus sensors by **entity_id** (from name), e.g. `sensor.power_flow_status`. Our modbus sensors use `sensor.sg_running_state` (from unique_id). So even internal template references differ.

---

## 2. entity_id vs unique_id – Critical Difference

- **mkaiser Modbus:** entity_id = slugified **name** (e.g. "MPPT1 voltage" → `sensor.mppt1_voltage`)
- **Modbus Manager:** entity_id = **unique_id** (with prefix) (e.g. `sg_mppt1_voltage` → `sensor.sg_mppt1_voltage`)

So with prefix `sg`, Modbus Manager entities are `sensor.sg_mppt1_voltage`, while mkaiser Modbus entities are `sensor.mppt1_voltage`. **They do not match.**

---

## 3. Summary

| Aspect | Result |
|--------|--------|
| **unique_id alignment** | Many match when using prefix `sg`; some differ (`_raw`, different names) |
| **entity_id alignment** | **Do not match** – mkaiser uses name-based entity_ids, we use unique_id-based |
| **Automation compatibility** | Automations referencing mkaiser entity_ids (e.g. `sensor.mppt1_voltage`) will **not** work with Modbus Manager entities (e.g. `sensor.sg_mppt1_voltage`) without updates |

---

## 4. Recommendation for Migration Guide

1. **Do not** claim that entity_ids match when using prefix `sg`.
2. **State clearly** that automations, dashboards, and scripts must be updated to the new entity_ids.
3. **History:** History is tied to entity_id. If entity_ids differ, history will not carry over. To keep history, entity_ids would need to match, which is not the case with the current designs.
4. **Prefix `sg`:** Use prefix `sg` for consistency with mkaiser’s `sg_` unique_ids and to avoid conflicts with other integrations, but expect different entity_ids and plan for automation updates.
