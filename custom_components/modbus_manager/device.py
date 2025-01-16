"""Modbus Manager Device Class."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Dict, Any, Optional, List


from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_NAME, CONF_DEVICE_ID
from homeassistant.helpers.event import async_track_state_change_event

from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.input_select import DOMAIN as INPUT_SELECT_DOMAIN

from .const import DOMAIN, NameType
from .logger import ModbusManagerLogger
from .entities import ModbusRegisterEntity
from .input_entities import ModbusManagerInputNumber, ModbusManagerInputSelect
from .helpers import EntityNameHelper



_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerDevice:
    """Modbus Manager Device class."""

    def __init__(
        self,
        hub,
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
        self.config_entry = hub.config_entry
        self.name_helper = EntityNameHelper(self.config_entry)
        
        # Hole die Default-Polling-Intervalle
        polling_config = register_definitions.get("polling", {})
        self._fast_interval = int(polling_config.get("fast", {}).get("interval", 5))
        self._normal_interval = int(polling_config.get("normal", {}).get("interval", 15))
        self._slow_interval = int(polling_config.get("slow", {}).get("interval", 600))

        # Initialisiere die Register-Listen nach Polling-Intervall
        self._registers_by_interval = {
            self._fast_interval: [],
            self._normal_interval: [],
            self._slow_interval: []
        }
        
        # Lade die Register-Definitionen
        registers = register_definitions.get("registers", {})
        read_registers = registers.get("read", [])
        write_registers = registers.get("write", [])
        
        # Ordne die Register den Polling-Intervallen zu
        for register in read_registers + write_registers:
            register_name = register.get("name")
            if not register_name:
                continue
                
            # Bestimme das Polling-Intervall für dieses Register
            interval = self._normal_interval  # Standard-Intervall
            
            # Prüfe in welchem Polling-Intervall das Register definiert ist
            for poll_type, poll_config in polling_config.items():
                if register_name in poll_config.get("registers", []):
                    interval = int(poll_config.get("interval", self._normal_interval))
                    break
            
            # Füge das Register zur entsprechenden Liste hinzu
            self._registers_by_interval[interval].append(register)
        
        _LOGGER.info(
            "Device initialisiert",
            extra={
                "device": self.name,
                "fast_register_count": len(self._registers_by_interval[self._fast_interval]),
                "normal_register_count": len(self._registers_by_interval[self._normal_interval]),
                "slow_register_count": len(self._registers_by_interval[self._slow_interval]),
                "register_names": {
                    "fast": [reg.get("name") for reg in self._registers_by_interval[self._fast_interval]],
                    "normal": [reg.get("name") for reg in self._registers_by_interval[self._normal_interval]],
                    "slow": [reg.get("name") for reg in self._registers_by_interval[self._slow_interval]]
                }
            }
        )
        
        # Initialisiere die Koordinatoren
        for interval in [self._fast_interval, self._normal_interval, self._slow_interval]:
            if not self._hub.get_coordinator(interval):
                self._hub.create_coordinator(interval)

        self.unique_id = f"modbus_manager_{self.name.lower()}"
        self.manufacturer = config.get("manufacturer", "Unknown")
        self.model = config.get("model", "Generic Modbus Device")
        
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
                        _LOGGER.error(
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
        """Erstellt eine Entity für ein Register."""
        try:
            # Hole den Coordinator vom Hub
            coordinator = self._hub.get_coordinator(self._normal_interval)
            if not coordinator:
                return None
            
            # Erstelle die Entity mit dem Original-Namen aus der Definition
            entity = ModbusRegisterEntity(
                device=self,
                register_name=register_name,  # Original-Name aus der Definition
                register_config=register_def,
                coordinator=coordinator
            )
            
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

    async def validate_helper_entities(self) -> bool:
        """Validiert die Registrierung und Konfiguration der Helper-Entities."""
        try:
            # Hole die Entity Registry
            entity_registry = er.async_get(self.hass)
            
            # Validiere Input Number Entities
            if "input_number" in self._device_config:
                for input_id, config in self._device_config["input_number"].items():
                    # Erstelle erwartete Entity-ID
                    expected_entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="number")
                    
                    # Prüfe ob Entity in Registry existiert
                    entity = entity_registry.async_get(expected_entity_id)
                    if not entity:
                        _LOGGER.error(
                            "Input Number Entity nicht in Registry gefunden",
                            extra={
                                "input_id": input_id,
                                "expected_entity_id": expected_entity_id,
                                "device": self.name
                            }
                        )
                        return False
                    
                    # Validiere Entity-Attribute
                    expected_unique_id = self.name_helper.convert(input_id, NameType.UNIQUE_ID)
                    if entity.unique_id != expected_unique_id:
                        _LOGGER.error(
                            "Unique ID stimmt nicht überein",
                            extra={
                                "input_id": input_id,
                                "expected": expected_unique_id,
                                "actual": entity.unique_id,
                                "device": self.name
                            }
                        )
                        return False
                    
                    _LOGGER.debug(
                        "Input Number Entity validiert",
                        extra={
                            "entity_id": expected_entity_id,
                            "unique_id": expected_unique_id,
                            "device": self.name
                        }
                    )

            # Validiere Input Select Entities
            if "input_select" in self._device_config:
                for input_id, config in self._device_config["input_select"].items():
                    # Erstelle erwartete Entity-ID
                    expected_entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="select")
                    
                    # Prüfe ob Entity in Registry existiert
                    entity = entity_registry.async_get(expected_entity_id)
                    if not entity:
                        _LOGGER.error(
                            "Input Select Entity nicht in Registry gefunden",
                            extra={
                                "input_id": input_id,
                                "expected_entity_id": expected_entity_id,
                                "device": self.name
                            }
                        )
                        return False
                    
                    # Validiere Entity-Attribute
                    expected_unique_id = self.name_helper.convert(input_id, NameType.UNIQUE_ID)
                    if entity.unique_id != expected_unique_id:
                        _LOGGER.error(
                            "Unique ID stimmt nicht überein",
                            extra={
                                "input_id": input_id,
                                "expected": expected_unique_id,
                                "actual": entity.unique_id,
                                "device": self.name
                            }
                        )
                        return False
                    
                    _LOGGER.debug(
                        "Input Select Entity validiert",
                        extra={
                            "entity_id": expected_entity_id,
                            "unique_id": expected_unique_id,
                            "device": self.name
                        }
                    )

            _LOGGER.info(
                "Alle Helper-Entities erfolgreich validiert",
                extra={
                    "device": self.name,
                    "input_numbers": len(self._device_config.get("input_number", {})),
                    "input_selects": len(self._device_config.get("input_select", {}))
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Validierung der Helper-Entities",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

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
                    try:
                        # Erstelle Input Number Entity
                        entity = ModbusManagerInputNumber(
                            device=self,
                            name=input_id,
                            config=config,
                            register_config=config.get("register", {})
                        )
                        
                        if not entity:
                            _LOGGER.error(
                                "Fehler beim Erstellen der Input Number Entity",
                                extra={
                                    "input_id": input_id,
                                    "device": self.name
                                }
                            )
                            continue

                        # Setze die Entity-ID und unique_id mit dem Helper
                        entity.entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="number")
                        entity._attr_unique_id = self.name_helper.convert(input_id, NameType.UNIQUE_ID)
                        entity._attr_name = self.name_helper.convert(input_id, NameType.DISPLAY_NAME)
                        
                        _LOGGER.debug(
                            "Input Number Entity wird erstellt",
                            extra={
                                "entity_id": entity.entity_id,
                                "unique_id": entity._attr_unique_id,
                                "name": entity._attr_name,
                                "device": self.name
                            }
                        )
                        
                        # Registriere die Entity in der Entity Registry
                        entity_registry = er.async_get(self.hass)
                        entity_registry.async_get_or_create(
                            domain="number",
                            platform=DOMAIN,
                            unique_id=entity._attr_unique_id,
                            device_id=device.id,
                            suggested_object_id=self.name_helper.convert(input_id, NameType.BASE_NAME),
                            original_name=entity._attr_name
                        )
                        
                        self.entities[entity.entity_id] = entity
                        
                    except Exception as e:
                        _LOGGER.error(
                            "Fehler bei der Input Number Entity-Erstellung",
                            extra={
                                "input_id": input_id,
                                "error": str(e),
                                "device": self.name
                            }
                        )

            # Nach der Erstellung aller Entities, validiere sie
            validation_result = await self.validate_helper_entities()
            if not validation_result:
                _LOGGER.error(
                    "Validierung der Helper-Entities fehlgeschlagen",
                    extra={
                        "device": self.name
                    }
                )
                return

            # Führe Entity-Tests durch
            test_result = await self.test_helper_entities()
            if not test_result:
                _LOGGER.error(
                    "Tests der Helper-Entities fehlgeschlagen",
                    extra={
                        "device": self.name
                    }
                )
                return

            # Führe Service-Tests durch
            service_test_result = await self.test_service_calls()
            if not service_test_result:
                _LOGGER.error(
                    "Service-Tests fehlgeschlagen",
                    extra={
                        "device": self.name
                    }
                )
                return

            # Führe End-to-End Tests durch
            mapping_test_result = await self.test_register_mappings()
            if not mapping_test_result:
                _LOGGER.error(
                    "End-to-End Tests fehlgeschlagen",
                    extra={
                        "device": self.name
                    }
                )
                return

            # Führe Berechnungstests durch
            calculation_test_result = await self.test_calculations()
            if not calculation_test_result:
                _LOGGER.error(
                    "Berechnungstests fehlgeschlagen",
                    extra={
                        "device": self.name
                    }
                )
                return

            _LOGGER.info(
                "Helper-Entities erfolgreich erstellt, validiert und getestet",
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

    async def test_calculations(self) -> bool:
        """Testet die Berechnungsfunktionalität für Register."""
        try:
            _LOGGER.info(
                "Starte Test der Berechnungsfunktionalität",
                extra={
                    "device": self.name
                }
            )

            # Test 1: Formelauswertung
            if "calculated_registers" in self._device_config:
                for calc_register in self._device_config["calculated_registers"]:
                    register_name = calc_register.get("name")
                    calculation = calc_register.get("calculation", {})
                    
                    if calculation.get("type") == "formula":
                        formula = calculation.get("formula", "")
                        
                        _LOGGER.debug(
                            "Teste Formelberechnung",
                            extra={
                                "register": register_name,
                                "formula": formula,
                                "device": self.name
                            }
                        )

                        # Teste mit Test-Werten
                        test_values = {
                            "battery_level": 75.5,
                            "battery_state_of_health": 98.2,
                            "battery_power": 2500.0,
                            "grid_power": 1500.0
                        }

                        # Erstelle präfixierte Test-Werte
                        prefixed_test_values = {}
                        for key, value in test_values.items():
                            prefixed_key = self.name_helper.convert(key, NameType.BASE_NAME)
                            prefixed_test_values[prefixed_key] = value
                            self._register_data[prefixed_key] = value

                        # Berechne den Wert
                        value = self._calculate_register_value(calc_register)
                        if value is None:
                            _LOGGER.error(
                                "Formelberechnung fehlgeschlagen",
                                extra={
                                    "register": register_name,
                                    "formula": formula,
                                    "test_values": test_values,
                                    "device": self.name
                                }
                            )
                            return False

                        _LOGGER.debug(
                            "Formelberechnung erfolgreich",
                            extra={
                                "register": register_name,
                                "formula": formula,
                                "result": value,
                                "test_values": test_values,
                                "device": self.name
                            }
                        )

            # Test 2: Datentyp-Konvertierung
            test_cases = [
                {"type": "uint16", "value": 65535, "expected": 65535},
                {"type": "int16", "value": -32768, "expected": -32768},
                {"type": "uint32", "value": 4294967295, "expected": 4294967295},
                {"type": "int32", "value": -2147483648, "expected": -2147483648},
                {"type": "float32", "value": 3.14159, "expected": 3.14159}
            ]

            for test in test_cases:
                register_def = {
                    "name": f"test_{test['type']}",
                    "type": test["type"]
                }
                
                _LOGGER.debug(
                    "Teste Datentyp-Konvertierung",
                    extra={
                        "type": test["type"],
                        "value": test["value"],
                        "expected": test["expected"],
                        "device": self.name
                    }
                )

                # Teste Konvertierung
                result = self._process_register_value(register_def["name"], register_def, test["value"])
                if result != test["expected"]:
                    _LOGGER.error(
                        "Datentyp-Konvertierung fehlgeschlagen",
                        extra={
                            "type": test["type"],
                            "value": test["value"],
                            "expected": test["expected"],
                            "result": result,
                            "device": self.name
                        }
                    )
                    return False

            # Test 3: Skalierungsfaktoren
            scale_tests = [
                {"scale": 0.1, "value": 100, "expected": 10.0},
                {"scale": 10, "value": 50, "expected": 500.0},
                {"scale": 0.001, "value": 1000, "expected": 1.0}
            ]

            for test in scale_tests:
                register_def = {
                    "name": "test_scale",
                    "type": "uint16",
                    "scale": test["scale"]
                }
                
                _LOGGER.debug(
                    "Teste Skalierungsfaktor",
                    extra={
                        "scale": test["scale"],
                        "value": test["value"],
                        "expected": test["expected"],
                        "device": self.name
                    }
                )

                # Teste Skalierung
                result = self._process_register_value(register_def["name"], register_def, test["value"])
                if abs(result - test["expected"]) > 0.0001:  # Berücksichtige Fließkomma-Ungenauigkeit
                    _LOGGER.error(
                        "Skalierung fehlgeschlagen",
                        extra={
                            "scale": test["scale"],
                            "value": test["value"],
                            "expected": test["expected"],
                            "result": result,
                            "device": self.name
                        }
                    )
                    return False

            _LOGGER.info(
                "Alle Berechnungstests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei Berechnungstests",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def async_update(self, interval: int) -> Dict[str, Any]:
        """Aktualisiert die Gerätedaten für das angegebene Intervall."""
        try:
            # Hole die Register für dieses Intervall
            registers = self._registers_by_interval.get(interval, [])
            
            if not registers:
                _LOGGER.debug(
                    f"Keine Register für Intervall {interval}s",
                    extra={
                        "device": self.name,
                        "interval": interval
                    }
                )
                return {}
            
            # Lese die Register
            data = await self._hub._read_registers(registers)
            
            # Aktualisiere die lokalen Daten
            self._register_data.update(data)
            
            return data
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Aktualisieren der Gerätedaten",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "interval": interval,
                    "traceback": e.__traceback__
                }
            )
            return {}

    async def _read_register(self, register: Dict[str, Any], values: Dict[str, Any]):
        """Liest ein einzelnes Register."""
        try:
            register_name = register.get("name")
            if not register_name:
                _LOGGER.error(
                    "Register hat keinen Namen",
                    extra={
                        "register": register,
                        "device": self.name
                    }
                )
                return
                
            # Lese den Wert
            value = values.get(register_name)
            if value is None:
                _LOGGER.debug(
                    "Kein Wert für Register gefunden",
                    extra={
                        "register": register_name,
                        "device": self.name
                    }
                )
                return
                
            # Verarbeite den Wert
            try:
                processed_value = await self._process_register_value(register_name, register, value)
                if processed_value is not None:
                    self._register_data[register_name] = processed_value
            except Exception as e:
                _LOGGER.error(
                    "Fehler beim Verarbeiten des Register-Werts",
                    extra={
                        "error": str(e),
                        "register": register_name,
                        "device": self.name,
                        "traceback": e.__traceback__
                    }
                )
                
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Lesen des Registers",
                extra={
                    "error": str(e),
                    "register": register.get("name"),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )

    async def _update_entity_state(self, entity) -> bool:
        """Aktualisiert den Zustand einer Entity."""
        if not hasattr(entity, "_register"):
            _LOGGER.error(
                "Entity hat kein Register-Attribut",
                extra={
                    "entity": entity.entity_id,
                    "device": self.name
                }
            )
        return False
            
        register = entity._register
        register_name = register.get("name")
        if not register_name:
            _LOGGER.error(
                "Register hat keinen Namen",
                extra={
                    "entity": entity.entity_id,
                    "device": self.name
                }
            )
            return False
            
        try:
        # Hole den aktuellen Wert und aktualisiere den Zustand
            value = self._register_data.get(register_name)
            if value is None:
                _LOGGER.debug(
                    "Kein Wert für Register gefunden",
                    extra={
                        "entity": entity.entity_id,
                        "register": register_name,
                        "device": self.name
                    }
                )
                return False
                
            entity._attr_native_value = value
            entity.async_write_ha_state()
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Aktualisieren des Entity-Zustands",
                extra={
                    "error": str(e),
                    "entity": entity.entity_id if hasattr(entity, "entity_id") else "Unknown",
                    "register": register_name,
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _process_register_value(self, register_name: str, register_def: Dict[str, Any], raw_value: Any) -> Optional[Any]:
        """Verarbeitet den Rohwert eines Registers."""
        try:
            if raw_value is None:
                return None

            reg_type = register_def.get("type", "uint16")
            scale = register_def.get("scale", 1)
            precision = register_def.get("precision")

            # Konvertiere den Wert basierend auf dem Typ
            try:
                if reg_type == "uint16":
                    value = int(raw_value) & 0xFFFF
                elif reg_type == "int16":
                    value = int(raw_value)
                    if value > 32767:
                        value -= 65536
                elif reg_type == "uint32":
                    value = int(raw_value) & 0xFFFFFFFF
                elif reg_type == "int32":
                    value = int(raw_value)
                    if value > 2147483647:
                        value -= 4294967296
                elif reg_type == "float32":
                    value = float(raw_value)
                elif reg_type == "string":
                    value = str(raw_value)
                else:
                    _LOGGER.error(
                        "Ungültiger Register-Typ",
                        extra={
                            "type": reg_type,
                            "register": register_name,
                            "device": self.name
                        }
                    )
                    return None
            except (ValueError, TypeError) as e:
                _LOGGER.error(
                    "Fehler bei der Typkonvertierung",
                    extra={
                        "error": str(e),
                        "type": reg_type,
                        "raw_value": raw_value,
                        "register": register_name,
                        "device": self.name
                    }
                )
                return None

            # Skaliere den Wert wenn nötig
            if scale != 1:
                try:
                    value = float(value) * scale
                except (ValueError, TypeError) as e:
                    _LOGGER.error(
                        "Fehler bei der Skalierung",
                        extra={
                            "error": str(e),
                            "scale": scale,
                            "value": value,
                            "register": register_name,
                            "device": self.name
                        }
                    )
                    return None

            # Runde auf die angegebene Präzision wenn definiert
            if precision is not None:
                try:
                    value = round(float(value), precision)
                except (ValueError, TypeError) as e:
                    _LOGGER.error(
                        "Fehler beim Runden",
                        extra={
                            "error": str(e),
                            "precision": precision,
                            "value": value,
                            "register": register_name,
                            "device": self.name
                        }
                    )
                    return None

            return value

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Register-Wert-Verarbeitung",
                extra={
                    "error": str(e),
                    "register": register_name,
                    "raw_value": raw_value,
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def _update_calculated_registers(self):
        """Aktualisiert die berechneten Register."""
        try:
            if "calculated_registers" not in self._device_config:
                return

            for register in self._device_config["calculated_registers"]:
                try:
                    register_name = register.get("name")
                    if not register_name:
                        continue

                    value = self._calculate_register_value(register)
                    if value is not None:
                        self._register_data[register_name] = value

                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Berechnung eines Registers",
                        extra={
                            "error": str(e),
                            "register": register.get("name"),
                            "device": self.name,
                            "traceback": e.__traceback__
                        }
                    )

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Aktualisierung der berechneten Register",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )

    def _calculate_register_value(self, register_def: Dict[str, Any]) -> Optional[float]:
        """Berechnet den Wert eines berechneten Registers."""
        try:
            calculation = register_def.get("calculation", {})
            calc_type = calculation.get("type")
            
            _LOGGER.debug(
                "Starte Berechnung für Register",
                extra={
                    "register": register_def.get("name"),
                    "calc_type": calc_type,
                    "device": self.name
                }
            )

            if calc_type == "sum":
                # Summiere die Werte aus den Quellen
                sources = calculation.get("sources", [])
                values = []
                for source in sources:
                    # Verwende den Helper für die präfixierten Namen
                    prefixed_source = self.name_helper.convert(source, NameType.BASE_NAME)
                    value = self._register_data.get(prefixed_source)
                    if value is None:
                        _LOGGER.debug(
                            "Quellwert für Summenberechnung nicht gefunden",
                            extra={
                                "source": source,
                                "prefixed_source": prefixed_source,
                                "device": self.name,
                                "verfügbare_register": list(self._register_data.keys())
                            }
                        )
                        return None
                    values.append(value)
                return sum(values)

            elif calc_type == "mapping":
                # Wende eine Mapping-Tabelle auf den Quellwert an
                source = calculation.get("source")
                # Verwende den Helper für die präfixierten Namen
                prefixed_source = self.name_helper.convert(source, NameType.BASE_NAME)
                source_value = self._register_data.get(prefixed_source)
                
                if source_value is None:
                    _LOGGER.debug(
                        "Quellwert für Mapping nicht gefunden",
                        extra={
                            "source": source,
                            "prefixed_source": prefixed_source,
                            "device": self.name,
                            "verfügbare_register": list(self._register_data.keys())
                        }
                    )
                    return None
                    
                # Konvertiere den Wert in einen Hex-String
                hex_code = f"0x{int(source_value):04X}"
                map_name = calculation.get("map")
                mapping = self._device_config.get(map_name, {})
                return mapping.get(hex_code, f"Unknown code: {hex_code}")

            elif calc_type == "conditional":
                # Bedingter Wert basierend auf einer Quelle
                source = calculation.get("source")
                condition = calculation.get("condition")
                # Verwende den Helper für die präfixierten Namen
                prefixed_source = self.name_helper.convert(source, NameType.BASE_NAME)
                source_value = self._register_data.get(prefixed_source)
                
                if source_value is None:
                    _LOGGER.debug(
                        "Quellwert für Bedingung nicht gefunden",
                        extra={
                            "source": source,
                            "prefixed_source": prefixed_source,
                            "device": self.name,
                            "verfügbare_register": list(self._register_data.keys())
                        }
                    )
                    return None
                    
                if condition == "positive" and source_value > 0:
                    return source_value
                elif condition == "negative" and source_value < 0:
                    return abs(source_value) if calculation.get("absolute", False) else source_value
                return 0

            elif calc_type == "formula":
                formula = calculation.get("formula", "")
                if not formula:
                    _LOGGER.error(
                        "Keine Formel definiert",
                        extra={
                            "register": register_def.get("name"),
                            "device": self.name
                        }
                    )
                    return None
                
                _LOGGER.debug(
                    "Verarbeite Formel",
                    extra={
                        "original_formula": formula,
                        "device": self.name
                    }
                )
                
                import re
                variables = {}
                # Finde alle Variablen in der Formel (Wörter ohne mathematische Operatoren)
                var_names = re.findall(r'\b[a-zA-Z_]\w*\b', formula)
                
                # Erstelle ein Mapping von Original-Variablennamen zu präfixierten Namen
                var_mapping = {}
                for var in var_names:
                    # Ignoriere mathematische Funktionen
                    if var in ['abs', 'min', 'max', 'round']:
                        continue
                        
                    # Konvertiere den Variablennamen
                    prefixed_var = self.name_helper.convert(var, NameType.BASE_NAME)
                    var_mapping[var] = prefixed_var
                    
                    # Hole den Wert aus den Register-Daten
                    value = self._register_data.get(prefixed_var)
                    if value is None:
                        _LOGGER.debug(
                            "Wert für Variable nicht gefunden",
                            extra={
                                "original_var": var,
                                "prefixed_var": prefixed_var,
                                "formula": formula,
                                "device": self.name,
                                "verfügbare_register": list(self._register_data.keys())
                            }
                        )
                        return None
                        
                    variables[var] = float(value)
                
                _LOGGER.debug(
                    "Variablen für Formel vorbereitet",
                    extra={
                        "formula": formula,
                        "var_mapping": var_mapping,
                        "variables": variables,
                        "device": self.name
                    }
                )
                
                # Evaluiere die Formel
                try:
                    result = eval(formula, {"__builtins__": None}, variables)
                    return float(result)
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Formelevaluierung",
                        extra={
                            "error": str(e),
                            "formula": formula,
                            "variables": variables,
                            "device": self.name
                        }
                    )
                    return None

            return None

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Berechnung des Register-Werts",
                extra={
                    "error": str(e),
                    "register": register_def.get("name"),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Aktualisiert die Gerätedaten."""
        try:
            _LOGGER.debug(
                "Starte Datenaktualisierung",
                extra={
                    "device": self.name,
                    "register_count": len(self._registers) if self._registers else 0
                }
            )

            # Hole die Register-Werte
            data = await self._hub._read_registers(self._registers)
            
            _LOGGER.debug(
                "Datenaktualisierung abgeschlossen",
                extra={
                    "device": self.name,
                    "verfügbare_register": list(data.keys()),
                    "register_werte": data
                }
            )
            
            return data
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Datenaktualisierung",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return {}

    async def test_helper_entities(self) -> bool:
        """Testet die Funktionalität der Helper-Entities."""
        try:
            _LOGGER.info(
                "Starte Test der Helper-Entities",
                extra={
                    "device": self.name
                }
            )

            # Test der Input Number Entities
            if "input_number" in self._device_config:
                for input_id, config in self._device_config["input_number"].items():
                    try:
                        # Hole die Entity
                        entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="number")
                        entity = self.entities.get(entity_id)
                        
                        if not entity:
                            _LOGGER.error(
                                "Input Number Entity nicht gefunden",
                                extra={
                                    "input_id": input_id,
                                    "entity_id": entity_id,
                                    "device": self.name
                                }
                            )
                            return False
                        
                        # Teste Schreibzugriff mit Minimal- und Maximalwert
                        min_value = float(config.get("min", 0))
                        max_value = float(config.get("max", 100))
                        test_values = [min_value, max_value, (min_value + max_value) / 2]
                        
                        for value in test_values:
                            _LOGGER.debug(
                                "Teste Input Number mit Wert",
                                extra={
                                    "entity_id": entity_id,
                                    "value": value,
                                    "device": self.name
                                }
                            )
                            
                            await entity.async_set_native_value(value)
                            
                            # Prüfe ob der Wert im Register angekommen ist
                            register_name = config.get("register", {}).get("name")
                            if register_name:
                                register_value = self._register_data.get(register_name)
                                if register_value is None:
                                    _LOGGER.error(
                                        "Register-Wert nicht gefunden",
                                        extra={
                                            "register": register_name,
                                            "entity_id": entity_id,
                                            "device": self.name
                                        }
                                    )
                                    return False
                            
                            _LOGGER.debug(
                                "Input Number Test erfolgreich",
                                extra={
                                    "entity_id": entity_id,
                                    "value": value,
                                    "register_value": register_value,
                                    "device": self.name
                                }
                            )

            # Test der Input Select Entities
            if "input_select" in self._device_config:
                for input_id, config in self._device_config["input_select"].items():
                    try:
                        # Hole die Entity
                        entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="select")
                        entity = self.entities.get(entity_id)
                        
                        if not entity:
                            _LOGGER.error(
                                "Input Select Entity nicht gefunden",
                                extra={
                                    "input_id": input_id,
                                    "entity_id": entity_id,
                                    "device": self.name
                                }
                            )
                            return False
                        
                        # Teste alle verfügbaren Optionen
                        options = config.get("options", [])
                        for option in options:
                            _LOGGER.debug(
                                "Teste Input Select mit Option",
                                extra={
                                    "entity_id": entity_id,
                                    "option": option,
                                    "device": self.name
                                }
                            )
                            
                            await entity.async_select_option(option)
                            
                            # Prüfe ob der Wert im Register angekommen ist
                            register_name = config.get("register", {}).get("name")
                            if register_name:
                                register_value = self._register_data.get(register_name)
                                if register_value is None:
                                    _LOGGER.error(
                                        "Register-Wert nicht gefunden",
                                        extra={
                                            "register": register_name,
                                            "entity_id": entity_id,
                                            "device": self.name
                                        }
                                    )
                                    return False
                            
                            _LOGGER.debug(
                                "Input Select Test erfolgreich",
                                extra={
                                    "entity_id": entity_id,
                                    "option": option,
                                    "register_value": register_value,
                                    "device": self.name
                                }
                            )

            _LOGGER.info(
                "Alle Helper-Entity Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name,
                    "input_numbers": len(self._device_config.get("input_number", {})),
                    "input_selects": len(self._device_config.get("input_select", {}))
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Testen der Helper-Entities",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def test_service_calls(self) -> bool:
        """Testet die Service-Aufrufe mit den Helper-Entities."""
        try:
            _LOGGER.info(
                "Starte Test der Service-Aufrufe",
                extra={
                    "device": self.name
                }
            )

            # Test: Batteriemodus
            battery_modes = {
                "forced_discharge": {"power": 2500},
                "forced_charge": {"power": 3000},
                "bypass": {},
                "self_consumption": {}
            }

            for mode, params in battery_modes.items():
                _LOGGER.debug(
                    "Teste Batteriemodus",
                    extra={
                        "mode": mode,
                        "params": params,
                        "device": self.name
                    }
                )
                
                success = await self.set_battery_mode(mode, params.get("power"))
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen des Batteriemodus",
                        extra={
                            "mode": mode,
                            "params": params,
                            "device": self.name
                        }
                    )
                    return False

            # Test: Wechselrichter-Modi
            inverter_modes = ["Enabled", "Shutdown"]
            for mode in inverter_modes:
                _LOGGER.debug(
                    "Teste Wechselrichter-Modus",
                    extra={
                        "mode": mode,
                        "device": self.name
                    }
                )
                
                success = await self.set_inverter_mode(mode)
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen des Wechselrichter-Modus",
                        extra={
                            "mode": mode,
                            "device": self.name
                        }
                    )
                    return False

            # Test: Einspeiselimitierung
            export_power_tests = [
                {"enabled": True, "limit": 5000},
                {"enabled": False, "limit": None},
                {"enabled": True, "limit": 10000}
            ]

            for test in export_power_tests:
                _LOGGER.debug(
                    "Teste Einspeiselimitierung",
                    extra={
                        "config": test,
                        "device": self.name
                    }
                )
                
                success = await self.set_export_power_limit(test["enabled"], test["limit"])
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen der Einspeiselimitierung",
                        extra={
                            "config": test,
                            "device": self.name
                        }
                    )
                    return False

            # Validiere die Register-Werte nach den Tests
            validation_result = await self.validate_helper_entities()
            if not validation_result:
                _LOGGER.error(
                    "Validierung nach Service-Tests fehlgeschlagen",
                    extra={
                        "device": self.name
                    }
                )
                return False

            _LOGGER.info(
                "Alle Service-Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Testen der Service-Aufrufe",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def test_register_mappings(self) -> bool:
        """Führt End-to-End Tests der Register-Zuordnungen durch."""
        try:
            _LOGGER.info(
                "Starte End-to-End Tests der Register-Zuordnungen",
                extra={
                    "device": self.name
                }
            )

            # Test 1: Basis-Register
            if "registers" in self._device_config:
                for register_type in ["read", "write"]:
                    for register in self._device_config["registers"].get(register_type, []):
                        register_name = register.get("name")
                        if not register_name:
                            continue

                        # Teste Register-Zuordnung
                        prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                        
                        _LOGGER.debug(
                            "Teste Basis-Register",
                            extra={
                                "original_name": register_name,
                                "prefixed_name": prefixed_name,
                                "register_type": register_type,
                                "device": self.name
                            }
                        )

                        # Prüfe ob Register in den Daten existiert
                        if prefixed_name not in self._register_data:
                            _LOGGER.error(
                                "Register nicht in Daten gefunden",
                                extra={
                                    "register": register_name,
                                    "prefixed_name": prefixed_name,
                                    "device": self.name
                                }
                            )
                            return False

            # Test 2: Berechnete Register
            if "calculated_registers" in self._device_config:
                for calc_register in self._device_config["calculated_registers"]:
                    register_name = calc_register.get("name")
                    if not register_name:
                        continue

                    # Teste berechnetes Register
                    prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                    calculation = calc_register.get("calculation", {})
                    
                    _LOGGER.debug(
                        "Teste berechnetes Register",
                        extra={
                            "original_name": register_name,
                            "prefixed_name": prefixed_name,
                            "calculation_type": calculation.get("type"),
                            "device": self.name
                        }
                    )

                    # Prüfe Quell-Register für die Berechnung
                    if calculation.get("type") == "formula":
                        formula = calculation.get("formula", "")
                        import re
                        var_names = re.findall(r'\b[a-zA-Z_]\w*\b', formula)
                        
                        for var in var_names:
                            if var in ['abs', 'min', 'max', 'round']:
                                continue
                                
                            prefixed_var = self.name_helper.convert(var, NameType.BASE_NAME)
                            if prefixed_var not in self._register_data:
                                _LOGGER.error(
                                    "Quell-Register für Formel nicht gefunden",
                                    extra={
                                        "variable": var,
                                        "prefixed_variable": prefixed_var,
                                        "formula": formula,
                                        "device": self.name
                                    }
                                )
                                return False

                    # Berechne und validiere den Wert
                    value = self._calculate_register_value(calc_register)
                    if value is None:
                        _LOGGER.error(
                            "Berechnung fehlgeschlagen",
                            extra={
                                "register": register_name,
                                "calculation": calculation,
                                "device": self.name
                            }
                        )
                        return False

                    _LOGGER.debug(
                        "Berechnung erfolgreich",
                        extra={
                            "register": register_name,
                            "value": value,
                            "device": self.name
                        }
                    )

            # Test 3: Register-Entity Zuordnung
            for entity_id, entity in self.entities.items():
                if isinstance(entity, ModbusRegisterEntity):
                    register_name = entity._register.get("name")
                    if not register_name:
                        continue

                    prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                    
                    _LOGGER.debug(
                        "Teste Register-Entity Zuordnung",
                        extra={
                            "entity_id": entity_id,
                            "register": register_name,
                            "prefixed_name": prefixed_name,
                            "device": self.name
                        }
                    )

                    # Prüfe ob Entity korrekt aktualisiert wird
                    if not await self._update_entity_state(entity):
                        _LOGGER.error(
                            "Entity-Aktualisierung fehlgeschlagen",
                            extra={
                                "entity_id": entity_id,
                                "register": register_name,
                                "device": self.name
                            }
                        )
                        return False

            _LOGGER.info(
                "End-to-End Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei End-to-End Tests",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def test_calculations(self) -> bool:
        """Testet die Berechnungsfunktionalität für Register."""
        try:
            _LOGGER.info(
                "Starte Test der Berechnungsfunktionalität",
                extra={
                    "device": self.name
                }
            )

            # Test 1: Formelauswertung
            if "calculated_registers" in self._device_config:
                for calc_register in self._device_config["calculated_registers"]:
                    register_name = calc_register.get("name")
                    calculation = calc_register.get("calculation", {})
                    
                    if calculation.get("type") == "formula":
                        formula = calculation.get("formula", "")
                        
                        _LOGGER.debug(
                            "Teste Formelberechnung",
                            extra={
                                "register": register_name,
                                "formula": formula,
                                "device": self.name
                            }
                        )

                        # Teste mit Test-Werten
                        test_values = {
                            "battery_level": 75.5,
                            "battery_state_of_health": 98.2,
                            "battery_power": 2500.0,
                            "grid_power": 1500.0
                        }

                        # Erstelle präfixierte Test-Werte
                        prefixed_test_values = {}
                        for key, value in test_values.items():
                            prefixed_key = self.name_helper.convert(key, NameType.BASE_NAME)
                            prefixed_test_values[prefixed_key] = value
                            self._register_data[prefixed_key] = value

                        # Berechne den Wert
                        value = self._calculate_register_value(calc_register)
                        if value is None:
                            _LOGGER.error(
                                "Formelberechnung fehlgeschlagen",
                                extra={
                                    "register": register_name,
                                    "formula": formula,
                                    "test_values": test_values,
                                    "device": self.name
                                }
                            )
                            return False

                        _LOGGER.debug(
                            "Formelberechnung erfolgreich",
                            extra={
                                "register": register_name,
                                "formula": formula,
                                "result": value,
                                "test_values": test_values,
                                "device": self.name
                            }
                        )

            # Test 2: Datentyp-Konvertierung
            test_cases = [
                {"type": "uint16", "value": 65535, "expected": 65535},
                {"type": "int16", "value": -32768, "expected": -32768},
                {"type": "uint32", "value": 4294967295, "expected": 4294967295},
                {"type": "int32", "value": -2147483648, "expected": -2147483648},
                {"type": "float32", "value": 3.14159, "expected": 3.14159}
            ]

            for test in test_cases:
                register_def = {
                    "name": f"test_{test['type']}",
                    "type": test["type"]
                }
                
                _LOGGER.debug(
                    "Teste Datentyp-Konvertierung",
                    extra={
                        "type": test["type"],
                        "value": test["value"],
                        "expected": test["expected"],
                        "device": self.name
                    }
                )

                # Teste Konvertierung
                result = self._process_register_value(register_def["name"], register_def, test["value"])
                if result != test["expected"]:
                    _LOGGER.error(
                        "Datentyp-Konvertierung fehlgeschlagen",
                        extra={
                            "type": test["type"],
                            "value": test["value"],
                            "expected": test["expected"],
                            "result": result,
                            "device": self.name
                        }
                    )
                    return False

            # Test 3: Skalierungsfaktoren
            scale_tests = [
                {"scale": 0.1, "value": 100, "expected": 10.0},
                {"scale": 10, "value": 50, "expected": 500.0},
                {"scale": 0.001, "value": 1000, "expected": 1.0}
            ]

            for test in scale_tests:
                register_def = {
                    "name": "test_scale",
                    "type": "uint16",
                    "scale": test["scale"]
                }
                
                _LOGGER.debug(
                    "Teste Skalierungsfaktor",
                    extra={
                        "scale": test["scale"],
                        "value": test["value"],
                        "expected": test["expected"],
                        "device": self.name
                    }
                )

                # Teste Skalierung
                result = self._process_register_value(register_def["name"], register_def, test["value"])
                if abs(result - test["expected"]) > 0.0001:  # Berücksichtige Fließkomma-Ungenauigkeit
                    _LOGGER.error(
                        "Skalierung fehlgeschlagen",
                        extra={
                            "scale": test["scale"],
                            "value": test["value"],
                            "expected": test["expected"],
                            "result": result,
                            "device": self.name
                        }
                    )
                    return False

            _LOGGER.info(
                "Alle Berechnungstests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei Berechnungstests",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _async_update_data(self) -> Dict[str, Any]:
        """Aktualisiert die Gerätedaten."""
        try:
            _LOGGER.debug(
                "Starte Datenaktualisierung",
                extra={
                    "device": self.name,
                    "register_count": len(self._registers) if self._registers else 0
                }
            )

            # Hole die Register-Werte
            data = await self._hub._read_registers(self._registers)
            
            _LOGGER.debug(
                "Datenaktualisierung abgeschlossen",
                extra={
                    "device": self.name,
                    "verfügbare_register": list(data.keys()),
                    "register_werte": data
                }
            )
            
            return data
            
        except Exception as e:
                _LOGGER.error(
                "Fehler bei der Datenaktualisierung",
                    extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return {}

    async def test_helper_entities(self) -> bool:
        """Testet die Funktionalität der Helper-Entities."""
        try:
            _LOGGER.info(
                "Starte Test der Helper-Entities",
                extra={
                    "device": self.name
                }
            )

            # Test der Input Number Entities
            if "input_number" in self._device_config:
                for input_id, config in self._device_config["input_number"].items():
                    try:
                        # Hole die Entity
                        entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="number")
                        entity = self.entities.get(entity_id)
                        
                        if not entity:
                            _LOGGER.error(
                                "Input Number Entity nicht gefunden",
                                extra={
                                    "input_id": input_id,
                                    "entity_id": entity_id,
                        "device": self.name
                    }
                )
                return False
                
                        # Teste Schreibzugriff mit Minimal- und Maximalwert
                        min_value = float(config.get("min", 0))
                        max_value = float(config.get("max", 100))
                        test_values = [min_value, max_value, (min_value + max_value) / 2]
                        
                        for value in test_values:
                            _LOGGER.debug(
                                "Teste Input Number mit Wert",
                                extra={
                                    "entity_id": entity_id,
                                    "value": value,
                                    "device": self.name
                                }
                            )
                            
                            await entity.async_set_native_value(value)
                            
                            # Prüfe ob der Wert im Register angekommen ist
                            register_name = config.get("register", {}).get("name")
                            if register_name:
                                register_value = self._register_data.get(register_name)
                                if register_value is None:
                                    _LOGGER.error(
                                        "Register-Wert nicht gefunden",
                                        extra={
                                            "register": register_name,
                                            "entity_id": entity_id,
                                            "device": self.name
                                        }
                                    )
                                    return False
                            
                            _LOGGER.debug(
                                "Input Number Test erfolgreich",
                                extra={
                                    "entity_id": entity_id,
                                    "value": value,
                                    "register_value": register_value,
                                    "device": self.name
                                }
                            )

            # Test der Input Select Entities
            if "input_select" in self._device_config:
                for input_id, config in self._device_config["input_select"].items():
                    try:
                        # Hole die Entity
                        entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="select")
                        entity = self.entities.get(entity_id)
                        
                        if not entity:
                            _LOGGER.error(
                                "Input Select Entity nicht gefunden",
                                extra={
                                    "input_id": input_id,
                                    "entity_id": entity_id,
                                    "device": self.name
                                }
                            )
                            return False
                        
                        # Teste alle verfügbaren Optionen
                        options = config.get("options", [])
                        for option in options:
                            _LOGGER.debug(
                                "Teste Input Select mit Option",
                                extra={
                                    "entity_id": entity_id,
                                    "option": option,
                                    "device": self.name
                                }
                            )
                            
                            await entity.async_select_option(option)
                            
                            # Prüfe ob der Wert im Register angekommen ist
                            register_name = config.get("register", {}).get("name")
                            if register_name:
                                register_value = self._register_data.get(register_name)
                                if register_value is None:
                                    _LOGGER.error(
                                        "Register-Wert nicht gefunden",
                                        extra={
                                            "register": register_name,
                                            "entity_id": entity_id,
                                            "device": self.name
                                        }
                                    )
                                    return False
                            
                            _LOGGER.debug(
                                "Input Select Test erfolgreich",
                                extra={
                                    "entity_id": entity_id,
                                    "option": option,
                                    "register_value": register_value,
                                    "device": self.name
                                }
                            )

            _LOGGER.info(
                "Alle Helper-Entity Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name,
                    "input_numbers": len(self._device_config.get("input_number", {})),
                    "input_selects": len(self._device_config.get("input_select", {}))
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Testen der Helper-Entities",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def test_service_calls(self) -> bool:
        """Testet die Service-Aufrufe mit den Helper-Entities."""
        try:
            _LOGGER.info(
                "Starte Test der Service-Aufrufe",
                extra={
                    "device": self.name
                }
            )

            # Test: Batteriemodus
            battery_modes = {
                "forced_discharge": {"power": 2500},
                "forced_charge": {"power": 3000},
                "bypass": {},
                "self_consumption": {}
            }

            for mode, params in battery_modes.items():
                _LOGGER.debug(
                    "Teste Batteriemodus",
                    extra={
                        "mode": mode,
                        "params": params,
                        "device": self.name
                    }
                )
                
                success = await self.set_battery_mode(mode, params.get("power"))
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen des Batteriemodus",
                        extra={
                            "mode": mode,
                            "params": params,
                            "device": self.name
                        }
                    )
                    return False

            # Test: Wechselrichter-Modi
            inverter_modes = ["Enabled", "Shutdown"]
            for mode in inverter_modes:
                _LOGGER.debug(
                    "Teste Wechselrichter-Modus",
                    extra={
                        "mode": mode,
                        "device": self.name
                    }
                )
                
                success = await self.set_inverter_mode(mode)
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen des Wechselrichter-Modus",
                        extra={
                            "mode": mode,
                            "device": self.name
                        }
                    )
                    return False

            # Test: Einspeiselimitierung
            export_power_tests = [
                {"enabled": True, "limit": 5000},
                {"enabled": False, "limit": None},
                {"enabled": True, "limit": 10000}
            ]

            for test in export_power_tests:
                _LOGGER.debug(
                    "Teste Einspeiselimitierung",
                    extra={
                        "config": test,
                        "device": self.name
                    }
                )
                
                success = await self.set_export_power_limit(test["enabled"], test["limit"])
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen der Einspeiselimitierung",
                        extra={
                            "config": test,
                            "device": self.name
                        }
                    )
                    return False

            # Validiere die Register-Werte nach den Tests
            validation_result = await self.validate_helper_entities()
            if not validation_result:
                _LOGGER.error(
                    "Validierung nach Service-Tests fehlgeschlagen",
                    extra={
                        "device": self.name
                    }
                )
                return False

            _LOGGER.info(
                "Alle Service-Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Testen der Service-Aufrufe",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def test_register_mappings(self) -> bool:
        """Führt End-to-End Tests der Register-Zuordnungen durch."""
        try:
            _LOGGER.info(
                "Starte End-to-End Tests der Register-Zuordnungen",
                extra={
                    "device": self.name
                }
            )

            # Test 1: Basis-Register
            if "registers" in self._device_config:
                for register_type in ["read", "write"]:
                    for register in self._device_config["registers"].get(register_type, []):
            register_name = register.get("name")
            if not register_name:
                            continue

                        # Teste Register-Zuordnung
                        prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                        
                        _LOGGER.debug(
                            "Teste Basis-Register",
                            extra={
                                "original_name": register_name,
                                "prefixed_name": prefixed_name,
                                "register_type": register_type,
                                "device": self.name
                            }
                        )

                        # Prüfe ob Register in den Daten existiert
                        if prefixed_name not in self._register_data:
                _LOGGER.error(
                                "Register nicht in Daten gefunden",
                    extra={
                                    "register": register_name,
                                    "prefixed_name": prefixed_name,
                        "device": self.name
                    }
                )
                return False
                
            # Test 2: Berechnete Register
            if "calculated_registers" in self._device_config:
                for calc_register in self._device_config["calculated_registers"]:
                    register_name = calc_register.get("name")
                    if not register_name:
                        continue

                    # Teste berechnetes Register
                    prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                    calculation = calc_register.get("calculation", {})
                    
                    _LOGGER.debug(
                        "Teste berechnetes Register",
                        extra={
                            "original_name": register_name,
                            "prefixed_name": prefixed_name,
                            "calculation_type": calculation.get("type"),
                            "device": self.name
                        }
                    )

                    # Prüfe Quell-Register für die Berechnung
                    if calculation.get("type") == "formula":
                        formula = calculation.get("formula", "")
                        import re
                        var_names = re.findall(r'\b[a-zA-Z_]\w*\b', formula)
                        
                        for var in var_names:
                            if var in ['abs', 'min', 'max', 'round']:
                                continue
                                
                            prefixed_var = self.name_helper.convert(var, NameType.BASE_NAME)
                            if prefixed_var not in self._register_data:
                                _LOGGER.error(
                                    "Quell-Register für Formel nicht gefunden",
                                    extra={
                                        "variable": var,
                                        "prefixed_variable": prefixed_var,
                                        "formula": formula,
                                        "device": self.name
                                    }
                                )
                                return False

                    # Berechne und validiere den Wert
                    value = self._calculate_register_value(calc_register)
                    if value is None:
                        _LOGGER.error(
                            "Berechnung fehlgeschlagen",
                            extra={
                                "register": register_name,
                                "calculation": calculation,
                                "device": self.name
                            }
                        )
                        return False

                    _LOGGER.debug(
                        "Berechnung erfolgreich",
                        extra={
                            "register": register_name,
                            "value": value,
                            "device": self.name
                        }
                    )

            # Test 3: Register-Entity Zuordnung
            for entity_id, entity in self.entities.items():
                if isinstance(entity, ModbusRegisterEntity):
                    register_name = entity._register.get("name")
                    if not register_name:
                        continue

                    prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                    
                    _LOGGER.debug(
                        "Teste Register-Entity Zuordnung",
                        extra={
                            "entity_id": entity_id,
                            "register": register_name,
                            "prefixed_name": prefixed_name,
                            "device": self.name
                        }
                    )

                    # Prüfe ob Entity korrekt aktualisiert wird
                    if not await self._update_entity_state(entity):
                        _LOGGER.error(
                            "Entity-Aktualisierung fehlgeschlagen",
                            extra={
                                "entity_id": entity_id,
                                "register": register_name,
                                "device": self.name
                            }
                        )
                        return False

            _LOGGER.info(
                "End-to-End Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei End-to-End Tests",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def test_calculations(self) -> bool:
        """Testet die Berechnungsfunktionalität für Register."""
        try:
            _LOGGER.info(
                "Starte Test der Berechnungsfunktionalität",
                extra={
                    "device": self.name
                }
            )

            # Test 1: Formelauswertung
            if "calculated_registers" in self._device_config:
                for calc_register in self._device_config["calculated_registers"]:
                    register_name = calc_register.get("name")
                    calculation = calc_register.get("calculation", {})
                    
                    if calculation.get("type") == "formula":
                        formula = calculation.get("formula", "")
                        
                        _LOGGER.debug(
                            "Teste Formelberechnung",
                            extra={
                                "register": register_name,
                                "formula": formula,
                                "device": self.name
                            }
                        )

                        # Teste mit Test-Werten
                        test_values = {
                            "battery_level": 75.5,
                            "battery_state_of_health": 98.2,
                            "battery_power": 2500.0,
                            "grid_power": 1500.0
                        }

                        # Erstelle präfixierte Test-Werte
                        prefixed_test_values = {}
                        for key, value in test_values.items():
                            prefixed_key = self.name_helper.convert(key, NameType.BASE_NAME)
                            prefixed_test_values[prefixed_key] = value
                            self._register_data[prefixed_key] = value

                        # Berechne den Wert
                        value = self._calculate_register_value(calc_register)
                if value is None:
                            _LOGGER.error(
                                "Formelberechnung fehlgeschlagen",
                                extra={
                                    "register": register_name,
                                    "formula": formula,
                                    "test_values": test_values,
                                    "device": self.name
                                }
                            )
                            return False

                    _LOGGER.debug(
                            "Formelberechnung erfolgreich",
                        extra={
                            "register": register_name,
                                "formula": formula,
                                "result": value,
                                "test_values": test_values,
                                "device": self.name
                            }
                        )

            # Test 2: Datentyp-Konvertierung
            test_cases = [
                {"type": "uint16", "value": 65535, "expected": 65535},
                {"type": "int16", "value": -32768, "expected": -32768},
                {"type": "uint32", "value": 4294967295, "expected": 4294967295},
                {"type": "int32", "value": -2147483648, "expected": -2147483648},
                {"type": "float32", "value": 3.14159, "expected": 3.14159}
            ]

            for test in test_cases:
                register_def = {
                    "name": f"test_{test['type']}",
                    "type": test["type"]
                }
                
                _LOGGER.debug(
                    "Teste Datentyp-Konvertierung",
                    extra={
                        "type": test["type"],
                        "value": test["value"],
                        "expected": test["expected"],
                        "device": self.name
                    }
                )

                # Teste Konvertierung
                result = self._process_register_value(register_def["name"], register_def, test["value"])
                if result != test["expected"]:
                    _LOGGER.error(
                        "Datentyp-Konvertierung fehlgeschlagen",
                        extra={
                            "type": test["type"],
                            "value": test["value"],
                            "expected": test["expected"],
                            "result": result,
                            "device": self.name
                        }
                    )
                    return False
                    
            # Test 3: Skalierungsfaktoren
            scale_tests = [
                {"scale": 0.1, "value": 100, "expected": 10.0},
                {"scale": 10, "value": 50, "expected": 500.0},
                {"scale": 0.001, "value": 1000, "expected": 1.0}
            ]

            for test in scale_tests:
                register_def = {
                    "name": "test_scale",
                    "type": "uint16",
                    "scale": test["scale"]
                }
                
                _LOGGER.debug(
                    "Teste Skalierungsfaktor",
                    extra={
                        "scale": test["scale"],
                        "value": test["value"],
                        "expected": test["expected"],
                        "device": self.name
                    }
                )

                # Teste Skalierung
                result = self._process_register_value(register_def["name"], register_def, test["value"])
                if abs(result - test["expected"]) > 0.0001:  # Berücksichtige Fließkomma-Ungenauigkeit
                    _LOGGER.error(
                        "Skalierung fehlgeschlagen",
                        extra={
                            "scale": test["scale"],
                            "value": test["value"],
                            "expected": test["expected"],
                            "result": result,
                            "device": self.name
                        }
                    )
                    return False

            _LOGGER.info(
                "Alle Berechnungstests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
                return True
                
            except Exception as e:
                _LOGGER.error(
                "Fehler bei Berechnungstests",
                    extra={
                        "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _async_update_data(self) -> Dict[str, Any]:
        """Aktualisiert die Gerätedaten."""
        try:
            _LOGGER.debug(
                "Starte Datenaktualisierung",
                extra={
                    "device": self.name,
                    "register_count": len(self._registers) if self._registers else 0
                }
            )

            # Hole die Register-Werte
            data = await self._hub._read_registers(self._registers)
            
            _LOGGER.debug(
                "Datenaktualisierung abgeschlossen",
                extra={
                    "device": self.name,
                    "verfügbare_register": list(data.keys()),
                    "register_werte": data
                }
            )
            
            return data
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Datenaktualisierung",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return {}

    async def test_helper_entities(self) -> bool:
        """Testet die Funktionalität der Helper-Entities."""
        try:
            _LOGGER.info(
                "Starte Test der Helper-Entities",
                extra={
                    "device": self.name
                }
            )

            # Test der Input Number Entities
            if "input_number" in self._device_config:
                for input_id, config in self._device_config["input_number"].items():
                    try:
                        # Hole die Entity
                        entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="number")
                        entity = self.entities.get(entity_id)
                        
                        if not entity:
                            _LOGGER.error(
                                "Input Number Entity nicht gefunden",
                                extra={
                                    "input_id": input_id,
                                    "entity_id": entity_id,
                                    "device": self.name
                                }
                            )
                            return False
                        
                        # Teste Schreibzugriff mit Minimal- und Maximalwert
                        min_value = float(config.get("min", 0))
                        max_value = float(config.get("max", 100))
                        test_values = [min_value, max_value, (min_value + max_value) / 2]
                        
                        for value in test_values:
                            _LOGGER.debug(
                                "Teste Input Number mit Wert",
                                extra={
                                    "entity_id": entity_id,
                                    "value": value,
                                    "device": self.name
                                }
                            )
                            
                            await entity.async_set_native_value(value)
                            
                            # Prüfe ob der Wert im Register angekommen ist
                            register_name = config.get("register", {}).get("name")
                            if register_name:
                                register_value = self._register_data.get(register_name)
                                if register_value is None:
                                    _LOGGER.error(
                                        "Register-Wert nicht gefunden",
                                        extra={
                        "register": register_name,
                                            "entity_id": entity_id,
                                            "device": self.name
                                        }
                                    )
                                    return False
                            
                            _LOGGER.debug(
                                "Input Number Test erfolgreich",
                                extra={
                                    "entity_id": entity_id,
                                    "value": value,
                                    "register_value": register_value,
                                    "device": self.name
                                }
                            )

            # Test der Input Select Entities
            if "input_select" in self._device_config:
                for input_id, config in self._device_config["input_select"].items():
                    try:
                        # Hole die Entity
                        entity_id = self.name_helper.convert(input_id, NameType.ENTITY_ID, domain="select")
                        entity = self.entities.get(entity_id)
                        
                        if not entity:
                            _LOGGER.error(
                                "Input Select Entity nicht gefunden",
                                extra={
                                    "input_id": input_id,
                                    "entity_id": entity_id,
                                    "device": self.name
                                }
                            )
                            return False
                        
                        # Teste alle verfügbaren Optionen
                        options = config.get("options", [])
                        for option in options:
                            _LOGGER.debug(
                                "Teste Input Select mit Option",
                                extra={
                                    "entity_id": entity_id,
                                    "option": option,
                                    "device": self.name
                                }
                            )
                            
                            await entity.async_select_option(option)
                            
                            # Prüfe ob der Wert im Register angekommen ist
                            register_name = config.get("register", {}).get("name")
                            if register_name:
                                register_value = self._register_data.get(register_name)
                                if register_value is None:
                                    _LOGGER.error(
                                        "Register-Wert nicht gefunden",
                                        extra={
                                            "register": register_name,
                                            "entity_id": entity_id,
                                            "device": self.name
                                        }
                                    )
                                    return False
                            
                            _LOGGER.debug(
                                "Input Select Test erfolgreich",
                                extra={
                                    "entity_id": entity_id,
                                    "option": option,
                                    "register_value": register_value,
                                    "device": self.name
                                }
                            )

            _LOGGER.info(
                "Alle Helper-Entity Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name,
                    "input_numbers": len(self._device_config.get("input_number", {})),
                    "input_selects": len(self._device_config.get("input_select", {}))
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Testen der Helper-Entities",
                extra={
                    "error": str(e),
                        "device": self.name,
                        "traceback": e.__traceback__
                    }
                )
                return False
            
    async def test_service_calls(self) -> bool:
        """Testet die Service-Aufrufe mit den Helper-Entities."""
        try:
            _LOGGER.info(
                "Starte Test der Service-Aufrufe",
                extra={
                    "device": self.name
                }
            )

            # Test: Batteriemodus
            battery_modes = {
                "forced_discharge": {"power": 2500},
                "forced_charge": {"power": 3000},
                "bypass": {},
                "self_consumption": {}
            }

            for mode, params in battery_modes.items():
                _LOGGER.debug(
                    "Teste Batteriemodus",
                    extra={
                        "mode": mode,
                        "params": params,
                        "device": self.name
                    }
                )
                
                success = await self.set_battery_mode(mode, params.get("power"))
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen des Batteriemodus",
                        extra={
                            "mode": mode,
                            "params": params,
                            "device": self.name
                        }
                    )
                    return False

            # Test: Wechselrichter-Modi
            inverter_modes = ["Enabled", "Shutdown"]
            for mode in inverter_modes:
                _LOGGER.debug(
                    "Teste Wechselrichter-Modus",
                    extra={
                        "mode": mode,
                        "device": self.name
                    }
                )
                
                success = await self.set_inverter_mode(mode)
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen des Wechselrichter-Modus",
                        extra={
                            "mode": mode,
                            "device": self.name
                        }
                    )
                    return False

            # Test: Einspeiselimitierung
            export_power_tests = [
                {"enabled": True, "limit": 5000},
                {"enabled": False, "limit": None},
                {"enabled": True, "limit": 10000}
            ]

            for test in export_power_tests:
                _LOGGER.debug(
                    "Teste Einspeiselimitierung",
                    extra={
                        "config": test,
                        "device": self.name
                    }
                )
                
                success = await self.set_export_power_limit(test["enabled"], test["limit"])
                if not success:
                    _LOGGER.error(
                        "Fehler beim Setzen der Einspeiselimitierung",
                        extra={
                            "config": test,
                            "device": self.name
                        }
                    )
                    return False

            # Validiere die Register-Werte nach den Tests
            validation_result = await self.validate_helper_entities()
            if not validation_result:
                _LOGGER.error(
                    "Validierung nach Service-Tests fehlgeschlagen",
                    extra={
                        "device": self.name
                    }
                )
                return False

            _LOGGER.info(
                "Alle Service-Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Testen der Service-Aufrufe",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def test_register_mappings(self) -> bool:
        """Führt End-to-End Tests der Register-Zuordnungen durch."""
        try:
            _LOGGER.info(
                "Starte End-to-End Tests der Register-Zuordnungen",
                extra={
                    "device": self.name
                }
            )

            # Test 1: Basis-Register
            if "registers" in self._device_config:
                for register_type in ["read", "write"]:
                    for register in self._device_config["registers"].get(register_type, []):
                        register_name = register.get("name")
                        if not register_name:
                            continue

                        # Teste Register-Zuordnung
                        prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                        
                        _LOGGER.debug(
                            "Teste Basis-Register",
                            extra={
                                "original_name": register_name,
                                "prefixed_name": prefixed_name,
                                "register_type": register_type,
                                "device": self.name
                            }
                        )

                        # Prüfe ob Register in den Daten existiert
                        if prefixed_name not in self._register_data:
                            _LOGGER.error(
                                "Register nicht in Daten gefunden",
                                extra={
                                    "register": register_name,
                                    "prefixed_name": prefixed_name,
                                    "device": self.name
                                }
                            )
                            return False

            # Test 2: Berechnete Register
            if "calculated_registers" in self._device_config:
                for calc_register in self._device_config["calculated_registers"]:
                    register_name = calc_register.get("name")
                    if not register_name:
                        continue

                    # Teste berechnetes Register
                    prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                    calculation = calc_register.get("calculation", {})
                    
                    _LOGGER.debug(
                        "Teste berechnetes Register",
                        extra={
                            "original_name": register_name,
                            "prefixed_name": prefixed_name,
                            "calculation_type": calculation.get("type"),
                            "device": self.name
                        }
                    )

                    # Prüfe Quell-Register für die Berechnung
                    if calculation.get("type") == "formula":
                        formula = calculation.get("formula", "")
                        import re
                        var_names = re.findall(r'\b[a-zA-Z_]\w*\b', formula)
                        
                        for var in var_names:
                            if var in ['abs', 'min', 'max', 'round']:
                                continue
                                
                            prefixed_var = self.name_helper.convert(var, NameType.BASE_NAME)
                            if prefixed_var not in self._register_data:
                                _LOGGER.error(
                                    "Quell-Register für Formel nicht gefunden",
                                    extra={
                                        "variable": var,
                                        "prefixed_variable": prefixed_var,
                                        "formula": formula,
                                        "device": self.name
                                    }
                                )
                                return False

                    # Berechne und validiere den Wert
                    value = self._calculate_register_value(calc_register)
                    if value is None:
                        _LOGGER.error(
                            "Berechnung fehlgeschlagen",
                            extra={
                                "register": register_name,
                                "calculation": calculation,
                                "device": self.name
                            }
                        )
                        return False

                    _LOGGER.debug(
                        "Berechnung erfolgreich",
                        extra={
                            "register": register_name,
                            "value": value,
                            "device": self.name
                        }
                    )

            # Test 3: Register-Entity Zuordnung
            for entity_id, entity in self.entities.items():
                if isinstance(entity, ModbusRegisterEntity):
                    register_name = entity._register.get("name")
                    if not register_name:
                        continue

                    prefixed_name = self.name_helper.convert(register_name, NameType.BASE_NAME)
                    
                    _LOGGER.debug(
                        "Teste Register-Entity Zuordnung",
                        extra={
                            "entity_id": entity_id,
                            "register": register_name,
                            "prefixed_name": prefixed_name,
                            "device": self.name
                        }
                    )

                    # Prüfe ob Entity korrekt aktualisiert wird
                    if not await self._update_entity_state(entity):
                        _LOGGER.error(
                            "Entity-Aktualisierung fehlgeschlagen",
                            extra={
                                "entity_id": entity_id,
                                "register": register_name,
                                "device": self.name
                            }
                        )
                        return False

            _LOGGER.info(
                "End-to-End Tests erfolgreich abgeschlossen",
                extra={
                    "device": self.name
                }
            )
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei End-to-End Tests",
                extra={
                    "error": str(e),
                    "device": self.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def test_calculations(self) -> bool:
        """Testet die Berechnungsfunktionalität für Register."""
        try:
            _LOGGER.info(
                "Starte Test der Berechnungsfunktionalität",
                extra={
                    "device": self.name
                }
            )

            # Test 1: Formelauswertung
            if "calculated_registers" in self._device_config:
                for calc_register in self._device_config["calculated_registers"]:
                    register_name = calc_register.get("name")
                    calculation = calc_register.get("calculation", {})
                    
                    if calculation.get("type") == "formula":
                        formula = calculation.get("formula", "")
                        
                        _LOGGER.debug(
                            "Teste Formelberechnung",
                            extra={
                                "register": register_name,
                                "formula": formula,
                                "device": self.name
                            }
                        )

                        # Teste mit Test-Werten
                        test_values = {
                            "battery_level": 75.5,
