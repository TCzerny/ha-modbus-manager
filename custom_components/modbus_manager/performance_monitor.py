"""Performance Monitor for Modbus Manager."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a single operation."""

    operation_type: str
    start_time: float
    end_time: Optional[float] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None
    register_count: int = 0
    bytes_transferred: int = 0

    @property
    def duration(self) -> float:
        """Return operation duration in seconds."""
        if self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    @property
    def throughput(self) -> float:
        """Return throughput in bytes per second."""
        if self.duration <= 0:
            return 0.0
        return self.bytes_transferred / self.duration


@dataclass
class DeviceMetrics:
    """Metrics for a specific device."""

    device_id: str
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    total_duration: float = 0.0
    total_bytes: int = 0
    operations: List[OperationMetrics] = field(default_factory=list)
    last_operation: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Return success rate as percentage."""
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100

    @property
    def average_duration(self) -> float:
        """Return average operation duration."""
        if self.total_operations == 0:
            return 0.0
        return self.total_duration / self.total_operations

    @property
    def average_throughput(self) -> float:
        """Return average throughput in bytes per second."""
        if self.total_duration <= 0:
            return 0.0
        return self.total_bytes / self.total_duration


class PerformanceMonitor:
    """Monitors performance of Modbus operations."""

    def __init__(self, max_history: int = 1000):
        """Initialize the performance monitor."""
        self.max_history = max_history
        self.devices: Dict[str, DeviceMetrics] = {}
        self.global_metrics = DeviceMetrics(device_id="global")
        _LOGGER.debug(
            "Performance-Monitor initialisiert mit max_history: %d", max_history
        )

    def start_operation(
        self,
        device_id: str,
        operation_type: str,
        register_count: int = 0,
        bytes_transferred: int = 0,
    ) -> str:
        """Start monitoring an operation."""
        try:
            # Device-Metriken erstellen falls nicht vorhanden
            if device_id not in self.devices:
                self.devices[device_id] = DeviceMetrics(device_id=device_id)

            # Operation starten
            operation = OperationMetrics(
                operation_type=operation_type,
                start_time=time.time(),
                register_count=register_count,
                bytes_transferred=bytes_transferred,
            )

            # Operation-ID generieren
            operation_id = (
                f"{device_id}_{operation_type}_{int(operation.start_time * 1000)}"
            )

            # Metriken aktualisieren
            self.devices[device_id].operations.append(operation)
            self.global_metrics.operations.append(operation)

            # History begrenzen
            self._limit_history(device_id)
            self._limit_global_history()

            _LOGGER.debug("Operation gestartet: %s", operation_id)
            return operation_id

        except Exception as e:
            _LOGGER.error("Fehler beim Starten der Operation: %s", str(e))
            return ""

    def end_operation(
        self,
        device_id: str,
        operation_id: str,
        success: bool,
        error_message: str = None,
    ) -> None:
        """End monitoring an operation."""
        try:
            # Operation in Device-Metriken finden
            device_metrics = self.devices.get(device_id)
            if device_metrics:
                for operation in device_metrics.operations:
                    if operation.end_time is None:  # Noch nicht beendet
                        operation.end_time = time.time()
                        operation.success = success
                        operation.error_message = error_message

                        # Device-Metriken aktualisieren
                        device_metrics.total_operations += 1
                        device_metrics.total_duration += operation.duration
                        device_metrics.total_bytes += operation.bytes_transferred
                        device_metrics.last_operation = datetime.now()

                        if success:
                            device_metrics.successful_operations += 1
                        else:
                            device_metrics.failed_operations += 1

                        break

            # Global-Metriken aktualisieren
            for operation in self.global_metrics.operations:
                if operation.end_time is None:  # Noch nicht beendet
                    operation.end_time = time.time()
                    operation.success = success
                    operation.error_message = error_message

                    # Global-Metriken aktualisieren
                    self.global_metrics.total_operations += 1
                    self.global_metrics.total_duration += operation.duration
                    self.global_metrics.total_bytes += operation.bytes_transferred
                    self.global_metrics.last_operation = datetime.now()

                    if success:
                        self.global_metrics.successful_operations += 1
                    else:
                        self.global_metrics.failed_operations += 1

                    break

            _LOGGER.debug("Operation beendet: %s (Success: %s)", operation_id, success)

        except Exception as e:
            _LOGGER.error("Fehler beim Beenden der Operation: %s", str(e))

    def get_device_metrics(self, device_id: str) -> Optional[DeviceMetrics]:
        """Get metrics for a specific device."""
        return self.devices.get(device_id)

    def get_global_metrics(self) -> DeviceMetrics:
        """Get global metrics."""
        return self.global_metrics

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of all performance metrics."""
        try:
            summary = {
                "global": {
                    "total_operations": self.global_metrics.total_operations,
                    "success_rate": round(self.global_metrics.success_rate, 2),
                    "average_duration": round(self.global_metrics.average_duration, 3),
                    "average_throughput": round(
                        self.global_metrics.average_throughput, 2
                    ),
                    "last_operation": self.global_metrics.last_operation.isoformat()
                    if self.global_metrics.last_operation
                    else None,
                },
                "devices": {},
            }

            for device_id, device_metrics in self.devices.items():
                summary["devices"][device_id] = {
                    "total_operations": device_metrics.total_operations,
                    "success_rate": round(device_metrics.success_rate, 2),
                    "average_duration": round(device_metrics.average_duration, 3),
                    "average_throughput": round(device_metrics.average_throughput, 2),
                    "last_operation": device_metrics.last_operation.isoformat()
                    if device_metrics.last_operation
                    else None,
                }

            return summary

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen der Performance-Zusammenfassung: %s", str(e)
            )
            return {}

    def get_recent_operations(
        self, device_id: str = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent operations for a device or globally."""
        try:
            if device_id:
                device_metrics = self.devices.get(device_id)
                if not device_metrics:
                    return []
                operations = device_metrics.operations
            else:
                operations = self.global_metrics.operations

            # Neueste Operationen zuerst
            recent_operations = sorted(
                [op for op in operations if op.end_time is not None],
                key=lambda x: x.end_time,
                reverse=True,
            )[:limit]

            return [
                {
                    "operation_type": op.operation_type,
                    "duration": round(op.duration, 3),
                    "success": op.success,
                    "error_message": op.error_message,
                    "register_count": op.register_count,
                    "throughput": round(op.throughput, 2),
                    "timestamp": datetime.fromtimestamp(op.start_time).isoformat(),
                }
                for op in recent_operations
            ]

        except Exception as e:
            _LOGGER.error("Fehler beim Abrufen der letzten Operationen: %s", str(e))
            return []

    def _limit_history(self, device_id: str) -> None:
        """Limit operation history for a device."""
        device_metrics = self.devices.get(device_id)
        if device_metrics and len(device_metrics.operations) > self.max_history:
            # Älteste Operationen entfernen
            device_metrics.operations = device_metrics.operations[-self.max_history :]

    def _limit_global_history(self) -> None:
        """Limit global operation history."""
        if len(self.global_metrics.operations) > self.max_history:
            # Älteste Operationen entfernen
            self.global_metrics.operations = self.global_metrics.operations[
                -self.max_history :
            ]

    def reset_metrics(self, device_id: str = None) -> None:
        """Reset metrics for a device or globally."""
        try:
            if device_id:
                if device_id in self.devices:
                    self.devices[device_id] = DeviceMetrics(device_id=device_id)
                    _LOGGER.debug("Metriken für Device %s zurückgesetzt", device_id)
            else:
                self.devices.clear()
                self.global_metrics = DeviceMetrics(device_id="global")
                _LOGGER.debug("Alle Metriken zurückgesetzt")

        except Exception as e:
            _LOGGER.error("Fehler beim Zurücksetzen der Metriken: %s", str(e))
