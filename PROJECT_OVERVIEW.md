# 🔧 Projektbeschreibung: Home Assistant Modbus Manager

## 👤 Autor: TCzerny  
## 📦 Repository: [github.com/TCzerny/ha-modbus-manager](https://github.com/TCzerny/ha-modbus-manager)  
## 📅 Stand: August 2025  
## 🧠 Ziel: Eine universelle, template-gesteuerte Modbus-Integration für Home Assistant

---

## 🧱 Projektziel

Der Modbus Manager soll eine modulare, skalierbare und wartbare Plattform zur Verwaltung von Modbus-Geräten in Home Assistant bieten. Ziel ist es, beliebige Geräte wie PV-Wechselrichter, Wärmepumpen, Wallboxen, Klimageräte oder Heizungen über ein einheitliches Template-System zu integrieren — ohne manuelle YAML-Konfiguration oder Automationen.

---

## 🔧 Architekturüberblick

### 📁 Template-Struktur

Templates befinden sich unter `device_definitions/*.yaml` und enthalten:

- `registers:` → Modbus-Sensoren  
- `calculated:` → Berechnete Sensoren via Jinja2  
- `controls:` → Direkte Modbus-Steuerung (`number`, `select`, `button`)  
- `version:` → Template-Versionierung zur Update-Erkennung  
- `type:` → Gerätetyp (z. B. `inverter`, `heatpump`, `wallbox`)  

### 🧩 Module

| Datei                  | Funktion                                           |
|------------------------|----------------------------------------------------|
| `template_loader.py`   | Lädt und validiert Templates                      |
| `entity_factory.py`    | Erzeugt Entitäten aus Template-Daten              |
| `controls.py`          | Direkte Modbus-Steuerung                          |
| `calculated.py`        | Berechnete Sensoren mit Jinja2                    |
| `modbus_device.py`     | Zentrale Geräteklasse                             |
| `config_flow.py`       | UI-Setup für Geräte                               |

---

## ✅ Features

- Dynamisches Laden von Templates
- Direkte Steuerung ohne Automationen (`ModbusNumberEntity`, `ModbusSelectEntity`, `ModbusButtonEntity`)
- Berechnete Sensoren mit `{prefix}`-Platzhalter
- Unterstützung für `data_type`, `length`, `bitmask`
- Halbautomatische Template-Updates mit Versionsvergleich
- Aggregation über `group:`-Feld
- UI-kompatibel, keine YAML nötig

---

## 📋 Beispiel-Template: `heatpump_generic.yaml`

```yaml
name: Generic Heatpump
type: heatpump
version: 2
slave_id: 1

registers:
  - name: "Flow Temperature"
    address: 30010
    unit: "°C"
    scale: 0.1
    device_class: temperature
    state_class: measurement
    group: heat_flow

  - name: "Compressor Status"
    address: 30020
    data_type: bitfield
    bitmask: 0x01
    device_class: running
    group: heat_status

calculated:
  - name: "Delta Temperature"
    type: sensor
    template: "{{ states('sensor.{prefix}_flow_temperature') | float - states('sensor.{prefix}_return_temperature') | float }}"
    unit: "°C"
    device_class: temperature
    state_class: measurement
    group: heat_delta

controls:
  - type: number
    name: "Target Temperature"
    address: 40010
    scale: 0.1
    unit: "°C"
    min: 30
    max: 60
    step: 0.5
    group: heat_control
