"""Run portable CI from a source-only snapshot with no research outputs or binaries."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    target = Path(tempfile.mkdtemp(prefix="release-portable-", dir=root / "tmp"))
    paths = set(
        subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode("utf-8").split("\0")
    )
    paths.update(
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root
        )
        .decode("utf-8")
        .split("\0")
    )
    excluded = {".zip", ".7z", ".npz", ".doc", ".docx", ".pdf", ".rtf", ".pptx", ".xlsx"}
    count = 0
    for name in sorted(paths - {""}):
        source = root / name
        if (
            not source.is_file()
            or name.startswith(("outputs/", "tmp/"))
            or source.suffix.lower() in excluded
        ):
            continue
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        count += 1
    env = {
        **os.environ,
        "PYTHONPATH": str(target / "src") + os.pathsep + str(target),
        "PYTHONIOENCODING": "utf-8",
    }
    location = subprocess.check_output(
        [sys.executable, "-c", "import hf_tcm; print(hf_tcm.__file__)"],
        cwd=target,
        env=env,
        text=True,
    ).strip()
    assert Path(location).resolve().is_relative_to(target.resolve()), location
    report = root / "outputs/release_readiness"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        "not historical",
        "--junitxml=" + str(report / "portable_source_only.xml"),
    ]
    result = subprocess.run(
        command,
        cwd=target,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    (report / "portable_source_only.log").write_text(result.stdout, encoding="utf-8")
    (report / "portable_source_only.json").write_text(
        json.dumps(
            {
                "snapshot": str(target),
                "source_files": count,
                "research_outputs_present_before_test": False,
                "binary_documents_copied": False,
                "module_location": location,
                "exit_code": result.returncode,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(result.stdout[-3500:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
