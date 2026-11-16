"""Record the exact source-quality CI commands and their real exit codes."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def main() -> int:
    output = Path("outputs/release_readiness")
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, command in (
        ("source_lint", ["ruff", "check", "src", "tests", "scripts/ci"]),
        ("source_format", ["ruff", "format", "--check", "src", "tests", "scripts/ci"]),
    ):
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / (name + ".log")).write_bytes(run.stdout)
        rows.append({"command": command, "exit_code": run.returncode})
        print(name, run.returncode)
    status = "PASS" if all(r["exit_code"] == 0 for r in rows) else "FAIL"
    (output / "source_quality.json").write_text(
        json.dumps({"status": status, "checks": rows}, indent=2), encoding="utf-8"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
