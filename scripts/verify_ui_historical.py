"""Read-only SHA-256 audit against original checkpoint manifests."""

import csv
import hashlib
import json
import time
from pathlib import Path

ROOT = Path("outputs/scientific_exp03b")
OUT = Path("outputs/ui_article_alignment")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    start = time.monotonic()
    rows = []
    with (OUT / "historical_sha256.csv").open("w", encoding="utf8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "expected", "actual", "status"])
        writer.writeheader()
        for checkpoint in ROOT.glob("**/checkpoint.jsonl"):
            folder = checkpoint.parent
            manifest_path = folder / "manifest.json"
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf8"))
                if manifest_path.exists()
                else {}
            )
            targets = [(checkpoint, manifest.get("checkpoint_sha256"))]
            for line in checkpoint.read_text(encoding="utf8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                for key in ("record", "array"):
                    if entry.get(key + "_path"):
                        targets.append((folder / entry[key + "_path"], entry.get(key + "_sha256")))
            for p, expected in targets:
                try:
                    if not p.resolve().is_relative_to(ROOT.resolve()):
                        raise ValueError("escaped path")
                    actual = sha(p)
                    status = (
                        "NOT_VERIFIED" if not expected else "PASS" if actual == expected else "FAIL"
                    )
                except (OSError, ValueError):
                    actual = ""
                    status = "NOT_VERIFIED"
                row = dict(path=str(p), expected=expected or "", actual=actual, status=status)
                writer.writerow(row)
                rows.append(row)
            f.flush()
            print(folder, len(rows), flush=True)
        # Protocol/source checks require an existing independently recorded digest.
        for p in [
            Path("docs/research/SCIENTIFIC_EXP_03B_FROZEN_PROTOCOL.md"),
            Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json"),
        ]:
            writer.writerow(dict(path=str(p), expected="", actual=sha(p), status="NOT_VERIFIED"))
            rows.append(dict(status="NOT_VERIFIED"))
    result = {s: sum(r["status"] == s for r in rows) for s in ("PASS", "FAIL", "NOT_VERIFIED")}
    result["seconds"] = time.monotonic() - start
    (OUT / "historical_sha256_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf8"
    )
    print(result)


if __name__ == "__main__":
    main()
