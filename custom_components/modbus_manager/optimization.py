"""Performance optimizations for Modbus Manager."""
from typing import List, Dict, Any, Optional
import asyncio
from collections import defaultdict
import time
import logging

_LOGGER = logging.getLogger(__name__)

class ModbusManagerOptimizer:
    """Optimize Modbus operations for better performance."""

    def __init__(self, max_batch_size: int = 125, cache_timeout: int = 5):
        """Initialize optimizer.
        
        Args:
            max_batch_size: Maximum number of registers in one batch (Modbus limit)
            cache_timeout: Number of seconds to keep values in cache
        """
        self.register_cache: Dict[str, Dict[str, Any]] = {}
        self.operation_queue = defaultdict(list)
        self.batch_size = min(max_batch_size, 125)  # Ensure we don't exceed Modbus limit
        self.cache_timeout = max(1, cache_timeout)  # Minimum 1 second timeout
        self._last_optimization = 0
        self._optimization_cache: Optional[List[List[Dict[str, Any]]]] = None

    async def optimize_reads(
        self, 
        registers: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Optimize register reads by grouping them efficiently."""
        try:
            current_time = time.time()
            
            # Use cached optimization if recent
            if (self._optimization_cache and 
                current_time - self._last_optimization < self.cache_timeout and 
                len(registers) == sum(len(group) for group in self._optimization_cache)):
                return self._optimization_cache

            # Sort registers by address
            sorted_registers = sorted(registers, key=lambda x: x["address"])
            
            optimized_groups = []
            current_group = []
            current_size = 0
            
            for register in sorted_registers:
                register_size = register.get("count", 1)
                
                # Check if adding this register exceeds batch size
                if current_size + register_size > self.batch_size:
                    optimized_groups.append(current_group)
                    current_group = [register]
                    current_size = register_size
                else:
                    # Check if register is contiguous with previous
                    if current_group and register["address"] > (
                        current_group[-1]["address"] + 
                        current_group[-1].get("count", 1) + 5
                    ):
                        optimized_groups.append(current_group)
                        current_group = [register]
                        current_size = register_size
                    else:
                        current_group.append(register)
                        current_size += register_size
            
            if current_group:
                optimized_groups.append(current_group)
            
            # Cache the optimization result
            self._optimization_cache = optimized_groups
            self._last_optimization = current_time
            
            return optimized_groups
            
        except Exception as e:
            _LOGGER.error("Error optimizing reads: %s", e)
            # Return single register groups as fallback
            return [[reg] for reg in registers]

    def should_use_cache(
        self, 
        register: Dict[str, Any], 
        current_time: Optional[float] = None
    ) -> bool:
        """Determine if cached value should be used."""
        try:
            if not current_time:
                current_time = time.time()
                
            if register["name"] not in self.register_cache:
                return False
                
            cache_entry = self.register_cache[register["name"]]
            
            # Never cache error values
            if cache_entry.get("error"):
                return False
                
            # Always use real-time for certain registers
            if register.get("real_time", False):
                return False
                
            # Check cache age
            if current_time - cache_entry["timestamp"] > self.cache_timeout:
                return False
                
            return True
            
        except Exception as e:
            _LOGGER.error("Error checking cache: %s", e)
            return False

    def update_cache(
        self, 
        register_name: str, 
        value: Any, 
        timestamp: Optional[float] = None,
        error: Optional[Exception] = None
    ) -> None:
        """Update cache with new value."""
        try:
            if not timestamp:
                timestamp = time.time()
                
            self.register_cache[register_name] = {
                "value": value,
                "timestamp": timestamp,
                "error": str(error) if error else None
            }
        except Exception as e:
            _LOGGER.error("Error updating cache: %s", e) 