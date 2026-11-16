"""Read-only integrity check for REPRO-06B output and frozen M5-M10 files."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/repro06b/reference_static_2path"
HISTORICAL = ROOT / "tmp/m11d-integrity-before.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    failed: list[str] = []
    for relative, entry in manifest["files"].items():
        path = OUTPUT / relative
        if not path.is_file():
            failed.append(f"missing:{relative}")
        elif path.stat().st_size != entry["size_bytes"] or _sha(path) != entry["sha256"]:
            failed.append(f"hash_or_size:{relative}")

    svg_count = 0
    for path in OUTPUT.rglob("*.svg"):
        ET.parse(path)
        svg_count += 1

    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))["files"]
    matched = 0
    for relative, expected in historical.items():
        path = ROOT / relative
        if path.is_file() and _sha(path) == expected:
            matched += 1
        else:
            failed.append(f"historical:{relative}")

    counts = {
        "root_files_verified": len(manifest["files"])
        - sum(entry.startswith(("missing:", "hash_or_size:")) for entry in failed),
        "root_files_expected": len(manifest["files"]),
        "historical_matched": matched,
        "historical_expected": len(historical),
        "svg_xml_valid": svg_count,
        "failed": failed,
    }
    if failed or matched != len(historical):
        print(json.dumps(counts, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
