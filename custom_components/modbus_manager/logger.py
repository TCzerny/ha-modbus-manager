"""Enhanced logging for Modbus Manager."""
import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import time

_LOGGER = logging.getLogger(__name__)

class ModbusLogger:
    """Enhanced logging functionality for Modbus operations."""

    def __init__(self, device_name: str, max_buffer_size: int = 100):
        """Initialize logger.
        
        Args:
            device_name: Name of the device being logged
            max_buffer_size: Maximum number of log entries to keep
        """
        self.device_name = device_name
        self.log_buffer: List[Dict[str, Any]] = []
        self.max_buffer_size = max_buffer_size
        self.start_time = time.time()

    def log_operation(
        self, 
        operation: str, 
        registers: List[Dict[str, Any]], 
        result: Optional[Any] = None, 
        duration: Optional[float] = None,
        error: Optional[Exception] = None
    ) -> None:
        """Log a Modbus operation with details."""
        try:
            # Create safe copy of registers without sensitive data
            safe_registers = [
                {k: v for k, v in reg.items() if k not in ("password", "key")}
                for reg in registers
            ]

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "device": self.device_name,
                "operation": operation,
                "registers": safe_registers,
                "duration_ms": round(duration * 1000, 2) if duration else None,
                "success": error is None,
                "error": str(error) if error else None,
                "result": result if not error else None
            }
            
            self.log_buffer.append(log_entry)
            while len(self.log_buffer) > self.max_buffer_size:
                self.log_buffer.pop(0)
                
            if error:
                _LOGGER.error(
                    "Modbus operation failed - Device: %s, Operation: %s, Error: %s",
                    self.device_name, operation, error
                )
            else:
                _LOGGER.debug(
                    "Modbus operation successful - Device: %s, Operation: %s, Duration: %sms",
                    self.device_name, operation, log_entry["duration_ms"]
                )
                
        except Exception as e:
            _LOGGER.error("Error logging Modbus operation: %s", e)

    def get_statistics(self) -> Dict[str, Any]:
        """Calculate statistics from logged operations."""
        try:
            if not self.log_buffer:
                return {
                    "total_operations": 0,
                    "uptime": round(time.time() - self.start_time, 2)
                }
                
            successful_ops = [op for op in self.log_buffer if op["success"]]
            failed_ops = [op for op in self.log_buffer if not op["success"]]
            
            return {
                "total_operations": len(self.log_buffer),
                "successful_operations": len(successful_ops),
                "failed_operations": len(failed_ops),
                "success_rate": round(len(successful_ops) / len(self.log_buffer) * 100, 2),
                "average_duration": round(
                    sum(op["duration_ms"] for op in successful_ops if op["duration_ms"]) 
                    / len([op for op in successful_ops if op["duration_ms"]])
                    if successful_ops and any(op["duration_ms"] for op in successful_ops)
                    else 0,
                    2
                ),
                "most_common_errors": self._get_common_errors(failed_ops),
                "uptime": round(time.time() - self.start_time, 2)
            }
        except Exception as e:
            _LOGGER.error("Error calculating statistics: %s", e)
            return {"error": str(e)}

    def _get_common_errors(self, failed_ops: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get most common error types."""
        try:
            error_counts: Dict[str, int] = {}
            for op in failed_ops:
                if op.get("error"):
                    error_type = op["error"].split(":")[0]
                    error_counts[error_type] = error_counts.get(error_type, 0) + 1
            return dict(sorted(
                error_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5])
        except Exception as e:
            _LOGGER.error("Error processing error counts: %s", e)
            return {} 