"""Run the frozen SCIENTIFIC-EXP-03B preflight or confirmatory series.

Examples:
  python scripts/run_scientific_exp03b.py --stage preflight --block all
  python scripts/run_scientific_exp03b.py --stage confirmatory --block metric
  python scripts/run_scientific_exp03b.py --stage confirmatory --block system

The runner has no wall-clock timeout. Ctrl+C is honored between complete paired
trials; rerun the same command to verify and resume immutable completed trials.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from hf_tcm.repro.atomic_io import atomic_replace_bytes
from hf_tcm.repro.exp03b_runner import (
    load_frozen_protocol,
    run_metric_series,
    run_system_series,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs/SCIENTIFIC_EXP_03B_PROTOCOL.json"
OUTPUT = ROOT / "outputs/scientific_exp03b"


def _write_json(path: Path, value: Any) -> None:
    atomic_replace_bytes(
        path,
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False).encode(
            "utf-8"
        )
        + b"\n",
    )


def _progress_printer(block: str):
    modulus = 20 if block == "metric" else 5

    def report(value: dict[str, Any]) -> None:
        completed = int(value["completed_trials"])
        if completed % modulus == 0 or completed == int(value["planned_trials"]):
            print(json.dumps(value, ensure_ascii=False, sort_keys=True), flush=True)

    return report


def run(
    stage: str, block: str, scenario_filter: str | None, sweep_filter: str | None, output_root: Path
) -> int:
    protocol, _, protocol_hash, _ = load_frozen_protocol(PROTOCOL)
    state_path = output_root / f"{stage}_execution_state.json"
    state: dict[str, Any] = {
        "protocol_sha256": protocol_hash,
        "stage": stage,
        "status": "running",
        "studies": [],
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _write_json(state_path, state)

    try:
        if block in {"metric", "all"}:
            scenarios = protocol["metric_isolation"]["scenarios"]
            sweeps = protocol["metric_isolation"]["sweeps"]
            for scenario in scenarios:
                key = scenario["id"]
                if scenario_filter and scenario_filter not in {key, "awgn", "static", "rician"}:
                    continue
                if scenario_filter == "awgn" and not key.startswith("awgn"):
                    continue
                if scenario_filter == "static" and key != "static_pilot":
                    continue
                if scenario_filter == "rician" and not key.startswith("rician"):
                    continue
                for sweep in sweeps:
                    if sweep_filter and sweep != sweep_filter:
                        continue
                    summary = run_metric_series(
                        PROTOCOL,
                        output_root,
                        scenario_key=key,
                        sweep=sweep,
                        stage=stage,
                        progress_callback=_progress_printer("metric"),
                    )
                    state["studies"].append(summary)
                    _write_json(state_path, state)

        if block in {"system", "all"}:
            for scenario in ("awgn", "static", "rician"):
                if scenario_filter and scenario_filter != scenario:
                    continue
                summary = run_system_series(
                    PROTOCOL,
                    output_root,
                    scenario=scenario,
                    stage=stage,
                    progress_callback=_progress_printer("system"),
                )
                state["studies"].append(summary)
                _write_json(state_path, state)
    except KeyboardInterrupt:
        state["status"] = "interrupted_between_trials"
        state["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _write_json(state_path, state)
        print(
            "Interrupted. Completed trial payloads are checkpointed; rerun the same command to resume.",
            file=sys.stderr,
        )
        return 130
    except Exception as exc:
        state["status"] = "failed_or_resource_guard"
        state["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        state["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _write_json(state_path, state)
        raise

    state["status"] = (
        "completed"
        if all(item["status"] == "completed" for item in state["studies"])
        else "partial"
    )
    state["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_json(state_path, state)
    print(
        json.dumps(
            {"state": str(state_path), "status": state["status"], "studies": len(state["studies"])},
            ensure_ascii=False,
        )
    )
    return 0 if state["status"] == "completed" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("preflight", "confirmatory"), required=True)
    parser.add_argument("--block", choices=("metric", "system", "all"), default="all")
    parser.add_argument("--scenario", default=None)
    parser.add_argument(
        "--sweep", choices=("amplitude_fixed_noise", "noise_fixed_amplitude"), default=None
    )
    parser.add_argument("--output-root", type=Path, default=OUTPUT)
    args = parser.parse_args()
    return run(args.stage, args.block, args.scenario, args.sweep, args.output_root)


if __name__ == "__main__":
    raise SystemExit(main())
