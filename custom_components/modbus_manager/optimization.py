"""Performance optimizations for Modbus Manager."""
from typing import List, Dict, Any
import asyncio
from collections import defaultdict

class ModbusOptimizer:
    """Optimize Modbus operations for better performance."""

    def __init__(self):
        """Initialize optimizer."""
        self.register_cache = {}
        self.operation_queue = defaultdict(list)
        self.batch_size = 125  # Maximum Modbus register count
        self.cache_timeout = 5  # Seconds

    async def optimize_reads(
        self, 
        registers: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Optimize register reads by grouping them efficiently."""
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
            
        return optimized_groups

    def should_use_cache(
        self, 
        register: Dict[str, Any], 
        current_time: float
    ) -> bool:
        """Determine if cached value should be used."""
        if register["name"] not in self.register_cache:
            return False
            
        cache_entry = self.register_cache[register["name"]]
        
        # Always use real-time for certain registers
        if register.get("real_time", False):
            return False
            
        # Check cache age
        if current_time - cache_entry["timestamp"] > self.cache_timeout:
            return False
            
        return True

    def update_cache(
        self, 
        register_name: str, 
        value: Any, 
        timestamp: float
    ) -> None:
        """Update cache with new value."""
        self.register_cache[register_name] = {
            "value": value,
            "timestamp": timestamp
        } 