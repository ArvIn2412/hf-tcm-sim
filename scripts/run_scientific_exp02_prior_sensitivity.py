"""Run the preregistered EXP-02 prior sensitivity on saved EXP-01B frames."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.adaptive_multipath_config import AdaptiveMultipathReceiverConfig
from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver
from hf_tcm.repro.channel_result import ReceiverObservation, readonly
from hf_tcm.repro.exp02_prior_sensitivity import PRIOR_VARIANTS, prior_means_for_variant

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "SCIENTIFIC_EXP_02_PRIOR_SENSITIVITY.json"
SOURCE_ROOT = ROOT / "outputs" / "scientific_exp_01b"
OUTPUT_ROOT = ROOT / "outputs" / "scientific_exp_02" / "prior_sensitivity"
EXPECTED_PROTOCOL_SHA256 = "75b065c1d0a7f5c1f06af3bc290678a532e35d7c0062fb42f68f3914aaa6a5ab"
CHANNEL_MODEL_ID = "repro03_discrete_complex_baseband_v1"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode(
        "utf-8"
    )
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".pending", delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def _tree_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    canonical = _canonical_json(files)
    return {
        "root": str(root.relative_to(ROOT)),
        "file_count": len(files),
        "sha256": _sha256_bytes(canonical),
        "files": files,
    }


def _load_protocol() -> dict[str, Any]:
    snapshot = json.loads((SOURCE_ROOT / "protocol_snapshot.json").read_text(encoding="utf-8"))
    protocol_sha = snapshot.get("sha256")
    if protocol_sha != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("EXP-01B frozen protocol SHA-256 does not match the preregistered value")
    protocol = json.loads(snapshot["raw_utf8"])
    config = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if config.get("source_protocol_sha256") != protocol_sha:
        raise ValueError("EXP-02 is not linked to the verified EXP-01B protocol")
    if protocol["experiment_id"] != config["source_experiment_id"]:
        raise ValueError("EXP-02 source experiment identifier mismatch")
    if tuple(config["prior_variants"]) != PRIOR_VARIANTS:
        raise ValueError("frozen prior variant list differs from implementation")
    return config


def _trial_rows(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = json.loads((SOURCE_ROOT / "study_manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "scientific-exp01b-study-manifest-v1"
        or manifest.get("experiment_id") != protocol["source_experiment_id"]
        or manifest.get("protocol_sha256") != protocol["source_protocol_sha256"]
        or manifest.get("status") != "completed"
        or manifest.get("planned_pairs") != 2160
        or manifest.get("completed_pairs") != 2160
        or len(manifest.get("records", [])) != 2160
    ):
        raise ValueError("EXP-01B does not have the complete expected 2160-frame study manifest")
    static: dict[tuple[float, int], dict[str, Any]] = {}
    for source in manifest["records"]:
        if source.get("scenario") != "static":
            continue
        rel = Path(str(source.get("path", "")))
        if rel.is_absolute() or ".." in rel.parts or rel.suffix != ".json":
            raise ValueError("unsafe EXP-01B record path")
        trial_dir = (SOURCE_ROOT / rel).resolve().parent
        if SOURCE_ROOT.resolve() not in trial_dir.parents:
            raise ValueError("EXP-01B record path escaped source root")
        record_path = trial_dir / "record.json"
        manifest_path = trial_dir / "manifest.json"
        record_bytes = record_path.read_bytes()
        trial_manifest_bytes = manifest_path.read_bytes()
        if _sha256_bytes(record_bytes) != source.get("record_sha256"):
            raise ValueError(f"EXP-01B record integrity failure: {rel.as_posix()}")
        if _sha256_bytes(trial_manifest_bytes) != source.get("trial_manifest_sha256"):
            raise ValueError(f"EXP-01B trial manifest integrity failure: {rel.as_posix()}")
        record = json.loads(record_bytes.decode("utf-8"))
        key = (float(record["gamma_db"]), int(record["trial_index"]))
        static[key] = {"source": source, "trial_dir": trial_dir, "record": record}
    expected_gammas = [float(value) for value in protocol["energy_points_gamma_b_d_db"]]
    trial_indices = [int(value) for value in protocol["source_trial_indices_per_point"]]
    selected = []
    for gamma in expected_gammas:
        for trial_index in trial_indices:
            try:
                selected.append(static[(gamma, trial_index)])
            except KeyError as exc:
                raise ValueError(
                    f"missing frozen source trial gamma={gamma}, trial={trial_index}"
                ) from exc
    if len(selected) != protocol["compute_budget"]["planned_saved_observations"]:
        raise ValueError("selected EXP-01B frame count does not match preregistered design")
    return selected


def _validate_trial_files(trial: dict[str, Any]) -> dict[str, Any]:
    trial_dir = trial["trial_dir"]
    manifest = json.loads((trial_dir / "manifest.json").read_text(encoding="utf-8"))
    config_path = trial_dir / "config.json"
    if _sha256_file(config_path) != manifest.get("config_sha256"):
        raise ValueError("EXP-01B source config hash mismatch")
    for name, expected in manifest.get("files", {}).items():
        candidate = (trial_dir / name).resolve()
        if trial_dir.resolve() not in candidate.parents or _sha256_file(candidate) != expected:
            raise ValueError(f"EXP-01B source file hash mismatch: {name}")
    source_config = json.loads(config_path.read_text(encoding="utf-8"))
    record = trial["record"]
    if (
        source_config.get("phase") != "confirmatory"
        or source_config.get("scenario") != "static"
        or source_config.get("sweep") != "amplitude"
        or record.get("phase") != "confirmatory"
        or record.get("scenario") != "static"
        or record.get("sweep") != "amplitude"
        or record.get("receiver_arms") != ["joint", "b0", "b1"]
    ):
        raise ValueError("selected source frame is outside the frozen static confirmatory design")
    hashes = record.get("receiver_observation_hashes", {})
    if set(hashes) != {"joint", "b0", "b1"} or len(set(hashes.values())) != 1:
        raise ValueError("source receiver observations are not paired")
    return manifest


def _observation_and_evaluation_bits(
    trial: dict[str, Any],
) -> tuple[ReceiverObservation, np.ndarray, np.ndarray]:
    trial_dir = trial["trial_dir"]
    record = trial["record"]
    with np.load(trial_dir / "arrays.npz", allow_pickle=False) as archive:
        # Do not access channel coefficients, noise, transmitted samples, or any
        # other evaluation-truth arrays. Bits are copied only for post-decode scoring.
        received = archive["received_samples"].copy()
        information_bits = archive["information_bits"].copy()
        saved_joint_bits = archive["joint_decoded_bits"].copy()
    indices = np.arange(received.size, dtype=np.int64)
    channel_config = record["channel_config"]
    observation = ReceiverObservation(
        received_samples=readonly(received),
        absolute_sample_index=readonly(indices),
        sample_symbol_index=readonly(indices // 8),
        sample_local_index=readonly(indices % 8),
        samples_per_symbol=8,
        profile_id=str(channel_config["profile_id"]),
        model_id=CHANNEL_MODEL_ID,
        sampling_convention="discrete_complex_baseband_absolute_sample_index",
        boundary_policy=str(channel_config["boundary_policy"]),
        output_length_policy=str(channel_config["output_length_policy"]),
        noise_model=str(channel_config["noise_model"]),
        noise_complex_variance=None,
    )
    expected_hash = record["observation_sha256"]
    if observation.sha256 != expected_hash:
        raise ValueError(
            "reconstructed public ReceiverObservation hash does not match source record"
        )
    if any(value != observation.sha256 for value in record["receiver_observation_hashes"].values()):
        raise ValueError("receiver observation hashes do not match reconstructed input")
    return observation, information_bits, saved_joint_bits


def _variant_output_path(gamma: float, trial_index: int, variant: str) -> Path:
    gamma_tag = f"g{gamma:04.1f}".replace(".", "p")
    return OUTPUT_ROOT / gamma_tag / f"t{trial_index:04d}" / variant


def _read_verified_result(
    path: Path, source_hash: str, observation_hash: str
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        record_bytes = (path / "record.json").read_bytes()
        if _sha256_bytes(record_bytes) != manifest["files"]["record.json"]:
            raise ValueError("stored EXP-02 record hash mismatch")
        record = json.loads(record_bytes.decode("utf-8"))
        for name, expected in manifest["files"].items():
            if _sha256_file(path / name) != expected:
                raise ValueError(f"stored EXP-02 file hash mismatch: {name}")
        if (
            record.get("source_record_sha256") != source_hash
            or record.get("observation_sha256") != observation_hash
        ):
            raise ValueError("stored EXP-02 result has different source provenance")
        return record
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError(f"incomplete EXP-02 result at {path}") from exc


def _save_result(
    path: Path, config: dict[str, Any], record: dict[str, Any], decoded: np.ndarray
) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite existing EXP-02 result: {path}")
    path.mkdir(parents=True)
    config_bytes = _canonical_json(config)
    record_bytes = json.dumps(
        record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ).encode("utf-8")
    config_path = path / "receiver_config.json"
    record_path = path / "record.json"
    arrays_path = path / "decoded.npz"
    config_path.write_bytes(config_bytes)
    record_path.write_bytes(record_bytes)
    np.savez_compressed(arrays_path, decoded_information_bits=np.asarray(decoded, dtype=np.int8))
    file_hashes = {
        file.name: _sha256_file(file) for file in (config_path, record_path, arrays_path)
    }
    _atomic_json(
        path / "manifest.json", {"schema": "scientific-exp02-result-v1", "files": file_hashes}
    )


def _copy_source_frame(trial: dict[str, Any], gamma: float, trial_index: int) -> None:
    gamma_tag = f"g{gamma:04.1f}".replace(".", "p")
    dest = (
        ROOT / "outputs" / "scientific_exp_02" / "source_frames" / gamma_tag / f"t{trial_index:04d}"
    )
    if dest.exists():
        return
    dest.mkdir(parents=True)
    for name in ("arrays.npz", "config.json", "manifest.json", "record.json"):
        shutil.copyfile(trial["trial_dir"] / name, dest / name)
    source_hashes = {
        name: _sha256_file(dest / name)
        for name in ("arrays.npz", "config.json", "manifest.json", "record.json")
    }
    _atomic_json(
        dest / "copy_manifest.json",
        {"source_record_sha256": trial["source"]["record_sha256"], "files": source_hashes},
    )


def _metric_counts(reference: np.ndarray, decoded: np.ndarray) -> tuple[int, int, int]:
    if reference.shape != decoded.shape or reference.ndim != 1 or reference.size % 2:
        raise ValueError(
            "reference and decoded information bits must be aligned even-length vectors"
        )
    errors = np.asarray(reference != decoded, dtype=bool)
    bit_errors = int(errors.sum())
    pair_errors = int(errors.reshape(-1, 2).any(axis=1).sum())
    return bit_errors, pair_errors, int(bit_errors > 0)


def _paired_bootstrap(values: np.ndarray, seed: int, replicates: int) -> list[float] | None:
    if values.size < 2:
        return None
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(replicates, values.size))
    means = values[indices].mean(axis=1)
    return [float(x) for x in np.quantile(means, [0.025, 0.975])]


def _collect_analysis(protocol: dict[str, Any]) -> dict[str, Any]:
    rows = []
    expected = set(protocol["prior_variants"])
    for gamma in protocol["energy_points_gamma_b_d_db"]:
        for trial_index in protocol["source_trial_indices_per_point"]:
            per_variant = {}
            for variant in protocol["prior_variants"]:
                path = _variant_output_path(float(gamma), int(trial_index), variant)
                if not path.is_dir():
                    per_variant = {}
                    break
                record = _read_verified_result(
                    path,
                    _read_source_hash(gamma, trial_index),
                    _read_observation_hash(gamma, trial_index),
                )
                if record is None:
                    per_variant = {}
                    break
                per_variant[variant] = record
            if set(per_variant) != expected:
                continue
            hashes = {row["observation_sha256"] for row in per_variant.values()}
            if len(hashes) != 1:
                raise ValueError("paired EXP-02 variants contain different observations")
            rows.append(
                {"gamma_db": float(gamma), "trial_index": int(trial_index), "variants": per_variant}
            )
    points = []
    rng_seed = int(protocol["analysis"]["bootstrap_seed"])
    replicates = int(protocol["analysis"]["bootstrap_replicates"])
    for point_index, gamma in enumerate(protocol["energy_points_gamma_b_d_db"]):
        point_rows = [row for row in rows if row["gamma_db"] == float(gamma)]
        if not point_rows:
            continue
        total_bits = sum(row["variants"]["exact"]["bit_count"] for row in point_rows)
        total_pairs = sum(row["variants"]["exact"]["pair_count"] for row in point_rows)
        variant_metrics = {}
        exact_ber = np.asarray(
            [
                row["variants"]["exact"]["bit_errors"] / row["variants"]["exact"]["bit_count"]
                for row in point_rows
            ],
            dtype=float,
        )
        for variant in protocol["prior_variants"]:
            bit_errors = sum(row["variants"][variant]["bit_errors"] for row in point_rows)
            pair_errors = sum(row["variants"][variant]["pair_errors"] for row in point_rows)
            frame_errors = sum(row["variants"][variant]["frame_error"] for row in point_rows)
            per_frame_ber = np.asarray(
                [
                    row["variants"][variant]["bit_errors"] / row["variants"][variant]["bit_count"]
                    for row in point_rows
                ],
                dtype=float,
            )
            paired_deltas = per_frame_ber - exact_ber
            variant_metrics[variant] = {
                "trials": len(point_rows),
                "bit_errors": bit_errors,
                "bits": total_bits,
                "ber": bit_errors / total_bits,
                "pair_errors": pair_errors,
                "pairs": total_pairs,
                "information_pair_ser": pair_errors / total_pairs,
                "frame_errors": frame_errors,
                "fer": frame_errors / len(point_rows),
                "mean_paired_ber_delta_vs_exact": float(paired_deltas.mean()),
                "paired_frame_cluster_bootstrap_95_ci_ber_delta": _paired_bootstrap(
                    paired_deltas,
                    rng_seed + point_index * 100 + list(protocol["prior_variants"]).index(variant),
                    replicates,
                )
                if variant != "exact"
                else [0.0, 0.0],
                "mean_runtime_seconds": float(
                    np.mean([row["variants"][variant]["runtime_seconds"] for row in point_rows])
                ),
            }
        points.append(
            {"gamma_db": float(gamma), "trials": len(point_rows), "metrics": variant_metrics}
        )
    return {
        "schema": "scientific-exp02-prior-sensitivity-analysis-v1",
        "experiment_id": protocol["experiment_id"],
        "status": "COMPLETE"
        if len(rows) == protocol["compute_budget"]["planned_saved_observations"]
        else "PARTIAL",
        "inferential_status": "EXPLORATORY_PRIOR_SENSITIVITY_NOT_CONFIRMATORY_GAIN_EVIDENCE",
        "complete_paired_observations": len(rows),
        "planned_paired_observations": protocol["compute_budget"]["planned_saved_observations"],
        "receiver_calls_completed": sum(len(row["variants"]) for row in rows),
        "points": points,
        "energy_gain_db": None,
        "source_experiment_id": protocol["source_experiment_id"],
    }


def _read_source_hash(gamma: float, trial_index: int) -> str:
    gamma_tag = f"g{float(gamma):04.1f}".replace(".", "p")
    path = (
        ROOT
        / "outputs"
        / "scientific_exp_02"
        / "source_frames"
        / gamma_tag
        / f"t{int(trial_index):04d}"
        / "record.json"
    )
    return _sha256_file(path)


def _read_observation_hash(gamma: float, trial_index: int) -> str:
    gamma_tag = f"g{float(gamma):04.1f}".replace(".", "p")
    path = (
        ROOT
        / "outputs"
        / "scientific_exp_02"
        / "source_frames"
        / gamma_tag
        / f"t{int(trial_index):04d}"
        / "record.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))["observation_sha256"]


def run() -> dict[str, Any]:
    protocol = _load_protocol()
    started = time.monotonic()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    config_bytes = PROTOCOL_PATH.read_bytes()
    config_sha = _sha256_bytes(config_bytes)
    if (OUTPUT_ROOT / "protocol.sha256").exists():
        saved_sha = (OUTPUT_ROOT / "protocol.sha256").read_text(encoding="ascii").strip()
        if saved_sha != config_sha:
            raise ValueError("refusing to resume with a different preregistered EXP-02 protocol")
        saved_protocol = json.loads((OUTPUT_ROOT / "protocol.json").read_text(encoding="utf-8"))
        if saved_protocol != protocol:
            raise ValueError("saved EXP-02 protocol contents do not match the frozen configuration")
    else:
        _atomic_json(OUTPUT_ROOT / "protocol.json", protocol)
        (OUTPUT_ROOT / "protocol.sha256").write_text(config_sha + "\n", encoding="ascii")

    source_before = _tree_manifest(SOURCE_ROOT / "confirmatory")
    prior_baseline_path = OUTPUT_ROOT / "source_tree_before.json"
    if prior_baseline_path.exists():
        prior_baseline = json.loads(prior_baseline_path.read_text(encoding="utf-8"))
        if prior_baseline["sha256"] != source_before["sha256"]:
            raise ValueError("EXP-01B source tree differs from the saved immutable baseline")
    else:
        _atomic_json(prior_baseline_path, source_before)
    selected = _trial_rows(protocol)
    nominal = tuple(
        complex(float(real), float(imag))
        for real, imag in protocol["channel"]["public_nominal_coefficients"]
    )
    variants = tuple(protocol["prior_variants"])
    budget = float(protocol["compute_budget"]["total_wall_seconds"])
    completed_calls = 0
    stopped_for_budget = False
    for frame_number, trial in enumerate(selected, start=1):
        record = trial["record"]
        gamma = float(record["gamma_db"])
        trial_index = int(record["trial_index"])
        trial_manifest = _validate_trial_files(trial)
        source_hash = trial["source"]["record_sha256"]
        _copy_source_frame(trial, gamma, trial_index)
        observation, reference_bits, saved_joint_bits = _observation_and_evaluation_bits(trial)
        source_config = record["receiver_configs"]["joint"]
        base_config = AdaptiveMultipathReceiverConfig.from_dict(source_config)
        if base_config.channel_mode != "unknown_static" or base_config.expected_symbol_count != 256:
            raise ValueError(
                "selected Joint receiver config does not match frozen static F=256 design"
            )
        if tuple(base_config.delays_samples) != tuple(protocol["channel"]["delays_samples"]):
            raise ValueError("Joint delays do not match EXP-02 public channel profile")
        if not math.isclose(base_config.observation_noise_variance, 1.0, abs_tol=0.0):
            raise ValueError("Joint noise variance does not match frozen static profile")
        output_records = {}
        for variant in variants:
            out_path = _variant_output_path(gamma, trial_index, variant)
            existing = _read_verified_result(out_path, source_hash, observation.sha256)
            if existing is not None:
                output_records[variant] = existing
                continue
            if time.monotonic() - started >= budget:
                stopped_for_budget = True
                break
            means = prior_means_for_variant(nominal, variant)
            changed_paths = tuple(
                replace(path, prior_mean=mean)
                for path, mean in zip(base_config.paths, means, strict=True)
            )
            variant_config = replace(base_config, paths=changed_paths)
            receiver_started = time.perf_counter()
            result = run_adaptive_multipath_receiver(observation, variant_config)
            receiver_runtime = time.perf_counter() - receiver_started
            decoded = np.asarray(result.decoded_information_bits, dtype=np.int8)
            bit_errors = int(np.count_nonzero(reference_bits != decoded))
            pair_errors = int(np.any((reference_bits != decoded).reshape(-1, 2), axis=1).sum())
            exact_match = (
                bool(np.array_equal(decoded, saved_joint_bits)) if variant == "exact" else None
            )
            if variant == "exact" and not exact_match:
                raise ValueError(
                    "exact-prior replay does not reproduce the saved Joint decoded bits"
                )
            variant_record = {
                "schema": "scientific-exp02-prior-sensitivity-trial-v1",
                "experiment_id": protocol["experiment_id"],
                "source_experiment_id": protocol["source_experiment_id"],
                "source_relative_path": trial["source"]["path"],
                "source_record_sha256": source_hash,
                "source_trial_manifest_sha256": trial["source"]["trial_manifest_sha256"],
                "source_config_sha256": trial_manifest["config_sha256"],
                "source_seeds": record["seeds"],
                "gamma_db": gamma,
                "amplitude": float(record["amplitude"]),
                "noise_complex_variance": float(record["noise_variance"]),
                "frame_symbols": int(record["frame_symbols"]),
                "observation_sha256": observation.sha256,
                "prior_variant": variant,
                "prior_means": [[float(value.real), float(value.imag)] for value in means],
                "prior_variances": [float(path.prior_variance) for path in variant_config.paths],
                "receiver_config_sha256": _sha256_bytes(_canonical_json(variant_config.to_dict())),
                "bit_count": int(reference_bits.size),
                "pair_count": int(reference_bits.size // 2),
                "bit_errors": bit_errors,
                "ber": bit_errors / int(reference_bits.size),
                "pair_errors": pair_errors,
                "information_pair_ser": pair_errors / int(reference_bits.size // 2),
                "frame_error": int(bit_errors > 0),
                "runtime_seconds": float(receiver_runtime),
                "exact_decoded_bits_match_source": exact_match,
                "evaluation_truth_passed_to_receiver": False,
                "paper_exact": False,
            }
            _save_result(out_path, variant_config.to_dict(), variant_record, decoded)
            output_records[variant] = variant_record
            completed_calls += 1
        _atomic_json(
            OUTPUT_ROOT / "progress.json",
            {
                "status": "incomplete" if stopped_for_budget else "running",
                "paired_observation_index": frame_number,
                "planned_paired_observations": len(selected),
                "completed_receiver_calls_this_invocation": completed_calls,
                "elapsed_seconds_this_invocation": time.monotonic() - started,
                "stop_reason": "total wall-clock budget reached" if stopped_for_budget else None,
            },
        )
        print(
            f"progress observations={frame_number}/{len(selected)} "
            f"calls_this_run={completed_calls} elapsed={time.monotonic() - started:.1f}s",
            flush=True,
        )
        if stopped_for_budget:
            break

    analysis = _collect_analysis(protocol)
    _atomic_json(OUTPUT_ROOT / "analysis.json", analysis)
    source_after = _tree_manifest(SOURCE_ROOT / "confirmatory")
    unchanged = (
        source_before["sha256"] == source_after["sha256"]
        and source_before["file_count"] == source_after["file_count"]
    )
    _atomic_json(
        OUTPUT_ROOT / "source_immutability.json",
        {
            "source_experiment_id": protocol["source_experiment_id"],
            "source_manifest_sha256": _sha256_file(SOURCE_ROOT / "study_manifest.json"),
            "before_tree_sha256": source_before["sha256"],
            "after_tree_sha256": source_after["sha256"],
            "before_file_count": source_before["file_count"],
            "after_file_count": source_after["file_count"],
            "unchanged": unchanged,
        },
    )
    _atomic_json(OUTPUT_ROOT / "source_tree_after.json", source_after)
    result = {
        "status": analysis["status"],
        "complete_paired_observations": analysis["complete_paired_observations"],
        "receiver_calls_completed": analysis["receiver_calls_completed"],
        "elapsed_seconds_this_invocation": time.monotonic() - started,
        "source_frames_unchanged": unchanged,
    }
    _atomic_json(
        OUTPUT_ROOT / "progress.json",
        {
            **result,
            "planned_paired_observations": len(selected),
            "stop_reason": "budget" if stopped_for_budget else None,
        },
    )
    if not unchanged:
        raise RuntimeError(
            "EXP-01B source confirmatory tree changed during EXP-02; inspect before continuing"
        )
    print(json.dumps(result, sort_keys=True), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-source-only", action="store_true")
    args = parser.parse_args()
    if args.verify_source_only:
        before = json.loads((OUTPUT_ROOT / "source_tree_before.json").read_text(encoding="utf-8"))
        current = _tree_manifest(SOURCE_ROOT / "confirmatory")
        ok = before["sha256"] == current["sha256"] and before["file_count"] == current["file_count"]
        print(
            json.dumps(
                {
                    "source_frames_unchanged": ok,
                    "before": before["sha256"],
                    "current": current["sha256"],
                },
                sort_keys=True,
            )
        )
        if not ok:
            raise SystemExit(1)
        return
    run()


if __name__ == "__main__":
    main()
