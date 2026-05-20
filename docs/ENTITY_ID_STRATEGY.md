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

### Fresh install vs existing registry

| Situation | What you get |
|-----------|----------------|
| **New device**, empty entity registry (or no row for that `unique_id`) | Strategy applies immediately: unprefixed (`sensor.export_power`), prefixed (`sensor.sg_export_power`), or HA-assigned ids for `ha_generated`. |
| **Existing device**, same `unique_id` already in registry | Home Assistant **reuses** the registry row. The visible **`entity_id` usually does not change** when you only change `entity_id_strategy` in Configure. A **restart does not fix** that. |
| **Strategy change** on an existing install | Integration may set a different `default_entity_id` / `self.entity_id` in code, but the registry keeps the old `entity_id` until you rename, remove entities, or reinstall. |

## History preservation

Home Assistant **recorder history** is tied to **`entity_id`**, not `unique_id`.

Modbus Manager is designed for **maximum history continuity** on upgrade and migration:

- **Upgrades** without changing strategy: `unique_id` stays stable (v0.1.9-compatible rules). Existing history and automations keep working when `entity_id` is unchanged.
- **mkaiser-style migration** ([Migration from mkaiser](https://github.com/TCzerny/ha-modbus-manager/wiki/Migration-from-mkaiser)): use **`legacy_unprefixed`** on a **fresh** Modbus Manager setup so new entities get the same unprefixed `entity_id` values as the old YAML integration (e.g. `sensor.export_power`). History is preserved **when** that `entity_id` is free and matches the old name (no `*_2` duplicate).
- **Controlled rename to prefixed ids**: use the [`add_entity_prefix`](SERVICES.md) service. Home Assistant **migrates history** when an `entity_id` is renamed through the registry (same `unique_id`).

History is **not** guaranteed if:

- A **second** registry entry is created for the same logical entity with a **different** `unique_id` while the old `entity_id` is still taken → Home Assistant may assign `entity_id_2` (see [Discussion #54](https://github.com/TCzerny/ha-modbus-manager/discussions/54)).
- You change strategy and expect new ids **without** renaming or cleaning the registry — old `entity_id` values remain.
- Target `entity_id` already exists when running `add_entity_prefix` → that rename is skipped (logged as conflict).

## Existing installs and strategy changes

Changing **`entity_id_strategy`** in **Configure** (reconfigure) does **not** automatically rewrite all `entity_id` values in the entity registry.

1. **`unique_id`** is the match key. Stale cleanup after reconfigure only removes entities whose `unique_id` is **no longer** in the current template set — not every entity when strategy changes.
2. **`legacy_prefixed`** after **`legacy_unprefixed`**: code requests `sensor.sg_export_power`, but the registry may still show `sensor.export_power` until you run **`add_entity_prefix`** or remove/recreate entities.
3. **`ha_generated`**: integration does not force `entity_id`; HA may still assign names similar to unprefixed slugs depending on device/name settings. Calculated/binary templates should use **`[[mm:…]]`**, not hard-coded `sensor.sg_…` strings.

To **change** visible ids on an existing installation:

| Goal | Suggested path |
|------|----------------|
| Keep mkaiser / unprefixed names | `legacy_unprefixed`; avoid strategy churn |
| Move unprefixed → prefixed with history | `add_entity_prefix`, then set `legacy_prefixed` |
| Start clean with a new strategy | Remove Modbus Manager entry (or delete stale registry rows), reinstall, pick strategy on add device |

## mkaiser YAML migration (safe checklist)

Typical steps from the [migration guide](https://github.com/TCzerny/ha-modbus-manager/wiki/Migration-from-mkaiser):

1. **Backup** Home Assistant (including `.storage`).
2. **Remove** the mkaiser YAML Modbus configuration; **restart** Home Assistant so old entities are gone from the live system (registry rows may still exist until cleaned).
3. **Install** Modbus Manager and **add device** with **`entity_id_strategy: legacy_unprefixed`** (or legacy **Entity IDs without prefix: yes**).
4. **Verify** key entities: same `entity_id` as before (e.g. `sensor.export_power`), no unexpected `*_2` suffixes.
5. **Optional later:** run **`modbus_manager.add_entity_prefix`**, then switch device to **`legacy_prefixed`** so future reloads align with prefixed ids.

If you see duplicate entities or `*_2` ids, check the [unique_id comparison](https://github.com/TCzerny/ha-modbus-manager/wiki/Migration-mkaiser-unique-id-comparison) wiki and remove conflicting registry rows before re-adding the device.

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
- [Migration from mkaiser](https://github.com/TCzerny/ha-modbus-manager/wiki/Migration-from-mkaiser) – step-by-step migration
- [Discussion #54](https://github.com/TCzerny/ha-modbus-manager/discussions/54) – duplicate `*_2` entities after upgrade
- [SERVICES.md](SERVICES.md) – `add_entity_prefix` for controlled renames
