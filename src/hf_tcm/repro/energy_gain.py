"""Guarded energy-gain interpolation for a future physically normalized study."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnergyGainEstimate:
    gain_db: float
    target_ber: float
    snr_joint_db: float
    snr_separate_db: float
    interpolation: str
    evidence_status: str = "interpolated_from_measured_points"


def estimate_energy_gain_db(
    joint_points: list[tuple[float, float]],
    separate_points: list[tuple[float, float]],
    *,
    target_ber: float,
    x_axis_unit: str,
    physical_snr_defined: bool,
    interpolation: str = "linear_ber_between_adjacent_measured_points",
) -> EnergyGainEstimate:
    """Compute SNR_B(target)-SNR_A(target), refusing sample-noise proxies."""
    if x_axis_unit != "physical_snr_db" or not physical_snr_defined:
        raise ValueError(
            "energy gain requires a physically defined SNR axis; sample-domain noise is insufficient"
        )
    if interpolation != "linear_ber_between_adjacent_measured_points":
        raise ValueError("unsupported interpolation method")
    if not 0 < target_ber < 1:
        raise ValueError("target_ber must lie strictly between zero and one")

    def crossing(points: list[tuple[float, float]], label: str) -> float:
        ordered = sorted((float(x), float(y)) for x, y in points)
        if len(ordered) < 2 or any(not 0 <= y <= 1 for _, y in ordered):
            raise ValueError(f"{label} needs at least two measured BER points in [0,1]")
        matches: list[float] = []
        for (x0, y0), (x1, y1) in zip(ordered, ordered[1:], strict=False):
            if x0 == x1:
                raise ValueError(f"{label} contains duplicate SNR coordinates")
            if y0 == target_ber:
                matches.append(x0)
            if (y0 - target_ber) * (y1 - target_ber) < 0:
                ratio = (target_ber - y0) / (y1 - y0)
                matches.append(x0 + ratio * (x1 - x0))
        if ordered[-1][1] == target_ber:
            matches.append(ordered[-1][0])
        if len(matches) != 1:
            raise ValueError(
                f"{label} curve must have exactly one measured bracket/crossing; no extrapolation"
            )
        return matches[0]

    snr_a = crossing(joint_points, "joint")
    snr_b = crossing(separate_points, "separate")
    return EnergyGainEstimate(
        gain_db=snr_b - snr_a,
        target_ber=target_ber,
        snr_joint_db=snr_a,
        snr_separate_db=snr_b,
        interpolation=interpolation,
    )
