"""Display labels for dynamic_config dropdowns.

Stored option keys stay as in YAML. vol.In shows dict values, which Home
Assistant does not load from translations JSON when keys are not slugs
(WINET, 1.0.0). Same pattern as generic_device form radios.
"""

from __future__ import annotations

from typing import Any

from .generic_device import generic_ui_language

# field -> option value as str -> German label
_DE_BY_VALUE: dict[str, dict[str, str]] = {
    "preheater_type": {
        "none": "Keine integrierte Vorheizung",
        "electric": "Integrierte elektrische Vorheizung",
    },
    "post_heating_cooling_type": {
        "none": "Kein externes Wasserregister",
        "external_chilled_water_cooling_coil": "Externes Kaltwasser-Kühlregister",
        "external_combined_heating_cooling_water_coil": "Externes kombiniertes Heiz-/Kühlregister",
    },
    "connector_type": {
        "cable": "Festes Kabel",
        "socket": "Steckdose",
    },
    "rfid": {
        "unavailable": "RFID-Informationen nicht lesen",
        "enabled": "RFID-Informationen lesen (sensible Daten)",
    },
    "phase_switching_registers": {
        "unavailable": "Nicht bestätigt (nicht lesen)",
        "confirmed": "An diesem Gerät bestätigt",
    },
    "battery_config": {
        "none": "Keine Batterie",
        "battery": "Batterie angeschlossen",
        "sbr_battery": "SBR/SBH-Batterie",
        "standard_battery": "Standardbatterie",
        "fronius_battery": "Fronius-Batterie",
        "solax_battery": "SolaX-Batterie",
    },
    "charger_region": {
        "EU": "Europa (Modi 160–163)",
        "AU": "Australien (Modi 164–167)",
    },
    "protocol_version": {
        "1.0.0": "V1.0.0 — erste Karte",
        "1.0.1": "V1.0.1 — Zählerkanal 2, App-Softwareversion, Wirkleistungsgrenze; Einspeiseverhältnis S32",
        "1.0.2": "V1.0.2 — Einspeisebegrenzung aktivieren (8028); Einspeiseverhältnis S16",
    },
    "connection_type": {
        "LAN": "Dedizierter Ethernet-Anschluss am Wechselrichter (RJ45)",
        "WINET": "WiNet-S — WLAN oder Kabel zum Dongle (auch LAN-Port des Dongles)",
        "RS485": "Modbus-TCP-Gateway am RS485-Port (A1/B1), z. B. WaveShare — kein natives serielles RTU",
        "WiFi": "WLAN",
        "TCP": "TCP",
        "RTU": "RTU",
    },
    "entity_id_strategy": {
        "legacy_prefixed": "Entity-ID mit Präfix (Standard, z. B. sensor.sg_export_power)",
        "legacy_unprefixed": "Entity-ID ohne Präfix (Migration ohne Präfix; danach Dienst add_entity_prefix)",
        "ha_generated": "Home Assistant vergibt die Entity-ID ([[mm:domain:unique_id]] in Templates für Querverweise)",
    },
    "display": {
        "Yes": "Ja",
        "No": "Nein",
    },
    "wallbox_connected": {
        "yes": "Ja",
        "no": "Nein",
    },
    "meter_type": {
        "None": "Keiner",
        "DTSU666": "DTSU666",
        "DTSU666-20": "DTSU666-20",
    },
}

# Same English YAML label used on several firmware option keys.
_DE_BY_ENGLISH: dict[str, str] = {
    "Default profile — recommended if unsure": "Standardprofil — empfohlen, falls unsicher",
    "Installed firmware below 1.2.1 (Wh)": "Installierte Firmware unter 1.2.1 (Wh)",
    "Installed firmware 1.2.1 or newer (0.1 Wh)": "Installierte Firmware 1.2.1 oder neuer (0,1 Wh)",
    "Data type changes (03011.95.10)": "Datentyp-Änderungen (03011.95.10)",
    "No battery": "Keine Batterie",
    "Battery connected": "Batterie angeschlossen",
}


def flow_option_label(
    field_name: str | None,
    value: Any,
    fallback: str,
    hass: Any | None = None,
) -> str:
    """German dropdown label when the UI language is de; otherwise YAML English."""
    if generic_ui_language(hass) != "de":
        return fallback
    if field_name:
        mapped = _DE_BY_VALUE.get(field_name, {}).get(str(value))
        if mapped:
            return mapped
    return _DE_BY_ENGLISH.get(fallback, fallback)


def localize_dynamic_options(
    field_name: str | None,
    options: Any,
    hass: Any | None = None,
) -> Any:
    """Return vol.In mapping: stored keys unchanged, values are UI labels."""
    if isinstance(options, dict):
        return {
            key: flow_option_label(field_name, key, str(label), hass)
            for key, label in options.items()
        }
    if isinstance(options, (list, tuple)):
        return {
            item: flow_option_label(field_name, item, str(item), hass)
            for item in options
        }
    return options
