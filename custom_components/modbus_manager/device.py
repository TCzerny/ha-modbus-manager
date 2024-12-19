"""Modbus Manager Device Class."""

from pathlib import Path
import yaml
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import DOMAIN
from .logger import ModbusManagerLogger
from typing import Dict, Any, Optional, List
import aiofiles
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_NAME

_LOGGER = ModbusManagerLogger(__name__)


class ModbusManagerDevice:
    """Class representing a Modbus device."""

    def __init__(self, hub, device_type: str, config: dict):
        """Initialisiert das Gerät.
        
        Args:
            hub: Referenz zum ModbusManagerHub
            device_type: Typ des Geräts (z.B. 'sungrow', 'fronius')
            config: Konfigurationsdaten aus dem Config Flow
        """
        # Initialisiere zuerst den Logger
        self.name = config.get("name", f"modbus_{device_type}")
        self._logger = ModbusManagerLogger(name=f"device_{self.name}")
        
        # Dann die anderen Attribute
        self.hub = hub
        self.hass = hub.hass
        self.device_type = device_type
        self.config = config
        
        if "name" not in config:
            self._logger.error("Kein Name in der Konfiguration gefunden")
            raise ValueError("Der Gerätename muss im Config Flow konfiguriert werden")
            
        self._register_definitions = None  # Änderung zu None für bessere Kontrolle
        self._cached_values = {}
        self._last_read = {}
        self._current_firmware_version = None
        self._coordinators = {}  # Lokales Dictionary für Koordinatoren
        self.entities: Dict[str, Entity] = {}
        self._setup_complete = False
        self._entity_configs = {}

        self._logger.debug(
            "Gerät initialisiert",
            extra={
                "name": self.name,
                "device_type": self.device_type
            }
        )

    async def read_registers(self) -> Dict[str, Any]:
        """Liest alle konfigurierten Register des Geräts."""
        try:
            self._logger.debug(
                "Starte Register-Lesevorgang", 
                extra={
                    "device_type": self.device_type,
                    "name": self.name
                }
            )

            result = {}
            register_defs = await self._get_register_definitions()
            
            self._logger.debug(
                "Geladene Register-Definitionen",
                extra={
                    "device": self.name,
                    "definitions": register_defs
                }
            )

            if not register_defs:
                self._logger.error("Keine Register-Definitionen gefunden")
                return {}

            # Extrahiere die lesbaren Register entsprechend der YAML-Struktur
            read_registers = []
            if isinstance(register_defs, dict):
                if "registers" in register_defs and isinstance(register_defs["registers"], dict):
                    read_registers = register_defs["registers"].get("read", [])
                elif "read" in register_defs:
                    read_registers = register_defs["read"]

            if not read_registers:
                self._logger.warning(
                    "Keine lesbaren Register gefunden",
                    extra={
                        "device": self.name,
                        "register_defs": register_defs
                    }
                )
                return {}

            self._logger.debug(
                "Gefundene Register",
                extra={
                    "device": self.name,
                    "count": len(read_registers),
                    "registers": [reg.get("name") for reg in read_registers]
                }
            )

            # Gruppiere Register nach Adressen für Batch-Lesungen
            grouped_registers = self._group_registers(read_registers)

            for group in grouped_registers:
                try:
                    # Lese die Gruppe von Registern
                    values = await self._read_register_group(group)
                    if values:
                        result.update(values)
                except Exception as e:
                    self._logger.error(
                        "Fehler beim Lesen einer Register-Gruppe",
                        extra={
                            "error": str(e),
                            "addresses": [reg["address"] for reg in group],
                            "device": self.name
                        }
                    )

            self._logger.debug(
                "Register-Lesevorgang abgeschlossen",
                extra={
                    "device": self.name,
                    "register_count": len(result),
                    "values": result
                }
            )

            return result

        except Exception as e:
            self._logger.error(
                "Fehler beim Lesen der Register", 
                extra={
                    "error": str(e),
                    "device": self.name
                }
            )
            return {}

    def _group_registers(self, register_defs: List[Dict]) -> List[List[Dict]]:
        """Gruppiert Register für optimierte Batch-Lesungen."""
        # Sortiere nach Adresse
        sorted_regs = sorted(register_defs, key=lambda x: x["address"])
        groups = []
        current_group = []

        for reg in sorted_regs:
            if not current_group:
                current_group.append(reg)
            else:
                # Prüfe ob Register kontinuierlich sind
                last_reg = current_group[-1]
                if (
                    reg["address"] - (last_reg["address"] + last_reg.get("count", 1))
                ) <= 1:
                    current_group.append(reg)
                else:
                    groups.append(current_group)
                    current_group = [reg]

        if current_group:
            groups.append(current_group)

        return groups

    async def _read_register_group(self, group: List[Dict]) -> Dict[str, Any]:
        """Liest eine Gruppe von Registern."""
        if not group:
            return {}

        try:
            # Bestimme Start- und Endadresse
            start_address = group[0]["address"]
            end_reg = group[-1]
            count = (end_reg["address"] - start_address) + end_reg.get("count", 1)

            self._logger.debug(
                "Lese Register-Gruppe",
                extra={
                    "device": self.name,
                    "start_address": start_address,
                    "count": count,
                    "registers": [
                        {
                            "name": reg["name"],
                            "address": reg["address"],
                            "type": reg.get("type", "uint16"),
                            "register_type": reg.get("register_type", "holding")
                        } for reg in group
                    ]
                }
            )

            # Lese die Register als Block
            values = await self.hub.read_register(
                device_name=self.device_type,
                address=start_address,
                count=count,
                reg_type="uint16",  # Rohdaten lesen
                register_type=group[0].get("register_type", "holding")  # Verwende den Register-Typ aus der Definition
            )

            self._logger.debug(
                "Rohdaten empfangen",
                extra={
                    "device": self.name,
                    "start_address": start_address,
                    "count": count,
                    "raw_values": values
                }
            )

            if not values:
                self._logger.warning(
                    "Keine Werte vom Register empfangen",
                    extra={
                        "device": self.name,
                        "start_address": start_address,
                        "count": count
                    }
                )
                return {}

            # Verarbeite die Werte für jedes Register
            result = {}
            for reg in group:
                try:
                    offset = reg["address"] - start_address
                    reg_count = reg.get("count", 1)
                    reg_values = values[offset : offset + reg_count]

                    self._logger.debug(
                        "Verarbeite Register",
                        extra={
                            "device": self.name,
                            "register": reg["name"],
                            "address": reg["address"],
                            "type": reg.get("type", "uint16"),
                            "raw_values": reg_values
                        }
                    )

                    if reg_values:
                        processed_value = await self.hub._process_register_value(
                            reg_values,
                            reg.get("type", "uint16"),
                            reg.get("scale", 1),
                            reg.get("swap"),
                        )

                        if processed_value is not None:
                            result[reg["name"]] = processed_value
                            self._logger.debug(
                                "Register erfolgreich verarbeitet",
                                extra={
                                    "device": self.name,
                                    "register": reg["name"],
                                    "raw_value": reg_values,
                                    "processed_value": processed_value
                                }
                            )
                        else:
                            self._logger.warning(
                                "Register-Verarbeitung ergab None",
                                extra={
                                    "device": self.name,
                                    "register": reg["name"],
                                    "raw_value": reg_values
                                }
                            )
                except Exception as e:
                    self._logger.error(
                        "Fehler bei der Verarbeitung eines einzelnen Registers",
                        extra={
                            "error": str(e),
                            "device": self.name,
                            "register": reg.get("name"),
                            "address": reg.get("address")
                        }
                    )

            return result

        except Exception as e:
            self._logger.error(
                "Fehler beim Lesen einer Register-Gruppe",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "start_address": start_address,
                    "count": count
                }
            )
            return {}

    async def _get_register_definitions(self) -> List[Dict]:
        """Lädt die Register-Definitionen für das Gerät."""
        try:
            if not self._register_definitions:
                device_def = await self.get_device_definition()
                self._logger.debug(
                    "Geladene Gerätedefinition",
                    extra={
                        "device": self.name,
                        "definition": device_def
                    }
                )
                
                if device_def and "registers" in device_def:
                    self._register_definitions = device_def["registers"]
                    self._logger.debug(
                        "Register-Definitionen gesetzt",
                        extra={
                            "device": self.name,
                            "registers": self._register_definitions
                        }
                    )
                else:
                    self._logger.error(
                        "Keine Register in der Gerätedefinition gefunden",
                        extra={
                            "device": self.name,
                            "device_type": self.device_type
                        }
                    )
            return self._register_definitions
        except Exception as e:
            self._logger.error(
                "Fehler beim Laden der Register-Definitionen",
                extra={
                    "error": str(e),
                    "device": self.name
                }
            )
            return {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.name)},
            name=self.name,
            manufacturer=self.config.get("manufacturer", "Unknown"),
            model=self.config.get("model", "Unknown"),
            sw_version=self._current_firmware_version,
        )

    async def async_update_ha_state(self):
        """Update Home Assistant state."""
        if self.config.get("firmware_handling", {}).get("auto_detect", False):
            current_version = await self.detect_firmware_version()
            if current_version != self._current_firmware_version:
                self._logger.info(
                    "Firmware version changed",
                    old_version=self._current_firmware_version,
                    new_version=current_version,
                )
                await self.update_register_definitions(current_version)
                self._current_firmware_version = current_version

    async def detect_firmware_version(self) -> Optional[str]:
        """Erkennt die Firmware-Version aus den Registern.
        
        Die Version wird aus mehreren uint16-Registern zusammengesetzt:
        - Erstes Register (z.B. 4953): 0xAABB = Version AA.BB
        - Zweites Register (z.B. 4954): 0xCCDD = Version CC.DD
        Ergibt: Version AA.BB.CC.DD
        """
        try:
            device_def = await self.get_device_definition()
            if not device_def or "firmware" not in device_def:
                return None

            firmware_config = device_def["firmware"]
            version_registers = firmware_config.get("version_registers", [])
            
            if not version_registers:
                self._logger.error("Keine Version-Register konfiguriert")
                return None

            version_parts = []
            for reg in version_registers:
                value = await self.hub.read_register(
                    device_name=self.name,
                    address=reg["address"],
                    reg_type="uint16"
                )
                
                if not value:
                    self._logger.error(
                        "Konnte Version-Register nicht lesen",
                        extra={
                            "register": reg["name"],
                            "address": reg["address"]
                        }
                    )
                    return None
                
                # Extrahiere Major und Minor aus dem uint16-Wert
                # z.B. 0x0123 wird zu 1.23
                major = (value[0] >> 8) & 0xFF
                minor = value[0] & 0xFF
                version_parts.extend([major, minor])

            # Formatiere die Version entsprechend der Konfiguration
            version_format = firmware_config.get("version_format", "{:d}.{:d}.{:d}.{:d}")
            version = version_format.format(*version_parts)

            self._logger.info(
                "Firmware-Version erkannt",
                extra={
                    "device": self.name,
                    "version": version,
                    "raw_values": version_parts
                }
            )

            return version

        except Exception as e:
            self._logger.error(
                "Fehler bei der Firmware-Versionserkennung",
                extra={
                    "error": str(e),
                    "device": self.name
                }
            )
            return None

    async def update_register_definitions(self, firmware_version: str) -> None:
        """Aktualisiert die Register-Definitionen basierend auf der Firmware-Version."""
        try:
            self._logger.debug(
                "Aktualisiere Register-Definitionen für Firmware-Version %s",
                firmware_version,
            )

            # Lade die vollständige Geräte-Definition
            device_definitions = await self.get_device_definition()
            if not device_definitions:
                self._logger.warning(
                    "No device definitions found for %s", self.device_type
                )
                return

            # Bereinige alte Entitäten vor dem Update
            await self._cleanup_entities()

            # Speichere die neuen Register-Definitionen
            if "registers" in device_definitions:
                self._register_definitions = device_definitions["registers"]
                self._logger.debug(
                    "Neue Register-Definitionen geladen",
                    extra={
                        "device": self.name,
                        "registers": self._register_definitions
                    }
                )

                # Aktualisiere die Polling-Konfiguration
                polling_config = device_definitions.get("polling", {})
                
                # Aktualisiere oder erstelle Koordinatoren für jede Polling-Gruppe
                for group_name, group_config in polling_config.items():
                    interval = group_config.get("interval", 30)
                    
                    # Wenn der Koordinator bereits existiert, aktualisiere ihn
                    if group_name in self._coordinators:
                        coordinator = self._coordinators[group_name]
                        coordinator.update_interval = timedelta(seconds=interval)
                        await coordinator.async_refresh()
                        self._logger.debug(
                            "Koordinator aktualisiert",
                            extra={
                                "device": self.name,
                                "group": group_name,
                                "interval": interval
                            }
                        )
                    else:
                        # Erstelle einen neuen Koordinator
                        coordinator = DataUpdateCoordinator(
                            self.hass,
                            self._logger,
                            name=f"{self.name}_{group_name}",
                            update_method=self.read_registers,
                            update_interval=timedelta(seconds=interval),
                        )
                        self._coordinators[group_name] = coordinator
                        await coordinator.async_refresh()
                        self._logger.debug(
                            "Neuer Koordinator erstellt",
                            extra={
                                "device": self.name,
                                "group": group_name,
                                "interval": interval
                            }
                        )

                # Entferne nicht mehr benötigte Koordinatoren
                for group_name in list(self._coordinators.keys()):
                    if group_name not in polling_config:
                        coordinator = self._coordinators.pop(group_name)
                        await coordinator.async_shutdown()
                        self._logger.debug(
                            "Koordinator entfernt",
                            extra={
                                "device": self.name,
                                "group": group_name
                            }
                        )

                # Aktualisiere die Entitäten im Entity Registry
                await self._update_entity_registry()

            self._logger.info(
                "Register-Definitionen erfolgreich aktualisiert",
                extra={
                    "device": self.name,
                    "firmware_version": firmware_version,
                    "coordinator_count": len(self._coordinators)
                }
            )

        except Exception as e:
            self._logger.error(
                "Fehler beim Aktualisieren der Register-Definitionen",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "firmware_version": firmware_version
                }
            )

    async def _update_entity_registry(self):
        """Aktualisiert die Entitäten im Entity Registry."""
        try:
            ent_reg = er.async_get(self.hass)
            dev_reg = dr.async_get(self.hass)
            
            # Finde das Gerät im Device Registry
            device_entry = dev_reg.async_get_device(
                identifiers={(DOMAIN, self.name)}
            )
            
            if not device_entry:
                self._logger.error(
                    "Gerät nicht im Device Registry gefunden",
                    extra={"device": self.name}
                )
                return

            # Hole alle Entitäten für dieses Gerät
            entities = er.async_entries_for_device(
                ent_reg,
                device_entry.id,
                include_disabled_entities=True
            )

            # Aktualisiere jede Entität
            for entity in entities:
                try:
                    # Erzwinge eine Aktualisierung der Entität
                    if entity.disabled:
                        # Aktiviere deaktivierte Entitäten
                        ent_reg.async_update_entity(
                            entity.entity_id,
                            disabled_by=None
                        )
                    
                    # Trigger eine Aktualisierung
                    self.hass.states.async_set(
                        entity.entity_id,
                        "unavailable",
                        {
                            "friendly_name": entity.name,
                            "device_class": entity.device_class,
                            "unit_of_measurement": entity.unit_of_measurement
                        }
                    )
                    
                    self._logger.debug(
                        "Entität aktualisiert",
                        extra={
                            "device": self.name,
                            "entity_id": entity.entity_id
                        }
                    )
                
                except Exception as e:
                    self._logger.error(
                        "Fehler beim Aktualisieren der Entität",
                        extra={
                            "error": str(e),
                            "device": self.name,
                            "entity_id": entity.entity_id
                        }
                    )

        except Exception as e:
            self._logger.error(
                "Fehler beim Aktualisieren des Entity Registry",
                extra={
                    "error": str(e),
                    "device": self.name
                }
            )

    async def async_setup(self) -> bool:
        """Führe das Setup des Geräts durch."""
        try:
            _LOGGER.debug(
                "Starte Setup für Gerät",
                extra={
                    "device_type": self.device_type,
                    "name": self.config.get(CONF_NAME)
                }
            )

            # Bereinige alte Entities
            await self.cleanup_entities()

            # Erstelle neue Entities basierend auf den Register-Definitionen
            await self.create_entities()

            self._setup_complete = True
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup des Geräts",
                extra={
                    "error": str(e),
                    "device_type": self.device_type,
                    "name": self.config.get(CONF_NAME)
                }
            )
            return False

    async def cleanup_entities(self):
        """Bereinige nicht mehr benötigte Entities."""
        try:
            # Hole alle registrierten Entities für dieses Gerät
            device_entities = self.hass.data[DOMAIN].get(self.config["entry_id"], {}).get("entities", {})
            
            # Erstelle eine Liste der aktuell gültigen Entity-IDs
            valid_entity_ids = set()
            for reg_def in self.register_definitions.get("read", []):
                entity_id = f"{self.config['name']}_{reg_def['name']}"
                valid_entity_ids.add(entity_id)
            
            # Entferne Entities, die nicht mehr in den Definitionen sind
            for entity_id, entity in list(device_entities.items()):
                if entity_id not in valid_entity_ids:
                    _LOGGER.debug(f"Entferne Entity {entity_id}")
                    await entity.async_remove()
                    if entity_id in device_entities:
                        del device_entities[entity_id]

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Bereinigen der Entities",
                extra={
                    "error": str(e),
                    "device_type": self.device_type,
                    "name": self.config.get(CONF_NAME)
                }
            )

    async def create_entities(self):
        """Erstelle Entities basierend auf den Register-Definitionen."""
        try:
            # Erstelle Entities für lesbare Register
            for reg_def in self.register_definitions.get("read", []):
                entity_id = f"{self.config['name']}_{reg_def['name']}"
                if entity_id not in self.entities:
                    entity_config = {
                        "name": f"{self.config['name']} {reg_def.get('description', reg_def['name'])}",
                        "unique_id": f"{self.config['entry_id']}_{reg_def['name']}",
                        "device_class": reg_def.get("device_class"),
                        "state_class": reg_def.get("state_class"),
                        "unit_of_measurement": reg_def.get("unit"),
                        "register": reg_def
                    }
                    self._entity_configs[entity_id] = entity_config

            # Registriere die Entities bei Home Assistant
            if self._entity_configs:
                self.hass.async_create_task(
                    self.hass.config_entries.async_forward_entry_setup(
                        self.config["entry_id"],
                        "sensor"
                    )
                )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen der Entities",
                extra={
                    "error": str(e),
                    "device_type": self.device_type,
                    "name": self.config.get(CONF_NAME)
                }
            )

    async def async_update(self):
        """Update device data."""
        if not self._setup_complete:
            _LOGGER.warning("Update wurde aufgerufen, bevor das Setup abgeschlossen war")
            return

        try:
            # Aktualisiere die Werte aller Register
            for reg_def in self.register_definitions.get("read", []):
                try:
                    value = await self.hub.read_register(
                        device_name=self.config["name"],
                        address=reg_def["address"],
                        reg_type=reg_def.get("type", "uint16"),
                        count=reg_def.get("count", 1),
                        scale=reg_def.get("scale", 1),
                        swap=reg_def.get("swap"),
                        register_type=reg_def.get("register_type", "holding")
                    )

                    entity_id = f"{self.config['name']}_{reg_def['name']}"
                    if entity_id in self.entities:
                        self.entities[entity_id].update_value(value)

                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Lesen des Registers",
                        extra={
                            "error": str(e),
                            "register": reg_def["name"],
                            "address": reg_def["address"]
                        }
                    )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Update des Geräts",
                extra={
                    "error": str(e),
                    "device_type": self.device_type,
                    "name": self.config.get(CONF_NAME)
                }
            )

    async def async_teardown(self):
        """Teardown the device."""
        try:
            _LOGGER.debug(
                "Starte Teardown für Gerät",
                extra={
                    "device_type": self.device_type,
                    "name": self.config.get(CONF_NAME)
                }
            )

            # Bereinige alle Entities
            await self.cleanup_entities()

            self._setup_complete = False

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Teardown des Geräts",
                extra={
                    "error": str(e),
                    "device_type": self.device_type,
                    "name": self.config.get(CONF_NAME)
                }
            )

    def get_entity_configs(self) -> Dict[str, Any]:
        """Gibt die Entity-Konfigurationen zurück."""
        return self._entity_configs

    def register_entity(self, entity_id: str, entity: Entity):
        """Registriert eine Entity."""
        self.entities[entity_id] = entity

    async def get_device_definition(self) -> Dict[str, Any]:
        """Lädt die Gerätekonfiguration basierend auf dem Gerätetyp."""
        try:
            # Bestimme den Pfad zur Gerätedefinitionsdatei
            definition_path = (
                Path(__file__).parent
                / "device_definitions"
                / f"{self.device_type}.yaml"
            )

            self._logger.debug(
                "Versuche Gerätedefinition zu laden",
                extra={
                    "device": self.name,
                    "path": str(definition_path),
                    "exists": definition_path.exists()
                }
            )

            if not definition_path.exists():
                self._logger.error(
                    "Gerätedefinitionsdatei nicht gefunden",
                    extra={
                        "device_type": self.device_type,
                        "path": str(definition_path),
                    },
                )
                return None

            # Lade die Gerätedefinition asynchron
            async with aiofiles.open(definition_path, "r", encoding="utf-8") as f:
                content = await f.read()
                self._logger.debug(
                    "YAML-Inhalt geladen",
                    extra={
                        "device": self.name,
                        "content": content[:200]  # Zeige die ersten 200 Zeichen
                    }
                )
                device_definition = yaml.safe_load(content)

            self._logger.debug(
                "Gerätedefinition geladen",
                extra={
                    "device": self.name,
                    "definition": device_definition
                }
            )

            # Verarbeite 'include' Direktiven
            if "include" in device_definition:
                for include_file in device_definition["include"]:
                    include_path = Path(__file__).parent / include_file
                    if include_path.exists():
                        async with aiofiles.open(
                            include_path, "r", encoding="utf-8"
                        ) as f:
                            include_content = await f.read()
                            include_data = yaml.safe_load(include_content)
                            # Merge die inkludierten Daten
                            device_definition = self._merge_definitions(
                                device_definition, include_data
                            )
                    else:
                        self._logger.warning(
                            "Include-Datei nicht gefunden",
                            extra={"file": str(include_path), "device": self.name},
                        )

            # Verarbeite Firmware-spezifische Register
            if "firmware_versions" in device_definition:
                current_version = self._current_firmware_version or self.config.get(
                    "firmware_handling", {}
                ).get("fallback_version")
                if (
                    current_version
                    and current_version in device_definition["firmware_versions"]
                ):
                    firmware_specific = device_definition["firmware_versions"][
                        current_version
                    ]
                    device_definition = self._merge_definitions(
                        device_definition, firmware_specific
                    )

            # Entferne die firmware_versions aus der finalen Definition
            if "firmware_versions" in device_definition:
                del device_definition["firmware_versions"]

            return device_definition

        except Exception as e:
            self._logger.error(
                "Fehler beim Laden der Gerätedefinition",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "device_type": self.device_type,
                },
            )
            return None

    def _merge_definitions(
        self, base: Dict[str, Any], overlay: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Führt zwei Definitionen zusammen.

        Args:
            base: Basis-Definition
            overlay: Zu überlagernde Definition

        Returns:
            Zusammengeführte Definition
        """
        result = base.copy()

        for key, value in overlay.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_definitions(result[key], value)
            elif (
                key in result
                and isinstance(result[key], list)
                and isinstance(value, list)
            ):
                # Für Register: Ersetze bestehende Einträge mit gleichem Namen
                if key == "registers":
                    existing_names = {
                        item.get("name"): i for i, item in enumerate(result[key])
                    }
                    for new_item in value:
                        if new_item.get("name") in existing_names:
                            result[key][existing_names[new_item["name"]]] = new_item
                        else:
                            result[key].append(new_item)
                else:
                    result[key].extend(value)
            else:
                result[key] = value

        return result

    async def write_register(self, register_name: str, value: Any) -> bool:
        """Schreibt einen Wert in ein Register.
        
        Args:
            register_name: Name des Registers aus der Gerätedefinition
            value: Zu schreibender Wert
            
        Returns:
            True wenn erfolgreich, False sonst
        """
        try:
            self._logger.debug(
                "Starte Schreibvorgang",
                extra={
                    "device": self.name,
                    "register": register_name,
                    "value": value
                }
            )

            # Lade Register-Definitionen
            register_defs = await self._get_register_definitions()
            if not register_defs:
                self._logger.error("Keine Register-Definitionen gefunden")
                return False

            # Finde das Write-Register
            write_registers = []
            if isinstance(register_defs, dict):
                if "registers" in register_defs and isinstance(register_defs["registers"], dict):
                    write_registers = register_defs["registers"].get("write", [])
                elif "write" in register_defs:
                    write_registers = register_defs["write"]

            # Suche das spezifische Register
            register = None
            for reg in write_registers:
                if reg.get("name") == register_name:
                    register = reg
                    break

            if not register:
                self._logger.error(
                    "Register nicht gefunden",
                    extra={
                        "device": self.name,
                        "register": register_name
                    }
                )
                return False

            # Schreibe den Wert
            success = await self.hub.write_register(
                device_name=self.name,
                address=register["address"],
                value=value,
                reg_type=register.get("type", "uint16"),
                scale=register.get("scale", 1),
                swap=register.get("swap")
            )

            if success:
                self._logger.info(
                    "Schreibvorgang erfolgreich",
                    extra={
                        "device": self.name,
                        "register": register_name,
                        "value": value
                    }
                )
            else:
                self._logger.error(
                    "Schreibvorgang fehlgeschlagen",
                    extra={
                        "device": self.name,
                        "register": register_name,
                        "value": value
                    }
                )

            return success

        except Exception as e:
            self._logger.error(
                "Fehler beim Schreiben des Registers",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "register": register_name,
                    "value": value
                }
            )
            return False

    async def write_registers(self, values: Dict[str, Any]) -> bool:
        """Schreibt mehrere Werte in Register.
        
        Args:
            values: Dictionary mit Register-Namen und Werten
            
        Returns:
            True wenn alle Schreibvorgänge erfolgreich, False sonst
        """
        try:
            success = True
            for register_name, value in values.items():
                if not await self.write_register(register_name, value):
                    success = False
                    self._logger.error(
                        "Fehler beim Schreiben eines Registers in der Gruppe",
                        extra={
                            "device": self.name,
                            "register": register_name,
                            "value": value
                        }
                    )
            return success
        except Exception as e:
            self._logger.error(
                "Fehler beim Schreiben mehrerer Register",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "values": values
                }
            )
            return False

    async def _cleanup_entities(self):
        """Bereinigt nicht mehr benötigte Entitäten basierend auf der aktuellen Gerätedefinition."""
        try:
            # Hole aktuelle Register-Definitionen
            register_defs = await self._get_register_definitions()
            if not register_defs or "registers" not in register_defs:
                return

            # Erstelle Liste aller gültigen Register-Namen
            valid_registers = set()
            if isinstance(register_defs["registers"], dict):
                # Füge Read-Register hinzu
                for reg in register_defs["registers"].get("read", []):
                    valid_registers.add(reg["name"])
                # Füge Write-Register hinzu
                for reg in register_defs["registers"].get("write", []):
                    valid_registers.add(reg["name"])

            self._logger.debug(
                "Gültige Register",
                extra={
                    "device": self.name,
                    "registers": list(valid_registers)
                }
            )

            # Hole Registry-Einträge
            ent_reg = er.async_get(self.hass)
            dev_reg = dr.async_get(self.hass)
            
            device_entry = dev_reg.async_get_device(
                identifiers={(DOMAIN, self.name)}
            )
            
            if not device_entry:
                self._logger.error("Gerät nicht im Device Registry gefunden")
                return

            # Hole alle Entitäten für dieses Gerät
            entities = er.async_entries_for_device(
                ent_reg,
                device_entry.id,
                include_disabled_entities=True
            )

            # Überprüfe jede Entität
            for entity in entities:
                try:
                    # Extrahiere Register-Namen aus der Entity-ID
                    # Format ist normalerweise: sensor.device_name_register_name
                    parts = entity.entity_id.split("_")
                    if len(parts) > 1:
                        register_name = parts[-1]  # Letzter Teil sollte der Register-Name sein
                        
                        # Wenn das Register nicht mehr in der Definition existiert
                        if register_name not in valid_registers:
                            self._logger.info(
                                "Entferne nicht mehr benötigte Entität",
                                extra={
                                    "device": self.name,
                                    "entity_id": entity.entity_id,
                                    "register": register_name
                                }
                            )
                            # Entferne die Entität
                            ent_reg.async_remove(entity.entity_id)

                except Exception as e:
                    self._logger.error(
                        "Fehler beim Überprüfen einer Entität",
                        extra={
                            "error": str(e),
                            "entity_id": entity.entity_id
                        }
                    )

        except Exception as e:
            self._logger.error(
                "Fehler beim Bereinigen der Entitäten",
                extra={
                    "error": str(e),
                    "device": self.name
                }
            )
