"""Register Optimizer for Modbus Manager."""
from __future__ import annotations

from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

@dataclass
class RegisterRange:
    """Represents a range of consecutive registers."""
    start_address: int
    end_address: int
    registers: List[Dict[str, Any]]
    
    @property
    def count(self) -> int:
        """Return the number of registers in this range."""
        return self.end_address - self.start_address + 1
    
    @property
    def register_count(self) -> int:
        """Return the actual register count needed for reading."""
        # Für 32-bit Werte (count > 1) müssen wir die tatsächliche Anzahl berücksichtigen
        total_count = 0
        for reg in self.registers:
            total_count += reg.get("count", 1)
        return total_count

class RegisterOptimizer:
    """Optimizes register reading by grouping consecutive registers."""
    
    def __init__(self, max_read_size: int = 8):
        """Initialize the optimizer."""
        # Ensure max_read_size is an integer
        if isinstance(max_read_size, list):
            self.max_read_size = max_read_size[0] if max_read_size else 8
        else:
            self.max_read_size = max_read_size
        _LOGGER.info("Register-Optimizer initialisiert mit max_read_size: %d", self.max_read_size)
    
    def optimize_registers(self, registers: List[Dict[str, Any]]) -> List[RegisterRange]:
        """Group registers into optimal reading ranges."""
        try:
            if not registers:
                return []
            
            # Register nach Adresse sortieren
            sorted_registers = sorted(registers, key=lambda x: x.get("address", 0))
            
            ranges = []
            current_range = None
            
            for reg in sorted_registers:
                address = reg.get("address", 0)
                count = reg.get("count", 1)
                end_address = address + count - 1
                
                if current_range is None:
                    # Neuen Bereich starten
                    current_range = RegisterRange(
                        start_address=address,
                        end_address=end_address,
                        registers=[reg]
                    )
                else:
                    # Prüfen ob Register an den aktuellen Bereich angehängt werden kann
                    if (address <= current_range.end_address + 1 and 
                        current_range.register_count + count <= self.max_read_size):
                        # Bereich erweitern
                        current_range.end_address = max(current_range.end_address, end_address)
                        current_range.registers.append(reg)
                    else:
                        # Aktuellen Bereich abschließen und neuen starten
                        ranges.append(current_range)
                        current_range = RegisterRange(
                            start_address=address,
                            end_address=end_address,
                            registers=[reg]
                        )
            
            # Letzten Bereich hinzufügen
            if current_range:
                ranges.append(current_range)
            
            _LOGGER.info("Register in %d optimierte Bereiche gruppiert", len(ranges))
            for i, range_obj in enumerate(ranges):
                _LOGGER.debug("Bereich %d: Adresse %d-%d (%d Register)", 
                             i, range_obj.start_address, range_obj.end_address, range_obj.register_count)
            
            return ranges
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Register-Optimierung: %s", str(e))
            # Fallback: Jedes Register einzeln
            return [RegisterRange(
                start_address=reg.get("address", 0),
                end_address=reg.get("address", 0) + reg.get("count", 1) - 1,
                registers=[reg]
            ) for reg in registers]
    
    def get_register_value(self, register: Dict[str, Any], 
                          register_data: List[int], 
                          range_start: int) -> Any:
        """Extract the value for a specific register from the read data."""
        try:
            address = register.get("address", 0)
            count = register.get("count", 1)
            data_type = register.get("data_type", "uint16")
            
            # Relative Position im gelesenen Bereich berechnen
            relative_start = address - range_start
            relative_end = relative_start + count
            
            if relative_end > len(register_data):
                _LOGGER.error("Register-Daten zu kurz für Register %s", address)
                return None
            
            # Register-Daten extrahieren
            if count == 1:
                raw_value = register_data[relative_start]
            else:
                # Für 32-bit Werte (2 Register)
                if relative_start + 1 < len(register_data):
                    if register.get("swap", False):
                        raw_value = (register_data[relative_start + 1] << 16) | register_data[relative_start]
                    else:
                        raw_value = (register_data[relative_start] << 16) | register_data[relative_start + 1]
                else:
                    _LOGGER.error("Nicht genügend Register-Daten für 32-bit Wert")
                    return None
            
            # Daten-Typ-Konvertierung
            if data_type == "int16":
                raw_value = raw_value if raw_value < 32768 else raw_value - 65536
            elif data_type == "int32":
                raw_value = raw_value if raw_value < 2147483648 else raw_value - 4294967296
            
            return raw_value
            
        except Exception as e:
            _LOGGER.error("Fehler beim Extrahieren des Register-Wertes: %s", str(e))
            return None
    
    def calculate_optimization_stats(self, registers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate optimization statistics."""
        try:
            total_registers = len(registers)
            total_addresses = sum(reg.get("count", 1) for reg in registers)
            
            # Ohne Optimierung: Jedes Register einzeln lesen
            reads_without_optimization = total_registers
            
            # Mit Optimierung
            optimized_ranges = self.optimize_registers(registers)
            reads_with_optimization = len(optimized_ranges)
            
            # Performance-Verbesserung berechnen
            improvement = ((reads_without_optimization - reads_with_optimization) / 
                         reads_without_optimization * 100) if reads_without_optimization > 0 else 0
            
            stats = {
                "total_registers": total_registers,
                "total_addresses": total_addresses,
                "reads_without_optimization": reads_without_optimization,
                "reads_with_optimization": reads_with_optimization,
                "improvement_percent": round(improvement, 1),
                "optimized_ranges": len(optimized_ranges)
            }
            
            _LOGGER.info("Optimierungs-Statistiken: %s", stats)
            return stats
            
        except Exception as e:
            _LOGGER.error("Fehler bei der Berechnung der Optimierungs-Statistiken: %s", str(e))
            return {} 