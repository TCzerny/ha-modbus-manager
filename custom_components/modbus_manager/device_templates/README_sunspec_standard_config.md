# SunSpec Standard Configuration Template

## Übersicht

Das **SunSpec Standard Configuration Template** ist ein universelles Template für alle SunSpec-konformen Geräte. Benutzer geben ihre eigenen Modell-Basisadressen an, und das System generiert automatisch alle SunSpec-Register als Sensoren.

## Features

- ✅ **Universell**: Funktioniert mit allen SunSpec-konformen Geräten
- ✅ **Flexibel**: Benutzer geben ihre eigenen Modell-Adressen an
- ✅ **Automatisch**: Alle SunSpec-Register werden automatisch erstellt
- ✅ **Berechnete Sensoren**: Automatische Effizienz- und Leistungsberechnungen
- ✅ **Gruppierung**: Sensoren werden automatisch in logische Gruppen eingeteilt
- ✅ **Prefix-Unterstützung**: Eindeutige Entity-Namen mit User-Prefix

## Unterstützte Geräte

**Alle SunSpec-konformen Geräte**, einschließlich:
- **SMA** - Sunny Boy, Tripower, Home Storage
- **Fronius** - GEN24, Tauro
- **Huawei** - Luna, FusionSolar
- **SolarEdge** - HD Wave, StorEdge
- **Kostal** - Piko, Plenticore
- **Growatt** - MIN, MAX series
- **Victron** - MultiPlus, Quattro
- **Und viele weitere...**

## Installation

### 1. Template installieren
Das Template ist bereits im `device_templates/` Verzeichnis enthalten.

### 2. Integration hinzufügen
1. **Home Assistant** → Configuration → Integrations
2. **"Add Integration"** → "Modbus Manager"
3. **Template auswählen**: "SunSpec Standard Configuration"
4. **Konfiguration eingeben**:
   - **Prefix**: Eindeutiger Prefix (z.B. `sma_1`)
   - **Name**: Anzeigename (optional)
   - **Common Model Address**: Basisadresse für Common Model (z.B. `40001`)
   - **Inverter Model Address**: Basisadresse für Inverter Model (z.B. `40069`)
   - **Storage Model Address**: Basisadresse für Storage Model (optional, z.B. `40187`)
   - **Meter Model Address**: Basisadresse für Meter Model (optional, z.B. `40277`)

### 3. Modbus-Konfiguration
Das Template verwendet die Standard Home Assistant Modbus-Integration. Stellen Sie sicher, dass Sie eine Modbus-Integration für Ihr Gerät konfiguriert haben:

```yaml
# configuration.yaml
modbus:
  - name: "sunspec_device"
    type: tcp
    host: 192.168.1.100  # IP-Adresse Ihres Geräts
    port: 502
    timeout: 3
    retries: 3
```

## Standard-Modelladressen

### Häufig verwendete Basisadressen:

#### **SMA**
- Common Model: `40001`
- Inverter Model: `40069`
- Storage Model: `40187`
- Meter Model: `40277`

#### **Fronius**
- Common Model: `40001`
- Inverter Model: `40069`
- Storage Model: `40187`
- Meter Model: `40277`

#### **Huawei**
- Common Model: `40001`
- Inverter Model: `40069`
- Storage Model: `40187`
- Meter Model: `40277`

#### **SolarEdge**
- Common Model: `40001`
- Inverter Model: `40069`
- Storage Model: `40187`
- Meter Model: `40277`

## Automatisch generierte Sensoren

### Common Model (Geräteinformationen)
- **Manufacturer**: Hersteller
- **Model**: Modellbezeichnung
- **Serial Number**: Seriennummer
- **Firmware Version**: Firmware-Version
- **Device Address**: Modbus-Geräteadresse

### Inverter Model (Wechselrichter-Daten)
- **AC Power**: AC-Leistung (W)
- **AC Current**: AC-Strom (A) - alle Phasen
- **AC Voltage**: AC-Spannung (V) - alle Phasen
- **AC Frequency**: AC-Frequenz (Hz)
- **DC Power**: DC-Leistung (W)
- **DC Current**: DC-Strom (A)
- **DC Voltage**: DC-Spannung (V)
- **Temperature**: Temperatur (°C) - verschiedene Sensoren
- **Status**: Betriebsstatus

### Storage Model (Batterie-Daten, falls vorhanden)
- **Storage Status**: Batterie-Status
- **Charge Limit**: Ladegrenze (%)
- **Discharge Limit**: Entladegrenze (%)
- **Available Energy**: Verfügbare Energie (kWh)
- **Available Capacity**: Verfügbare Kapazität (%)
- **Total Capacity**: Gesamtkapazität (kWh)
- **Charge Power**: Ladeleistung (W)
- **Discharge Power**: Entladeleistung (W)
- **Charge Energy**: Ladeenergie (Wh)
- **Discharge Energy**: Entladeenergie (Wh)

### Meter Model (Zähler-Daten, falls vorhanden)
- **Meter Status**: Zähler-Status
- **AC Current**: AC-Strom (A) - alle Phasen
- **AC Voltage**: AC-Spannung (V) - alle Phasen
- **AC Power**: AC-Leistung (W)
- **AC Frequency**: AC-Frequenz (Hz)
- **AC Energy**: AC-Energie (Wh)

## Berechnete Sensoren

### Effizienz-Berechnungen
- **Inverter Efficiency**: Wechselrichter-Effizienz (%)
- **Grid Power Balance**: Netz-Leistungsbilanz (W)

### Batterie-Berechnungen
- **Battery Charging Power**: Batterie-Ladeleistung (W)
- **Battery Discharging Power**: Batterie-Entladeleistung (W)
- **Battery State of Charge**: Batterie-Ladezustand (%)

## Sensor-Gruppen

### PV_inverter_power
- AC-Leistung, DC-Leistung, Effizienz

### PV_inverter_current
- AC-Strom (alle Phasen), DC-Strom

### PV_inverter_voltage
- AC-Spannung (alle Phasen), DC-Spannung

### PV_inverter_frequency
- AC-Frequenz

### PV_inverter_temperature
- Temperatur-Sensoren

### PV_battery_power
- Batterie-Leistung, Lade-/Entladeleistung

### PV_battery_soc
- Batterie-Ladezustand

### PV_battery_voltage
- Batterie-Spannung

### PV_battery_current
- Batterie-Strom

### PV_battery_energy
- Batterie-Energie

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
title: "SunSpec Gerät Übersicht"
entities:
  # Wechselrichter-Daten
  - sensor.sma_1_i_ac_power
  - sensor.sma_1_i_dc_power
  - sensor.sma_1_inverter_efficiency
  
  # Batterie-Daten (falls vorhanden)
  - sensor.sma_1_s_charge_power
  - sensor.sma_1_s_available_capacity
  
  # Netz-Daten (falls vorhanden)
  - sensor.sma_1_m_ac_power
  - sensor.sma_1_grid_power_balance
```

### Automatisierungen
```yaml
# Batterie voll - Ladeleistung reduzieren
automation:
  - alias: "Battery Full - Reduce Charging"
    trigger:
      platform: numeric_state
      entity_id: sensor.sma_1_battery_state_of_charge
      above: 95
    action:
      - service: number.set_value
        target:
          entity_id: number.sma_1_battery_charge_limit
        data:
          value: 50
```

## Troubleshooting

### Keine Daten
1. **Modell-Adressen prüfen**: Stellen Sie sicher, dass die Basisadressen korrekt sind
2. **Modbus-Verbindung prüfen**: Stellen Sie sicher, dass die Modbus-Integration funktioniert
3. **IP-Adresse prüfen**: Korrekte IP-Adresse des Geräts
4. **Port prüfen**: Standard ist 502, kann bei manchen Geräten anders sein
5. **Firewall prüfen**: Port 502 muss erreichbar sein

### Falsche Werte
1. **Basisadressen prüfen**: Verschiedene Hersteller können andere Basisadressen verwenden
2. **Skalierung prüfen**: Werte können falsch skaliert sein
3. **Byte-Reihenfolge prüfen**: Big/Little Endian kann unterschiedlich sein

### Fehlende Sensoren
1. **Modell-Adressen prüfen**: Nicht alle Geräte unterstützen alle SunSpec-Modelle
2. **Firmware prüfen**: Ältere Firmware kann weniger Register unterstützen
3. **Konfiguration prüfen**: Batterie/Zähler müssen aktiviert sein

## Modell-Adressen ermitteln

### Methode 1: Gerätedokumentation
Schauen Sie in der Dokumentation Ihres Geräts nach den SunSpec-Modelladressen.

### Methode 2: Modbus-Scanner
Verwenden Sie einen Modbus-Scanner, um die verfügbaren Register zu finden:

```bash
# Beispiel mit modbus-cli
modbus read --host 192.168.1.100 --port 502 --slave 1 --address 40001 --count 10
```

### Methode 3: SunSpec-Tools
Verwenden Sie SunSpec-Tools, um die Modellstruktur zu analysieren:

```bash
# Beispiel mit sunspec-tools
sunspec scan --host 192.168.1.100 --port 502
```

## Technische Details

### SunSpec-Modellstruktur
Jedes SunSpec-Modell hat:
- **ID**: Modell-Identifikation (1, 103, 124, 203, etc.)
- **Länge**: Anzahl der Register im Modell
- **Register**: Liste der Register mit Offsets

### Register-Adressberechnung
```
Absolute Adresse = Modell-Basisadresse + Register-Offset
```

Beispiele:
- Common Model Register 0: `40001 + 0 = 40001`
- Inverter Model Register 10: `40069 + 10 = 40079`
- Storage Model Register 2: `40187 + 2 = 40189`

### Entity-Namen
Alle Entities verwenden das Format: `{prefix}_{register_name}`

Beispiele:
- `sma_1_c_manufacturer`
- `sma_1_i_ac_power`
- `sma_1_s_charge_power`
- `sma_1_m_ac_power`

## Support

- **GitHub Issues**: [HA-Modbus-Manager Issues](https://github.com/TCzerny/ha-modbus-manager/issues)
- **GitHub Discussions**: [HA-Modbus-Manager Discussions](https://github.com/TCzerny/ha-modbus-manager/discussions)
- **Wiki**: [HA-Modbus-Manager Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki)

## Version

- **Template Version**: 1.0.0
- **Letzte Aktualisierung**: 2025-01-20
- **Kompatibilität**: Home Assistant 2024.8+
- **SunSpec Standard**: Version 1.0
