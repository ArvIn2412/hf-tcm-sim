from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.evaluation.matched_m2_observation import (
    effective_discrete_gamma_b,
    prepare_matched_m2_observations,
    sample_variance_from_effective_discrete_gamma_b,
)
from hf_tcm.receiver.reconstruction_observation import ADR012_PROFILE, ADR012_SAMPLES_PER_SYMBOL


def _prepare(
    received: np.ndarray,
    *,
    origin: int = 19,
    first_symbol: int = 4,
    gain: float = 0.75,
    sigma_squared: float | None = 0.012,
) -> object:
    labels = np.arange(origin + 8 * first_symbol, origin + 8 * first_symbol + received.size)
    return prepare_matched_m2_observations(
        received,
        absolute_sample_indices=labels,
        received_start_sample=int(labels[0]),
        symbol_origin_sample=origin,
        symbol_indices=tuple(range(first_symbol, first_symbol + received.size // 8)),
        real_channel_gain=gain,
        sigma_squared=sigma_squared,
        profile=ADR012_PROFILE,
        path_count=1,
        path_delays_samples=(0,),
        samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL,
    )


def test_mean_of_eight_is_equalized_once_and_time_windows_are_explicit() -> None:
    gain = 0.75
    clean_symbols = np.array([1.0 + 1.0j, -1.0 + 0.0j], dtype=np.complex128)
    noise = np.arange(16, dtype=np.float64).reshape(2, 8) * (0.01 + 0.02j)
    received = gain * np.repeat(clean_symbols, 8) + noise.reshape(-1)
    original = received.copy()

    result = _prepare(received, gain=gain)

    expected = np.mean(received.reshape(2, 8), axis=1) / gain
    assert result.observations.shape == (2,)
    assert np.allclose(result.observations, expected, rtol=0.0, atol=1e-15)
    assert result.symbol_indices == (4, 5)
    assert result.sample_windows == (
        tuple(range(51, 59)),
        tuple(range(59, 67)),
    )
    assert result.effective_symbol_noise_variance == pytest.approx(0.012 / (8 * gain**2))
    assert np.array_equal(received, original)
    with pytest.raises(ValueError):
        result.observations[0] = 0.0


def test_effective_gamma_and_sample_variance_are_inverse() -> None:
    for gain in (0.75, 2.0):
        for variance in (0.001, 0.25):
            gamma = effective_discrete_gamma_b(gain, variance)
            assert gamma == pytest.approx(4 * gain**2 / variance)
            assert sample_variance_from_effective_discrete_gamma_b(gain, gamma) == pytest.approx(
                variance
            )


@pytest.mark.parametrize("gain", [0.0, -0.5, float("nan"), float("inf")])
def test_observation_adapter_rejects_invalid_gain(gain: float) -> None:
    with pytest.raises(ValueError):
        _prepare(np.ones(8, dtype=np.complex128), gain=gain)


def test_observation_adapter_rejects_invalid_profile_noise_and_windows() -> None:
    received = np.ones(8, dtype=np.complex128)
    labels = np.arange(51, 59)
    arguments = {
        "absolute_sample_indices": labels,
        "received_start_sample": 51,
        "symbol_origin_sample": 19,
        "symbol_indices": (4,),
        "real_channel_gain": 0.75,
        "sigma_squared": 0.01,
        "profile": ADR012_PROFILE,
        "path_count": 1,
        "path_delays_samples": (0,),
        "samples_per_symbol": 8,
    }
    for invalid in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            prepare_matched_m2_observations(received, **(arguments | {"sigma_squared": invalid}))
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(received, **(arguments | {"profile": "source_faithful"}))
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(received, **(arguments | {"path_count": 2}))
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(received, **(arguments | {"path_delays_samples": (1,)}))
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(received, **(arguments | {"samples_per_symbol": 4}))
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(received[:-1], **arguments)
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(received, **(arguments | {"symbol_indices": (5,)}))
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(
            received,
            **(arguments | {"absolute_sample_indices": np.arange(52, 60)}),
        )
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(
            received,
            **(
                arguments
                | {"absolute_sample_indices": np.full(8, np.iinfo(np.uint64).max, dtype=np.uint64)}
            ),
        )
    invalid_received = received.copy()
    invalid_received[-1] = complex(np.nan, 0.0)
    with pytest.raises(ValueError):
        prepare_matched_m2_observations(invalid_received, **arguments)


def test_noise_variance_may_be_absent_for_explicit_zero_noise_control() -> None:
    result = _prepare(np.zeros(8, dtype=np.complex128), sigma_squared=None)
    assert result.observations.shape == (1,)
    assert result.effective_symbol_noise_variance is None
    assert result.effective_discrete_gamma_b is None
