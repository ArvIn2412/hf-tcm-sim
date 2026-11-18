"""SCIENTIFIC-EXP-04 runner.

python scripts/run_scientific_exp04.py preflight            # validates, times; no series
python scripts/run_scientific_exp04.py freeze               # writes <protocol>.sha256 (after approval)
python scripts/run_scientific_exp04.py run --approve <SHA256> [--cell A1-awgn ...]
python scripts/run_scientific_exp04.py analyze [--cell ...] # gains at all targets from stored trials
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hf_tcm.repro.exp04_protocol import (
    DEFAULT_OUTPUT,
    DEFAULT_PROTOCOL,
    analyze_cell,
    load_protocol,
    preflight,
    run_cells,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("command", choices=["preflight", "freeze", "run", "analyze"])
    parser.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--cell", action="append", default=[])
    parser.add_argument("--approve", default="")
    parser.add_argument("--timing-trials", type=int, default=3)
    args = parser.parse_args()
    protocol_path = Path(args.protocol)
    protocol, digest, status = load_protocol(protocol_path)
    output = Path(args.output)
    cells = args.cell or [cell["id"] for cell in protocol["cells"]]

    if args.command == "preflight":
        report = preflight(protocol, digest, timing_trials=args.timing_trials)
        report["freeze_status"] = status
        output.mkdir(parents=True, exist_ok=True)
        (output / "preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        for row in report["cells"]:
            print(
                f"{row['cell']:<28} {row['points']:>3} pts x {row['trials_per_point']:>4} "
                f"= {row['planned_trials']:>6} trials  {row['seconds_per_trial']:.3f} s/trial  "
                f"~{row['estimated_seconds'] / 60:7.1f} min  budget ok={row['fits_budget']}  "
                f"Eb/N0 axis ok={row['eb_n0_axis_ok']}"
            )
        print(
            f"total ~{report['estimated_total_seconds'] / 3600:.2f} h; protocol {status} {digest}"
        )
    elif args.command == "freeze":
        sidecar = protocol_path.with_name(protocol_path.name + ".sha256")
        sidecar.write_text(f"{digest}  {protocol_path.name}\n", encoding="utf-8")
        print(f"frozen {protocol_path} -> {digest}")
    elif args.command == "run":
        for summary in run_cells(
            protocol_path, cells, approve_sha256=args.approve, output_root=output
        ):
            print(summary["experiment_id"], summary["status"], summary["completed_trials"])
    else:
        results = []
        for cell in cells:
            root = output / "studies" / f"exp04-{cell}"
            if not root.is_dir():
                print(f"{cell}: no stored study")
                continue
            results.append(analyze_cell(protocol, cell, root))
        output.mkdir(parents=True, exist_ok=True)
        (output / "analysis.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        for item in results:
            for target, value in item["targets"].items():
                print(item["cell"], target, value["verdict"], value["gain_db"], value["ci95_db"])


if __name__ == "__main__":
    main()
