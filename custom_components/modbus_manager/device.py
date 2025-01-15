"""Modbus Manager Device Class."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Dict, Any, Optional, List

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.input_select import DOMAIN as INPUT_SELECT_DOMAIN

from .const import DOMAIN
from .logger import ModbusManagerLogger
from .entities import ModbusRegisterEntity
from .input_entities import ModbusManagerInputNumber, ModbusManagerInputSelect
from homeassistant.const import CONF_NAME, CONF_DEVICE_ID

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerDevice:
    """Modbus Manager Device class."""

    def __init__(
        self,
        hub: ModbusManagerHub,
        device_type: str,
        config: dict,
        register_definitions: dict,
    ) -> None:
        """Initialize the device."""
        self._hub = hub
        self.hass: HomeAssistant = hub.hass
        self.device_type: str = device_type
        self.config: dict = config
        self.name: str = config.get(CONF_NAME)
        self.entry_id: str = config.get("entry_id")
        self._device_config: dict = register_definitions
        self._register_data: Dict[str, Any] = {}
        self._setup_complete: bool = False
        self.entities: Dict[str, ModbusRegisterEntity] = {}
        self._remove_state_listeners: list = []
        
        # Hole die Default-Polling-Intervalle
        polling_config = register_definitions.get("device_config", {}).get("default_polling", {})
        self._fast_interval = int(polling_config.get("fast", 5))
        self._normal_interval = int(polling_config.get("normal", 15))
        self._slow_interval = int(polling_config.get("slow", 600))

        # Initialisiere die Koordinatoren
        for interval in [self._fast_interval, self._normal_interval, self._slow_interval]:
            if not self._hub.get_coordinator(interval):
                self._hub.create_coordinator(interval)
    @property
    def device_info(self) -> DeviceInfo:
        """Gibt die Geräteinformationen zurück."""
        device_info = self._device_config.get("device_info", {})
        
        # Basis-Informationen aus der Konfiguration
        info = {
            "identifiers": {(DOMAIN, self.name)},
            "name": self.name,
            "manufacturer": device_info.get("manufacturer", "Unknown"),
            "model": device_info.get("model", self.device_type),
        }
        
        # Firmware-Version aus den Registern
        arm_version = self._register_data.get("arm_software_version")
        dsp_version = self._register_data.get("dsp_software_version")
        if arm_version or dsp_version:
            versions = []
            if arm_version:
                versions.append(f"ARM: {arm_version}")
            if dsp_version:
                versions.append(f"DSP: {dsp_version}")
            info["sw_version"] = " | ".join(versions)
        
        # Geräte-Code aus den Registern
        device_code = self._register_data.get("device_code")
        if device_code:
            info["model"] = device_code
            
        # Seriennummer aus den Registern
        inverter_serial = self._register_data.get("inverter_serial")
        if inverter_serial:
            info["hw_version"] = f"SN: {inverter_serial}"
            
        return DeviceInfo(**info)

    async def async_setup(self) -> bool:
        """Setup the device."""
        try:
            # Hole die Register-Definitionen
            registers = self._device_config.get("registers", {})
            
            # Erstelle Entities für lesbare Register
            if "read" in registers:
                for register in registers["read"]:
                    register_name = register.get("name")
                    if register_name:
                        entity = await self._create_register_entity(
                            register_name=register_name,
                            register_def=register,
                            writable=False
                        )
                        if entity:
                            self.entities[register_name] = entity
            
            # Erstelle Entities für schreibbare Register
            if "write" in registers:
                for register in registers["write"]:
                    register_name = register.get("name")
                    if register_name:
                        entity = await self._create_register_entity(
                            register_name=register_name,
                            register_def=register,
                            writable=True
                        )
                        if entity:
                            self.entities[register_name] = entity
            
            # Setup Input Synchronization wenn konfiguriert
            if "input_sync" in self._device_config:
                await self.setup_input_sync()
            
            # Starte das initiale Update für fast-polling Register
            await self._initial_update()
            
            # Starte das verzögerte Setup für normal und slow-polling Register
            asyncio.create_task(self._delayed_setup())
            
            self._setup_complete = True
            
            _LOGGER.debug(
                "Geräte-Setup abgeschlossen",
                extra={
                    "device": self.name,
                    "entities_count": len(self.entities)
                }
            )
            
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup des Geräts",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False
        
    async def _initial_update(self):
        """Führt das initiale Update für wichtige Register durch."""
        try:
            # Sofortiges Update für fast Register
            update_tasks = []
            
            # Verwende das fast_interval aus default_polling
            if self._fast_interval:
                update_tasks.append(self.async_update(self._fast_interval))
            
            if update_tasks:
                results = await asyncio.gather(*update_tasks, return_exceptions=True)
                
                # Aktualisiere die Register-Daten
                for result in results:
                    if isinstance(result, dict):
                        self._register_data.update(result)
                
                # Aktualisiere die Entities parallel
                entity_update_tasks = []
                for entity in self.entities.values():
                    if hasattr(entity, "async_write_ha_state"):
                        try:
                            # Stelle sicher, dass die Entity initialisiert ist
                            if not entity.hass:
                                entity.hass = self.hass
                            if not entity._attr_unique_id:
                                entity._attr_unique_id = f"{self.name}_{entity.name}"
                            
                            # Aktualisiere den State
                            if hasattr(entity, "_handle_coordinator_update"):
                                try:
                                    entity._handle_coordinator_update()
                                except Exception as e:
                                    _LOGGER.warning(
                                        "Fehler beim Koordinator-Update",
                                        extra={
                                            "error": str(e),
                                            "entity": entity.entity_id,
                                            "device": self.name
                                        }
                                    )
                            entity_update_tasks.append(entity.async_update_ha_state(force_refresh=True))
                        except Exception as e:
                            _LOGGER.warning(
                                "Fehler beim Aktualisieren der Entity",
                                extra={
                                    "error": str(e),
                                    "entity": entity.entity_id,
                                    "device": self.name
                                }
                            )
                
                if entity_update_tasks:
                    await asyncio.gather(*entity_update_tasks, return_exceptions=True)
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler beim initialen Update",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )

    async def _delayed_setup(self):
        """Führt verzögerte Setup-Aufgaben aus."""
        try:
            # Warte kurz, damit die wichtigen Register zuerst geladen werden
            await asyncio.sleep(5)
            
            # Verwende normal und slow Intervalle
            polling_intervals = set()
            if self._normal_interval:
                polling_intervals.add(self._normal_interval)
            if self._slow_interval:
                polling_intervals.add(self._slow_interval)
            
            # Erstelle Update-Tasks für alle Intervalle
            update_tasks = []
            for interval in polling_intervals:
                update_tasks.append(self.async_update(interval))
            
            # Führe alle Updates parallel aus
            if update_tasks:
                results = await asyncio.gather(*update_tasks, return_exceptions=True)
                
                # Logge Fehler, falls welche aufgetreten sind
                for interval, result in zip(polling_intervals, results):
                    if isinstance(result, Exception):
                        _LOGGER.warning(
                            f"Fehler beim verzögerten Update für Intervall {interval}",
                            extra={
                                "error": str(result),
                                "interval": interval,
                                "device": self.name
                            }
                        )
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler beim verzögerten Setup",
                extra={
                    "error": str(e),
                    "device": self.name
                }
            )

    async def _create_register_entity(self, register_name, register_def, writable: bool = False):
        """Erstelle eine Entity für ein Register."""
        try:
            # Bestimme das Polling-Intervall direkt aus der Register-Definition
            polling = register_def.get("polling", "normal")
            if polling == "fast":
                polling_interval = self._fast_interval
            elif polling == "slow":
                polling_interval = self._slow_interval
            else:  # "normal" oder nicht definiert
                polling_interval = self._normal_interval
            
            # Hole den Koordinator für dieses Intervall
            coordinator = self._hub.get_coordinator(polling_interval)
            if not coordinator:
                _LOGGER.error(
                    "Kein Koordinator für das Polling-Intervall gefunden",
                    extra={
                        "polling_interval": polling_interval,
                        "register": register_name,
                        "device": self.name
                    }
                )
                return None

            # Bestimme den Domain-Typ basierend auf den Register-Eigenschaften
            if writable:
                domain = "select" if "options" in register_def else "number"
            else:
                domain = "sensor"

            # Erstelle die Entity
            entity = ModbusRegisterEntity(
                device=self,
                register_name=register_name,
                register_config=register_def,
                coordinator=coordinator,
            )
            
            # Formatiere den Entity-Namen korrekt (lowercase und underscores)
            formatted_name = register_name.lower().replace(" ", "_")
            entity_id = f"{domain}.{self.name.lower()}_{formatted_name}"
            
            # Setze die Entity-ID
            entity.entity_id = entity_id
            entity.platform = domain
            
            # Füge die Entity zum entities Dictionary hinzu
            self.entities[register_name] = entity
            
            return entity
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen einer Register-Entity",
                extra={
                    "error": str(e),
                    "register": register_name,
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return None
    async def _setup_helper_entities(self):
        """Erstellt Helper-Entities über die Registry API."""
        try:
            # Hole die Device Registry
            dev_reg = dr.async_get(self.hass)
            device = dev_reg.async_get_device({(DOMAIN, self.name)})
            
            if not device:
                _LOGGER.error(
                    "Gerät nicht in Registry gefunden",
                    extra={
                        "device": self.name
                    }
                )
                return

            # Input Numbers
            if "input_number" in self._device_config:
                for input_id, config in self._device_config["input_number"].items():
                    # Erstelle Input Number Entity
                    entity = ModbusManagerInputNumber(
                        device=self,
                        name=input_id,
                        config=config,
                        register_config=config.get("register", {})
                    )
                    
                    if entity:
                        # Setze die Entity-ID und unique_id mit Gerätenamen
                        entity.entity_id = f"number.{self.name}_{input_id.lower()}"
                        entity._attr_unique_id = f"{self.name}_{input_id}_number"
                        
                        # Registriere die Entity in der Entity Registry
                        entity_registry = er.async_get(self.hass)
                        entity_registry.async_get_or_create(
                            domain="number",
                            platform=DOMAIN,
                            unique_id=entity._attr_unique_id,
                            device_id=device.id,
                            suggested_object_id=f"{self.name}_{input_id.lower()}",
                            original_name=entity._attr_name
                        )
                        
                        self.entities[entity.entity_id] = entity
            
            # Input Selects
            if "input_select" in self._device_config:
                for input_id, config in self._device_config["input_select"].items():
                    if "options" in config and config["options"]:
                        # Erstelle Input Select Entity
                        entity = ModbusManagerInputSelect(
                            device=self,
                            name=input_id,
                            config=config,
                            register_config=config.get("register", {})
                        )
                        
                        if entity:
                            # Setze die Entity-ID und unique_id mit Gerätenamen
                            entity.entity_id = f"select.{self.name}_{input_id.lower()}"
                            entity._attr_unique_id = f"{self.name}_{input_id}_select"
                            
                            # Registriere die Entity in der Entity Registry
                            entity_registry = er.async_get(self.hass)
                            entity_registry.async_get_or_create(
                                domain="select",
                                platform=DOMAIN,
                                unique_id=entity._attr_unique_id,
                                device_id=device.id,
                                suggested_object_id=f"{self.name}_{input_id.lower()}",
                                original_name=entity._attr_name
                            )
                            
                            self.entities[entity.entity_id] = entity

            _LOGGER.debug(
                "Helper-Entities erfolgreich erstellt",
                extra={
                    "device": self.name,
                    "input_numbers": len(self._device_config.get("input_number", {})),
                    "input_selects": len(self._device_config.get("input_select", {}))
                }
            )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen der Helper-Entities",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            
    async def setup_automation_components(self):
        """Richtet die Automatisierungskomponenten ein."""
        try:
            # Registriere Device Triggers
            if "device_triggers" in self._device_config:
                _LOGGER.debug(
                    "Registriere Device Triggers",
                    extra={
                        "device": self.name,
                        "triggers_count": len(self._device_config["device_triggers"])
                    }
                )
                
                # Registriere die Trigger im Device Registry
                dev_reg = dr.async_get(self.hass)
                device = dev_reg.async_get_device({(DOMAIN, self.name)})
                if device and device.id:
                    self.hass.data.setdefault(DOMAIN, {}).setdefault("device_triggers", {})[device.id] = \
                        self._device_config["device_triggers"]

            # Registriere Device Conditions
            if "device_conditions" in self._device_config:
                _LOGGER.debug(
                    "Registriere Device Conditions",
                    extra={
                        "device": self.name,
                        "conditions_count": len(self._device_config["device_conditions"])
                    }
                )
                
                # Registriere die Conditions im Device Registry
                dev_reg = dr.async_get(self.hass)
                device = dev_reg.async_get_device({(DOMAIN, self.name)})
                if device and device.id:
                    self.hass.data.setdefault(DOMAIN, {}).setdefault("device_conditions", {})[device.id] = \
                        self._device_config["device_conditions"]

            # Registriere Device Actions
            if "device_actions" in self._device_config:
                _LOGGER.debug(
                    "Registriere Device Actions",
                    extra={
                        "device": self.name,
                        "actions_count": len(self._device_config["device_actions"])
                    }
                )
                
                # Registriere die Actions im Device Registry
                dev_reg = dr.async_get(self.hass)
                device = dev_reg.async_get_device({(DOMAIN, self.name)})
                if device and device.id:
                    self.hass.data.setdefault(DOMAIN, {}).setdefault("device_actions", {})[device.id] = \
                        self._device_config["device_actions"]

            _LOGGER.debug(
                "Automatisierungskomponenten erfolgreich eingerichtet",
                extra={
                    "device": self.name,
                    "triggers": len(self._device_config.get("device_triggers", [])),
                    "conditions": len(self._device_config.get("device_conditions", [])),
                    "actions": len(self._device_config.get("device_actions", []))
                }
            )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Einrichten der Automatisierungskomponenten",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
    async def async_update(self, polling_interval: int) -> dict:
        """Aktualisiert die Register für das angegebene Polling-Intervall."""
        if not self._setup_complete:
            return {}

        # Bestimme das Polling-Level basierend auf dem Intervall
        if polling_interval == self._fast_interval:
            polling_level = "fast"
        elif polling_interval == self._slow_interval:
            polling_level = "slow"
        else:
            polling_level = "normal"

        try:
            data = {}
            errors = []
            tasks = []
            register_groups = {}
            
            # Hole alle Register mit dem entsprechenden Polling-Level
            if "registers" in self._device_config:
                for section in ["read", "write"]:
                    if section in self._device_config["registers"]:
                        registers = [
                            reg for reg in self._device_config["registers"][section]
                            if reg.get("polling", "normal") == polling_level
                        ]
                        
                        # Gruppiere Register nach Adresse und Typ
                        for register in registers:
                            if register.get("type") == "calculated":
                                # Verarbeite berechnete Register direkt
                                try:
                                    processed_value = self._process_register_value(
                                        register_name=register.get("name"),
                                        register_def=register,
                                        raw_value=None
                                    )
                                    if processed_value is not None:
                                        data[register["name"]] = processed_value
                                except Exception as e:
                                    errors.append({
                                        "register": register.get("name"),
                                        "error": str(e)
                                    })
                                continue

                            # Gruppiere normale Register
                            key = (
                                register.get("address"),
                                register.get("type", "uint16"),
                                register.get("count", 1),
                                register.get("register_type", "input")
                            )
                            if key not in register_groups:
                                register_groups[key] = []
                            register_groups[key].append(register)

            # Erstelle Tasks für jede Registergruppe
            for (address, reg_type, count, register_type), group in register_groups.items():
                task = self._hub.read_register(
                    device_name=self.name,
                    address=address,
                    count=count,
                    reg_type=reg_type,
                    register_type=register_type
                )
                tasks.append((task, group))

            # Führe alle Lese-Tasks parallel aus
            results = await asyncio.gather(
                *(task for task, _ in tasks),
                return_exceptions=True
            )

            # Verarbeite die Ergebnisse
            for (task, group), result in zip(tasks, results):
                if isinstance(result, Exception):
                    for register in group:
                        errors.append({
                            "register": register.get("name"),
                            "error": str(result)
                        })
                    continue

                # Verarbeite die Werte für jedes Register in der Gruppe
                for register in group:
                    try:
                        processed_value = self._process_register_value(
                            register_name=register.get("name"),
                            register_def=register,
                            raw_value=result
                        )
                        if processed_value is not None:
                            data[register["name"]] = processed_value
                    except Exception as e:
                        errors.append({
                            "register": register.get("name"),
                            "error": str(e)
                        })

            # Aktualisiere die Register-Daten
            self._register_data.update(data)
            
            # Logge eine Zusammenfassung
            _LOGGER.debug(
                "Update abgeschlossen",
                extra={
                    "device": self.name,
                    "polling_interval": polling_interval,
                    "successful_updates": len(data),
                    "errors": len(errors),
                    "error_details": errors if errors else None
                }
            )
                
            return data

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Update der Register",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "polling_interval": polling_interval
                }
            )
            return {}
    async def _read_register(self, register: Dict[str, Any], values: Dict[str, Any]):
        """Liest ein einzelnes Register."""
        try:
            # Überspringe das Lesen für berechnete Register
            if register.get("type") == "calculated":
                # Verarbeite den Wert direkt
                processed_value = self._process_register_value(
                    register_name=register.get("name"),
                    register_def=register,
                    raw_value=None
                )
                
                # Speichere den Wert wenn er nicht None ist
                if processed_value is not None:
                    values[register["name"]] = processed_value
                return

            reg_type = register.get("type", "uint16")
            reg_count = register.get("count", 1)
            swap = register.get("swap", "").lower()
            
            # Bestimme den Register-Typ für das Lesen
            # Verwende immer "input" zum Lesen, außer es ist explizit "holding" spezifiziert
            register_type = register.get("register_type", "input")
            
            _LOGGER.debug(
                "Starte Modbus Register Lesevorgang",
                extra={
                    "register_name": register.get("name"),
                    "address": register.get("address"),
                    "count": reg_count,
                    "type": reg_type,
                    "register_type": register_type,
                    "swap": swap,
                    "device": self.name
                }
            )            
            result = await self._hub.read_register(
                device_name=self.name,
                address=register["address"],
                count=reg_count,
                reg_type=reg_type,
                register_type=register_type
            )
            
            if result is not None:
                # Verarbeite Word-Swap wenn nötig
                if swap == "word" and len(result) >= 2:
                    result = list(reversed(result))
                
                # Verarbeite den Wert mit der _process_register_value Methode
                processed_value = self._process_register_value(
                    register_name=register.get("name"),
                    register_def=register,
                    raw_value=result
                )
                
                # Speichere den Wert
                if processed_value is not None:
                    values[register["name"]] = processed_value
                
                # Logging mit allen relevanten Informationen
                log_extra = {
                    "register_name": register.get("name"),
                    "address": register.get("address"),
                    "value": processed_value,
                    "raw_result": result,
                    "type": reg_type,
                    "device": self.name
                }
                
                # Füge optionale Parameter zum Log hinzu
                if "scale" in register:
                    log_extra["scale"] = register["scale"]
                if "precision" in register:
                    log_extra["precision"] = register["precision"]
                if swap:
                    log_extra["swap"] = swap
                if "unit_of_measurement" in register:
                    log_extra["unit"] = register["unit_of_measurement"]
                if "device_class" in register:
                    log_extra["device_class"] = register["device_class"]
                if "state_class" in register:
                    log_extra["state_class"] = register["state_class"]
                
                _LOGGER.debug(
                    "Modbus Register erfolgreich gelesen",
                    extra=log_extra
                )
            else:
                _LOGGER.warning(
                    "Modbus Register Lesevorgang ohne Ergebnis",
                    extra={
                        "register_name": register.get("name"),
                        "address": register.get("address"),
                        "type": reg_type,
                        "device": self.name
                    }
                )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Lesen eines Registers",
                extra={
                    "error": str(e),
                    "register_name": register.get("name"),
                    "address": register.get("address"),
                    "type": reg_type,
                    "device": self.name
                }
            )
    async def async_write_register(self, register_name: str, value: Any) -> bool:
        """Schreibt einen Wert in ein Register."""
        try:
            # Suche in Holding Registern
            register = next(
                (r for r in self._device_config["registers"].get("write", [])
                 if r["name"] == register_name),
                None
            )
            
            if not register:
                _LOGGER.warning(
                    "Register für Schreibvorgang nicht gefunden",
                    extra={
                        "register_name": register_name,
                        "device": self.name
                    }
                )
                return False

            # Konvertiere den Wert in den richtigen Typ
            try:
                if isinstance(value, str):
                    value = float(value)
            except ValueError:
                _LOGGER.error(
                    "Ungültiger Wert für Register",
                    extra={
                        "register_name": register_name,
                        "value": value,
                        "device": self.name
                    }
                )
                return False

            # Skaliere den Wert wenn nötig (in die andere Richtung für das Schreiben)
            scale = register.get("scale", 1)
            if scale != 1:
                value = value / scale

            # Runde auf ganze Zahlen für das Register
            value = int(round(value))

            # Prüfe Minimal- und Maximalwerte nur wenn sie definiert sind
            if "min" in register and value < register["min"]:
                _LOGGER.warning(
                    "Wert unter Minimum, setze auf Minimum",
                    extra={
                        "register_name": register_name,
                        "value": value,
                        "min": register["min"],
                        "device": self.name
                    }
                )
                value = register["min"]
            elif "max" in register and value > register["max"]:
                _LOGGER.warning(
                    "Wert über Maximum, setze auf Maximum",
                    extra={
                        "register_name": register_name,
                        "value": value,
                        "max": register["max"],
                        "device": self.name
                    }
                )
                value = register["max"]

            # Logging mit allen relevanten Informationen
            log_extra = {
                "register_name": register_name,
                "address": register.get("address"),
                "value": value,
                "original_value": value * scale if scale != 1 else value,
                "type": register.get("type", "uint16"),
                "device": self.name
            }

            # Füge optionale Parameter zum Log hinzu
            if scale != 1:
                log_extra["scale"] = scale
            if "unit_of_measurement" in register:
                log_extra["unit"] = register["unit_of_measurement"]
            if "device_class" in register:
                log_extra["device_class"] = register["device_class"]
            if "min" in register:
                log_extra["min"] = register["min"]
            if "max" in register:
                log_extra["max"] = register["max"]

            _LOGGER.debug(
                "Starte Modbus Register Schreibvorgang",
                extra=log_extra
            )

            success = await self._hub.write_register(
                device_name=self.name,
                address=register["address"],
                value=value,
                reg_type=register.get("type", "uint16"),
                scale=1  # Skalierung wurde bereits oben durchgeführt
            )

            if success:
                _LOGGER.debug(
                    "Modbus Register erfolgreich geschrieben",
                    extra=log_extra
                )
            else:
                _LOGGER.warning(
                    "Modbus Register Schreibvorgang fehlgeschlagen",
                    extra=log_extra
                )

            return success

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Schreiben eines Registers",
                extra={
                    "error": str(e),
                    "register_name": register_name,
                    "value": value,
                    "device": self.name
                }
            )
            return False

    async def async_teardown(self):
        """Bereinigt das Gerät und alle zugehörigen Entities."""
        try:
            # Hole die Registries
            ent_reg = er.async_get(self.hass)
            dev_reg = dr.async_get(self.hass)
            
            # Finde das Gerät
            device_entry = dev_reg.async_get_device(
                identifiers={(DOMAIN, self.name)}
            )
            
            if device_entry:
                # Entferne alle Entities
                entities = er.async_entries_for_device(
                    ent_reg,
                    device_entry.id,
                    include_disabled_entities=True
                )
                
                for entity in entities:
                    if entity and entity.entity_id:
                        try:
                            ent_reg.async_remove(entity.entity_id)
                            _LOGGER.debug(
                                f"Entity {entity.entity_id} wurde entfernt",
                                extra={
                                    "device": self.name,
                                    "entity_id": entity.entity_id
                                }
                            )
                        except Exception as e:
                            _LOGGER.warning(
                                "Fehler beim Entfernen einer Entity",
                                extra={
                                    "error": str(e),
                                    "entity_id": entity.entity_id,
                                    "device": self.name
                                }
                            )

                # Entferne auch die Input Helper Entities
                input_prefixes = [
                    f"number.{self.name}_set_",
                    f"select.{self.name}_set_",
                ]
                
                for entity_id in list(self.hass.states.async_entity_ids()):
                    if any(entity_id.startswith(prefix) for prefix in input_prefixes):
                        try:
                            # Entferne aus der Entity Registry
                            ent_reg.async_remove(entity_id)
                            _LOGGER.debug(
                                f"Input Helper Entity {entity_id} wurde entfernt",
                                extra={
                                    "device": self.name,
                                    "entity_id": entity_id
                                }
                            )
                        except Exception as e:
                            _LOGGER.warning(
                                "Fehler beim Entfernen einer Input Helper Entity",
                                extra={
                                    "error": str(e),
                                    "entity_id": entity_id,
                                    "device": self.name
                                }
                            )
                
                # Entferne das Gerät
                try:
                    dev_reg.async_remove_device(device_entry.id)
                    _LOGGER.debug(
                        "Gerät wurde entfernt",
                        extra={
                            "device": self.name
                        }
                    )
                except Exception as e:
                    _LOGGER.warning(
                        "Fehler beim Entfernen des Geräts",
                        extra={
                            "error": str(e),
                            "device": self.name
                        }
                    )

            # Bereinige interne Zustände
            self.entities.clear()
            self._register_data.clear()
            self._setup_complete = False

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Teardown des Geräts",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
    def _process_register_value(
        self,
        register_name: str,
        register_def: Dict[str, Any],
        raw_value: Any
    ) -> Any:
        """Verarbeitet den Rohwert eines Registers basierend auf seiner Definition."""
        if raw_value is None:
            return None

        try:
            reg_type = register_def.get("type", "uint16")
            swap = register_def.get("swap", "")

            # Spezielle Behandlung für String-Register
            if reg_type == "string":
                try:
                    # Jeder Register-Wert enthält 2 ASCII-Zeichen
                    chars = []
                    for value in raw_value:
                        # Extrahiere die beiden ASCII-Zeichen aus dem 16-bit Wert
                        high_byte = (value >> 8) & 0xFF
                        low_byte = value & 0xFF
                        # Nur druckbare ASCII-Zeichen (32-126) und einige Steuerzeichen akzeptieren
                        if 32 <= high_byte <= 126:
                            chars.append(chr(high_byte))
                        if 32 <= low_byte <= 126:
                            chars.append(chr(low_byte))
                    # Verbinde die Zeichen und entferne Whitespace
                    result = ''.join(chars).strip()
                    # Spezielle Behandlung für Battery Serial
                    if register_name == "battery_serial" and not any(32 <= ord(c) <= 126 for c in result):
                        return "Encrypted or Not Available"
                    return result
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der String-Konvertierung",
                        extra={
                            "error": str(e),
                            "register": register_name,
                            "raw_value": raw_value
                        }
                    )
                    return None

            # Für numerische Register
            if isinstance(raw_value, (list, tuple)):
                # Behandle mehrere Register als ein Wert (z.B. für 32-bit Werte)
                if reg_type in ["uint32", "int32", "float32"] and len(raw_value) >= 2:
                    from pymodbus.payload import BinaryPayloadDecoder
                    from pymodbus.constants import Endian
                    
                    # Die Standard HA Modbus-Komponente verwendet diese Konfiguration
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        raw_value,
                        byteorder=Endian.BIG,
                        wordorder=Endian.LITTLE
                    )
                    
                    if reg_type == "int32":
                        processed_value = decoder.decode_32bit_int()
                    elif reg_type == "uint32":
                        processed_value = decoder.decode_32bit_uint()
                    elif reg_type == "float32":
                        processed_value = decoder.decode_32bit_float()
                else:
                    # Einzelnes Register (16-bit)
                    value = raw_value[0]
                    if reg_type == "int16":
                        # Konvertiere zu signed 16-bit
                        if value > 32767:  # 2^15 - 1
                            value = value - 65536  # 2^16
                    processed_value = value
            else:
                # Einzelner Wert
                value = raw_value
                if reg_type == "int16":
                    # Konvertiere zu signed 16-bit
                    if value > 32767:  # 2^15 - 1
                        value = value - 65536  # 2^16
                processed_value = value

            # Spezielle Behandlungen für bestimmte Register
            if register_name == "device_code":
                hex_code = f"0x{int(processed_value):04X}"
                device_type_mapping = self._device_config.get("device_type_mapping", {})
                return device_type_mapping.get(hex_code, f"Unknown device code: {hex_code}")
                
            elif register_name == "system_state":
                hex_code = f"0x{int(processed_value):04X}"
                system_state_mapping = self._device_config.get("system_state_mapping", {})
                return system_state_mapping.get(hex_code, f"Unknown state code: {hex_code}")
                
            elif register_name == "battery_forced_charge_discharge_cmd":
                battery_cmd = self._get_register_value("battery_forced_charge_discharge")
                if battery_cmd is not None:
                    battery_cmd_mapping = self._device_config.get("battery_cmd_mapping", {})
                    hex_code = f"0x{int(battery_cmd):04X}"
                    return battery_cmd_mapping.get(hex_code, f"Unknown command code: {hex_code}")

            return processed_value

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Wertverarbeitung",
                extra={
                    "error": str(e),
                    "register": register_name,
                    "raw_value": raw_value,
                    "type": reg_type
                }
            )
            return None

    def _get_register_value(self, register_name: str) -> Optional[float]:
        """Hilfsmethode zum Abrufen eines Registerwerts."""
        try:
            # Suche zuerst in den Lese-Registern
            register_def = next(
                (reg for reg in self._device_config["registers"]["read"] 
                 if reg["name"] == register_name),
                None
            )
            
            # Wenn nicht gefunden, suche in den Schreib-Registern
            if not register_def:
                register_def = next(
                    (reg for reg in self._device_config["registers"].get("write", [])
                     if reg["name"] == register_name),
                    None
                )
            
            if not register_def:
                return None

            # Für berechnete Register
            if register_def.get("type") == "calculated":
                return self._register_data.get(register_name)
                
            # Für normale Register
            raw_value = self._register_data.get(register_name)
            if raw_value is None:
                return None
                
            return self._process_register_value(register_name, register_def, raw_value)
            
        except Exception:
            return None

    async def setup_input_sync(self) -> None:
        """Setup synchronization between Modbus registers and input helpers."""
        for sync_config in self._device_config.get("input_sync", []):
            source_entity = sync_config.get("source_entity")
            target_entity = sync_config.get("target_entity")
            mapping = sync_config.get("mapping", {})
            
            if not source_entity or not target_entity:
                continue

            @callback
            def _state_changed_listener(event, target=target_entity, mapping=mapping):
                """Handle source entity state changes."""
                new_state = event.data.get("new_state")
                if new_state is None or new_state.state in ("unknown", "unavailable"):
                    return

                # Bestimme den Service basierend auf dem Entity-Typ
                domain = target.split(".")[0]
                
                # Verarbeite den Wert basierend auf dem Entity-Typ
                if domain == "input_number":
                    service = "set_value"
                    try:
                        value = float(new_state.state)
                    except (ValueError, TypeError):
                        return
                    service_data = {"value": value}
                    
                elif domain == "input_text":
                    service = "set_value"
                    service_data = {"value": str(new_state.state)}
                    
                elif domain == "input_select":
                    service = "select_option"
                    # Wende das Mapping an, falls vorhanden
                    if mapping:
                        state_value = str(new_state.state)
                        if state_value in mapping:
                            option = mapping[state_value]
                        elif "*" in mapping:  # Fallback für alle anderen Werte
                            option = mapping["*"]
                        else:
                            option = state_value
                    else:
                        option = str(new_state.state)
                    service_data = {"option": option}
                    
                elif domain == "input_boolean":
                    service = "turn_on" if new_state.state == "on" else "turn_off"
                    service_data = {}
                else:
                    return

                service_data["entity_id"] = target
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        domain, service, service_data
                    )
                )

            # Registriere den State Change Listener
            remove_listener = async_track_state_change_event(
                self.hass, [source_entity], _state_changed_listener
            )
            self._remove_state_listeners.append(remove_listener)

    async def unload(self) -> None:
        """Unload the device."""
        # Entferne alle State Change Listener
        while self._remove_state_listeners:
            remove_listener = self._remove_state_listeners.pop()
            remove_listener()

    async def write_modbus_with_validation(self, register_name: str, value: Any, validation_rules: dict = None) -> bool:
        """Schreibt einen Wert in ein Modbus-Register mit Validierung."""
        try:
            # Prüfe ob Schreibzugriff erlaubt ist
            write_enabled = self.hass.states.get("input_boolean.enable_modbus_write")
            if not write_enabled or write_enabled.state != "on":
                _LOGGER.warning(
                    "Modbus Schreibzugriff ist deaktiviert",
                    extra={
                        "register": register_name,
                        "value": value
                    }
                )
                return False

            # Validiere den Wert
            if validation_rules:
                if "min" in validation_rules and value < validation_rules["min"]:
                    _LOGGER.warning(
                        "Wert unter Minimum",
                        extra={
                            "value": value,
                            "min": validation_rules["min"],
                            "register": register_name
                        }
                    )
                    return False
                if "max" in validation_rules and value > validation_rules["max"]:
                    _LOGGER.warning(
                        "Wert über Maximum",
                        extra={
                            "value": value,
                            "max": validation_rules["max"],
                            "register": register_name
                        }
                    )
                    return False
                if "allowed_values" in validation_rules and value not in validation_rules["allowed_values"]:
                    _LOGGER.warning(
                        "Wert nicht in erlaubten Werten",
                        extra={
                            "value": value,
                            "allowed_values": validation_rules["allowed_values"],
                            "register": register_name
                        }
                    )
                    return False

            # Schreibe den Wert
            success = await self.async_write_register(register_name, value)
            
            if success:
                _LOGGER.info(
                    "Wert erfolgreich geschrieben",
                    extra={
                        "value": value,
                        "register": register_name
                    }
                )
            else:
                _LOGGER.warning(
                    "Fehler beim Schreiben",
                    extra={
                        "value": value,
                        "register": register_name
                    }
                )
                
            return success

        except Exception as e:
            _LOGGER.error(
                "Fehler bei write_modbus_with_validation",
                extra={
                    "error": str(e),
                    "value": value,
                    "register": register_name
                }
            )
            return False

    async def set_battery_mode(self, mode: str, power: float = None) -> bool:
        """Setzt den Batteriemodus mit Validierung."""
        allowed_modes = {
            "forced_discharge": {
                "ems_mode": "Forced mode",
                "battery_cmd": "Forced discharge"
            },
            "forced_charge": {
                "ems_mode": "Forced mode",
                "battery_cmd": "Forced charge"
            },
            "bypass": {
                "ems_mode": "Forced mode",
                "battery_cmd": "Stop (default)"
            },
            "self_consumption": {
                "ems_mode": "Self-consumption mode (default)",
                "battery_cmd": "Stop (default)"
            }
        }

        if mode not in allowed_modes:
            _LOGGER.warning(
                "Ungültiger Batteriemodus",
                extra={
                    "mode": mode,
                    "allowed_modes": list(allowed_modes.keys())
                }
            )
            return False

        try:
            # Setze EMS Mode
            success = await self.write_modbus_with_validation(
                "bms_mode_selection_raw",
                allowed_modes[mode]["ems_mode"],
                {"allowed_values": ["Self-consumption mode (default)", "Forced mode"]}
            )
            if not success:
                return False

            # Setze Battery Command
            success = await self.write_modbus_with_validation(
                "battery_forced_charge_discharge",
                allowed_modes[mode]["battery_cmd"],
                {"allowed_values": ["Stop (default)", "Forced charge", "Forced discharge"]}
            )
            if not success:
                return False

            # Setze Power wenn angegeben
            if power is not None:
                success = await self.write_modbus_with_validation(
                    "battery_forced_charge_discharge_power",
                    power,
                    {"min": 0, "max": 5000}
                )
                if not success:
                    return False

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setzen des Batteriemodus",
                extra={
                    "error": str(e),
                    "mode": mode,
                    "power": power
                }
            )
            return False

    async def set_inverter_mode(self, mode: str) -> bool:
        """Setzt den Wechselrichter-Modus."""
        try:
            if mode not in ["Enabled", "Shutdown"]:
                _LOGGER.warning(
                    "Ungültiger Wechselrichter-Modus",
                    extra={
                        "mode": mode,
                        "allowed_modes": ["Enabled", "Shutdown"]
                    }
                )
                return False

            value = 0xCF if mode == "Enabled" else 0xCE
            return await self.write_modbus_with_validation(
                "inverter_start_stop",
                value,
                {"allowed_values": [0xCF, 0xCE]}
            )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setzen des Wechselrichter-Modus",
                extra={
                    "error": str(e),
                    "mode": mode
                }
            )
            return False

    async def set_export_power_limit(self, enabled: bool, limit: float = None) -> bool:
        """Setzt die Einspeiselimitierung."""
        try:
            # Setze den Modus
            success = await self.write_modbus_with_validation(
                "export_power_limit_mode_raw",
                0xAA if enabled else 0x55,
                {"allowed_values": [0xAA, 0x55]}
            )
            if not success:
                return False

            # Setze das Limit wenn angegeben
            if limit is not None:
                success = await self.write_modbus_with_validation(
                    "export_power_limit",
                    limit,
                    {"min": 0, "max": 10500}
                )
                if not success:
                    return False

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setzen der Einspeiselimitierung",
                extra={
                    "error": str(e),
                    "enabled": enabled,
                    "limit": limit
                }
            )
            return False

    async def execute_action(self, action_id: str, **kwargs):
        """Führt eine vordefinierte Aktion aus."""
        if action_id not in self.actions:
            raise ValueError(f"Unbekannte Aktion: {action_id}")

        action = self.actions[action_id]
        sequence = action.get("sequence", [])
        
        for step in sequence:
            service = step.get("service")
            target = step.get("target")
            data = step.get("data", {})
            
            # Führe den Service-Call aus
            await self.hass.services.async_call(
                service.split(".")[0],
                service.split(".")[1],
                service_data=data,
                target={"entity_id": target}
            )

    async def set_forced_discharge_mode(self):
        """Setzt den Wechselrichter in den Forced Discharge Modus."""
        await self.execute_action("set_forced_discharge_mode")

    async def set_forced_charge_mode(self):
        """Setzt den Wechselrichter in den Forced Charge Modus."""
        await self.execute_action("set_forced_charge_mode")

    async def set_battery_bypass_mode(self):
        """Setzt den Wechselrichter in den Battery Bypass Modus."""
        await self.execute_action("set_battery_bypass_mode")

    async def set_self_consumption_mode(self):
        """Setzt den Wechselrichter in den Self Consumption Modus."""
        await self.execute_action("set_self_consumption_mode")








