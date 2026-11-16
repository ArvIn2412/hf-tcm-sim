"""Run the frozen, independently seeded SCIENTIFIC-EXP-01B energy series."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Any, Mapping

from hf_tcm.repro.energy_experiment import EnergyTrialSpec, run_energy_trial

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "configs/SCIENTIFIC_EXP_01B_PROTOCOL.json"
DEFAULT_OUTPUT = ROOT / "outputs/scientific_exp_01b"
RUNTIME_STALL_THRESHOLD_SECONDS = 60.0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_protocol(path: Path = DEFAULT_PROTOCOL) -> tuple[dict[str, Any], bytes, str]:
    raw = path.read_bytes()
    protocol = json.loads(raw.decode("utf-8"))
    validate_protocol(protocol)
    return protocol, raw, sha256(raw)


def validate_protocol(protocol: Mapping[str, Any]) -> None:
    if protocol.get("schema") != "scientific-exp01b-frozen-protocol-v1":
        raise ValueError("unsupported SCIENTIFIC-EXP-01B protocol schema")
    if protocol.get("phase") != "confirmatory" or protocol.get("sweep") != "amplitude":
        raise ValueError("01B requires a fresh confirmatory amplitude sweep")
    if protocol.get("paper_exact") is not False:
        raise ValueError("paper_exact must remain false")
    if (
        int(protocol.get("frame_symbols", 0)) != 256
        or int(protocol.get("trials_per_point", 0)) < 30
    ):
        raise ValueError("frozen frame length or independent cluster count is invalid")
    if float(protocol.get("fixed_complex_noise_variance", 0)) != 1.0:
        raise ValueError("frozen amplitude sweep requires fixed complex noise variance 1")
    scenarios = protocol.get("scenarios", {})
    if set(scenarios) != {"static", "rician"}:
        raise ValueError("01B requires static and Rician scenarios")
    static = scenarios["static"]
    if static["delays_samples"] != [0, 3] or static["receiver_arms"] != ["joint", "b0", "b1"]:
        raise ValueError("static scenario must preserve [0,3] and Joint/B0/B1")
    expected_static = [
        [math.sqrt(0.8), 0.0],
        [math.sqrt(0.2) * math.cos(0.7), math.sqrt(0.2) * math.sin(0.7)],
    ]
    for actual, expected in zip(static["path_coefficients"], expected_static, strict=True):
        if any(
            not math.isclose(float(a), b, rel_tol=0.0, abs_tol=1e-14)
            for a, b in zip(actual, expected, strict=True)
        ):
            raise ValueError("static public coefficients differ from the frozen path powers/phases")
    rician = scenarios["rician"]
    if rician["delays_samples"] != [0, 3] or rician["receiver_arms"] != ["joint", "b0"]:
        raise ValueError("Rician scenario must preserve [0,3] and Joint/B0")
    if rician.get("b1_available") is not False:
        raise ValueError("B1 must remain unavailable in Rician AR(1)")
    for name, step in (("static", 0.5), ("rician", 1.0)):
        grid = [float(value) for value in scenarios[name]["gamma_db_grid"]]
        if len(grid) < 4 or any(right - left != step for left, right in zip(grid, grid[1:])):
            raise ValueError(f"{name} energy grid does not match the frozen spacing")
    runtime = protocol["runtime_plan"]
    projected = runtime["projected_p90_static_seconds"] + runtime["projected_p90_rician_seconds"]
    if projected > runtime["total_runtime_budget_seconds"]:
        raise ValueError("frozen total budget is below the p90 runtime projection")


def trial_spec(
    protocol: Mapping[str, Any], scenario: str, point_index: int, trial_index: int
) -> EnergyTrialSpec:
    scenario_spec = protocol["scenarios"][scenario]
    return EnergyTrialSpec(
        phase="confirmatory",
        scenario=scenario,
        sweep="amplitude",
        gamma_db=float(scenario_spec["gamma_db_grid"][point_index]),
        point_index=point_index,
        trial_index=trial_index,
        frame_symbols=int(protocol["frame_symbols"]),
        root_seed=int(protocol["seed_policy"]["root_seed"]),
        noise_reference_variance=float(protocol["fixed_complex_noise_variance"]),
        receiver_arms=tuple(scenario_spec["receiver_arms"]),
    )


def _historical_seeds(path: Path) -> set[int]:
    manifest_path = path / "analysis/analysis_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"historical seed manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    seeds: set[int] = set()
    for source in manifest["source_records"]:
        record = json.loads((path / source["path"]).read_text(encoding="utf-8"))
        seeds.update(int(value) for value in record.get("seeds", {}).values())
    return seeds


def validate_seed_separation(
    protocol: Mapping[str, Any], historical_seed_root: Path
) -> dict[str, int]:
    prior = _historical_seeds(historical_seed_root)
    new: set[int] = set()
    spec_count = 0
    for scenario, spec in protocol["scenarios"].items():
        for point_index in range(len(spec["gamma_db_grid"])):
            for trial_index in range(int(protocol["trials_per_point"])):
                trial = trial_spec(protocol, scenario, point_index, trial_index)
                spec_count += 1
                new.update(int(seed) for seed in trial.seeds)
    if len(new) != spec_count * 3:
        raise ValueError("fresh seed plan contains an internal collision")
    overlap = new & prior
    if overlap:
        raise ValueError(f"new seed plan overlaps historical data ({len(overlap)} seeds)")
    return {
        "new_trial_count": spec_count,
        "new_stream_seeds": len(new),
        "historical_stream_seeds": len(prior),
        "overlap": 0,
    }


def _runtime_accounting(output_root: Path, scenario: str) -> dict[str, Any]:
    rows = []
    base = output_root / "confirmatory" / scenario / "amplitude"
    if base.exists():
        for record_path in base.glob("p*/t*/record.json"):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            runtimes = {key: float(value) for key, value in record["runtime_seconds"].items()}
            rows.append(
                {
                    "path": record_path.relative_to(output_root).as_posix(),
                    "elapsed": float(record["elapsed_seconds"]),
                    "runtimes": runtimes,
                    "record": record,
                }
            )

    def is_wall_stall(row: Mapping[str, Any]) -> bool:
        runtimes = row["runtimes"]
        if not runtimes:
            return False
        largest = max(runtimes.values())
        return (
            largest >= RUNTIME_STALL_THRESHOLD_SECONDS
            and row["elapsed"] >= largest
            and row["elapsed"] - largest <= max(5.0, 0.05 * row["elapsed"])
        )

    ordinary = [row for row in rows if not is_wall_stall(row)]
    corrections = []
    if ordinary:
        arm_names = sorted({arm for row in ordinary for arm in row["runtimes"]})
        arm_medians = {
            arm: statistics.median(
                row["runtimes"][arm] for row in ordinary if arm in row["runtimes"]
            )
            for arm in arm_names
        }
        overheads = [max(0.0, row["elapsed"] - sum(row["runtimes"].values())) for row in ordinary]
        overhead_median = statistics.median(overheads)
    else:
        arm_medians = {}
        overhead_median = 0.0

    effective_total = 0.0
    raw_total = 0.0
    for row in rows:
        raw_total += row["elapsed"]
        if is_wall_stall(row) and arm_medians:
            estimated = overhead_median + sum(arm_medians[arm] for arm in row["runtimes"])
            effective_total += estimated
            corrections.append(
                {
                    "record": row["path"],
                    "raw_elapsed_seconds": row["elapsed"],
                    "raw_receiver_seconds": row["runtimes"],
                    "budget_elapsed_seconds": estimated,
                    "reason": "receiver wall timer exceeded 60 seconds and accounted for nearly all trial elapsed time; treated as a process suspension outlier",
                }
            )
        else:
            effective_total += row["elapsed"]
    return {
        "effective_compute_seconds": effective_total,
        "raw_recorded_wall_seconds": raw_total,
        "record_count": len(rows),
        "suspension_outlier_count": len(corrections),
        "ordinary_receiver_medians_seconds": arm_medians,
        "ordinary_overhead_median_seconds": overhead_median,
        "corrections": corrections,
    }


def _used_runtime(output_root: Path, scenario: str) -> float:
    return float(_runtime_accounting(output_root, scenario)["effective_compute_seconds"])


def _write_runtime_audit(output_root: Path) -> dict[str, Any]:
    scenarios = {name: _runtime_accounting(output_root, name) for name in ("static", "rician")}
    result = {
        "schema": "scientific-exp01b-runtime-accounting-v1",
        "metric": "effective per-trial compute budget seconds",
        "raw_trial_elapsed_values_preserved": True,
        "outlier_rule_threshold_seconds": RUNTIME_STALL_THRESHOLD_SECONDS,
        "outlier_rule": "a receiver wall timer >= threshold that accounts for all but max(5 s, 5%) of the total frame elapsed time is excluded from the compute-budget estimate; its replacement estimate is median ordinary receiver runtime per arm plus median ordinary non-receiver overhead",
        "scenarios": scenarios,
    }
    _write_json(output_root / "runtime_measurement_audit.json", result)
    return result


def _completed_count(output_root: Path, scenario: str) -> int:
    base = output_root / "confirmatory" / scenario / "amplitude"
    return sum(1 for path in base.glob("p*/t*/manifest.json")) if base.exists() else 0


def _directory_size(path: Path) -> int:
    return (
        sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        if path.exists()
        else 0
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    for attempt in range(8):
        try:
            os.replace(pending, path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.25 * (attempt + 1))


def _snapshot_protocol(
    output_root: Path, protocol: Mapping[str, Any], raw: bytes, digest: str
) -> None:
    snapshot_path = output_root / "protocol_snapshot.json"
    if snapshot_path.exists():
        saved = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if saved.get("sha256") != digest:
            raise ValueError("existing 01B output was created from a different frozen protocol")
        if saved.get("protocol") != protocol:
            raise ValueError("existing 01B protocol snapshot differs from the frozen file")
    else:
        _write_json(
            snapshot_path, {"sha256": digest, "protocol": protocol, "raw_utf8": raw.decode("utf-8")}
        )


def run_study(protocol_path: Path, output_root: Path) -> dict[str, Any]:
    protocol, raw, protocol_hash = load_protocol(protocol_path)
    validate_seed_separation(protocol, ROOT / "outputs/scientific_exp_01")
    output_root.mkdir(parents=True, exist_ok=True)
    _snapshot_protocol(output_root, protocol, raw, protocol_hash)
    time_plan = protocol["runtime_plan"]
    overall_start = time.monotonic()
    runtime_audit = _write_runtime_audit(output_root)
    scenario_spent = {name: _used_runtime(output_root, name) for name in ("static", "rician")}
    scenario_raw_elapsed = {
        name: float(runtime_audit["scenarios"][name]["raw_recorded_wall_seconds"])
        for name in ("static", "rician")
    }
    scenario_completed = {
        name: _completed_count(output_root, name) for name in ("static", "rician")
    }
    disk_used_bytes = _directory_size(output_root)
    progress_path = output_root / "progress.json"
    state = {
        "experiment_id": protocol["experiment_id"],
        "protocol_sha256": protocol_hash,
        "status": "running",
        "planned_pairs": sum(len(row["gamma_db_grid"]) for row in protocol["scenarios"].values())
        * int(protocol["trials_per_point"]),
        "completed_pairs": 0,
        "scenario": None,
        "updated_at_monotonic_seconds": 0.0,
        "budget_seconds": int(time_plan["total_runtime_budget_seconds"]),
    }
    try:
        for scenario in ("static", "rician"):
            spec_config = protocol["scenarios"][scenario]
            scenario_budget = int(time_plan[f"{scenario}_runtime_budget_seconds"])
            state["scenario"] = scenario
            for point_index, gamma_db in enumerate(spec_config["gamma_db_grid"]):
                for trial_index in range(int(protocol["trials_per_point"])):
                    total_spent = sum(scenario_spent.values())
                    if scenario_spent[scenario] >= scenario_budget or total_spent >= int(
                        time_plan["total_runtime_budget_seconds"]
                    ):
                        break
                    if disk_used_bytes >= int(time_plan["disk_budget_bytes"]):
                        state["status"] = "disk_budget_exhausted"
                        raise StopIteration
                    trial = trial_spec(protocol, scenario, point_index, trial_index)
                    trial_dir = (
                        output_root
                        / "confirmatory"
                        / scenario
                        / "amplitude"
                        / f"p{point_index:02d}"
                        / f"t{trial_index:04d}"
                    )
                    existing = (trial_dir / "manifest.json").exists()
                    if existing:
                        continue
                    trial_size_before = _directory_size(trial_dir)
                    record = run_energy_trial(trial, output_root)
                    disk_used_bytes += max(0, _directory_size(trial_dir) - trial_size_before)
                    scenario_raw_elapsed[scenario] += float(record["elapsed_seconds"])
                    runtime_map = {
                        key: float(value) for key, value in record["runtime_seconds"].items()
                    }
                    largest_receiver_runtime = max(runtime_map.values(), default=0.0)
                    if largest_receiver_runtime >= RUNTIME_STALL_THRESHOLD_SECONDS:
                        runtime_audit = _write_runtime_audit(output_root)
                        scenario_spent[scenario] = float(
                            runtime_audit["scenarios"][scenario]["effective_compute_seconds"]
                        )
                    else:
                        scenario_spent[scenario] += float(record["elapsed_seconds"])
                    scenario_completed[scenario] += 1
                    state["completed_pairs"] = sum(scenario_completed.values())
                    state["scenario_runtime_seconds"] = dict(scenario_spent)
                    state["scenario_recorded_wall_seconds"] = dict(scenario_raw_elapsed)
                    state["updated_at_monotonic_seconds"] = time.monotonic() - overall_start
                    _write_json(progress_path, state)
                    if (
                        state["completed_pairs"] % 10 == 0
                        or state["completed_pairs"] == state["planned_pairs"]
                    ):
                        print(
                            f"\r{scenario}: {state['completed_pairs']}/{state['planned_pairs']} paired frames; "
                            f"recorded runtime {sum(scenario_spent.values()):.1f}s",
                            end="\n",
                            flush=True,
                        )
                if scenario_spent[scenario] >= scenario_budget or sum(
                    scenario_spent.values()
                ) >= int(time_plan["total_runtime_budget_seconds"]):
                    break
            state["completed_pairs"] = sum(scenario_completed.values())
            _write_json(progress_path, state)
            if state["status"] == "disk_budget_exhausted":
                break
        if state["status"] == "running":
            complete = state["completed_pairs"] == state["planned_pairs"]
            state["status"] = "completed" if complete else "partial_budget"
    except KeyboardInterrupt:
        state["status"] = "paused_by_user"
        state["completed_pairs"] = _completed_count(output_root, "static") + _completed_count(
            output_root, "rician"
        )
    except StopIteration:
        pass
    state["updated_at_monotonic_seconds"] = time.monotonic() - overall_start
    state["scenario_runtime_seconds"] = {
        scenario: _used_runtime(output_root, scenario) for scenario in ("static", "rician")
    }
    runtime_audit = _write_runtime_audit(output_root)
    state["scenario_recorded_wall_seconds"] = {
        scenario: float(runtime_audit["scenarios"][scenario]["raw_recorded_wall_seconds"])
        for scenario in ("static", "rician")
    }
    _write_json(progress_path, state)

    run_manifest = []
    for scenario in ("static", "rician"):
        base = output_root / "confirmatory" / scenario / "amplitude"
        for manifest_path in sorted(base.glob("p*/t*/manifest.json")) if base.exists() else []:
            record_path = manifest_path.parent / "record.json"
            run_manifest.append(
                {
                    "scenario": scenario,
                    "path": record_path.relative_to(output_root).as_posix(),
                    "record_sha256": sha256(record_path.read_bytes()),
                    "trial_manifest_sha256": sha256(manifest_path.read_bytes()),
                }
            )
    _write_json(
        output_root / "study_manifest.json",
        {
            "schema": "scientific-exp01b-study-manifest-v1",
            "experiment_id": protocol["experiment_id"],
            "protocol_sha256": protocol_hash,
            "status": state["status"],
            "planned_pairs": state["planned_pairs"],
            "completed_pairs": state["completed_pairs"],
            "records": run_manifest,
        },
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="validate the frozen grid and fresh seed domain without running trials",
    )
    args = parser.parse_args()
    if args.plan_only:
        protocol, _, digest = load_protocol(args.protocol)
        separation = validate_seed_separation(protocol, ROOT / "outputs/scientific_exp_01")
        plan = protocol["runtime_plan"]
        print(
            json.dumps(
                {
                    "protocol_sha256": digest,
                    "seed_separation": separation,
                    "trials_per_scenario": {
                        name: len(spec["gamma_db_grid"]) * int(protocol["trials_per_point"])
                        for name, spec in protocol["scenarios"].items()
                    },
                    "runtime_budget_seconds": plan["total_runtime_budget_seconds"],
                    "projected_p90_seconds": plan["projected_p90_static_seconds"]
                    + plan["projected_p90_rician_seconds"],
                    "disk_budget_bytes": plan["disk_budget_bytes"],
                    "output_created": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    run_study(args.protocol, args.output)


if __name__ == "__main__":
    main()
