"""Independently verify EXP-02 outputs against the saved EXP-01B frames."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs" / "scientific_exp_02" / "prior_sensitivity"
SOURCE_ROOT = ROOT / "outputs" / "scientific_exp_01b"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_manifest(root: Path) -> dict[str, Any]:
    files = [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return {
        "file_count": len(files),
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "files": files,
    }


def _assert_close(actual: float, expected: float, name: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-14):
        raise AssertionError(f"{name} mismatch: {actual!r} != {expected!r}")


def _source_frame(gamma: float, trial_index: int) -> Path:
    tag = f"g{gamma:04.1f}".replace(".", "p")
    return ROOT / "outputs" / "scientific_exp_02" / "source_frames" / tag / f"t{trial_index:04d}"


def verify() -> dict[str, Any]:
    protocol = json.loads((OUTPUT_ROOT / "protocol.json").read_text(encoding="utf-8"))
    analysis = json.loads((OUTPUT_ROOT / "analysis.json").read_text(encoding="utf-8"))
    if analysis.get("status") != "COMPLETE" or analysis.get("complete_paired_observations") != 48:
        raise AssertionError("EXP-02 sensitivity series is incomplete")
    variants = protocol["prior_variants"]
    source_manifest = json.loads((SOURCE_ROOT / "study_manifest.json").read_text(encoding="utf-8"))
    if (
        source_manifest.get("completed_pairs") != 2160
        or len(source_manifest.get("records", [])) != 2160
    ):
        raise AssertionError("EXP-01B no longer has the frozen 2160 source records")
    source_static = [row for row in source_manifest["records"] if row.get("scenario") == "static"]
    prior_config_checks = {
        "joint_exact_prior_matches_public_channel": 0,
        "b0_only_nominal_gain": 0,
        "b1_exact_public_taps": 0,
    }
    for item in source_static:
        record_path = SOURCE_ROOT / item["path"]
        record_bytes = record_path.read_bytes()
        if hashlib.sha256(record_bytes).hexdigest() != item["record_sha256"]:
            raise AssertionError("EXP-01B static record hash mismatch during channel-access audit")
        trial_manifest_path = record_path.parent / "manifest.json"
        if _sha256_file(trial_manifest_path) != item["trial_manifest_sha256"]:
            raise AssertionError("EXP-01B static trial manifest hash mismatch")
        record = json.loads(record_bytes.decode("utf-8"))
        channel_paths = record["channel_config"]["paths"]
        joint_paths = record["receiver_configs"]["joint"]["paths"]
        b0_front_end = record["receiver_configs"]["b0"]["front_end"]
        b1_taps = record["receiver_configs"]["b1"]["taps"]
        if len(channel_paths) != 2 or len(joint_paths) != 2 or len(b1_taps) != 2:
            raise AssertionError("unexpected static path count in receiver configuration")
        for channel_path, joint_path, b1_tap in zip(
            channel_paths, joint_paths, b1_taps, strict=True
        ):
            actual = channel_path["constant_coefficient"]
            prior = joint_path["prior_mean"]
            b1 = b1_tap["coefficient"]
            if not np.allclose(actual, prior, rtol=0, atol=1e-15):
                raise AssertionError(
                    "Joint static prior differs from public nominal channel coefficients"
                )
            if not np.allclose(actual, b1, rtol=0, atol=1e-15):
                raise AssertionError("B1 public taps differ from static channel profile")
        if b0_front_end.get("known_static_gain") != [1.0, 0.0]:
            raise AssertionError("B0 front-end channel information changed")
        prior_config_checks["joint_exact_prior_matches_public_channel"] += 1
        prior_config_checks["b0_only_nominal_gain"] += 1
        prior_config_checks["b1_exact_public_taps"] += 1
    if len(source_static) != 1160:
        raise AssertionError("expected 1160 static frames in EXP-01B")

    n_outputs = 0
    checked_observations = set()
    prior_vs_exact = {
        variant: {"frames_bit_identical_to_exact": 0, "bit_errors_vs_exact": 0, "frames": 0}
        for variant in protocol["prior_variants"]
    }
    recomputed_points = []
    reps = int(protocol["analysis"]["bootstrap_replicates"])
    base_seed = int(protocol["analysis"]["bootstrap_seed"])
    for point_index, gamma in enumerate(protocol["energy_points_gamma_b_d_db"]):
        frame_rows = []
        total_bits = 0
        total_pairs = 0
        for trial_index in protocol["source_trial_indices_per_point"]:
            source_root = _source_frame(float(gamma), int(trial_index))
            source_copy_manifest = json.loads(
                (source_root / "copy_manifest.json").read_text(encoding="utf-8")
            )
            for name, expected in source_copy_manifest["files"].items():
                if _sha256_file(source_root / name) != expected:
                    raise AssertionError(f"copied source frame integrity failure: {name}")
            source_record_bytes = (source_root / "record.json").read_bytes()
            source_record = json.loads(source_record_bytes.decode("utf-8"))
            source_record_hash = hashlib.sha256(source_record_bytes).hexdigest()
            with np.load(source_root / "arrays.npz", allow_pickle=False) as arrays:
                reference_bits = arrays["information_bits"].copy()
                prior_joint_bits = arrays["joint_decoded_bits"].copy()
            per_variant = {}
            for variant in variants:
                tag = f"g{float(gamma):04.1f}".replace(".", "p")
                result_root = OUTPUT_ROOT / tag / f"t{int(trial_index):04d}" / variant
                manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
                for name, expected in manifest["files"].items():
                    if _sha256_file(result_root / name) != expected:
                        raise AssertionError(f"EXP-02 output hash mismatch: {name}")
                record = json.loads((result_root / "record.json").read_text(encoding="utf-8"))
                if record["source_record_sha256"] != source_record_hash:
                    raise AssertionError("EXP-02 output source record hash mismatch")
                if record["observation_sha256"] != source_record["observation_sha256"]:
                    raise AssertionError(
                        "EXP-02 output does not use the original receiver observation"
                    )
                if record["evaluation_truth_passed_to_receiver"] is not False:
                    raise AssertionError("EvaluationTruth isolation marker is not false")
                with np.load(result_root / "decoded.npz", allow_pickle=False) as decoded_npz:
                    decoded = decoded_npz["decoded_information_bits"].copy()
                errors = reference_bits != decoded
                bit_errors = int(errors.sum())
                pair_errors = int(errors.reshape(-1, 2).any(axis=1).sum())
                expected_values = {
                    "bit_errors": bit_errors,
                    "pair_errors": pair_errors,
                    "ber": bit_errors / reference_bits.size,
                    "information_pair_ser": pair_errors / (reference_bits.size // 2),
                    "frame_error": int(bit_errors > 0),
                }
                for key, expected in expected_values.items():
                    if isinstance(expected, float):
                        _assert_close(float(record[key]), expected, f"{variant}.{key}")
                    elif record[key] != expected:
                        raise AssertionError(f"{variant}.{key} mismatch")
                if variant == "exact" and not np.array_equal(decoded, prior_joint_bits):
                    raise AssertionError("exact prior replay differs from original decoded bits")
                checked_observations.add(record["observation_sha256"])
                per_variant[variant] = {**record, "decoded": decoded}
                n_outputs += 1
            if len({row["observation_sha256"] for row in per_variant.values()}) != 1:
                raise AssertionError("prior variants do not form one paired observation set")
            for variant, row in per_variant.items():
                difference = row["decoded"] != per_variant["exact"]["decoded"]
                prior_vs_exact[variant]["frames_bit_identical_to_exact"] += int(
                    not difference.any()
                )
                prior_vs_exact[variant]["bit_errors_vs_exact"] += int(difference.sum())
                prior_vs_exact[variant]["frames"] += 1
            frame_rows.append(per_variant)
            total_bits += reference_bits.size
            total_pairs += reference_bits.size // 2
        metrics = {}
        exact_ber = np.asarray(
            [row["exact"]["bit_errors"] / row["exact"]["bit_count"] for row in frame_rows],
            dtype=float,
        )
        for variant_index, variant in enumerate(variants):
            bit_errors = sum(row[variant]["bit_errors"] for row in frame_rows)
            pair_errors = sum(row[variant]["pair_errors"] for row in frame_rows)
            frame_errors = sum(row[variant]["frame_error"] for row in frame_rows)
            delta = (
                np.asarray(
                    [row[variant]["bit_errors"] / row[variant]["bit_count"] for row in frame_rows],
                    dtype=float,
                )
                - exact_ber
            )
            if delta.size < 2:
                interval = None
            elif variant == "exact":
                interval = [0.0, 0.0]
            else:
                rng = np.random.default_rng(base_seed + point_index * 100 + variant_index)
                draws = rng.integers(0, delta.size, size=(reps, delta.size))
                interval = [
                    float(x) for x in np.quantile(delta[draws].mean(axis=1), [0.025, 0.975])
                ]
            metrics[variant] = {
                "trials": len(frame_rows),
                "bit_errors": bit_errors,
                "bits": total_bits,
                "ber": bit_errors / total_bits,
                "pair_errors": pair_errors,
                "pairs": total_pairs,
                "information_pair_ser": pair_errors / total_pairs,
                "frame_errors": frame_errors,
                "fer": frame_errors / len(frame_rows),
                "mean_paired_ber_delta_vs_exact": float(delta.mean()),
                "paired_frame_cluster_bootstrap_95_ci_ber_delta": interval,
                "mean_runtime_seconds": float(
                    np.mean([row[variant]["runtime_seconds"] for row in frame_rows])
                ),
            }
        recomputed_points.append(
            {"gamma_db": float(gamma), "trials": len(frame_rows), "metrics": metrics}
        )
    if n_outputs != 288 or len(checked_observations) != 48:
        raise AssertionError("unexpected EXP-02 output or unique-observation count")
    if analysis["receiver_calls_completed"] != n_outputs or analysis["points"] != recomputed_points:
        raise AssertionError(
            "EXP-02 aggregate analysis does not independently reproduce from decoded arrays"
        )

    before = json.loads((OUTPUT_ROOT / "source_tree_before.json").read_text(encoding="utf-8"))
    after = _tree_manifest(SOURCE_ROOT / "confirmatory")
    if before["sha256"] != after["sha256"] or before["file_count"] != after["file_count"]:
        raise AssertionError("the 2160-frame EXP-01B confirmatory source tree changed")
    historic = json.loads(
        (ROOT / "outputs" / "scientific_exp_01b" / "analysis" / "analysis_results.json").read_text(
            encoding="utf-8"
        )
    )
    expected_gain = historic["scenarios"]["static"]["target_gain_analysis"]["0.05"]
    for arm, expected, valid in (
        ("b0", 5.7799887361185665, 4808),
        ("b1", 2.4560630949253532, 4946),
    ):
        actual = expected_gain[arm]
        _assert_close(float(actual["gain_db"]), expected, f"EXP-01B {arm} gain")
        if actual["bootstrap"]["valid_replicates"] != valid:
            raise AssertionError("unexpected historic bootstrap crossing count")
    summary = {
        "status": "PASS",
        "prior_config_checks": prior_config_checks,
        "source_confirmatory_frames": 2160,
        "static_source_frames_checked_for_information_access": 1160,
        "sensitivity_paired_observations": 48,
        "sensitivity_decoded_outputs": n_outputs,
        "unique_observation_hashes": len(checked_observations),
        "decoded_output_comparison_with_exact_prior": prior_vs_exact,
        "source_tree_unchanged": True,
        "analysis_recomputed_from_decoded_bits": True,
        "historic_gains_db": {"joint_b0": 5.7799887361185665, "joint_b1": 2.4560630949253532},
        "paper_exact": False,
    }
    (OUTPUT_ROOT / "independent_verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
