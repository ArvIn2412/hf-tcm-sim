"""Render publication figures from an already-computed SCIENTIFIC-EXP-03B analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyze_scientific_exp03b import render_figures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.analysis.read_text(encoding="utf-8"))
    exports = render_figures(result, args.destination)
    manifest_path = args.destination / "figure_exports.json"
    manifest_path.write_text(
        json.dumps(exports, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "analysis": str(args.analysis),
                "destination": str(args.destination),
                "figure_count": len(exports),
                "file_count": 2 * len(exports),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
