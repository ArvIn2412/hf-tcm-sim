"""Recheck pinned EXP-03B protocols/manifests without rewriting scientific files."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


def main() -> None:
    baseline = Path("outputs/ui_interactivity_stage4/historical_sha256.csv")
    with baseline.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    checkpoint_parents = {
        Path(r["path"]).parent for r in rows if r["path"].endswith("/checkpoint.jsonl")
    }
    selected = [
        r
        for r in rows
        if r["expected"]
        and (
            (r["path"].startswith("configs/") and "03B" in r["path"])
            or ("SCIENTIFIC_EXP_03B" in r["path"] and "PROTOCOL" in r["path"])
            or (
                r["path"].startswith("outputs/scientific_exp03b/")
                and Path(r["path"]).parent in checkpoint_parents
                and Path(r["path"]).name in {"manifest.json", "checkpoint.jsonl", "config.json"}
            )
        )
    ]
    results = []
    for row in selected:
        path = Path(row["path"])
        try:
            with path.open("rb") as source:
                actual = hashlib.file_digest(source, "sha256").hexdigest()
            status = "PASS" if actual == row["expected"] else "FAIL"
        except OSError:
            actual, status = "", "NOT_VERIFIED"
        results.append(
            {"path": row["path"], "expected": row["expected"], "actual": actual, "status": status}
        )
    summary = {s: sum(r["status"] == s for r in results) for s in ("PASS", "FAIL", "NOT_VERIFIED")}
    summary["scope"] = (
        "Fresh pinned protocol/config/manifest/checkpoint subset; not a fresh full trial-array audit"
    )
    summary["files"] = results
    Path("outputs/release_readiness/protected_references.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "files"}))


if __name__ == "__main__":
    main()
