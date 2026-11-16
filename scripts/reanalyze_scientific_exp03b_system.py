"""Recount and reaggregate the SCIENTIFIC-EXP-03B full-system block on its frozen grid."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from analyze_scientific_exp03b import (
    PROTOCOL_PATH,
    _analysis_precision_criteria,
    _context_seed,
    _manifest,
    _system_grid_gamma,
    _system_trial_id,
    _validate_system_observation_pair,
    _write_json,
)

from hf_tcm.repro.confirmatory_exp03b import build_system_trial_spec, system_trial_seeds
from hf_tcm.repro.exp03b_runner import load_frozen_protocol, sha256_file
from hf_tcm.repro.scientific_exp03b_analysis import (
    aggregate_paired_trials,
    assess_gain_precision,
    estimate_paired_gain,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT / "outputs/scientific_exp03b/analysis/independent_analysis_numeric_snapshot.json"
)
DEFAULT_DESTINATION = ROOT / "outputs/scientific_exp03b/analysis/independent_analysis.json"


def analyze_system_block(output_root: Path, source: dict[str, Any]) -> dict[str, Any]:
    protocol, _, protocol_hash, _ = load_frozen_protocol(PROTOCOL_PATH)
    if source.get("protocol_sha256") != protocol_hash:
        raise ValueError("numeric analysis source has a different frozen protocol hash")
    root_seed = int(protocol["analysis"]["bootstrap_seed_root"])
    replicates = int(protocol["analysis"]["bootstrap_resamples"])
    targets = [float(value) for value in protocol["system_comparison"]["targets_ber"]]
    precision = _analysis_precision_criteria(protocol, "system_comparison")
    comparison: dict[str, Any] = {}

    for scenario in ("awgn", "static", "rician"):
        grid = protocol["system_comparison"]["energy_grid_gamma_db"][scenario]
        trials_per_point = int(protocol["system_comparison"]["confirmatory_trials_per_point"])
        planned = len(grid) * trials_per_point
        root = output_root / "system" / "confirmatory" / scenario
        manifest = _manifest(root, planned, protocol_hash)
        old_provenance = source["full_system_comparison"][scenario]["provenance"]
        if (
            old_provenance["verification"].get("independent_count_replay") != "PASS"
            or old_provenance["verification"].get("nested_sha256_manifests") != "PASS"
            or old_provenance["verification"].get("paired_observation_hashes") != "PASS"
        ):
            raise ValueError(
                "source analysis does not record a complete raw-array verification pass"
            )
        paths = sorted((root / "trials").glob("*.json"))
        rows = []
        seen_ids: set[str] = set()
        seen_by_point = [0] * len(grid)
        recount = {
            arm: {"bit_errors": 0, "pair_errors": 0, "frame_errors": 0}
            for arm in protocol["system_comparison"]["channel_profiles"][scenario]["receiver_arms"]
        }
        for path in paths:
            sidecar = json.loads(path.read_text(encoding="utf-8"))
            point_index = int(sidecar["point_index"])
            trial_index = int(sidecar["trial_index"])
            spec = build_system_trial_spec(
                protocol, scenario, point_index, trial_index, "confirmatory"
            )
            expected_seeds = dict(
                zip(("bits", "fading", "noise"), system_trial_seeds(spec, scenario), strict=True)
            )
            record = sidecar["record"]
            if (
                sidecar["trial_id"] != _system_trial_id(scenario, point_index, trial_index)
                or sidecar["protocol_sha256"] != protocol_hash
                or sidecar["derived_seeds"] != expected_seeds
                or record["seeds"] != expected_seeds
            ):
                raise ValueError(f"sidecar provenance or seed mismatch: {path}")
            _validate_system_observation_pair(record)
            grid_gamma = _system_grid_gamma(
                protocol,
                scenario,
                point_index,
                float(sidecar["gamma_db"]),
                float(record["gamma_db"]),
                float(record["gamma_measured_db"]),
            )
            trial_id = str(sidecar["trial_id"])
            if trial_id in seen_ids:
                raise ValueError(f"duplicate system trial ID: {trial_id}")
            seen_ids.add(trial_id)
            seen_by_point[point_index] += 1
            for arm in recount:
                recount[arm]["bit_errors"] += int(record["bit_errors"][arm])
                recount[arm]["pair_errors"] += int(record["pair_errors"][arm])
                recount[arm]["frame_errors"] += int(record["frame_errors"][arm])
            rows.append(
                {
                    "trial_id": trial_id,
                    "scenario": scenario,
                    "sweep": "amplitude",
                    "phase": "confirmatory",
                    "gamma_db": grid_gamma,
                    "noise_variance": float(record["noise_variance"]),
                    "bits": int(record["bits"]),
                    "pairs": int(record["pairs"]),
                    "bit_errors": {key: int(value) for key, value in record["bit_errors"].items()},
                    "pair_errors": {
                        key: int(value) for key, value in record["pair_errors"].items()
                    },
                    "frame_errors": {
                        key: int(value) for key, value in record["frame_errors"].items()
                    },
                    "observation_sha256": record["observation_sha256"],
                    "energy_per_bit": float(record["eb_d"]),
                    "tx_energy_discrete": float(record["tx_energy"]),
                    "payload_signal_symbols": int(record["bits"] // 2),
                    "total_signal_symbols": int(record["frame_symbols"]),
                    "runtime_seconds": record["runtime_seconds"],
                    "receiver_process_cpu_seconds": record["receiver_process_cpu_seconds"],
                }
            )
        if (
            len(rows) != planned
            or len(seen_ids) != planned
            or any(count != trials_per_point for count in seen_by_point)
        ):
            raise ValueError(f"system sidecars do not cover every frozen point: {scenario}")
        if recount != old_provenance["recounted_counts"]:
            raise ValueError(
                f"sidecar recount differs from previously validated NPZ arrays: {scenario}"
            )
        provenance = {
            "study_id": manifest.get("study_id"),
            "root": root,
            "manifest": manifest,
            "manifest_sha256": sha256_file(root / "manifest.json"),
            "verification": old_provenance["verification"],
            "independent_count_replay": "PASS",
            "recounted_counts": recount,
        }
        points = aggregate_paired_trials(
            rows,
            replicates=replicates,
            seed=_context_seed(root_seed, f"system:{scenario}", 0),
        )
        arms = tuple(sorted(rows[0]["bit_errors"]))
        separate_arms = [arm for arm in arms if arm != "joint"]
        gains: dict[str, Any] = {}
        for target_index, target in enumerate(targets):
            gains[f"{target:g}"] = {}
            for arm in separate_arms:
                estimate = estimate_paired_gain(
                    rows,
                    target=target,
                    euclidean_arm="joint",
                    hamming_arm=arm,
                    replicates=replicates,
                    seed=_context_seed(root_seed, f"system-gain:{scenario}:{arm}", target_index),
                )
                estimate["precision_assessment"] = assess_gain_precision(
                    estimate,
                    points,
                    target=target,
                    arms=("joint", arm),
                    estimate_arms=("euclidean", "hamming"),
                    precision_criteria=precision,
                )
                gains[f"{target:g}"][arm] = estimate
        runtime = {
            arm: {
                "wall_seconds_mean": float(
                    sum(row["runtime_seconds"][arm] for row in rows) / len(rows)
                ),
                "wall_seconds_median": float(
                    statistics.median(row["runtime_seconds"][arm] for row in rows)
                ),
                "cpu_seconds_mean": float(
                    sum(row["receiver_process_cpu_seconds"][arm] for row in rows) / len(rows)
                ),
            }
            for arm in arms
        }
        comparison[scenario] = {
            "provenance": {
                key: str(value) if isinstance(value, Path) else value
                for key, value in provenance.items()
            },
            "point_summaries": points,
            "energy_gain": gains,
            "runtime": runtime,
            "arms": list(arms),
            "paired_observation_hashes_unique": len({row["observation_sha256"] for row in rows}),
            "energy_grid_grouping": "frozen point_index; measured gamma checked within 1e-9 dB",
        }
    return comparison


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs/scientific_exp03b")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    result = analyze_system_block(args.output_root, source)
    source["full_system_comparison"] = result
    _write_json(args.destination, source)
    manifest = {
        "schema_version": "scientific-exp03b-analysis-manifest-v1",
        "analysis_sha256": sha256_file(args.destination),
        "protocol_sha256": source["protocol_sha256"],
        "confirmatory_only": True,
        "system_energy_grid_grouping": "frozen point_index with measured-energy tolerance check",
        "independent_system_recount": "PASS",
    }
    _write_json(args.destination.with_name("analysis_manifest.json"), manifest)
    print(
        json.dumps(
            {
                "destination": str(args.destination),
                "scenarios": {
                    scenario: {
                        "points": len(section["point_summaries"]),
                        "trials": sum(point["trials"] for point in section["point_summaries"]),
                    }
                    for scenario, section in result.items()
                },
                "manifest_sha256": sha256_file(
                    args.destination.with_name("analysis_manifest.json")
                ),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
