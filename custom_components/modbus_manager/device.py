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
from typing import Dict, Any, Optional

class ModbusManagerDevice:
    """Class representing a Modbus device."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
        """Initialize the device.
        
        Args:
            hass: HomeAssistant instance
            config: Configuration dictionary
        """
        self.hass = hass
        self.config = config

        # Sicherstellen, dass 'name' im config vorhanden ist
        if "name" not in config:
            raise KeyError("'name' Schlüssel fehlt im config Dictionary")

        self.name = config["name"]
        self.host = config.get("host")
        self.port = config.get("port")
        self.slave = config.get("slave")
        self.device_type = config.get("device_type")
        self.logger = ModbusManagerLogger(self.name)
        self.register_definitions = {}
        self._current_firmware_version = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.name)},
            name=self.name,
            manufacturer=self.config.get("manufacturer", "Unknown"),
            model=self.config.get("model", "Unknown"),
            sw_version=self._current_firmware_version
        )

    async def async_update_ha_state(self):
        """Update Home Assistant state."""
        if self.config.get("firmware_handling", {}).get("auto_detect", False):
            current_version = await self.detect_firmware_version()
            if current_version != self._current_firmware_version:
                self.logger.info(
                    "Firmware version changed",
                    old_version=self._current_firmware_version,
                    new_version=current_version
                )
                await self.update_register_definitions(current_version)
                self._current_firmware_version = current_version

    async def detect_firmware_version(self) -> Optional[str]:
        """Detect firmware version from device."""
        try:
            # Implementierung der Firmware-Erkennung
            return "1.0.0"  # Platzhalter
        except Exception as e:
            self.logger.warning(
                "Could not detect firmware version",
                error=e,
                device=self.name
            )
            return None

    async def update_register_definitions(self, firmware_version: str) -> None:
        """Aktualisiert die Register-Definitionen basierend auf der Firmware-Version."""
        try:
            self.logger.debug("Aktualisiere Register-Definitionen für Firmware-Version %s", firmware_version)
            
            # Lade die vollständige Geräte-Definition
            device_definitions = self.get_device_definition()
            if not device_definitions:
                self.logger.warning("No device definitions found for %s", self.device_type)
                return
            
            # Update der Register basierend auf der Firmware-Version
            # Implementieren Sie die Logik entsprechend Ihren Anforderungen
            
            self.register_definitions = device_definitions
            self.logger.info(
                "Register-Definitionen erfolgreich für Firmware-Version %s aktualisiert",
                firmware_version
            )
            
            # Informiere den Modbus-Hub, dass die Register-Definitionen aktualisiert wurden
            entry_id = self.config.get("entry_id")
            if not entry_id or entry_id not in self.hass.data[DOMAIN]:
                self.logger.error("Hub not found", entry_id=entry_id)
                return

            hub = self.hass.data[DOMAIN][entry_id]
            await hub.reload_registers(self.name, firmware_version)
            
        except Exception as e:
            self.logger.error(
                "Fehler beim Aktualisieren der Register-Definitionen: %s",
                e,
                firmware_version=firmware_version,
                device=self.name
            )

    async def async_setup(self) -> bool:
        """Set up the device."""
        try:
            self.logger.debug("Starting device setup", extra={"device": self.name})
            
            # Lade die Gerätedefinition
            device_definition = self.get_device_definition()
            if not device_definition:
                self.logger.error(
                    "Keine Gerätedefinition gefunden",
                    extra={"device": self.name}
                )
                return False

            # Speichere die Register-Definitionen
            self.register_definitions = device_definition
            
            # Firmware-Version erkennen
            if self.config.get("firmware_handling", {}).get("auto_detect", False):
                firmware_version = await self.detect_firmware_version()
                if firmware_version:
                    self.logger.info(
                        "Detected firmware version",
                        extra={
                            "version": firmware_version,
                            "device": self.name
                        }
                    )
                    await self.update_register_definitions(firmware_version)
                    self._current_firmware_version = firmware_version

            # Hole den Hub aus den Home Assistant Daten
            entry_id = self.config.get("entry_id")
            if not entry_id or entry_id not in self.hass.data[DOMAIN]:
                self.logger.error("Hub nicht gefunden", entry_id=entry_id)
                return False

            hub = self.hass.data[DOMAIN][entry_id]

            # Initialisiere die Polling-Intervalle
            polling_config = device_definition.get("polling", {})
            update_intervals = {}
            
            for group_name, group_config in polling_config.items():
                interval = group_config.get("interval", 30)
                registers = group_config.get("registers", [])
                
                coordinator = DataUpdateCoordinator(
                    self.hass,
                    self.logger,
                    name=f"{self.name} {group_name} Coordinator",
                    update_method=lambda r=registers: self.read_registers(),
                    update_interval=timedelta(seconds=interval)
                )
                
                update_intervals[group_name] = {
                    "coordinator": coordinator,
                    "registers": registers,
                    "interval": interval
                }

            # Speichere die Update-Intervalle im Hub
            if not hasattr(hub, "update_intervals"):
                hub.update_intervals = {}
            hub.update_intervals[self.name] = update_intervals

            # Führe erste Aktualisierung für alle Koordinatoren durch
            for group_config in update_intervals.values():
                await group_config["coordinator"].async_refresh()
            
            self.logger.info(
                "Device setup complete",
                extra={
                    "device": self.name,
                    "entry_id": entry_id,
                    "polling_groups": list(update_intervals.keys())
                }
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Device setup failed",
                error=e,
                extra={
                    "device": self.name
                }
            )
            return False

    async def async_teardown(self):
        """Bereinigt das Gerät und stoppt alle laufenden Prozesse."""
        try:
            self.logger.info("Starte Teardown für Gerät", extra={"device": self.name})
            
            # Stoppe alle laufenden Koordinatoren
            for coordinator in self.hass.data[DOMAIN].get("coordinators", {}).values():
                await coordinator.async_shutdown()
            
            # Bereinige Geräteregistrierungen
            dev_reg = dr.async_get(self.hass)
            device_entry = dev_reg.async_get_device(identifiers={(DOMAIN, self.name)})
            if device_entry:
                self.logger.debug("Entferne Gerät aus Registry", extra={"device": self.name})
                dev_reg.async_remove_device(device_entry.id)
            
            # Bereinige Entitätsregistrierungen
            ent_reg = er.async_get(self.hass)
            entities = er.async_entries_for_device(
                ent_reg,
                device_entry.id if device_entry else None,
                include_disabled_entities=True
            )
            for entity in entities:
                self.logger.debug(
                    "Entferne Entität",
                    extra={"entity_id": entity.entity_id, "device": self.name}
                )
                ent_reg.async_remove(entity.entity_id)
            
            self.logger.info("Teardown erfolgreich abgeschlossen", extra={"device": self.name})
            
        except Exception as e:
            self.logger.error(
                "Fehler beim Teardown",
                extra={
                    "error": str(e),
                    "device": self.name
                }
            )
            raise

    def get_device_definition(self) -> Dict[str, Any]:
        """Lädt die Gerätekonfiguration basierend auf dem Gerätetyp.
        
        Returns:
            Dict mit der Gerätekonfiguration oder None bei Fehler
        """
        try:
            # Bestimme den Pfad zur Gerätedefinitionsdatei
            definition_path = Path(__file__).parent / "device_definitions" / f"{self.device_type}.yaml"
            
            if not definition_path.exists():
                self.logger.error(
                    "Gerätedefinitionsdatei nicht gefunden",
                    extra={
                        "device_type": self.device_type,
                        "path": str(definition_path)
                    }
                )
                return None
                
            # Lade die Gerätedefinition
            with open(definition_path, "r", encoding="utf-8") as f:
                device_definition = yaml.safe_load(f)
                
            # Verarbeite 'include' Direktiven
            if "include" in device_definition:
                for include_file in device_definition["include"]:
                    include_path = Path(__file__).parent / include_file
                    if include_path.exists():
                        with open(include_path, "r", encoding="utf-8") as f:
                            include_data = yaml.safe_load(f)
                            # Merge die inkludierten Daten
                            device_definition = self._merge_definitions(device_definition, include_data)
                    else:
                        self.logger.warning(
                            "Include-Datei nicht gefunden",
                            extra={
                                "file": str(include_path),
                                "device": self.name
                            }
                        )

            # Verarbeite Firmware-spezifische Register
            if "firmware_versions" in device_definition:
                current_version = self._current_firmware_version or self.config.get("firmware_handling", {}).get("fallback_version")
                if current_version and current_version in device_definition["firmware_versions"]:
                    firmware_specific = device_definition["firmware_versions"][current_version]
                    device_definition = self._merge_definitions(device_definition, firmware_specific)

            # Entferne die firmware_versions aus der finalen Definition
            if "firmware_versions" in device_definition:
                del device_definition["firmware_versions"]

            return device_definition

        except Exception as e:
            self.logger.error(
                "Fehler beim Laden der Gerätedefinition",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "device_type": self.device_type
                }
            )
            return None

    def _merge_definitions(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """Führt zwei Definitionen zusammen.
        
        Args:
            base: Basis-Definition
            overlay: Zu überlagernde Definition
            
        Returns:
            Zusammengeführte Definition
        """
        result = base.copy()
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_definitions(result[key], value)
            elif key in result and isinstance(result[key], list) and isinstance(value, list):
                # Für Register: Ersetze bestehende Einträge mit gleichem Namen
                if key == "registers":
                    existing_names = {item.get("name"): i for i, item in enumerate(result[key])}
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

    async def read_registers(self) -> Dict[str, Any]:
        """Liest die Register des Geräts.
        
        Returns:
            Dict mit den Registerwerten
        """
        try:
            if not self.register_definitions:
                self.logger.warning(
                    "Keine Register-Definitionen vorhanden",
                    extra={"device": self.name}
                )
                return {}

            # Hole den Hub aus den Home Assistant Daten
            entry_id = self.config.get("entry_id")
            if not entry_id or entry_id not in self.hass.data[DOMAIN]:
                self.logger.error("Hub nicht gefunden", entry_id=entry_id)
                return {}

            hub = self.hass.data[DOMAIN][entry_id]
            result = {}

            # Lese die Register basierend auf den Definitionen
            for register_type in ["read", "write"]:
                if register_type not in self.register_definitions.get("registers", {}):
                    continue

                for register in self.register_definitions["registers"][register_type]:
                    try:
                        name = register["name"]
                        address = register["address"]
                        reg_type = register["type"]
                        count = register.get("count", 1)
                        scale = register.get("scale", 1)
                        swap = register.get("swap", None)

                        # Lese die Register
                        value = await hub.read_register(
                            self.name,
                            address,
                            reg_type,
                            count,
                            scale,
                            swap
                        )

                        if value is not None:
                            result[name] = value
                            self.logger.debug(
                                "Register gelesen",
                                extra={
                                    "name": name,
                                    "value": value,
                                    "device": self.name
                                }
                            )

                    except Exception as e:
                        self.logger.error(
                            "Fehler beim Lesen des Registers",
                            extra={
                                "name": register.get("name"),
                                "address": register.get("address"),
                                "error": str(e),
                                "device": self.name
                            }
                        )

            return result

        except Exception as e:
            self.logger.error(
                "Fehler beim Lesen der Register",
                extra={
                    "error": str(e),
                    "device": self.name
                }
            )
            return {}