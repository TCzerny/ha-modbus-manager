"""Helper for managing entities and loading common configurations."""
from typing import Dict, Any
import os
import yaml
from pathlib import Path

class EntityHelper:
    """Helper class for entity management."""

    def __init__(self, hass_config_dir: str):
        """Initialize the entity helper.
        
        Args:
            hass_config_dir: Home Assistant config directory path
        """
        self.base_path = Path(hass_config_dir) / "custom_components" / "modbus_manager"
        self._common_entities = None
        self._load_management = None

    def load_common_entities(self) -> Dict[str, Any]:
        """Load common entities configuration."""
        if self._common_entities is None:
            path = self.base_path / "core" / "common_entities.yaml"
            with open(path, 'r') as f:
                self._common_entities = yaml.safe_load(f)
        return self._common_entities

    def load_load_management(self) -> Dict[str, Any]:
        """Load load management configuration."""
        if self._load_management is None:
            path = self.base_path / "core" / "load_management.yaml"
            with open(path, 'r') as f:
                self._load_management = yaml.safe_load(f)
        return self._load_management

    def get_device_definition(self, device_type: str) -> Dict[str, Any]:
        """Load device definition and merge with common configurations.
        
        Args:
            device_type: Type of device to load
            
        Returns:
            Merged configuration dictionary
        """
        # Load device-specific definition
        device_path = self.base_path / "device_definitions" / f"{device_type}.yaml"
        with open(device_path, 'r') as f:
            device_config = yaml.safe_load(f)

        # Merge with common entities
        common = self.load_common_entities()
        device_config['entities'] = {
            **common.get('common_entities', {}),
            **device_config.get('entities', {})
        }

        # Add load management if device supports it
        if device_config.get('supports_load_management', False):
            load_mgmt = self.load_load_management()
            device_config['load_management'] = load_mgmt.get('load_management', {})

        return device_config 