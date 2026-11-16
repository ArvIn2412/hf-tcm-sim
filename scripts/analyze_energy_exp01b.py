"""Independently recount and analyze SCIENTIFIC-EXP-01B trial artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ARMS = ("joint", "b0", "b1")
ROOT = Path(__file__).resolve().parents[1]
ARM_LABELS = {
    "joint": "Спільне приймання — метрика Евкліда",
    "b0": "Роздільне приймання — метрика Хемінга",
    "b1": "Роздільне приймання з оцінюванням каналу — метрика Хемінга",
}
INTERPOLATIONS = {"log10_ber", "linear_ber"}
RUNTIME_STALL_THRESHOLD_SECONDS = 60.0


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def recompute_trial_metrics(
    record: Mapping[str, Any], arrays: Mapping[str, np.ndarray]
) -> dict[str, Any]:
    """Recount bit/pair/frame errors and transmit energy from immutable NPZ arrays."""
    reference = np.asarray(arrays["information_bits"])
    if reference.ndim != 1 or reference.size == 0 or reference.size % 2:
        raise ValueError("information bits must be a nonempty even-length vector")
    if not np.isin(reference, (0, 1)).all():
        raise ValueError("information bits are not binary")
    arms = tuple(sorted(record["bit_errors"]))
    hashes = record["receiver_observation_hashes"]
    if set(hashes) != set(arms) or len(set(hashes.values())) != 1:
        raise ValueError("paired observation hash mismatch between receiver arms")
    observation_hash = record.get("observation_sha256")
    if observation_hash is not None and any(value != observation_hash for value in hashes.values()):
        raise ValueError("receiver hash does not match the shared observation")
    bit_errors: dict[str, int] = {}
    pair_errors: dict[str, int] = {}
    frame_errors: dict[str, int] = {}
    for arm in arms:
        decoded = np.asarray(arrays[f"{arm}_decoded_bits"])
        if decoded.shape != reference.shape or not np.isin(decoded, (0, 1)).all():
            raise ValueError(f"decoded bits for {arm} are invalid or misaligned")
        error_mask = decoded != reference
        bits = int(error_mask.sum())
        pairs = int(error_mask.reshape(-1, 2).any(axis=1).sum())
        bit_errors[arm] = bits
        pair_errors[arm] = pairs
        frame_errors[arm] = int(bits > 0)
        if not pairs <= bits <= 2 * pairs:
            raise ValueError("decoded bit and information-pair errors are inconsistent")

    tx_samples = np.asarray(arrays["tx_samples"], dtype=np.complex128)
    if tx_samples.ndim != 1 or not np.isfinite(tx_samples).all():
        raise ValueError("transmitted samples are invalid")
    tx_energy = float(np.vdot(tx_samples, tx_samples).real)
    bits_count = int(reference.size)
    eb_d = tx_energy / bits_count
    amplitude = float(record["amplitude"])
    expected_eb_d = 4.0 * amplitude**2
    if not math.isclose(eb_d, float(record["eb_d"]), rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("stored energy per bit does not match actual transmitter samples")
    if not math.isclose(tx_energy, float(record["tx_energy"]), rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("stored transmitted energy does not match actual samples")
    if not math.isclose(eb_d, expected_eb_d, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("actual samples do not satisfy the frozen E_b,d = 4 A^2 convention")

    noise_samples = np.asarray(arrays["noise_samples"], dtype=np.complex128)
    if noise_samples.ndim != 1 or noise_samples.size == 0 or not np.isfinite(noise_samples).all():
        raise ValueError("saved complex noise samples are invalid")
    empirical_noise_power = float(np.mean(np.abs(noise_samples) ** 2))
    if not math.isclose(
        empirical_noise_power,
        float(record["empirical_noise_power"]),
        rel_tol=1e-12,
        abs_tol=1e-14,
    ):
        raise ValueError("stored empirical noise power does not match saved complex samples")

    coefficients = np.asarray(arrays["coefficients"], dtype=np.complex128)
    if coefficients.ndim != 2 or coefficients.shape[0] == 0 or not np.isfinite(coefficients).all():
        raise ValueError("saved path coefficients are invalid")
    empirical_path_powers = np.mean(np.abs(coefficients) ** 2, axis=1)
    stored_path_powers = np.asarray(record["empirical_path_powers"], dtype=float)
    if stored_path_powers.shape != empirical_path_powers.shape or not np.allclose(
        stored_path_powers, empirical_path_powers, rtol=1e-12, atol=1e-14
    ):
        raise ValueError("stored empirical path powers do not match saved channel coefficients")

    pairs_count = bits_count // 2
    for arm in arms:
        if bit_errors[arm] != int(record["bit_errors"][arm]):
            raise ValueError(f"stored bit-error count for {arm} does not match decoded bits")
        if pair_errors[arm] != int(record["pair_errors"][arm]):
            raise ValueError(f"stored pair-error count for {arm} does not match decoded bits")
        if frame_errors[arm] != int(record["frame_errors"][arm]):
            raise ValueError(f"stored frame-error count for {arm} does not match decoded bits")
        if not math.isclose(
            bit_errors[arm] / bits_count, float(record["ber"][arm]), rel_tol=1e-12, abs_tol=1e-15
        ):
            raise ValueError(f"stored BER for {arm} does not match integer counts")
        if not math.isclose(
            pair_errors[arm] / pairs_count, float(record["ser"][arm]), rel_tol=1e-12, abs_tol=1e-15
        ):
            raise ValueError(f"stored information-pair SER for {arm} does not match counts")
    return {
        "tx_energy": tx_energy,
        "eb_d": eb_d,
        "amplitude": amplitude,
        "bits": bits_count,
        "pairs": pairs_count,
        "bit_errors": bit_errors,
        "pair_errors": pair_errors,
        "frame_errors": frame_errors,
        "observation_sha256": observation_hash,
        "empirical_noise_power": empirical_noise_power,
        "empirical_path_powers": empirical_path_powers.tolist(),
    }


def crossing_gamma_db(
    points: Sequence[Mapping[str, Any]], target_ber: float, arm: str, interpolation: str
) -> dict[str, Any]:
    """Find one measured target crossing, without extrapolation or zero pseudocounts."""
    if interpolation not in INTERPOLATIONS:
        raise ValueError(f"unsupported interpolation: {interpolation}")
    if not 0.0 < target_ber < 1.0 or not math.isfinite(target_ber):
        raise ValueError("target BER must be finite and in (0, 1)")
    rows = sorted(points, key=lambda row: float(row["gamma_db"]))
    gamma = [float(row["gamma_db"]) for row in rows]
    ber = [float(row["ber"][arm]) for row in rows]
    if not gamma or any(not math.isfinite(value) for value in gamma + ber):
        return {"status": "NO_CROSSING", "gamma_db": None, "bracket_gamma_db": None}
    if any(not 0.0 <= value <= 1.0 for value in ber) or any(
        right <= left for left, right in zip(gamma, gamma[1:])
    ):
        raise ValueError("crossing points require unique gamma and BER in [0, 1]")
    exact = [index for index, value in enumerate(ber) if value == target_ber]
    if any(right == left + 1 for left, right in zip(exact, exact[1:])):
        return {"status": "TARGET_PLATEAU", "gamma_db": None, "bracket_gamma_db": None}
    brackets = [
        index
        for index in range(len(ber) - 1)
        if (ber[index] - target_ber) * (ber[index + 1] - target_ber) < 0
    ]
    if len(exact) + len(brackets) > 1:
        return {
            "status": "AMBIGUOUS_MULTIPLE_CROSSINGS",
            "gamma_db": None,
            "bracket_gamma_db": None,
        }
    if exact:
        value = gamma[exact[0]]
        return {"status": "EXACT_GRID_POINT", "gamma_db": value, "bracket_gamma_db": [value, value]}
    if not brackets:
        return {"status": "NO_CROSSING", "gamma_db": None, "bracket_gamma_db": None}
    index = brackets[0]
    y0, y1 = ber[index], ber[index + 1]
    if y0 < y1:
        return {
            "status": "UPWARD_CROSSING",
            "gamma_db": None,
            "bracket_gamma_db": [gamma[index], gamma[index + 1]],
        }
    if interpolation == "log10_ber":
        if y0 <= 0.0 or y1 <= 0.0:
            return {
                "status": "ZERO_BER_BRACKET_UNRESOLVED",
                "gamma_db": None,
                "bracket_gamma_db": [gamma[index], gamma[index + 1]],
            }
        fraction = (math.log10(target_ber) - math.log10(y0)) / (math.log10(y1) - math.log10(y0))
    else:
        fraction = (target_ber - y0) / (y1 - y0)
    crossing = gamma[index] + fraction * (gamma[index + 1] - gamma[index])
    return {
        "status": "BRACKETED",
        "gamma_db": crossing,
        "bracket_gamma_db": [gamma[index], gamma[index + 1]],
    }


def _aggregate_points(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[float, list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[float(row["gamma_db"])].append(row)
    result = []
    for gamma_db, trials in sorted(grouped.items()):
        arms = tuple(sorted(trials[0]["bit_errors"]))
        total_bits = sum(int(row["bits"]) for row in trials)
        total_pairs = sum(int(row["pairs"]) for row in trials)
        bit_errors = {arm: sum(int(row["bit_errors"][arm]) for row in trials) for arm in arms}
        pair_errors = {arm: sum(int(row["pair_errors"][arm]) for row in trials) for arm in arms}
        frame_errors = {arm: sum(int(row["frame_errors"][arm]) for row in trials) for arm in arms}
        result.append(
            {
                "gamma_db": gamma_db,
                "eb_d": float(np.mean([float(row["eb_d"]) for row in trials])),
                "trials": len(trials),
                "bits": total_bits,
                "pairs": total_pairs,
                "bit_errors": bit_errors,
                "pair_errors": pair_errors,
                "frame_errors": frame_errors,
                "ber": {arm: bit_errors[arm] / total_bits for arm in arms},
                "ser": {arm: pair_errors[arm] / total_pairs for arm in arms},
                "fer": {arm: frame_errors[arm] / len(trials) for arm in arms},
                "runtime_seconds": {
                    arm: [float(row["runtime_seconds"][arm]) for row in trials] for arm in arms
                },
            }
        )
    return result


def _runtime_suspension_outliers(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    outliers = []
    for row in records:
        runtimes = {arm: float(value) for arm, value in row["runtime_seconds"].items()}
        if not runtimes:
            continue
        largest = max(runtimes.values())
        elapsed = float(row["elapsed_seconds"])
        if (
            largest >= RUNTIME_STALL_THRESHOLD_SECONDS
            and elapsed >= largest
            and elapsed - largest <= max(5.0, 0.05 * elapsed)
        ):
            outliers.append(
                {
                    "point_index": int(row["point_index"]),
                    "trial_index": int(row["trial_index"]),
                    "gamma_db": float(row["gamma_db"]),
                    "raw_elapsed_seconds": elapsed,
                    "raw_receiver_runtime_seconds": runtimes,
                    "status": "EXCLUDED_FROM_RUNTIME_SUMMARY_ONLY",
                    "ber_ser_inclusion": "included; receiver decisions and trial metrics remain valid",
                }
            )
    return outliers


def paired_bootstrap_gain(
    records: Sequence[Mapping[str, Any]],
    target_ber: float,
    separate_arm: str,
    replicates: int,
    seed: int,
    interpolation: str,
) -> dict[str, Any]:
    """Resample paired trial clusters independently within each measured point."""
    if replicates < 1 or seed < 0:
        raise ValueError("bootstrap replicates must be positive and seed nonnegative")
    if not records:
        raise ValueError("at least one completed paired record is required")
    context = (records[0]["phase"], records[0]["scenario"], records[0]["sweep"])
    grouped: dict[float, list[Mapping[str, Any]]] = defaultdict(list)
    unique_trials: set[tuple[float, int, int]] = set()
    for row in records:
        if (row["phase"], row["scenario"], row["sweep"]) != context:
            raise ValueError("bootstrap records mix experiment contexts")
        hashes = row["receiver_observation_hashes"]
        if "joint" not in hashes or separate_arm not in hashes or len(set(hashes.values())) != 1:
            raise ValueError("bootstrap records do not contain paired observations")
        key = (float(row["gamma_db"]), int(row["point_index"]), int(row["trial_index"]))
        if key in unique_trials:
            raise ValueError("duplicate paired trial identifier")
        unique_trials.add(key)
        grouped[float(row["gamma_db"])].append(row)
    gammas = sorted(grouped)
    arms = ("joint", separate_arm)
    points = _aggregate_points(records)
    crossing_joint = crossing_gamma_db(points, target_ber, "joint", interpolation)
    crossing_separate = crossing_gamma_db(points, target_ber, separate_arm, interpolation)
    observed = crossing_joint["gamma_db"] is not None and crossing_separate["gamma_db"] is not None
    observed_gain = (
        float(crossing_separate["gamma_db"] - crossing_joint["gamma_db"]) if observed else None
    )
    streams = np.random.SeedSequence(seed).spawn(len(gammas))
    prepared = []
    for index, gamma in enumerate(gammas):
        trials = sorted(
            grouped[gamma], key=lambda row: (int(row["point_index"]), int(row["trial_index"]))
        )
        denominators = np.asarray([int(row["bits"]) for row in trials], dtype=np.int64)
        errors = {
            arm: np.asarray([int(row["bit_errors"][arm]) for row in trials], dtype=np.int64)
            for arm in arms
        }
        rng = np.random.default_rng(streams[index])
        draws = rng.integers(len(trials), size=(replicates, len(trials)))
        sampled_bits = denominators[draws].sum(axis=1)
        sampled_errors = {arm: errors[arm][draws].sum(axis=1) for arm in arms}
        prepared.append((sampled_bits, sampled_errors))
    valid = []
    for replicate in range(replicates):
        bootstrap_points = []
        for index, gamma in enumerate(gammas):
            denominator, sampled_errors = prepared[index]
            bootstrap_points.append(
                {
                    "gamma_db": gamma,
                    "ber": {
                        arm: float(sampled_errors[arm][replicate] / denominator[replicate])
                        for arm in arms
                    },
                }
            )
        joint = crossing_gamma_db(bootstrap_points, target_ber, "joint", interpolation)
        separate = crossing_gamma_db(bootstrap_points, target_ber, separate_arm, interpolation)
        if joint["gamma_db"] is not None and separate["gamma_db"] is not None:
            valid.append(float(separate["gamma_db"] - joint["gamma_db"]))
    fraction = len(valid) / replicates
    quantiles = np.quantile(valid, [0.025, 0.975]).tolist() if valid else None
    ci = quantiles if observed and fraction >= 0.95 else None
    return {
        "status": "ESTIMATED" if ci is not None else "PARTIAL" if observed else "NOT_ESTIMABLE",
        "target_ber": target_ber,
        "separate_arm": separate_arm,
        "interpolation": interpolation,
        "observed_crossings": observed,
        "crossings": {"joint": crossing_joint, separate_arm: crossing_separate},
        "required_gamma_db": {
            "joint": crossing_joint["gamma_db"],
            "separate": crossing_separate["gamma_db"],
        },
        "required_eb_d": {
            "joint": 10.0 ** (crossing_joint["gamma_db"] / 10.0)
            if crossing_joint["gamma_db"] is not None
            else None,
            "separate": 10.0 ** (crossing_separate["gamma_db"] / 10.0)
            if crossing_separate["gamma_db"] is not None
            else None,
        },
        "gain_db": observed_gain,
        "bootstrap": {
            "seed": seed,
            "total_replicates": replicates,
            "valid_replicates": len(valid),
            "valid_fraction": fraction,
            "minimum_valid_fraction": 0.95,
            "confidence_interval_db": ci,
            "conditional_quantiles_db": quantiles,
            "method": "paired independent trial clusters resampled within each measured energy point",
        },
    }


def _verify_trial_files(trial_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = trial_dir / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    for name, expected in manifest["files"].items():
        data = (trial_dir / name).read_bytes()
        if _sha256(data) != expected:
            raise ValueError(f"trial payload hash mismatch: {trial_dir / name}")
    record = json.loads((trial_dir / "record.json").read_text(encoding="utf-8"))
    config = json.loads((trial_dir / "config.json").read_text(encoding="utf-8"))
    canonical_config = {**config, "seed_override": None}
    canonical = json.dumps(
        canonical_config, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    if _sha256(canonical) != manifest["config_sha256"]:
        raise ValueError(f"trial config hash mismatch: {trial_dir}")
    with np.load(trial_dir / "arrays.npz", allow_pickle=False) as file:
        arrays = {name: file[name] for name in file.files}
    received = np.asarray(arrays["received_samples"])
    delays = [int(value) for value in record["delays"]]
    expected_received_size = np.asarray(arrays["tx_samples"]).size + max(delays)
    if received.ndim != 1 or received.size != expected_received_size:
        raise ValueError("saved received-sample length does not match the multipath tail")
    if np.asarray(arrays["noise_samples"]).shape != received.shape:
        raise ValueError("saved noise and received sample sequences are not aligned")
    if np.asarray(arrays["coefficients"]).shape != (len(delays), received.size):
        raise ValueError("saved channel coefficient trace is not aligned with the received frame")
    counted = recompute_trial_metrics(record, arrays)
    record["_independent_recount"] = counted
    return record, manifest


def _expected_stream_seeds(
    protocol: Mapping[str, Any], scenario: str, point_index: int, trial_index: int
) -> dict[str, int]:
    policy = protocol["seed_policy"]
    scenario_id = int(policy["scenario_ids"][scenario])
    return {
        stream: int(
            np.random.SeedSequence(
                [
                    int(policy["root_seed"]),
                    2,  # EnergyTrialSpec confirmatory phase id
                    scenario_id,
                    1,  # EnergyTrialSpec amplitude sweep id
                    point_index,
                    trial_index,
                    int(stream_id),
                ]
            ).generate_state(1, dtype=np.uint64)[0]
        )
        for stream, stream_id in policy["stream_ids"].items()
    }


def _close(actual: float, expected: float) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-14)


def _verify_record_channel_and_receivers(
    record: Mapping[str, Any],
    scenario: str,
    scenario_spec: Mapping[str, Any],
    protocol: Mapping[str, Any],
) -> None:
    delays = [int(value) for value in scenario_spec["delays_samples"]]
    powers = [float(value) for value in scenario_spec["path_powers"]]
    if [int(value) for value in record["delays"]] != delays:
        raise ValueError("trial path delays differ from the frozen scenario")
    if len(record["path_powers"]) != len(powers) or any(
        not _close(actual, expected)
        for actual, expected in zip(record["path_powers"], powers, strict=True)
    ):
        raise ValueError("trial path powers differ from the frozen scenario")

    channel = record["channel_config"]
    expected_mode = "rician_ar1" if scenario == "rician" else "constant"
    expected_correlation = (
        float(scenario_spec["fading_correlation_per_complex_sample"])
        if scenario == "rician"
        else 0.0
    )
    if channel["fading_mode"] != expected_mode:
        raise ValueError("trial fading mode differs from the frozen scenario")
    if not _close(channel["correlation"], expected_correlation):
        raise ValueError("trial channel correlation differs from the frozen scenario")
    if channel["noise_model"] != "complex_awgn_sample_domain" or not _close(
        channel["noise_complex_variance"], float(protocol["fixed_complex_noise_variance"])
    ):
        raise ValueError("trial noise model or complex variance differs from the protocol")
    channel_paths = channel["paths"]
    if len(channel_paths) != len(delays):
        raise ValueError("trial channel path count differs from the frozen scenario")
    for index, path in enumerate(channel_paths):
        if int(path["delay_samples"]) != delays[index] or not _close(
            path["average_power"], powers[index]
        ):
            raise ValueError("trial channel path delay or power mismatch")
        expected_phase = (
            math.atan2(
                float(scenario_spec["path_coefficients"][index][1]),
                float(scenario_spec["path_coefficients"][index][0]),
            )
            if scenario == "static"
            else float(scenario_spec["los_phases_rad"][index])
        )
        if not _close(path["los_phase_rad"], expected_phase):
            raise ValueError("trial path phase differs from the frozen scenario")
        if scenario == "static":
            coefficient = scenario_spec["path_coefficients"][index]
            actual = path["constant_coefficient"]
            if actual is None or any(
                not _close(value, expected)
                for value, expected in zip(actual, coefficient, strict=True)
            ):
                raise ValueError("static path coefficient differs from the frozen scenario")
            if not _close(path["k_factor"], 0.0):
                raise ValueError("static channel unexpectedly uses a Rician K factor")
        else:
            if path["constant_coefficient"] is not None or not _close(
                path["k_factor"], scenario_spec["rician_k_factors"][index]
            ):
                raise ValueError("Rician path coefficient or K factor differs from the protocol")

    configs = record["receiver_configs"]
    expected_arms = set(scenario_spec["receiver_arms"])
    if set(configs) != expected_arms:
        raise ValueError("saved receiver configuration set differs from the paired experiment")
    frame_symbols = int(protocol["frame_symbols"])
    amplitude = float(record["amplitude"])
    joint = configs["joint"]
    b0 = configs["b0"]
    for name, config in (("joint", joint), ("b0", b0)):
        configured_amplitude = (
            config["amplitude"] if name == "joint" else config["front_end"]["amplitude"]
        )
        if int(config["expected_symbol_count"]) != frame_symbols or not _close(
            configured_amplitude, amplitude
        ):
            raise ValueError(f"{name} receiver frame length or amplitude mismatch")
    if joint["decoder_mode"] != "finite_depth" or int(joint["traceback_depth"]) != 20:
        raise ValueError("Joint receiver decoder settings differ from the frozen experiment")
    if joint["metric_profile"] != "squared_euclidean":
        raise ValueError("Joint receiver metric differs from the frozen experiment")
    expected_joint_mode = "rician_ar1" if scenario == "rician" else "unknown_static"
    expected_joint_correlation = (
        float(scenario_spec["fading_correlation_per_complex_sample"])
        if scenario == "rician"
        else 1.0
    )
    if joint["channel_mode"] != expected_joint_mode or not _close(
        joint["correlation"], expected_joint_correlation
    ):
        raise ValueError("Joint receiver channel profile differs from the frozen scenario")
    if not _close(
        joint["observation_noise_variance"], float(protocol["fixed_complex_noise_variance"])
    ):
        raise ValueError("Joint receiver noise variance differs from the protocol")
    joint_paths = joint["paths"]
    if len(joint_paths) != len(delays):
        raise ValueError("Joint receiver path count differs from the channel")
    for index, path in enumerate(joint_paths):
        if int(path["delay_samples"]) != delays[index]:
            raise ValueError("Joint receiver path delay differs from the channel")
        if scenario == "static":
            coefficient = scenario_spec["path_coefficients"][index]
            if (
                path["prior_mean"] is None
                or any(
                    not _close(value, expected)
                    for value, expected in zip(path["prior_mean"], coefficient, strict=True)
                )
                or not _close(path["prior_variance"], 0.25)
            ):
                raise ValueError("Joint static-channel prior differs from the confirmed profile")
        elif (
            not _close(path["average_power"], powers[index])
            or not _close(path["k_factor"], scenario_spec["rician_k_factors"][index])
            or not _close(path["los_phase_rad"], scenario_spec["los_phases_rad"][index])
            or path["prior_mean"] is not None
            or path["prior_variance"] is not None
        ):
            raise ValueError("Joint Rician path profile differs from the frozen scenario")
    if b0["decoder_mode"] != "finite_depth" or int(b0["traceback_depth"]) != 20:
        raise ValueError("B0 receiver decoder settings differ from the frozen experiment")
    if "b1" in configs:
        b1 = configs["b1"]
        if scenario != "static" or b1["channel_mode"] != "public_static_complex_taps":
            raise ValueError("B1 is enabled outside its supported static public-tap profile")
        if int(b1["expected_symbol_count"]) != frame_symbols or not _close(
            b1["amplitude"], amplitude
        ):
            raise ValueError("B1 receiver frame length or amplitude mismatch")
        if int(b1["traceback_depth"]) != 20:
            raise ValueError("B1 decoder depth differs from the frozen experiment")
        taps = b1["taps"]
        if len(taps) != len(delays):
            raise ValueError("B1 public tap count differs from the static channel")
        for index, tap in enumerate(taps):
            coefficient = scenario_spec["path_coefficients"][index]
            if int(tap["delay_samples"]) != delays[index] or any(
                not _close(value, expected)
                for value, expected in zip(tap["coefficient"], coefficient, strict=True)
            ):
                raise ValueError("B1 public channel tap differs from the static profile")


def load_completed_records(
    output_root: Path, scenario: str, protocol: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    spec = protocol["scenarios"][scenario]
    records = []
    counts: dict[str, int] = {}
    for point_index, gamma_db in enumerate(spec["gamma_db_grid"]):
        trial_count = 0
        for trial_index in range(int(protocol["trials_per_point"])):
            trial_dir = (
                output_root
                / "confirmatory"
                / scenario
                / "amplitude"
                / f"p{point_index:02d}"
                / f"t{trial_index:04d}"
            )
            if not (trial_dir / "manifest.json").exists():
                continue
            record, _ = _verify_trial_files(trial_dir)
            expected_context = {
                "phase": "confirmatory",
                "scenario": scenario,
                "sweep": "amplitude",
                "frame_symbols": protocol["frame_symbols"],
                "point_index": point_index,
                "trial_index": trial_index,
                "root_seed": protocol["seed_policy"]["root_seed"],
            }
            if any(record.get(name) != value for name, value in expected_context.items()):
                raise ValueError(f"trial configuration context mismatch: {trial_dir}")
            if not math.isclose(float(record["gamma_db"]), float(gamma_db), abs_tol=1e-12):
                raise ValueError(f"trial gamma does not match frozen grid: {trial_dir}")
            if tuple(sorted(record["bit_errors"])) != tuple(sorted(spec["receiver_arms"])):
                raise ValueError(f"trial receiver arms do not match frozen protocol: {trial_dir}")
            if {
                key: int(value) for key, value in record["seeds"].items()
            } != _expected_stream_seeds(protocol, scenario, point_index, trial_index):
                raise ValueError(f"trial RNG seeds do not match frozen seed policy: {trial_dir}")
            expected_amplitude = math.sqrt(
                float(protocol["fixed_complex_noise_variance"])
                * 10.0 ** (float(gamma_db) / 10.0)
                / 4.0
            )
            if not math.isclose(float(record["amplitude"]), expected_amplitude, rel_tol=1e-13):
                raise ValueError(
                    f"trial amplitude does not match the frozen energy grid: {trial_dir}"
                )
            expected_variance = float(protocol["fixed_complex_noise_variance"])
            if not math.isclose(
                float(record["noise_variance"]), expected_variance, rel_tol=0.0, abs_tol=0.0
            ):
                raise ValueError(
                    f"trial noise variance changed during amplitude sweep: {trial_dir}"
                )
            if not math.isclose(
                float(record["gamma_measured_db"]), float(gamma_db), rel_tol=1e-12, abs_tol=1e-12
            ):
                raise ValueError(
                    f"measured energy ratio does not match the frozen grid: {trial_dir}"
                )
            _verify_record_channel_and_receivers(record, scenario, spec, protocol)
            channel_variance = float(record["channel_config"]["noise_complex_variance"])
            if not math.isclose(channel_variance, expected_variance, rel_tol=0.0, abs_tol=0.0):
                raise ValueError(
                    f"saved channel configuration has a different noise variance: {trial_dir}"
                )
            records.append(record)
            trial_count += 1
        counts[str(gamma_db)] = trial_count
    keys = [
        (row["scenario"], float(row["gamma_db"]), int(row["point_index"]), int(row["trial_index"]))
        for row in records
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate trial records detected")
    seeds = [seed for row in records for seed in row["seeds"].values()]
    if len(seeds) != len(set(seeds)):
        raise ValueError("new trial seed collision detected")
    return records, counts


def verify_seed_independence(
    records_by_scenario: Mapping[str, Sequence[Mapping[str, Any]]], historical_root: Path
) -> dict[str, int]:
    historical_manifest = json.loads(
        (historical_root / "analysis/analysis_manifest.json").read_text(encoding="utf-8")
    )
    historical: set[int] = set()
    for row in historical_manifest["source_records"]:
        record = json.loads((historical_root / row["path"]).read_text(encoding="utf-8"))
        historical.update(int(value) for value in record.get("seeds", {}).values())
    new: list[int] = []
    for records in records_by_scenario.values():
        new.extend(int(seed) for record in records for seed in record["seeds"].values())
    if len(new) != len(set(new)):
        raise ValueError("new confirmatory stream seeds are not globally unique")
    overlap = set(new) & historical
    if overlap:
        raise ValueError("new confirmatory seeds overlap SCIENTIFIC-EXP-01")
    return {
        "historical_stream_seeds": len(historical),
        "new_stream_seeds": len(new),
        "overlap": 0,
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "gamma_db",
        "eb_d",
        "trials",
        "bits",
        "pairs",
        "bit_errors",
        "pair_errors",
        "frame_errors",
        "ber",
        "ser",
        "fer",
        "runtime_seconds",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: json.dumps(row.get(field), ensure_ascii=False)
                    if isinstance(row.get(field), dict)
                    else row.get(field)
                    for field in fields
                }
            )


def _gain_plot_entry(
    result: Mapping[str, Any] | None,
) -> tuple[float | None, tuple[float, float] | None, str | None]:
    """Return only statistically supported gains for bar rendering."""
    if not result:
        return None, None, "unsupported"
    if result.get("status") == "ESTIMATED":
        gain = result.get("gain_db")
        interval = result.get("bootstrap", {}).get("confidence_interval_db")
        if gain is not None and interval is not None and len(interval) == 2:
            return float(gain), (float(interval[0]), float(interval[1])), None
    if result.get("status") == "PARTIAL":
        return None, None, "insufficient_bootstrap"
    crossings = result.get("crossings", {})
    if any(item.get("status") == "NO_CROSSING" for item in crossings.values()):
        return None, None, "no_crossing"
    return None, None, "not_estimable"


def _plot_scenario(
    scenario: str,
    points: Sequence[Mapping[str, Any]],
    gains: Mapping[str, Any],
    output: Path,
    frame_symbols: int,
) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "Segoe UI", "svg.fonttype": "none", "axes.grid": True})
    arms = tuple(sorted(points[0]["ber"])) if points else ()
    colors = {"joint": "#087e8b", "b0": "#e76f51", "b1": "#7656a8"}
    generated: list[Path] = []
    if not points:
        return generated
    gamma = [float(row["gamma_db"]) for row in points]
    context = f"{scenario}; F={frame_symbols}; completed trials/point={min(row['trials'] for row in points)}–{max(row['trials'] for row in points)}"

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for arm in arms:
        values = [float(row["ber"][arm]) for row in points]
        label = ARM_LABELS[arm]
        for axis in axes:
            axis.plot(gamma, values, marker="o", ms=3.5, lw=1.6, color=colors[arm], label=label)
    for axis, ymax, title in (
        (axes[0], 1.0, "Повний діапазон BER"),
        (axes[1], 0.1, "Ділянка цільових BER"),
    ):
        axis.set_ylim(0.0, ymax)
        axis.set_xlabel("Нормована дискретна шкала γᵦ,ᵈ (дБ)")
        axis.set_ylabel("BER інформаційних бітів (частка, 0–1)")
        axis.set_title(title)
        axis.axhline(0.05, color="#6c5ce7", ls="--", lw=1.0, label="Ціль BER = 0,05")
        axis.axhline(0.01, color="#2d6a4f", ls=":", lw=1.1, label="Ціль BER = 0,01")
        axis.text(
            0.01,
            0.02,
            "Нуль означає 0 помилок у виміряній вибірці",
            transform=axis.transAxes,
            fontsize=8,
        )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=2, fontsize=8)
    fig.suptitle(f"BER — {context}")
    for suffix in ("png", "svg"):
        path = output / f"{scenario}_ber.{suffix}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        generated.append(path)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(8, 5), constrained_layout=True)
    for arm in arms:
        axis.plot(
            gamma,
            [float(row["ser"][arm]) for row in points],
            marker="o",
            ms=3.5,
            lw=1.6,
            color=colors[arm],
            label=ARM_LABELS[arm],
        )
    axis.set_ylim(0.0, 1.0)
    axis.set_xlabel("Нормована дискретна шкала γᵦ,ᵈ (дБ)")
    axis.set_ylabel("SER інформаційних пар (частка, 0–1)")
    axis.set_title(f"SER інформаційних пар — {context}")
    axis.legend(fontsize=8)
    for suffix in ("png", "svg"):
        path = output / f"{scenario}_ser.{suffix}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        generated.append(path)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(8, 5), constrained_layout=True)
    positions = []
    tick_labels = []
    values = []
    errors = []
    colors_used = []
    unsupported = []
    status_labels = {
        "insufficient_bootstrap": "\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043d\u044c\u043e \u0434\u0430\u043d\u0438\u0445",
        "no_crossing": "\u041d\u0435\u043c\u0430\u0454 \u043f\u0435\u0440\u0435\u0442\u0438\u043d\u0443",
        "unsupported": "B1 \u043d\u0435 \u043f\u0456\u0434\u0442\u0440\u0438\u043c\u0443\u0454\u0442\u044c\u0441\u044f",
        "not_estimable": "\u041d\u0435 \u043e\u0446\u0456\u043d\u044e\u0454\u0442\u044c\u0441\u044f",
    }
    for target_index, target in enumerate((0.05, 0.01)):
        for arm_index, arm in enumerate(("b0", "b1")):
            position = target_index * 3 + arm_index + 1
            tick_labels.append(f"BER {target:g}\nJoint/{arm.upper()}")
            result = gains.get(f"{target:.2g}", {}).get(arm)
            value, ci, status = _gain_plot_entry(result)
            if value is None:
                unsupported.append((position, status_labels[status or "not_estimable"]))
            else:
                positions.append(position)
                values.append(value)
                errors.append((value - ci[0], ci[1] - value))
                colors_used.append(colors[arm])
    if positions:
        axis.bar(positions, values, color=colors_used, alpha=0.86)
        for position, value, error in zip(positions, values, errors, strict=True):
            axis.errorbar(
                position,
                value,
                yerr=np.asarray(error).reshape(2, 1),
                fmt="none",
                ecolor="#222222",
                capsize=4,
            )
            axis.text(
                position, value, f"{value:.2f} \u0434\u0411", ha="center", va="bottom", fontsize=8
            )
    y_top = max([*values, 1.0]) * 1.2
    for position, message in unsupported:
        axis.text(
            position,
            0.04 * y_top,
            message,
            ha="center",
            va="bottom",
            fontsize=7,
            color="#555555",
            wrap=True,
        )
    all_positions = [
        target_index * 3 + arm_index + 1 for target_index in range(2) for arm_index in range(2)
    ]
    axis.set_xticks(all_positions, tick_labels)
    axis.set_ylim(0.0, y_top)
    axis.axhline(0.0, color="#222222", lw=0.8)
    axis.set_ylabel("Модельний виграш 10 log₁₀(Eb,sep / Eb,joint), дБ")
    axis.set_title(f"Необхідна енергія та виграш — {context}")
    for suffix in ("png", "svg"):
        path = output / f"{scenario}_energy_gain.{suffix}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        generated.append(path)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(9, 5), constrained_layout=True)
    for arm in arms:
        medians = []
        for row in points:
            valid = [
                value
                for value in row["runtime_seconds"][arm]
                if value < RUNTIME_STALL_THRESHOLD_SECONDS
            ]
            medians.append(float(np.median(valid)) if valid else float("nan"))
        axis.plot(
            gamma, medians, marker=".", ms=4, lw=1.4, color=colors[arm], label=ARM_LABELS[arm]
        )
    axis.set_xlabel("Нормована дискретна шкала γᵦ,ᵈ (дБ)")
    axis.set_ylabel("Медіанний час декодування кадру (с)")
    axis.set_title(f"Час роботи приймачів — {context}")
    axis.legend(fontsize=8)
    for suffix in ("png", "svg"):
        path = output / f"{scenario}_runtime.{suffix}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        generated.append(path)
    plt.close(fig)
    return generated


def analyze_scenario(
    records: Sequence[Mapping[str, Any]],
    scenario: str,
    protocol: Mapping[str, Any],
    analysis_root: Path,
) -> dict[str, Any]:
    if not records:
        _write_csv(analysis_root / f"{scenario}_aggregates.csv", [])
        return {
            "scenario": scenario,
            "status": "PARTIAL",
            "planned_grid_points": len(protocol["scenarios"][scenario]["gamma_db_grid"]),
            "observed_grid_points": 0,
            "planned_trials_per_point": int(protocol["trials_per_point"]),
            "observed_trials_by_gamma": {},
            "runtime_suspension_outliers": [],
            "aggregate_points": [],
            "target_gain_analysis": {},
            "plot_files": [],
            "paper_exact": False,
        }
    points = _aggregate_points(records)
    bootstrap = protocol["bootstrap"]
    seed_base = int(bootstrap[f"seed_{scenario}"])
    gains: dict[str, Any] = {}
    for target_index, target in enumerate(protocol["target_ber"]):
        target_key = f"{float(target):.2g}"
        gains[target_key] = {}
        for arm_index, arm in enumerate(("b0", "b1") if scenario == "static" else ("b0",)):
            primary = paired_bootstrap_gain(
                records,
                float(target),
                arm,
                int(bootstrap["replicates"]),
                seed_base + target_index * 10 + arm_index,
                "log10_ber",
            )
            sensitivity = paired_bootstrap_gain(
                records,
                float(target),
                arm,
                int(bootstrap["replicates"]),
                seed_base + 100 + target_index * 10 + arm_index,
                "linear_ber",
            )
            primary["linear_interpolation_sensitivity"] = {
                "gain_db": sensitivity["gain_db"],
                "confidence_interval_db": sensitivity["bootstrap"]["confidence_interval_db"],
                "valid_fraction": sensitivity["bootstrap"]["valid_fraction"],
                "status": sensitivity["status"],
                "required_gamma_db": sensitivity["required_gamma_db"],
            }
            gains[target_key][arm] = primary

    _write_csv(analysis_root / f"{scenario}_aggregates.csv", points)
    generated = _plot_scenario(
        scenario, points, gains, analysis_root / "plots", int(protocol["frame_symbols"])
    )
    expected = int(protocol["trials_per_point"])
    counts = {str(row["gamma_db"]): int(row["trials"]) for row in points}
    plan_complete = len(points) == len(protocol["scenarios"][scenario]["gamma_db_grid"]) and all(
        value == expected for value in counts.values()
    )
    return {
        "scenario": scenario,
        "status": "COMPLETE" if plan_complete else "PARTIAL",
        "planned_grid_points": len(protocol["scenarios"][scenario]["gamma_db_grid"]),
        "observed_grid_points": len(points),
        "planned_trials_per_point": expected,
        "observed_trials_by_gamma": counts,
        "runtime_suspension_outliers": _runtime_suspension_outliers(records),
        "aggregate_points": points,
        "target_gain_analysis": gains,
        "plot_files": [str(path.relative_to(analysis_root.parent.parent)) for path in generated],
        "paper_exact": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/scientific_exp_01b"))
    parser.add_argument(
        "--protocol", type=Path, default=Path("configs/SCIENTIFIC_EXP_01B_PROTOCOL.json")
    )
    args = parser.parse_args()
    output_root = args.output.resolve()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    analysis_root = output_root / "analysis"
    plot_root = analysis_root / "plots"
    plot_root.mkdir(parents=True, exist_ok=True)
    scenarios = {}
    records_by_scenario = {}
    for scenario in ("static", "rician"):
        records, counts = load_completed_records(output_root, scenario, protocol)
        records_by_scenario[scenario] = records
        scenarios[scenario] = analyze_scenario(records, scenario, protocol, analysis_root)
        scenarios[scenario]["completed_trials_by_gamma"] = counts
    seed_independence = verify_seed_independence(
        records_by_scenario, ROOT / "outputs/scientific_exp_01"
    )
    summary = {
        "schema": "scientific-exp01b-independent-analysis-v1",
        "experiment_id": protocol["experiment_id"],
        "protocol_sha256": _sha256(args.protocol.read_bytes()),
        "seed_independence": seed_independence,
        "scenarios": scenarios,
        "paper_exact": False,
        "physical_eb_n0": None,
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    (analysis_root / "analysis_results.json").write_bytes(payload)
    print(
        json.dumps(
            {
                "status": "complete"
                if all(value["status"] == "COMPLETE" for value in scenarios.values())
                else "partial",
                "trial_counts": {
                    name: sum(value["completed_trials_by_gamma"].values())
                    for name, value in scenarios.items()
                },
                "analysis": str(analysis_root / "analysis_results.json"),
                "plot_count": sum(len(value["plot_files"]) for value in scenarios.values()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
