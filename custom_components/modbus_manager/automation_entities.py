"""ModbusManager Automation Entities."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN, AutomationEntity
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN, ScriptEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.script import Script, SCRIPT_MODE_SINGLE

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerAutomation(AutomationEntity):
    """Repräsentiert eine ModbusManager Automation."""

    def __init__(
        self,
        device,
        automation_id: str,
        config: Dict[str, Any],
    ) -> None:
        """Initialisiere die Automation Entity."""
        self.device = device
        self._automation_id = automation_id
        self._config = config
        
        # Erstelle die Basis-Konfiguration für die Automation
        trigger_config = config.get("trigger", [])
        action_config = config.get("action", [])
        condition_config = config.get("condition", [])
        
        # Erstelle das Action-Script
        script_config = {
            "mode": config.get("mode", "single"),
            "sequence": action_config
        }
        action_script = Script(
            hass=device.hass,
            sequence=action_config,
            name=f"{automation_id}_script",
            domain=AUTOMATION_DOMAIN,
            logger=_LOGGER,
            script_mode=SCRIPT_MODE_SINGLE,
        )

        # Erstelle die Condition-Funktion
        @callback
        def cond_func() -> bool:
            """Evaluiere die Bedingungen."""
            return True  # TODO: Implementiere die tatsächliche Bedingungslogik
            
        # Initialisiere die Basis-Klasse mit allen erforderlichen Parametern
        super().__init__(
            automation_id=automation_id,
            name=config.get("alias", automation_id),
            trigger_config=trigger_config,
            cond_func=cond_func,
            action_script=action_script,
            initial_state=True,
            variables=config.get("variables", {}),
            trigger_variables=config.get("trigger_variables", {}),
            raw_config=config,
            blueprint_inputs={},
            trace_config=None
        )
        
        self._attr_unique_id = f"{device.config['entry_id']}_{automation_id}"
        self._attr_device_info = device.device_info
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()
        
        try:
            # Registriere die Automation in Home Assistant
            registry = er.async_get(self.hass)
            registry.async_get_or_create(
                AUTOMATION_DOMAIN,
                DOMAIN,
                self.unique_id,
                suggested_object_id=self._automation_id,
                config_entry=self.device.config_entry,
                device_id=self.device_info["identifiers"],
            )
            
            # Aktiviere die Automation
            await self._enable_automation()
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Hinzufügen der Automation",
                extra={
                    "error": str(e),
                    "automation": self._automation_id,
                    "device": self.device.name
                }
            )

    async def _enable_automation(self) -> None:
        """Aktiviere die Automation mit der korrekten Konfiguration."""
        try:
            await self.hass.services.async_call(
                AUTOMATION_DOMAIN,
                "reload",
                {},
                blocking=True
            )
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Aktivieren der Automation",
                extra={
                    "error": str(e),
                    "automation": self._automation_id,
                    "device": self.device.name
                }
            )

    async def async_will_remove_from_hass(self):
        """Wird aufgerufen, wenn die Entity entfernt wird."""
        try:
            # Deaktiviere die Automation
            await self.hass.services.async_call(
                AUTOMATION_DOMAIN,
                "turn_off",
                {"entity_id": f"automation.{self._automation_id}"},
                blocking=True
            )
            
            # Entferne die Registrierung
            registry = er.async_get(self.hass)
            if entity_id := registry.async_get_entity_id(AUTOMATION_DOMAIN, DOMAIN, self.unique_id):
                registry.async_remove(entity_id)
                
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Entfernen der Automation",
                extra={
                    "error": str(e),
                    "automation": self._automation_id,
                    "device": self.device.name
                }
            )

class ModbusManagerScript(ScriptEntity):
    """Repräsentiert ein ModbusManager Script."""

    def __init__(
        self,
        device,
        script_id: str,
        config: Dict[str, Any],
    ) -> None:
        """Initialisiere die Script Entity."""
        self.device = device
        self._script_id = script_id
        
        # Erstelle die Script-Konfiguration
        sequence = config.get("sequence", [])
        script_config = {
            "mode": config.get("mode", "single"),
            "sequence": sequence
        }
        
        # Erstelle das Script-Objekt
        script = Script(
            hass=device.hass,
            sequence=sequence,
            name=config.get("alias", script_id),
            domain=SCRIPT_DOMAIN,
            logger=_LOGGER,
            script_mode=SCRIPT_MODE_SINGLE,
        )
        
        # Initialisiere die Basis-Klasse
        super().__init__(
            name=config.get("alias", script_id),
            script=script,
            script_mode=SCRIPT_MODE_SINGLE,
            max_runs=config.get("max", 2),
            max_exceeded=config.get("max_exceeded", "warning"),
            logger=_LOGGER
        )
        
        self._attr_unique_id = f"{device.config['entry_id']}_{script_id}"
        self._attr_device_info = device.device_info
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()
        
        try:
            # Registriere das Script in Home Assistant
            registry = er.async_get(self.hass)
            registry.async_get_or_create(
                SCRIPT_DOMAIN,
                DOMAIN,
                self.unique_id,
                suggested_object_id=self._script_id,
                config_entry=self.device.config_entry,
                device_id=self.device_info["identifiers"],
            )
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Hinzufügen des Scripts",
                extra={
                    "error": str(e),
                    "script": self._script_id,
                    "device": self.device.name
                }
            )

    async def async_will_remove_from_hass(self):
        """Wird aufgerufen, wenn die Entity entfernt wird."""
        try:
            # Deaktiviere das Script
            await self.hass.services.async_call(
                SCRIPT_DOMAIN,
                "turn_off",
                {"entity_id": f"script.{self._script_id}"},
                blocking=True
            )
            
            # Entferne die Registrierung
            registry = er.async_get(self.hass)
            if entity_id := registry.async_get_entity_id(SCRIPT_DOMAIN, DOMAIN, self.unique_id):
                registry.async_remove(entity_id)
                
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Entfernen des Scripts",
                extra={
                    "error": str(e),
                    "script": self._script_id,
                    "device": self.device.name
                }
            ) 