# Generic Device (PoC)

> **General documentation (Wiki):** [User Guide](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide) · [Template reference](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference) · [Local customization](https://github.com/TCzerny/ha-modbus-manager/wiki/Local-Customization)

> **Status:** Proof of concept in **1.3.0** (`feat/generic-device-poc`, [Discussion #100](https://github.com/TCzerny/ha-modbus-manager/discussions/100)). Same coordinator, optimizer, transport, and platforms as YAML devices. Coils/discrete, Jinja calculated sensors, Combined Device, and `dynamic_config` stay **out**.

A **Generic Modbus Device** is a UI-configured register map on a Modbus Manager hub. Rows are stored on the hub `devices[]` entry (sentinel template `__generic_device__`) and normalized into the same entity dicts a YAML template produces.

---

## Setup

1. **Settings → Devices & services → Add integration → Modbus Manager**.
2. Choose **Create a generic device**.
3. Connection (TCP or RTU) — the same screens as a YAML hub.
4. Prefix, slave ID, then add entities one by one.

On an **existing hub**: **Add device → Generic Modbus Device**. That uses the hub connection (no second TCP/RTU setup). A second generic device is another `devices[]` row.

The device card title is **Generic Modbus Device**.

---

## Options (after the hub exists)

Open the hub → **Configure**. Form radios (add / edit / remove / save, entity type, holding/input, category) follow the Home Assistant UI language (`en` / `de`). Stored YAML keys stay English.

| Menu | Purpose |
|------|---------|
| **Generic device — add or edit registers** | Add / edit / remove entities on that generic device |
| **Device options** | Prefix and slave ID |
| **Generic device — export YAML template** | Write a normal MM template and notify with a download link |
| **Connection** | Host, port, timing (hub-level) |
| **Reload register templates** | Hidden when the hub has **only** generic devices |

**Edit** keeps `unique_id` (recorder history). **Remove** drops the row from the generic map but does **not** purge the entity registry in this PoC.

---

## Always-on fields

`address` is the same number as YAML `address:` — the Modbus address we read, **no −1**.

| Field | Notes |
|-------|--------|
| `unique_id` | Stable slug (`a-z`, `0-9`, `_`). History key. Do not change later. |
| `name` | English display name when there is no `translation_key` |
| `address` | YAML address (e.g. SHx reactive power **5032**) |
| `input_type` | `holding` or `input` only |
| `data_type` | Extra fields (encoding, word swap, count) appear only when they apply |
| `scan_interval` | Seconds |
| `entity_category` | none / diagnostic / config |
| `icon`, `mm_group` | Optional |
| `translation_key` | Optional. See [Localization](#localization-translation_key) |
| `enabled_by_default` | Optional, default **on**. See [Disabled by default](#disabled-by-default) |

Platforms: `sensor`, `binary_sensor`, `number`, `switch`, `select`, `text`, `button`.

Pick **int32** vs **uint32** yourself. Word swap matches YAML (`swap: word` where the template uses it).

---

## Select, map, flags, bitmask

All three text maps are **one line, comma-separated**. Quotes around labels are optional. Hex keys (`0xCF`) store as integers like YAML (`207`).

### Select — `options`

Value written/read as the select option:

```
0xCF: Enabled, 0xCE: Shutdown
```

### Sensor — `map`

Whole register value → one label (not a bitmask):

```
0xAA: Enabled, 0x55: Disabled
```

or `170: Enabled, 85: Disabled`. Leave **Bitmask** empty.

### Sensor — `flags`

**Bit positions** → names. Several bits can be on at once (e.g. Running state):

```
0: PV Generating, 1: Battery charging, 2: Battery discharging, 3: Positive load power, 4: Exporting power to grid, 5: Importing power from grid, 7: Negative load power
```

Do not fill **map** and **flags** on the same sensor.

### Bitmask / bit position

Extracts **one** bit as a number. Different from map and flags.

---

## Localization (`translation_key`)

Optional on **YAML templates and Generic rows**. Without a key, YAML/`name` is the English label (existing templates unchanged).

```yaml
- name: Outdoor Air Temperature
  unique_id: outdoor_air_temperature
  translation_key: pichler_outdoor_air_temperature
```

Home Assistant looks up `entity.<platform>.<translation_key>.name` in this integration’s `translations/en.json` and `de.json`. Put the English string in **en.json** as well as YAML `name`. `unique_id` does not change.

Select/map **state** strings are not localized yet.

---

## Disabled by default

```yaml
enabled_by_default: false
```

Alias: `enable_default`. Default is **true**. Use `false` for installer/diagnostic entities so a new device is not flooded. This applies only when the entity is **first created**; existing registry rows keep their enabled flag.

---

## YAML export

**Options → Export YAML template**, or `modbus_manager.export_generic_device` (see [SERVICES.md](SERVICES.md#5-modbus_managerexport_generic_device)).

- Writes a normal device template to `config/modbus_manager/templates/` (`unique_id` suffixes unchanged).
- Persistent notification **Download YAML** is a **signed** `/api/modbus_manager/generic_export/…` link, valid **1 hour**.
- After a **full Home Assistant restart** (the HTTP view registers at setup), export again and use the new link. An unsigned `/api/` click looks like a failed login.
- Reload register templates, then add the file as a YAML device. No GitHub push.

Full template keys (`condition`, `valid_models`, `dynamic_config`, calculated sensors) are documented in the [Template reference (Wiki)](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference) — add those by hand after export if needed.

---

## History

`unique_id` is `generate_unique_id(prefix, template unique_id, name)` only. Never `entry_id_…`. Changing the display name or `translation_key` must not invent a second `unique_id`.

---

## Not in this PoC

Coils / discrete inputs, `dynamic_config` on the generic form, calculated/Jinja, Combined Device, extra registers on an existing **YAML** template device, auto-push to GitHub.
