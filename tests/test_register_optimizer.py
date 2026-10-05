"""Focused tests for template read-group transaction boundaries."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
OPTIMIZER_PATH = REPO_ROOT / "custom_components/modbus_manager/register_optimizer.py"
TEMPLATE_DIR = REPO_ROOT / "custom_components/modbus_manager/device_templates"


def load_optimizer_module():
    """Load the pure optimizer without requiring a Home Assistant runtime."""
    package_name = "optimizer_test_package"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package

    const = types.ModuleType(f"{package_name}.const")
    const.CONF_READ_GROUP = "read_group"
    const.DEFAULT_MAX_REGISTER_READ = 64
    sys.modules[const.__name__] = const

    logger = types.ModuleType(f"{package_name}.logger")

    class StubLogger:
        def __init__(self, *_args):
            pass

        def debug(self, *_args):
            pass

        def error(self, *_args):
            pass

    logger.ModbusManagerLogger = StubLogger
    sys.modules[logger.__name__] = logger

    utils = types.ModuleType(f"{package_name}.modbus_utils")
    utils.is_valid_modbus_address = lambda address: isinstance(address, int) and address >= 0
    sys.modules[utils.__name__] = utils

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.register_optimizer", OPTIMIZER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


OPTIMIZER_MODULE = load_optimizer_module()


def reg(address: int, **overrides):
    result = {
        "address": address,
        "data_type": "uint16",
        "count": 1,
        "input_type": "holding",
        "slave_id": 1,
    }
    result.update(overrides)
    return result


def ranges(registers, max_read_size=None):
    optimized = OPTIMIZER_MODULE.RegisterOptimizer(max_read_size).optimize_registers(registers)
    return [(item.start_address, item.end_address, item.register_count) for item in optimized]


def pre_read_group_ranges(registers, max_read_size=64):
    """Reference the optimizer's pre-read_group behavior for compatibility tests."""
    def width(item):
        if item.get("data_type", "uint16") in {"uint32", "int32", "float", "float32"}:
            return 2
        if item.get("data_type") == "float64":
            return 4
        return item.get("count", 1) or 1

    filtered = [item for item in registers if isinstance(item.get("address"), int) and item["address"] >= 0]
    sorted_registers = sorted(filtered, key=lambda item: (item.get("slave_id", 1), item["address"]))
    result = []
    current = None
    for item in sorted_registers:
        count = item.get("count", 1) or 1
        if current is None:
            current = {"start": item["address"], "end": item["address"] + count - 1, "items": [item]}
            continue
        first = current["items"][0]
        compatible_fc = first.get("read_function_code") == item.get("read_function_code") or (
            first.get("read_function_code") is None and item.get("read_function_code") is None
        )
        current_width = sum(width(existing) for existing in current["items"])
        if (
            item["address"] <= current["end"] + 1
            and current_width + width(item) <= max_read_size
            and first.get("input_type", "holding") == item.get("input_type", "holding")
            and first.get("slave_id", 1) == item.get("slave_id", 1)
            and compatible_fc
        ):
            current["end"] = max(current["end"], item["address"] + count - 1)
            current["items"].append(item)
        else:
            result.append((current["start"], current["end"], current_width))
            current = {"start": item["address"], "end": item["address"] + count - 1, "items": [item]}
    if current:
        result.append((current["start"], current["end"], sum(width(item) for item in current["items"])))
    return result


class RegisterOptimizerReadGroupTest(unittest.TestCase):
    def test_adjacent_ungrouped_registers_keep_existing_merge_behavior(self):
        self.assertEqual(ranges([reg(10), reg(11)]), [(10, 11, 2)])

    def test_adjacent_same_read_group_merges(self):
        self.assertEqual(
            ranges([reg(10, read_group="block_a"), reg(11, read_group="block_a")]),
            [(10, 11, 2)],
        )
        self.assertEqual(
            ranges(
                [
                    reg(20, input_type="input", read_group="input_block"),
                    reg(21, input_type="input", read_group="input_block"),
                ]
            ),
            [(20, 21, 2)],
        )

    def test_different_read_groups_do_not_merge(self):
        self.assertEqual(
            ranges([reg(10, read_group="block_a"), reg(11, read_group="block_b")]),
            [(10, 10, 1), (11, 11, 1)],
        )

    def test_grouped_and_ungrouped_registers_do_not_merge_in_either_order(self):
        for registers in (
            [reg(10, read_group="block_a"), reg(11)],
            [reg(10), reg(11, read_group="block_a")],
        ):
            with self.subTest(registers=registers):
                self.assertEqual(ranges(registers), [(10, 10, 1), (11, 11, 1)])

    def test_group_boundary_cannot_be_bridged(self):
        self.assertEqual(
            ranges(
                [
                    reg(10, read_group="block_a"),
                    reg(11),
                    reg(12, read_group="block_a"),
                ]
            ),
            [(10, 10, 1), (11, 11, 1), (12, 12, 1)],
        )

    def test_address_gaps_remain_boundaries_with_matching_groups(self):
        self.assertEqual(
            ranges(
                [
                    reg(10, read_group="block_a"),
                    reg(12, read_group="block_a"),
                ]
            ),
            [(10, 10, 1), (12, 12, 1)],
        )

    def test_float32_is_atomic_at_a_read_group_boundary(self):
        self.assertEqual(
            ranges(
                [
                    reg(20522, data_type="float32", count=2, read_group="pf_total"),
                    reg(20524, data_type="float32", count=2, read_group="pf_l1"),
                ]
            ),
            [(20522, 20523, 2), (20524, 20525, 2)],
        )

    def test_existing_max_read_size_still_applies(self):
        self.assertEqual(
            ranges([reg(10), reg(11), reg(12)], max_read_size=2),
            [(10, 11, 2), (12, 12, 1)],
        )

    def test_existing_slave_function_and_register_type_boundaries_still_apply(self):
        self.assertEqual(
            ranges([reg(10), reg(11, slave_id=2)]), [(10, 10, 1), (11, 11, 1)]
        )
        self.assertEqual(
            ranges([reg(10, read_function_code=3), reg(11, read_function_code=4)]),
            [(10, 10, 1), (11, 11, 1)],
        )
        self.assertEqual(
            ranges([reg(10, input_type="holding"), reg(11, input_type="input")]),
            [(10, 10, 1), (11, 11, 1)],
        )

    def test_existing_templates_are_ungrouped_and_retain_pre_feature_ranges(self):
        for template_path in TEMPLATE_DIR.glob("*.yaml"):
            template = yaml.safe_load(template_path.read_text()) or {}
            sensors = template.get("sensors", [])
            sensors = [sensor for sensor in sensors if isinstance(sensor, dict)]
            # This compatibility check covers templates which do not opt in to
            # read_group. Templates that deliberately use it are tested with
            # their device-specific transaction expectations.
            if any("read_group" in sensor for sensor in sensors):
                continue
            with self.subTest(template=template_path.name):
                self.assertEqual(ranges(sensors), pre_read_group_ranges(sensors))


if __name__ == "__main__":
    unittest.main()
