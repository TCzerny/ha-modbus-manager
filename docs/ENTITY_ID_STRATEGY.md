# Entity ID strategy and template references (`[[mm:…]]`)

This document describes how **Modbus Manager** assigns **entity IDs**, how that relates to the entity registry **`unique_id`**, and how **calculated** / **template binary** entities reference other entities. It applies to the **`entity_id_strategy`** setting (per device) and the **`[[mm:…]]` markers** in device templates.

## Concepts

| Term | Role |
|------|------|
| **`unique_id`** | Globally unique string in the Home Assistant entity registry. Modbus Manager matches **legacy (v0.1.9)**: `prefix` from config plus `_` and the template id (casing of the **configured** prefix is kept, e.g. `SG_export_power` when the device prefix is `SG`). **Visible `entity_id` is still lowercased** from this string. If the device prefix is **left empty**, the id is **`_` + suffix** (e.g. `_export_power`). **Stable** across renames in many cases; used as the key for `[[mm:…]]` resolution. In templates, `{PREFIX}` is **lowercased** in Jinja/entity-style text, but **raw** when resolving registry ids and `[[mm:…]]` so it matches this field. |
| **`entity_id`** | The ID you use in **automations, dashboards, and `states('sensor.…')`**, e.g. `sensor.sg_export_power` or a HA–assigned name if not forced. |
| **`default_entity_id` / `self.entity_id`** | When set in the template, the integration **forces** a predictable `entity_id` (used for **legacy** strategies). When **not** set, Home Assistant can assign the entity ID (used for **HA–generated** strategy). |

## `entity_id_strategy` (per device)

One setting replaces the old boolean **`entity_ids_without_prefix`** (still read for migration):

| Value | Meaning |
|--------|---------|
| **`ha_generated`** | Do **not** auto-inject `default_entity_id` for every entity. **Home Assistant** assigns `entity_id` (device flow, rename, “recreate entity IDs” / 2025.6+). Registry matching stays on **`unique_id`**. Best alignment with [Issue #52](https://github.com/TCzerny/ha-modbus-manager/issues/52) (recreate entity IDs after renaming a device). |
| **`legacy_prefixed`** | Force `entity_id` with object id **`{prefix}_<suffix>`** (prefix lowercased in practice), e.g. `sensor.sg_export_power`. Same intent as old **`entity_ids_without_prefix: no`**. |
| **`legacy_unprefixed`** | Force `entity_id` **without** prefix in the object id (mkaiser-style), e.g. `sensor.export_power` while `unique_id` still includes the prefix. Same intent as **`entity_ids_without_prefix: yes`**. Placeholder resolution for legacy string refs strips bare `{PREFIX}` in entity-style text where applicable. |

**Migration:** `entity_ids_without_prefix: yes` → `legacy_unprefixed`; `no` → `legacy_prefixed`. New installs / UI should use **`entity_id_strategy`**; the old key is deprecated but still accepted.

## Why `[[mm:domain:…]]` in templates

For **`ha_generated`**, you cannot rely on a fixed `sensor.<prefix>_<id>` in Jinja: the **visible** `entity_id` may differ. **Calculated** and **template binary** templates therefore use markers:

```text
[[mm:sensor:{PREFIX}_export_power]]
```

1. **Step A (coordinator):** `{PREFIX}` and other placeholders are applied; markers become e.g. `[[mm:sensor:SG2_export_power]]` using the same **registry `unique_id`** string as `generate_unique_id` (configured prefix casing).
2. **Step B (entity):** The integration resolves `[[mm:<domain>:<unique_id>]]` to the current **`entity_id`** via the entity registry (`modbus_manager` platform), then the Jinja template uses `states('sensor.actual_id')` as usual.

If a reference is missing (e.g. optional entity not created yet), resolution retries until the entity exists; **debug** may log a missing key **at most once** per `(domain, unique_id)`.

## What you do not need to change

- **Modbus register entities** (sensors, numbers, etc.): no `[[mm:…]]` in their YAML; they get `entity_id` / `unique_id` from the integration as before.
- **`add_entity_prefix` service** ([SERVICES](SERVICES.md)): still renames **legacy unprefixed** `entity_id`s; it only changes `entity_id`, not `unique_id`, and does not replace the `[[mm:…]]` mechanism.

## Further reading

- [Issue #52](https://github.com/TCzerny/ha-modbus-manager/issues/52) – HA “recreate entity IDs”
