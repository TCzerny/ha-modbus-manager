"""Tests for cyclic writes (keepalive), without a Home Assistant runtime.

Every scenario runs in one event loop. The fake coordinator uses a real
asyncio.Lock and evaluates the write guard under it, like
ModbusCoordinator.async_pb_write.
"""

from __future__ import annotations

import asyncio
import importlib.util
import math
import struct
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components/modbus_manager"
PKG = "keepalive_test_pkg"


def _load_package():
    """Load keepalive.py with the real logger/modbus_utils and stubbed HA modules."""
    for name in ("homeassistant", "homeassistant.components", "homeassistant.components.modbus"):
        sys.modules.setdefault(name, types.ModuleType(name))
    const = types.ModuleType("homeassistant.components.modbus.const")
    for attr in (
        "CALL_TYPE_REGISTER_HOLDING",
        "CALL_TYPE_REGISTER_INPUT",
        "CALL_TYPE_WRITE_REGISTERS",
        "CALL_TYPE_WRITE_REGISTER",
    ):
        setattr(const, attr, attr.lower())
    sys.modules["homeassistant.components.modbus.const"] = const

    package = types.ModuleType(PKG)
    package.__path__ = []
    sys.modules[PKG] = package

    device_utils = types.ModuleType(f"{PKG}.device_utils")
    device_utils.hub_is_connected = lambda hub: bool(getattr(hub, "connected", True))
    sys.modules[device_utils.__name__] = device_utils

    for module in ("logger", "modbus_utils", "keepalive"):
        spec = importlib.util.spec_from_file_location(f"{PKG}.{module}", PKG_DIR / f"{module}.py")
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = loaded
        spec.loader.exec_module(loaded)
    return sys.modules[f"{PKG}.keepalive"]


ka = _load_package()
GID = "t_bat_keepalive"


class FakeHub:
    def __init__(self):
        self.connected = True


class FakeCoordinator:
    """Mimics async_pb_write: IO lock, guard checked under the lock."""

    def __init__(self):
        self.hass = None  # no timer; tests drive rounds directly
        self.hub = FakeHub()
        self._is_unloading = False
        self.last_update_success = True
        self.register_data = {}
        self.writes = []
        self.write_result = True
        self.lock = asyncio.Lock()

    def get_register_data(self, key):
        return self.register_data.get(key)

    async def async_pb_write(self, slave_id, address, value, call_type, *, refresh=True, guard=None):
        async with self.lock:
            if guard is not None and (self._is_unloading or not guard()):
                return False
            self.writes.append((slave_id, address, value, call_type, refresh))
            await asyncio.sleep(0)
            return self.write_result


class Clock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def time(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(round(seconds, 6))
        self.now += seconds
        await asyncio.sleep(0)


GROUP_CFG = {"name": "External battery control", "interval": 15.0, "min_write_spacing_ms": 1000.0, "max_failures": 3}


def number_config(uid="t_limit", address=1026, **keepalive):
    return {
        "unique_id": uid,
        "type": "number",
        "address": address,
        "slave_id": 71,
        "data_type": "float32",
        "count": 2,
        "byte_order": "big",
        "swap": "word",
        "keepalive": {"group": "bat", "group_id": GID, "release": "stop", **keepalive},
    }


def make_manager():
    coordinator = FakeCoordinator()
    clock = Clock()
    manager = ka.KeepaliveManager(coordinator, loop_time=clock.time, wall_time=clock.time, sleep=clock.sleep)
    manager.register_groups({GID: dict(GROUP_CFG)})
    coordinator.keepalive = manager
    return coordinator, manager, clock


def decode_float_cdab(words):
    return struct.unpack(">f", struct.pack(">HH", words[1], words[0]))[0]


async def settle(task):
    if task is not None:
        try:
            await task
        except asyncio.CancelledError:
            pass


def run(coro_fn):
    return asyncio.run(coro_fn())


class ValidationTest(unittest.TestCase):
    def test_groups_and_controls(self):
        controls = [
            {"type": "number", "unique_id": "a", "keepalive": {"group": "bat"}},
            {"type": "number", "unique_id": "b", "keepalive": {"group": "missing"}},
            {"type": "select", "unique_id": "c", "keepalive": {"group": "bat", "clamp_max_to_register": "soc"}},
            {"type": "button", "unique_id": "d", "keepalive": {"group": "bat"}},
            {"type": "number", "unique_id": "e", "keepalive": {"group": "bat", "release": "write"}},
            {"type": "number", "unique_id": "f", "input_type": "input", "keepalive": {"group": "bat"}},
            {"type": "number", "unique_id": "g"},
            {"type": "number", "unique_id": "h", "keepalive": {"group": "bat", "release": "write", "release_value": "nan"}},
        ]
        groups = ka.validate_template_keepalive(
            {"bat": {"interval": 15}, "fast": {"interval": 1}, "bad": "x", "inf": {"interval": "inf"}},
            controls,
            "t",
        )
        self.assertEqual(set(groups), {"bat"})
        self.assertEqual(groups["bat"]["min_write_spacing_ms"], 1000)
        self.assertEqual(groups["bat"]["max_failures"], 3)
        self.assertEqual(controls[0]["keepalive"], {"group": "bat", "release": "stop"})
        for index in (1, 2, 3, 4, 5, 6, 7):
            self.assertNotIn("keepalive", controls[index], controls[index]["unique_id"])

    def test_release_write_and_clamp(self):
        controls = [
            {
                "type": "number",
                "unique_id": "a",
                "keepalive": {
                    "group": "bat",
                    "release": "write",
                    "release_value": "0",
                    "clamp_max_to_register": " battery_soc ",
                    "clamp_max_age": 30,
                },
            }
        ]
        ka.validate_template_keepalive({"bat": {"interval": 20}}, controls, "t")
        self.assertEqual(
            controls[0]["keepalive"],
            {
                "group": "bat",
                "release": "write",
                "release_value": 0.0,
                "clamp_max_to_register": "battery_soc",
                "clamp_max_age": 30.0,
            },
        )

    def test_resume_after_restart_is_not_supported_but_group_kept(self):
        groups = ka.validate_keepalive_groups({"bat": {"interval": 15, "resume_after_restart": True}}, "t")
        self.assertIn("bat", groups)
        self.assertNotIn("resume_after_restart", groups["bat"])

    def test_tick_runs_in_event_loop(self):
        # Home Assistant runs non-callback timer targets in an executor thread.
        self.assertTrue(getattr(ka.KeepaliveManager._handle_tick, "_hass_callback", False))


class BasicRuntimeTest(unittest.TestCase):
    def test_store_ignores_controls_without_keepalive(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            config = number_config()
            config.pop("keepalive")
            ka.store_keepalive_setpoint(coordinator, "k", config, 5, "number")
            self.assertEqual(manager.groups[GID].setpoints, {})

        run(scenario)

    def test_no_repeat_while_switch_off(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await manager.async_run_round(GID)
            self.assertEqual(coordinator.writes, [])
            self.assertEqual(manager.due_groups(), [])

        run(scenario)

    def test_activate_writes_all_setpoints_with_spacing(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k1", number_config("a", 1038), 0, "number")
            ka.store_keepalive_setpoint(coordinator, "k2", number_config("b", 1040), 2500, "number")
            await settle(manager.async_activate(GID))
            self.assertTrue(manager.is_active(GID))
            self.assertEqual([w[1] for w in coordinator.writes], [1038, 1040])
            self.assertTrue(all(w[4] is False for w in coordinator.writes))  # refresh=False
            self.assertEqual(clock.sleeps, [1.0])
            self.assertAlmostEqual(decode_float_cdab(coordinator.writes[1][2]), 2500.0)

        run(scenario)

    def test_spacing_enforced_between_rounds(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            clock.now += 0.4  # a round right after the previous write
            await manager.async_run_round(GID)
            self.assertEqual(len(coordinator.writes), 2)
            self.assertEqual(clock.sleeps, [0.6])

        run(scenario)

    def test_activate_is_idempotent(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            first = manager.async_activate(GID)
            second = manager.async_activate(GID)
            self.assertIsNone(second)
            await settle(first)
            self.assertEqual(len(coordinator.writes), 1)

        run(scenario)

    def test_due_groups_follow_interval(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            clock.now += 14
            self.assertEqual(manager.due_groups(), [])
            clock.now += 1
            self.assertEqual(manager.due_groups(), [GID])

        run(scenario)

    def test_repeated_write_failures_stop_group(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            coordinator.write_result = False
            await settle(manager.async_activate(GID))
            for _ in range(2):
                clock.now += 15
                await manager.async_run_round(GID)
            group = manager.groups[GID]
            self.assertEqual(group.state, ka.STATE_STOPPED)
            self.assertEqual(group.stop_reason, "repeated write failures")
            self.assertEqual(group.setpoints, {})
            self.assertEqual(group.failed_writes, 3)

        run(scenario)

    def test_one_mismatch_keeps_setpoint_repeated_mismatches_stop(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            group = manager.groups[GID]

            clock.now += 15
            coordinator.register_data["k"] = {"processed_value": 15300.0, "timestamp": clock.now - 1}
            await manager.async_run_round(GID)
            self.assertEqual(group.mismatches, 1)
            self.assertIn("k", group.setpoints)
            self.assertEqual(group.state, ka.STATE_ACTIVE)

            for _ in range(2):
                clock.now += 15
                coordinator.register_data["k"] = {"processed_value": 15300.0, "timestamp": clock.now - 1}
                await manager.async_run_round(GID)
            self.assertEqual(group.state, ka.STATE_STOPPED)
            self.assertEqual(group.stop_reason, "repeated read-back mismatches")

        run(scenario)

    def test_effective_value_within_tolerance_is_not_a_mismatch(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 1000, "number")
            await settle(manager.async_activate(GID))
            clock.now += 15
            coordinator.register_data["k"] = {"processed_value": 999.1, "timestamp": clock.now - 1}
            await manager.async_run_round(GID)
            self.assertEqual(manager.groups[GID].mismatches, 0)

        run(scenario)

    def test_select_raw_value_and_scaled_number(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            keepalive = {"group": "bat", "group_id": GID, "release": "stop"}
            select_cfg = {"unique_id": "mode", "type": "select", "address": 2000, "data_type": "uint16", "keepalive": keepalive}
            scaled_cfg = {"unique_id": "power", "type": "number", "address": 3000, "data_type": "uint16", "scale": 0.1, "keepalive": keepalive}
            ka.store_keepalive_setpoint(coordinator, "k1", select_cfg, 2, "raw")
            ka.store_keepalive_setpoint(coordinator, "k2", scaled_cfg, 50, "number")
            await settle(manager.async_activate(GID))
            self.assertEqual(coordinator.writes[0][2], 2)
            self.assertEqual(coordinator.writes[1][2], 500)

        run(scenario)

    def test_non_finite_setpoint_is_ignored(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), math.nan, "number")
            self.assertEqual(manager.groups[GID].setpoints, {})

        run(scenario)

    def test_reactivation_needs_new_setpoints(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            await settle(manager.async_deactivate(GID))
            writes_before = len(coordinator.writes)
            await settle(manager.async_activate(GID))
            self.assertEqual(len(coordinator.writes), writes_before)

        run(scenario)

    def test_register_groups_removes_unused_groups(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            manager.register_groups({})
            self.assertEqual(manager.groups, {})

        run(scenario)


class ClampTest(unittest.TestCase):
    def _soc(self, coordinator, clock, value, age=0.0):
        coordinator.register_data["soc"] = {
            "processed_value": value,
            "timestamp": clock.now - age,
            "register_config": {"unique_id": "t_battery_soc"},
        }

    def _cfg(self, **extra):
        return number_config(
            "min_soc", 1042, clamp_max_to_register="battery_soc", clamp_max_to_register_source="t_battery_soc", **extra
        )

    def test_clamp_limits_written_value(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            self._soc(coordinator, clock, 14.0)
            ka.store_keepalive_setpoint(coordinator, "k", self._cfg(), 15, "number")
            await settle(manager.async_activate(GID))
            self.assertAlmostEqual(decode_float_cdab(coordinator.writes[-1][2]), 14.0)

        run(scenario)

    def test_stale_clamp_source_stops_without_write(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            self._soc(coordinator, clock, 14.0, age=120)
            ka.store_keepalive_setpoint(coordinator, "k", self._cfg(), 15, "number")
            await settle(manager.async_activate(GID))
            group = manager.groups[GID]
            self.assertEqual(coordinator.writes, [])
            self.assertEqual(group.state, ka.STATE_STOPPED)
            self.assertIn("stale or unavailable", group.stop_reason)

        run(scenario)

    def test_nan_clamp_source_stops_without_write(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            self._soc(coordinator, clock, math.nan)
            ka.store_keepalive_setpoint(coordinator, "k", self._cfg(), 15, "number")
            await settle(manager.async_activate(GID))
            self.assertEqual(coordinator.writes, [])
            self.assertEqual(manager.groups[GID].state, ka.STATE_STOPPED)

        run(scenario)

    def test_missing_clamp_source_stops_without_write(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            config = number_config("min_soc", 1042, clamp_min_to_register="x", clamp_min_to_register_source="t_x")
            ka.store_keepalive_setpoint(coordinator, "k", config, 15, "number")
            await settle(manager.async_activate(GID))
            self.assertEqual(coordinator.writes, [])
            self.assertEqual(manager.groups[GID].state, ka.STATE_STOPPED)

        run(scenario)

    def test_contradicting_clamps_stop_without_write(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            self._soc(coordinator, clock, 10.0)
            coordinator.register_data["min"] = {
                "processed_value": 20.0,
                "timestamp": clock.now,
                "register_config": {"unique_id": "t_floor"},
            }
            config = self._cfg(clamp_min_to_register="floor", clamp_min_to_register_source="t_floor")
            ka.store_keepalive_setpoint(coordinator, "k", config, 15, "number")
            await settle(manager.async_activate(GID))
            self.assertEqual(coordinator.writes, [])
            self.assertIn("contradict", manager.groups[GID].stop_reason)

        run(scenario)


class StopAndRaceTest(unittest.TestCase):
    def test_switch_off_release_stop_writes_nothing(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            writes_before = len(coordinator.writes)
            self.assertIsNone(manager.async_deactivate(GID))
            group = manager.groups[GID]
            self.assertEqual(len(coordinator.writes), writes_before)
            self.assertEqual(group.state, ka.STATE_OFF)
            self.assertEqual(group.setpoints, {})

        run(scenario)

    def test_switch_off_release_write_sends_one_release(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            config = number_config(release="write", release_value=13500.0)
            ka.store_keepalive_setpoint(coordinator, "k", config, 0, "number")
            await settle(manager.async_activate(GID))
            await settle(manager.async_deactivate(GID))
            self.assertAlmostEqual(decode_float_cdab(coordinator.writes[-1][2]), 13500.0)
            self.assertEqual(len(coordinator.writes), 2)

        run(scenario)

    def test_switch_off_while_round_waits_for_io_lock(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await coordinator.lock.acquire()  # a poll holds the IO lock
            task = manager.async_activate(GID)
            await asyncio.sleep(0)
            manager.async_deactivate(GID)
            coordinator.lock.release()
            await settle(task)
            await asyncio.sleep(0)
            self.assertEqual(coordinator.writes, [])

        run(scenario)

    def test_unload_while_round_waits_for_io_lock(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await coordinator.lock.acquire()
            task = manager.async_activate(GID)
            await asyncio.sleep(0)
            coordinator._is_unloading = True
            manager.stop_all("unload")
            coordinator.lock.release()
            await settle(task)
            self.assertEqual(coordinator.writes, [])
            self.assertEqual(manager.groups[GID].state, ka.STATE_STOPPED)

        run(scenario)

    def test_unload_during_release_spacing_stops_further_releases(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            cfg_a = number_config("a", 1038, release="write", release_value=1.0)
            cfg_b = number_config("b", 1040, release="write", release_value=2.0)
            ka.store_keepalive_setpoint(coordinator, "k1", cfg_a, 0, "number")
            ka.store_keepalive_setpoint(coordinator, "k2", cfg_b, 0, "number")
            await settle(manager.async_activate(GID))
            writes_before = len(coordinator.writes)
            task = manager.async_deactivate(GID)
            # Let the first release go out, then unload during the spacing sleep.
            while len(coordinator.writes) == writes_before:
                await asyncio.sleep(0)
            coordinator._is_unloading = True
            manager.stop_all("unload")
            await settle(task)
            self.assertEqual(len(coordinator.writes), writes_before + 1)

        run(scenario)

    def test_reactivation_invalidates_pending_release(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            cfg = number_config(release="write", release_value=13500.0)
            ka.store_keepalive_setpoint(coordinator, "k", cfg, 0, "number")
            await settle(manager.async_activate(GID))
            writes_before = len(coordinator.writes)
            await coordinator.lock.acquire()
            release_task = manager.async_deactivate(GID)
            await asyncio.sleep(0)
            manager.async_activate(GID)  # no setpoints after switch-off, so no round writes
            coordinator.lock.release()
            await settle(release_task)
            self.assertEqual(len(coordinator.writes), writes_before)

        run(scenario)

    def test_newer_setpoint_is_not_overwritten_by_running_round(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k1", number_config("a", 1038), 0, "number")
            ka.store_keepalive_setpoint(coordinator, "k2", number_config("b", 1040), 100, "number")
            task = manager.async_activate(GID)
            # After the first write, the round sleeps for the spacing gap.
            while len(coordinator.writes) < 1:
                await asyncio.sleep(0)
            ka.store_keepalive_setpoint(coordinator, "k2", number_config("b", 1040), 200, "number")
            await settle(task)
            values = [decode_float_cdab(w[2]) for w in coordinator.writes if w[1] == 1040]
            self.assertNotIn(100.0, values)
            clock.now += 15
            await manager.async_run_round(GID)
            values = [decode_float_cdab(w[2]) for w in coordinator.writes if w[1] == 1040]
            self.assertEqual(values[-1], 200.0)

        run(scenario)

    def test_failed_poll_stops_group(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            coordinator.last_update_success = False  # e.g. core unit backend lost the link
            clock.now += 15
            await manager.async_run_round(GID)
            self.assertEqual(len(coordinator.writes), 1)
            self.assertEqual(manager.groups[GID].state, ka.STATE_STOPPED)

        run(scenario)

    def test_dropped_link_stops_group(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            coordinator.hub.connected = False
            clock.now += 15
            await manager.async_run_round(GID)
            self.assertEqual(len(coordinator.writes), 1)
            self.assertEqual(manager.groups[GID].state, ka.STATE_STOPPED)

        run(scenario)

    def test_activation_refused_while_link_down(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            coordinator.hub.connected = False
            self.assertIsNone(manager.async_activate(GID))
            self.assertFalse(manager.is_active(GID))

        run(scenario)



class SecondReviewTest(unittest.TestCase):
    def test_switch_off_while_off_keeps_values_and_writes_nothing(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            config = number_config(release="write", release_value=13500.0)
            ka.store_keepalive_setpoint(coordinator, "k", config, 0, "number")
            self.assertIsNone(manager.async_deactivate(GID))  # already off
            await asyncio.sleep(0)
            self.assertEqual(coordinator.writes, [])
            self.assertIn("k", manager.groups[GID].setpoints)

        run(scenario)

    def test_switch_off_after_stop_resets_state_without_writing(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            config = number_config(release="write", release_value=13500.0)
            ka.store_keepalive_setpoint(coordinator, "k", config, 0, "number")
            await settle(manager.async_activate(GID))
            manager.stop_group(GID, "test")
            writes_before = len(coordinator.writes)
            self.assertIsNone(manager.async_deactivate(GID))
            self.assertEqual(len(coordinator.writes), writes_before)
            self.assertEqual(manager.groups[GID].state, ka.STATE_OFF)

        run(scenario)

    def test_spacing_holds_across_concurrent_groups(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            gid2 = "t_other_keepalive"
            manager.register_groups({GID: dict(GROUP_CFG), gid2: dict(GROUP_CFG)})
            send_times = []
            original = coordinator.async_pb_write

            async def recording(*args, **kwargs):
                result = await original(*args, **kwargs)
                if result:
                    send_times.append(clock.now)
                return result

            coordinator.async_pb_write = recording
            ka.store_keepalive_setpoint(coordinator, "k1", number_config("a", 1038), 0, "number")
            other = number_config("b", 1040)
            other["keepalive"]["group_id"] = gid2
            ka.store_keepalive_setpoint(coordinator, "k2", other, 0, "number")
            t1 = manager.async_activate(GID)
            t2 = manager.async_activate(gid2)
            await settle(t1)
            await settle(t2)
            self.assertEqual(len(send_times), 2)
            self.assertGreaterEqual(send_times[1] - send_times[0], 1.0)

        run(scenario)

    def test_stop_does_not_abort_write_in_flight(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            entered = asyncio.Event()
            proceed = asyncio.Event()
            finished = []

            async def slow_write(*args, guard=None, **kwargs):
                async with coordinator.lock:
                    if guard is not None and not guard():
                        return False
                    entered.set()
                    await proceed.wait()
                    finished.append(args[1])
                    return True

            coordinator.async_pb_write = slow_write
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            task = manager.async_activate(GID)
            await entered.wait()
            manager.stop_group(GID, "test")  # cancels the round task
            proceed.set()
            await settle(task)
            for _ in range(5):
                await asyncio.sleep(0)
            self.assertEqual(finished, [1026])  # transaction completed, not torn down

        run(scenario)

    def test_home_assistant_stop_stops_groups(self):
        async def scenario():
            coordinator, manager, _ = make_manager()
            ka.store_keepalive_setpoint(coordinator, "k", number_config(), 0, "number")
            await settle(manager.async_activate(GID))
            manager._handle_hass_stop(None)
            self.assertEqual(manager.groups[GID].state, ka.STATE_STOPPED)

        run(scenario)

    def test_switch_mismatch_uses_raw_value(self):
        async def scenario():
            coordinator, manager, clock = make_manager()
            config = {
                "unique_id": "t_switch",
                "type": "switch",
                "address": 1080,
                "slave_id": 71,
                "data_type": "uint16",
                "count": 1,
                "keepalive": {"group": "bat", "group_id": GID, "release": "stop"},
            }
            ka.store_keepalive_setpoint(coordinator, "s", config, 1, "raw")
            await settle(manager.async_activate(GID))
            clock.now += 15
            coordinator.register_data["s"] = {
                "processed_value": False,
                "raw_value": 0,
                "timestamp": clock.now,
            }
            await manager.async_run_round(GID)
            self.assertEqual(manager.groups[GID].mismatches, 1)

        run(scenario)


if __name__ == "__main__":
    unittest.main()
