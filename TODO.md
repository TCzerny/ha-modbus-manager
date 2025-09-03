# TODO: Geplante Features

## ✅ Abgeschlossen
- [x] BASE Templates (Standards) implementieren
- [x] Template-Vererbung mit `extends` implementieren
- [x] SunSpec-Standard BASE Template erstellen
- [x] Hersteller-spezifische Mappings für SunSpec-konforme Geräte
- [x] SunSpec-Mappings für SMA, Fronius, Huawei und SolarEdge
- [x] Template-Loader für SunSpec-Modellstruktur erweitern
- [x] SunSpec-Template-Validierung implementieren
- [x] **Dynamic Template Configuration implementiert**
  - [x] ConfigFlow erweitert für dynamische Parameter
  - [x] Template-Filterung basierend auf Konfiguration
  - [x] Firmware-Kompatibilität (SAPPHIRE-H_03011.95.01)
  - [x] Sungrow SHx Dynamic Template v1.0.0 erstellt
- [x] **Float Conversion vollständig implementiert**
  - [x] IEEE 754 32-bit (float32) Support
  - [x] IEEE 754 64-bit (float64) Support
  - [x] Automatische count=2 für float32
  - [x] Byte-Order-Handling
- [x] **Services & Diagnostics implementiert**
  - [x] Performance Monitoring
  - [x] Register Optimization
  - [x] Built-in Services
  - [x] Diagnostics Panel

## 🔄 In Bearbeitung
- [x] Modbus-Kommunikationsprobleme identifizieren und beheben
- [ ] SunSpec-Template-Tests implementieren
- [x] Vereinfachte SunSpec-Templates implementieren (Fronius GEN24 Simple)

## 📋 Geplant
- [ ] Weitere BASE Templates (VDMA24247 für Wärmepumpen, etc.)
- [ ] UI-Verbesserungen für Template-Verwaltung
- [ ] Template-Versionierung und Update-Mechanismus
- [ ] Erweiterte Datenverarbeitung und Aggregation
- [ ] SunSpec-Template-Validierung in der UI
- [ ] **Dynamic Template Configuration erweitern**
  - [ ] Weitere Templates mit dynamischer Konfiguration
  - [ ] Tests für verschiedene Parameter-Kombinationen
  - [ ] UI-Verbesserungen für dynamische Parameter
- [ ] **🔤 Convert remaining German log messages and comments to English**
  - [ ] template_loader.py: ~15 more German error messages
  - [ ] config_flow.py: German messages and comments
  - [ ] sensor.py: German messages and comments
  - [ ] switch.py: German messages and comments
  - [ ] number.py: German messages and comments
  - [ ] select.py: German messages and comments
  - [ ] button.py: German messages and comments
  - [ ] text.py: German messages and comments
  - [ ] binary_sensor.py: German messages and comments
  - [ ] calculated.py: German messages and comments
  - [ ] aggregates.py: German messages and comments
  - [ ] performance_monitor.py: German messages and comments
  - [ ] register_optimizer.py: German messages and comments

## 📚 SunSpec-Implementierung

### ✅ SunSpec-konforme Hersteller (verwenden SunSpec-Standard)
- **SMA** - Sunny Boy, Tripower, Home Storage ✅
- **Fronius** - GEN24, Tauro ✅
- **Huawei** - Luna, FusionSolar ✅
- **SolarEdge** - HD Wave, StorEdge ✅

### ❌ Nicht SunSpec-konforme Hersteller (eigene Register)
- **Sungrow** - Eigene Modbus-Register (bereits implementiert in `sungrow_shx_dynamic.yaml` v1.0.0)
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
- Duplizierte Unique IDs (behoben)

## 📝 Nächste Schritte
1. ✅ Template-Loader für SunSpec-Modellstruktur aktualisiert
2. ✅ SunSpec-Template-Validierung implementiert
3. ✅ Vereinfachte SunSpec-Templates implementiert (Fronius GEN24 Simple)
4. SunSpec-Template-Tests implementieren
5. Weitere SunSpec-konforme Hersteller hinzufügen
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

### Vereinfachtes Template-Format (Neu)
```yaml
# Fronius GEN24 Simple Template
name: "Fronius GEN24 Simple"
extends: "SunSpec Standard"
model_addresses:
  common_model: 40001
  inverter_model: 40069
  storage_model: 40187
  meter_model: 40277

# Erforderliche Konfigurationsfelder
required_fields:
  - prefix      # Eindeutiger Prefix für alle Entities
  - name        # Anzeigename für das Gerät (optional)

# Automatisch generierte Sensoren basierend auf SunSpec-Standard
auto_generated_sensors:
  common_model:
    enabled: true
    groups: ["device_info"]
  inverter_model:
    enabled: true
    groups: ["PV_inverter_power", "PV_inverter_current"]
  storage_model:
    enabled: true
    groups: ["PV_battery_power", "PV_battery_soc"]

# Berechnete Sensoren (automatisch generiert)
calculated_sensors:
  - name: "Inverter Efficiency"
    state: >-
      {% set ac_power = states('sensor.{PREFIX}_ac_power') | default(0) | float %}
      {% set dc_power = states('sensor.{PREFIX}_dc_power') | default(0) | float %}
      {% if dc_power > 0 %}
        {{ (ac_power / dc_power * 100) | round(1) }}
      {% else %}
        0
      {% endif %}
```


