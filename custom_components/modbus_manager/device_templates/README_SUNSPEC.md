# SunSpec Standard Implementation

Diese Dokumentation beschreibt die Implementierung des SunSpec-Standards im Modbus Manager.

## Was ist SunSpec?

SunSpec ist ein offener Industriestandard für die Kommunikation mit Solar- und Energiesystemen. Er definiert eine einheitliche Modbus-Registerstruktur für verschiedene Gerätetypen.

## SunSpec-Modellstruktur

### Modell-IDs
- **1**: Common Model (Geräteinformationen)
- **101/102/103**: Inverter Model (Wechselrichter-Daten)
- **124**: Storage Model (Speicher-Daten)
- **201/202/203**: Meter Model (Zähler-Daten)

### Register-Adressierung
SunSpec verwendet relative Offsets innerhalb jedes Modells. Die absolute Adresse wird berechnet als:
```
Absolute Adresse = Modellbasis-Adresse + Offset
```

## Template-Struktur

### BASE Template (`sunspec_standard.yaml`)
Das BASE Template definiert die SunSpec-Modellstruktur mit allen Standardregistern und deren Offsets.

### Hersteller-Mappings
Hersteller-spezifische Templates erweitern das BASE Template mit:
- `extends: "SunSpec Standard"` - Verweis auf das BASE Template
- `model_addresses` - Modellbasis-Adressen für den jeweiligen Hersteller
- `custom_registers` - Herstellerspezifische Register
- `custom_controls` - Herstellerspezifische Steuerungen
- `calculated` - Berechnete Entitäten

## Verfügbare Templates

### BASE Templates
- `sunspec_standard.yaml` - SunSpec-Standard für PV-Wechselrichter

### Hersteller-Mappings
- `sma_sunspec_standard.yaml` - SMA Wechselrichter
- `fronius_sunspec_standard.yaml` - Fronius Wechselrichter
- `huawei_sunspec_standard.yaml` - Huawei Wechselrichter
- `solaredge_sunspec_standard.yaml` - SolarEdge Wechselrichter

## Template-Beispiel

```yaml
name: "Fronius Inverter (SunSpec Standard)"
extends: "SunSpec Standard"
version: 1
description: "Fronius Wechselrichter (GEN24, Tauro)"
manufacturer: "Fronius"
model: "GEN24/Tauro"

# SunSpec-Modellbasis-Adressen
model_addresses:
  common_model: 40001   # Common Model (1) beginnt bei 40001
  inverter_model: 40069  # Inverter Model (103) beginnt bei 40069
  storage_model: 40187   # Storage Model (124) beginnt bei 40187
  meter_model: 40277     # Meter Model (203) beginnt bei 40277

# Herstellerspezifische Register
custom_registers:
  - name: "System Time"
    unique_id: "system_time"
    address: 40093
    input_type: "holding"
    data_type: "uint32"
    count: 2
    # ... weitere Eigenschaften
```

## Verwendung

1. **BASE Template auswählen**: Wähle das passende BASE Template für dein Gerät
2. **Hersteller-Mapping erstellen**: Erstelle ein Mapping basierend auf dem BASE Template
3. **Modellbasis-Adressen anpassen**: Passe die Adressen an dein spezifisches Gerät an
4. **Custom Register hinzufügen**: Füge herstellerspezifische Register hinzu

## Vorteile

- **Standardisierung**: Einheitliche Registerstruktur für alle SunSpec-konformen Geräte
- **Wartbarkeit**: Änderungen am Standard werden automatisch übernommen
- **Erweiterbarkeit**: Einfaches Hinzufügen neuer Hersteller
- **Kompatibilität**: Funktioniert mit allen SunSpec-konformen Geräten

## Bekannte SunSpec-konforme Hersteller

- ✅ **SMA** - Sunny Boy, Tripower, Home Storage
- ✅ **Fronius** - GEN24, Tauro
- ✅ **Huawei** - Luna, FusionSolar
- ✅ **SolarEdge** - HD Wave, StorEdge

## Nicht SunSpec-konforme Hersteller

Diese Hersteller verwenden eigene Modbus-Register:
- ❌ **Sungrow** - Eigene Register (bereits implementiert in `sungrow_shx.yaml`)
- ❌ **Kostal** - Eigene Register
- ❌ **Growatt** - Eigene Register

## Nächste Schritte

1. **Template-Loader erweitern**: Unterstützung für SunSpec-Modellstruktur
2. **Weitere BASE Templates**: VDMA24247 für Wärmepumpen, etc.
3. **UI-Integration**: Template-Auswahl in der Konfiguration
4. **Validierung**: Automatische Validierung der SunSpec-Struktur

## Ressourcen

- [SunSpec Alliance](https://sunspec.org/) - Offizielle Spezifikationen
- [Home Assistant Modbus Integration](https://www.home-assistant.io/integrations/modbus/) - HA Modbus-Dokumentation
- [EVCC Project](https://github.com/evcc-io/evcc) - Referenz für SunSpec-Implementierungen
