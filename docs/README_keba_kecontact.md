# KEBA KeContact P30 / P40

## Scope and validation status

Two independent **read-only** templates follow the existing wallbox architecture:

```text
custom_components/modbus_manager/device_templates/
  keba_kecontact_p30.yaml
  keba_kecontact_p40.yaml
docs/
  README_keba_kecontact.md
tests/
  test_keba_templates.py
```

These templates are documentation-verified, **not hardware-certified**. No KEBA
device or running Home Assistant instance was available for acceptance testing.
Do not treat the presence of a template as production field validation.
There are no core changes, custom entity platforms, external includes, new
dependencies, speculative registers, or write operations.

The requested template-only scope deliberately excludes controls the current
integration cannot represent correctly. In particular, **even buttons are polled**
by the current coordinator. Adding KEBA write-only registers as controls would
therefore generate unsupported FC03 reads. See the control mapping below.

## Sources and precedence

1. [Symcon KEBA overview](https://www.symcon.de/de/service/dokumentation/modulreferenz/geraete/keba/).
2. [KEBA P30 Modbus TCP Programmers Guide V1.03](https://www.symcon.de/media/pages/service/dokumentation/modulreferenz/geraete/keba/dafc7da7e7-1791206400/keba-p30-wallbox-modbus.pdf):
   requirements p.6, transport p.8, reads pp.9-15, writes pp.16-18.
3. [KEBA P40/P40 Pro Modbus TCP Programmers Guide V1.02, April 2025](https://www.symcon.de/media/pages/service/dokumentation/modulreferenz/geraete/keba/8ad234ed8e-1791206400/keba-p40-wallbox-modbus.pdf):
   transport pp.7-8, reads pp.9-19, writes pp.20-23, known bugs p.24.
4. [Symcon example JSON](https://www.symcon.de/media/pages/service/dokumentation/modulreferenz/geraete/keba/95f894dbf9-1791206400/kebamodbus_v1.json),
   used as a cross-check, not as a model-specific protocol specification.

The model-specific KEBA guides take precedence over the combined Symcon JSON.
The latter uses 0.0001 kWh energy scaling for both devices, includes P40-only
registers without model conditions, and gives unscaled failsafe current.
Those settings must not be copied blindly.

### Conflicts and unresolved information

- **P30 energy:** V1.03 explicitly specifies Wh for 1036 and 1502, including
  examples. Both use `scale: 0.001` to kWh. The Symcon JSON disagrees by factor 10.
  Verify against the installed P30 meter before recording statistics. No invented
  firmware threshold or arbitrary energy-scale selector is provided.
- **P40 energy:** V1.02 p.24 states firmware **below 1.2.1 reports Wh**, whereas
  **1.2.1 and newer reports 0.1 Wh**. This is implemented using the existing
  firmware profile and `sensor_replacements` mechanism.
- **P30 firmware:** V1.03 p.12 notes address **1013 for Modbus TCP version 1.11**,
  but normally specifies 1018. It does not give a reliable model/software-to-layout
  transition. Address 1013 would also overlap the documented 1012/1014 values.
  No speculative remapping is supplied. Sensor 1018 is disabled by default.
- **P30 firmware decoding:** example `50990336 = 0x030A0D00` is described as
  3.10.14 even though 0x0D is 13. Only the raw number is exposed; no misleading
  formatted firmware string is generated.
- **P30 failsafe:** headings specify 5018/5020, but their tables repeat 5016.
  The likely intended addresses are documented below as ambiguous, not implemented.
- **P40 phase switching and enable:** 1550, 1552, 5050, 5052 and 5014 are marked
  for a later software release. Neither P40 Pro branding nor firmware 1.2.1 proves
  support. No minimum version is invented.
- The guides provide no complete per-meter-variant availability matrix for the
  measurements. Templates follow the listed readable map; acceptance testing must
  check the installed metering equipment and firmware. Do not infer availability
  from the model name alone.

## Setup

1. Select **KEBA KeContact P30** or **KEBA KeContact P40** from the wallbox category
   and select the actual model.
   - P30: c-series **firmware >= 3.10.16**, or x-series **software >= 1.11**.
     Other P30 series are not covered by the guide.
   - P40: P40 and P40 Pro share this documented map, subject to installed options.
2. Use **native Modbus TCP**, TCP port **502**, Unit/Slave ID **255**.
   The generic Symcon overview mentions RS485, but these two source guides
   establish TCP support, not a corresponding RTU register contract.
3. P40: enable Modbus control in the KEBA app or through OCPP; it is normally off.
   P30: **do not run the UDP interface and Modbus TCP simultaneously**.
4. Set the hub **message wait to at least 500 ms**, preferably **600 ms** for the
   P30 recommendation of more than 0.5 seconds between requests. This setting is
   essential: scan groups alone do not space the individual reads within a cycle.
   KEBA permits only **one UINT32 value / two words per read**.
   Per-address `read_group` values enforce this even with the default optimizer
   limit of 64 words. No global optimizer change is necessary.
5. Keep normal scan groups (defaults: fast 10 s, medium 30 s, slow 600 s).
   Reading all registers takes several seconds; do not configure a fast cadence
   shorter than the transaction workload allows.
6. P40: select the **installed energy encoding profile before enabling Recorder**:
   - `1.0.0` means *installed firmware below 1.2.1*, not a claim that it is 1.0.0.
   - `1.2.1` means *installed firmware 1.2.1 or newer*.
   The default is 1.2.1. This is manual selection, **not auto-detection**.
7. Select `socket` only for socket hardware. `Plug Locked` is not created for an
   attached cable, which does not have the socket locking mechanism.
8. RFID defaults to excluded. Enable it only with RFID hardware and permission to
   record sensitive UID data. On P40 also enable RFID reading in the KEBA app.
   Exclude both RFID entities from Recorder if persistence is not wanted.
9. P40 phase registers default to excluded. Choose `confirmed` only when the
   installed hardware supports phase switching **and** register support is
   independently verified for the installed firmware.
10. P30: leave raw firmware disabled until the 1018 layout has been verified.

Modbus TCP has no authentication or encryption. Keep the wallbox on a trusted,
restricted local network; never expose port 502 to the Internet.

## Read-register mapping

Addresses below are **zero-based decimal protocol addresses**, without subtracting
one. All implemented physical reads use **FC03, UINT32, count 2, big endian,
no word swap, read-only**. Access to the `holding` register area does **not** imply
that the register is writable.

Notation: `-` means intentionally absent/not applicable, `diag` means diagnostic,
`M` = `measurement`, `TI` = `total_increasing`.
Every omitted numeric scale is 1. Entity IDs below are template-local `unique_id`
suffixes, not forced HA entity IDs. All mapped entities are sensors.

| Register | HA unique_id / meaning | Scale to HA | Unit | Device class | State class | Category | Poll | Model / availability |
|---|---|---:|---|---|---|---|---|---|
| 1000 | `charging_state_raw` | 1 | - | - | - | diag | fast | Both; codes 0-5 |
| 1004 | `cable_state_raw` | 1 | - | - | - | diag | fast | Both; codes 0,1,3,5,7 |
| 1006 | `error_code` | 1 | - | - | - | diag | fast | Both; meaningful during charging state 4 |
| 1008 | `current_l1` | 0.001 | A | current | M | - | fast | Both |
| 1010 | `current_l2` | 0.001 | A | current | M | - | fast | Both; unused phase may report zero |
| 1012 | `current_l3` | 0.001 | A | current | M | - | fast | Both; unused phase may report zero |
| 1014 | `serial_number` | 1 | - | - | - | diag | slow | Both; decimal serial, not ASCII |
| 1016 | `product_type_and_features` | 1 | - | - | - | diag | slow | Both; different model-specific decimal encodings |
| 1018 | `firmware_version_raw` | 1 | - | - | - | diag | slow | Both; P30 disabled by default, see conflict above |
| 1020 | `active_power` | 0.001 | W | power | M | - | fast | Both; raw mW |
| 1036 | `total_energy` | P30 0.001; P40 <1.2.1 0.001, >=1.2.1 0.0001 | kWh | energy | TI | - | medium | Both; persistent cumulative meter |
| 1040 | `voltage_l1` | 1 | V | voltage | M | - | fast | Both |
| 1042 | `voltage_l2` | 1 | V | voltage | M | - | fast | Both |
| 1044 | `voltage_l3` | 1 | V | voltage | M | - | fast | Both |
| 1046 | `power_factor` | 0.1 | % | power_factor | M | - | fast | Both; 928 = 92.8%, not 0.928% |
| 1100 | `maximum_charging_current` | 0.001 | A | current | M | - | fast | Both; effective maximum, not an echoed user setpoint |
| 1110 | `supported_charging_current` | 0.001 | A | current | M | - | fast | Both; installation/cable/temperature limit |
| 1200 | `fast_charging_status` | 1, mapped | - | - | - | - | fast | P40 only; active prevents Modbus current control |
| 1500 | `rfid_card_raw` | 1 | - | - | - | diag | slow | Both; RFID opt-in; first 4 UID bytes only |
| 1502 | `session_energy` | Same firmware-dependent scale as 1036 | kWh | energy | TI | - | medium | Both; resets per charging session |
| 1550 | `phase_switching_source` | 1, mapped | - | - | - | diag | medium | P40 only; confirmed hardware/firmware opt-in |
| 1552 | `phase_switching_state` | 1, mapped | - | - | - | - | medium | P40 only; confirmed hardware/firmware opt-in |
| 1600 | `failsafe_current_setting` | 0.001 | A | current | M | diag | medium | P40 only; not documented as readable for P30 |
| 1602 | `failsafe_timeout_setting` | 1 | s | duration | M | diag | medium | P40 only |
| 1700 | `hardware_revision_device` | 1 | - | - | - | diag | slow | P40 only |
| 1702 | `hardware_revision_ms10` | 1 | - | - | - | diag | slow | P40 only; KC-MS10 revision |

P30 1110 may report **6 A with no cable attached**, rather than the installation
maximum. P40 1552 means single-phase in use (1), or three-phase **possible** (3);
it is not an indication that a transition is currently running.

### Derived entities

These perform no extra Modbus reads. They use the existing `calculated` and
`binary_sensors` sections with registry-safe `[[mm:sensor:{PREFIX}_...]]` references.
Unknown, unavailable and undocumented state codes fail availability checks,
rather than silently presenting a healthy/off state.

| Source | Entity | Type | Device class / category | Semantics |
|---|---|---|---|---|
| 1000 | `charging_state` | sensor | - / - | 0 Starting, 1 Not ready, 2 Ready, 3 Charging, 4 Error, 5 Suspended |
| 1004 (+1016 on P40) | `cable_state` | sensor | - / - | Descriptive cable state; P40 attached-cable codes 3/7 do not claim locking |
| 1018 | `firmware_version` | sensor | - / diagnostic | P40 only: 10000 = 1.0.0, 10201 = 1.2.1 |
| 1500 | `rfid_uid_prefix` | sensor | - / diagnostic | Both, RFID opt-in; 8 uppercase hex digits; zero unavailable |
| 1004 | `vehicle_connected` | binary_sensor | plug / - | On for 5 or 7; vehicle connectivity, not vehicle SoC |
| 1000 | `charging_active` | binary_sensor | running / - | On only for 3 |
| 1000 | `error_present` | binary_sensor | problem / diagnostic | On only for 4; avoids interpreting a retained error code as a live error |
| 1004 | `plug_locked` | binary_sensor | - / - | Socket only; on for 3 or 7; uses lock icon, **not** HA `lock` class (which means on = unlocked) |

Derived entities have no scale, unit, state class, function code or write access.
The P40 cable text uses the documented connector digit of 1016; it is unavailable
until that value is readable. The manually selected connector option gates the
socket-only binary sensor and must match the physical device.

## Documented commands deliberately not instantiated

**All entries here are UINT16, one word, FC06, write-only. None are read/write.**
Scale describes raw-to-display conversion for a future supported entity; there is
no implemented control with these metadata. Proposed config controls would use
category `config`, no state class; actions would have no unit/device/state class.

| Register | Requested / possible entity | Scale / unit / proposed class | P30 | P40 | Why absent / constraints |
|---|---|---|---|---|---|
| 5004 | Number Max Charging Current | 0.001 A / current | 6000-63000 mA | 0 or 6000-32000 mA | WO, no exact setpoint readback; 1100 is effective current, not an equivalent echo; P40 0 suspends |
| 5010 | Number Session Energy Limit | 0.01 kWh / energy | Current or next session | Current session; 0 removes limit | WO; no readable limit; uint16 maximum corresponds to 655.35 kWh |
| 5012 | Button Unlock Cable | 1 / - | Write 0, only after stopping/suspending | Write 0; stops current session and unlocks | Current coordinator polls buttons; no fake readback or automatic stop/unlock sequence |
| 5014 | Enable State select / Enable Charger switch; enable/disable buttons | 1 / - | 0 disable, 1 enable | Same values; future unspecified firmware | WO; charging state is not an enable-state echo; buttons also polled |
| 5016 | Number Failsafe Current | 0.001 A / current | 0 or 6000-32000 mA | Same | P40 readback 1600 uses another address and UINT32, unsupported by current Number contract |
| 5018 | Number Failsafe Timeout | 1 s / duration | 0 or 10-600 s; table typo repeats 5016 | 0 or 5-600 s | P30 ambiguity; P40 readback 1602 has different address/type |
| 5020 | Button Persist Failsafe | 1 / - | Write 1 per heading; table typo repeats 5016 | Not documented | Ambiguous P30 address; not a general reset or restart |
| 5050 | Select Phase Switching Mode/source | 1 / - | Not documented | 0 off, 1 profiles, 2 REST, 3 Modbus | Future unspecified firmware; separate UINT32 readback 1550 |
| 5052 | Trigger Phase Switch / explicit phase actions | 1 / - | Not documented | 0 single-phase, 1 three-phase | Future firmware; requires 5050=3; not a generic toggle; readback 1552 has values 1/3 |
| 5200 | Button Activate Fast Charging | 1 / - | Not documented | Write 1 only | Cannot deactivate via Modbus; cannot be a truthful Smart Charging switch |

Do not substitute FC16 for FC06, or read a command address to manufacture its
state. Failsafe current and timeout have disjoint valid ranges (0 **or** a
positive interval); a continuous Number slider would permit invalid values.
Current limits must never exceed the installation, cable and hardware ratings.
Do not use a template control to change installation protection settings.

P40 failsafe timeout is refreshed by **Modbus requests**, not necessarily a fresh
EMS control decision. Read-only polling may keep an externally configured EMS
watchdog alive even when the controller stops updating current limits. Coordinate
ownership with the EMS; this template is not a watchdog safety controller.

## Requested entities without a documented equivalent

| Request | Evidence / decision |
|---|---|
| Device Temperature | No temperature register in either source guide; charging state 5 does not identify temperature alone |
| Vehicle status beyond connection / charging | No vehicle SoC, battery, model or control-pilot state register documented |
| Communication Status | No KEBA register documented; use normal integration availability/hub diagnostics, not a fabricated device register |
| External Enable binary sensor | No readable external-enable input documented; 5014 is a WO command |
| Phase Switching Active binary sensor | 1552 reports available/in-use phases, not a transition-in-progress flag |
| Charging Mode select | No general charging-mode register documented; fast charging is a separate P40 one-way command |
| Restart Charging Session button | No restart-session command; stop then enable is not guaranteed to restart a session and would require sequencing |
| Reset Errors button | No reset-error register documented |
| Remote Control switch | No corresponding readable/writable register documented |
| Smart Charging switch | No two-way smart-charging register; do not relabel P40 fast charging as Smart Charging |
| Full RFID UID / authorization identity | Only the first four UID bytes are available, not a unique full-card identity or authentication proof |

## Identity, device information and Home Assistant statistics

- Local suffixes are unique across all sections. The existing coordinator prefixes
  them with `keba_p30` / `keba_p40` (or the user-selected device prefix).
  **Choose a distinct prefix per physical wallbox**, including two P40 devices.
  References resolve through the entity registry and survive entity-ID renaming.
- Manufacturer and selected model feed the normal device factory; the existing
  hub/device-entry identifier provides stable device association. Serial, product
  code and actual firmware are diagnostic entities, not invented static values.
- **Existing core limitation:** arbitrary YAML sensors are not bound to device
  registry `serial_number`, `hw_version` or live wallbox `sw_version`. The core's
  automatic live firmware updater only handles inverter/battery roles. P30 leaves
  static firmware blank; P40's registry firmware is the chosen **profile floor**,
  not necessarily the installed release. Use the P40 live firmware sensor for the
  actual value. Fully dynamic DeviceInfo requires a separate core enhancement.
- `total_energy` uses kWh, `energy`, `total_increasing`: suitable for the Energy
  Dashboard's individual device consumption and long-term statistics.
- `session_energy` uses `total_increasing`: register 1502 reports transferred
  energy accumulated during the current charging session, increasing within that
  session and restarting for the next one. Home Assistant can therefore treat a
  decrease as a new meter cycle, rather than negative energy consumption.
  `total` without `last_reset` would incorrectly subtract the previous session's
  energy at the reset; removing the state class would unnecessarily disable
  long-term statistics. No explicit `last_reset` is needed for `total_increasing`.
  See [Home Assistant's state-class guidance](https://developers.home-assistant.io/docs/core/entity/sensor/#how-to-choose-state_class-and-last_reset).
  Use `total_energy` as the preferred Energy Dashboard consumption meter: do not
  add both counters for the same wallbox and double-count consumption. Session
  resets missed between polls can hide consumption from the session counter.
  Correct previously recorded negative session statistics explicitly; changing
  the state class does not repair historical data.
- Power/current/voltage/power factor use `measurement`, enabling long-term
  statistics. Raw status/identity/RFID sensors have no statistics state class.
- After a P40 firmware upgrade crossing 1.2.1, pause Recorder, change the profile
  and reload before resuming. Otherwise a factor-10 discontinuity can corrupt
  lifetime statistics. Fix any already-recorded incorrect statistics explicitly.

## Focused improvements for a later core PR

1. Exclude write-only actions from polling **and post-write readback**, and
   propagate failed writes to HA service errors rather than only logging them.
2. Define separate read/write addresses, types, counts and scales for controls;
   compare requested values only against semantically equivalent readback.
3. Support write-only numbers/selects explicitly without claiming confirmed state,
   disjoint allowed ranges, hardware current limits, and documented write spacing
   of at least 5 seconds. Do not implement hidden heartbeat writes.
4. Add per-device register-backed DeviceInfo bindings, with tested model-specific
   formatting and no leakage between devices.
5. Obtain current KEBA release notes for phase registers, the P30 firmware layout
   transition, the P30 failsafe errata and meter/firmware-specific energy units.

## Validation and hardware acceptance

Focused checks use the repository's lightweight `unittest` pattern:

```bash
python3 -m unittest discover -s tests -p test_keba_templates.py -v
```

Tests execute the production loader validation, optimizer, UINT32 decoding,
value processing, condition evaluator and version-replacement helpers, rather than
reimplementing them. Jinja tests cover cable/lock truth tables, unavailable data,
RFID prefix, P40 firmware formatting and the 1.2.1 energy boundary.
They do not replace a running Home Assistant or actual wallbox test.

### P40 stored-profile normalization regression cases

The tests also execute the production path used by the coordinator:
stored profile -> `resolve_firmware_profile_version()` ->
`apply_version_replacements()` -> UINT32 decoding and final kWh scaling.
Both `total_energy` and `session_energy` are checked for every case.

| Stored profile | Normalized profile | Scale to kWh | Precision |
|---|---|---:|---:|
| `1.0.0` | `1.0.0` | 0.001 | 3 |
| `1.2.0` | `1.2.1` | 0.0001 | 4 |
| `1.2.1` | `1.2.1` | 0.0001 | 4 |
| `1.3.0` | `1.2.1` | 0.0001 | 4 |
| `None` (missing) | `1.2.1` | 0.0001 | 4 |

This documents the **existing fallback**, not automatic firmware detection or a
change to normalization. Only `1.0.0` and `1.2.1` are valid selectable profiles.
Other stored values fall back to the default `1.2.1` before replacements run.
In particular, storing the actual firmware string `1.2.0` would select the wrong
scale for that device; select profile `1.0.0` for installed firmware below 1.2.1.
The separate replacement-helper boundary test does not include normalization;
the end-to-end profile test prevents mistaking its result for runtime behavior.

The session-reset regression also checks a positive-to-zero-to-positive sequence
through production decoding and verifies that the existing sensor helper does
not suppress a valid reset with `total_increasing`. Recorder's actual sum
calculation still requires Home Assistant acceptance testing.

Before production use:

- Capture FC03 requests: address equals the documented index, count always 2,
  Unit ID 255, no requests to 5000+, >=500 ms between transactions.
- Compare serial, firmware, current, voltages, power and both energies against the
  wallbox/app/meter; specifically rule out a factor-10 energy error.
- Test unplugged, station-only, vehicle-connected, locked, charging and suspended
  states on the installed connector variant.
- Disconnect/reconnect the network and verify entity unavailability/recovery.
  Per-register stale-data behavior is governed by the existing coordinator.
- Verify optional RFID/phase registers are not read by default and only enabled
  after hardware/firmware confirmation.
- Add two wallboxes with different prefixes, restart HA, rename entities, and
  verify calculated dependencies and device associations remain correct.
- Verify Energy Dashboard eligibility and Recorder statistics without unit or
  state-class warnings. Confirm a new charging session does not affect the
  lifetime meter.
