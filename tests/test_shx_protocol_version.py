"""SHx protocol_version: battery row gating and probe pre-fill without HA installed."""

from __future__ import annotations

import ast
import logging
import re
import unittest
from pathlib import Path
from typing import Any, Optional

import yaml

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components/modbus_manager"
TEMPLATE = COMPONENT / "device_templates/sungrow_shx_dynamic.yaml"
BATTERY_IDS = {"battery_power", "battery_current", "battery_power_unsigned_raw"}


def _load_functions(path: Path, names: set[str], namespace: dict[str, Any]) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    exec(  # nosec B102
        compile(ast.Module(functions, type_ignores=[]), str(path), "exec"),
        namespace,
    )


NS: dict[str, Any] = {
    "Any": Any,
    "Optional": Optional,
    "re": re,
    "_LOGGER": logging.getLogger(__name__),
}
_load_functions(
    COMPONENT / "device_utils.py",
    {
        "_parse_version_loose",
        "entity_allowed_for_protocol",
        "find_applicable_version",
        "_coerce_compare_value",
    },
    NS,
)
_load_functions(
    COMPONENT / "template_loader.py",
    {"_evaluate_condition", "_evaluate_single_condition"},
    NS,
)
_load_functions(COMPONENT / "hub_identify.py", {"sungrow_protocol_version"}, NS)


def _template() -> dict[str, Any]:
    return yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))


def _battery_rows(protocol_version: str | None) -> list[tuple[str, str, Any]]:
    dynamic_config: dict[str, Any] = {"battery_enabled": True}
    if protocol_version is not None:
        dynamic_config["protocol_version"] = protocol_version
    selected = []
    template = _template()
    for kind in ("sensors", "calculated"):
        for row in template[kind]:
            if row.get("unique_id") not in BATTERY_IDS:
                continue
            if not NS["entity_allowed_for_protocol"](row, protocol_version):
                continue
            if not NS["_evaluate_condition"](row["condition"], dynamic_config):
                continue
            selected.append((kind, row["unique_id"], row.get("address")))
    return selected


class ShxProtocolVersionRowTests(unittest.TestCase):
    def test_unset_keeps_recommended_registers(self) -> None:
        self.assertEqual(
            sorted(_battery_rows(None)),
            [("sensors", "battery_current", 5630), ("sensors", "battery_power", 5213)],
        )

    def test_v1011_matches_unset(self) -> None:
        self.assertEqual(sorted(_battery_rows("1.0.11")), sorted(_battery_rows(None)))

    def test_v107_uses_13021_13022_and_calculated_power(self) -> None:
        self.assertEqual(
            sorted(_battery_rows("1.0.7")),
            [
                ("calculated", "battery_power", None),
                ("sensors", "battery_current", 13020),
                ("sensors", "battery_power_unsigned_raw", 13021),
            ],
        )

    def test_unsigned_source_is_polled_while_disabled(self) -> None:
        row = next(
            row
            for row in _template()["sensors"]
            if row.get("unique_id") == "battery_power_unsigned_raw"
        )
        self.assertFalse(row["enabled_by_default"])
        self.assertTrue(row["always_poll"])

    def test_option_keys_are_strings(self) -> None:
        section = _template()["dynamic_config"]["protocol_version"]
        self.assertEqual(list(section["options"]), ["1.0.7", "1.0.11"])
        self.assertEqual(section["default"], "1.0.11")


class ShxProtocolProbeTests(unittest.TestCase):
    def test_decode_sh20t_raw_registers(self) -> None:
        # reg 4952-4953 read [1792, 256], word swap -> 0x01000700
        raw = (256 << 16) | 1792
        self.assertEqual(NS["sungrow_protocol_version"](raw), "1.0.7")

    def test_decode_bcd_patch(self) -> None:
        self.assertEqual(NS["sungrow_protocol_version"](0x01011100), "1.1.11")

    def test_decode_rejects_absent(self) -> None:
        for raw in (None, 0, 0xFFFFFFFF, True, "1.0.7"):
            self.assertIsNone(NS["sungrow_protocol_version"](raw))

    def test_detected_version_maps_to_option(self) -> None:
        keys = list(_template()["dynamic_config"]["protocol_version"]["options"])
        pick = NS["find_applicable_version"]
        self.assertEqual(pick("1.0.7", keys), "1.0.7")
        self.assertEqual(pick("1.0.11", keys), "1.0.11")
        self.assertEqual(pick("1.0.8", keys), "1.0.7")
        self.assertEqual(pick("1.1.11", keys), "1.0.11")
        self.assertEqual(pick("1.2.0", keys), "1.0.11")
        self.assertIsNone(pick("0.9.0", keys))


if __name__ == "__main__":
    unittest.main()
