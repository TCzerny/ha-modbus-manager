#!/usr/bin/env python3
"""Fail unless the git tag matches manifest.json and CHANGELOG.md has that section.

Does not bump versions. Run from the repository root:

    python3 scripts/release_check.py --expect 1.3.5 --notes-file /tmp/notes.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "modbus_manager" / "manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def changelog_section(text: str, version: str) -> str | None:
    """Return the body under ``## [version]``, excluding the heading."""
    escaped = re.escape(version)
    pattern = re.compile(
        rf"^## \[{escaped}\](?:[^\n]*)\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect",
        required=True,
        help="Version from the git tag without the leading v, e.g. 1.3.5",
    )
    parser.add_argument(
        "--notes-file",
        type=Path,
        help="Write the CHANGELOG section for this version to this path",
    )
    args = parser.parse_args()
    expect = args.expect.lstrip("v")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    found = str(manifest.get("version", ""))
    if found != expect:
        print(
            f"manifest.json version {found!r} does not match tag {expect!r}",
            file=sys.stderr,
        )
        return 1

    notes = changelog_section(CHANGELOG.read_text(encoding="utf-8"), expect)
    if not notes:
        print(
            f"CHANGELOG.md has no ## [{expect}] section; move Unreleased before tagging",
            file=sys.stderr,
        )
        return 1

    if args.notes_file:
        args.notes_file.write_text(notes + "\n", encoding="utf-8")

    print(f"ok: manifest {found}, changelog section present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
