# ModBus Manager Modul-Struktur

## Übersicht
Die ModBus Manager Integration ist modular aufgebaut und folgt einer klaren Struktur. Jedes Modul hat eine spezifische Verantwortlichkeit und ist klar dokumentiert.

## Core Components

### __init__.py
- Integration Setup und Initialisierung
- Plattform-Registrierung
- Konfigurations-Handling

### modbus_hub.py
- ModBus Kommunikation
- Hub-Management
- Geräte-Verwaltung
- Optimierte Import-Struktur für ModBus-spezifische Funktionalität

### device_base.py
- Basis-Klasse für Geräte
- Gemeinsame Funktionalität
- Geräte-Lifecycle-Management

### device_registers.py
- Register-Verarbeitung
- Register-Verwaltung
- Optimierte Typ-Konvertierungen

### device_entities.py
- Entity-Management
- Zustandsverwaltung
- Entity-Registrierung

### device_tests.py
- Test Suite
- Automatisierte Tests
- Validierung

## Platform Components

### binary_sensor.py
- Binary Sensor Platform
- Optimierte Import-Struktur
- Spezifische Sensor-Logik

### script.py
- Script Platform
- Automatisierungs-Integration
- Event-Handling

### select.py
- Select Platform
- Auswahloptionen
- Zustandsmanagement

### number.py
- Number Platform
- Numerische Eingaben
- Wertevalidierung

### sensor.py
- Sensor Platform
- Messwert-Verarbeitung
- Zustandsüberwachung

### switch.py
- Switch Platform
- Schaltfunktionen
- Statusverwaltung

## Support Components

### common_sensors.py
- Gemeinsam genutzte Sensor-Definitionen
- Wiederverwendbare Komponenten
- Optimierte Import-Struktur

### config_flow.py
- Konfigurations-Flow
- Benutzerinteraktion
- Validierung

### firmware.py
- Firmware-Management
- Update-Funktionalität
- Version-Kontrolle

### template_entities.py
- Template-basierte Entities
- Flexible Entitäts-Definitionen
- Optimierte Import-Struktur

### automation_entities.py
- Automatisierungs-Entities
- Event-Handling
- Optimierte Import-Struktur

### input_entities.py
- Input-Entity-Typen
- Benutzereingaben
- Validierung

## Helper Components

### const.py
- Konstanten
- Konfigurationen
- Typ-Definitionen

### logger.py
- Erweitertes Logging
- Debug-Funktionalität
- Fehler-Tracking

### helpers.py
- Hilfsfunktionen
- Utility-Methoden
- Gemeinsam genutzte Funktionalität

### errors.py
- Fehler-Definitionen
- Exception-Handling
- Fehlermeldungen

## Import-Struktur
Alle Module folgen diesem einheitlichen Import-Muster:

1. `__future__` Imports
   - Zukunftssichere Funktionalität
   - Python-Kompatibilität

2. Standard-Python-Bibliotheken
   - Built-in Module
   - System-Funktionalität

3. Externe Bibliotheken (HomeAssistant)
   - HA-Komponenten
   - HA-Hilfsfunktionen

4. Lokale Module
   - Eigene Komponenten
   - Integration-spezifische Module

## Best Practices
- Klare Trennung der Verantwortlichkeiten
- Einheitliche Import-Struktur
- Ausführliche Dokumentation
- Typisierung aller Komponenten
- Fehlerbehandlung und Logging
- Modulare und wartbare Struktur 