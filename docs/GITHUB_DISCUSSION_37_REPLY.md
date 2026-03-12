# Draft Reply for GitHub Discussion #37

**Copy this to:** https://github.com/TCzerny/ha-modbus-manager/discussions/37

---

Hi @LucTs,

Thank you for your interest in Modbus Manager and for planning to migrate from the mkaiser YAML-based integration. We're glad you appreciate the native HA integration approach!

**We are actively working on a solution** to preserve history during migration. However, it's not straightforward. Here's why:

**The core challenge: entity_id differences**

- In Home Assistant, **history is tied to `entity_id`** (e.g. `sensor.battery_level`), not to `unique_id`.
- The mkaiser integration uses **entity names** (slugified) for entity_ids, e.g. `sensor.mppt1_voltage`, `sensor.battery_level`.
- Modbus Manager uses **prefixed unique_ids** by default, e.g. `sensor.sg_mppt1_voltage`, `sensor.sg_battery_level`.
- Because the entity_ids differ, history does not carry over automatically when switching integrations.

To retain history, the new entities must use the **same entity_ids** as the old ones—at least initially. That requires matching the entity_id format of the source integration.

**What we're implementing**

We're adding an **`entity_ids_without_prefix`** option. When enabled during device setup:
- Entity IDs will match the mkaiser format (e.g. `sensor.battery_level` instead of `sensor.sg_battery_level`).
- History and automations can continue to work without changes.
- After migration is complete, a service (`add_entity_prefix`) will allow you to add the prefix later and migrate history when renaming.

**Status**

The feature is implemented on the `feature/mkaiser-migration` branch and is ready for testing. We plan to release it soon, but we need more real-world testing to ensure it works reliably across different setups.

If you'd like to help test, you can try the branch and report any issues. The [Migration Guide](https://github.com/TCzerny/ha-modbus-manager/blob/main/docs/MIGRATION_mkaiser_to_modbus_manager.md) will be updated with the new flow once the feature is released.

Best regards
