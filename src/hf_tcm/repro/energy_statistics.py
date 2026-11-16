"""[ПРОЄКТ] Measured-grid energy contrasts and paired trial-cluster bootstrap.

Interpolation is linear in log10(BER) against gamma in dB, within adjacent
measured points only. Zero observed errors receive no pseudocount. These
utilities neither define a physical energy convention nor establish article
fidelity; callers must supply homogeneous, independently sampled trial grids.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from numbers import Integral
from typing import Any

import numpy as np

Record = Mapping[str, Any]
_CONTEXT = ("scenario", "sweep", "phase")


def _count(value: Any, name: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    if value < (1 if positive else 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return int(value)


def _validated_records(records: Iterable[Record]) -> tuple[list[Record], tuple[str, ...]]:
    rows = list(records)
    if not rows:
        raise ValueError("records must contain at least one paired trial")
    try:
        arms = tuple(sorted(rows[0]["bit_errors"]))
        if "joint" not in arms:
            raise ValueError("bit_errors must contain the joint arm")
        for row in rows:
            if not np.isfinite(float(row["gamma_db"])):
                raise ValueError("gamma_db must be finite")
            for key in _CONTEXT:
                if row[key] != rows[0][key]:
                    raise ValueError(f"records must have a single {key}")
            bits = _count(row["bits"], "bits", positive=True)
            pairs = _count(row["pairs"], "pairs", positive=True)
            for key, denominator in (("bit_errors", bits), ("pair_errors", pairs)):
                if tuple(sorted(row[key])) != arms:
                    raise ValueError(f"{key} must contain the same paired arms in every trial")
                for arm in arms:
                    if _count(row[key][arm], f"{key}.{arm}") > denominator:
                        raise ValueError(f"{key}.{arm} exceeds its denominator")
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError("invalid paired trial record or missing required field") from exc
    return rows, arms


def _aggregate(rows: Sequence[Record], arms: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[float, list[Record]] = {}
    for row in rows:
        grouped.setdefault(float(row["gamma_db"]), []).append(row)
    result = []
    for gamma, trials in sorted(grouped.items()):
        bits = sum(int(row["bits"]) for row in trials)
        pairs = sum(int(row["pairs"]) for row in trials)
        bit_errors = {arm: sum(int(row["bit_errors"][arm]) for row in trials) for arm in arms}
        pair_errors = {arm: sum(int(row["pair_errors"][arm]) for row in trials) for arm in arms}
        result.append(
            {
                "gamma_db": gamma,
                "trials": len(trials),
                "bits": bits,
                "pairs": pairs,
                "bit_errors": bit_errors,
                "pair_errors": pair_errors,
                "ber": {arm: bit_errors[arm] / bits for arm in arms},
                "ser": {arm: pair_errors[arm] / pairs for arm in arms},
                **{key: trials[0][key] for key in _CONTEXT},
            }
        )
    return result


def aggregate_energy_records(records: Iterable[Record]) -> list[dict[str, Any]]:
    """Pool integer numerators and denominators by gamma, within one context."""
    rows, arms = _validated_records(records)
    return _aggregate(rows, arms)


def required_gamma_crossing(
    points: Sequence[Record], target: float, arm: str = "joint"
) -> dict[str, Any]:
    """Locate an unambiguous measured crossing without extrapolation or floors.

    Inputs are aggregates with ``gamma_db`` and ``ber`` fields. Exact isolated
    grid hits are accepted. Multiple crossings, target plateaus, and crossings
    requiring log(0) remain unestimated. A sole upward crossing is rejected.
    """
    if not np.isfinite(target) or not 0 < target < 1:
        raise ValueError("target must be finite and strictly between zero and one")
    ordered = sorted(points, key=lambda row: float(row["gamma_db"]))
    gamma = np.asarray([float(row["gamma_db"]) for row in ordered])
    ber = np.asarray([float(row["ber"][arm]) for row in ordered])
    if (
        not np.all(np.isfinite(gamma))
        or not np.all(np.isfinite(ber))
        or np.any((ber < 0) | (ber > 1))
        or np.any(np.diff(gamma) <= 0)
    ):
        raise ValueError("crossing requires unique finite gamma and BER in [0, 1]")

    def answer(status: str, value: float | None = None, bracket: Any = None) -> dict:
        return {"status": status, "required_gamma_db": value, "bracket_gamma_db": bracket}

    if len(ber) == 0:
        return answer("NO_CROSSING")
    if np.all(ber == 0):
        return answer("ALL_ZERO_BER")
    exact = np.flatnonzero(ber == target)
    if np.any(np.diff(exact) == 1):
        return answer("TARGET_PLATEAU")
    brackets = [
        index
        for index in range(len(ber) - 1)
        if (ber[index] - target) * (ber[index + 1] - target) < 0
    ]
    if len(exact) + len(brackets) > 1:
        return answer("AMBIGUOUS_MULTIPLE_CROSSINGS")
    if len(exact) == 1:
        value = float(gamma[exact[0]])
        return answer("EXACT_GRID_POINT", value, [value, value])
    if not brackets:
        return answer("NO_CROSSING")
    index = brackets[0]
    if ber[index] < ber[index + 1]:
        return answer("UPWARD_CROSSING")
    if min(ber[index], ber[index + 1]) == 0:
        return answer("ZERO_BER_BRACKET_UNRESOLVED")
    fraction = (np.log10(target) - np.log10(ber[index])) / (
        np.log10(ber[index + 1]) - np.log10(ber[index])
    )
    value = float(gamma[index] + fraction * (gamma[index + 1] - gamma[index]))
    return answer("BRACKETED", value, [float(gamma[index]), float(gamma[index + 1])])


def analyze_energy_records(
    records: Iterable[Record],
    target: float,
    arm: str = "b0",
    replicates: int = 1000,
    seed: int = 0,
) -> dict[str, Any]:
    """Estimate separate-minus-joint required gamma with paired bootstrap.

    Each grid point receives an independent SeedSequence child stream. A draw
    selects whole paired trial rows, jointly for all receiver arms, then pools
    counts/denominators. Grid crossings are re-evaluated for every replicate.
    The percentile 95% CI is exposed only if >=95% of replicates have valid
    crossings in both arms and the observed gain is estimable. Otherwise only
    explicitly conditional quantiles of valid replicates are exposed.
    """
    replicates = _count(replicates, "replicates", positive=True)
    seed = _count(seed, "seed")
    rows, arms = _validated_records(records)
    if arm == "joint" or arm not in arms:
        raise ValueError("arm must name an available separate receiver")
    points = _aggregate(rows, arms)
    crossings = {name: required_gamma_crossing(points, target, name) for name in ("joint", arm)}
    required = {
        "joint": crossings["joint"]["required_gamma_db"],
        "separate": crossings[arm]["required_gamma_db"],
    }
    observed = all(value is not None for value in required.values())
    gain = required["separate"] - required["joint"] if observed else None
    grouped = {point["gamma_db"]: [] for point in points}
    for row in rows:
        grouped[float(row["gamma_db"])].append(row)
    streams = np.random.SeedSequence(seed).spawn(len(points))
    sampled_ber = np.empty((replicates, len(points), 2))
    for index, (gamma, trials) in enumerate(sorted(grouped.items())):
        # A canonical row order also makes seeded replay independent of file order.
        trials.sort(
            key=lambda row: (
                row["bits"],
                row["pairs"],
                *(row["bit_errors"][name] for name in arms),
                *(row["pair_errors"][name] for name in arms),
            )
        )
        rng = np.random.default_rng(streams[index])
        draws = rng.integers(len(trials), size=(replicates, len(trials)))
        denominators = np.asarray([row["bits"] for row in trials], dtype=float)
        sampled_bits = denominators[draws].sum(axis=1)
        for column, name in enumerate(("joint", arm)):
            errors = np.asarray([row["bit_errors"][name] for row in trials], dtype=float)
            sampled_ber[:, index, column] = errors[draws].sum(axis=1) / sampled_bits
    valid_gains = []
    for replicate in range(replicates):
        sample_points = [
            {
                "gamma_db": point["gamma_db"],
                "ber": {
                    "joint": sampled_ber[replicate, index, 0],
                    arm: sampled_ber[replicate, index, 1],
                },
            }
            for index, point in enumerate(points)
        ]
        joint = required_gamma_crossing(sample_points, target)["required_gamma_db"]
        separate = required_gamma_crossing(sample_points, target, arm)["required_gamma_db"]
        if joint is not None and separate is not None:
            valid_gains.append(separate - joint)
    valid_fraction = len(valid_gains) / replicates
    quantiles = np.quantile(valid_gains, [0.025, 0.975]).tolist() if valid_gains else None
    ci_available = observed and valid_fraction >= 0.95
    flags = []
    if min(point["trials"] for point in points) < 20:
        flags.append("LOW_TRIAL_COUNT")
    if any(point["bit_errors"][name] == 0 for point in points for name in ("joint", arm)):
        flags.append("ZERO_BIT_ERRORS")
    if quantiles is not None and quantiles[0] == quantiles[1]:
        flags.append("DEGENERATE_BOOTSTRAP")
    return {
        "status": "ESTIMATED" if ci_available else "PARTIAL" if observed else "NOT_ESTIMABLE",
        "target_ber": target,
        "separate_arm": arm,
        "observed_crossing": observed,
        "crossings": crossings,
        "required_gamma_db": required,
        "gain_db": gain,
        "aggregate": points,
        "flags": flags,
        "bootstrap": {
            "status": "VALID_CROSSINGS"
            if ci_available
            else "PARTIAL_VALID_CROSSINGS"
            if valid_gains
            else "NO_VALID_CROSSINGS",
            "method": "paired_trial_cluster_percentile_independent_gamma_streams",
            "seed": seed,
            "total_replicates": replicates,
            "valid_replicates": len(valid_gains),
            "valid_fraction": valid_fraction,
            "minimum_valid_fraction": 0.95,
            "confidence_level": 0.95,
            "confidence_interval_db": quantiles if ci_available else None,
            "conditional_quantiles_db": quantiles,
        },
    }
