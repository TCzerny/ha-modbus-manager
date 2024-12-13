"""Enhanced logging for Modbus Manager."""
import logging
import json
from datetime import datetime
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)

class ModbusLogger:
    """Enhanced logging functionality for Modbus operations."""

    def __init__(self, device_name: str):
        """Initialize logger."""
        self.device_name = device_name
        self.log_buffer = []
        self.max_buffer_size = 100

    def log_operation(
        self, 
        operation: str, 
        registers: list, 
        result: Any, 
        duration: float,
        error: Exception = None
    ) -> None:
        """Log a Modbus operation with details."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "device": self.device_name,
            "operation": operation,
            "registers": registers,
            "duration_ms": round(duration * 1000, 2),
            "success": error is None,
            "error": str(error) if error else None,
            "result": result if not error else None
        }
        
        self.log_buffer.append(log_entry)
        if len(self.log_buffer) > self.max_buffer_size:
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

    def get_statistics(self) -> Dict[str, Any]:
        """Calculate statistics from logged operations."""
        if not self.log_buffer:
            return {}
            
        successful_ops = [op for op in self.log_buffer if op["success"]]
        failed_ops = [op for op in self.log_buffer if not op["success"]]
        
        return {
            "total_operations": len(self.log_buffer),
            "successful_operations": len(successful_ops),
            "failed_operations": len(failed_ops),
            "success_rate": round(len(successful_ops) / len(self.log_buffer) * 100, 2),
            "average_duration": round(
                sum(op["duration_ms"] for op in successful_ops) / len(successful_ops)
                if successful_ops else 0,
                2
            ),
            "most_common_errors": self._get_common_errors(failed_ops)
        }

    def _get_common_errors(self, failed_ops: list) -> Dict[str, int]:
        """Get most common error types."""
        error_counts = {}
        for op in failed_ops:
            error_type = op["error"].split(":")[0]
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        return dict(sorted(
            error_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]) 