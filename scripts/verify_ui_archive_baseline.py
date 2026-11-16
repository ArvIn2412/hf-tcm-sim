"""Compare historical protocol, reports and figures with the archived manifest."""

import csv
import hashlib
import json
import zipfile
from pathlib import Path


def main():
    out = Path("outputs/ui_article_alignment")
    with zipfile.ZipFile("HF_TCM_SIM_EXP03B_CHATGPT_AUDIT_COMPACT.zip") as archive:
        name = next(n for n in archive.namelist() if n.endswith("/full_archive_manifest.json"))
        baseline = json.loads(archive.read(name))
    rows = []
    with (out / "historical_sha256.csv").open(encoding="utf8", newline="") as source:
        already = {
            r["path"].replace("\\", "/"): r["actual"] for r in csv.DictReader(source) if r["actual"]
        }
    for entry in baseline["files"]:
        name = entry["path"]
        selected = (
            (name.startswith("configs/") and "03B" in name)
            or (name.startswith("docs/research/") and ("03B" in name or "CHAPTER_4" in name))
            or (
                name.startswith("outputs/scientific_exp03b/")
                and "/trials/" not in name
                and not name.endswith(".npz")
            )
        )
        if not selected:
            continue
        path = Path(name)
        try:
            actual = already.get(name) or hashlib.sha256(path.read_bytes()).hexdigest()
            status = "PASS" if actual == entry["sha256"] else "FAIL"
        except OSError:
            actual = ""
            status = "NOT_VERIFIED"
        rows.append(dict(path=name, expected=entry["sha256"], actual=actual, status=status))
    with (out / "historical_archive_baseline.csv").open("w", encoding="utf8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "expected", "actual", "status"])
        w.writeheader()
        w.writerows(rows)
    summary = {s: sum(r["status"] == s for r in rows) for s in ("PASS", "FAIL", "NOT_VERIFIED")}
    (out / "historical_archive_baseline_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf8"
    )
    print(summary)


if __name__ == "__main__":
    main()
