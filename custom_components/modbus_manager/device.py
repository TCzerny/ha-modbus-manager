"""Modbus Manager Device Class."""
from __future__ import annotations

from datetime import timedelta
from typing import Dict, Any, Optional

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
    """Repräsentiert ein Modbus-Gerät."""

    def __init__(
        self,
        hub,
        device_type: str,
        config: dict,
        register_definitions: Optional[Dict[str, Any]] = None,
    ):
        """Initialisiert das Gerät."""
        self.name = config.get("name")
        self._logger = ModbusManagerLogger(name=f"device_{self.name}")
        
        self.hub = hub
        self.hass = hub.hass
        self.device_type = device_type
        self.config = config
        self.entry_id = config.get("entry_id")
        self.config_entry = config.get("config_entry")
        
        # YAML-Definitionen
        self._device_config = register_definitions or {}
        
        # Entity-Verwaltung
        self.entities: Dict[str, Any] = {}
        self._register_data: Dict[str, Any] = {}
        self._setup_complete = False
        self._remove_state_listeners = []

    @property
    def device_info(self) -> DeviceInfo:
        """Gibt die Geräteinformationen zurück."""
        info = {
            "identifiers": {(DOMAIN, self.name)},
            "name": self.name,
            "manufacturer": self.config.get("manufacturer", "Modbus Manager"),
            "model": self.config.get("model", self.device_type)
        }
            
        return DeviceInfo(**info)

    async def async_setup(self) -> bool:
        """Führt das Setup des Geräts durch."""
        try:
            self._logger.debug(
                "Starte Geräte-Setup",
                extra={
                    "device": self.name,
                    "device_type": self.device_type
                }
            )

            # Registriere das Gerät im Device Registry
            dev_reg = dr.async_get(self.hass)
            device_entry = dev_reg.async_get_or_create(
                config_entry_id=self.entry_id,
                **self.device_info
            )

            # Verarbeite Register-Definitionen
            if "registers" in self._device_config:
                self._logger.debug(
                    "Verarbeite Register-Definitionen",
                    extra={
                        "device": self.name,
                        "read_count": len(self._device_config["registers"].get("read", [])),
                        "write_count": len(self._device_config["registers"].get("write", []))
                    }
                )
                
                # Input Register (nur lesen)
                for register in self._device_config["registers"].get("read", []):
                    entity = await self._create_register_entity(register, writable=False)
                    if entity:
                        self.entities[entity.entity_id] = entity
                
                # Holding Register (lesen/schreiben)
                for register in self._device_config["registers"].get("write", []):
                    entity = await self._create_register_entity(register, writable=True)
                    if entity:
                        self.entities[entity.entity_id] = entity

            # Erstelle Helper-Entities
            await self._setup_helper_entities()

            # Setup Automation Components
            await self.setup_automation_components()

            self._setup_complete = True
            
            self._logger.debug(
                "Geräte-Setup abgeschlossen",
                extra={
                    "device": self.name,
                    "entities_count": len(self.entities)
                }
            )
            
            return True

        except Exception as e:
            self._logger.error(
                "Fehler beim Setup des Geräts",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _create_register_entity(self, register_def: dict, writable: bool = False) -> Optional[ModbusRegisterEntity]:
        """Erstellt eine Register-Entity."""
        try:
            # Hole das Polling-Intervall
            polling_interval = str(register_def.get("polling_interval", 30))
            
            # Prüfe ob ein Koordinator für dieses Intervall existiert
            if polling_interval not in self.hub.coordinators:
                _LOGGER.error(
                    "Kein Koordinator für das Polling-Intervall gefunden",
                    extra={
                        "polling_interval": polling_interval,
                        "register": register_def.get("name"),
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
                register_name=register_def.get("name"),
                register_config=register_def,
                coordinator=self.hub.coordinators[polling_interval],
            )
            
            # Setze die Entity-ID
            entity.entity_id = f"{domain}.{register_def.get('name').lower()}"
            
            self._logger.debug(
                "Register-Entity erstellt",
                extra={
                    "entity_id": entity.entity_id,
                    "register": register_def.get("name"),
                    "device": self.name,
                    "domain": domain,
                    "writable": writable
                }
            )
            
            return entity

        except Exception as e:
            self._logger.error(
                "Fehler beim Erstellen einer Register-Entity",
                extra={
                    "error": str(e),
                    "register": register_def.get("name"),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def _setup_helper_entities(self):
        """Erstellt Helper-Entities über die Registry API."""
        try:
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
                        # Setze die Entity-ID
                        entity.entity_id = f"number.{input_id.lower()}"
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
                            # Setze die Entity-ID
                            entity.entity_id = f"select.{input_id.lower()}"
                            self.entities[entity.entity_id] = entity

            self._logger.debug(
                "Helper-Entities erfolgreich erstellt",
                extra={
                    "device": self.name,
                    "input_numbers": len(self._device_config.get("input_number", {})),
                    "input_selects": len(self._device_config.get("input_select", {}))
                }
            )

        except Exception as e:
            self._logger.error(
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
                self._logger.debug(
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
                self._logger.debug(
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
                self._logger.debug(
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

            self._logger.debug(
                "Automatisierungskomponenten erfolgreich eingerichtet",
                extra={
                    "device": self.name,
                    "triggers": len(self._device_config.get("device_triggers", [])),
                    "conditions": len(self._device_config.get("device_conditions", [])),
                    "actions": len(self._device_config.get("device_actions", []))
                }
            )

        except Exception as e:
            self._logger.error(
                "Fehler beim Einrichten der Automatisierungskomponenten",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )

    async def async_update(self, polling_interval: str = "30") -> Dict[str, Any]:
        """Aktualisiert die Registerwerte für das angegebene Polling-Intervall."""
        try:
            if not self._setup_complete:
                return {}

            data = {}
            errors = []
            
            # Lese alle Register mit dem entsprechenden Polling-Intervall
            if "registers" in self._device_config:
                # Input Register (nur lesen)
                for register in self._device_config["registers"].get("read", []):
                    if str(register.get("polling_interval", "30")) == polling_interval:
                        try:
                            await self._read_register(register, data)
                        except Exception as e:
                            errors.append({
                                "register": register.get("name"),
                                "error": str(e)
                            })
                            self._logger.error(
                                "Fehler beim Lesen eines Registers",
                                extra={
                                    "error": str(e),
                                    "register": register.get("name"),
                                    "device": self.name
                                }
                            )
                            # Fahre mit dem nächsten Register fort
                            continue
                
                # Holding Register (lesen/schreiben)
                for register in self._device_config["registers"].get("write", []):
                    if str(register.get("polling_interval", "30")) == polling_interval:
                        try:
                            await self._read_register(register, data)
                        except Exception as e:
                            errors.append({
                                "register": register.get("name"),
                                "error": str(e)
                            })
                            self._logger.error(
                                "Fehler beim Lesen eines Registers",
                                extra={
                                    "error": str(e),
                                    "register": register.get("name"),
                                    "device": self.name
                                }
                            )
                            # Fahre mit dem nächsten Register fort
                            continue

            # Aktualisiere die Register-Daten für dieses Intervall
            for key, value in data.items():
                self._register_data[key] = value
            
            # Logge eine Zusammenfassung
            self._logger.debug(
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
            self._logger.error(
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
            reg_type = register.get("type", "uint16")
            reg_count = register.get("count", 1)
            swap = register.get("swap", "").lower()
            
            # Bestimme den Register-Typ für das Lesen
            # Verwende immer "input" zum Lesen, außer es ist explizit "holding" spezifiziert
            register_type = register.get("register_type", "input")
            
            self._logger.debug(
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
            
            result = await self.hub.read_register(
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
                
                self._logger.debug(
                    "Modbus Register erfolgreich gelesen",
                    extra=log_extra
                )
            else:
                self._logger.warning(
                    "Modbus Register Lesevorgang ohne Ergebnis",
                    extra={
                        "register_name": register.get("name"),
                        "address": register.get("address"),
                        "type": reg_type,
                        "device": self.name
                    }
                )

        except Exception as e:
            self._logger.error(
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
                self._logger.warning(
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
                self._logger.error(
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
                self._logger.warning(
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
                self._logger.warning(
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

            self._logger.debug(
                "Starte Modbus Register Schreibvorgang",
                extra=log_extra
            )

            success = await self.hub.write_register(
                device_name=self.name,
                address=register["address"],
                value=value,
                reg_type=register.get("type", "uint16"),
                scale=1  # Skalierung wurde bereits oben durchgeführt
            )

            if success:
                self._logger.debug(
                    "Modbus Register erfolgreich geschrieben",
                    extra=log_extra
                )
            else:
                self._logger.warning(
                    "Modbus Register Schreibvorgang fehlgeschlagen",
                    extra=log_extra
                )

            return success

        except Exception as e:
            self._logger.error(
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
                            await ent_reg.async_remove(entity.entity_id)
                            self._logger.debug(
                                f"Entity {entity.entity_id} wurde entfernt",
                                extra={
                                    "device": self.name,
                                    "entity_id": entity.entity_id
                                }
                            )
                        except Exception as e:
                            self._logger.warning(
                                "Fehler beim Entfernen einer Entity",
                                extra={
                                    "error": str(e),
                                    "entity_id": entity.entity_id,
                                    "device": self.name
                                }
                            )
                
                # Entferne das Gerät
                try:
                    dev_reg.async_remove_device(device_entry.id)
                    self._logger.debug(
                        "Gerät wurde entfernt",
                        extra={
                            "device": self.name
                        }
                    )
                except Exception as e:
                    self._logger.warning(
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
            self._logger.error(
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
        """Verarbeitet den Rohwert eines Registers basierend auf seinem Typ."""
        try:
            if raw_value is None:
                return None

            reg_type = register_def.get("type", "uint16")
            
            # Für String-Register
            if reg_type == "string":
                try:
                    # Konvertiere die Register-Werte in ASCII-Zeichen
                    ascii_string = ""
                    for value in raw_value:
                        # Extrahiere die beiden ASCII-Zeichen aus jedem Register
                        high_byte = (value >> 8) & 0xFF
                        low_byte = value & 0xFF
                        
                        # Füge nur gültige ASCII-Zeichen hinzu
                        if high_byte >= 32 and high_byte <= 126:  # Druckbare ASCII-Zeichen
                            ascii_string += chr(high_byte)
                        if low_byte >= 32 and low_byte <= 126:  # Druckbare ASCII-Zeichen
                            ascii_string += chr(low_byte)
                    
                    # Entferne Nullbytes und Leerzeichen am Ende
                    return ascii_string.strip('\x00 ')
                    
                except Exception as e:
                    self._logger.error(
                        "Fehler bei der String-Konvertierung",
                        extra={
                            "error": str(e),
                            "register": register_name,
                            "raw_value": raw_value,
                            "device": self.name
                        }
                    )
                    return None

            # Für numerische Register
            processed_value = None
            
            if isinstance(raw_value, (list, tuple)):
                if len(raw_value) == 1:
                    processed_value = raw_value[0]
                else:
                    # Behandle mehrere Register als ein Wert (z.B. für 32-bit Werte)
                    if reg_type == "uint32" and len(raw_value) >= 2:
                        processed_value = (raw_value[0] << 16) | raw_value[1]
                    elif reg_type == "int32" and len(raw_value) >= 2:
                        value = (raw_value[0] << 16) | raw_value[1]
                        if value > 2147483647:  # 2^31 - 1
                            processed_value = value - 4294967296  # 2^32
                        else:
                            processed_value = value
                    elif reg_type == "float32" and len(raw_value) >= 2:
                        import struct
                        # Konvertiere zwei 16-bit Register in einen 32-bit Float
                        combined = (raw_value[0] << 16) | raw_value[1]
                        processed_value = struct.unpack('!f', struct.pack('!I', combined))[0]
                    else:
                        processed_value = raw_value[0]
            else:
                processed_value = raw_value

            # Konvertiere zu float für weitere Verarbeitung
            if processed_value is not None:
                processed_value = float(processed_value)

                # Skalierung anwenden wenn konfiguriert
                if "scale" in register_def:
                    processed_value = processed_value * register_def["scale"]

                # Wert entsprechend der Präzision runden
                if "precision" in register_def:
                    processed_value = round(processed_value, register_def["precision"])

            return processed_value

        except Exception as e:
            self._logger.error(
                "Fehler bei der Wertverarbeitung",
                extra={
                    "error": str(e),
                    "register": register_name,
                    "raw_value": raw_value,
                    "register_type": reg_type,
                    "device": self.name
                }
            )
            return None

    async def setup_device(self) -> None:
        """Set up the device."""
        # Registriere das Gerät
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.entry_id,
            identifiers={(DOMAIN, self.name)},
            name=self.name,
            manufacturer=self.config.get("manufacturer", "Unknown"),
            model=self.config.get("model", "Unknown"),
        )

        # Setup Input Synchronization
        if "input_sync" in self._device_config:
            await self.setup_input_sync()

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
                self._logger.warning(
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
                    self._logger.warning(
                        "Wert unter Minimum",
                        extra={
                            "value": value,
                            "min": validation_rules["min"],
                            "register": register_name
                        }
                    )
                    return False
                if "max" in validation_rules and value > validation_rules["max"]:
                    self._logger.warning(
                        "Wert über Maximum",
                        extra={
                            "value": value,
                            "max": validation_rules["max"],
                            "register": register_name
                        }
                    )
                    return False
                if "allowed_values" in validation_rules and value not in validation_rules["allowed_values"]:
                    self._logger.warning(
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
                self._logger.info(
                    "Wert erfolgreich geschrieben",
                    extra={
                        "value": value,
                        "register": register_name
                    }
                )
            else:
                self._logger.warning(
                    "Fehler beim Schreiben",
                    extra={
                        "value": value,
                        "register": register_name
                    }
                )
                
            return success

        except Exception as e:
            self._logger.error(
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
            self._logger.warning(
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
            self._logger.error(
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
                self._logger.warning(
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
            self._logger.error(
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
            self._logger.error(
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