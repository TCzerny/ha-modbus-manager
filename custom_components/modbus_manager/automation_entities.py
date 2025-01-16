"""ModbusManager Automation Entity Support."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.const import (
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_TRIGGER,
    CONF_TRIGGERS,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.script import Script

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

# Vordefinierte Trigger-Typen
TRIGGER_TYPES = [
    "state",  # Statusänderung einer Entity
    "numeric_state",  # Numerischer Zustand (über/unter Schwellwert)
    "time_pattern",  # Zeitbasiert
    "template"  # Template-basiert
]

# Vordefinierte Condition-Typen
CONDITION_TYPES = [
    "state",  # Entity hat bestimmten Status
    "numeric_state",  # Numerischer Zustand
    "template",  # Template-Bedingung
    "time"  # Zeitbasierte Bedingung
]

# Vordefinierte Action-Typen
ACTION_TYPES = [
    "service",  # Home Assistant Service aufrufen
    "modbus_write",  # Modbus Register schreiben
    "delay",  # Verzögerung
    "template"  # Template-basierte Aktion
]

# Schema für Device Triggers
DEVICE_TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("platform"): cv.string,
    vol.Optional("above"): vol.Coerce(float),
    vol.Optional("below"): vol.Coerce(float),
    vol.Optional("after"): cv.string,
    vol.Optional("before"): cv.string
})

# Schema für Device Conditions
DEVICE_CONDITION_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("above"): vol.Coerce(float),
    vol.Optional("below"): vol.Coerce(float),
    vol.Optional("after"): cv.string,
    vol.Optional("before"): cv.string
})

# Schema für Device Actions
DEVICE_ACTION_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
    vol.Required("service"): cv.string,
    vol.Required("target"): {
        vol.Required(CONF_ENTITY_ID): cv.entity_id
    },
    vol.Required("fields"): dict
})

# Schema für die YAML-Validierung der Device Automation Komponenten
DEVICE_AUTOMATION_SCHEMA = vol.Schema({
    vol.Optional("device_triggers"): vol.All(cv.ensure_list, [DEVICE_TRIGGER_SCHEMA]),
    vol.Optional("device_conditions"): vol.All(cv.ensure_list, [DEVICE_CONDITION_SCHEMA]),
    vol.Optional("device_actions"): vol.All(cv.ensure_list, [DEVICE_ACTION_SCHEMA])
})

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
        
        # Validiere die Konfiguration
        try:
            self._config = AUTOMATION_SCHEMA(config)
        except vol.Invalid as e:
            _LOGGER.error(
                "Ungültige Automatisierungskonfiguration",
                extra={
                    "error": str(e),
                    "automation": automation_id,
                    "device": device.name
                }
            )
            raise
        
        # Erstelle die Basis-Konfiguration für die Automation
        trigger_config = self._config.get(CONF_TRIGGER, [])
        action_config = self._config.get(CONF_ACTION, [])
        condition_config = self._config.get(CONF_CONDITION, [])
        
        # Erstelle das Action-Script
        script_config = {
            "mode": self._config.get(CONF_MODE, "single"),
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
            if not condition_config:
                return True
                
            try:
                hass = self.device.hass
                return all(
                    condition.async_from_config(hass, cond).async_run(hass)
                    for cond in condition_config
                )
            except Exception as e:
                _LOGGER.error(
                    "Fehler bei der Auswertung der Bedingungen",
                    extra={
                        "error": str(e),
                        "automation": self._automation_id,
                        "device": self.device.name,
                        "conditions": condition_config
                    }
                )
                return False
            
        # Initialisiere die Basis-Klasse mit allen erforderlichen Parametern
        super().__init__(
            automation_id=automation_id,
            name=self._config.get("alias", automation_id),
            trigger_config=trigger_config,
            cond_func=cond_func,
            action_script=action_script,
            initial_state=True,
            variables=self._config.get("variables", {}),
            trigger_variables=self._config.get("trigger_variables", {}),
            raw_config=self._config,
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