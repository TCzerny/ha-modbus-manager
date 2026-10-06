"""Tests for scan-interval scheduling in the coordinator."""

from __future__ import annotations

import types
import unittest
from unittest import mock

from custom_components.modbus_manager import coordinator as coordinator_module
from custom_components.modbus_manager.coordinator import ModbusCoordinator


def due_registers(now, last_update_time, registers_by_interval):
    """Run the scheduler against a fake coordinator at monotonic time ``now``."""
    fake = types.SimpleNamespace(
        _cached_registers_by_interval=registers_by_interval,
        _last_update_time=last_update_time,
    )
    loop = mock.Mock()
    loop.time.return_value = now
    with mock.patch.object(
        coordinator_module.asyncio, "get_running_loop", return_value=loop
    ):
        return ModbusCoordinator._get_registers_due_for_update(fake)


class ScanIntervalScheduleTest(unittest.TestCase):
    def setUp(self):
        self.fast = {"unique_id": "fast", "scan_interval": 30}
        self.slow = {"unique_id": "slow", "scan_interval": 3600}
        self.groups = {30: [self.fast], 3600: [self.slow]}

    def test_every_group_is_read_on_first_refresh(self):
        # Monotonic clock below the longest interval, e.g. shortly after boot.
        due = due_registers(120.0, {}, self.groups)
        self.assertEqual(due, [self.fast, self.slow])

    def test_groups_wait_for_their_interval_after_first_read(self):
        last = {30: 120.0, 3600: 120.0}
        self.assertEqual(due_registers(150.0, last, self.groups), [self.fast])
        self.assertEqual(
            due_registers(3720.0, last, self.groups), [self.fast, self.slow]
        )


if __name__ == "__main__":
    unittest.main()
