# TODO: Geplante Features

## ✅ Abgeschlossen
- [x] BASE Templates (Standards) implementieren
- [x] Template-Vererbung mit `extends` implementieren
- [x] SunSpec-Standard BASE Template erstellen
- [x] Hersteller-spezifische Mappings für SunSpec-konforme Geräte
- [x] SunSpec-Mappings für SMA, Fronius, Huawei und SolarEdge
- [x] Template-Loader für SunSpec-Modellstruktur erweitern
- [x] SunSpec-Template-Validierung implementieren

## 🔄 In Bearbeitung
- [ ] Modbus-Kommunikationsprobleme identifizieren und beheben
- [ ] SunSpec-Template-Tests implementieren

## 📋 Geplant
- [ ] Weitere BASE Templates (VDMA24247 für Wärmepumpen, etc.)
- [ ] UI-Verbesserungen für Template-Verwaltung
- [ ] Template-Versionierung und Update-Mechanismus
- [ ] Erweiterte Datenverarbeitung und Aggregation
- [ ] Performance-Monitoring und Optimierung
- [ ] SunSpec-Template-Validierung in der UI

## 📚 SunSpec-Implementierung

### ✅ SunSpec-konforme Hersteller (verwenden SunSpec-Standard)
- **SMA** - Sunny Boy, Tripower, Home Storage ✅
- **Fronius** - GEN24, Tauro ✅
- **Huawei** - Luna, FusionSolar ✅
- **SolarEdge** - HD Wave, StorEdge ✅

### ❌ Nicht SunSpec-konforme Hersteller (eigene Register)
- **Sungrow** - Eigene Modbus-Register (bereits implementiert in `sungrow_shx.yaml`)
- **Kostal** - Eigene Register
- **Growatt** - Eigene Register

### 🔧 SunSpec-Modellstruktur
- **Common Model (1)**: Geräteinformationen, Seriennummer, Firmware
- **Inverter Model (101/102/103)**: AC/DC-Leistung, Spannung, Strom, Temperatur
- **Storage Model (124)**: Batterie-Status, SOC, Ladeleistung
- **Meter Model (201/202/203)**: Netzbezug/-einspeisung, Energiezähler

### 📍 Register-Adressierung
- SunSpec verwendet relative Offsets innerhalb jedes Modells
- Absolute Adressen werden durch Modellbasis-Adressen + Offset berechnet
- Verschiedene Hersteller können unterschiedliche Basisadressen verwenden

### 🆕 Neue Template-Loader-Funktionen
- **`process_sunspec_model_structure()`**: Verarbeitet SunSpec-Modellstrukturen mit Offsets
- **`validate_sunspec_template()`**: Validiert SunSpec-Template-Struktur und Daten
- **`validate_custom_register()`**: Validiert Custom-Register in SunSpec-Templates
- **`validate_custom_control()`**: Validiert Custom-Controls in SunSpec-Templates
- **Automatische Adressberechnung**: Offset + Modellbasis-Adresse = Absolute Adresse
- **Modellinformationen**: Jedes Register erhält `model` und `model_offset` Informationen
- **Rückwärtskompatibilität**: Bestehende Templates funktionieren weiterhin

## 🚨 Bekannte Probleme
- Modbus-Kommunikationsfehler bei Sungrow-Geräten
- Langsame Entity-Updates
- Duplizierte Unique IDs (behoben)

## 📝 Nächste Schritte
1. ✅ Template-Loader für SunSpec-Modellstruktur aktualisiert
2. ✅ SunSpec-Template-Validierung implementiert
3. SunSpec-Template-Tests implementieren
4. Weitere SunSpec-konforme Hersteller hinzufügen
5. Modbus-Kommunikation optimieren
6. Performance-Monitoring implementieren

## 🔧 Technische Details

### SunSpec-Modellstruktur-Verarbeitung
```python
def process_sunspec_model_structure(base_template, model_addresses):
    """
    Verarbeitet SunSpec-Modellstrukturen:
    - Extrahiert Register aus jedem Modell
    - Berechnet absolute Adressen: Basis + Offset
    - Fügt Modellinformationen hinzu
    - Unterstützt register_mapping für Hersteller-spezifische Anpassungen
    """
```

### SunSpec-Template-Validierung
```python
def validate_sunspec_template(template_data, template_name):
    """
    Validiert SunSpec-Templates:
    - Prüft Pflichtfelder (extends, model_addresses)
    - Validiert Modelladressen
    - Validiert Custom-Register und -Controls
    - Gibt detaillierte Fehlermeldungen
    """
```

### Template-Format
```yaml
# SunSpec-Hersteller-Template
name: "Hersteller Name"
extends: "SunSpec Standard"
model_addresses:
  common_model: 40001
  inverter_model: 40069
  storage_model: 40187
  meter_model: 40277

# Optional: Register-Mappings für Hersteller-spezifische Adressen
register_mapping:
  "I_AC_Power": 40079  # Überschreibt berechnete Adresse

# Custom-Register und -Controls werden automatisch validiert
custom_registers:
  - name: "Custom Register"
    unique_id: "custom_register"
    address: 40093
    # ... weitere Eigenschaften
```


