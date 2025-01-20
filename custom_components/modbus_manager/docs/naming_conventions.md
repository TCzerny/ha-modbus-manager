# Namenskonventionen im ModbusManager

## Übersicht
Der ModbusManager verwendet verschiedene Namenstypen für unterschiedliche Zwecke. Diese Dokumentation beschreibt die verschiedenen Namenstypen, ihre Verwendung und Validierungsregeln.

## Namenstypen

### 1. Entity ID (NameType.ENTITY_ID)
- Format: `{domain}.{device_name}_{entity_name}`
- Beispiel: `sensor.sungrow_battery_level`
- Verwendung: Eindeutige Identifikation einer Entity in Home Assistant
- Validierung:
  - Nur Kleinbuchstaben, Zahlen und Unterstriche
  - Muss mit einem Buchstaben beginnen
  - Domain muss gültig sein (sensor, binary_sensor, etc.)
  - Maximale Länge: 255 Zeichen

### 2. Unique ID (NameType.UNIQUE_ID)
- Format: `{device_name}_{entity_name}`
- Beispiel: `sungrow_battery_level`
- Verwendung: Interne eindeutige Identifikation
- Validierung:
  - Nur Kleinbuchstaben, Zahlen und Unterstriche
  - Muss mit einem Buchstaben beginnen
  - Keine aufeinanderfolgenden Unterstriche
  - Maximale Länge: 128 Zeichen

### 3. Display Name (NameType.DISPLAY_NAME)
- Format: `{Device Name} {Entity Name}`
- Beispiel: `Sungrow Battery Level`
- Verwendung: Anzeigename in der Home Assistant UI
- Formatierung:
  - Title Case für bessere Lesbarkeit
  - Leerzeichen zwischen Wörtern
  - Sonderzeichen erlaubt
  - Maximale Länge: 64 Zeichen

### 4. Base Name (NameType.BASE_NAME)
- Format: `{device_name}_{entity_name}`
- Beispiel: `sungrow_battery_level`
- Verwendung: Interne Referenzierung
- Validierung:
  - Nur Kleinbuchstaben, Zahlen und Unterstriche
  - Muss mit einem Buchstaben beginnen
  - Keine aufeinanderfolgenden Unterstriche
  - Maximale Länge: 128 Zeichen

### 5. Service Name (NameType.SERVICE_NAME)
- Format: `{device_name}_{service_name}`
- Beispiel: `sungrow_set_battery_mode`
- Verwendung: Registrierung von Services
- Validierung:
  - Nur Kleinbuchstaben, Zahlen und Unterstriche
  - Muss mit einem Buchstaben beginnen
  - Verb am Anfang des service_name
  - Maximale Länge: 128 Zeichen

## Namenskonvertierung

Die Namenskonvertierung erfolgt durch die `EntityNameHelper` Klasse:

```python
name_helper = EntityNameHelper(config_entry)

# Entity ID generieren
entity_id = name_helper.convert(name, NameType.ENTITY_ID, domain="sensor")

# Unique ID generieren
unique_id = name_helper.convert(name, NameType.UNIQUE_ID)

# Display Name generieren
display_name = name_helper.convert(name, NameType.DISPLAY_NAME)

# Service Name generieren
service_name = name_helper.convert(name, NameType.SERVICE_NAME)
```

## Automatische Validierung & Bereinigung

Der EntityNameHelper führt automatisch folgende Bereinigungen durch:

1. Zeichenbereinigung:
   - Entfernung nicht erlaubter Zeichen
   - Konvertierung in Kleinbuchstaben (außer bei Display Name)
   - Ersetzung von Leerzeichen durch Unterstriche
   - Entfernung von Sonderzeichen

2. Strukturbereinigung:
   - Entfernung doppelter Unterstriche
   - Entfernung führender/nachfolgender Unterstriche
   - Entfernung von Zahlen am Ende
   - Sicherstellung gültiger Startzeichen

3. Längenvalidierung:
   - Kürzung auf maximale Länge wenn nötig
   - Beibehaltung der Lesbarkeit

## Best Practices

### 1. Gerätenamen
- Kurz und beschreibend
- Keine Sonderzeichen
- Keine Leerzeichen
- Herstellername oder Modell verwenden
- Beispiele:
  - ✓ `sungrow`, `fronius`, `solaredge`
  - ✗ `Sungrow-SH5.0RT`, `my inverter`, `123device`

### 2. Entity-Namen
- Beschreibend und eindeutig
- Englische Bezeichnungen
- Logische Gruppierung
- Physikalische Größe am Ende
- Beispiele:
  - ✓ `battery_level`, `grid_power`, `inverter_temperature`
  - ✗ `level`, `power_1`, `temp`

### 3. Service-Namen
- Aktions-orientiert
- Verb am Anfang
- Eindeutige Beschreibung
- Zielkomponente am Ende
- Beispiele:
  - ✓ `set_battery_mode`, `update_power_limit`, `reset_error_counter`
  - ✗ `battery`, `mode_set`, `update`

## YAML Beispiele

### 1. Einfaches Gerät mit Register
```yaml
name: sungrow
device_type: sungrow_shrt

registers:
  read:
    - name: battery_level
      address: 13000
      type: uint16
    - name: grid_power
      address: 13001
      type: int16
```

### 2. Gerät mit Services
```yaml
name: sungrow
device_type: sungrow_shrt

services:
  set_battery_mode:
    name: Set Battery Mode
    type: select
    register: battery_mode_reg
    options:
      - "Auto"
      - "Charge"
      - "Discharge"

  update_power_limit:
    name: Update Power Limit
    type: number
    register: power_limit_reg
    min: 0
    max: 5000
```

Dies erzeugt:
- Entity IDs:
  - `sensor.sungrow_battery_level`
  - `sensor.sungrow_grid_power`
- Display Names:
  - `Sungrow Battery Level`
  - `Sungrow Grid Power`
- Service Names:
  - `modbus_manager.sungrow_set_battery_mode`
  - `modbus_manager.sungrow_update_power_limit` 