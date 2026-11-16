"""Run only the frozen bounded SCIENTIFIC-EXP-03A range-finding controls."""

from __future__ import annotations

import json
from pathlib import Path

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.metric_experiment import MetricStudyConfig, run_metric_study


def _common(noise_seed: int, fading_seed: int) -> dict:
    return {
        "noise_model": "complex_awgn_sample_domain",
        "noise_complex_variance": 0.05,
        "fading_seed": fading_seed,
        "noise_seed": noise_seed,
        "reveal_noise_variance": True,
        "boundary_policy": "zero_extension",
        "output_length_policy": "tx_plus_max_delay",
        "rng_algorithm": "numpy.PCG64",
        "schema_version": "repro03-channel-v1",
    }


def _channel(name: str, root_seed: int) -> ChannelConfig:
    common = _common(root_seed + 18, root_seed + 17)
    if name in {"awgn", "awgn-pilot"}:
        return ChannelConfig(
            profile_id="awgn",
            paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
            fading_mode="constant",
            correlation=0.0,
            **common,
        )
    if name == "static":
        return ChannelConfig(
            profile_id="static_multipath",
            paths=(
                ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),
                ChannelPathConfig(3, 0.13, 0.0, constant_coefficient=0.3 - 0.2j),
            ),
            fading_mode="constant",
            correlation=0.0,
            **common,
        )
    return ChannelConfig(
        profile_id="rician_ar1_multipath",
        paths=(
            ChannelPathConfig(0, 1.0, 4.0, 0.0),
            ChannelPathConfig(3, 0.25, 1.0, 0.7),
        ),
        fading_mode="rician_ar1",
        correlation=0.98,
        **common,
    )


def main() -> int:
    designs = (
        ("awgn", "awgn_direct_control", 831031),
        ("awgn-pilot", "pilot_equalized", 831032),
        ("static", "pilot_equalized", 831033),
        ("rician", "pilot_equalized", 831034),
    )
    root = Path("outputs/scientific-exp03a/metric-studies")
    summaries = []
    for scenario_name, frontend, seed in designs:
        scenario = "awgn" if scenario_name.startswith("awgn") else scenario_name
        experiment_id = {
            "awgn": "exp03a-pilot-awgn-direct-v1",
            "awgn-pilot": "exp03a-pilot-awgn-pilot-v1",
            "static": "exp03a-pilot-static-d3-v1",
            "rician": "exp03a-pilot-rician-ar1-v1",
        }[scenario_name]
        config = MetricStudyConfig(
            experiment_id=experiment_id,
            scenario=scenario,  # type: ignore[arg-type]
            phase="range_finding",
            frame_symbols=128,
            energy_grid_db=(-15.0, -12.0, -9.0, -6.0, -3.0),
            trials_per_point=5,
            root_seed=seed,
            target_ber=0.05,
            time_budget_seconds=120.0,
            sweep="amplitude",
            amplitude=1.0,
            channel_config=_channel(scenario_name, seed).to_dict(),
            frontend_mode=frontend,  # type: ignore[arg-type]
            preamble_symbols=4,
            pilot_period=32,
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
