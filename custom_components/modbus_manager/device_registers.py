"""Modbus Manager Register Processing."""
from __future__ import annotations

import asyncio
import logging
import weakref
from functools import lru_cache
from typing import Any, Dict, List, Optional, TypedDict, Callable

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

    @lru_cache(maxsize=128)
    def _validate_register_definition(self, register: Dict[str, Any]) -> bool:
        """Validiert eine Register-Definition (cached)."""
        try:
            # Prüfe Pflichtfelder
            if not register.get("name"):
                return False
                
            # Prüfe Register-Typ
            reg_type = register.get("type", "uint16")
            if reg_type not in TYPE_CONVERTERS:
                return False
                
            return True
            
        except Exception:
            return False

    def _validate_calculation(self, calc_id: str, calc_def: Dict[str, Any]) -> bool:
        """Validiert eine Berechnungsdefinition."""
        try:
            # Schnellprüfung der Pflichtfelder
            if not all(field in calc_def for field in ["formula", "variables"]):
                _LOGGER.error(
                    "Pflichtfelder fehlen in der Berechnungsdefinition",
                    extra={
                        "calc_id": calc_id,
                        "device": self._device.name,
                        "fields": ["formula", "variables"]
                    }
                )
                return False
                    
            # Optimierte Variablenprüfung
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
                        "device": self._device.name
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
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return False

    async def setup_registers(self, register_definitions: Dict[str, Any]) -> None:
        """Richtet die Register basierend auf der Konfiguration ein."""
        try:
            # Hole die Register-Definitionen
            registers = register_definitions.get("registers", {})
            
            # Initialisiere Intervall-Listen für bessere Performance
            self._registers_by_interval = {
                "fast": [],
                "normal": [],
                "slow": []
            }
            
            # Sammle alle Register für parallele Verarbeitung
            read_registers = registers.get("read", [])
            write_registers = registers.get("write", [])
            all_registers = read_registers + write_registers
            
            # Parallele Validierung aller Register
            validation_tasks = [
                self._validate_and_sort_register(register)
                for register in all_registers
            ]
            await asyncio.gather(*validation_tasks)
            
            # Verarbeite berechnete Register parallel
            calculated = register_definitions.get("calculated_registers", {})
            if calculated:
                calc_tasks = [
                    self._validate_and_store_calculation(calc_id, calc_def)
                    for calc_id, calc_def in calculated.items()
                ]
                await asyncio.gather(*calc_tasks)
                
            # Log Setup-Statistiken
            _LOGGER.debug(
                "Register-Setup abgeschlossen",
                extra={
                    "device": self._device.name,
                    "fast_registers": len(self._registers_by_interval["fast"]),
                    "normal_registers": len(self._registers_by_interval["normal"]),
                    "slow_registers": len(self._registers_by_interval["slow"]),
                    "calculated_registers": len(self._calculated_registers)
                }
            )
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Setup der Register",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def _validate_and_sort_register(self, register: Dict[str, Any]) -> None:
        """Validiert ein Register und sortiert es in das entsprechende Intervall ein."""
        try:
            if self._validate_register_definition(register):
                interval = register.get("interval", "normal")
                self._registers_by_interval[interval].append(register)
            else:
                _LOGGER.error(
                    "Ungültige Register-Definition",
                    extra={
                        "register": register,
                        "device": self._device.name
                    }
                )
                
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Register-Validierung",
                extra={
                    "error": str(e),
                    "register": register,
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def _validate_and_store_calculation(self, calc_id: str, calc_def: Dict[str, Any]) -> None:
        """Validiert eine Berechnung und speichert sie wenn gültig."""
        try:
            if await self._validate_calculation_async(calc_id, calc_def):
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
                            "device": self._device.name,
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
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )
            return None

    async def read_register(self, register: Dict[str, Any], values: Dict[str, Any]) -> None:
        """Liest ein einzelnes Register."""
        try:
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
                
            # Lese den Wert
            value = values.get(prefixed_name)
            if value is None:
                _LOGGER.debug(
                    "Kein Wert für Register gefunden",
                    extra={
                        "register": register_name,
                        "prefixed_name": prefixed_name,
                        "device": self._device.name
                    }
                )
                return
                
            # Verarbeite den Wert
            try:
                processed_value = await self.process_register_value(register_name, register, value)
                if processed_value is not None:
                    self._register_data[prefixed_name] = processed_value
                    
            except Exception as e:
                _LOGGER.error(
                    "Fehler beim Verarbeiten des Register-Werts",
                    extra={
                        "error": str(e),
                        "register": register_name,
                        "prefixed_name": prefixed_name,
                        "device": self._device.name,
                        "traceback": e.__traceback__
                    }
                )
                
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Lesen des Registers",
                extra={
                    "error": str(e),
                    "register": register.get("name"),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def update_registers(self, interval: str) -> None:
        """Aktualisiert die Register für das angegebene Intervall."""
        try:
            # Hole die Register für dieses Intervall
            registers = self._registers_by_interval.get(interval, [])
            
            if not registers:
                _LOGGER.debug(
                    f"Keine Register für Intervall {interval}",
                    extra={
                        "device": self._device.name,
                        "interval": interval
                    }
                )
                return
                
            # Optimierte Batch-Verarbeitung
            batch_size = 10  # Anpassbar basierend auf Performance-Tests
            for i in range(0, len(registers), batch_size):
                batch = registers[i:i + batch_size]
                
                # Lese die Register im Batch
                values = await self._device._hub._read_registers(batch)
                
                # Verarbeite die Werte parallel
                await asyncio.gather(*[
                    self.read_register(register, values)
                    for register in batch
                ])
            
            # Aktualisiere berechnete Register
            await self.update_calculated_registers()
            
            # Passe Cache-Größen an
            self._adjust_cache_sizes()
            
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

    async def update_calculated_registers(self) -> None:
        """Aktualisiert die berechneten Register."""
        try:
            # Optimierte Datensammlung mit Set für schnellere Lookups
            required_sources = {
                var["source"]
                for calc_def in self._calculated_registers.values()
                for var in calc_def["variables"]
            }
            
            # Vorverarbeitung der Quell-Namen
            prefixed_sources = {
                source: self._device.name_helper.convert(source, NameType.BASE_NAME)
                for source in required_sources
            }
            
            # Effiziente Wertesammlung
            available_values = {
                source: self._register_data.get(prefixed_sources[source])
                for source in required_sources
            }
            
            # Parallele Verarbeitung der Berechnungen
            calculations_to_process = [
                (calc_id, calc_def)
                for calc_id, calc_def in self._calculated_registers.items()
                if all(
                    available_values.get(var["source"]) is not None
                    for var in calc_def["variables"]
                )
            ]
            
            if calculations_to_process:
                await asyncio.gather(*[
                    self._process_calculation(
                        calc_id, 
                        calc_def,
                        {
                            var["name"]: available_values[var["source"]]
                            for var in calc_def["variables"]
                        }
                    )
                    for calc_id, calc_def in calculations_to_process
                ])
                    
        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Aktualisierung der berechneten Register",
                extra={
                    "error": str(e),
                    "device": self._device.name,
                    "traceback": e.__traceback__
                }
            )

    async def _process_calculation(self, calc_id: str, calc_def: Dict[str, Any], variables: Dict[str, Any]) -> None:
        """Verarbeitet eine einzelne Berechnung."""
        try:
            formula = calc_def["formula"]
            
            # Berechne den Wert (wird in Calculator-Klasse implementiert)
            try:
                # Platzhalter für die eigentliche Berechnung
                calculated_value = None  # calculator.evaluate(formula, variables)
                
                if calculated_value is not None:
                    # Konvertiere den Register-Namen (cached)
                    prefixed_name = self._device.name_helper.convert(calc_id, NameType.BASE_NAME)
                    self._register_data[prefixed_name] = calculated_value
                    
            except Exception as e:
                _LOGGER.error(
                    "Fehler bei der Berechnung",
                    extra={
                        "error": str(e),
                        "formula": formula,
                        "variables": variables,
                        "calc_id": calc_id,
                        "device": self._device.name,
                        "traceback": e.__traceback__
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

    @property
    def register_data(self) -> Dict[str, Any]:
        """Gibt die aktuellen Register-Daten zurück."""
        return self._register_data.copy()

    @property
    def registers_by_interval(self) -> Dict[str, List[Dict[str, Any]]]:
        """Gibt die Register gruppiert nach Intervall zurück."""
        return self._registers_by_interval.copy() 