"""Logger für Modbus Manager."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any


class ModbusManagerLogger(logging.Logger):
    """Custom logger for Modbus Manager."""

    def __init__(self, name: str):
        """Initialize the logger.

        Args:
            name: Name for the logger instance (e.g. 'hub_sungrow1')
        """
        super().__init__(f"custom_components.modbus_manager.{name}")
        self.name = name
        self.logger = logging.getLogger(f"{name}")

        # Übernehme die Einstellungen vom Parent-Logger
        self.parent = logging.getLogger("custom_components.modbus_manager")
        self.setLevel(self.parent.level)
        for handler in self.parent.handlers:
            self.addHandler(handler)

    def _format_message(self, msg: str, *args: Any, **kwargs: Any) -> str:
        """Format log message with additional context.

        Args:
            msg: Message to format
            *args: Positional arguments for string formatting
            **kwargs: Keyword arguments for context and string formatting
        """
        try:
            # Extrahiere Kontext-Daten aus kwargs
            context_items = []
            extra_data = kwargs.get("extra", {})

            for k, v in extra_data.items():
                if isinstance(v, (dict, list)):
                    context_items.append(f"{k}={repr(v)}")
                else:
                    context_items.append(f"{k}={v}")

            context = " ".join(context_items) if context_items else ""

            # Formatiere die Nachricht
            if args:
                formatted_msg = msg % args
            else:
                formatted_msg = msg

            # Füge den Kontext hinzu
            if context:
                return f"[{self.name}] {formatted_msg} extra={{{context}}}"
            else:
                return f"[{self.name}] {formatted_msg}"

        except Exception as e:
            return f"[{self.name}] ERROR FORMATTING MESSAGE: {msg} (Error: {str(e)})"

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        if self.isEnabledFor(logging.DEBUG):
            self.logger.debug(self._format_message(msg, *args, **kwargs))

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        if self.isEnabledFor(logging.INFO):
            self.logger.info(self._format_message(msg, *args, **kwargs))

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        if self.isEnabledFor(logging.WARNING):
            self.logger.warning(self._format_message(msg, *args, **kwargs))

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        if self.isEnabledFor(logging.ERROR):
            self.logger.error(self._format_message(msg, *args, **kwargs))

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an exception message."""
        if self.isEnabledFor(logging.ERROR):
            self.logger.exception(self._format_message(msg, *args, **kwargs))
