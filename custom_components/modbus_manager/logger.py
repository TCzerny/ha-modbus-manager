"""Logging utilities for Modbus Manager."""
import logging
from datetime import datetime
from typing import Any, Optional

class ModbusManagerLogger:
    """Custom logger for Modbus Manager."""

    def __init__(self, name: str):
        """Initialize the logger.
        
        Args:
            name: Name for the logger instance (e.g. 'hub_sungrow1')
        """
        self.logger = logging.getLogger(f"custom_components.modbus_manager.{name}")
        self.name = name

    def _format_message(self, msg: str, **kwargs: Any) -> str:
        """Format log message with additional context."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        context = ' '.join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ''
        return f"[{self.name}] {msg} {context}".strip()

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(self._format_message(msg, **kwargs))

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(self._format_message(msg, **kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(self._format_message(msg, **kwargs))

    def error(self, msg: str, error: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log error message with optional exception."""
        if error:
            kwargs['error'] = str(error)
            kwargs['error_type'] = type(error).__name__
        self.logger.error(self._format_message(msg, **kwargs))

    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self.logger.exception(self._format_message(msg, **kwargs))