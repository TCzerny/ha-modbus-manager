"""Helper for managing entities and loading common configurations."""

from typing import Dict, Any, List, Optional
import os
import yaml
from pathlib import Path
import aiofiles
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.const import CONF_NAME
from homeassistant.components.sensor import SensorEntity
import logging

_LOGGER = logging.getLogger(__name__)


class EntityHelper:
    """Helper class for entity management."""

    def __init__(self, hass_config_dir: str):
        """Initialize the entity helper."""
        self.base_path = Path(hass_config_dir) / "custom_components" / "modbus_manager"
        self._common_entities = None
        self._load_management = None
        self._device_configs = {}

    async def load_common_entities(self, device_type: str = None) -> Dict[str, Any]:
        """Load common entities configuration.

        Args:
            device_type: Optional device type to filter entities

        Returns:
            Dictionary with common entity configurations
        """
        if self._common_entities is None:
            path = self.base_path / "core" / "common_entities.yaml"
            async with aiofiles.open(path, "r") as f:
                content = await f.read()
                self._common_entities = yaml.safe_load(content)

        if device_type and self._common_entities:
            # Filtere Entities basierend auf dem Gerätetyp
            filtered_entities = {}
            for system_type, config in self._common_entities.items():
                if self._is_device_compatible(device_type, system_type):
                    filtered_entities[system_type] = config
            return filtered_entities

        return self._common_entities

    async def load_load_management(self, device_type: str = None) -> Dict[str, Any]:
        """Load load management configuration.

        Args:
            device_type: Optional device type to filter configurations

        Returns:
            Dictionary with load management configurations
        """
        if self._load_management is None:
            path = self.base_path / "core" / "load_management.yaml"
            async with aiofiles.open(path, "r") as f:
                content = await f.read()
                self._load_management = yaml.safe_load(content)

        if device_type and self._load_management:
            # Filtere Konfigurationen basierend auf dem Gerätetyp
            filtered_config = {}
            for section, config in self._load_management.items():
                if self._is_device_compatible(device_type, section):
                    filtered_config[section] = config
            return filtered_config

        return self._load_management

    async def _is_device_compatible(self, device_type: str, system_type: str) -> bool:
        """Überprüft, ob ein Gerät mit einem System-Typ kompatibel ist."""
        try:
            # Lade die Gerätedefinition
            device_def_path = (
                self.base_path / "device_definitions" / f"{device_type}.yaml"
            )
            async with aiofiles.open(device_def_path, "r") as f:
                content = await f.read()
                device_def = yaml.safe_load(content)

            # PV-System Kompatibilität
            if system_type == "pv_system":
                return device_def.get("supports_pv_system", False)

            # Lade-System Kompatibilität
            if system_type == "charging_system":
                return device_def.get("supports_charging_system", False)

            # Batterie-System Kompatibilität
            if system_type == "battery_system":
                return device_def.get("supports_battery_system", False)

            # Load Management Kompatibilität
            if system_type == "load_management":
                return device_def.get("supports_load_management", False)

            return False

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Kompatibilitätsprüfung",
                extra={
                    "error": str(e),
                    "device_type": device_type,
                    "system_type": system_type,
                },
            )
            return False

    async def setup_common_entities(
        self,
        hass: HomeAssistant,
        device_name: str,
        device_type: str,
        config_entry_id: str,
    ) -> None:
        """Richtet gemeinsame Entities für ein Gerät ein."""
        # Lade gemeinsame Entities für den Gerätetyp
        common_entities = await self.load_common_entities(device_type)

        if not common_entities:
            return

        # Hole die Registries
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)

        # Hole oder erstelle den Device-Eintrag
        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry_id,
            identifiers={("modbus_manager", device_name)},
            name=device_name,
            manufacturer="ModbusManager",
            model=device_type,
        )

        # Verarbeite jedes System
        for system_type, system_config in common_entities.items():
            # Verarbeite Sensoren
            if "sensors" in system_config:
                for sensor_config in system_config["sensors"]:
                    try:
                        # Erstelle eine eindeutige Entity-ID
                        unique_id = f"{device_name}_{sensor_config['unique_id']}"
                        entity_id = f"sensor.{unique_id}"

                        # Registriere den Sensor
                        entity_registry.async_get_or_create(
                            domain="sensor",
                            platform="modbus_manager",
                            unique_id=unique_id,
                            config_entry=None,
                            device_id=device_entry.id,
                            original_name=sensor_config.get("name", unique_id),
                            suggested_object_id=unique_id,
                            unit_of_measurement=sensor_config.get(
                                "unit_of_measurement"
                            ),
                            device_class=sensor_config.get("device_class"),
                            state_class=sensor_config.get("state_class"),
                            original_device_class=sensor_config.get("device_class"),
                            disabled_by=None,
                        )

                        _LOGGER.debug(
                            "Sensor registriert",
                            extra={
                                "device": device_name,
                                "entity_id": entity_id,
                                "config": sensor_config,
                            },
                        )

                    except Exception as e:
                        _LOGGER.error(
                            f"Fehler beim Registrieren des Sensors: {str(e)} -  {device_name} {sensor_config}"
                        )

            # Verarbeite Automationen
            if "automations" in system_config:
                for automation in system_config["automations"]:
                    try:
                        # Füge Gerätenamen zur Automation-ID hinzu
                        automation["id"] = f"{device_name}_{automation['id']}"

                        # Ersetze Platzhalter im Template
                        if "value_template" in automation:
                            automation["value_template"] = automation[
                                "value_template"
                            ].replace("{{device_name}}", device_name)

                        # Registriere die Automation
                        #await hass.services.async_call(
                        #    "automation",
                        #     "reload",
                        #     {"entity_id": f"automation.{automation['id']}"},
                        # )

                        # Setup an automation in Home Assistant.

                        # Erstellen Sie die Automation
                        await hass.helpers.automation.async_create(hass, automation)
                        


                        _LOGGER.debug(
                            "Automation registriert",
                            extra={
                                "device": device_name,
                                "automation_id": automation["id"],
                            },
                        )

                    except Exception as e:
                        _LOGGER.error(
                            f"Fehler beim Registrieren der Automation {automation['id']}: {str(e)}"
                        )

    async def setup_load_management(
        self,
        hass: HomeAssistant,
        device_name: str,
        device_type: str,
        config_entry_id: str,
    ) -> None:
        """Richtet das Lastmanagement für ein Gerät ein."""
        # Lade Lastmanagement-Konfiguration für den Gerätetyp
        load_config = await self.load_load_management(device_type)

        if not load_config:
            return

        # Hole die Registries
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)

        # Hole oder erstelle den Device-Eintrag
        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry_id,
            identifiers={("modbus_manager", device_name)},
            name=device_name,
            manufacturer="ModbusManager",
            model=device_type,
        )

        # Verarbeite Sensoren
        if "sensors" in load_config:
            for sensor_config in load_config["sensors"]:
                try:
                    # Erstelle eine eindeutige Entity-ID
                    unique_id = f"{device_name}_{sensor_config['unique_id']}"
                    entity_id = f"sensor.{unique_id}"

                    # Registriere den Sensor
                    entity_registry.async_get_or_create(
                        domain="sensor",
                        platform="modbus_manager",
                        unique_id=unique_id,
                        config_entry=None,
                        device_id=device_entry.id,
                        original_name=sensor_config.get("name", unique_id),
                        suggested_object_id=unique_id,
                        unit_of_measurement=sensor_config.get("unit_of_measurement"),
                        device_class=sensor_config.get("device_class"),
                        state_class=sensor_config.get("state_class"),
                        original_device_class=sensor_config.get("device_class"),
                        disabled_by=None,
                    )

                    _LOGGER.debug(
                        "Load Management Sensor registriert",
                        extra={
                            "device": device_name,
                            "entity_id": entity_id,
                            "config": sensor_config,
                        },
                    )

                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Registrieren des Load Management Sensors",
                        extra={
                            "error": str(e),
                            "device": device_name,
                            "config": sensor_config,
                        },
                    )

        # Verarbeite Automationen
        if "automations" in load_config:
            for automation in load_config["automations"]:
                try:
                    # Füge Gerätenamen zur Automation-ID hinzu
                    automation["id"] = f"{device_name}_{automation['id']}"

                    # Ersetze Platzhalter im Template
                    if "value_template" in automation:
                        automation["value_template"] = automation[
                            "value_template"
                        ].replace("{{device_name}}", device_name)

                    # Registriere die Automation
                    await hass.services.async_call(
                        "automation",
                        "reload",
                        {"entity_id": f"automation.{automation['id']}"},
                    )

                    _LOGGER.debug(
                        "Load Management Automation registriert",
                        extra={
                            "device": device_name,
                            "automation_id": automation["id"],
                        },
                    )

                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Registrieren der Load Management Automation",
                        extra={
                            "error": str(e),
                            "device": device_name,
                            "automation": automation,
                        },
                    )
