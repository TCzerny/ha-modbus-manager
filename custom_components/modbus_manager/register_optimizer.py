"""Register Optimizer for Modbus Manager."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

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
        # For string registers and other multi-register types, consider the actual count
        total_count = 0
        for reg in self.registers:
            data_type = reg.get("data_type", "uint16")
            count = reg.get("count", 1)

            # Always set correct count based on data type, regardless of template
            if data_type in ["uint32", "int32", "float", "float32"]:
                # 32-bit values: always 2 registers
                total_count += 2
            elif data_type == "float64":
                # 64-bit values: always 4 registers
                total_count += 4
            elif data_type == "string":
                # String registers: count is the number of registers to read
                total_count += count if count is not None else 1
            else:
                # Standard: 1 register
                total_count += 1
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
        _LOGGER.debug(
            "Register optimizer initialized with max_read_size: %d", self.max_read_size
        )

    def optimize_registers(
        self, registers: List[Dict[str, Any]]
    ) -> List[RegisterRange]:
        """Group registers into optimal reading ranges."""
        try:
            if not registers:
                return []

            # Sort registers by address
            sorted_registers = sorted(registers, key=lambda x: x.get("address", 0))

            ranges = []
            current_range = None

            for reg in sorted_registers:
                address = reg.get("address", 0)
                count = reg.get("count", 1)
                if count is None:
                    count = 1
                end_address = address + count - 1

                if current_range is None:
                    # Start new range
                    current_range = RegisterRange(
                        start_address=address, end_address=end_address, registers=[reg]
                    )
                else:
                    # Check if register can be appended to current range
                    if (
                        address <= current_range.end_address + 1
                        and current_range.register_count + (count or 1)
                        <= self.max_read_size
                    ):
                        # Extend range
                        current_range.end_address = max(
                            current_range.end_address, end_address
                        )
                        current_range.registers.append(reg)
                    else:
                        # Finish current range and start new one
                        ranges.append(current_range)
                        current_range = RegisterRange(
                            start_address=address,
                            end_address=end_address,
                            registers=[reg],
                        )

            # Add last range
            if current_range:
                ranges.append(current_range)

            _LOGGER.debug("Registers grouped into %d optimized ranges", len(ranges))
            for i, range_obj in enumerate(ranges):
                _LOGGER.debug(
                    "Range %d: Address %d-%d (%d registers)",
                    i,
                    range_obj.start_address,
                    range_obj.end_address,
                    range_obj.register_count,
                )

            return ranges

        except Exception as e:
            _LOGGER.error("Error during register optimization: %s", str(e))
            # Fallback: Each register individually
            return [
                RegisterRange(
                    start_address=reg.get("address", 0),
                    end_address=reg.get("address", 0) + (reg.get("count", 1) or 1) - 1,
                    registers=[reg],
                )
                for reg in registers
            ]

    def get_register_value(
        self, register: Dict[str, Any], register_data: List[int], range_start: int
    ) -> Any:
        """Extract the value for a specific register from the read data."""
        try:
            address = register.get("address", 0)
            count = register.get("count", 1)
            if count is None:
                count = 1
            data_type = register.get("data_type", "uint16")

            # Always set correct count based on data type, regardless of template
            if data_type in ["uint32", "int32", "float", "float32"]:
                count = 2  # 32-bit types need 2 registers
            elif data_type == "float64":
                count = 4  # 64-bit types need 4 registers

            # Calculate relative position in read range
            relative_start = address - range_start
            relative_end = relative_start + count

            if relative_end > len(register_data):
                _LOGGER.error("Register data too short for register %s", address)
                return None

            # Extract register data
            if data_type == "string":
                # For string registers: return all registers as list
                raw_value = register_data[relative_start:relative_end]
            elif data_type in ["uint32", "int32", "float", "float32"]:
                # For 32-bit values (2 registers) - return raw register data as list
                if relative_start + 1 < len(register_data):
                    raw_value = register_data[relative_start : relative_start + 2]
                else:
                    _LOGGER.error("Insufficient register data for 32-bit value")
                    return None
            elif data_type == "float64":
                # For 64-bit values (4 registers)
                if relative_start + 3 < len(register_data):
                    raw_value = register_data[relative_start:relative_end]
                else:
                    _LOGGER.error("Insufficient register data for 64-bit value")
                    return None
            else:
                # Standard: 1 register
                raw_value = register_data[relative_start]

            # Data type conversion (only for numeric values)
            if data_type == "int16":
                raw_value = raw_value if raw_value < 32768 else raw_value - 65536
            elif data_type == "int32":
                raw_value = (
                    raw_value if raw_value < 2147483648 else raw_value - 4294967296
                )

            return raw_value

        except Exception as e:
            _LOGGER.error("Error extracting register value: %s", str(e))
            return None

    def calculate_optimization_stats(
        self, registers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate optimization statistics."""
        try:
            total_registers = len(registers)
            total_addresses = sum(reg.get("count", 1) or 1 for reg in registers)

            # Without optimization: read each register individually
            reads_without_optimization = total_registers

            # With optimization
            optimized_ranges = self.optimize_registers(registers)
            reads_with_optimization = len(optimized_ranges)

            # Calculate performance improvement
            improvement = (
                (
                    (reads_without_optimization - reads_with_optimization)
                    / reads_without_optimization
                    * 100
                )
                if reads_without_optimization > 0
                else 0
            )

            stats = {
                "total_registers": total_registers,
                "total_addresses": total_addresses,
                "reads_without_optimization": reads_without_optimization,
                "reads_with_optimization": reads_with_optimization,
                "improvement_percent": round(improvement, 1),
                "optimized_ranges": len(optimized_ranges),
            }

            _LOGGER.debug("Optimization statistics: %s", stats)
            return stats

        except Exception as e:
            _LOGGER.error("Error calculating optimization statistics: %s", str(e))
            return {}
