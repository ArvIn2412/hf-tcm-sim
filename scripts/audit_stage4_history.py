"""Rehash immutable historical references into a new stage-4 report only."""

import csv
import hashlib
import json
import sys
import time
from pathlib import Path


def main() -> None:
    started = time.perf_counter()
    references = {}
    for name in ("historical_sha256.csv", "historical_archive_baseline.csv"):
        path = Path("outputs/ui_article_alignment", name)
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                references[row["path"].replace("\\", "/")] = row.get("expected", "")
    for row in json.loads(
        Path("outputs/ui_article_alignment/historical_later_revisions_not_verified.json").read_text(
            encoding="utf-8"
        )
    ):
        references.setdefault(row["path"], "")
    counts = dict(PASS=0, FAIL=0, NOT_VERIFIED=0)
    records = 0
    confirmatory = 0
    with Path("outputs/ui_interactivity_stage4/historical_sha256.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "expected", "actual", "status"])
        writer.writeheader()
        for name, expected in references.items():
            path = Path(name)
            try:
                actual = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
                status = (
                    "NOT_VERIFIED" if not expected else "PASS" if expected == actual else "FAIL"
                )
            except OSError:
                actual, status = "", "NOT_VERIFIED"
            counts[status] += 1
            if "/trials/" in name and path.suffix == ".json" and status == "PASS":
                records += 1
                confirmatory += int("/confirmatory/" in name)
            writer.writerow(dict(path=name, expected=expected, actual=actual, status=status))
    result = {
        **counts,
        "verified_trial_json": records,
        "confirmatory_record_count": confirmatory,
        "overall_status": "FAIL"
        if counts["FAIL"]
        else "PARTIAL"
        if counts["NOT_VERIFIED"]
        else "PASS",
        "seconds": time.perf_counter() - started,
    }
    Path("outputs/ui_interactivity_stage4/historical.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))


def append_unverified() -> None:
    """Extend an already completed fresh audit without rehashing its 87714 files."""
    root = Path("outputs/ui_interactivity_stage4")
    with (root / "historical_sha256.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    names = {row["path"] for row in rows}
    additions = json.loads(
        Path("outputs/ui_article_alignment/historical_later_revisions_not_verified.json").read_text(
            encoding="utf-8"
        )
    )
    with (root / "historical_sha256.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "expected", "actual", "status"])
        for entry in additions:
            if entry["path"] in names:
                continue
            try:
                with Path(entry["path"]).open("rb") as source:
                    actual = hashlib.file_digest(source, "sha256").hexdigest()
            except OSError:
                actual = ""
            row = dict(path=entry["path"], expected="", actual=actual, status="NOT_VERIFIED")
            writer.writerow(row)
            rows.append(row)
    result = json.loads((root / "historical.json").read_text(encoding="utf-8"))
    result.update(
        {s: sum(r["status"] == s for r in rows) for s in ("PASS", "FAIL", "NOT_VERIFIED")}
    )
    result["confirmatory_record_count"] = sum(
        "/confirmatory/" in row["path"]
        and "/trials/" in row["path"]
        and row["path"].endswith(".json")
        and row["status"] == "PASS"
        for row in rows
    )
    result["overall_status"] = "PARTIAL" if result["NOT_VERIFIED"] else "PASS"
    (root / "historical.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    append_unverified() if "--append-unverified" in sys.argv else main()
