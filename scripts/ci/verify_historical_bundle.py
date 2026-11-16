"""Verify a supplied historical outputs bundle before running audit tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "outputs" / "ci" / "historical-artifacts.sha256"


def main() -> int:
    if not MANIFEST.is_file():
        raise SystemExit(
            "Historical audit NOT RUN: missing outputs/ci/historical-artifacts.sha256. "
            "Provide the reviewed manifest and matching immutable outputs bundle."
        )
    entries = 0
    for line_number, raw in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            expected, relative = line.split(None, 1)
        except ValueError as exc:
            raise SystemExit(f"Invalid SHA manifest line {line_number}") from exc
        relative = relative.lstrip("* ")
        if len(expected) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected):
            raise SystemExit(f"Invalid SHA-256 on manifest line {line_number}")
        if not relative.startswith("outputs/") or ".." in Path(relative).parts:
            raise SystemExit(f"Manifest path must be a safe outputs/ path (line {line_number})")
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"Historical artifact missing: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual.lower() != expected.lower():
            raise SystemExit(f"Historical SHA-256 mismatch: {relative}")
        entries += 1
    if entries == 0:
        raise SystemExit("Historical SHA-256 manifest contains no file entries")
    print(f"Verified {entries} historical artifacts against the supplied SHA-256 manifest")
    print("Note: trust in the manifest source must be established independently.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
