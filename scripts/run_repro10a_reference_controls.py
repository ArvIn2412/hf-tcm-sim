"""Create new, immutable REPRO-10A identity/static/Rician control runs."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hf_tcm.studio.scientific import ScientificRunConfig, run_scientific_run

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "repro10a" / "reference_runs"
COMMON = {
    "frame_symbols": 32,
    "source_seed": 1010,
    "channel_seed": 9010,
    "traceback_depth": 20,
}
CONFIGS = (
    ScientificRunConfig(
        run_id="repro10a-identity-f32",
        channel_profile="identity",
        noise_variance=0.0,
        delays_samples=(0,),
        path_coefficients=((1.0, 0.0),),
        include_b1=True,
        **COMMON,
    ),
    ScientificRunConfig(
        run_id="repro10a-static-multipath-f32",
        channel_profile="static_multipath",
        noise_variance=0.0,
        delays_samples=(0, 3),
        path_coefficients=((0.8, 0.0), (0.2, -0.1)),
        include_b1=True,
        **COMMON,
    ),
    ScientificRunConfig(
        run_id="repro10a-rician-ar1-f32",
        channel_profile="rician_ar1_multipath",
        noise_variance=0.005,
        delays_samples=(0, 3),
        include_b1=False,
        **COMMON,
    ),
)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    for config in CONFIGS:
        summary = run_scientific_run(
            ScientificRunConfig(**{**asdict(config), "output_root": str(OUTPUT)})
        )
        row = {
            "config": {**asdict(config), "output_root": str(OUTPUT)},
            "run_id": summary["run_id"],
            "observation_sha256": summary["receiver_observation_sha256"],
            "sample_count": summary["sample_count"],
            "paired_observation_verified": summary["paired_observation_verified"],
            "joint": {
                key: summary["joint"][key]
                for key in (
                    "compared_bits",
                    "bit_errors",
                    "ber",
                    "compared_information_pairs",
                    "information_pair_errors",
                    "information_pair_ser",
                    "phase_symbol_errors",
                    "phase_symbol_ser",
                    "runtime_seconds",
                )
            },
            "separate": {
                key: summary["separate"][key]
                for key in (
                    "compared_bits",
                    "bit_errors",
                    "ber",
                    "compared_information_pairs",
                    "information_pair_errors",
                    "information_pair_ser",
                    "phase_symbol_errors",
                    "phase_symbol_ser",
                    "runtime_seconds",
                )
            },
            "b1": summary["b1"],
            "truth_is_receiver_input": summary["channel"]["truth_is_receiver_input"],
        }
        results.append(row)
    target = ROOT / "outputs" / "repro10a" / "reference_control_summary.json"
    target.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
