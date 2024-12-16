"""Logging utilities for Modbus Manager."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

class ModbusLogger:
    """Class to handle logging for Modbus operations."""

    def __init__(self, name: str):
        """Initialize the logger.
        
        Args:
            name: Name/identifier for this logger instance
        """
        self.name = name
        self._logger = logging.getLogger(f"{__name__}.{name}")

    def debug(self, message: str) -> None:
        """Log debug message."""
        print(f"DEBUG: {message}")  # Temporär für bessere Sichtbarkeit
        self._logger.debug(message)

    def info(self, message: str) -> None:
        """Log info message."""
        self._logger.info(message)

    def warning(self, message: str) -> None:
        """Log warning message."""
        self._logger.warning(message)

    def error(self, message: str) -> None:
        """Log error message."""
        self._logger.error(message)

    def log_operation(
        self,
        operation: str,
        registers: List[Dict[str, Any]],
        result: Optional[Any] = None,
        error: Optional[Exception] = None,
        duration: Optional[float] = None,
    ) -> None:
        """Log a Modbus operation with details.
        
        Args:
            operation: Type of operation (read/write)
            registers: List of registers involved
            result: Operation result (if successful)
            error: Exception (if operation failed)
            duration: Operation duration in seconds
        """
        timestamp = datetime.now().isoformat()
        
        log_data = {
            "timestamp": timestamp,
            "operation": operation,
            "registers": registers,
            "duration": f"{duration:.3f}s" if duration else None
        }

        if error:
            log_data["error"] = str(error)
            self._logger.error(f"Modbus operation failed: {log_data}")
        else:
            log_data["result"] = result
            self._logger.debug(f"Modbus operation completed: {log_data}") 