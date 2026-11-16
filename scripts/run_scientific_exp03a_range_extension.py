"""Run only the separately frozen bounded SCIENTIFIC-EXP-03A range extension."""

from __future__ import annotations

import json
from pathlib import Path

from hf_tcm.repro.metric_experiment import MetricStudyConfig, run_metric_study
from scripts.run_scientific_exp03a_range_pilot import _channel


def main() -> int:
    designs = (
        ("awgn", "awgn_direct_control", 831041, (-18.0, -16.5, -15.0), 32),
        ("awgn-pilot", "pilot_equalized", 831042, (-12.0, -10.5, -9.0, -7.5), 32),
        ("static", "pilot_equalized", 831043, (-13.5, -12.0, -10.5, -9.0), 32),
        ("rician", "pilot_equalized", 831044, (-3.0, 0.0, 3.0, 6.0, 9.0), 32),
        ("rician-pilot8", "pilot_equalized", 831045, (-3.0, 0.0, 3.0, 6.0, 9.0), 8),
    )
    root = Path("outputs/scientific-exp03a/metric-studies")
    summaries = []
    for scenario_name, frontend, seed, grid, pilot_period in designs:
        scenario = (
            "awgn"
            if scenario_name.startswith("awgn")
            else "rician"
            if scenario_name == "rician-pilot8"
            else scenario_name
        )
        experiment_id = {
            "awgn": "exp03a-range2-awgn-direct-v1",
            "awgn-pilot": "exp03a-range2-awgn-pilot-v1",
            "static": "exp03a-range2-static-d3-v1",
            "rician": "exp03a-range2-rician-ar1-v1",
            "rician-pilot8": "exp03a-range2-rician-pilot8-v1",
        }[scenario_name]
        config = MetricStudyConfig(
            experiment_id=experiment_id,
            scenario=scenario,  # type: ignore[arg-type]
            phase="range_finding",
            frame_symbols=128,
            energy_grid_db=grid,
            trials_per_point=5,
            root_seed=seed,
            target_ber=0.05,
            time_budget_seconds=120.0,
            sweep="amplitude",
            amplitude=1.0,
            channel_config=_channel(
                "rician" if scenario_name == "rician-pilot8" else scenario_name, seed
            ).to_dict(),
            frontend_mode=frontend,  # type: ignore[arg-type]
            preamble_symbols=4,
            pilot_period=pilot_period,
            pilot_burst_symbols=4,
            bootstrap_replicates=500,
        )
        summary = run_metric_study(config, root)
        summaries.append(
            {
                "experiment_id": experiment_id,
                "status": summary["status"],
                "completed_trials": summary["completed_trials"],
                "planned_trials": summary["planned_trials"],
                "runtime_seconds": summary["runtime_seconds_this_invocation"],
                "paired_hashes_valid": summary["paired_hashes_valid"],
                "gain_status": summary["gain_analysis"]["status"],
                "gain_db": summary["gain_analysis"]["gain_db"],
            }
        )
        print(json.dumps(summaries[-1], ensure_ascii=False, sort_keys=True))
    return 0 if all(row["completed_trials"] == row["planned_trials"] for row in summaries) else 2


if __name__ == "__main__":
    raise SystemExit(main())
