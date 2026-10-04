# Pichler LG ES2020

This device template supports the documented ES2020 Modbus interface used by
Pichler LG ventilation units. It exposes documented measurements, status
values, diagnostics, and selected controls while allowing installed optional
equipment to be configured explicitly.

## Supported models

The Pichler Modbus workbook covers LG350, LG450, LG740, and LG1000. The
template retains an LG ES2020 family identity because the workbook does not
provide a complete per-model feature matrix. Hardware validation has been
performed on an LG350 only; accessory availability must not be inferred for
other models.

## Configuration

The default unique-ID prefix is `pichler_lg`. Select optional equipment only
when it is installed; these choices select documented equipment-dependent
entities and do not automatically detect hardware.

| Field | Values |
| --- | --- |
| `preheater_type` | `none` (default), `electric` |
| `post_heating_cooling_type` | `none` (default), `external_chilled_water_cooling_coil`, `external_combined_heating_cooling_water_coil` |

The two fields are independent. They deliberately use stable machine values so
that entity conditions do not depend on the Home Assistant UI language.

## Controls

The template provides a `Ventilation Level` select and airflow-setpoint number
controls for Level 1, Level 2, Level 3, and Basic ventilation. The documented
holding registers are FC3-readable and FC6-writable:

| Control | Holding register | Range |
| --- | ---: | --- |
| Ventilation Level | 2 | 0 Standby; 1--3 Levels; 4 Basic ventilation |
| Level 1 Airflow Setpoint | 9 | 0--1000 m³/h, step 1 |
| Level 2 Airflow Setpoint | 10 | 0--1000 m³/h, step 1 |
| Level 3 Airflow Setpoint | 11 | 0--1000 m³/h, step 1 |
| Basic Ventilation Airflow Setpoint | 12 | 0--1000 m³/h, step 1 |

Changing a writable value changes ventilation-unit operation. The workbook does
not document persistence or every operating-mode dependency.

## Optional heating and cooling equipment

An integrated electric preheater exposes T5 (input 34) and its documented T5
sensor and low-temperature faults (inputs 69 and 76). H2/input 16 is not
conditioned as a preheater signal because Pichler also documents it for EWT
pump/damper operation.

For an external chilled-water cooling coil, the template includes T6/input 4,
H5/input 18, Ao2/input 12, H11/input 28, and the T6 sensor fault/input 70.
For an external combined heating/cooling water coil, it includes T6/input 4,
H3/input 17, H5/input 18, Ao3/input 26, H11/input 28, and the T6 sensor
fault/input 70.

Ao2 and Ao3 are read-only 0--10 V controller command signals, not physical
valve-position feedback. Pichler assigns H10/input 27 to the separate external
hot-water post-heater and H11/input 28 to the external chilled-water cooling
coil; H11 is therefore the circulation-pump output used by the cooling and
combined-coil configurations. A separate hot-water post-heater option is not
modeled yet.

## Model identification

The diagnostic model register maps value 0 to LG350, 1 to LG450, and 2 to
LG740. The workbook does not provide an LG1000 value, so identification does
not select a template model automatically.

## Known limitations

- Optional-equipment compatibility outside the available LG350/LG450
  documentation is not confirmed for every model in the family.
- Inputs 80 and 108 have unresolved scope and are not conditioned on equipment.
- Air-quality and EWT/geothermal equipment are not modeled as configuration
  choices.
- Dynamic-configuration labels and template state labels currently use English;
  generic UI localization is a separate integration concern.

## Sources

- Pichler, `LIST_Modbus_ES2020_FW_LG350_LG450_LG740_LG1000_v2.1.0` Modbus
  workbook.
- Pichler LG350/LG450 installation and commissioning documentation, including
  the optional-equipment and ES2020 input/output sections.
