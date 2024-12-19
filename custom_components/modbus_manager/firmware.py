"""Firmware management for Modbus Manager."""
import logging
from typing import Optional, Dict, Any

from .const import CONF_FIRMWARE_VERSION
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class FirmwareManager:
    """Manages firmware versions and related functionality."""

    def __init__(self, device_config: Dict[str, Any], selected_version: str = None):
        """Initialize the firmware manager.
        
        Args:
            device_config: The device configuration from the YAML file
            selected_version: The manually selected firmware version
        """
        self.device_config = device_config
        self.selected_version = selected_version
        self.detected_version = None
        self.current_version = None
        
        # Firmware-Konfiguration aus der Gerätedefinition
        self.firmware_config = device_config.get("firmware", {})
        self.auto_detect = self.firmware_config.get("auto_detect", False)
        self.fallback_version = self.firmware_config.get("fallback_version", "1.0.0")
        
        # Verfügbare Firmware-Versionen
        self.available_versions = device_config.get("firmware_versions", {})

    async def initialize(self, hub) -> str:
        """Initialize firmware version.
        
        Returns:
            The determined firmware version
        """
        if self.selected_version == "auto" and self.auto_detect:
            try:
                self.detected_version = await self._detect_version(hub)
                if self.detected_version:
                    self.current_version = self.detected_version
                else:
                    _LOGGER.warning(
                        "Firmware-Version konnte nicht erkannt werden, verwende Fallback-Version %s",
                        self.fallback_version
                    )
                    self.current_version = self.fallback_version
            except Exception as e:
                _LOGGER.error("Fehler bei der Firmware-Erkennung: %s", str(e))
                self.current_version = self.fallback_version
        else:
            self.current_version = self.selected_version or self.fallback_version
            
        return self.current_version

    async def _detect_version(self, hub) -> Optional[str]:
        """Detect firmware version from device.
        
        Returns:
            The detected firmware version or None if not detected
        """
        try:
            if not self.firmware_config.get("version_register"):
                return None
                
            register = self.firmware_config["version_register"]
            reg_type = self.firmware_config.get("version_type", "uint16")
            
            # Lese Firmware-Version aus Register
            value = await hub.read_register(
                device_name=hub.device_type,
                address=register,
                reg_type=reg_type,
                register_type="holding"
            )
            
            if value:
                # Konvertiere Register-Wert in Firmware-Version
                version = self._convert_to_version(value, reg_type)
                if version in self.available_versions:
                    return version
                    
            return None
            
        except Exception as e:
            _LOGGER.error("Fehler beim Lesen der Firmware-Version: %s", str(e))
            return None

    def _convert_to_version(self, value: Any, reg_type: str) -> str:
        """Convert register value to firmware version string."""
        if isinstance(value, list):
            value = value[0] if value else 0
            
        if reg_type == "uint16":
            # Format: 123 -> "1.2.3"
            major = (value >> 12) & 0xF
            minor = (value >> 8) & 0xF
            patch = value & 0xFF
            return f"{major}.{minor}.{patch}"
        elif reg_type == "string":
            # Format: Direct string value
            return str(value).strip()
        else:
            return str(value)

    def get_register_definitions(self) -> Dict[str, Any]:
        """Get register definitions for current firmware version."""
        base_registers = self.device_config.get("registers", {})
        
        if self.current_version in self.available_versions:
            firmware_registers = self.available_versions[self.current_version].get("registers", {})
            
            # Merge base registers with firmware-specific registers
            merged = {
                "read": base_registers.get("read", []).copy(),
                "write": base_registers.get("write", []).copy()
            }
            
            # Update with firmware-specific registers
            if "read" in firmware_registers:
                for reg in firmware_registers["read"]:
                    # Remove existing register with same name if exists
                    merged["read"] = [r for r in merged["read"] if r["name"] != reg["name"]]
                    merged["read"].append(reg)
                    
            if "write" in firmware_registers:
                for reg in firmware_registers["write"]:
                    merged["write"] = [r for r in merged["write"] if r["name"] != reg["name"]]
                    merged["write"].append(reg)
                    
            return merged
            
        return base_registers

    def get_version(self) -> str:
        """Get current firmware version."""
        return self.current_version

    def is_version_supported(self, version: str) -> bool:
        """Check if a firmware version is supported."""
        return version in self.available_versions

    def get_available_versions(self) -> Dict[str, str]:
        """Get list of available firmware versions."""
        versions = {}
        if self.auto_detect:
            versions["auto"] = "Auto-Detect"
        versions.update({v: f"Version {v}" for v in self.available_versions.keys()})
        return versions 