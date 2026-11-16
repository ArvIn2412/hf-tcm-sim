"""Measure bounded in-memory SCIENTIFIC-EXP-03A paired-trial runtimes."""

from __future__ import annotations

import json
import time
from pathlib import Path

from hf_tcm.repro.metric_experiment import MetricTrialSpec, run_metric_trial
from scripts.run_scientific_exp03a_range_pilot import _channel


def main() -> int:
    designs = (
        ("awgn_direct", "awgn", "awgn_direct_control", 831091, 32),
        ("awgn_pilot", "awgn-pilot", "pilot_equalized", 831092, 32),
        ("static_d3", "static", "pilot_equalized", 831093, 32),
        ("rician_period32", "rician", "pilot_equalized", 831094, 32),
        ("rician_period8", "rician", "pilot_equalized", 831095, 8),
    )
    report = []
    for name, channel_name, frontend, root_seed, period in designs:
        seconds = []
        for trial_index in range(5):
            config = _channel(channel_name, root_seed + trial_index)
            spec = MetricTrialSpec(
                trial_id=f"bench-{name}-{trial_index}",
                frame_symbols=128,
                source_seed=root_seed + trial_index,
                channel_config=config,
                frontend_mode=frontend,  # type: ignore[arg-type]
                amplitude=1.0,
                preamble_symbols=4,
                pilot_period=period,
                pilot_burst_symbols=4,
            )
            started = time.perf_counter()
            run_metric_trial(spec)
            seconds.append(time.perf_counter() - started)
        report.append(
            {
                "scenario": name,
                "frame_symbols": 128,
                "trials": len(seconds),
                "mean_paired_trial_wall_seconds": sum(seconds) / len(seconds),
                "min_seconds": min(seconds),
                "max_seconds": max(seconds),
                "pilot_period": period if frontend == "pilot_equalized" else None,
                "confirmatory": False,
                "output_records_written": False,
            }
        )
    destination = Path("outputs/scientific-exp03a/validation/runtime_benchmark.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
