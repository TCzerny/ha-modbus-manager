#!/usr/bin/env python3
"""Refresh an existing device README from the whole YAML template.

One page per device, in this order: title and wiki line, template overview,
dynamic-config options plus a hand-kept info block, registers by type, then
Additional information. The writer refreshes the generated parts and copies
the two hand blocks through. Pages without those markers are left unchanged.

    python3 scripts/readme_from_template.py
    python3 scripts/readme_from_template.py --print sungrow_ac011e_wallbox
    python3 scripts/readme_from_template.py --write
    python3 scripts/readme_from_template.py --adopt docs/README_inepro_pro380_mod.md

Does not create a second document, and does not add a page for a template
that has no README yet.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "custom_components" / "modbus_manager" / "device_templates"
DOCS = ROOT / "docs"

# Stems whose page name is not docs/README_<stem>.md.
PAGE_FOR_STEM = {
    "sungrow_ihomemanager": "README_iHomeManager.md",
    "keba_kecontact_p30": "README_keba_kecontact.md",
    "keba_kecontact_p40": "README_keba_kecontact.md",
}

DEVICE_KEYS = (
    "name",
    "display_name",
    "description",
    "manufacturer",
    "model",
    "version",
    "type",
    "firmware_version",
    "default_prefix",
    "default_slave_id",
    "detect_slave_ids",
    "config_flow_note",
)


def kept_marker(end: bool) -> str:
    """Return the start or end marker for Additional information."""
    which = "end" if end else "start"
    return f"<!-- mm-kept {which} -->"


def info_marker(stem: str, end: bool) -> str:
    """Return the marker around hand-written Dynamic Configuration notes."""
    which = "end" if end else "start"
    return f"<!-- mm-info:{stem}.yaml {which} -->"


WIKI_LINE = (
    "> **General documentation (Wiki):** "
    "[User Guide](https://github.com/TCzerny/ha-modbus-manager/wiki/User-Guide) · "
    "[Template reference](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference) · "
    "[Capabilities and limits](https://github.com/TCzerny/ha-modbus-manager/wiki/Capabilities-and-Limits) · "
    "[Local customization](https://github.com/TCzerny/ha-modbus-manager/wiki/Local-Customization)"
)

REGISTER_SECTIONS = (
    ("sensors", "Sensors"),
    ("controls", "Controls"),
    ("binary_sensors", "Binary sensors"),
    ("calculated", "Calculated sensors"),
)

OVERVIEW_FIELDS = (
    ("name", "Name"),
    ("manufacturer", "Manufacturer"),
    ("model", "Model"),
    ("type", "Type"),
    ("default_prefix", "Default prefix"),
    ("default_slave_id", "Default slave ID"),
    ("firmware_version", "Firmware"),
    ("version", "Template version"),
    ("detect_slave_ids", "Detect slave IDs"),
    ("description", "Description"),
)


def page_for_stem(stem: str) -> Path | None:
    """Return the existing README for a template stem, if one exists."""
    name = PAGE_FOR_STEM.get(stem, f"README_{stem}.md")
    path = DOCS / name
    if path.is_file():
        return path
    return None


def load_templates() -> list[tuple[str, dict]]:
    """Load every device template. The stem is the file name without .yaml."""
    loaded: list[tuple[str, dict]] = []
    for path in sorted(TEMPLATE_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit(f"{path.name} did not parse as a mapping")
        loaded.append((path.stem, data))
    return loaded


def cell(value: object) -> str:
    """Render one Markdown table cell on a single line."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text.replace("|", "\\|")


def choices(value: object) -> str:
    """Render a dynamic-config options value as a short list."""
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            label = cell(item)
            parts.append(
                f"{key} ({label})" if label and label != str(key) else str(key)
            )
        return ", ".join(parts)
    if isinstance(value, list):
        return ", ".join(cell(item) for item in value)
    return cell(value)


def gating(row: dict) -> str:
    """Join the fields that decide whether a row is exposed."""
    parts = []
    for key in ("condition", "depends_on", "valid_models", "requires_connection_type"):
        value = row.get(key)
        if value not in (None, "", [], {}):
            parts.append(cell(value))
    return "; ".join(parts)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown table from already escaped cells."""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def overview_section(data: dict, level: int) -> str:
    """Template overview from the template header."""
    heading = "#" * level
    lines = [f"{heading} Template Overview", ""]
    for key, label in OVERVIEW_FIELDS:
        value = data.get(key)
        if value in (None, ""):
            continue
        lines.append(f"- **{label}**: {cell(value)}")
    return "\n".join(lines)


def dynamic_section(stem: str, data: dict, info: str, level: int) -> str:
    """Options from dynamic_config, then the hand-kept info block."""
    heading = "#" * level
    lines = [f"{heading} Dynamic Configuration", ""]
    config = data.get("dynamic_config")
    if isinstance(config, dict) and config:
        option_rows: list[list[str]] = []
        model_blocks: list[str] = []
        for key, item in config.items():
            if isinstance(item, dict) and {"description", "options", "default"} & set(
                item
            ):
                option_rows.append(
                    [
                        cell(key),
                        cell(item.get("description")),
                        choices(item.get("options", "")),
                        cell(item.get("default")),
                    ]
                )
                continue
            if (
                isinstance(item, dict)
                and item
                and all(isinstance(value, dict) for value in item.values())
            ):
                model_blocks.append(model_table(str(key), item, level + 1))
                continue
            option_rows.append([cell(key), "", cell(item), ""])
        if option_rows:
            lines.append(
                markdown_table(
                    ["Option", "Description", "Choices", "Default"], option_rows
                )
            )
            lines.append("")
        lines.extend(block.rstrip() for block in model_blocks)
        if model_blocks:
            lines.append("")
    note = data.get("config_flow_note")
    if note:
        lines.append(cell(note))
        lines.append("")
    keepalive = data.get("keepalive_groups")
    if isinstance(keepalive, dict) and keepalive:
        lines.append(keepalive_table(keepalive, level + 1))
        lines.append("")
    lines.append(info_marker(stem, False))
    if info.strip():
        lines.append(info.strip())
    lines.append(info_marker(stem, True))
    return "\n".join(lines)


def model_table(title: str, models: dict, level: int) -> str:
    """One row per model, using the scalar fields on each model."""
    field_names: list[str] = []
    for model in models.values():
        if not isinstance(model, dict):
            continue
        for key, value in model.items():
            if key not in field_names and not isinstance(value, (dict, list)):
                field_names.append(key)
    headers = ["Model", *field_names]
    rows = []
    for name, model in models.items():
        if not isinstance(model, dict):
            rows.append([cell(name), cell(model), *([""] * (len(field_names) - 1))])
            continue
        rows.append([cell(name), *[cell(model.get(key)) for key in field_names]])
    heading = "#" * level
    return f"{heading} {title.replace('_', ' ')}\n\n" + markdown_table(headers, rows)


def keepalive_table(groups: dict, level: int) -> str:
    """Short table of keepalive groups. The controls stay in the register section."""
    rows = []
    for key, item in groups.items():
        if not isinstance(item, dict):
            rows.append([cell(key), "", cell(item)])
            continue
        rows.append([cell(key), cell(item.get("name")), cell(item.get("interval"))])
    heading = "#" * level
    return f"{heading} Keepalive groups\n\n" + markdown_table(
        ["Group", "Name", "Interval"], rows
    )


def register_table(rows: list[dict]) -> str:
    """Narrow register table: identity, address, and the gating fields."""
    has_type = any(row.get("type") for row in rows)
    has_address = any(row.get("address") not in (None, "") for row in rows)
    headers = ["Name", "Unique ID"]
    if has_type:
        headers.append("Type")
    if has_address:
        headers.extend(["Address", "Input", "Data", "Unit", "Scale"])
    elif any(row.get("unit_of_measurement") for row in rows):
        headers.append("Unit")
    headers.append("Condition")
    rendered = []
    for row in rows:
        cells = [cell(row.get("name")), cell(row.get("unique_id"))]
        if has_type:
            cells.append(cell(row.get("type")))
        if has_address:
            cells.extend(
                [
                    cell(row.get("address")),
                    cell(row.get("input_type")),
                    cell(row.get("data_type")),
                    cell(row.get("unit_of_measurement")),
                    cell(row.get("scale")),
                ]
            )
        elif "Unit" in headers:
            cells.append(cell(row.get("unit_of_measurement")))
        cells.append(gating(row))
        rendered.append(cells)
    return markdown_table(headers, rendered)


def registers_section(data: dict, level: int) -> str:
    """Registers grouped by template block. Empty blocks are omitted."""
    heading = "#" * level
    sub = "#" * (level + 1)
    blocks: list[tuple[str, object]] = []
    seen = set()
    for key, title in REGISTER_SECTIONS:
        if key in data:
            blocks.append((title, data[key]))
            seen.add(key)
    for key, value in data.items():
        if (
            key in seen
            or key in DEVICE_KEYS
            or key in {"dynamic_config", "keepalive_groups"}
        ):
            continue
        if isinstance(value, list):
            blocks.append((str(key).replace("_", " ").capitalize(), value))
    parts = [f"{heading} Registers", ""]
    parts.append("Address is the protocol address stored in the template.")
    parts.append("")
    wrote = False
    for title, value in blocks:
        if not isinstance(value, list) or not value:
            continue
        if not all(isinstance(item, dict) for item in value):
            continue
        parts.append(f"{sub} {title}")
        parts.append("")
        parts.append(register_table(value))
        parts.append("")
        wrote = True
    if not wrote:
        parts.append("_None._")
        parts.append("")
    return "\n".join(parts).rstrip()


def render_template(
    stem: str, data: dict, info: str = "", *, nested: bool = False
) -> str:
    """Render overview, dynamic configuration, and registers for one template."""
    level = 3 if nested else 2
    title = ""
    if nested:
        title = f"## {data.get('display_name') or data.get('name') or stem}\n\n"
    return "\n\n".join(
        [
            (title + overview_section(data, level)).rstrip(),
            dynamic_section(stem, data, info, level).rstrip(),
            registers_section(data, level).rstrip(),
        ]
    )


def extract_marked(text: str, start: str, end: str) -> str:
    """Return the body between two markers, without the markers."""
    if start not in text or end not in text:
        return ""
    return text.split(start, 1)[1].split(end, 1)[0].strip("\n")


def compose(groups: list[tuple[str, dict]], infos: dict[str, str], kept: str) -> str:
    """Build one device page. Hand-written blocks are passed in and copied through."""
    if len(groups) == 1:
        stem, data = groups[0]
        title = data.get("display_name") or data.get("name") or stem
        body = render_template(stem, data, infos.get(stem, ""))
    else:
        title = " / ".join(
            data.get("display_name") or data.get("name") or stem
            for stem, data in groups
        )
        body = "\n\n".join(
            render_template(stem, data, infos.get(stem, ""), nested=True).rstrip()
            for stem, data in groups
        )
    parts = [
        f"# {title}",
        "",
        WIKI_LINE,
        "",
        body.rstrip(),
        "",
        "## Additional information",
        "",
        kept_marker(False),
    ]
    if kept.strip():
        parts.append(kept.strip())
    parts.append(kept_marker(True))
    parts.append("")
    return "\n".join(parts)


def pages_by_path(
    templates: list[tuple[str, dict]],
) -> tuple[dict[Path, list[tuple[str, dict]]], list[str]]:
    """Group templates that share one existing README. Report stems with no page."""
    grouped: dict[Path, list[tuple[str, dict]]] = defaultdict(list)
    missing: list[str] = []
    for stem, data in templates:
        page = page_for_stem(stem)
        if page is None:
            missing.append(stem)
            continue
        grouped[page].append((stem, data))
    return grouped, missing


def hand_blocks(
    text: str, groups: list[tuple[str, dict]]
) -> tuple[dict[str, str], str]:
    """Pull the special-info and additional-information bodies out of a page."""
    infos = {
        stem: extract_marked(text, info_marker(stem, False), info_marker(stem, True))
        for stem, _ in groups
    }
    kept = extract_marked(text, kept_marker(False), kept_marker(True))
    return infos, kept


def region_present(text: str, groups: list[tuple[str, dict]]) -> bool:
    """True when every info block and the additional-information block are marked."""
    if kept_marker(False) not in text or kept_marker(True) not in text:
        return False
    return all(
        info_marker(stem, False) in text and info_marker(stem, True) in text
        for stem, _ in groups
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print",
        metavar="STEM",
        help="Print the template region for one stem and exit",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Replace template regions on pages that already have markers",
    )
    parser.add_argument(
        "--adopt",
        metavar="README",
        help="Wrap this existing page: generated regions, current text kept",
    )
    args = parser.parse_args()
    templates = load_templates()
    by_stem = dict(templates)

    if args.print:
        data = by_stem.get(args.print)
        if data is None:
            print(f"No template named {args.print}", file=sys.stderr)
            return 1
        sys.stdout.write(compose([(args.print, data)], {args.print: ""}, ""))
        return 0

    grouped, missing = pages_by_path(templates)

    if args.adopt:
        page = Path(args.adopt)
        if not page.is_file():
            page = DOCS / args.adopt
        if not page.is_file():
            print(f"No such page: {args.adopt}", file=sys.stderr)
            return 1
        groups = grouped.get(page)
        if not groups:
            print(f"{page.name} is not a device page for a template", file=sys.stderr)
            return 1
        previous = page.read_text(encoding="utf-8")
        infos, kept = hand_blocks(previous, groups)
        if not region_present(previous, groups):
            kept = previous.strip()
            infos = {stem: "" for stem, _ in groups}
        page.write_text(compose(groups, infos, kept), encoding="utf-8")
        print(f"adopted {page.relative_to(ROOT)}")
        return 0

    changed = 0
    unmarked = 0
    for page in sorted(grouped):
        groups = grouped[page]
        text = page.read_text(encoding="utf-8")
        if not region_present(text, groups):
            unmarked += 1
            stems = ", ".join(stem for stem, _ in groups)
            print(f"unmarked  {page.relative_to(ROOT)}  ({stems})")
            continue
        infos, kept = hand_blocks(text, groups)
        fresh = compose(groups, infos, kept)
        if fresh == text:
            print(f"current   {page.relative_to(ROOT)}")
            continue
        changed += 1
        print(f"differs   {page.relative_to(ROOT)}")
        if args.write:
            page.write_text(fresh, encoding="utf-8")
    if missing:
        print("no page   " + ", ".join(missing))
    print(
        f"{unmarked} unmarked, {changed} differ, {len(grouped) - unmarked - changed} current"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
