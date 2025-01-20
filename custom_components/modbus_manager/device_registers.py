"""Modbus Manager Register Processing."""
from __future__ import annotations

import asyncio
import logging
import weakref
from functools import lru_cache
from typing import Any, Dict, List, Optional, TypedDict, Callable
import ast

from .const import DOMAIN, NameType
from .logger import ModbusManagerLogger
from .device_common import DeviceCommon

_LOGGER = ModbusManagerLogger(__name__)

# Optimierte Typ-Definitionen
class RegisterDefinition(TypedDict):
    name: str
    type: str
    scale: float
    precision: Optional[int]
    interval: str

# Typ-Konvertierungen als Lookup-Table
TYPE_CONVERTERS: Dict[str, Callable] = {
    "uint16": lambda x: int(x) & 0xFFFF,
    "int16": lambda x: int(x) if int(x) < 32768 else int(x) - 65536,
    "uint32": lambda x: int(x) & 0xFFFFFFFF,
    "int32": lambda x: int(x),
    "float32": lambda x: float(x),
    "string": str,
    "bool": bool
}

class ModbusManagerRegisterProcessor:
    """Processor for Modbus Manager registers."""
    
    def __init__(self, device: DeviceCommon):
        """Initialize the register processor."""
        self.device = device
        self.registers: Dict[str, RegisterDefinition] = {}
        self.values: Dict[str, Any] = {}

    @property
    def cache_size(self) -> int:
        """Berechnet die optimale Cache-Größe basierend auf der Register-Anzahl."""
        total_registers = sum(len(regs) for regs in self.registers.values())
        return max(32, min(total_registers * 2, 256))

    @lru_cache(maxsize=None)  # Größe wird dynamisch angepasst
    def _get_scale_factor(self, register_name: str) -> float:
        """Cached Zugriff auf Skalierungsfaktoren."""
        register_def = next((r for r in self.registers.values() 
                           if r.get("name") == register_name), None)
        return float(register_def.get("scale", 1)) if register_def else 1.0

    def _adjust_cache_sizes(self) -> None:
        """Passt die Cache-Größen dynamisch an."""
        new_size = self.cache_size
        if new_size != self.cache_size:
            self.cache_size = new_size
            self._get_scale_factor.cache_clear()
            # Setze neue Cache-Größe
            self._get_scale_factor = lru_cache(maxsize=new_size)(self._get_scale_factor.__wrapped__)

    def _validate_register_definition(self, register: Dict[str, Any]) -> bool:
        """Validiert eine Register-Definition."""
        try:
            # Prüfe ob register ein Dictionary ist
            if not isinstance(register, dict):
                return False
                
            # Prüfe Pflichtfelder
            if not register.get("name"):
                return False
                
            # Prüfe Register-Adresse
            if "address" not in register:
                return False
                
            try:
                register["address"] = int(register["address"])
            except (ValueError, TypeError):
                return False
                
            # Prüfe Register-Typ
            reg_type = register.get("type", "uint16")
            if reg_type not in TYPE_CONVERTERS:
                return False
                
            # Prüfe Register-Art (input/holding)
            register_type = register.get("register_type")
            if register_type not in ["input", "holding"]:
                return False

            # Prüfe Polling-Intervall
            polling = register.get("polling", "normal")
            if polling not in ["fast", "normal", "slow"]:
                _LOGGER.warning(
                    f"Ungültiges Polling-Intervall '{polling}', setze auf 'normal'",
                    extra={
                        "register": register["name"],
                        "device": self.device.name
                    }
                )
                register["polling"] = "normal"
                
            # Prüfe und konvertiere Skalierung
            try:
                register["scale"] = float(register.get("scale", 1.0))
            except (ValueError, TypeError):
                _LOGGER.warning(
                    f"Ungültige Skalierung für {register.get('name')}, setze auf 1.0",
                    extra={
                        "register": register["name"],
                        "scale": register.get("scale"),
                        "device": self.device.name
                    }
                )
                register["scale"] = 1.0
                
            # Prüfe und konvertiere Präzision
            try:
                register["precision"] = int(register.get("precision", 0))
            except (ValueError, TypeError):
                _LOGGER.warning(
                    f"Ungültige Präzision für {register.get('name')}, setze auf 0",
                    extra={
                        "register": register["name"],
                        "precision": register.get("precision"),
                        "device": self.device.name
                    }
                )
                register["precision"] = 0
                
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Register-Validierung",
                extra={
                    "error": str(e),
                    "register": register,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    def _validate_calculation(self, calc_id: str, calc_def: Dict[str, Any]) -> bool:
        """Validiert eine Berechnungsdefinition."""
        try:
            # Prüfe ob calculation oder formula/variables Format
            if "calculation" in calc_def:
                calc_type = calc_def["calculation"].get("type")
                if not calc_type:
                    _LOGGER.error(
                        "Berechnungstyp fehlt",
                        extra={
                            "calc_id": calc_id,
                            "device": self.device.name
                        }
                    )
                    return False

                # Validiere basierend auf dem Typ
                if calc_type == "sum":
                    if "sources" not in calc_def["calculation"]:
                        _LOGGER.error(
                            "Quellen für Summenberechnung fehlen",
                            extra={
                                "calc_id": calc_id,
                                "device": self.device.name
                            }
                        )
                        return False
                elif calc_type in ["mapping", "conditional"]:
                    if "source" not in calc_def["calculation"]:
                        _LOGGER.error(
                            "Quelle für Mapping/Conditional fehlt",
                            extra={
                                "calc_id": calc_id,
                                "device": self.device.name
                            }
                        )
                        return False
                elif calc_type == "formula":
                    if "formula" not in calc_def["calculation"]:
                        _LOGGER.error(
                            "Formel fehlt",
                            extra={
                                "calc_id": calc_id,
                                "device": self.device.name
                            }
                        )
                        return False
                else:
                    _LOGGER.error(
                        "Ungültiger Berechnungstyp",
                        extra={
                            "calc_id": calc_id,
                            "type": calc_type,
                            "device": self.device.name
                        }
                    )
                    return False
                    
                return True
                
            # Prüfe formula/variables Format
            elif not all(field in calc_def for field in ["formula", "variables"]):
                _LOGGER.error(
                    "Pflichtfelder fehlen in der Berechnungsdefinition",
                    extra={
                        "calc_id": calc_id,
                        "device": self.device.name,
                        "fields": ["formula", "variables"]
                    }
                )
                return False
                    
            # Optimierte Variablenprüfung
            if "variables" in calc_def:
                invalid_vars = [
                    var for var in calc_def["variables"]
                    if not all(key in var for key in ["name", "source"])
                ]
                
                if invalid_vars:
                    _LOGGER.error(
                        "Ungültige Variablendefinitionen gefunden",
                        extra={
                            "invalid_vars": invalid_vars,
                            "calc_id": calc_id,
                            "device": self.device.name
                        }
                    )
                    return False
                    
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Validierung der Berechnungsdefinition",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def setup_registers(self, register_definitions: Dict[str, Any]) -> bool:
        """Richtet die Register basierend auf der Konfiguration ein."""
        try:
            # Hole die Register-Definitionen
            registers = register_definitions.get("registers", {})
            
            # Initialisiere Intervall-Listen
            self.registers = {
                "fast": [],
                "normal": [],
                "slow": []
            }
            
            # Verarbeite Register-Definitionen
            if "registers" in register_definitions:
                registers = register_definitions["registers"]
                
                # Prüfe ob registers ein Dictionary oder eine Liste ist
                if isinstance(registers, dict):
                    # Dictionary-Format: {"read": [...], "write": [...]}
                    for reg_type, reg_list in registers.items():
                        if isinstance(reg_list, list):
                            for register in reg_list:
                                # Setze register_type basierend auf der Definition
                                register["register_type"] = "input" if reg_type == "read" else "holding"
                                if self._validate_register_definition(register):
                                    polling = register.get("polling", "normal")
                                    self.registers[polling].append(register)
                                else:
                                    _LOGGER.warning(
                                        "Register-Definition übersprungen",
                                        extra={
                                            "register": register,
                                            "device": self.device.name,
                                            "errors": self.errors
                                        }
                                    )
                elif isinstance(registers, list):
                    # Listen-Format: [{"name": ..., "type": ..., ...}, ...]
                    for register in registers:
                        if self._validate_register_definition(register):
                            polling = register.get("polling", "normal")
                            self.registers[polling].append(register)
                        else:
                            _LOGGER.warning(
                                "Register-Definition übersprungen",
                                extra={
                                    "register": register,
                                    "device": self.device.name,
                                    "errors": self.errors
                                }
                            )
                else:
                    _LOGGER.error(
                        "Ungültiges Register-Format",
                        extra={
                            "type": type(registers),
                            "device": self.device.name
                        }
                    )
                    return False
                            
            # Verarbeite berechnete Register
            if "calculated_registers" in register_definitions:
                calc_registers = register_definitions["calculated_registers"]
                
                # Prüfe ob calculated_registers ein Dictionary oder eine Liste ist
                if isinstance(calc_registers, dict):
                    for calc_id, calc_def in calc_registers.items():
                        if self._validate_calculation(calc_id, calc_def):
                            self.values[calc_id] = calc_def
                        else:
                            _LOGGER.warning(
                                "Berechnungsdefinition übersprungen",
                                extra={
                                    "calc_id": calc_id,
                                    "device": self.device.name,
                                    "errors": self.errors
                                }
                            )
                elif isinstance(calc_registers, list):
                    for calc_def in calc_registers:
                        if "name" not in calc_def:
                            _LOGGER.warning(
                                "Berechnungsdefinition ohne Namen übersprungen",
                                extra={
                                    "calc_def": calc_def,
                                    "device": self.device.name
                                }
                            )
                            continue
                            
                        calc_id = calc_def["name"]
                        if self._validate_calculation(calc_id, calc_def):
                            self.values[calc_id] = calc_def
                        else:
                            _LOGGER.warning(
                                "Berechnungsdefinition übersprungen",
                                extra={
                                    "calc_id": calc_id,
                                    "device": self.device.name,
                                    "errors": self.errors
                                }
                            )
                            
            # Passe Cache-Größen an
            self._adjust_cache_sizes()
            
            # Logge Setup-Ergebnis
            _LOGGER.info(
                "Register-Setup abgeschlossen",
                extra={
                    "device": self.device.name,
                    "total_registers": sum(len(regs) for regs in self.registers.values()),
                    "calculated_registers": len(self.values),
                    "validation_errors": len(self.errors)
                }
            )
            
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup der Register",
                extra={
                    "error": str(e),
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _validate_and_sort_register(self, register: Dict[str, Any]) -> bool:
        """Validiert und sortiert ein Register."""
        try:
            # Validiere das Register
            if not self._validate_register_definition(register):
                return False
                
            # Generiere eindeutige Namen mit dem EntityNameHelper
            register["unique_id"] = self.device.name_helper.convert(
                register["name"],
                NameType.UNIQUE_ID
            )
            
            # Setze Standard-Polling wenn nicht definiert
            if "polling" not in register:
                register["polling"] = "normal"
                
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Register-Verarbeitung",
                extra={
                    "error": str(e),
                    "register": register,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _validate_and_store_calculation(self, calc_id: str, calc_def: Dict[str, Any]) -> None:
        """Validiert eine Berechnung und speichert sie wenn gültig."""
        try:
            if await self._validate_calculation_async(calc_id, calc_def):
                self.values[calc_id] = calc_def
                
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Berechnungs-Validierung",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )

    async def _validate_calculation_async(self, calc_id: str, calc_def: Dict[str, Any]) -> bool:
        """Asynchrone Wrapper-Methode für die Berechnungsvalidierung."""
        return self._validate_calculation(calc_id, calc_def)

    async def process_register_value(self, register_name: str, register_def: Dict[str, Any], raw_value: Any) -> Optional[Any]:
        """Verarbeitet den Rohwert eines Registers."""
        try:
            if raw_value is None:
                return None

            reg_type = register_def.get("type", "uint16")
            
            # Typ-Konvertierung über Lookup-Table
            converter = TYPE_CONVERTERS.get(reg_type)
            if not converter:
                _LOGGER.error(
                    "Ungültiger Register-Typ",
                    extra={
                        "type": reg_type,
                        "register": register_name,
                        "device": self.device.name
                    }
                )
                return None

            try:
                value = converter(raw_value)
            except (ValueError, TypeError) as e:
                _LOGGER.error(
                    "Fehler bei der Typkonvertierung",
                    extra={
                        "error": str(e),
                        "type": reg_type,
                        "raw_value": raw_value,
                        "register": register_name,
                        "device": self.device.name,
                        "traceback": e.__traceback__
                    }
                )
                return None

            # Optimierte Skalierung mit Cache
            scale = self._get_scale_factor(register_name)
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
                            "device": self.device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    return None

            # Präzision anwenden wenn definiert
            precision = register_def.get("precision")
            if precision is not None:
                value = round(float(value), precision)

            return value

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Register-Verarbeitung",
                extra={
                    "error": str(e),
                    "register": register_name,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def update_registers(self, interval: str) -> bool:
        """Aktualisiert die Register für das angegebene Intervall."""
        try:
            # Hole die Register für dieses Intervall
            registers = self.registers.get(interval, [])

            _LOGGER.debug(
                f"Starte Register-Update",
                extra={
                    "device": self.device.name,
                    "interval": interval,
                    "register_count": len(registers)
                }
            )

            if not registers:
                _LOGGER.debug(
                    f"Keine Register für Intervall {interval}",
                    extra={
                        "device": self.device.name,
                        "interval": interval
                    }
                )
                return True  # Kein Fehler, nur keine Register

            # Verarbeite jedes Register einzeln
            failed_registers = []
            successful_registers = []
            tasks = []
            
            # Gruppiere Register nach Adresse für Batch-Verarbeitung
            address_groups = {}
            for register in registers:
                if not isinstance(register, dict):
                    _LOGGER.error(
                        "Ungültiges Register-Format",
                        extra={
                            "register_type": type(register),
                            "register": register,
                            "device": self.device.name
                        }
                    )
                    failed_registers.append(register)
                    continue

                address = register.get("address", 0)
                reg_type = register.get("register_type", "holding")
                count = register.get("count", 1)
                
                key = (reg_type, address, count)
                if key not in address_groups:
                    address_groups[key] = []
                address_groups[key].append(register)

            # Verarbeite Register in Batches
            for (reg_type, address, count), batch_registers in address_groups.items():
                try:
                    _LOGGER.debug(
                        "Erstelle Register-Batch-Task",
                        extra={
                            "type": reg_type,
                            "address": address,
                            "count": count,
                            "batch_size": len(batch_registers),
                            "device": self.device.name
                        }
                    )

                    # Lese die Register basierend auf dem Typ
                    if reg_type == "input":
                        values = await self.device._hub.async_read_input_registers(
                            slave=self.device._slave,
                            address=address,
                            count=count
                        )
                    else:  # holding register
                        values = await self.device._hub.async_read_registers(
                            slave=self.device._slave,
                            address=address,
                            count=count
                        )

                    if values:
                        for register in batch_registers:
                            await self.process_register_value(register["name"], register, values[0])
                            successful_registers.append(register)
                    else:
                        _LOGGER.error(
                            "Keine Werte vom Register-Batch gelesen",
                            extra={
                                "type": reg_type,
                                "address": address,
                                "count": count,
                                "device": self.device.name
                            }
                        )
                        failed_registers.extend(batch_registers)
                        
                except Exception as e:
                    _LOGGER.error(
                        "Fehler beim Lesen des Register-Batches",
                        extra={
                            "error": str(e),
                            "type": reg_type,
                            "address": address,
                            "count": count,
                            "device": self.device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    failed_registers.extend(batch_registers)

            # Log Zusammenfassung
            _LOGGER.info(
                "Register-Update abgeschlossen",
                extra={
                    "device": self.device.name,
                    "interval": interval,
                    "total_registers": len(registers),
                    "failed_registers": len(failed_registers),
                    "successful_registers": len(successful_registers)
                }
            )

            # Wenn zu viele Register fehlgeschlagen sind, breche ab
            if len(failed_registers) > len(registers) * 0.5:  # Mehr als 50% fehlgeschlagen
                _LOGGER.error(
                    "Zu viele Register-Updates fehlgeschlagen",
                    extra={
                        "device": self.device.name,
                        "interval": interval,
                        "failed_count": len(failed_registers),
                        "total_count": len(registers),
                        "failed_registers": [r.get("name", "Unbekannt") for r in failed_registers]
                    }
                )
                return False

            # Aktualisiere berechnete Register nur wenn mindestens ein Register erfolgreich war
            if successful_registers:
                await self.update_calculated_registers()

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Aktualisieren der Register",
                extra={
                    "error": str(e),
                    "device": self.device.name,
                    "interval": interval,
                    "traceback": e.__traceback__
                }
            )
            return False  # Wichtig: Fehler signalisieren für Device-Initialisierung

    async def update_calculated_registers(self) -> None:
        """Aktualisiert die berechneten Register."""
        try:
            if not self.values:
                _LOGGER.debug(
                    "Keine berechneten Register vorhanden",
                    extra={
                        "device": self.device.name
                    }
                )
                return

            # Optimierte Datensammlung mit Set für schnellere Lookups
            required_sources = set()
            for calc_def in self.values.values():
                if "variables" in calc_def:
                    for var in calc_def["variables"]:
                        if isinstance(var, dict) and "source" in var:
                            required_sources.add(var["source"])
                elif "calculation" in calc_def:
                    calc_type = calc_def["calculation"].get("type")
                    if calc_type == "sum":
                        required_sources.update(calc_def["calculation"].get("sources", []))
                    elif calc_type in ["mapping", "conditional"]:
                        source = calc_def["calculation"].get("source")
                        if source:
                            required_sources.add(source)

            # Sammle verfügbare Werte
            available_values = {}
            for source in required_sources:
                # Konvertiere den Quell-Namen
                prefixed_source = self.device.name_helper.convert(source, NameType.BASE_NAME)
                if prefixed_source in self.values:
                    available_values[source] = self.values[prefixed_source]

            # Verarbeite die Berechnungen
            for calc_id, calc_def in self.values.items():
                try:
                    # Prüfe ob es sich um eine Berechnung oder direkte Formel handelt
                    if "calculation" in calc_def:
                        await self._process_calculation_type(calc_id, calc_def, available_values)
                    elif "formula" in calc_def and "variables" in calc_def:
                        # Prüfe ob alle benötigten Variablen verfügbar sind
                        if all(isinstance(var, dict) and 
                              "source" in var and 
                              var["source"] in available_values 
                              for var in calc_def["variables"]):
                            variables = {
                                var["name"]: available_values[var["source"]]
                                for var in calc_def["variables"]
                            }
                            # Berechne das Ergebnis mit dem Calculator
                            result = await self.device.calculator.calculate_value(calc_def["formula"], variables)
                            if result is not None:
                                # Speichere das Ergebnis in den Register-Daten
                                prefixed_calc_id = self.device.name_helper.convert(calc_id, NameType.BASE_NAME)
                                self.values[prefixed_calc_id] = result
                                _LOGGER.debug(
                                    "Berechnetes Register aktualisiert",
                                    extra={
                                        "calc_id": calc_id,
                                        "formula": calc_def["formula"],
                                        "variables": variables,
                                        "result": result,
                                        "device": self.device.name
                                    }
                                )
                        else:
                            _LOGGER.debug(
                                "Nicht alle Variablen für Berechnung verfügbar",
                                extra={
                                    "calc_id": calc_id,
                                    "device": self.device.name,
                                    "missing_vars": [
                                        var["source"] for var in calc_def["variables"]
                                        if var["source"] not in available_values
                                    ]
                                }
                            )
                    else:
                        _LOGGER.warning(
                            "Ungültiges Berechnungsformat",
                            extra={
                                "calc_id": calc_id,
                                "device": self.device.name
                            }
                        )
                        
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Verarbeitung der Berechnung",
                        extra={
                            "error": str(e),
                            "calc_id": calc_id,
                            "device": self.device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    continue
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Aktualisierung der berechneten Register",
                extra={
                    "error": str(e),
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )

    async def _process_calculation_type(self, calc_id: str, calc_def: Dict[str, Any], available_values: Dict[str, Any]) -> None:
        """Verarbeitet verschiedene Berechnungstypen."""
        try:
            calc_type = calc_def["calculation"].get("type")
            result = None
            
            if calc_type == "sum":
                sources = calc_def["calculation"].get("sources", [])
                if all(source in available_values for source in sources):
                    result = sum(available_values[source] for source in sources)
                    
            elif calc_type == "mapping":
                source = calc_def["calculation"].get("source")
                if source in available_values:
                    map_name = calc_def["calculation"].get("map")
                    # TODO: Implementiere Mapping-Logik
                    result = available_values[source]  # Vorläufig direkter Wert
                    
            elif calc_type == "conditional":
                source = calc_def["calculation"].get("source")
                if source in available_values:
                    condition = calc_def["calculation"].get("condition")
                    value = available_values[source]
                    
                    if condition == "positive":
                        result = value if value > 0 else 0
                    elif condition == "negative":
                        result = abs(value) if value < 0 else 0
                    else:
                        result = value
                        
            elif calc_type == "formula":
                formula = calc_def["calculation"].get("formula", "")
                try:
                    # Parse die Formel um Variablen zu extrahieren
                    tree = ast.parse(formula, mode='eval')
                    var_names = set()
                    
                    def extract_vars(node):
                        if isinstance(node, ast.Name):
                            var_names.add(node.id)
                        elif isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare)):
                            for child in ast.iter_child_nodes(node):
                                extract_vars(child)
                                
                    extract_vars(tree.body)
                    
                    # Sammle verfügbare Variablenwerte
                    variables = {}
                    missing_vars = []
                    
                    for var_name in var_names:
                        prefixed_name = self.device.name_helper.convert(var_name, NameType.BASE_NAME)
                        if prefixed_name in available_values:
                            variables[var_name] = available_values[prefixed_name]
                        else:
                            missing_vars.append(var_name)
                    
                    if missing_vars:
                        _LOGGER.debug(
                            "Variablen für Formel nicht verfügbar",
                            extra={
                                "calc_id": calc_id,
                                "formula": formula,
                                "missing_vars": missing_vars,
                                "device": self.device.name
                            }
                        )
                        return
                    
                    # Berechne das Ergebnis mit dem Calculator
                    result = await self.device.calculator.calculate_value(formula, variables)
                    
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Formelverarbeitung",
                        extra={
                            "error": str(e),
                            "calc_id": calc_id,
                            "formula": formula,
                            "device": self.device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    return
                
            # Speichere das Ergebnis wenn vorhanden
            if result is not None:
                prefixed_calc_id = self.device.name_helper.convert(calc_id, NameType.BASE_NAME)
                self.values[prefixed_calc_id] = result
                _LOGGER.debug(
                    "Berechnetes Register aktualisiert",
                    extra={
                        "calc_id": calc_id,
                        "type": calc_type,
                        "result": result,
                        "device": self.device.name
                    }
                )
                
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Verarbeitung des Berechnungstyps",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "type": calc_type if 'calc_type' in locals() else None,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )

    def _store_calculated_value(self, calc_id: str, value: Any) -> None:
        """Speichert einen berechneten Wert."""
        try:
            prefixed_name = self.device.name_helper.convert(calc_id, NameType.BASE_NAME)
            self.values[prefixed_name] = value
            
            _LOGGER.debug(
                "Berechneter Wert gespeichert",
                extra={
                    "calc_id": calc_id,
                    "value": value,
                    "device": self.device.name
                }
            )
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Speichern des berechneten Werts",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "device": self.device.name,
                    "traceback": e.__traceback__
                }
            )

    @property
    def register_data(self) -> Dict[str, Any]:
        """Gibt die aktuellen Register-Daten zurück."""
        return self.values.copy()

    @property
    def registers_by_interval(self) -> Dict[str, List[Dict[str, Any]]]:
        """Gibt die Register gruppiert nach Intervall zurück."""
        return self.registers.copy() 