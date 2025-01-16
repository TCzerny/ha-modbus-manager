"""Modbus Manager Test Suite."""
from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant

from .const import DOMAIN, NameType
from .logger import ModbusManagerLogger
from .device_base import ModbusManagerDeviceBase
from .device_registers import ModbusManagerRegisterProcessor
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
        """Initialisiert die Test Suite."""
        try:
            self._hass = hass
            self._device = device
            self._register_processor = register_processor
            self._entity_manager = entity_manager
            self._service_handler = service_handler
            self._calculator = calculator
            
            self._test_results: Dict[str, Dict[str, Any]] = {}
            
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

    async def run_register_tests(self) -> Tuple[bool, Dict[str, Any]]:
        """Führt Tests für die Register-Verarbeitung durch."""
        try:
            results = {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "details": []
            }
            
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

    def get_test_results(self) -> Dict[str, Any]:
        """Gibt die Ergebnisse aller Tests zurück."""
        return self._test_results.copy() 