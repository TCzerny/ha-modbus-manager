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

            # Lese die Register als Block
            values = await self.hub.read_register(
                device_name=self.device_type,
                address=start_address,
                count=count,
                reg_type="uint16",  # Rohdaten lesen
            )

            if not values:
                return {}

            # Verarbeite die Werte für jedes Register
            result = {}
            for reg in group:
                offset = reg["address"] - start_address
                reg_count = reg.get("count", 1)
                reg_values = values[offset : offset + reg_count]

                if reg_values:
                    processed_value = await self.hub._process_register_value(
                        reg_values,
                        reg.get("type", "uint16"),
                        reg.get("scale", 1),
                        reg.get("swap"),
                    )

                    if processed_value is not None:
                        result[reg["name"]] = processed_value

            return result

        except Exception as e:
            self._logger.error(
                "Fehler beim Lesen einer Register-Gruppe",
                extra={"error": str(e), "start_address": start_address, "count": count},
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
        """Detect firmware version from device."""
        try:
            # Implementierung der Firmware-Erkennung
            return "1.0.0"  # Platzhalter
        except Exception as e:
            self._logger.warning(
                "Could not detect firmware version", error=e, device=self.name
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

            # Update der Register basierend auf der Firmware-Version
            # Implementieren Sie die Logik entsprechend Ihren Anforderungen

            self.register_definitions = device_definitions
            self._logger.info(
                "Register-Definitionen erfolgreich für Firmware-Version %s aktualisiert",
                firmware_version,
            )

            # Informiere den Modbus-Hub, dass die Register-Definitionen aktualisiert wurden
            entry_id = self.config.get("entry_id")
            if not entry_id or entry_id not in self.hass.data[DOMAIN]:
                self._logger.error("Hub not found", entry_id=entry_id)
                return

            hub = self.hass.data[DOMAIN][entry_id]
            await hub.reload_registers(self.name, firmware_version)

        except Exception as e:
            self._logger.error(
                "Fehler beim Aktualisieren der Register-Definitionen: %s",
                e,
                firmware_version=firmware_version,
                device=self.name,
            )

    async def async_setup(self) -> bool:
        """Führe das Setup des Geräts durch."""
        try:
            self._logger.debug("Starte Geräte-Setup", extra={"device": self.name})

            # Lade die Gerätedefinition
            device_definition = await self.get_device_definition()
            if not device_definition:
                self._logger.error(
                    "Keine Gerätedefinition gefunden", 
                    extra={"device": self.name}
                )
                return False

            # Speichere die Register-Definitionen
            if "registers" in device_definition:
                self._register_definitions = device_definition["registers"]
            else:
                self._logger.error(
                    "Keine Register in der Gerätedefinition gefunden",
                    extra={"device": self.name}
                )
                return False

            # Firmware-Version erkennen (optional)
            if self.config.get("firmware_handling", {}).get("auto_detect", False):
                firmware_version = await self.detect_firmware_version()
                if firmware_version:
                    self._current_firmware_version = firmware_version
                    self._logger.info(
                        "Firmware-Version erkannt",
                        extra={
                            "version": firmware_version,
                            "device": self.name
                        }
                    )

            # Initialisiere die Polling-Intervalle
            polling_config = device_definition.get("polling", {})
            
            # Erstelle Coordinators für jede Polling-Gruppe
            for group_name, group_config in polling_config.items():
                interval = group_config.get("interval", 30)
                
                coordinator = DataUpdateCoordinator(
                    self.hass,
                    self._logger,
                    name=f"{self.name}_{group_name}",
                    update_method=self.read_registers,  # Direkte Referenz
                    update_interval=timedelta(seconds=interval),
                )
                
                self._coordinators[group_name] = coordinator
                
                # Erste Aktualisierung ohne await
                coordinator.async_refresh()

            self._logger.info(
                "Geräte-Setup abgeschlossen",
                extra={
                    "device": self.name,
                    "polling_groups": list(polling_config.keys())
                }
            )
            return True

        except Exception as e:
            self._logger.error(
                "Fehler beim Geräte-Setup",
                error=e,
                extra={"device": self.name}
            )
            return False

    async def async_teardown(self):
        """Bereinigt das Gerät und stoppt alle laufenden Prozesse."""
        try:
            self._logger.info("Starte Teardown für Gerät", extra={"device": self.name})

            # Stoppe alle laufenden Koordinatoren
            for coordinator in self.hass.data[DOMAIN].get("coordinators", {}).values():
                await coordinator.async_shutdown()

            # Bereinige Geräteregistrierungen
            dev_reg = dr.async_get(self.hass)
            device_entry = dev_reg.async_get_device(identifiers={(DOMAIN, self.name)})
            if device_entry:
                self._logger.debug(
                    "Entferne Gerät aus Registry", extra={"device": self.name}
                )
                dev_reg.async_remove_device(device_entry.id)

            # Bereinige Entitätsregistrierungen
            ent_reg = er.async_get(self.hass)
            entities = er.async_entries_for_device(
                ent_reg,
                device_entry.id if device_entry else None,
                include_disabled_entities=True,
            )
            for entity in entities:
                self._logger.debug(
                    "Entferne Entität",
                    extra={"entity_id": entity.entity_id, "device": self.name},
                )
                ent_reg.async_remove(entity.entity_id)

            self._logger.info(
                "Teardown erfolgreich abgeschlossen", extra={"device": self.name}
            )

        except Exception as e:
            self._logger.error(
                "Fehler beim Teardown", extra={"error": str(e), "device": self.name}
            )
            raise

    async def get_device_definition(self) -> Dict[str, Any]:
        """Lädt die Gerätekonfiguration basierend auf dem Gerätetyp.

        Returns:
            Dict mit der Gerätekonfiguration oder None bei Fehler
        """
        try:
            # Bestimme den Pfad zur Gerätedefinitionsdatei
            definition_path = (
                Path(__file__).parent
                / "device_definitions"
                / f"{self.device_type}.yaml"
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
                device_definition = yaml.safe_load(content)

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
