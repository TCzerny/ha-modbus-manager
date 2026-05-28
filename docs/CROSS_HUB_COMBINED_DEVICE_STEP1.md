# Cross-hub Combined Device (Step 1 Design)

## Goal

Provide an opt-in virtual combined device that can aggregate data from two existing Modbus Manager hub entries, without changing behavior for users that do not enable it.

Supported pairs:
- Inverter + iHomeManager
- Inverter + Inverter

## Chosen architecture

Use a dedicated `combined_device` config entry (virtual third entry) that references two existing hub entries by `entry_id`.

Rationale:
- Clear separation from normal hub setup
- Explicit user consent and easy disable/remove
- Low risk for existing polling and template handling

## Data model (config entry)

New entry type marker and references:
- `entry_type: "combined_device"`
- `source_entry_id_a: "<entry_id>"`
- `source_entry_id_b: "<entry_id>"`
- `combination_type: "inverter_ihm" | "inverter_inverter"`
- `combined_prefix: "<prefix>"`
- `enabled_entities: [...]` (optional, future filtering)

Constraints:
- `source_entry_id_a != source_entry_id_b`
- both source entries must exist and belong to `modbus_manager`
- selected pair must match one supported combination type
- `combined_prefix` must be globally unique across hubs/devices

## ConfigFlow UX (opt-in)

New flow path:
1. User opens "Add integration" and chooses "Combined Device (cross-hub)".
2. Flow lists eligible existing entries/devices.
3. User picks source A and source B.
4. Flow validates supported pair type.
5. User confirms default combined prefix (editable).
6. Flow creates the virtual `combined_device` entry.

Validation and errors:
- No eligible entries -> abort reason `no_eligible_sources`
- Invalid pair type -> form error `invalid_pair`
- Duplicate prefix -> abort `already_configured`
- Missing source on submit -> form error `source_not_found`

## Runtime design

Add a small `CombinedDeviceCoordinator` that:
- resolves both source coordinators from `hass.data[DOMAIN]`
- reads required source entity values from coordinator caches
- computes combined values
- exposes computed data to combined entities

No additional Modbus I/O should be performed by combined entry itself.

## Availability and fallback behavior

Combined entity availability rules:
- both sources available -> all combined entities available
- one source unavailable -> only entities depending on both become unavailable
- source-specific entities can stay available if dependency graph allows
- both unavailable -> all combined entities unavailable

Recovery:
- automatic recovery when source coordinators refresh again
- no manual reload required

## Entity and device registry model

Combined entry creates its own HA device:
- identifiers include `combined_prefix` and source entry IDs
- entities belong to combined entry and combined device only
- source entries remain untouched

## Non-goals for step 1

- No full implementation of all combined metrics
- No UI customization beyond basic ConfigFlow fields
- No migration of old entries (feature is opt-in only)

## Definition of done for step 1

- Architecture and data model documented
- ConfigFlow path and validations specified
- Availability/fallback behavior specified
- Clear implementation plan for step 2

## Step 2 implementation outline

1. Add constants + entry type handling in setup/unload.
2. Implement ConfigFlow branch for `combined_device`.
3. Implement `CombinedDeviceCoordinator` (cache-only reads).
4. Add first minimal combined sensor set for both pair types.
5. Add tests for pair validation and availability transitions.
6. Document user setup and troubleshooting.
