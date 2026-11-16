"""Descriptive per-path channel power and lag-one correlation statistics."""

from dataclasses import dataclass

import numpy as np

from hf_tcm.channels.multipath import ChannelTruth


@dataclass(frozen=True, slots=True)
class ChannelPathStatistics:
    """Configured and measured values for one diagnostic channel path."""

    delay_samples: int
    configured_average_power: float
    measured_average_power: float
    lag_one_correlation: complex | None


def channel_statistics(truth: ChannelTruth) -> tuple[ChannelPathStatistics, ...]:
    """Summarize coefficient power and normalized lag-one correlation by path."""
    if not isinstance(truth, ChannelTruth):
        raise ValueError("truth must be a ChannelTruth diagnostic object")
    coefficients = np.asarray(truth.coefficients, dtype=np.complex128)
    expected_shape = (len(truth.path_delays), "nonzero sample count")
    if (
        coefficients.ndim != 2
        or coefficients.shape[0] != len(truth.path_delays)
        or coefficients.shape[1] == 0
        or len(truth.average_powers) != len(truth.path_delays)
        or len(truth.k_factors) != len(truth.path_delays)
        or not np.all(np.isfinite(coefficients))
    ):
        raise ValueError(f"truth coefficient shape is invalid; expected {expected_shape}")
    result = []
    for index, delay in enumerate(truth.path_delays):
        path = coefficients[index]
        power = float(np.mean(np.abs(path) ** 2))
        if len(path) < 2:
            correlation = None
        else:
            denominator = float(np.vdot(path[:-1], path[:-1]).real)
            correlation = (
                complex(np.vdot(path[:-1], path[1:]) / denominator) if denominator > 0.0 else None
            )
        result.append(
            ChannelPathStatistics(
                delay_samples=delay,
                configured_average_power=truth.average_powers[index],
                measured_average_power=power,
                lag_one_correlation=correlation,
            )
        )
    return tuple(result)
