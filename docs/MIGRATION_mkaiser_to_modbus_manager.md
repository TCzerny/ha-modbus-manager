# Migration Guide: mkaiser Sungrow Modbus → Modbus Manager SH Template

This guide helps you migrate from the [mkaiser Sungrow-SHx-Inverter-Modbus-Home-Assistant](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant) YAML-based integration to the **Modbus Manager** integration with the **Sungrow SHx Dynamic** template.

---

## ⚠️ Before You Start

**Always make a backup of your Home Assistant installation before migrating.**

- Use **Settings → System → Backups** to create a full backup
- Or back up at least: `configuration.yaml`, `secrets.yaml`, `.storage/`, and any custom `integrations/` or package files

---

## Entity ID and History Compatibility

### unique_id Alignment

The Modbus Manager SH template uses a **similar naming convention** for `unique_id`s as the mkaiser implementation, **without** the `sg_` prefix. The prefix is configured during setup. With prefix `sg`, many unique_ids align (e.g. `sg_mppt1_voltage`, `sg_daily_pv_gen_battery_discharge`). See [MIGRATION_mkaiser_unique_id_comparison.md](MIGRATION_mkaiser_unique_id_comparison.md) for a detailed comparison.

### entity_id Difference (Important)

| Integration | entity_id source | Example |
|-------------|------------------|---------|
| **mkaiser** (built-in Modbus) | Entity **name** (slugified) | "MPPT1 voltage" → `sensor.mppt1_voltage` |
| **Modbus Manager** (default) | **unique_id** (with prefix) | `sg_mppt1_voltage` → `sensor.sg_mppt1_voltage` |

**Entity IDs will not match** when using the default Modbus Manager setup. mkaiser uses names (e.g. `sensor.mppt1_voltage`), Modbus Manager uses prefixed unique_ids (e.g. `sensor.sg_mppt1_voltage`).

### History Retention with entity_ids_without_prefix (Optional)

To **preserve history** when migrating from integrations that use unprefixed entity_ids:

1. **Add device with `entity_ids_without_prefix: yes`** – Entity IDs will match the source integration (e.g. `sensor.battery_level`, `sensor.mppt1_voltage`). History carries over.
2. **After migration is complete**, call the service `modbus_manager.add_entity_prefix` to add the prefix to entity_ids (e.g. `sensor.battery_level` → `sensor.sg_battery_level`). Home Assistant migrates history when entity_ids are renamed.
3. **Set `entity_ids_without_prefix: no`** in the device configuration (via device reconfigure) so future reloads use prefixed entity_ids.

**Constraint:** Only safe for a **single** Sungrow SH device per hub. With multiple devices, unprefixed entity_ids would collide.

**Implementation details:** See [MIGRATION_mkaiser_unique_id_comparison.md](MIGRATION_mkaiser_unique_id_comparison.md) for unique_id vs entity_id alignment.

### Automations, Dashboards, Scripts

**Automations do not break** when entities are deleted—they keep their `entity_id` references. If the new entities use different entity_ids (as in default migration), those references will point to non-existent entities until you update them. There is no need to delete or disable automations before migration. After migration, update automations, dashboards, and scripts to use the new Modbus Manager entity_ids (e.g. `sensor.sg_mppt1_voltage` instead of `sensor.mppt1_voltage`).

With **entity_ids_without_prefix=yes**, entity_ids match the source integration initially, so automations continue to work without changes.

---

## Step 1: Remove the mkaiser Integration

### 1.1 Remove from configuration.yaml

1. Open **File Editor** or **VS Code** and edit `configuration.yaml`
2. Find the `homeassistant.packages` section that includes the mkaiser modbus file, e.g.:
   ```yaml
   homeassistant:
     packages:
       modbus_sungrow: !include integrations/modbus_sungrow.yaml
   ```
3. **Remove or comment out** the `modbus_sungrow` line:
   ```yaml
   # homeassistant:
   #  packages:
   #    modbus_sungrow: !include integrations/modbus_sungrow.yaml  # Removed for migration
   ```

### 1.2 Remove or rename the modbus_sungrow.yaml file

- **Option A:** Rename the file to avoid inclusion (e.g. `modbus_sungrow.yaml.bak`)
- **Option B:** Delete the file (only if you have a backup)

If you use a symlink to the mkaiser repo, remove the symlink and the package reference.

### 1.3 Restart Home Assistant

- Go to **Developer Tools → YAML → Check Configuration**
- If OK: **Developer Tools → YAML → Restart**

After the restart, the mkaiser Modbus entities will appear as **Unavailable**.

---

## Step 2: Clean Up Unavailable Entities

Before adding the Modbus Manager device, remove the old entities so the new ones can reuse the same entity IDs and history.

### 2.1 Find and delete unavailable entities

1. Go to **Settings → Devices & Services**
2. Open the **Entities** tab
3. Use the filters (top left):
   - **Status** → **Unavailable**
   - **Integration** → **Modbus**
4. Click the **selection mode** icon (checkbox icon next to the search bar)
5. Select the entities you want to remove (or use "Select all" if applicable)
6. Click the **three dots** menu (top right) → **Delete selected entities**

> **Note:** If you have multiple Modbus integrations, filter carefully to ensure you only delete Sungrow-related entities. You can also search for `sg_` in the entity list to narrow results.

### 2.2 Remove orphaned devices (optional)

If the Modbus integration no longer has any devices after cleanup:

1. Go to **Settings → Devices & Services**
2. Find the **Modbus** integration
3. If it shows a Sungrow device with no entities, you can delete the device via the device's three-dots menu → **Delete device**

> **Tip:** The mkaiser integration uses the built-in Home Assistant Modbus integration. If you have other Modbus devices, do **not** remove the Modbus integration itself—only the Sungrow-related entities and devices.

### 2.3 Restart Home Assistant again

- **Developer Tools → YAML → Restart**

This finalizes the cleanup and ensures no stale references remain.

---

## Step 3: Install and Configure Modbus Manager

### 3.1 Install Modbus Manager (if not already done)

- Via **HACS**: Search for "Modbus Manager" and install
- Or download from [Releases](https://github.com/TCzerny/ha-modbus-manager/releases) and copy to `custom_components/modbus_manager/`

Restart Home Assistant after installation.

### 3.2 Add the integration or a new hub

- **First time:** Go to **Settings → Devices & Services** → **Add Integration** → search for **Modbus Manager**
- **Already installed:** On the Modbus Manager card, click **Configure** → **Add hub** (or use the **+** button)

Follow the hub wizard to set connection type (TCP for LAN, RTU for serial), host, port, and timing (e.g. 5 ms for LAN, 20+ ms for WiNet-S).

### 3.3 Add the Sungrow SHx device

1. On the Modbus Manager hub card, click **+ Add device** (or **Configure** → **Add device**)
2. **Select the Sungrow SHx Dynamic template** (first step)
3. Enter connection details using **`sg`** as the Prefix and your inverter Slave ID (typically `1`)
4. Select your **model** from the dropdown (e.g. SH10RT, SH5.0RS)
5. Configure dynamic options: **Meter Type**, **Wallbox connected**, **Firmware**, **Connection type** (LAN/WINET), **Battery**, etc.
6. ⚠️ **VERY IMPORTANT – For history retention:** Set **Entity IDs without prefix** to **yes** (entity_ids will match source integration)
7. Save

---

## Step 4: Verify and Correct Entity IDs

### 4.1 Check devices and entities

1. Go to **Settings → Devices & Services**
2. Find your Modbus Manager hub and the new Sungrow device
3. Open the device and verify that entities are created and updating

### 4.2 (Optional) Add prefix after history retention

If you used **Entity IDs without prefix: yes**, entity_ids match the source integration and history is preserved. When you are ready to switch to prefixed entity_ids:

1. Call the service **`modbus_manager.add_entity_prefix`** with your config entry ID:
   ```yaml
   service: modbus_manager.add_entity_prefix
   data:
     entry_id: "<your-modbus-manager-config-entry-id>"
     # device_entry_id: "<device-subentry-unique_id>"  # Optional: for multi-device hubs, to target a specific device
   ```
   **Finding the entry_id:** In **Developer Tools → Services**, select `modbus_manager.add_entity_prefix`—the dropdown shows your hub(s) (e.g. "Modbus Hub (192.168.178.83:502)") with the config entry ID.
2. Entity IDs will be renamed (e.g. `sensor.battery_level` → `sensor.sg_battery_level`). Home Assistant migrates history automatically.
3. Set **Entity IDs without prefix** to **no** in the device configuration (device → Configure).

### 4.3 Update automations, dashboards, and scripts (if not using entity_ids_without_prefix)

If you did **not** use entity_ids_without_prefix, entity IDs will differ from the source integration (e.g. `sensor.sg_mppt1_voltage` instead of `sensor.mppt1_voltage`). You must update:

- **Automations** – Replace old entity_ids with the new Modbus Manager entity_ids
- **Dashboards** – Re-add or update entity cards
- **Scripts** – Update any `entity_id` references

You can find the new entity IDs under **Settings → Devices & Services → [your Modbus Manager device] → Entities**.

### 4.4 Update Energy Dashboard (if used)

If you use the Home Assistant Energy Dashboard, re-map the entities:

- **Grid consumption** → e.g. `Total imported energy`
- **Return to grid** → e.g. `Total exported energy`
- **Grid power** → e.g. `Meter active power`
- **Solar production energy** → e.g. `Total PV generation`
- **Solar production power** → e.g. `Total DC power`
- **Battery charged** → e.g. `Total battery charge`
- **Battery discharged** → e.g. `Total battery discharge`
- **Battery power** → e.g. `Battery discharging power signed`

Entity names may vary by template configuration; use the entity picker to select the correct ones.

---

## Summary Checklist

- [ ] Backup created
- [ ] mkaiser package removed from `configuration.yaml`
- [ ] `modbus_sungrow.yaml` removed or renamed
- [ ] Home Assistant restarted
- [ ] Unavailable Modbus entities deleted
- [ ] Home Assistant restarted again
- [ ] Modbus Manager installed (HACS or manual)
- [ ] Integration or new hub added (connection details)
- [ ] Sungrow SHx Dynamic template selected
- [ ] Device configured with prefix **`sg`**, model, meter type, wallbox, firmware, connection type (optionally **Entity IDs without prefix: yes** for history retention)
- [ ] Devices and entities verified
- [ ] Update dashboards, automations, and scripts to use new entity IDs (required)
- [ ] Energy Dashboard re-mapped if used

---

## References

- **mkaiser repository:** https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant
- **mkaiser cleanup guide:** [cleanup_entities.md](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant/blob/main/doc/cleanup_entities.md)
- **unique_id comparison (detailed):** [MIGRATION_mkaiser_unique_id_comparison.md](MIGRATION_mkaiser_unique_id_comparison.md)
- **Modbus Manager SH template docs:** [README_sungrow_shx_dynamic.md](README_sungrow_shx_dynamic.md)
- **Home Assistant entity registry:** [Entity registry documentation](https://developers.home-assistant.io/docs/entity_registry_index/)
