"""Modbus Manager Device Class."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from .logger import ModbusManagerLogger
from typing import Dict, Any

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
        self.name = config["name"]
        self._current_firmware_version = None
        self.logger = ModbusManagerLogger(f"device_{self.name}")
        
        self.logger.debug(
            "Initializing device",
            name=self.name,
            manufacturer=config.get("manufacturer"),
            model=config.get("model")
        )

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

    async def detect_firmware_version(self) -> str:
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
            device_definitions = self.hass.data[DOMAIN].get('device_definitions', {})
            device_def = device_definitions.get(self.name, {})
            
            if not device_def:
                self.logger.warning("Keine Geräte-Definition für %s gefunden", self.name)
                return
            
            # Basis-Register laden (Read und Write)
            base_registers = device_def.get('registers', {})
            merged_registers = {
                "read": base_registers.get('read', []).copy(),
                "write": base_registers.get('write', []).copy()
            }
            
            # Firmware-spezifische Änderungen laden
            firmware_defs = device_def.get('firmware_versions', {}).get(firmware_version, {})
            firmware_read_registers = firmware_defs.get('registers', {}).get('read', [])
            firmware_write_registers = firmware_defs.get('registers', {}).get('write', [])
            
            # Update der Read-Register
            for fw_reg in firmware_read_registers:
                # Überprüfen, ob das Register bereits existiert
                existing = next((reg for reg in merged_registers["read"] if reg["name"] == fw_reg["name"]), None)
                if existing:
                    self.logger.debug("Aktualisiere Register: %s", fw_reg["name"])
                    merged_registers["read"].remove(existing)
                else:
                    self.logger.debug("Füge neues Register hinzu: %s", fw_reg["name"])
                merged_registers["read"].append(fw_reg)
            
            # Update der Write-Register (falls vorhanden)
            for fw_reg in firmware_write_registers:
                existing = next((reg for reg in merged_registers["write"] if reg["name"] == fw_reg["name"]), None)
                if existing:
                    self.logger.debug("Aktualisiere Write-Register: %s", fw_reg["name"])
                    merged_registers["write"].remove(existing)
                else:
                    self.logger.debug("Füge neues Write-Register hinzu: %s", fw_reg["name"])
                merged_registers["write"].append(fw_reg)
            
            # Aktualisiere die internen Register-Definitionen
            self.register_definitions = merged_registers
            
            self.logger.info(
                "Register-Definitionen erfolgreich für Firmware-Version %s aktualisiert",
                firmware_version
            )
            
            # Informiere den Modbus-Hub, dass die Register-Definitionen aktualisiert wurden
            await self.hass.data[DOMAIN]['hub'].reload_registers(self.name, firmware_version)
            
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
            self.logger.debug("Starting device setup", device=self.name)
            
            # Firmware-Version erkennen
            if self.config.get("firmware_handling", {}).get("auto_detect", False):
                firmware_version = await self.detect_firmware_version()
                if firmware_version:
                    self.logger.info(
                        "Detected firmware version",
                        version=firmware_version,
                        device=self.name
                    )
                    await self.update_register_definitions(firmware_version)
                    self._current_firmware_version = firmware_version
            
            self.logger.info("Device setup complete", device=self.name)
            return True
            
        except Exception as e:
            self.logger.error(
                "Device setup failed",
                error=e,
                device=self.name
            )
            return False 