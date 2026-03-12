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

### Option A: Use `entity_ids_without_prefix` (Recommended for single-device setups)

**Implemented in Modbus Manager v1.0.2+.** When adding the Sungrow SH device, set **Entity IDs without prefix** to **yes** in the dynamic configuration.

- **Behavior:** Entity IDs are generated **without** the prefix (e.g. `sensor.mppt1_voltage`, `sensor.load_power` instead of `sensor.sg_mppt1_voltage`).
- **Registry:** `unique_id` keeps the prefix (e.g. `sg_mppt1_voltage`) for registry stability.
- **Pros:** Entity IDs match mkaiser; **history carries over**; automations and dashboards continue to work without changes.
- **Cons:** Only safe when there is **one** Sungrow SH device per hub. With multiple devices, entity_ids would collide.

**After migration:** When ready to switch to prefixed entity_ids, call the service `modbus_manager.add_entity_prefix` with your config entry ID. Entity IDs will be renamed (e.g. `sensor.load_power` → `sensor.sg_load_power`). Home Assistant migrates history automatically when entity_ids are renamed.

See [MIGRATION_mkaiser_to_modbus_manager.md](MIGRATION_mkaiser_to_modbus_manager.md) for the full step-by-step guide.

### Option B: Manual entity rename after migration

- **Flow:** Migrate as usual (prefix `sg`), then manually rename entities in **Settings → Devices & Services → Entities** to remove the `sg_` prefix (e.g. `sensor.sg_mppt1_voltage` → `sensor.mppt1_voltage`).
- **Pros:** Works with existing setup.
- **Cons:** Tedious for many entities; history does not carry over unless the entity_id matches exactly.

### Option C: Update automations and dashboards

- **Flow:** Migrate as usual and update all references to the new entity_ids.
- **Pros:** Works for any number of devices; clear and consistent.
- **Cons:** Requires manual updates; history is lost.

### Recommendation

- **Single Sungrow SH device per hub:** Use **Option A** (`entity_ids_without_prefix: yes`) for seamless migration with history retention.
- **Multiple devices per hub:** Use **Option C** (update references) and document the new entity_ids.

---

## 1. unique_id Comparison (Modbus Manager prefix `sg` vs mkaiser)

**Note on `_raw` entities:** Modbus Manager exposes both `_raw` (direct register value) and calculated entities where a transformation is applied. The calculated entity (e.g. `sg_protocol_version`, `sg_meter_active_power`) typically aligns with mkaiser's equivalent. The `_raw` variant is the internal source (e.g. BCD-encoded protocol version, or meter value before filtering invalid 0x7FFFFFFF).

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
| sg_meter_active_power | sg_meter_active_power | ✓ (calculated from _raw, filters 0x7FFFFFFF) |
| sg_meter_phase_a_active_power | sg_meter_phase_a_active_power | ✓ (calculated from _raw) |
| sg_meter_phase_b_active_power | sg_meter_phase_b_active_power | ✓ (calculated from _raw) |
| sg_meter_phase_c_active_power | sg_meter_phase_c_active_power | ✓ (calculated from _raw) |
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
| sg_battery_export_power_raw | sg_export_power_raw | Different name (same register); we also have sg_export_power (calculated) |
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
| sg_protocol_version | sg_protocol_version | ✓ (calculated from _raw, BCD→version string) |
| sg_inverter_serial | sg_inverter_serial | ✓ |
| sg_load_adjustment_mode_selection_raw | sg_load_adjustment_mode_selection_raw | ✓ |
| sg_ems_mode_selection_raw | sg_ems_mode_selection_raw | ✓ |
| sg_export_power_limit | sg_export_power_limit | ✓ |
| sg_backup_mode_raw | sg_backup_mode_raw | ✓ |
| sg_export_power_limit_mode_raw | sg_export_power_limit_mode_raw | ✓ |
| sg_battery_reserved_soc_for_backup | sg_battery_reserved_soc_for_backup | ✓ |
| sg_battery_max_charge_power | sg_battery_max_charge_power | ✓ |
| sg_battery_max_discharge_power | sg_battery_max_discharge_power | ✓ |
| sg_battery_charging_start_power | sg_battery_charging_start_power | ✓ |
| sg_battery_discharging_start_power | sg_battery_discharging_start_power | ✓ |

### 1.2 Sensors – Mismatch or Different Structure

| mkaiser | Modbus Manager | Notes |
|---------|----------------|-------|
| sg_version_1, sg_version_2, sg_version_3, sg_version_4_battery | inverter_firmware_info (combined) | mkaiser: 4 separate firmware strings; we: single combined firmware |
| sg_arm_software | sg_certification_version_arm_software | Different name |
| sg_dsp_software | sg_certification_version_dsp_software | Different name |
| sg_dev_code | sg_sungrow_device_type_code | Different name |
| sg_inverter_rated_output | sg_nominal_output_power | Different name |
| uid_battery_capacity_high_precision | sg_battery_capacity | Different (we use battery_capacity) |
| uid_sg_running_state_raw | sg_system_state | Different (we have system_state + running_state) |
| uid_power_flow_status | sg_running_state | Different (power flow vs running state) |
| sg_load_adjustment_mode_enable_raw | sg_load_adjustment_mode_on_off_selection_raw | Different (different register semantics) |
| sg_battery_forced_charge_discharge_cmd_raw | (in controls) | Same semantic, different platform (controls vs sensors) |
| sg_battery_forced_charge_discharge_power | (in controls) | Same semantic, different platform (controls vs sensors) |
| uid_sg_battery_max_soc | sg_max_export_power_limit_value (or battery max SoC control) | Different structure |
| uid_sg_battery_min_soc | sg_min_export_power_limit_value (or battery min SoC control) | Different structure |
| sg_inverter_firmware_version | sg_inverter_firmware_info | Different name |
| sg_communication_module_firmware_version | sg_communication_module_firmware_info | Different name |
| sg_battery_firmware_version | sg_battery_firmware_info | Different name |

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
| **entity_id alignment (default)** | **Do not match** – mkaiser uses name-based entity_ids, Modbus Manager uses unique_id-based with prefix |
| **entity_id alignment (entity_ids_without_prefix: yes)** | **Match** – Modbus Manager generates unprefixed entity_ids (e.g. `sensor.mppt1_voltage`), same as mkaiser |
| **History retention** | With `entity_ids_without_prefix: yes`, entity_ids match → history carries over. Use `add_entity_prefix` service later to add prefix; HA migrates history on rename |
| **Automation compatibility** | With `entity_ids_without_prefix: yes`, automations continue to work. With default (prefixed), automations must be updated |

---

## 4. Recommendation for Migration Guide

1. **Single-device setups:** Use `entity_ids_without_prefix: yes` for history retention and automation compatibility. Call `modbus_manager.add_entity_prefix` when ready to switch to prefixed entity_ids.
2. **Multi-device setups:** Use default (prefixed) mode. Update automations, dashboards, and scripts to the new entity_ids.
3. **Prefix `sg`:** Use prefix `sg` for consistency with mkaiser's `sg_` unique_ids and to avoid conflicts with other integrations.
4. **Full guide:** See [MIGRATION_mkaiser_to_modbus_manager.md](MIGRATION_mkaiser_to_modbus_manager.md) for the complete step-by-step migration process.
