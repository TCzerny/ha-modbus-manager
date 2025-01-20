"""Modbus Manager Test Suite."""
from __future__ import annotations

import logging
import asyncio
<<<<<<< HEAD
from typing import Any, Dict, List, Optional, Tuple, Set

from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
=======
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
>>>>>>> task/name_helpers_2025-01-16_1

from .const import DOMAIN, NameType
from .logger import ModbusManagerLogger
from .device_base import ModbusManagerDeviceBase
<<<<<<< HEAD
from .device_registers import ModbusManagerRegisterProcessor, TYPE_CONVERTERS
=======
from .device_registers import ModbusManagerRegisterProcessor
>>>>>>> task/name_helpers_2025-01-16_1
from .device_entities import ModbusManagerEntityManager
from .device_services import ModbusManagerServiceHandler
from .device_calculations import ModbusManagerCalculator

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerTestSuite:
    """Klasse für das Testen von Modbus-Geräten."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: ModbusManagerDeviceBase,
        register_processor: ModbusManagerRegisterProcessor,
        entity_manager: ModbusManagerEntityManager,
        service_handler: ModbusManagerServiceHandler,
        calculator: ModbusManagerCalculator,
    ) -> None:
<<<<<<< HEAD
        """Initialisiere die Test Suite."""
        try:
            self.hass = hass
=======
        """Initialisiert die Test Suite."""
        try:
            self._hass = hass
>>>>>>> task/name_helpers_2025-01-16_1
            self._device = device
            self._register_processor = register_processor
            self._entity_manager = entity_manager
            self._service_handler = service_handler
            self._calculator = calculator
            
<<<<<<< HEAD
            # Initialisiere die Testergebnisse
            self._test_results = {}
            self._register_test_results = {}
            
            _LOGGER.debug(
                "Test Suite initialisiert",
                extra={"device": device.name}
            )
=======
            self._test_results: Dict[str, Dict[str, Any]] = {}
>>>>>>> task/name_helpers_2025-01-16_1
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Initialisierung der Test Suite",
                extra={
                    "error": str(e),
                    "device": device.name,
                    "traceback": e.__traceback__
                }
            )
            raise

<<<<<<< HEAD
    def _validate_register_value(self, register: Dict[str, Any], value: Any) -> Tuple[bool, Optional[str]]:
        """Validiert einen Register-Wert basierend auf der Konfiguration."""
        try:
            # Prüfe ob der Wert existiert
            if value is None:
                return False, "Kein Wert verfügbar"
                
            # Prüfe Register-Typ
            reg_type = register.get("type", "uint16")
            if reg_type not in TYPE_CONVERTERS:
                return False, f"Ungültiger Register-Typ: {reg_type}"
                
            # Prüfe Wertebereich basierend auf Typ
            try:
                converted_value = TYPE_CONVERTERS[reg_type](value)
            except (ValueError, TypeError):
                return False, f"Wert {value} kann nicht in Typ {reg_type} konvertiert werden"
                
            # Prüfe Skalierung
            scale = float(register.get("scale", 1.0))
            try:
                scaled_value = float(converted_value) * scale
            except (ValueError, TypeError):
                return False, f"Skalierung fehlgeschlagen: {converted_value} * {scale}"
                
            return True, None
            
        except Exception as e:
            return False, str(e)

    def _validate_entity_attributes(self, entity: Any) -> Tuple[bool, List[str]]:
        """Validiert die Attribute einer Entity."""
        errors = []
        
        # Prüfe Pflicht-Attribute
        if not hasattr(entity, "unique_id"):
            errors.append("Unique ID fehlt")
        if not hasattr(entity, "name"):
            errors.append("Name fehlt")
            
        # Prüfe optionale Attribute
        if hasattr(entity, "device_class") and not isinstance(entity.device_class, str):
            errors.append("Ungültiger device_class Typ")
        if hasattr(entity, "unit_of_measurement") and not isinstance(entity.unit_of_measurement, str):
            errors.append("Ungültiger unit_of_measurement Typ")
            
        # Prüfe Device-Info
        if not hasattr(entity, "device_info") or not entity.device_info:
            errors.append("Device Info fehlt")
            
        return len(errors) == 0, errors

=======
>>>>>>> task/name_helpers_2025-01-16_1
    async def run_register_tests(self) -> Tuple[bool, Dict[str, Any]]:
        """Führt Tests für die Register-Verarbeitung durch."""
        try:
            results = {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "details": []
            }
            
<<<<<<< HEAD
            # Sammle alle Register-Adressen für Überlappungsprüfung
            used_addresses: Dict[str, Set[int]] = {
                "input": set(),
                "holding": set()
            }
            
            # Teste Register-Definitionen
            for interval, registers in self._register_processor.registers_by_interval.items():
                for register in registers:
                    results["total_tests"] += 1
                    test_result = {
                        "test": f"Register {register.get('name')}",
                        "interval": interval,
                        "checks": []
                    }
                    
                    # Prüfe Register-Adresse
                    address = register.get("address")
                    count = register.get("count", 1)
                    reg_type = register.get("register_type", "input")
                    
                    # Prüfe auf Überlappungen
                    address_range = set(range(address, address + count))
                    if address_range.intersection(used_addresses[reg_type]):
                        test_result["checks"].append({
                            "check": "address_overlap",
                            "status": "failed",
                            "message": f"Adresse {address} überlappt mit existierenden Registern"
                        })
                    else:
                        used_addresses[reg_type].update(address_range)
                        test_result["checks"].append({
                            "check": "address_overlap",
                            "status": "passed"
                        })
                    
                    # Prüfe Register-Wert
                    register_name = register.get("name")
                    if register_name:
                        value = self._register_processor.register_data.get(register_name)
                        is_valid, error = self._validate_register_value(register, value)
                        
                        if is_valid:
                            test_result["checks"].append({
                                "check": "value_validation",
                                "status": "passed",
                                "value": value
                            })
                        else:
                            test_result["checks"].append({
                                "check": "value_validation",
                                "status": "failed",
                                "error": error
                            })
                    
                    # Bewerte Gesamtergebnis des Register-Tests
                    failed_checks = [c for c in test_result["checks"] if c["status"] == "failed"]
                    if failed_checks:
                        results["failed_tests"] += 1
                        test_result["status"] = "failed"
                    else:
                        results["passed_tests"] += 1
                        test_result["status"] = "passed"
                        
                    results["details"].append(test_result)
=======
            # Teste Register-Definitionen
            register_data = self._register_processor.register_data
            for register_name, value in register_data.items():
                try:
                    results["total_tests"] += 1
                    
                    # Prüfe ob der Wert gültig ist
                    if value is not None:
                        results["passed_tests"] += 1
                        results["details"].append({
                            "test": f"Register {register_name}",
                            "status": "passed",
                            "value": value
                        })
                    else:
                        results["failed_tests"] += 1
                        results["details"].append({
                            "test": f"Register {register_name}",
                            "status": "failed",
                            "error": "Kein Wert verfügbar"
                        })
                        
                except Exception as e:
                    results["failed_tests"] += 1
                    results["details"].append({
                        "test": f"Register {register_name}",
                        "status": "error",
                        "error": str(e)
                    })
>>>>>>> task/name_helpers_2025-01-16_1
                    
            # Speichere die Ergebnisse
            self._test_results["register_tests"] = results
            
            return results["failed_tests"] == 0, results
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei den Register-Tests",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False, {"error": str(e)}

    async def run_entity_tests(self) -> Tuple[bool, Dict[str, Any]]:
        """Führt Tests für die Entity-Verwaltung durch."""
        try:
            results = {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "details": []
            }
            
<<<<<<< HEAD
            # Sammle alle Entity-IDs für Duplikat-Prüfung
            entity_ids = set()
            
            # Teste Entity-Zustände
            for entity_id, entity in self._entity_manager.entities.items():
                results["total_tests"] += 1
                test_result = {
                    "test": f"Entity {entity_id}",
                    "checks": []
                }
                
                # Prüfe auf doppelte Entity-IDs
                if entity_id in entity_ids:
                    test_result["checks"].append({
                        "check": "unique_id",
                        "status": "failed",
                        "error": "Doppelte Entity-ID gefunden"
                    })
                else:
                    entity_ids.add(entity_id)
                    test_result["checks"].append({
                        "check": "unique_id",
                        "status": "passed"
                    })
                
                # Prüfe Entity-Attribute
                is_valid, errors = self._validate_entity_attributes(entity)
                if is_valid:
                    test_result["checks"].append({
                        "check": "attributes",
                        "status": "passed"
                    })
                else:
                    test_result["checks"].append({
                        "check": "attributes",
                        "status": "failed",
                        "errors": errors
                    })
                
                # Prüfe Entity-Zustand
                if hasattr(entity, "_attr_native_value"):
                    test_result["checks"].append({
                        "check": "state",
                        "status": "passed",
                        "value": entity._attr_native_value
                    })
                else:
                    test_result["checks"].append({
                        "check": "state",
                        "status": "failed",
                        "error": "Kein Zustand verfügbar"
                    })
                
                # Bewerte Gesamtergebnis des Entity-Tests
                failed_checks = [c for c in test_result["checks"] if c["status"] == "failed"]
                if failed_checks:
                    results["failed_tests"] += 1
                    test_result["status"] = "failed"
                else:
                    results["passed_tests"] += 1
                    test_result["status"] = "passed"
                    
                results["details"].append(test_result)
=======
            # Teste Entity-Zustände
            for entity_id, entity in self._entity_manager.entities.items():
                try:
                    results["total_tests"] += 1
                    
                    # Prüfe ob die Entity einen Zustand hat
                    if hasattr(entity, "_attr_native_value"):
                        results["passed_tests"] += 1
                        results["details"].append({
                            "test": f"Entity {entity_id}",
                            "status": "passed",
                            "value": entity._attr_native_value
                        })
                    else:
                        results["failed_tests"] += 1
                        results["details"].append({
                            "test": f"Entity {entity_id}",
                            "status": "failed",
                            "error": "Kein Zustand verfügbar"
                        })
                        
                except Exception as e:
                    results["failed_tests"] += 1
                    results["details"].append({
                        "test": f"Entity {entity_id}",
                        "status": "error",
                        "error": str(e)
                    })
>>>>>>> task/name_helpers_2025-01-16_1
                    
            # Speichere die Ergebnisse
            self._test_results["entity_tests"] = results
            
            return results["failed_tests"] == 0, results
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei den Entity-Tests",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False, {"error": str(e)}

    async def run_calculation_tests(self) -> Tuple[bool, Dict[str, Any]]:
        """Führt Tests für die Berechnungen durch."""
        try:
            results = {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "details": []
            }
            
            # Teste Berechnungen
            register_data = self._register_processor.register_data
            calculated_values = await self._calculator.update_calculations(register_data)
            
            for calc_id, value in calculated_values.items():
                try:
                    results["total_tests"] += 1
                    
                    # Prüfe ob der berechnete Wert gültig ist
                    if value is not None:
                        results["passed_tests"] += 1
                        results["details"].append({
                            "test": f"Berechnung {calc_id}",
                            "status": "passed",
                            "value": value
                        })
                    else:
                        results["failed_tests"] += 1
                        results["details"].append({
                            "test": f"Berechnung {calc_id}",
                            "status": "failed",
                            "error": "Ungültiges Berechnungsergebnis"
                        })
                        
                except Exception as e:
                    results["failed_tests"] += 1
                    results["details"].append({
                        "test": f"Berechnung {calc_id}",
                        "status": "error",
                        "error": str(e)
                    })
                    
            # Speichere die Ergebnisse
            self._test_results["calculation_tests"] = results
            
            return results["failed_tests"] == 0, results
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei den Berechnungs-Tests",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False, {"error": str(e)}

    async def run_service_tests(self) -> Tuple[bool, Dict[str, Any]]:
        """Führt Tests für die Services durch."""
        try:
            results = {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "details": []
            }
            
            # Teste Service-Konfigurationen
            for service_id, service_config in self._service_handler._services.items():
                try:
                    results["total_tests"] += 1
                    
                    # Prüfe ob die Service-Konfiguration gültig ist
                    if self._service_handler._validate_service_config(service_id, service_config):
                        results["passed_tests"] += 1
                        results["details"].append({
                            "test": f"Service {service_id}",
                            "status": "passed",
                            "config": service_config
                        })
                    else:
                        results["failed_tests"] += 1
                        results["details"].append({
                            "test": f"Service {service_id}",
                            "status": "failed",
                            "error": "Ungültige Service-Konfiguration"
                        })
                        
                except Exception as e:
                    results["failed_tests"] += 1
                    results["details"].append({
                        "test": f"Service {service_id}",
                        "status": "error",
                        "error": str(e)
                    })
                    
            # Speichere die Ergebnisse
            self._test_results["service_tests"] = results
            
            return results["failed_tests"] == 0, results
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei den Service-Tests",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False, {"error": str(e)}

    async def run_all_tests(self) -> Tuple[bool, Dict[str, Any]]:
        """Führt alle Tests durch."""
        try:
            all_results = {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "test_suites": {}
            }
            
            # Führe alle Test-Suiten aus
            test_suites = [
                ("register_tests", self.run_register_tests),
                ("entity_tests", self.run_entity_tests),
                ("calculation_tests", self.run_calculation_tests),
                ("service_tests", self.run_service_tests)
            ]
            
            for suite_name, suite_func in test_suites:
                success, results = await suite_func()
                
                # Aktualisiere die Gesamtergebnisse
                all_results["total_tests"] += results.get("total_tests", 0)
                all_results["passed_tests"] += results.get("passed_tests", 0)
                all_results["failed_tests"] += results.get("failed_tests", 0)
                all_results["test_suites"][suite_name] = results
                
            # Logge die Gesamtergebnisse
            _LOGGER.info(
                "Test-Suite abgeschlossen",
                extra={
                    "total_tests": all_results["total_tests"],
                    "passed_tests": all_results["passed_tests"],
                    "failed_tests": all_results["failed_tests"],
                    "device": self._device.name
                }
            )
            
            return all_results["failed_tests"] == 0, all_results
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Ausführung der Test-Suite",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False, {"error": str(e)}

<<<<<<< HEAD
    async def get_test_results(self) -> Dict[str, Any]:
        """Gibt die Testergebnisse zurück."""
        try:
            if not hasattr(self, "_test_results"):
                return {}
                
            return self._test_results
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Abrufen der Testergebnisse",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return {} 
=======
    def get_test_results(self) -> Dict[str, Any]:
        """Gibt die Ergebnisse aller Tests zurück."""
        return self._test_results.copy() 
>>>>>>> task/name_helpers_2025-01-16_1
