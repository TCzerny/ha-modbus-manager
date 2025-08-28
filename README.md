# Modbus Manager für Home Assistant

Eine Custom Integration für Home Assistant, die Modbus-Geräte über eine template-basierte, UI-konfigurierbare Plattform verwaltet. Ziel ist es, die manuelle Pflege von `configuration.yaml` zu ersetzen und eine skalierbare Lösung für die Verwaltung mehrerer Modbus-TCP-Geräte bereitzustellen.

## 🔧 Hauptfunktionen

- **Geräte-Templates**: YAML-basierte Definitionen von Modbus-Geräten mit Register-Mapping, Skalierung, Einheiten, device_class, state_class und Gruppentags
- **UI-Setup**: Nutzer wählen ein Template, geben IP, Port, Slave-ID und einen Präfix ein – die Entitäten werden automatisch erzeugt
- **Entitätserzeugung**: Sensoren werden dynamisch aus Templates erstellt, mit Präfix zur Unterscheidung und Gruppentags für spätere Aggregation
- **Modbus-Hub-Management**: Jeder Gerät wird als eigener virtueller Modbus-Hub registriert, Kommunikation läuft über die Home Assistant Modbus-API
- **Aggregationsmodul**: Automatische Erzeugung von Summen-, Durchschnitts-, Max-/Min- und Statussensoren über Entitäten mit gleichem group-Tag
- **Live-Refresh**: Aggregationssensoren aktualisieren sich sofort bei Änderungen der zugehörigen Entitäten via `async_track_state_change`
- **Group Discovery**: Alle vorhandenen Gruppen werden erkannt und im UI zur Konfiguration von Aggregationen angeboten
- **Erweiterte Datenverarbeitung**: Unterstützung für Bit-Operationen, Enum-Mapping, Bit-Flags und mehr (basierend auf [modbus_connect](https://github.com/dmatscheko/modbus_connect))
- **Vollständige Entity-Typen**: Sensoren, Schalter, Zahlen, Select-Entitäten, Binary-Sensoren

## 📋 Unterstützte Geräte

### Sungrow SHx Inverter
- **Template**: `sungrow_shx.yaml`
- **Beschreibung**: Vollständige Unterstützung für Sungrow SHx Wechselrichter
- **Register**: Temperatur, MPPT-Daten, Grid-Parameter, Energie-Statistiken
- **Gruppen**: identification, energy_daily, energy_total, mppt1, mppt2, grid_l1, power_total, system

### Compleo EBox Professional Wallbox
- **Template**: `compleo_ebox.yaml`
- **Beschreibung**: Template für Compleo EBox Professional Wallbox
- **Register**: Lade-Status, Strom/Spannung/Leistung, Energie-Statistiken, Temperatur
- **Gruppen**: identification, status, charging, energy_session, energy_total, time_session, system

### Advanced Example Device
- **Template**: `advanced_example.yaml`
- **Beschreibung**: Demonstriert alle erweiterten Features
- **Features**: Bit-Operationen, Enum-Mapping, Bit-Flags, Float-Konvertierung, Control-Entitäten

## 🚀 Installation

### HACS Installation (Empfohlen)
1. Fügen Sie das Repository zu HACS hinzu
2. Installieren Sie die Integration über HACS
3. Starten Sie Home Assistant neu

### Manuelle Installation
1. Laden Sie den Code herunter
2. Kopieren Sie den `custom_components/modbus_manager` Ordner in Ihren `custom_components` Ordner
3. Starten Sie Home Assistant neu

## ⚙️ Konfiguration

### 1. Template auswählen
- Gehen Sie zu **Konfiguration** → **Geräte & Dienste**
- Klicken Sie auf **+ Integration hinzufügen**
- Wählen Sie **Modbus Manager**
- Wählen Sie ein verfügbares Template aus

### 2. Geräte-Konfiguration
- **Präfix**: Eindeutiger Name für das Gerät (z.B. `sungrow_1`)
- **Host**: IP-Adresse des Modbus-Geräts
- **Port**: Modbus-Port (Standard: 502)
- **Slave ID**: Modbus-Slave-ID (Standard: 1)
- **Timeout**: Verbindungs-Timeout in Sekunden (Standard: 3)
- **Retries**: Anzahl der Wiederholungsversuche (Standard: 3)

### 3. Aggregations-Konfiguration
- Gehen Sie zu den **Optionen** der Integration
- Wählen Sie **Aggregationen konfigurieren**
- Wählen Sie die gewünschten Gruppen aus
- Wählen Sie die Aggregations-Methoden (Summe, Durchschnitt, Max/Min, Anzahl)

## 📊 Template-Format

Templates verwenden das folgende YAML-Format:

```yaml
name: "Gerätename"
description: "Beschreibung des Geräts"
manufacturer: "Hersteller"
model: "Modell"

sensors:
  - name: "Sensor-Name"
    unique_id: "eindeutige_id"
    device_address: 1
    address: 1000
    input_type: "input"  # input oder holding
    data_type: "uint16"  # uint16, int16, uint32, int32, string, float, boolean
    count: 1
    scan_interval: 600
    precision: 2
    unit_of_measurement: "kWh"
    device_class: "energy"
    state_class: "total_increasing"
    scale: 0.01
    swap: false  # für 32-bit Werte
    group: "energy_total"
    
    # Erweiterte Datenverarbeitung (modbus_connect Features)
    offset: 0.0           # Offset hinzufügen
    multiplier: 1.0       # Multiplikator anwenden
    sum_scale: [1, 10000] # Mehrere Register kombinieren
    shift_bits: 4         # Bit-Shift nach rechts
    bits: 8               # Bit-Mask anwenden
    float: false          # 32-bit Float
    string: false         # String aus Registern
    
    # Control-Entitäten (read/write)
    control: "none"       # none, number, select, switch, text
    min_value: 0.0        # Für number-Entitäten
    max_value: 100.0      # Für number-Entitäten
    step: 1.0             # Für number-Entitäten
    options:              # Für select-Entitäten
      0: "Off"
      1: "On"
    switch:               # Für switch-Entitäten
      "on": 1
      "off": 0
    
    # Enum-Mapping und Bit-Flags
    map:                  # Wert-zu-Text-Mapping
      0: "Disabled"
      1: "Enabled"
    flags:                # Bit-Flag-Status
      0: "Power On"
      1: "Fan Active"
```

### Unterstützte Daten-Typen
- **uint16**: 16-bit unsigned integer
- **int16**: 16-bit signed integer  
- **uint32**: 32-bit unsigned integer (2 Register)
- **int32**: 32-bit signed integer (2 Register)
- **float**: 32-bit IEEE 754 float (2 Register)
- **string**: ASCII-String aus Registern
- **boolean**: Boolean-Wert

### Unterstützte Device Classes
- `energy`, `power`, `voltage`, `current`, `temperature`, `frequency`, `duration`, `pressure`, `problem`, `switch`

### Unterstützte State Classes
- `measurement`, `total`, `total_increasing`

### Erweiterte Datenverarbeitung

#### Bit-Operationen
- **shift_bits**: Verschiebt Bits nach rechts (z.B. `shift_bits: 4` für 4 Bits)
- **bits**: Wendet Bit-Mask an (z.B. `bits: 8` für untere 8 Bits)

#### Mathematische Operationen
- **offset**: Addiert einen Offset zum Wert
- **multiplier**: Multipliziert den Wert mit einem Faktor
- **sum_scale**: Kombiniert mehrere Register mit Skalierungsfaktoren

#### Enum-Mapping und Flags
- **map**: Konvertiert numerische Werte zu Text (z.B. 0="Off", 1="On")
- **flags**: Extrahiert einzelne Bit-Status als separate Attribute

#### Control-Entitäten
- **control: number**: Erstellt eine Number-Entity mit min/max/step
- **control: select**: Erstellt eine Select-Entity mit vordefinierten Optionen
- **control: switch**: Erstellt eine Switch-Entity mit on/off-Werten
- **control: text**: Erstellt eine Text-Entity für String-Eingaben

### Performance & Optimization

#### Register Optimization
- **Intelligent Grouping**: Automatically groups consecutive registers for batch reading
- **Configurable Batch Size**: Set `max_read_size` for optimal performance
- **Performance Monitoring**: Track operation success rates, duration, and throughput

#### Advanced Modbus Configuration
- **Connection Management**: Configurable timeout, retries, and reconnection settings
- **Error Handling**: Automatic connection closure and recovery on errors
- **Message Timing**: Configurable delays between operations and messages

## 🧮 Aggregations-Methoden

### Verfügbare Methoden
- **Summe**: Addiert alle Werte einer Gruppe
- **Durchschnitt**: Berechnet den Mittelwert aller Werte
- **Maximum**: Zeigt den höchsten Wert an
- **Minimum**: Zeigt den niedrigsten Wert an
- **Anzahl**: Zählt die Anzahl der aktiven Entitäten

### Automatische Einheiten-Erkennung
Aggregationssensoren erkennen automatisch die Einheit der zugehörigen Sensoren und verwenden die häufigste Einheit.

## 🔍 Troubleshooting

### Häufige Probleme

#### Keine Templates gefunden
- Stellen Sie sicher, dass Templates im `device_templates` Verzeichnis vorhanden sind
- Überprüfen Sie die YAML-Syntax der Template-Dateien
- Prüfen Sie die Home Assistant Logs auf Fehlermeldungen

#### Modbus-Verbindungsfehler
- Überprüfen Sie IP-Adresse und Port
- Stellen Sie sicher, dass der Slave-ID korrekt ist
- Prüfen Sie Firewall-Einstellungen
- Erhöhen Sie Timeout und Retry-Werte

#### Aggregationssensoren funktionieren nicht
- Stellen Sie sicher, dass Sensoren mit `group`-Tags konfiguriert sind
- Überprüfen Sie, ob die Gruppierung korrekt eingerichtet ist
- Prüfen Sie die Home Assistant Logs auf Fehlermeldungen

#### Erweiterte Features funktionieren nicht
- Überprüfen Sie die Template-Syntax für neue Felder
- Stellen Sie sicher, dass alle erforderlichen Parameter korrekt gesetzt sind
- Prüfen Sie die Logs auf Validierungsfehler

### Logs aktivieren
Fügen Sie folgendes zu Ihrer `configuration.yaml` hinzu:

```yaml
logger:
  custom_components.modbus_manager: debug
```

## 🤝 Beitragen

Beiträge sind willkommen! Bitte beachten Sie:

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch
3. Committen Sie Ihre Änderungen
4. Erstellen Sie einen Pull Request

### Template-Entwicklung
- Verwenden Sie das bestehende Template-Format
- Testen Sie Ihre Templates gründlich
- Dokumentieren Sie alle Register-Definitionen
- Fügen Sie aussagekräftige Gruppentags hinzu
- Nutzen Sie die erweiterten Datenverarbeitungsoptionen

## 📄 Lizenz

Dieses Projekt steht unter der MIT-Lizenz. Siehe [LICENSE](LICENSE) für Details.

## 🙏 Danksagungen

- **Sungrow Template**: Basierend auf [Sungrow-SHx-Inverter-Modbus-Home-Assistant](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant) von Martin Kaiser
- **modbus_connect**: Erweiterte Features basierend auf [modbus_connect](https://github.com/dmatscheko/modbus_connect) von dmatscheko
- **modbus_local_gateway**: Inspiration aus [modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway) von Tim Laing
- **Home Assistant Community**: Für die großartige Plattform und Unterstützung

## 📞 Support

- **GitHub Issues**: [Probleme melden](https://github.com/TCzerny/ha-modbus-manager/issues)
- **GitHub Discussions**: [Diskussionen](https://github.com/TCzerny/ha-modbus-manager/discussions)

---

**Entwickelt mit ❤️ für die Home Assistant Community** 