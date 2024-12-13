# Modbus Manager für Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Eine leistungsstarke Home Assistant Integration zur Verwaltung von Modbus-Geräten mit vorkonfigurierten Gerätedefinitionen.

## Unterstützte Geräte

- Sungrow Wechselrichter
  - SG-RT Serie (einphasig)
  - SG-RT Serie (dreiphasig)
  - SH-RT Serie mit Batteriespeicher
- Compleo eBOX Professional Wallbox

## Features

### Allgemeine Features
- Flexible Modbus-Gerätekonfiguration über YAML-Dateien
- Automatische Sensor- und Entitätserstellung
- Integrierte Automationen und Benachrichtigungen
- Dynamische Berechnungen und Templates
- Lastmanagement-Funktionen

### Sungrow Wechselrichter Features
- Leistungs- und Energiemonitoring
- Batteriemanagementsystem
- Temperaturüberwachung
- Fehler- und Warnmeldungen
- Steuerungsfunktionen (Ein/Aus, Leistungsbegrenzung)

### Wallbox Features
- Ladestatus und -steuerung
- Energiemonitoring
- Fehlerüberwachung
- Temperaturmanagement

## Installation

### HACS Installation (empfohlen)
1. Öffnen Sie HACS in Home Assistant
2. Gehen Sie zu "Integrationen"
3. Klicken Sie auf das 3-Punkte-Menü
4. Wählen Sie "Eigenes Repository hinzufügen"
5. Fügen Sie die URL dieses Repositories ein
6. Wählen Sie "Integration" als Kategorie
7. Klicken Sie auf "Hinzufügen"

### Manuelle Installation
1. Laden Sie den Inhalt dieses Repositories herunter
2. Kopieren Sie den Ordner `custom_components/modbus_manager` in Ihren Home Assistant Ordner `config/custom_components/`
3. Starten Sie Home Assistant neu

## Konfiguration

### Basis-Konfiguration
1. Gehen Sie zu Einstellungen -> Geräte & Dienste
2. Klicken Sie auf "Integration hinzufügen"
3. Suchen Sie nach "Modbus Manager"
4. Folgen Sie dem Konfigurationsassistenten

### Gerätespezifische Konfiguration
Jedes Gerät wird über eine YAML-Datei im Ordner `device_definitions` konfiguriert. Die Konfiguration enthält:
- Modbus-Register-Definitionen
- Sensor-Konfigurationen
- Automatisierungen
- Berechnungsvorlagen

## Register-Definitionen

### Lese-Register
```yaml
read:
  - name: "sensor_name"
    address: 5000
    type: "uint16"
    unit_of_measurement: "W"
    device_class: "power"
    state_class: "measurement"
    scale: 0.1
```

### Schreib-Register
```yaml
write:
  - name: "control_parameter"
    address: 1000
    type: "uint16"
    description: "Beschreibung der Funktion"
```

## Automatisierungen

Die Integration enthält vordefinierte Automatisierungen für:
- Fehlerüberwachung
- Temperaturwarnungen
- Status-Benachrichtigungen
- Energiemanagement

## Templates und Berechnungen

Unterstützung für:
- Energieberechnungen
- Leistungsoptimierung
- Batteriemanagement
- Preisbasierte Steuerung

## Optimierungen und Berechnungen

### Energieoptimierung
- **Eigenverbrauchsoptimierung**: Automatische Anpassung der Batterieladung/-entladung basierend auf:
  - Aktuelle PV-Produktion
  - Haushaltsverbrauch
  - Strompreise (optional)
  - Wettervorhersage (optional)

### Batteriemanagement
- **Dynamische SOC-Steuerung**:
  ```yaml
  templates:
    - name: "battery_target_soc"
      value: >
        {% set price_factor = states('sensor.strompreis')|float %}
        {% set pv_forecast = states('sensor.pv_forecast_today')|float %}
        {% if price_factor > 0.30 %}
          {% if pv_forecast > 10 %}
            85
          {% else %}
            95
          {% endif %}
        {% else %}
          60
        {% endif %}
  ```

### Lastmanagement
- **Intelligente Verbrauchssteuerung**:
  ```yaml
  automations:
    - name: "load_management"
      trigger:
        - platform: numeric_state
          entity_id: sensor.grid_power
          above: 5000
      action:
        - service: switch.turn_off
          target:
            entity_id: switch.high_power_device
  ```

### Preisbasierte Optimierung
- **Riemann-Integral Berechnung**:
  ```yaml
  templates:
    - name: "energy_cost_calculation"
      value: >
        {% set power = states('sensor.total_power')|float %}
        {% set price = states('sensor.electricity_price')|float %}
        {{ (power * price / 1000) | round(2) }}
  ```

## Vordefinierte Automatisierungen

### Batterieüberwachung
```yaml
automations:
  - name: "battery_protection"
    trigger:
      - platform: numeric_state
        entity_id: sensor.battery_temperature
        above: 40
    condition:
      - condition: numeric_state
        entity_id: sensor.battery_soc
        above: 85
    action:
      - service: modbus_manager.set_charge_power
        data:
          power: 0
```

### Eigenverbrauchsoptimierung
```yaml
automations:
  - name: "self_consumption_optimization"
    trigger:
      - platform: numeric_state
        entity_id: sensor.pv_power
        above: sensor.house_consumption
    action:
      - service: modbus_manager.set_battery_mode
        data:
          mode: "charge"
```

### Netzüberlastungsschutz
```yaml
automations:
  - name: "grid_protection"
    trigger:
      - platform: numeric_state
        entity_id: sensor.grid_power
        above: 15000
    action:
      - service: modbus_manager.reduce_charge_power
        data:
          reduction: 50
```

## Helfer und Templates

### Energieberechnungen
```yaml
templates:
  - name: "daily_self_consumption"
    value: >
      {% set total = states('sensor.daily_energy_production')|float %}
      {% set grid = states('sensor.daily_grid_feed')|float %}
      {{ ((total - grid) / total * 100)|round(1) }}
```

### Leistungsoptimierung
```yaml
templates:
  - name: "optimal_charge_power"
    value: >
      {% set pv = states('sensor.pv_power')|float %}
      {% set home = states('sensor.home_consumption')|float %}
      {% set surplus = pv - home %}
      {{ [surplus, 10000] | min }}
```

### Batterieeffizienz
```yaml
templates:
  - name: "battery_efficiency"
    value: >
      {% set charge = states('sensor.total_battery_charge')|float %}
      {% set discharge = states('sensor.total_battery_discharge')|float %}
      {{ (discharge / charge * 100)|round(1) if charge > 0 else 0 }}
```

## Erweiterte Konfigurationsbeispiele

### Dynamische Ladeleistung
```yaml
templates:
  - name: "dynamic_charge_power"
    value: >
      {% set price = states('sensor.electricity_price')|float %}
      {% set soc = states('sensor.battery_soc')|float %}
      {% if price < 0.15 and soc < 80 %}
        {{ 10000 }}
      {% elif price < 0.25 and soc < 60 %}
        {{ 5000 }}
      {% else %}
        {{ 0 }}
      {% endif %}
```

### Wetterbasierte Steuerung
```yaml
automations:
  - name: "weather_based_charging"
    trigger:
      - platform: state
        entity_id: sensor.weather_forecast_today
    action:
      - service: modbus_manager.set_target_soc
        data:
          template: >
            {% if trigger.to_state.state == 'sunny' %}
              {{ 60 }}
            {% else %}
              {{ 85 }}
            {% endif %}
```

## Fehlerbehebung

### Bekannte Probleme
- Liste bekannter Probleme und Lösungen

### Debugging
1. Aktivieren Sie das Debug-Logging
2. Überprüfen Sie die Home Assistant Logs
3. Kontaktieren Sie den Support

## Beitragen

Beiträge sind willkommen! Bitte erstellen Sie einen Pull Request oder ein Issue.

## Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe die [LICENSE](LICENSE) Datei für Details. 