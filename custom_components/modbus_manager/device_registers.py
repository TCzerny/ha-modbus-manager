"""Modbus Manager Register Processing."""
from __future__ import annotations

import asyncio
import logging
import weakref
from functools import lru_cache
from typing import Any, Dict, List, Optional, TypedDict, Callable
import ast

from .const import DOMAIN, NameType
from .device_base import ModbusManagerDeviceBase
from .logger import ModbusManagerLogger

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
    "int16": lambda x: (int(x) & 0xFFFF) - 65536 if (int(x) & 0xFFFF) > 32767 else int(x) & 0xFFFF,
    "uint32": lambda x: int(x) & 0xFFFFFFFF,
    "int32": lambda x: (int(x) & 0xFFFFFFFF) - 4294967296 if (int(x) & 0xFFFFFFFF) > 2147483647 else int(x) & 0xFFFFFFFF,
    "float32": float,
    "string": str
}

# Standard-Werte für Register
DEFAULT_VALUES = {
    "type": "uint16",
    "scale": 1.0,
    "precision": 0,
    "polling": "normal"  # Standard-Polling-Intervall
}

class ModbusManagerRegisterProcessor:
    """Class for processing Modbus registers."""

    def __init__(self, device: ModbusManagerDeviceBase) -> None:
        """Initialize the register processor."""
        try:
            # Schwache Referenz auf das Device-Objekt
            self._device = weakref.proxy(device)
            
            # Optimierte Datenstrukturen
            self._register_data: Dict[str, Any] = {}
            self._registers_by_interval: Dict[str, List[RegisterDefinition]] = {
                "fast": [],
                "normal": [],
                "slow": []
            }
            self._calculated_registers: Dict[str, Dict[str, Any]] = {}
            
            # Cache-Größen basierend auf Register-Anzahl
            self._cache_size = 32  # Basis-Größe, wird dynamisch angepasst
            
            # Fehler-Tracking
            self._validation_errors: List[str] = []
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Initialisierung des Register-Prozessors",
                extra={
                    "error": str(e),
                    "device": device.name,
                    "traceback": e.__traceback__
                }
            )
            raise

    @property
    def cache_size(self) -> int:
        """Berechnet die optimale Cache-Größe basierend auf der Register-Anzahl."""
        total_registers = sum(len(regs) for regs in self._registers_by_interval.values())
        return max(32, min(total_registers * 2, 256))

    @lru_cache(maxsize=None)  # Größe wird dynamisch angepasst
    def _get_scale_factor(self, register_name: str) -> float:
        """Cached Zugriff auf Skalierungsfaktoren."""
        register_def = next((r for r in self._registers_by_interval.values() 
                           for reg in r if reg.get("name") == register_name), None)
        return float(register_def.get("scale", 1)) if register_def else 1.0

    def _adjust_cache_sizes(self) -> None:
        """Passt die Cache-Größen dynamisch an."""
        new_size = self.cache_size
        if new_size != self._cache_size:
            self._cache_size = new_size
            self._get_scale_factor.cache_clear()
            # Setze neue Cache-Größe
            self._get_scale_factor = lru_cache(maxsize=new_size)(self._get_scale_factor.__wrapped__)

    def _check_register_overlap(self, register: Dict[str, Any], existing_registers: List[Dict[str, Any]]) -> bool:
        """Prüft ob sich ein Register mit existierenden Registern überlappt."""
        try:
            if not register or "address" not in register:
                return False
                
            new_address = register["address"]
            new_count = register.get("count", 1)  # Standard ist 1 Register
            new_type = register.get("register_type", "input")
            new_range = set(range(new_address, new_address + new_count))
            
            for existing in existing_registers:
                if existing.get("register_type") != new_type:
                    continue  # Verschiedene Register-Typen können sich nicht überlappen
                    
                existing_address = existing.get("address")
                if existing_address is None:
                    continue
                    
                existing_count = existing.get("count", 1)
                existing_range = set(range(existing_address, existing_address + existing_count))
                
                if new_range.intersection(existing_range):
                    _LOGGER.error(
                        "Register-Überlappung gefunden",
                        extra={
                            "new_register": register["name"],
                            "existing_register": existing.get("name"),
                            "address_range": f"{new_address}-{new_address + new_count - 1}",
                            "existing_range": f"{existing_address}-{existing_address + existing_count - 1}",
                            "type": new_type,
                            "device": self._device.name
                        }
                    )
                    return True
                    
            return False
            
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Überlappungsprüfung",
                extra={
                    "error": str(e),
                    "register": register.get("name"),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return True  # Im Fehlerfall als Überlappung behandeln

    def _validate_register_definition(self, register: Dict[str, Any]) -> bool:
        """Validiert eine Register-Definition."""
        try:
            # Prüfe ob register ein Dictionary ist
            if not isinstance(register, dict):
                self._validation_errors.append(f"Register ist kein Dictionary: {register}")
                return False
                
            # Prüfe Pflichtfelder
            if not register.get("name"):
                self._validation_errors.append("Register-Name fehlt")
                return False
                
            # Prüfe Register-Adresse
            if "address" not in register:
                self._validation_errors.append(f"Register-Adresse fehlt für {register.get('name')}")
                return False
                
            try:
                register["address"] = int(register["address"])
            except (ValueError, TypeError):
                self._validation_errors.append(f"Ungültige Register-Adresse für {register.get('name')}: {register.get('address')}")
                return False
                
            # Prüfe auf Register-Überlappungen
            all_registers = []
            for regs in self._registers_by_interval.values():
                all_registers.extend(regs)
                
            if self._check_register_overlap(register, all_registers):
                self._validation_errors.append(
                    f"Register {register.get('name')} überlappt mit existierenden Registern"
                )
                return False

            # Setze Standard-Werte für fehlende Felder
            for key, default_value in DEFAULT_VALUES.items():
                if key not in register:
                    register[key] = default_value
                    _LOGGER.debug(
                        f"Standard-Wert für {key} gesetzt",
                        extra={
                            "register": register["name"],
                            "value": default_value,
                            "device": self._device.name
                        }
                    )

            # Prüfe Register-Typ
            reg_type = register.get("type", "uint16")
            if reg_type not in TYPE_CONVERTERS:
                self._validation_errors.append(f"Ungültiger Register-Typ: {reg_type}")
                return False
                
            # Prüfe Register-Art (input/holding)
            register_type = register.get("register_type")
            if register_type not in ["input", "holding"]:
                self._validation_errors.append(f"Ungültiger Register-Typ (input/holding) für {register.get('name')}")
                return False

            # Prüfe Polling-Intervall
            polling = register.get("polling", "normal")
            if polling not in ["fast", "normal", "slow"]:
                _LOGGER.warning(
                    f"Ungültiges Polling-Intervall '{polling}', setze auf 'normal'",
                    extra={
                        "register": register["name"],
                        "device": self._device.name
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
                        "device": self._device.name
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
                        "device": self._device.name
                    }
                )
                register["precision"] = 0
                
            return True
            
        except Exception as e:
            self._validation_errors.append(f"Validierungsfehler: {str(e)}")
            _LOGGER.error(
                "Fehler bei der Register-Validierung",
                extra={
                    "error": str(e),
                    "register": register,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    def _validate_calculation(self, calc_id: str, calc_config: Dict[str, Any]) -> bool:
        """Validiert eine Berechnungskonfiguration."""
        try:
            # Prüfe ob calc_config ein Dictionary ist
            if not isinstance(calc_config, dict):
                self._validation_errors.append(f"Berechnungskonfiguration ist kein Dictionary: {calc_config}")
                return False

            # Prüfe Berechnungstyp
            calc_type = calc_config.get("type")
            if not calc_type:
                self._validation_errors.append(f"Kein Berechnungstyp für {calc_id} angegeben")
                return False

            valid_calc_types = ["sum", "mapping", "conditional", "formula"]
            if calc_type not in valid_calc_types:
                self._validation_errors.append(f"Ungültiger Berechnungstyp für {calc_id}: {calc_type}")
                return False

            # Validiere typ-spezifische Felder
            if calc_type == "sum":
                if "sources" not in calc_config:
                    self._validation_errors.append(f"Keine Quellen für Sum-Berechnung {calc_id} angegeben")
                    return False
                # Passe Quell-Variablen an
                sources = calc_config["sources"]
                if isinstance(sources, list):
                    calc_config["sources"] = [
                        self._device.name_helper.convert(source, NameType.BASE_NAME)
                        for source in sources
                    ]

            elif calc_type == "mapping":
                if "source" not in calc_config:
                    self._validation_errors.append(f"Keine Quelle für Mapping-Berechnung {calc_id} angegeben")
                    return False
                # Passe Quell-Variable an
                calc_config["source"] = self._device.name_helper.convert(
                    calc_config["source"], 
                    NameType.BASE_NAME
                )

            elif calc_type == "conditional":
                if "source" not in calc_config:
                    self._validation_errors.append(f"Keine Quelle für Conditional-Berechnung {calc_id} angegeben")
                    return False
                # Passe Quell-Variable an
                calc_config["source"] = self._device.name_helper.convert(
                    calc_config["source"], 
                    NameType.BASE_NAME
                )

            elif calc_type == "formula":
                if "formula" not in calc_config:
                    self._validation_errors.append(f"Keine Formel für Formula-Berechnung {calc_id} angegeben")
                    return False
                if "variables" in calc_config:
                    # Passe Variablen-Namen in der Variablenliste an
                    variables = calc_config["variables"]
                    if isinstance(variables, list):
                        for var in variables:
                            if isinstance(var, dict) and "source" in var:
                                var["source"] = self._device.name_helper.convert(
                                    var["source"], 
                                    NameType.BASE_NAME
                                )

            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Berechnungsvalidierung",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "device": self._device.name,
                    "traceback": str(e.__traceback__)
                }
            )
            return False

    async def setup_registers(self, register_definitions: Dict[str, Any]) -> bool:
        """Richtet die Register basierend auf der Konfiguration ein."""
        try:
            _LOGGER.info(
                "Starte Register-Setup",
                extra={"device": self._device.name}
            )
            
            # Setze Validierungsfehler zurück
            self._validation_errors = []
            
            # Initialisiere Register-Listen
            self._registers_by_interval = {
                "fast": [],
                "normal": [],
                "slow": []
            }
            
            # Verarbeite Register-Definitionen
            if "registers" in register_definitions:
                registers = register_definitions["registers"]
                
                # Dictionary-Format: {"read": [...], "write": [...]}
                if isinstance(registers, dict):
                    for reg_type in ["read", "write"]:
                        if reg_type in registers:
                            for register in registers[reg_type]:
                                # Setze register_type basierend auf der Definition
                                register["register_type"] = "input" if reg_type == "read" else "holding"
                                if await self._validate_and_sort_register(register):
                                    polling = register.get("polling", "normal")
                                    self._registers_by_interval[polling].append(register)
                                else:
                                    _LOGGER.warning(
                                        "Register-Definition übersprungen",
                                        extra={
                                            "register": register,
                                            "device": self._device.name,
                                            "errors": self._validation_errors
                                        }
                                    )
            
            # Verarbeite berechnete Register
            if "calculated_registers" in register_definitions:
                calc_registers = register_definitions["calculated_registers"]
                
                # Konvertiere Liste in Dict wenn nötig
                if isinstance(calc_registers, list):
                    calc_registers = {
                        calc["name"]: calc 
                        for calc in calc_registers 
                        if "name" in calc
                    }
                
                if isinstance(calc_registers, dict):
                    for calc_id, calc_config in calc_registers.items():
                        # Stelle sicher, dass die Konfiguration vollständig ist
                        if not isinstance(calc_config, dict):
                            continue
                            
                        # Validiere die Berechnung
                        if self._validate_calculation(calc_id, calc_config):
                            self._calculated_registers[calc_id] = calc_config
                            _LOGGER.debug(
                                "Berechnetes Register hinzugefügt",
                                extra={
                                    "calc_id": calc_id,
                                    "device": self._device.name,
                                    "config": calc_config
                                }
                            )
                        else:
                            _LOGGER.warning(
                                "Berechnungsdefinition übersprungen",
                                extra={
                                    "calc_id": calc_id,
                                    "device": self._device.name,
                                    "errors": self._validation_errors
                                }
                            )
            
            return True
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Register-Setup",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": str(e.__traceback__)
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
            register["unique_id"] = self._device.name_helper.convert(
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
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def _validate_and_store_calculation(self, calc_id: str, calc_def: Dict[str, Any]) -> None:
        """Validiert eine Berechnung und speichert sie wenn gültig."""
        try:
            # Konvertiere calculation Format zu formula/variables wenn nötig
            if "calculation" in calc_def:
                calc_type = calc_def["calculation"].get("type")
                if calc_type == "sum":
                    sources = calc_def["calculation"].get("sources", [])
                    calc_def["formula"] = " + ".join(sources)
                    calc_def["variables"] = [{"name": s, "source": s} for s in sources]
                elif calc_type == "mapping":
                    source = calc_def["calculation"].get("source")
                    map_name = calc_def["calculation"].get("map")
                    # TODO: Implementiere Mapping-Logik
                    calc_def["formula"] = source
                    calc_def["variables"] = [{"name": source, "source": source}]
                elif calc_type == "conditional":
                    source = calc_def["calculation"].get("source")
                    condition = calc_def["calculation"].get("condition")
                    absolute = calc_def["calculation"].get("absolute", False)
                    
                    if condition == "positive":
                        calc_def["formula"] = f"{source} if {source} > 0 else 0"
                    elif condition == "negative":
                        if absolute:
                            calc_def["formula"] = f"abs({source}) if {source} < 0 else 0"
                        else:
                            calc_def["formula"] = f"{source} if {source} < 0 else 0"
                    else:
                        calc_def["formula"] = source
                        
                    calc_def["variables"] = [{"name": source, "source": source}]
                elif calc_type == "formula":
                    formula = calc_def["calculation"].get("formula", "")
                    calc_def["formula"] = formula
                    # Extrahiere Variablen aus der Formel mit AST
                    try:
                        tree = ast.parse(formula, mode='eval')
                        var_names = set()
                        
                        # Rekursive Funktion zum Extrahieren von Variablennamen
                        def extract_vars(node):
                            if isinstance(node, ast.Name):
                                var_names.add(node.id)
                            elif isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare)):
                                for child in ast.iter_child_nodes(node):
                                    extract_vars(child)
                                    
                        extract_vars(tree.body)
                        calc_def["variables"] = [{"name": v, "source": v} for v in var_names]
                        
                    except Exception as e:
                        _LOGGER.error(
                            "Fehler beim Extrahieren der Variablen aus der Formel",
                            extra={
                                "error": str(e),
                                "formula": formula,
                                "calc_id": calc_id,
                                "device": self._device.name,
                                "traceback": e.__traceback__
                            }
                        )
                        return

            if await self._validate_calculation_async(calc_id, calc_def):
                # Generiere alle benötigten Namen mit EntityNameHelper
                calc_def["unique_id"] = self._device.name_helper.convert(
                    calc_id,
                    NameType.UNIQUE_ID
                )
                calc_def["name"] = self._device.name_helper.convert(
                    calc_id,
                    NameType.DISPLAY_NAME
                )
                # Generiere entity_id mit Domain
                calc_def["entity_id"] = self._device.name_helper.convert(
                    calc_id,
                    NameType.ENTITY_ID,
                    domain="sensor"  # Berechnete Register sind immer Sensoren
                )
                
                self._calculated_registers[calc_id] = calc_def
                
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Berechnungs-Validierung",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def _validate_calculation_async(self, calc_id: str, calc_def: Dict[str, Any]) -> bool:
        """Asynchrone Wrapper-Methode für die Berechnungsvalidierung."""
        return self._validate_calculation(calc_id, calc_def)

    async def read_register(self, register: Dict[str, Any], values: List[int]) -> None:
        """Liest ein einzelnes Register."""
        try:
            # Validiere register
            if not isinstance(register, dict):
                _LOGGER.error(
                    "Register ist kein Dictionary",
                    extra={
                        "register_type": type(register),
                        "register": register,
                        "device": self._device.name
                    }
                )
                return

            register_name = register.get("name")
            if not register_name:
                _LOGGER.error(
                    "Register hat keinen Namen",
                    extra={
                        "register": register,
                        "device": self._device.name
                    }
                )
                return
                
            # Konvertiere den Register-Namen
            prefixed_name = self._device.name_helper.convert(register_name, NameType.BASE_NAME)
            
            # Verarbeite den Wert
            if len(values) > 0:
                processed_value = await self.process_register_value(register_name, register, values[0])
                if processed_value is not None:
                    self._register_data[prefixed_name] = processed_value
                    _LOGGER.debug(
                        "Register erfolgreich gelesen",
                        extra={
                            "register": register_name,
                            "prefixed_name": prefixed_name,
                            "raw_value": values[0],
                            "processed_value": processed_value,
                            "device": self._device.name
                        }
                    )
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Lesen des Registers",
                extra={
                    "error": str(e),
                    "register": register.get("name") if isinstance(register, dict) else register,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def process_register_value(self, register_name: str, register_def: Dict[str, Any], raw_value: Any) -> Optional[Any]:
        """Verarbeitet den Rohwert eines Registers."""
        try:
            if raw_value is None:
                return None
                
            # Validiere register_def
            if not isinstance(register_def, dict):
                _LOGGER.error(
                    "Register-Definition ist kein Dictionary",
                    extra={
                        "register": register_name,
                        "register_def_type": type(register_def),
                        "register_def": register_def,
                        "device": self._device.name
                    }
                )
                return None

            # Hole den Register-Typ
            reg_type = register_def.get("type", "uint16")
            if not isinstance(reg_type, str):
                _LOGGER.error(
                    "Register-Typ ist kein String",
                    extra={
                        "register": register_name,
                        "type": reg_type,
                        "type_type": type(reg_type),
                        "device": self._device.name
                    }
                )
                return None
            
            # Typ-Konvertierung über Lookup-Table
            converter = TYPE_CONVERTERS.get(reg_type)
            if not converter:
                _LOGGER.error(
                    "Ungültiger Register-Typ",
                    extra={
                        "type": reg_type,
                        "register": register_name,
                        "device": self._device.name
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
                        "device": self._device.name,
                        "traceback": e.__traceback__
                    }
                )
                return None

            # Optimierte Skalierung mit Cache
            scale = register_def.get("scale", 1.0)
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
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    return None

            # Präzision anwenden wenn definiert
            precision = register_def.get("precision")
            if precision is not None:
                try:
                    value = round(float(value), precision)
                except (ValueError, TypeError) as e:
                    _LOGGER.error(
                        "Fehler bei der Rundung",
                        extra={
                            "error": str(e),
                            "precision": precision,
                            "value": value,
                            "register": register_name,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    return None

            return value

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Register-Verarbeitung",
                extra={
                    "error": str(e),
                    "register": register_name,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def _read_single_register(self, register: Dict[str, Any], reg_type: str, address: int, count: int) -> None:
        """Liest ein einzelnes Register."""
        try:
            # Lese die Register basierend auf dem Typ
            if reg_type == "input":
                values = await self._device._hub.async_read_input_registers(
                    slave=self._device._slave,
                    address=address,
                    count=count
                )
            else:  # holding register
                values = await self._device._hub.async_read_registers(
                    slave=self._device._slave,
                    address=address,
                    count=count
                )

            if values:
                await self.read_register(register, values)
            else:
                _LOGGER.error(
                    "Keine Werte vom Register gelesen",
                    extra={
                        "register": register.get("name", "Unbekannt"),
                        "type": reg_type,
                        "address": address,
                        "count": count,
                        "device": self._device.name
                    }
                )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Lesen des Registers",
                extra={
                    "error": str(e),
                    "register": register.get("name", "Unbekannt"),
                    "type": reg_type,
                    "address": address,
                    "count": count,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def update_registers(self, interval: str) -> bool:
        """Aktualisiert die Register für das angegebene Intervall."""
        try:
            # Hole die Register für dieses Intervall
            registers = self._registers_by_interval.get(interval, [])

            _LOGGER.debug(
                f"Starte Register-Update",
                extra={
                    "device": self._device.name,
                    "interval": interval,
                    "register_count": len(registers)
                }
            )

            if not registers:
                _LOGGER.debug(
                    f"Keine Register für Intervall {interval}",
                    extra={
                        "device": self._device.name,
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
                            "device": self._device.name
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
                            "device": self._device.name
                        }
                    )

                    # Lese die Register basierend auf dem Typ
                    if reg_type == "input":
                        values = await self._device._hub.async_read_input_registers(
                            slave=self._device._slave,
                            address=address,
                            count=count
                        )
                    else:  # holding register
                        values = await self._device._hub.async_read_registers(
                            slave=self._device._slave,
                            address=address,
                            count=count
                        )

                    if values:
                        for register in batch_registers:
                            await self.read_register(register, values)
                            successful_registers.append(register)
                    else:
                        _LOGGER.error(
                            "Keine Werte vom Register-Batch gelesen",
                            extra={
                                "type": reg_type,
                                "address": address,
                                "count": count,
                                "device": self._device.name
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
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    failed_registers.extend(batch_registers)

            # Log Zusammenfassung
            _LOGGER.info(
                "Register-Update abgeschlossen",
                extra={
                    "device": self._device.name,
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
                        "device": self._device.name,
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
                    "device": self._device.name,
                    "interval": interval,
                    "traceback": e.__traceback__
                }
            )
            return False  # Wichtig: Fehler signalisieren für Device-Initialisierung

    async def update_calculated_registers(self) -> None:
        """Aktualisiert die berechneten Register."""
        try:
            if not self._calculated_registers:
                _LOGGER.debug(
                    "Keine berechneten Register vorhanden",
                    extra={
                        "device": self._device.name
                    }
                )
                return

            # Optimierte Datensammlung mit Set für schnellere Lookups
            required_sources = set()
            for calc_def in self._calculated_registers.values():
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
                prefixed_source = self._device.name_helper.convert(source, NameType.BASE_NAME)
                if prefixed_source in self._register_data:
                    available_values[source] = self._register_data[prefixed_source]

            # Verarbeite die Berechnungen
            for calc_id, calc_def in self._calculated_registers.items():
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
                            result = await self._device.calculator.calculate_value(calc_def["formula"], variables)
                            if result is not None:
                                # Speichere das Ergebnis in den Register-Daten
                                prefixed_calc_id = self._device.name_helper.convert(calc_id, NameType.BASE_NAME)
                                self._register_data[prefixed_calc_id] = result
                                _LOGGER.debug(
                                    "Berechnetes Register aktualisiert",
                                    extra={
                                        "calc_id": calc_id,
                                        "formula": calc_def["formula"],
                                        "variables": variables,
                                        "result": result,
                                        "device": self._device.name
                                    }
                                )
                        else:
                            _LOGGER.debug(
                                "Nicht alle Variablen für Berechnung verfügbar",
                                extra={
                                    "calc_id": calc_id,
                                    "device": self._device.name,
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
                                "device": self._device.name
                            }
                        )
                        
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Verarbeitung der Berechnung",
                        extra={
                            "error": str(e),
                            "calc_id": calc_id,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    continue
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Aktualisierung der berechneten Register",
                extra={
                    "error": str(e),
                    "device": self._device.name,
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
                        prefixed_name = self._device.name_helper.convert(var_name, NameType.BASE_NAME)
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
                                "device": self._device.name
                            }
                        )
                        return
                    
                    # Berechne das Ergebnis mit dem Calculator
                    result = await self._device.calculator.calculate_value(formula, variables)
                    
                except Exception as e:
                    _LOGGER.error(
                        "Fehler bei der Formelverarbeitung",
                        extra={
                            "error": str(e),
                            "calc_id": calc_id,
                            "formula": formula,
                            "device": self._device.name,
                            "traceback": e.__traceback__
                        }
                    )
                    return
                
            # Speichere das Ergebnis wenn vorhanden
            if result is not None:
                prefixed_calc_id = self._device.name_helper.convert(calc_id, NameType.BASE_NAME)
                self._register_data[prefixed_calc_id] = result
                _LOGGER.debug(
                    "Berechnetes Register aktualisiert",
                    extra={
                        "calc_id": calc_id,
                        "type": calc_type,
                        "result": result,
                        "device": self._device.name
                    }
                )
                
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Verarbeitung des Berechnungstyps",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "type": calc_type if 'calc_type' in locals() else None,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    def _store_calculated_value(self, calc_id: str, value: Any) -> None:
        """Speichert einen berechneten Wert."""
        try:
            prefixed_name = self._device.name_helper.convert(calc_id, NameType.BASE_NAME)
            self._register_data[prefixed_name] = value
            
            _LOGGER.debug(
                "Berechneter Wert gespeichert",
                extra={
                    "calc_id": calc_id,
                    "value": value,
                    "device": self._device.name
                }
            )
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Speichern des berechneten Werts",
                extra={
                    "error": str(e),
                    "calc_id": calc_id,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    def get_register_data(self) -> Dict[str, Any]:
        """Gibt die aktuellen Register-Daten zurück."""
        return self._register_data.copy() if hasattr(self, "_register_data") else {}

    @property
    def register_data(self) -> Dict[str, Any]:
        """Gibt die aktuellen Register-Daten zurück."""
        return self._register_data.copy()

    @property
    def registers_by_interval(self) -> Dict[str, List[Dict[str, Any]]]:
        """Gibt die Register gruppiert nach Intervall zurück."""
        return self._registers_by_interval.copy() 