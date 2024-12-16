"""Modbus Proxy for optimizing multiple requests to the same device."""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import time

from .const import (
    MAX_REGISTERS_PER_READ,
    REGISTER_CACHE_TIMEOUT,
    METRICS_RESPONSE_TIME,
    LOGGER_COMMUNICATION
)
from .errors import ModbusDeviceError, handle_modbus_error

_LOGGER = logging.getLogger(__name__)

class ModbusProxy:
    """Proxy class for handling multiple Modbus requests efficiently."""

    def __init__(self, client: Any, slave: int, cache_timeout: float = REGISTER_CACHE_TIMEOUT.total_seconds()):
        """Initialize the proxy.
        
        Args:
            client: Modbus client instance
            slave: Slave ID of the device
            cache_timeout: How long to cache values in seconds
        """
        self._client = client
        self._slave = slave
        self._cache: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self._cache_timeout = cache_timeout
        self._pending_requests: Dict[Tuple[int, int], asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._request_queue: Dict[int, List[Tuple[int, int, asyncio.Future]]] = defaultdict(list)
        self._metrics: Dict[str, float] = defaultdict(float)
        self._batch_size = MAX_REGISTERS_PER_READ

    async def read_registers(
        self, 
        address: int, 
        count: int, 
        unit: Optional[int] = None
    ) -> List[int]:
        """Read registers with request optimization.
        
        Args:
            address: Starting register address
            count: Number of registers to read
            unit: Optional unit ID (defaults to slave ID)
            
        Returns:
            List of register values
        """
        unit = unit or self._slave
        cache_key = (address, count)

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        async with self._lock:
            # Check if there's already a pending request for this range
            if cache_key in self._pending_requests:
                return await self._pending_requests[cache_key]

            # Create new future for this request
            future = asyncio.Future()
            self._pending_requests[cache_key] = future

            # Add to request queue
            self._request_queue[unit].append((address, count, future))

            # Process queue if it's full or after a short delay
            if (len(self._request_queue[unit]) >= 5 or 
                sum(c for _, c, _ in self._request_queue[unit]) >= self._batch_size):
                await self._process_queue(unit)
            else:
                asyncio.create_task(self._delayed_process_queue(unit))

            try:
                return await future
            finally:
                self._pending_requests.pop(cache_key, None)

    async def _delayed_process_queue(self, unit: int) -> None:
        """Process queue after a short delay to allow request batching."""
        await asyncio.sleep(0.01)  # 10ms delay
        async with self._lock:
            if self._request_queue[unit]:
                await self._process_queue(unit)

    async def _process_queue(self, unit: int) -> None:
        """Process all queued requests."""
        if not self._request_queue[unit]:
            return

        # Sort requests by address
        requests = sorted(self._request_queue[unit], key=lambda x: x[0])
        self._request_queue[unit] = []

        # Merge adjacent or overlapping requests
        merged = self._merge_requests(requests)

        # Execute merged requests
        for start_addr, count, futures in merged:
            try:
                start_time = time.time()
                response = await self._client.read_holding_registers(
                    start_addr,
                    count,
                    slave=unit
                )
                duration = time.time() - start_time
                self._metrics[METRICS_RESPONSE_TIME] = duration

                if response.isError():
                    error = ModbusDeviceError(f"Error reading registers: {response}")
                    for future in futures:
                        if not future.done():
                            future.set_exception(error)
                    continue

                # Update cache and resolve futures
                self._update_cache((start_addr, count), response.registers)
                
                # Distribute results to individual futures
                offset = 0
                for orig_addr, orig_count, future in futures:
                    if not future.done():
                        start_idx = orig_addr - start_addr
                        future.set_result(response.registers[start_idx:start_idx + orig_count])

            except Exception as e:
                error = handle_modbus_error(e)
                for future in futures:
                    if not future.done():
                        future.set_exception(error)

    def _merge_requests(
        self, 
        requests: List[Tuple[int, int, asyncio.Future]]
    ) -> List[Tuple[int, int, List[asyncio.Future]]]:
        """Merge adjacent or overlapping register requests."""
        if not requests:
            return []

        merged = []
        current_start = requests[0][0]
        current_end = requests[0][0] + requests[0][1]
        current_futures = [requests[0][2]]

        for addr, count, future in requests[1:]:
            end_addr = addr + count
            
            # Check if request can be merged
            if (addr <= current_end + 5 and  # Allow small gaps
                end_addr - current_start <= self._batch_size):  # Check batch size limit
                current_end = max(current_end, end_addr)
                current_futures.append(future)
            else:
                # Add current batch and start new one
                merged.append((
                    current_start,
                    current_end - current_start,
                    current_futures
                ))
                current_start = addr
                current_end = end_addr
                current_futures = [future]

        # Add last batch
        merged.append((
            current_start,
            current_end - current_start,
            current_futures
        ))

        return merged

    def _get_from_cache(
        self, 
        key: Tuple[int, int]
    ) -> Optional[List[int]]:
        """Get value from cache if still valid."""
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["timestamp"] <= self._cache_timeout:
                return entry["value"]
            else:
                del self._cache[key]
        return None

    def _update_cache(
        self, 
        key: Tuple[int, int], 
        value: List[int]
    ) -> None:
        """Update cache with new value."""
        self._cache[key] = {
            "value": value,
            "timestamp": time.time()
        }

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def get_metrics(self) -> Dict[str, float]:
        """Get proxy metrics."""
        return dict(self._metrics) 