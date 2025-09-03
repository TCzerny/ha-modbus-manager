# Fronius GEN24 Simple Template

## Übersicht

Das **Fronius GEN24 Simple Template** ist ein vereinfachtes Template für Fronius GEN24 Wechselrichter, das auf dem SunSpec-Standard basiert. Es erfordert nur minimale Konfiguration und generiert automatisch alle SunSpec-Register als Sensoren.

## Features

- ✅ **Minimale Konfiguration**: Nur Prefix und optional Name erforderlich
- ✅ **Automatische Sensor-Generierung**: Alle SunSpec-Register werden automatisch erstellt
- ✅ **Berechnete Sensoren**: Automatische Effizienz- und Leistungsberechnungen
- ✅ **Gruppierung**: Sensoren werden automatisch in logische Gruppen eingeteilt
- ✅ **Prefix-Unterstützung**: Eindeutige Entity-Namen mit User-Prefix

## Unterstützte Geräte

- **Fronius GEN24** - Alle Varianten
- **Fronius Tauro** - Alle Varianten
- **Fronius GEN24 Plus** - Mit Batterie-Speicher

## Installation

### 1. Template installieren
Das Template ist bereits im `device_templates/` Verzeichnis enthalten.

### 2. Integration hinzufügen
1. **Home Assistant** → Configuration → Integrations
2. **"Add Integration"** → "Modbus Manager"
3. **Template auswählen**: "Fronius GEN24 Simple"
4. **Konfiguration eingeben**:
   - **Prefix**: Eindeutiger Prefix (z.B. `gen24_1`)
   - **Name**: Anzeigename (optional, falls nicht angegeben wird Prefix verwendet)

### 3. Modbus-Konfiguration
Das Template verwendet die Standard Home Assistant Modbus-Integration. Stellen Sie sicher, dass Sie eine Modbus-Integration für Ihren Fronius Wechselrichter konfiguriert haben:

```yaml
# configuration.yaml
modbus:
  - name: "fronius_gen24"
    type: tcp
    host: 192.168.1.100  # IP-Adresse Ihres Wechselrichters
    port: 502
    timeout: 3
    retries: 3
```

## Automatisch generierte Sensoren

### Common Model (Geräteinformationen)
- **Manufacturer**: Hersteller
- **Model**: Modellbezeichnung
- **Serial Number**: Seriennummer
- **Firmware Version**: Firmware-Version
- **Device Address**: Modbus-Geräteadresse

### Inverter Model (Wechselrichter-Daten)
- **AC Power**: AC-Leistung (W)
- **AC Current**: AC-Strom (A)
- **AC Voltage**: AC-Spannung (V)
- **AC Frequency**: AC-Frequenz (Hz)
- **DC Power**: DC-Leistung (W)
- **DC Current**: DC-Strom (A)
- **DC Voltage**: DC-Spannung (V)
- **Temperature**: Temperatur (°C)

### Storage Model (Batterie-Daten, falls vorhanden)
- **Battery Power**: Batterie-Leistung (W)
- **Battery SOC**: Batterie-Ladezustand (%)
- **Battery Voltage**: Batterie-Spannung (V)
- **Battery Current**: Batterie-Strom (A)
- **Battery Temperature**: Batterie-Temperatur (°C)

### Meter Model (Zähler-Daten, falls vorhanden)
- **Grid Power**: Netz-Leistung (W)
- **Grid Energy**: Netz-Energie (kWh)
- **Grid Frequency**: Netz-Frequenz (Hz)

## Berechnete Sensoren

### Effizienz-Berechnungen
- **Inverter Efficiency**: Wechselrichter-Effizienz (%)
- **Grid Power Balance**: Netz-Leistungsbilanz (W)

### Batterie-Berechnungen
- **Battery Charging Power**: Batterie-Ladeleistung (W)
- **Battery Discharging Power**: Batterie-Entladeleistung (W)

## Sensor-Gruppen

### PV_inverter_power
- AC-Leistung, DC-Leistung, Effizienz

### PV_inverter_current
- AC-Strom (alle Phasen), DC-Strom

### PV_inverter_voltage
- AC-Spannung (alle Phasen), DC-Spannung

### PV_inverter_frequency
- AC-Frequenz, Netz-Frequenz

### PV_battery_power
- Batterie-Leistung, Lade-/Entladeleistung

### PV_battery_soc
- Batterie-Ladezustand

### PV_battery_voltage
- Batterie-Spannung

### PV_battery_current
- Batterie-Strom

### PV_grid_power
- Netz-Leistung, Leistungsbilanz

### PV_grid_energy
- Netz-Energie

### PV_grid_frequency
- Netz-Frequenz

## Beispiel-Konfiguration

### Lovelace Dashboard
```yaml
type: entities
title: "Fronius GEN24 Übersicht"
entities:
  # Wechselrichter-Daten
  - sensor.gen24_1_ac_power
  - sensor.gen24_1_dc_power
  - sensor.gen24_1_inverter_efficiency
  
  # Batterie-Daten (falls vorhanden)
  - sensor.gen24_1_battery_power
  - sensor.gen24_1_battery_soc
  
  # Netz-Daten
  - sensor.gen24_1_grid_power
  - sensor.gen24_1_grid_power_balance
```

### Automatisierungen
```yaml
# Batterie voll - Ladeleistung reduzieren
automation:
  - alias: "Battery Full - Reduce Charging"
    trigger:
      platform: numeric_state
      entity_id: sensor.gen24_1_battery_soc
      above: 95
    action:
      - service: number.set_value
        target:
          entity_id: number.gen24_1_battery_charge_limit
        data:
          value: 50
```

## Troubleshooting

### Keine Daten
1. **Modbus-Verbindung prüfen**: Stellen Sie sicher, dass die Modbus-Integration funktioniert
2. **IP-Adresse prüfen**: Korrekte IP-Adresse des Wechselrichters
3. **Port prüfen**: Standard ist 502, kann bei Fronius anders sein
4. **Firewall prüfen**: Port 502 muss erreichbar sein

### Falsche Werte
1. **Register-Adressen prüfen**: Fronius kann andere Basisadressen verwenden
2. **Skalierung prüfen**: Werte können falsch skaliert sein
3. **Byte-Reihenfolge prüfen**: Big/Little Endian kann unterschiedlich sein

### Fehlende Sensoren
1. **Modelle prüfen**: Nicht alle Fronius-Modelle unterstützen alle SunSpec-Modelle
2. **Firmware prüfen**: Ältere Firmware kann weniger Register unterstützen
3. **Konfiguration prüfen**: Batterie/Zähler müssen aktiviert sein

## Technische Details

### SunSpec-Modelladressen
- **Common Model**: 40001 (Register 0)
- **Inverter Model**: 40069 (Register 68)
- **Storage Model**: 40187 (Register 186)
- **Meter Model**: 40277 (Register 276)

### Register-Mapping
Das Template verwendet die Standard SunSpec-Register-Mappings. Falls Ihr Fronius andere Adressen verwendet, können Sie diese im Template anpassen:

```yaml
# Im Template anpassen
model_addresses:
  common_model: 40001   # Anpassen falls nötig
  inverter_model: 40069  # Anpassen falls nötig
  storage_model: 40187   # Anpassen falls nötig
  meter_model: 40277     # Anpassen falls nötig
```

### Entity-Namen
Alle Entities verwenden das Format: `{prefix}_{sensor_name}`

Beispiele:
- `gen24_1_ac_power`
- `gen24_1_battery_soc`
- `gen24_1_inverter_efficiency`

## Support

- **GitHub Issues**: [HA-Modbus-Manager Issues](https://github.com/TCzerny/ha-modbus-manager/issues)
- **GitHub Discussions**: [HA-Modbus-Manager Discussions](https://github.com/TCzerny/ha-modbus-manager/discussions)
- **Wiki**: [HA-Modbus-Manager Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)

## Version

- **Template Version**: 1.0.0
- **Letzte Aktualisierung**: 2025-01-20
- **Kompatibilität**: Home Assistant 2024.8+
