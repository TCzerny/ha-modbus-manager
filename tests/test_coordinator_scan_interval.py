"""Tests for scan-group scheduling in the coordinator."""

from __future__ import annotations

import types
import unittest
from unittest import mock

from custom_components.modbus_manager import coordinator as coordinator_module
from custom_components.modbus_manager.const import (
    DEFAULT_SCAN_GROUP_SECONDS,
    SCAN_GROUP_FAST,
    SCAN_GROUP_SLOW,
)
from custom_components.modbus_manager.coordinator import ModbusCoordinator


def due_registers(now, last_update_time, registers_by_group, seconds=None):
    """Run the scheduler against a fake coordinator at monotonic time ``now``."""
    fake = types.SimpleNamespace(
        _cached_registers_by_scan_group=registers_by_group,
        _last_update_time=last_update_time,
        _scan_group_seconds=seconds or dict(DEFAULT_SCAN_GROUP_SECONDS),
    )
    loop = mock.Mock()
    loop.time.return_value = now
    with mock.patch.object(
        coordinator_module.asyncio, "get_running_loop", return_value=loop
    ):
        return ModbusCoordinator._get_registers_due_for_update(fake)


class ScanIntervalScheduleTest(unittest.TestCase):
    def setUp(self):
        self.fast = {"unique_id": "fast", "scan_group": SCAN_GROUP_FAST}
        self.slow = {"unique_id": "slow", "scan_group": SCAN_GROUP_SLOW}
        self.groups = {SCAN_GROUP_FAST: [self.fast], SCAN_GROUP_SLOW: [self.slow]}
        self.seconds = {SCAN_GROUP_FAST: 30, SCAN_GROUP_SLOW: 3600, "medium": 30}

    def test_every_group_is_read_on_first_refresh(self):
        due = due_registers(120.0, {}, self.groups, self.seconds)
        self.assertEqual(due, [self.fast, self.slow])

    def test_groups_wait_for_their_interval_after_first_read(self):
        last = {SCAN_GROUP_FAST: 120.0, SCAN_GROUP_SLOW: 120.0}
        self.assertEqual(
            due_registers(150.0, last, self.groups, self.seconds), [self.fast]
        )
        self.assertEqual(
            due_registers(3720.0, last, self.groups, self.seconds),
            [self.fast, self.slow],
        )


if __name__ == "__main__":
    unittest.main()
