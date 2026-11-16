"""T-04: AWGN variance, validation, and deterministic random generation."""

import numpy as np
import pytest

from hf_tcm.channels.awgn import add_awgn, awgn_noise_variance


def test_noise_variance_matches_project_energy_convention() -> None:
    assert awgn_noise_variance(0.0) == pytest.approx(0.5)
    assert awgn_noise_variance(10.0) == pytest.approx(0.05)


def test_awgn_has_zero_mean_and_expected_complex_variance() -> None:
    transmitted = np.ones(100_000, dtype=np.complex128)
    received = add_awgn(transmitted, 0.0, rng=np.random.default_rng(271828))
    noise = received - transmitted

    assert abs(np.mean(noise)) < 0.01
    assert np.mean(np.abs(noise) ** 2) == pytest.approx(0.5, rel=0.015)


def test_awgn_is_reproducible_for_equal_seeds() -> None:
    transmitted = np.asarray([1.0 + 0.0j, 0.0 + 1.0j, -1.0 + 0.0j])

    first = add_awgn(transmitted, 4.0, rng=np.random.default_rng(1234))
    second = add_awgn(transmitted, 4.0, rng=np.random.default_rng(1234))

    assert np.array_equal(first, second)


@pytest.mark.parametrize(
    ("ebn0_db", "bits_per_symbol", "energy_per_symbol"),
    [(float("nan"), 2, 1), (-10000, 2, 1), (0, 0, 1), (0, 2, -1)],
)
def test_awgn_rejects_invalid_parameters(
    ebn0_db: float, bits_per_symbol: float, energy_per_symbol: float
) -> None:
    with pytest.raises(ValueError):
        awgn_noise_variance(
            ebn0_db, bits_per_symbol=bits_per_symbol, energy_per_symbol=energy_per_symbol
        )


def test_awgn_requires_numpy_generator() -> None:
    with pytest.raises(ValueError, match="Generator"):
        add_awgn(np.ones(2, dtype=np.complex128), 0.0, rng=123)  # type: ignore[arg-type]


def test_awgn_rejects_non_finite_or_non_vector_samples() -> None:
    with pytest.raises(ValueError, match="finite 1-D"):
        add_awgn(np.asarray([complex(float("inf"), 0.0)]), 0.0, rng=np.random.default_rng(1))
    with pytest.raises(ValueError, match="finite 1-D"):
        add_awgn(np.ones((2, 2), dtype=np.complex128), 0.0, rng=np.random.default_rng(1))
