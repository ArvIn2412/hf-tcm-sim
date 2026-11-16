"""Locate the named original archive without reading unrelated file contents."""

from __future__ import annotations

import json
import os
from pathlib import Path

NAME = "HF_TCM_SIM_SCIENTIFIC_EXP_01_ENERGY_AUDIT.zip"


def main() -> None:
    home = Path.home()
    roots = [
        home / p
        for p in (
            "OneDrive",
            "Downloads",
            "Documents",
            "Desktop",
            "source",
            "PycharmProjects",
            "AppData/Local/Temp",
        )
    ]
    roots += [Path("C:/Temp"), Path("C:/tmp"), Path("C:/Users/Public")]
    result: dict = {"name": NAME, "roots": [str(p) for p in roots], "found": [], "inaccessible": []}
    count = 0
    for root in roots:
        if not root.exists():
            continue
        for folder, directories, files in os.walk(
            root, onerror=lambda error: result["inaccessible"].append(str(error.filename))
        ):
            directories[:] = [
                p
                for p in directories
                if p not in {".git", ".venv", "venv", "node_modules", "__pycache__"}
                and not Path(folder, p).is_symlink()
            ]
            count += 1
            if NAME in files:
                result["found"].append(str(Path(folder, NAME)))
    result["directories_scanned"] = count
    target = Path("outputs/release_readiness/archive_search.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
