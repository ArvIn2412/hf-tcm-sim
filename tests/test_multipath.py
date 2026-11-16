"""M3 configurable integer-delay multipath channel checks."""

import numpy as np
import pytest

from hf_tcm.channels.multipath import (
    ChannelOutput,
    MultipathConfig,
    PathSpec,
    apply_multipath,
)


def test_impulse_reveals_configured_path_delays_and_truth() -> None:
    config = MultipathConfig(
        paths=(
            PathSpec(delay_samples=0, average_power=0.7, k_factor=1.0),
            PathSpec(delay_samples=3, average_power=0.3, k_factor=0.0),
        )
    )
    result = apply_multipath(
        np.asarray([1.0 + 0.0j, 0.0j, 0.0j, 0.0j]),
        config,
        rng=np.random.default_rng(5),
    )

    assert isinstance(result, ChannelOutput)
    assert result.received.shape == (7,)
    assert result.truth.path_delays == (0, 3)
    assert result.truth.average_powers == (0.7, 0.3)
    assert result.truth.k_factors == (1.0, 0.0)
    assert result.received[0] == result.truth.coefficients[0, 0]
    assert result.received[3] == result.truth.coefficients[1, 3]
    assert result.truth.coefficients.shape == (2, 7)
    assert result.truth.model_profile == "approximate_static_rician_multipath"


def test_multipath_output_is_reproducible_for_equal_seeds() -> None:
    config = MultipathConfig(
        paths=(
            PathSpec(delay_samples=0, average_power=0.5, k_factor=0.0),
            PathSpec(delay_samples=2, average_power=0.5, k_factor=2.0),
        ),
        fading_mode="approximate_ar1",
        correlation=0.7,
    )
    signal = np.asarray([1.0 + 1.0j, -1.0 + 0.5j, 0.25 - 0.75j])

    first = apply_multipath(signal, config, rng=np.random.default_rng(31))
    second = apply_multipath(signal, config, rng=np.random.default_rng(31))

    assert np.array_equal(first.received, second.received)
    assert np.array_equal(first.truth.coefficients, second.truth.coefficients)
    assert first.truth.path_delays == second.truth.path_delays


def test_multipath_rejects_bad_delays_power_and_inputs() -> None:
    with pytest.raises(ValueError, match="delay_samples"):
        PathSpec(delay_samples=-1, average_power=1.0, k_factor=0.0)
    with pytest.raises(ValueError, match="average_power"):
        PathSpec(delay_samples=0, average_power=-0.1, k_factor=0.0)
    with pytest.raises(ValueError, match="paths"):
        MultipathConfig(paths=())
    with pytest.raises(ValueError, match="finite 1-D"):
        apply_multipath(
            np.asarray([complex(float("nan"), 0.0)]),
            MultipathConfig(paths=(PathSpec(delay_samples=0, average_power=1.0, k_factor=0.0),)),
            rng=np.random.default_rng(0),
        )
