import logging
from pymodbus.client.tcp import AsyncModbusTcpClient
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta
import yaml
from pathlib import Path
import asyncio

_LOGGER = logging.getLogger(__name__)

class ModbusSungrowHub:
    """Klasse zur Verwaltung einer Modbus-Verbindung für Sungrow-Geräte."""

    def __init__(self, name, host, port, slave, device_type, hass):
        """Initialisiert das Hub."""
        self.name = name
        self.host = host
        self.port = port
        self.slave = slave
        self.device_type = device_type
        self.hass = hass
        self.client = None
        self.coordinators = {}
        self._device_definition_cache = {} # Cache für Gerätedefinitionen

    async def async_setup(self):
        """Verbesserte Modbus-Verbindung mit Retry-Logik."""
        retry_count = 0
        max_retries = self.config.get("retries", 3)
        retry_delay = self.config.get("retry_delay", 0.1)

        while retry_count <= max_retries:
            try:
                self.client = AsyncModbusTcpClient(
                    self.host,
                    self.port,
                    timeout=self.config.get("tcp_timeout", 3),
                    retries=0,  # Wir handeln Retries selbst
                    retry_on_empty=True,
                    close_comm_on_error=True
                )
                connected = await self.client.connect()
                if connected:
                    _LOGGER.info("Modbus-Verbindung hergestellt zu %s:%s", self.host, self.port)
                    return True
                    
            except Exception as e:
                _LOGGER.warning(
                    "Verbindungsversuch %d von %d fehlgeschlagen: %s",
                    retry_count + 1, max_retries + 1, str(e)
                )
                
            retry_count += 1
            if retry_count <= max_retries:
                await asyncio.sleep(retry_delay * retry_count)
                
        raise ConnectionError("Maximale Anzahl an Verbindungsversuchen erreicht")

    async def async_teardown(self):
        """Beendet die Modbus-Verbindung."""
        if self.client:
            await self.client.close()
            _LOGGER.info("Modbus-Verbindung geschlossen")

    def get_device_definition(self, device_definition_name):
        """Ruft die Gerätekonfiguration ab."""
        definition_path = Path(__file__).parent / "device_definitions" / f"{device_definition_name}.yaml"
        if not definition_path.exists():
            _LOGGER.error("Gerätekonfigurationsdatei %s existiert nicht", definition_path)
            return None

        with open(definition_path, "r") as f:
            definition = yaml.safe_load(f)
            
        # Füge Präfix zu allen Template-Namen hinzu
        if 'helpers' in definition and 'templates' in definition['helpers']:
            for template in definition['helpers']['templates']:
                template['name'] = f"{self.name}_{template['name']}"
                
        # Füge Präfix zu allen Automatisierungsnamen hinzu
        if 'automations' in definition:
            for automation in definition['automations']:
                automation['name'] = f"{self.name}_{automation['name']}"
                # Aktualisiere entity_id in Triggern
                if 'trigger' in automation:
                    if 'entity_id' in automation['trigger']:
                        old_entity_id = automation['trigger']['entity_id']
                        automation['trigger']['entity_id'] = f"sensor.{self.name}_{old_entity_id.split('.')[-1]}"
                # Aktualisiere entity_id in Bedingungen
                if 'condition' in automation:
                    if 'entity_id' in automation['condition']:
                        old_entity_id = automation['condition']['entity_id']
                        automation['condition']['entity_id'] = f"sensor.{self.name}_{old_entity_id.split('.')[-1]}"
                
        return definition

    async def read_registers(self, device_definition_name):
        """Liest Register basierend auf der Gerätekonfiguration."""
        try:
            _LOGGER.debug("Erstelle Coordinator für %s", self.name)
            
            coordinator = DataUpdateCoordinator(
                self.hass,
                _LOGGER,
                name=f"{self.name} Daten",
                update_method=lambda: self._async_update_data(device_definition_name),
                update_interval=timedelta(seconds=10),
            )
            
            # Initialer Refresh des Coordinators
            await coordinator.async_refresh()
            
            # Speichere den Coordinator
            self.coordinators[self.name] = coordinator
            _LOGGER.debug("Coordinator für %s erfolgreich erstellt", self.name)
            
            return coordinator
            
        except Exception as e:
            _LOGGER.error("Fehler beim Erstellen des Coordinators für %s: %s", self.name, e)
            raise

    async def _async_update_data(self, device_definition_name):
        """Holt Daten vom Modbus-Gerät basierend auf der Gerätekonfiguration."""
        try:
            device_definitions = self.get_device_definition(device_definition_name)
            if not device_definitions:
                raise UpdateFailed("Keine Gerätekonfiguration gefunden")

            _LOGGER.debug("Starte Aktualisierung für Gerät: %s mit Slave ID: %d", 
                         device_definition_name, self.slave)
            
            data = {}
            read_registers = device_definitions.get('registers', {}).get('read', [])
            
            if not read_registers:
                _LOGGER.error("Keine Leseregister in der Konfiguration gefunden")
                return None

            _LOGGER.debug("Lese %d Register", len(read_registers))

            for reg in read_registers:
                device_name = reg.get("name")
                address = reg.get("address")
                count = self._get_register_count(reg)
                # Verwende die konfigurierte Slave ID, falls keine spezifische für das Register definiert ist
                unit = reg.get("unit", self.slave)

                if address is None:
                    _LOGGER.error(f"Keine Adresse für Gerät {device_name} definiert")
                    continue

                _LOGGER.debug("Lese Register - Name: %s, Adresse: %d, Anzahl: %d, Unit: %d", 
                            device_name, address, count, unit)

                try:
                    response = await self.client.read_holding_registers(address, count, unit=unit)
                    if not response.isError():
                        data[device_name] = response.registers
                        _LOGGER.debug("Registerdaten für %s: %s", device_name, response.registers)
                    else:
                        _LOGGER.error("Fehler beim Lesen der Register für %s: %s", device_name, response)
                except Exception as reg_error:
                    _LOGGER.error("Fehler beim Lesen des Registers %s (Adresse %d): %s", 
                                device_name, address, reg_error)
                    continue

            if not data:
                _LOGGER.warning("Keine Daten von den Registern erhalten")
                return None

            _LOGGER.debug("Aktualisierung abgeschlossen. Gelesene Register: %d", len(data))
            return data

        except Exception as e:
            _LOGGER.error("Fehler beim Kommunizieren mit dem Modbus-Gerät: %s", e)
            raise UpdateFailed(f"Fehler bei der Kommunikation mit dem Modbus-Gerät: {e}") 

    def _get_register_count(self, reg):
        """Bestimmt die Anzahl der Register basierend auf dem Datentyp."""
        data_type = reg.get("type")
        type_register_count = {
            "uint16": 1,
            "int16": 1,
            "bool": 1,
            "uint32": 2,
            "int32": 2,
            "float": 2,
            "string": 2,  # Anpassung je nach Bedarf
        }
        count = reg.get("count", type_register_count.get(data_type, 1))
        _LOGGER.debug("Register Count für Typ %s: %d", data_type, count)
        return count