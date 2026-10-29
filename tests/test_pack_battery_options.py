"""Pack battery must not be cleared by the inverter options form."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any

FLOW = (
    Path(__file__).resolve().parents[1]
    / "custom_components/modbus_manager/config_flow.py"
)


def _load(names: set[str], namespace: dict[str, Any]) -> None:
    tree = ast.parse(FLOW.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    exec(  # nosec B102
        compile(ast.Module(functions, type_ignores=[]), str(FLOW), "exec"),
        namespace,
    )


def _role(device: dict[str, Any]) -> str:
    return str(device.get("type") or "inverter")


NS: dict[str, Any] = {
    "Any": Any,
    "resolve_device_role_type": _role,
    "_clamp_battery_config_for_connection": lambda value, _connection: value or "none",
    "_apply_entry_data_fallbacks_to_device": lambda device, _entry: dict(device),
    "_normalize_stored_device": lambda device: dict(device),
    "build_device_entry_id": lambda device: (
        f"{device.get('prefix')}_{device.get('slave_id')}_{device.get('template')}"
    ),
}
_load(
    {
        "_hub_battery_config_for_pack",
        "_hub_has_separate_pack",
        "_sync_inverter_battery_flags",
        "_apply_hub_battery_from_pack_device",
        "_apply_device_reconfigure",
    },
    NS,
)


class PackBatteryOptionsTests(unittest.TestCase):
    def test_add_pack_sets_inverter_row(self) -> None:
        entry = {
            "connection_type": "LAN",
            "devices": [
                {
                    "type": "inverter",
                    "template": "Sungrow SH Series Inverter",
                    "prefix": "SG",
                    "slave_id": 1,
                    "device_entry_id": "SG_1_Sungrow SH Series Inverter",
                    "battery_config": "none",
                    "battery_enabled": False,
                }
            ],
        }
        pack = {
            "type": "battery",
            "template": "Sungrow SBR Battery",
            "prefix": "SBR",
            "slave_id": 200,
            "device_entry_id": "SBR_200_Sungrow SBR Battery",
        }
        entry["devices"].append(pack)
        NS["_apply_hub_battery_from_pack_device"](entry, pack)
        inverter = entry["devices"][0]
        self.assertEqual(entry["battery_config"], "sbr_battery")
        self.assertTrue(entry["battery_enabled"])
        self.assertEqual(inverter["battery_config"], "sbr_battery")
        self.assertTrue(inverter["battery_enabled"])

    def test_inverter_options_keep_pack_when_form_sends_none(self) -> None:
        inverter = {
            "type": "inverter",
            "template": "Sungrow SH Series Inverter",
            "prefix": "SG",
            "slave_id": 1,
            "device_entry_id": "SG_1_Sungrow SH Series Inverter",
            "battery_config": "none",
            "battery_enabled": False,
            "connection_type": "LAN",
            "protocol_version": "1.0.7",
        }
        pack = {
            "type": "battery",
            "template": "Sungrow SBR Battery",
            "prefix": "SBR",
            "slave_id": 200,
            "device_entry_id": "SBR_200_Sungrow SBR Battery",
        }
        entry = {
            "prefix": "SG",
            "slave_id": 1,
            "template": "Sungrow SH Series Inverter",
            "connection_type": "LAN",
            "battery_config": "sbr_battery",
            "battery_enabled": True,
            "devices": [inverter, pack],
        }
        updated = NS["_apply_device_reconfigure"](
            entry,
            inverter["device_entry_id"],
            {
                "prefix": "SG",
                "slave_id": 1,
                "battery_config": "none",
                "protocol_version": "1.0.11",
            },
            {"dynamic_config": {"battery_config": {}, "protocol_version": {}}},
        )
        saved = updated["devices"][0]
        self.assertEqual(saved["battery_config"], "sbr_battery")
        self.assertTrue(saved["battery_enabled"])
        self.assertEqual(saved["protocol_version"], "1.0.11")
        self.assertEqual(updated["battery_config"], "sbr_battery")
        self.assertTrue(updated["battery_enabled"])
        self.assertEqual(updated["devices"][1]["template"], "Sungrow SBR Battery")


if __name__ == "__main__":
    unittest.main()
