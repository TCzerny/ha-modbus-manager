"""Logging utilities for Modbus Manager."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

class ModbusManagerLogger(logging.Logger):
    """Custom logger for Modbus Manager."""

    def __init__(self, name: str):
        """Initialize the logger.
        
        Args:
            name: Name for the logger instance (e.g. 'hub_sungrow1')
        """
        super().__init__(f"custom_components.modbus_manager.{name}")
        self.name = name
        self.logger = logging.getLogger(f"custom_components.modbus_manager.{name}")
        
        # Übernehme die Einstellungen vom Parent-Logger
        self.parent = logging.getLogger("custom_components.modbus_manager")
        self.setLevel(self.parent.level)
        for handler in self.parent.handlers:
            self.addHandler(handler)

    def _format_message(self, msg: str, *args: Any, **kwargs: Any) -> str:
        """Format log message with additional context.
        
        Args:
            msg: Message to format (can be an f-string)
            *args: Positional arguments for string formatting
            **kwargs: Keyword arguments for context and string formatting
        """
        try:
            # Loggen der übergebenen Argumente
            self.logger.debug(f"Formatting message with args: {args} and kwargs: {kwargs}")
            
            # Sicherstellen, dass args nur iterierbare Objekte enthalten
            safe_args = [arg for arg in args if isinstance(arg, (list, tuple, dict))]
            if safe_args or ('{' in msg and '}' in msg):
                msg = msg.format(*safe_args, **{k: v for k, v in kwargs.items() if not isinstance(v, (dict, list))})
            
            # Extrahiere Kontext-Daten aus kwargs
            context_items = []
            for k, v in kwargs.items():
                if isinstance(v, (dict, list)):
                    context_items.append(f"{k}={repr(v)}")
                else:
                    context_items.append(f"{k}={v}")
            
            context = ' '.join(context_items) if context_items else ''
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            return f"[{self.name}] {msg} {context}".strip()
            
        except Exception as e:
            return f"[{self.name}] ERROR FORMATTING MESSAGE: {msg} (Error: {str(e)})"

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message.
        
        Args:
            msg: Message to log (can be an f-string)
            *args: Positional arguments for string formatting
            **kwargs: Keyword arguments for context and string formatting
        """
        if self.isEnabledFor(logging.DEBUG):
            self.logger.debug(self._format_message(msg, *args, **kwargs))

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log info message.
        
        Args:
            msg: Message to log (can be an f-string)
            *args: Positional arguments for string formatting
            **kwargs: Keyword arguments for context and string formatting
        """
        if self.isEnabledFor(logging.INFO):
            self.logger.info(self._format_message(msg, *args, **kwargs))

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message.
        
        Args:
            msg: Message to log (can be an f-string)
            *args: Positional arguments for string formatting
            **kwargs: Keyword arguments for context and string formatting
        """
        if self.isEnabledFor(logging.WARNING):
            self.logger.warning(self._format_message(msg, *args, **kwargs))

    def error(self, msg: str, *args: Any, error: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log error message with optional exception.
        
        Args:
            msg: Message to log (can be an f-string)
            *args: Positional arguments for string formatting
            error: Optional exception to include in the log
            **kwargs: Keyword arguments for context and string formatting
        """
        if self.isEnabledFor(logging.ERROR):
            if error:
                kwargs['error'] = str(error)
                kwargs['error_type'] = type(error).__name__
            self.logger.error(self._format_message(msg, *args, **kwargs))

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback.
        
        Args:
            msg: Message to log (can be an f-string)
            *args: Positional arguments for string formatting
            **kwargs: Keyword arguments for context and string formatting
        """
        if self.isEnabledFor(logging.ERROR):
            self.logger.exception(self._format_message(msg, *args, **kwargs))

    def log_operation(
        self,
        operation: str,
        registers: List[Dict[str, Any]],
        result: Optional[Any] = None,
        error: Optional[Exception] = None,
        duration: Optional[float] = None,
        **kwargs: Any
    ) -> None:
        """Log a Modbus operation with details.
        
        Args:
            operation: Type of operation (read/write)
            registers: List of registers involved
            result: Operation result (if successful)
            error: Exception (if operation failed)
            duration: Operation duration in seconds
            **kwargs: Additional context information
        """
        log_data = {
            "operation": operation,
            "registers": [
                {
                    "name": reg.get("name", "unknown"),
                    "address": reg.get("address", 0),
                    "type": reg.get("type", "unknown")
                }
                for reg in registers
            ],
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }

        if duration is not None:
            log_data["duration"] = f"{duration:.3f}s"

        if error:
            log_data["error"] = str(error)
            log_data["error_type"] = type(error).__name__
            self.error(
                f"Modbus {operation} operation failed",
                **log_data
            )
        else:
            log_data["result"] = result
            self.debug(
                f"Modbus {operation} operation completed",
                **log_data
            )

    def log_batch_operation(
        self,
        operation: str,
        register_groups: List[List[Dict[str, Any]]],
        results: Optional[List[Any]] = None,
        errors: Optional[List[Exception]] = None,
        duration: Optional[float] = None,
        **kwargs: Any
    ) -> None:
        """Log a batch Modbus operation.
        
        Args:
            operation: Type of operation (read/write)
            register_groups: List of register groups
            results: List of results (if successful)
            errors: List of exceptions (if any failed)
            duration: Total operation duration in seconds
            **kwargs: Additional context information
        """
        log_data = {
            "operation": f"batch_{operation}",
            "group_count": len(register_groups),
            "total_registers": sum(len(group) for group in register_groups),
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }

        if duration is not None:
            log_data["duration"] = f"{duration:.3f}s"
            log_data["avg_group_duration"] = f"{duration/len(register_groups):.3f}s"

        if errors and any(errors):
            log_data["errors"] = [str(e) for e in errors if e]
            log_data["error_count"] = sum(1 for e in errors if e)
            self.error(
                f"Batch {operation} operation partially failed",
                **log_data
            )
        else:
            log_data["success_count"] = len(results) if results else 0
            self.debug(
                f"Batch {operation} operation completed",
                **log_data
            )