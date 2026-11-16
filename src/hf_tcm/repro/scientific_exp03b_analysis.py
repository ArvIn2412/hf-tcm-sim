"""Independent paired summaries for SCIENTIFIC-EXP-03B trial records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

import numpy as np

Interpolation = Literal["log_ber", "linear_ber"]


def _validate_trials(records: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    if not records:
        raise ValueError("at least one paired trial is required")
    arms = tuple(sorted(records[0]["bit_errors"]))
    if len(arms) < 2:
        raise ValueError("at least two paired receiver arms are required")
    context = (records[0]["scenario"], records[0]["sweep"], records[0]["phase"])
    for row in records:
        if (row["scenario"], row["sweep"], row["phase"]) != context:
            raise ValueError("paired records must share scenario, sweep and phase")
        if tuple(sorted(row["bit_errors"])) != arms:
            raise ValueError("paired records must have identical receiver arms")
        if tuple(sorted(row["pair_errors"])) != arms or tuple(sorted(row["frame_errors"])) != arms:
            raise ValueError("bit, pair and frame counters must have identical receiver arms")
        bits = int(row["bits"])
        pairs = int(row["pairs"])
        if bits <= 0 or pairs <= 0:
            raise ValueError("bit and pair denominators must be positive")
        for arm in arms:
            bit_errors = int(row["bit_errors"][arm])
            pair_errors = int(row["pair_errors"][arm])
            frame_errors = int(row["frame_errors"][arm])
            if not pair_errors <= bit_errors <= 2 * pair_errors:
                raise ValueError("information-bit and information-pair error counts disagree")
            if not 0 <= bit_errors <= bits or not 0 <= pair_errors <= pairs:
                raise ValueError("error count exceeds its denominator")
            if frame_errors not in (0, 1) or (frame_errors == 0) != (bit_errors == 0):
                raise ValueError("FER must indicate whether this complete frame has any bit error")
    return arms


def _point_summary(
    trials: Sequence[Mapping[str, Any]], arms: tuple[str, ...], *, replicates: int, seed: int
) -> dict[str, Any]:
    bits = np.asarray([int(row["bits"]) for row in trials], dtype=np.int64)
    pairs = np.asarray([int(row["pairs"]) for row in trials], dtype=np.int64)
    bit_errors = np.asarray(
        [[int(row["bit_errors"][arm]) for arm in arms] for row in trials], dtype=np.int64
    )
    pair_errors = np.asarray(
        [[int(row["pair_errors"][arm]) for arm in arms] for row in trials], dtype=np.int64
    )
    frame_errors = np.asarray(
        [[int(row["frame_errors"][arm]) for arm in arms] for row in trials], dtype=np.int8
    )
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(trials), size=(replicates, len(trials)))
    sampled_bits = bits[draws].sum(axis=1)
    sampled_pairs = pairs[draws].sum(axis=1)
    ber_boot = bit_errors[draws].sum(axis=1) / sampled_bits[:, None]
    ser_boot = pair_errors[draws].sum(axis=1) / sampled_pairs[:, None]
    fer_boot = frame_errors[draws].mean(axis=1)
    base_bits = int(bits.sum())
    base_pairs = int(pairs.sum())
    base_errors = bit_errors.sum(axis=0)
    base_pair_errors = pair_errors.sum(axis=0)
    base_frame_errors = frame_errors.sum(axis=0)

    def ci(values: np.ndarray) -> list[Any]:
        return np.quantile(values, [0.025, 0.975], axis=0).tolist()

    return {
        "trials": len(trials),
        "bits": base_bits,
        "pairs": base_pairs,
        "bit_errors": {arm: int(base_errors[i]) for i, arm in enumerate(arms)},
        "pair_errors": {arm: int(base_pair_errors[i]) for i, arm in enumerate(arms)},
        "frame_errors": {arm: int(base_frame_errors[i]) for i, arm in enumerate(arms)},
        "ber": {arm: float(base_errors[i] / base_bits) for i, arm in enumerate(arms)},
        "ser_information_pairs": {
            arm: float(base_pair_errors[i] / base_pairs) for i, arm in enumerate(arms)
        },
        "fer": {arm: float(base_frame_errors[i] / len(trials)) for i, arm in enumerate(arms)},
        "zero_error_uncertainty": {
            arm: {
                "observed_bit_errors": int(base_errors[i]),
                "iid_bit_ber_upper95_descriptive_only": (
                    float(1.0 - 0.05 ** (1.0 / base_bits)) if base_errors[i] == 0 else None
                ),
                "independent_trial_fer_upper95": (
                    float(1.0 - 0.05 ** (1.0 / len(trials))) if base_frame_errors[i] == 0 else None
                ),
                "iid_bit_bound_warning": (
                    "bit-level bound assumes independent bits and is not inferential for fading; "
                    "whole-trial cluster bootstrap remains the primary uncertainty method"
                    if base_errors[i] == 0
                    else None
                ),
            }
            for i, arm in enumerate(arms)
        },
        "paired_delta_ber": {
            f"{left}_minus_{right}": float((base_errors[i] - base_errors[j]) / base_bits)
            for i, left in enumerate(arms)
            for j, right in enumerate(arms)
            if i < j
        },
        **(
            {
                "noise_variance_complex": float(
                    next(iter({float(row["noise_variance"]) for row in trials}))
                )
            }
            if all("noise_variance" in row for row in trials)
            and len({float(row["noise_variance"]) for row in trials}) == 1
            else {}
        ),
        "bootstrap_95ci": {
            "method": "paired independent-trial cluster percentile bootstrap",
            "replicates": replicates,
            "seed": seed,
            "ber": {arm: ci(ber_boot[:, i]) for i, arm in enumerate(arms)},
            "ser_information_pairs": {arm: ci(ser_boot[:, i]) for i, arm in enumerate(arms)},
            "fer": {arm: ci(fer_boot[:, i]) for i, arm in enumerate(arms)},
            "paired_delta_ber": {
                f"{left}_minus_{right}": ci(ber_boot[:, i] - ber_boot[:, j])
                for i, left in enumerate(arms)
                for j, right in enumerate(arms)
                if i < j
            },
        },
        **(
            {
                "tx_energy_discrete": float(
                    sum(float(row["tx_energy_discrete"]) for row in trials)
                ),
                "payload_signal_symbols": int(
                    sum(int(row["payload_signal_symbols"]) for row in trials)
                ),
                "total_signal_symbols": int(
                    sum(int(row["total_signal_symbols"]) for row in trials)
                ),
                "information_efficiency_bits_per_symbol": {
                    arm: float(
                        (base_bits - base_errors[i])
                        / sum(int(row["total_signal_symbols"]) for row in trials)
                    )
                    for i, arm in enumerate(arms)
                },
                "energy_efficiency_bits_per_discrete_energy": {
                    arm: float(
                        (base_bits - base_errors[i])
                        / sum(float(row["tx_energy_discrete"]) for row in trials)
                    )
                    for i, arm in enumerate(arms)
                },
            }
            if all(
                "tx_energy_discrete" in row
                and "total_signal_symbols" in row
                and "payload_signal_symbols" in row
                for row in trials
            )
            else {}
        ),
    }


def aggregate_paired_trials(
    records: Sequence[Mapping[str, Any]], *, replicates: int = 5000, seed: int = 833101
) -> list[dict[str, Any]]:
    """Pool counts and paired-cluster CIs per measured energy point."""
    if isinstance(replicates, bool) or replicates <= 0:
        raise ValueError("replicates must be positive")
    if isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be nonnegative")
    arms = _validate_trials(records)
    grouped: dict[float, list[Mapping[str, Any]]] = {}
    for row in records:
        gamma = float(row["gamma_db"])
        if not np.isfinite(gamma):
            raise ValueError("gamma_db must be finite")
        grouped.setdefault(gamma, []).append(row)
    streams = np.random.SeedSequence(seed).spawn(len(grouped))
    result = []
    for (gamma, trials), stream in zip(sorted(grouped.items()), streams, strict=True):
        point_seed = int(stream.generate_state(1, dtype=np.uint32)[0])
        point = _point_summary(trials, arms, replicates=replicates, seed=point_seed)
        point["gamma_db"] = gamma
        point["scenario"] = trials[0]["scenario"]
        point["sweep"] = trials[0]["sweep"]
        point["phase"] = trials[0]["phase"]
        result.append(point)
    return result


def _crossing(
    points: Sequence[Mapping[str, Any]], target: float, arm: str, mode: Interpolation
) -> dict[str, Any]:
    ordered = sorted(points, key=lambda row: float(row["gamma_db"]))
    x = np.asarray([float(row["gamma_db"]) for row in ordered])
    y = np.asarray([float(row["ber"][arm]) for row in ordered])
    if len(x) == 0 or len(set(x.tolist())) != len(x):
        return {"status": "NO_MEASURED_GRID"}
    exact = np.flatnonzero(y == target)
    brackets = [i for i in range(len(y) - 1) if (y[i] - target) * (y[i + 1] - target) < 0]
    if len(exact) + len(brackets) != 1:
        return {"status": "NO_UNIQUE_BRACKET"}
    if len(exact):
        value = float(x[exact[0]])
        return {"status": "EXACT_GRID_POINT", "gamma_db": value, "bracket_db": [value, value]}
    i = brackets[0]
    if y[i] < y[i + 1]:
        return {"status": "UPWARD_CROSSING"}
    if mode == "log_ber" and min(y[i], y[i + 1]) <= 0:
        return {"status": "ZERO_BER_BRACKET_UNRESOLVED"}
    if mode == "log_ber":
        fraction = (np.log10(target) - np.log10(y[i])) / (np.log10(y[i + 1]) - np.log10(y[i]))
    else:
        fraction = (target - y[i]) / (y[i + 1] - y[i])
    value = float(x[i] + fraction * (x[i + 1] - x[i]))
    return {"status": "BRACKETED", "gamma_db": value, "bracket_db": [float(x[i]), float(x[i + 1])]}


def estimate_paired_gain(
    records: Sequence[Mapping[str, Any]],
    *,
    target: float,
    euclidean_arm: str,
    hamming_arm: str,
    replicates: int = 5000,
    seed: int = 833101,
) -> dict[str, Any]:
    """Estimate measured crossing and paired bootstrap gain for both interpolators."""
    if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates <= 0:
        raise ValueError("replicates must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not 0 < target < 1:
        raise ValueError("target BER must lie strictly between zero and one")
    _validate_trials(records)
    grouped: dict[float, list[Mapping[str, Any]]] = {}
    for row in records:
        grouped.setdefault(float(row["gamma_db"]), []).append(row)
    points = []
    for gamma, trials in sorted(grouped.items()):
        denominator = sum(int(row["bits"]) for row in trials)
        points.append(
            {
                "gamma_db": gamma,
                "ber": {
                    arm: sum(int(row["bit_errors"][arm]) for row in trials) / denominator
                    for arm in (euclidean_arm, hamming_arm)
                },
            }
        )
    observed = {
        mode: {
            "euclidean": _crossing(points, target, euclidean_arm, mode),
            "hamming": _crossing(points, target, hamming_arm, mode),
        }
        for mode in ("log_ber", "linear_ber")
    }
    rng = np.random.default_rng(seed)
    gains: dict[str, list[float]] = {"log_ber": [], "linear_ber": []}
    bootstrap_points = []
    for gamma, trials in sorted(grouped.items()):
        bits = np.asarray([int(row["bits"]) for row in trials], dtype=np.int64)
        errors = np.asarray(
            [
                [int(row["bit_errors"][euclidean_arm]), int(row["bit_errors"][hamming_arm])]
                for row in trials
            ],
            dtype=np.int64,
        )
        draws = rng.integers(0, len(trials), size=(replicates, len(trials)))
        denominator = bits[draws].sum(axis=1)
        ber = errors[draws].sum(axis=1) / denominator[:, None]
        bootstrap_points.append((gamma, ber))
    for replicate in range(replicates):
        boot_points = [
            {
                "gamma_db": gamma,
                "ber": {
                    euclidean_arm: float(ber[replicate, 0]),
                    hamming_arm: float(ber[replicate, 1]),
                },
            }
            for gamma, ber in bootstrap_points
        ]
        for mode in gains:
            e = _crossing(boot_points, target, euclidean_arm, mode)
            h = _crossing(boot_points, target, hamming_arm, mode)
            if e.get("gamma_db") is not None and h.get("gamma_db") is not None:
                gains[mode].append(float(h["gamma_db"] - e["gamma_db"]))
    output = {"target_ber": target, "observed": observed, "bootstrap": {}}
    for mode, values in gains.items():
        fraction = len(values) / replicates
        output["bootstrap"][mode] = {
            "replicates": replicates,
            "valid_replicates": len(values),
            "valid_fraction": fraction,
            "gain_db_ci95": np.quantile(values, [0.025, 0.975]).tolist()
            if values and fraction >= 0.95
            else None,
            "conditional_ci95": np.quantile(values, [0.025, 0.975]).tolist() if values else None,
        }
    primary = observed["log_ber"]
    if (
        primary["euclidean"].get("gamma_db") is not None
        and primary["hamming"].get("gamma_db") is not None
    ):
        output["gain_db_log_ber"] = (
            primary["hamming"]["gamma_db"] - primary["euclidean"]["gamma_db"]
        )
    else:
        output["gain_db_log_ber"] = None
    noise_values = {float(row["noise_variance"]) for row in records if "noise_variance" in row}
    if len(noise_values) == 1 and all("noise_variance" in row for row in records):
        noise_variance = noise_values.pop()
        output["noise_variance_complex"] = noise_variance
        output["required_energy_per_information_bit_discrete"] = {
            arm: (
                float(noise_variance * 10.0 ** (observed["log_ber"][arm]["gamma_db"] / 10.0))
                if observed["log_ber"][arm].get("gamma_db") is not None
                else None
            )
            for arm in ("euclidean", "hamming")
        }
    return output


def assess_gain_precision(
    estimate: Mapping[str, Any],
    point_summaries: Sequence[Mapping[str, Any]],
    *,
    target: float,
    arms: Sequence[str],
    estimate_arms: Sequence[str] | None = None,
    precision_criteria: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the frozen error-count, BER-CI, crossing, and gain-CI criteria."""
    target_key = f"{target:g}"
    required_errors = int(
        precision_criteria["per_arm_error_count_at_bracketing_points"][target_key]
    )
    max_ber_half_width = (
        float(precision_criteria["max_95ci_half_width_ber"][target_key])
        if "max_95ci_half_width_ber" in precision_criteria
        else None
    )
    max_gain_half_width = float(precision_criteria["max_95ci_half_width_gain_db"][target_key])
    minimum_valid_fraction = float(precision_criteria["minimum_valid_bootstrap_crossing_fraction"])
    by_gamma = {float(point["gamma_db"]): point for point in point_summaries}
    observed = estimate["observed"]["log_ber"]
    crossing_arms = tuple(estimate_arms or arms)
    if len(crossing_arms) != len(arms):
        raise ValueError("estimate_arms and arms must have the same length")
    checks: dict[str, Any] = {}
    reasons: list[str] = []
    for arm, crossing_arm in zip(arms, crossing_arms, strict=True):
        crossing = observed[crossing_arm]
        status = crossing.get("status")
        if status == "EXACT_GRID_POINT":
            bracket = [float(crossing["gamma_db"])]
        elif status == "BRACKETED":
            bracket = [float(value) for value in crossing["bracket_db"]]
        else:
            bracket = []
            reasons.append(f"{arm}:target_not_bracketed:{status}")
        point_checks = []
        for gamma in bracket:
            point = by_gamma.get(gamma)
            if point is None:
                reasons.append(f"{arm}:missing_measured_point:{gamma:g}")
                continue
            errors = int(point["bit_errors"][arm])
            ci = point["bootstrap_95ci"]["ber"][arm]
            half_width = max(
                float(point["ber"][arm]) - float(ci[0]), float(ci[1]) - float(point["ber"][arm])
            )
            adequate = errors >= required_errors and (
                max_ber_half_width is None or half_width <= max_ber_half_width
            )
            if errors < required_errors:
                reasons.append(f"{arm}:too_few_errors_at_{gamma:g}dB:{errors}<{required_errors}")
            if max_ber_half_width is not None and half_width > max_ber_half_width:
                reasons.append(
                    f"{arm}:ber_ci_too_wide_at_{gamma:g}dB:{half_width:.6g}>{max_ber_half_width:g}"
                )
            point_checks.append(
                {
                    "gamma_db": gamma,
                    "bit_errors": errors,
                    "ber_ci95": [float(ci[0]), float(ci[1])],
                    "ber_ci95_half_width": half_width,
                    "adequate": adequate,
                }
            )
        checks[arm] = {"crossing_status": status, "bracket_points": point_checks}

    bootstrap = estimate["bootstrap"]["log_ber"]
    valid_fraction = float(bootstrap["valid_fraction"])
    gain_ci = bootstrap.get("gain_db_ci95")
    gain = estimate.get("gain_db_log_ber")
    gain_half_width = (
        max(abs(float(gain) - float(gain_ci[0])), abs(float(gain_ci[1]) - float(gain)))
        if gain is not None and gain_ci is not None
        else None
    )
    if valid_fraction < minimum_valid_fraction:
        reasons.append(f"bootstrap_crossing_fraction_below_threshold:{valid_fraction:.6g}")
    if gain_ci is None or gain_half_width is None:
        reasons.append("gain_confidence_interval_unavailable")
    elif gain_half_width > max_gain_half_width:
        reasons.append(f"gain_ci_too_wide:{gain_half_width:.6g}>{max_gain_half_width:g}")
    estimable = all(checks[arm]["bracket_points"] for arm in arms)
    if not estimable:
        status = "TARGET_NOT_ESTIMABLE"
    elif reasons:
        status = "INSUFFICIENT_PRECISION"
    else:
        status = "PRECISION_CRITERIA_MET"
    return {
        "status": status,
        "target_ber": target,
        "required_errors_per_bracket_point_per_arm": required_errors,
        "maximum_ber_ci95_half_width": max_ber_half_width,
        "maximum_gain_ci95_half_width_db": max_gain_half_width,
        "minimum_valid_bootstrap_crossing_fraction": minimum_valid_fraction,
        "bootstrap_valid_fraction": valid_fraction,
        "gain_ci95": gain_ci,
        "gain_ci95_half_width_db": gain_half_width,
        "arm_checks": checks,
        "reasons": reasons,
    }


def to_energy_statistics_record(row: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt this module's verified per-trial rows to the legacy gain analyzer."""
    return {
        "scenario": row["scenario"],
        "sweep": row["sweep"],
        "phase": row["phase"],
        "gamma_db": row["gamma_db"],
        "bits": row["bits"],
        "pairs": row["pairs"],
        "bit_errors": dict(row["bit_errors"]),
        "pair_errors": dict(row["pair_errors"]),
    }
