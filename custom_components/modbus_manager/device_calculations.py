"""Modbus Manager Calculation Processing."""
from __future__ import annotations

from typing import Dict, Any, Optional, List
import asyncio
import ast
import operator

from .logger import ModbusManagerLogger
from .device_interfaces import IModbusManagerDevice
from .const import NameType

_LOGGER = ModbusManagerLogger(__name__)

class ModbusManagerCalculator:
    """Klasse für die Berechnung von Modbus-Registerwerten."""

    # Unterstützte Operatoren für Berechnungen
    _OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def __init__(
        self,
        device: IModbusManagerDevice,
    ) -> None:
        """Initialisiert den Calculator."""
        try:
            self._device = device
            self._calculations: Dict[str, Dict[str, Any]] = {}
            self._calculated_values: Dict[str, Any] = {}
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Initialisierung des Calculators",
                extra={
                    "error": str(e),
                    "device": device.name,
                    "traceback": e.__traceback__
                }
            )
            raise

    async def setup_calculations(self, calculation_definitions: Dict[str, Any]) -> None:
        """Richtet die Berechnungen basierend auf der Konfiguration ein."""
        try:
            # Hole die Berechnungs-Definitionen
            calculations = calculation_definitions.get("calculated_registers", {})
            
            # Verarbeite die Berechnungen
            for calc_id, calc_config in calculations.items():
                try:
                    # Validiere die Berechnungs-Konfiguration
                    if not self._validate_calculation_config(calc_id, calc_config):
                        continue
                        
                    # Speichere die Berechnungs-Konfiguration
                    self._calculations[calc_id] = calc_config
                    
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Einrichten einer Berechnung",
                        extra={
                            "error": str(e),
                            "calc_id": calc_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup der Berechnungen",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    def _validate_calculation_config(self, calc_id: str, calc_config: Dict[str, Any]) -> bool:
        """Validiert eine Berechnungs-Konfiguration."""
        try:
            # Prüfe ob alle erforderlichen Felder vorhanden sind
            required_fields = ["formula", "variables"]
            for field in required_fields:
                if field not in calc_config:
                    _LOGGER.error(
                        f"Pflichtfeld {field} fehlt in der Berechnungs-Konfiguration",
                        extra={
                            "calc_id": calc_id,
                            "device": self._device.name
                        }
                    )
                    return False
                    
            # Prüfe die Variablendefinitionen
            variables = calc_config["variables"]
            if not isinstance(variables, list):
                _LOGGER.error(
                    "Variables muss eine Liste sein",
                    extra={
                        "calc_id": calc_id,
                        "device": self._device.name
                    }
                )
                return False
                
            for var in variables:
                if not isinstance(var, dict) or "name" not in var or "source" not in var:
                    _LOGGER.error(
                        "Ungültige Variablendefinition",
                        extra={
                            "variable": var,
                            "calc_id": calc_id,
                            "device": self._device.name
                        }
                    )
                    return False
                    
            # Prüfe die Formel
            formula = calc_config["formula"]
            try:
                ast.parse(formula)
            except SyntaxError as e:
                _LOGGER.error(
                    "Ungültige Formel-Syntax",
                    extra={
                        "error": str(e),
                        "formula": formula,
                        "calc_id": calc_id,
                        "device": self._device.name,
                        "traceback": e.__traceback__
                    }
                )
                return False
                
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Validierung der Berechnungs-Konfiguration",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def update_calculations(self, register_data: Dict[str, Any]) -> Dict[str, Any]:
        """Aktualisiert alle Berechnungen."""
        try:
            results = {}
            
            for calc_id, calc_config in self._calculations.items():
                try:
                    # Sammle die Variablenwerte
                    variables = {}
                    for var in calc_config["variables"]:
                        var_name = var["name"]
                        var_source = var["source"]
                        
                        # Konvertiere den Quell-Namen
                        prefixed_source = self._device.name_helper.convert(var_source, NameType.BASE_NAME)
                        
                        # Hole den Wert
                        value = register_data.get(prefixed_source)
                        if value is None:
                            _LOGGER.debug(
                                "Kein Wert für Variable gefunden",
                                extra={
                                    "var_name": var_name,
                                    "var_source": var_source,
                                    "calc_id": calc_id,
                                    "device": self._device.name
                                }
                            )
                            continue
                            
                        variables[var_name] = value
                        
                    # Berechne den Wert
                    try:
                        result = await self.calculate_value(calc_config["formula"], variables)
                        if result is not None:
                            # Konvertiere den Berechnungs-Namen
                            prefixed_name = self._device.name_helper.convert(calc_id, NameType.BASE_NAME)
                            results[prefixed_name] = result
                            
                    except Exception as e:
                        _LOGGER.error(
                            "Fehler bei der Berechnung",
                            extra={
                                "error": str(e),
                                "calc_id": calc_id,
                                "formula": calc_config["formula"],
                                "variables": variables,
                                "device": self._device.name,
                                "traceback": e.__traceback__
                            }
                        )
                        
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Verarbeitung einer Berechnung",
                        extra={
                            "error": str(e),
                            "calc_id": calc_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    
            return results
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Aktualisierung der Berechnungen",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return {}

    async def calculate_value(self, formula: str, variables: Dict[str, Any]) -> Optional[float]:
        """Berechnet einen Wert basierend auf einer Formel und Variablen."""
        try:
            # Parse die Formel
            node = ast.parse(formula, mode='eval')
            
            # Evaluiere den AST
            result = self._eval_node(node.body, variables)
            
            return float(result)
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Berechnung des Werts",
                extra={
                    "error": str(e),
                    "formula": formula,
                    "variables": variables,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    def _eval_node(self, node: ast.AST, variables: Dict[str, Any]) -> Any:
        """Evaluiert einen AST-Knoten."""
        try:
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.Name):
                if node.id not in variables:
                    raise ValueError(f"Variable {node.id} nicht gefunden")
                return variables[node.id]
            elif isinstance(node, ast.BinOp):
                left = self._eval_node(node.left, variables)
                right = self._eval_node(node.right, variables)
                op = type(node.op)
                if op not in self._OPERATORS:
                    raise ValueError(f"Operator {op} nicht unterstützt")
                return self._OPERATORS[op](left, right)
            elif isinstance(node, ast.UnaryOp):
                operand = self._eval_node(node.operand, variables)
                op = type(node.op)
                if op not in self._OPERATORS:
                    raise ValueError(f"Operator {op} nicht unterstützt")
                return self._OPERATORS[op](operand)
            else:
                raise ValueError(f"AST-Knoten {type(node)} nicht unterstützt")
                
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Evaluierung des AST-Knotens",
                extra={
                    "error": str(e),
                    "node_type": type(node),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            raise

    def get_calculation_config(self, calc_id: str) -> Optional[Dict[str, Any]]:
        """Gibt die Konfiguration einer Berechnung zurück."""
        return self._calculations.get(calc_id) 