# Home Assistant Modbus Manager

Ein modularer, template-basierter Modbus-Manager für Home Assistant mit Unterstützung für SunSpec-Standards.

## 🚀 Features

- **Template-basierte Konfiguration**: Geräte werden über YAML-Templates definiert
- **SunSpec-Standard-Unterstützung**: Vollständige Implementierung des SunSpec-Alliance-Standards
- **BASE-Template-Vererbung**: Templates können von BASE-Templates erben
- **Automatische Validierung**: SunSpec-Templates werden automatisch validiert
- **Modulare Architektur**: Einfach erweiterbar für neue Gerätetypen
- **Home Assistant Integration**: Vollständig in die HA-UI integriert
- **Aggregate-Sensoren**: Automatische Aggregation von Sensoren über mehrere Geräte hinweg
- **Berechnete Sensoren**: Template-basierte Berechnungen mit Jinja2
- **Options Flow**: Nachträgliche Konfiguration von Aggregate-Hubs über die UI

## 📚 SunSpec-Standard

### Was ist SunSpec?
SunSpec ist ein offener Industriestandard für die Kommunikation mit Solar- und Energiesystemen. Er definiert eine einheitliche Modbus-Registerstruktur für verschiedene Gerätetypen.

### Unterstützte SunSpec-Modelle
- **Common Model (1)**: Geräteinformationen, Seriennummer, Firmware
- **Inverter Model (101/102/103)**: AC/DC-Leistung, Spannung, Strom, Temperatur
- **Storage Model (124)**: Batterie-Status, SOC, Ladeleistung
- **Meter Model (201/202/203)**: Netzbezug/-einspeisung, Energiezähler

### SunSpec-konforme Hersteller
- ✅ **SMA** - Sunny Boy, Tripower, Home Storage
- ✅ **Fronius** - GEN24, Tauro
- ✅ **Huawei** - Luna, FusionSolar
- ✅ **SolarEdge** - HD Wave, StorEdge

### Nicht SunSpec-konforme Hersteller
- ❌ **Sungrow** - Eigene Modbus-Register (bereits implementiert)
- ❌ **Kostal** - Eigene Register
- ❌ **Growatt** - Eigene Register

## 🏗️ Template-Struktur

### BASE Templates
BASE Templates definieren Standards für verschiedene Gerätetypen:

```yaml
# custom_components/modbus_manager/device_templates/base_templates/sunspec_standard.yaml
name: "SunSpec Standard"
type: "base_template"
version: 1
description: "SunSpec Alliance Standard-Implementierung"

common_model:
  id: 1
  length: 66
  registers:
    - name: "C_SunSpec_ID"
      offset: 0
      length: 2
      data_type: "uint32"
      description: "SunSpec Common Model ID"
```

### Hersteller-Mappings
Hersteller-spezifische Templates erweitern BASE Templates:

```yaml
# custom_components/modbus_manager/device_templates/manufacturer_mappings/sma_sunspec_standard.yaml
name: "SMA Inverter (SunSpec Standard)"
extends: "SunSpec Standard"
version: 1
manufacturer: "SMA"
model: "Sunny Boy/Tripower/Storage"

# SunSpec-Modellbasis-Adressen
model_addresses:
  common_model: 40001
  inverter_model: 40069
  storage_model: 40187
  meter_model: 40277

# Herstellerspezifische Register
custom_registers:
  - name: "Operating Time"
    unique_id: "operating_time"
    address: 40093
    input_type: "holding"
    data_type: "uint32"
    count: 2
    unit_of_measurement: "h"
    state_class: "total_increasing"
```

## 🔧 Installation

1. **Repository klonen**:
   ```bash
   git clone https://github.com/TCzerny/ha-modbus-manager.git
   cd ha-modbus-manager
   ```

2. **Branch wechseln**:
   ```bash
   git checkout feature/base_templates
   ```

3. **In Home Assistant kopieren**:
   ```bash
   cp -r custom_components/modbus_manager /path/to/homeassistant/config/custom_components/
   ```

4. **Home Assistant neu starten**

5. **Integration hinzufügen**: Konfiguration → Integrationen → "Modbus Manager" hinzufügen

## 📁 Verzeichnisstruktur

```
custom_components/modbus_manager/
├── __init__.py
├── template_loader.py          # Template-Loader mit SunSpec-Unterstützung
├── sensor.py                   # Sensor-Entitäten
├── controls.py                 # Control-Entitäten
├── calculated.py               # Berechnete Sensoren
├── config_flow.py             # Konfigurations-UI
├── device_templates/
│   ├── base_templates/
│   │   └── sunspec_standard.yaml    # SunSpec BASE Template
│   ├── manufacturer_mappings/
│   │   ├── sma_sunspec_standard.yaml
│   │   ├── fronius_sunspec_standard.yaml
│   │   ├── huawei_sunspec_standard.yaml
│   │   └── solaredge_sunspec_standard.yaml
│   └── README_SUNSPEC.md      # SunSpec-Dokumentation
└── README.md                  # Diese Datei
```

## 🧪 Verwendung

### 1. Template auswählen
Wähle ein passendes Template für dein Gerät aus dem `manufacturer_mappings` Verzeichnis.

### 2. Konfiguration anpassen
Passe die Modellbasis-Adressen in `model_addresses` an dein spezifisches Gerät an.

### 3. Custom-Register hinzufügen
Füge herstellerspezifische Register in `custom_registers` hinzu.

### 4. Integration konfigurieren
Konfiguriere die Integration in Home Assistant mit den gewünschten Templates.

## 🔍 Template-Validierung

Der Template-Loader validiert automatisch alle SunSpec-Templates:

- **Pflichtfelder**: `extends`, `model_addresses`
- **Modelladressen**: Gültige Adressen für alle definierten Modelle
- **Custom-Register**: Vollständige Validierung aller Register-Eigenschaften
- **Custom-Controls**: Typ-spezifische Validierung für Controls

## 🚧 Bekannte Probleme

- Modbus-Kommunikationsfehler bei Sungrow-Geräten (nicht SunSpec-konform)
- Langsame Entity-Updates bei einigen Geräten
- Duplizierte Unique IDs (behoben)
- Aggregate-Sensoren zeigen Doppelzählung bei mehreren Wechselrichtern (erwartetes Verhalten)

## ✅ Behobene Probleme

- **IndentationError** in aggregates.py (behoben)
- **Logger-Verbosity** reduziert (INFO → DEBUG)
- **Unique ID Prefixes** für alle Entity-Typen implementiert
- **Self-Referencing** in Aggregate-Berechnungen verhindert
- **Options Flow** für Aggregate-Hubs implementiert
- **Deprecation Warnings** für Home Assistant 2025.12 behoben
- **Asyncio Blocking Warnings** durch Task-Optimierung behoben
- **Template Warnings** für erwartete Fälle auf DEBUG reduziert

## 🤝 Beitragen

1. **Fork** das Repository
2. **Feature-Branch** erstellen: `git checkout -b feature/amazing-feature`
3. **Änderungen committen**: `git commit -m 'Add amazing feature'`
4. **Branch pushen**: `git push origin feature/amazing-feature`
5. **Pull Request** erstellen

### Entwicklungsumgebung
- Python 3.9+
- Home Assistant 2023.8+
- YAML-Linting aktiviert

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe [LICENSE](LICENSE) Datei für Details.

## 🙏 Danksagungen

- **SunSpec Alliance** für den offenen Industriestandard
- **Home Assistant Community** für die großartige Plattform
- **EVCC Project** für Referenz-Implementierungen

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/TCzerny/ha-modbus-manager/issues)
- **Discussions**: [GitHub Discussions](https://github.com/TCzerny/ha-modbus-manager/discussions)
- **Wiki**: [GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)

---

**Letzte Aktualisierung**: Januar 2025  
**Version**: 2.1.0  
**Status**: Stable (Aggregate-Sensoren und Options Flow implementiert) 