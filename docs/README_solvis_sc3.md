## Solvis SC3 Heating Control Template

This document lists the Modbus registers for the Solvis SC2/SC3 template: `solvis_sc3.yaml`.

### Template Overview

- **Name**: Solvis SC3 Heating Control
- **Type**: `heating_control`
- **Default prefix**: `solvis`
- **Default slave ID**: `1`
- **Firmware**: `SC3`

### Dynamic Configuration

- `selected_model`: Solvis device model (options: ['SC2', 'SC3']) (default: SC3)
- `connection_type`: Connection type (options: ['TCP', 'RTU']) (default: TCP)

### Sensor Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Anzahl Heizkreise | anzahl_heizkreise | 2 | input | uint16 |  |  |  |
| Version SC3 | version_sc3 | 32770 | input | uint16 |  |  |  |
| Version NBG | version_nbg | 32771 | input | uint16 |  |  |  |
| Meldungen Anzahl | meldungen_anzahl | 33792 | input | uint16 |  |  |  |
| Brennermodulation Modus | brennermodulation_modus | 3840 | input | uint16 |  |  |  |
| Wärmepumpe Ladepumpe Modus | warmepumpe_ladepumpe_modus | 3845 | input | uint16 |  |  |  |
| Analog Out 3 Status | analog_out_3_status | 3850 | input | uint16 |  |  |  |
| Analog Out 4 Status | analog_out_4_status | 3855 | input | uint16 |  |  |  |
| Warmwasserpumpe Modus | warmwasserpumpe_modus | 3860 | input | uint16 |  |  |  |
| Analog Out 6 Status | analog_out_6_status | 3865 | input | uint16 |  |  |  |
| Temperatur S1 | temperatur_s1 | 33024 | input | int16 | °C | 0.1 |  |
| Temperatur S2 | temperatur_s2 | 33025 | input | int16 | °C | 0.1 |  |
| Temperatur S3 | temperatur_s3 | 33026 | input | int16 | °C | 0.1 |  |
| Temperatur S4 | temperatur_s4 | 33027 | input | int16 | °C | 0.1 |  |
| Temperatur S5 | temperatur_s5 | 33028 | input | int16 | °C | 0.1 |  |
| Temperatur S6 | temperatur_s6 | 33029 | input | int16 | °C | 0.1 |  |
| Temperatur S7 | temperatur_s7 | 33030 | input | int16 | °C | 0.1 |  |
| Temperatur S8 | temperatur_s8 | 33031 | input | int16 | °C | 0.1 |  |
| Temperatur S9 | temperatur_s9 | 33032 | input | int16 | °C | 0.1 |  |
| Temperatur S10 | temperatur_s10 | 33033 | input | int16 | °C | 0.1 |  |
| Temperatur S11 | temperatur_s11 | 33034 | input | int16 | °C | 0.1 |  |
| Temperatur S12 | temperatur_s12 | 33035 | input | int16 | °C | 0.1 |  |
| Temperatur S13 | temperatur_s13 | 33036 | input | int16 | °C | 0.1 |  |
| Temperatur S14 | temperatur_s14 | 33037 | input | int16 | °C | 0.1 |  |
| Temperatur S15 | temperatur_s15 | 33038 | input | int16 | °C | 0.1 |  |
| Temperatur S16 | temperatur_s16 | 33039 | input | int16 | °C | 0.1 |  |
| Raumtemperatur 1 | raumtemperatur_1 | 34304 | input | int16 | °C | 0.1 |  |
| Raumtemperatur 2 | raumtemperatur_2 | 34305 | input | int16 | °C | 0.1 |  |
| Raumtemperatur 3 | raumtemperatur_3 | 34306 | input | int16 | °C | 0.1 |  |
| Durchflussmenge S17 | durchflussmenge_s17 | 33040 | input | uint16 | L/min |  |  |
| Durchflussmenge S18 | durchflussmenge_s18 | 33041 | input | uint16 | L/min |  |  |
| Analog Eingang 1 | analog_eingang_1 | 33042 | input | uint16 | V | 0.1 |  |
| Analog Eingang 2 | analog_eingang_2 | 33043 | input | uint16 | V | 0.1 |  |
| Analog Eingang 3 | analog_eingang_3 | 33044 | input | uint16 | V | 0.1 |  |
| Digital Eingang Störungen | digital_eingang_stoerungen | 33045 | input | uint16 |  |  |  |

### Control Registers

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Zirkulation Betriebsart | zirkulation_betriebsart | 2049 | holding | uint16 |  |  |  |
| HKR1 Betriebsart | hkr1_betriebsart | 2818 | holding | uint16 |  |  |  |
| HKR2 Betriebsart | hkr2_betriebsart | 3074 | holding | uint16 |  |  |  |
| Warmwasser Solltemperatur | warmwasser_solltemperatur | 2305 | holding | uint16 | °C |  |  |
| HKR1 Fix Vorlauf Tag-Temperatur | hkr1_fix_vorlauf_tag_temperatur | 2820 | holding | uint16 | °C |  |  |
| HKR1 Fix Vorlauf Absenk-Temperatur | hkr1_fix_vorlauf_absenk_temperatur | 2821 | holding | uint16 | °C |  |  |
| HKR1 Heizkurve Tag-Temperatur 1 | hkr1_heizkurve_tag_temperatur_1 | 2822 | holding | uint16 | °C |  |  |
| HKR1 Heizkurve Tag-Temperatur 2 | hkr1_heizkurve_tag_temperatur_2 | 2823 | holding | uint16 | °C |  |  |
| HKR1 Heizkurve Tag-Temperatur 3 | hkr1_heizkurve_tag_temperatur_3 | 2824 | holding | uint16 | °C |  |  |
| HKR1 Heizkurve Absenk-Temperatur | hkr1_heizkurve_absenk_temperatur | 2825 | holding | uint16 | °C |  |  |
| HKR1 Heizkurve Steilheit | hkr1_heizkurve_steilheit | 2832 | holding | uint16 |  |  |  |
| HKR2 Fix Vorlauf Tag-Temperatur | hkr2_fix_vorlauf_tag_temperatur | 3076 | holding | uint16 | °C |  |  |
| HKR2 Fix Vorlauf Absenk-Temperatur | hkr2_fix_vorlauf_absenk_temperatur | 3077 | holding | uint16 | °C |  |  |
| HKR2 Heizkurve Tag-Temperatur 1 | hkr2_heizkurve_tag_temperatur_1 | 3078 | holding | uint16 | °C |  |  |
| HKR2 Heizkurve Tag-Temperatur 2 | hkr2_heizkurve_tag_temperatur_2 | 3079 | holding | uint16 | °C |  |  |
| HKR2 Heizkurve Tag-Temperatur 3 | hkr2_heizkurve_tag_temperatur_3 | 3080 | holding | uint16 | °C |  |  |
| HKR2 Heizkurve Absenk-Temperatur | hkr2_heizkurve_absenk_temperatur | 3081 | holding | uint16 | °C |  |  |
| HKR2 Heizkurve Steilheit | hkr2_heizkurve_steilheit | 3088 | holding | uint16 |  |  |  |
| HKR1 Warmwasser Vorrang | hkr1_warmwasser_vorrang | 2817 | holding | uint16 |  |  |  |
| HKR2 Warmwasser Vorrang | hkr2_warmwasser_vorrang | 3073 | holding | uint16 |  |  |  |
| Warmwasser Nachheizung Start | warmwasser_nachheizung_start | 2322 | holding | uint16 |  |  |  |

### Binary Sensors

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| DigIn Fehler | digin_fehler | 33045 | input | uint16 |  |  |  |
| Zirkulationspumpe (A1) | zirkulationspumpe_a1 | 33280 | holding | uint16 |  |  |  |
| Wärmepumpe Ladepumpe (A2) | warmepumpe_ladepumpe_a2 | 33281 | holding | uint16 |  |  |  |
| HKR1 Pumpe (A3) | hkr1_pumpe_a3 | 33282 | holding | uint16 |  |  |  |
| HKR2 Pumpe (A4) | hkr2_pumpe_a4 | 33283 | holding | uint16 |  |  |  |
| Ausgang A5 | ausgang_a5 | 33284 | holding | uint16 |  |  |  |
| Ausgang A6 | ausgang_a6 | 33285 | holding | uint16 |  |  |  |
| Ausgang A7 | ausgang_a7 | 33286 | holding | uint16 |  |  |  |
| HKR1 Mischer Heizkreis auf (A8) | hkr1_mischer_heizkreis_auf_a8 | 33287 | holding | uint16 |  |  |  |
| HKR1 Mischer Heizkreis zu (A9) | hkr1_mischer_heizkreis_zu_a9 | 33288 | holding | uint16 |  |  |  |
| HKR2 Mischer Heizkreis auf (A10) | hkr2_mischer_heizkreis_auf_a10 | 33289 | holding | uint16 |  |  |  |
| HKR2 Mischer Heizkreis zu (A11) | hkr2_mischer_heizkreis_zu_a11 | 33290 | holding | uint16 |  |  |  |
| Brennerstatus (A12) | brennerstatus_a12 | 33291 | holding | uint16 |  |  |  |
| Wärmepumpe Heizstab Stufe 2 & 3 (A13) | warmepumpe_heizstab_stufe_2_3_a13 | 33292 | holding | uint16 |  |  |  |
| Wärmepumpe Umschaltventil (A14) | warmepumpe_umschaltventil_a14 | 33293 | holding | uint16 |  |  |  |
| Analog Ausgang 1 Status | analog_ausgang_1_status | 3840 | input | uint16 |  |  |  |
| Analog Ausgang 2 Status | analog_ausgang_2_status | 3845 | input | uint16 |  |  |  |
| Analog Ausgang 3 Status | analog_ausgang_3_status | 3850 | input | uint16 |  |  |  |
| Analog Ausgang 4 Status | analog_ausgang_4_status | 3855 | input | uint16 |  |  |  |
| Analog Ausgang 5 Status | analog_ausgang_5_status | 3860 | input | uint16 |  |  |  |
| Analog Ausgang 6 Status | analog_ausgang_6_status | 3865 | input | uint16 |  |  |  |

### Calculated Sensors

| Name | Unique ID | Address | Input | Data | Unit | Scale | Condition |
|---|---|---|---|---|---|---|---|
| Solarthermie Leistung | solarthermie_leistung |  |  |  | kW |  |  |
| Solarkollektor Delta T | solarkollektor_delta_t |  |  |  | °C |  |  |
| Heizkreis 1 Delta T | heizkreis_1_delta_t |  |  |  | °C |  |  |
| Heizkreis 2 Delta T | heizkreis_2_delta_t |  |  |  | °C |  |  |
| Heizkreis 1 Leistung | heizkreis_1_leistung |  |  |  | kW |  |  |
| Heizkreis 2 Leistung | heizkreis_2_leistung |  |  |  | kW |  |  |
| Solar Effizienz | solar_effizienz |  |  |  | % |  |  |

### Notes

- Addresses are the base register offsets used by the integration.
- Conditions reflect template logic and are evaluated in the dynamic config.
