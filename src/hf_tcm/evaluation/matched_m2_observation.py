"""Evaluation-side adapter from ADR-012 sample buffers to M2 observations."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.receiver.reconstruction_observation import (
    ADR012_PROFILE,
    ADR012_SAMPLES_PER_SYMBOL,
)

ComplexVector = NDArray[np.complex128]


def _integer(value: object, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _positive_real(value: object, *, name: str, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive real number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a finite positive real number")
    return result


def _immutable_complex_vector(values: ArrayLike, *, name: str) -> ComplexVector:
    try:
        raw = np.asarray(values)
        if not np.iscomplexobj(raw):
            raise ValueError
        vector = np.asarray(raw, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite complex vector") from exc
    if (
        vector.ndim != 1
        or not np.all(np.isfinite(vector.real))
        or not np.all(np.isfinite(vector.imag))
    ):
        raise ValueError(f"{name} must be a finite complex vector")
    owned = np.array(vector, dtype=np.complex128, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.complex128)


def effective_discrete_gamma_b(real_channel_gain: Real, sigma_squared: Real) -> float:
    """Return `4*a**2/sigma_squared` for the accepted sample-noise contract."""
    gain = _positive_real(real_channel_gain, name="real_channel_gain")
    variance = _positive_real(sigma_squared, name="sigma_squared")
    assert gain is not None and variance is not None
    gamma = 4.0 * gain * gain / variance
    if not math.isfinite(gamma) or gamma <= 0.0:
        raise ValueError("effective discrete gamma_b is outside the supported numeric range")
    return gamma


def sample_variance_from_effective_discrete_gamma_b(
    real_channel_gain: Real, gamma_b: Real
) -> float:
    """Invert `gamma_b_eff=4*a**2/sigma_squared` without a physical SNR label."""
    gain = _positive_real(real_channel_gain, name="real_channel_gain")
    gamma = _positive_real(gamma_b, name="effective_discrete_gamma_b")
    assert gain is not None and gamma is not None
    variance = 4.0 * gain * gain / gamma
    if not math.isfinite(variance) or variance <= 0.0:
        raise ValueError("sigma_squared is outside the supported numeric range")
    return variance


@dataclass(frozen=True, slots=True)
class MatchedM2ObservationResult:
    """Immutable equalized symbol-rate observations and their sample windows."""

    observations: ComplexVector
    symbol_indices: tuple[int, ...]
    sample_windows: tuple[tuple[int, ...], ...]
    symbol_origin_sample: int
    real_channel_gain: float
    sigma_squared: float | None
    effective_symbol_noise_variance: float | None
    effective_discrete_gamma_b: float | None
    effective_discrete_gamma_b_db: float | None
    profile: str
    reducer: str = "arithmetic_mean_exactly_8_then_divide_by_oracle_real_gain"

    def __post_init__(self) -> None:
        values = _immutable_complex_vector(self.observations, name="observations")
        if values.shape != (len(self.symbol_indices),):
            raise ValueError("observations must contain one value per symbol label")
        object.__setattr__(self, "observations", values)


def prepare_matched_m2_observations(
    received: ArrayLike,
    *,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    symbol_indices: Sequence[int],
    real_channel_gain: Real,
    sigma_squared: Real | None,
    profile: str,
    path_count: int,
    path_delays_samples: Sequence[int],
    samples_per_symbol: int,
) -> MatchedM2ObservationResult:
    """Reduce complete received windows and equalize by explicit positive `a`.

    This adapter does not create noise or inspect reference/transmitted data.
    `sigma_squared=None` is reserved for explicit deterministic or zero-noise
    operands and therefore produces no gamma or noise-variance claim.
    """
    if profile != ADR012_PROFILE:
        raise ValueError("profile must be 'reconstructed_offline'")
    if isinstance(path_count, (bool, np.bool_)) or path_count != 1:
        raise ValueError("matched M2 observation requires L=1")
    delays = tuple(path_delays_samples)
    if delays != (0,):
        raise ValueError("matched M2 observation requires exactly one zero-delay path")
    if type(samples_per_symbol) is not int or samples_per_symbol != ADR012_SAMPLES_PER_SYMBOL:
        raise ValueError("matched M2 observation requires exactly 8 samples per symbol")
    gain = _positive_real(real_channel_gain, name="real_channel_gain")
    variance = _positive_real(sigma_squared, name="sigma_squared", allow_none=True)
    assert gain is not None
    start = _integer(received_start_sample, name="received_start_sample", minimum=0)
    origin = _integer(symbol_origin_sample, name="symbol_origin_sample")
    try:
        samples = np.asarray(received)
        labels_raw = np.asarray(absolute_sample_indices)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("received and sample labels must be arrays") from exc
    if samples.ndim != 1 or not np.iscomplexobj(samples) or samples.size == 0:
        raise ValueError("received must be a nonempty one-dimensional complex array")
    if (
        labels_raw.ndim != 1
        or labels_raw.shape != samples.shape
        or labels_raw.dtype.kind not in "iu"
    ):
        raise ValueError("absolute_sample_indices must label every received sample with an integer")
    limits = np.iinfo(np.int64)
    if labels_raw.size and (np.any(labels_raw > limits.max) or np.any(labels_raw < limits.min)):
        raise ValueError("absolute_sample_indices exceed the supported int64 range")
    labels = np.asarray(labels_raw, dtype=np.int64)
    if start + samples.size - 1 > limits.max:
        raise ValueError("received sample window exceeds the supported int64 range")
    expected_labels = np.arange(start, start + samples.size, dtype=np.int64)
    if not np.array_equal(labels, expected_labels):
        raise ValueError("sample labels must be contiguous from received_start_sample")
    try:
        received_values = np.asarray(samples, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("received must contain finite complex values") from exc
    if not np.all(np.isfinite(received_values.real)) or not np.all(
        np.isfinite(received_values.imag)
    ):
        raise ValueError("received must contain finite complex values")
    try:
        symbols = tuple(
            _integer(value, name="symbol_indices entry", minimum=0) for value in symbol_indices
        )
    except TypeError as exc:
        raise ValueError("symbol_indices must be a nonempty sequence") from exc
    if not symbols or any(right != left + 1 for left, right in zip(symbols, symbols[1:])):
        raise ValueError("symbol_indices must be nonempty, ordered, and consecutive")

    observations: list[complex] = []
    windows: list[tuple[int, ...]] = []
    for symbol in symbols:
        first_sample = origin + ADR012_SAMPLES_PER_SYMBOL * symbol
        window_labels = tuple(range(first_sample, first_sample + ADR012_SAMPLES_PER_SYMBOL))
        if first_sample < start or window_labels[-1] >= start + samples.size:
            raise ValueError("received buffer does not contain a complete requested symbol window")
        offset = first_sample - start
        window = received_values[offset : offset + ADR012_SAMPLES_PER_SYMBOL]
        if window.shape != (ADR012_SAMPLES_PER_SYMBOL,) or not np.array_equal(
            labels[offset : offset + ADR012_SAMPLES_PER_SYMBOL], window_labels
        ):
            raise ValueError("symbol window labels do not match symbol origin and indices")
        observations.append(complex(np.mean(window, dtype=np.complex128)) / gain)
        windows.append(window_labels)
    observation_array = _immutable_complex_vector(observations, name="observations")
    effective_variance = None if variance is None else variance / (8.0 * gain * gain)
    if effective_variance is not None and (
        not math.isfinite(effective_variance) or effective_variance <= 0.0
    ):
        raise ValueError("effective symbol noise variance is outside the supported numeric range")
    gamma = None if variance is None else effective_discrete_gamma_b(gain, variance)
    gamma_db = None if gamma is None else 10.0 * math.log10(gamma)
    return MatchedM2ObservationResult(
        observations=observation_array,
        symbol_indices=symbols,
        sample_windows=tuple(windows),
        symbol_origin_sample=origin,
        real_channel_gain=gain,
        sigma_squared=variance,
        effective_symbol_noise_variance=effective_variance,
        effective_discrete_gamma_b=gamma,
        effective_discrete_gamma_b_db=gamma_db,
        profile=profile,
    )
