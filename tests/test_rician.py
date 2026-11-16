"""M3 Rician coefficient generation and T-09 power/correlation checks."""

import numpy as np
import pytest

from hf_tcm.channels.rician import generate_rician_coefficients


@pytest.mark.statistical
def test_correlated_rician_coefficients_match_power_and_correlation() -> None:
    average_power = 0.6
    rho = 0.65
    coefficients = generate_rician_coefficients(
        120_000,
        average_power=average_power,
        k_factor=0.0,
        rng=np.random.default_rng(20261026),
        mode="approximate_ar1",
        correlation=rho,
    )

    measured_power = float(np.mean(np.abs(coefficients) ** 2))
    measured_correlation = np.vdot(coefficients[:-1], coefficients[1:]) / np.vdot(
        coefficients[:-1], coefficients[:-1]
    )
    assert measured_power == pytest.approx(average_power, rel=0.012)
    assert measured_correlation.real == pytest.approx(rho, abs=0.015)
    assert abs(measured_correlation.imag) < 0.015


@pytest.mark.statistical
def test_rician_k_factor_matches_configured_mean_to_diffuse_power_ratio() -> None:
    coefficients = generate_rician_coefficients(
        120_000,
        average_power=0.8,
        k_factor=3.0,
        rng=np.random.default_rng(314159),
        mode="approximate_ar1",
        correlation=0.3,
    )
    diffuse = coefficients - np.mean(coefficients)
    measured_k = abs(np.mean(coefficients)) ** 2 / np.mean(np.abs(diffuse) ** 2)

    assert measured_k == pytest.approx(3.0, rel=0.025)


def test_static_rician_is_constant_over_requested_interval() -> None:
    coefficients = generate_rician_coefficients(
        12,
        average_power=0.7,
        k_factor=3.0,
        rng=np.random.default_rng(7),
        mode="static",
    )

    assert np.all(coefficients == coefficients[0])


def test_rician_coefficients_repeat_for_same_seed() -> None:
    kwargs = {
        "average_power": 1.0,
        "k_factor": 2.0,
        "mode": "approximate_ar1",
        "correlation": 0.4,
    }
    first = generate_rician_coefficients(
        32,
        rng=np.random.default_rng(99),
        **kwargs,  # type: ignore[arg-type]
    )
    second = generate_rician_coefficients(
        32,
        rng=np.random.default_rng(99),
        **kwargs,  # type: ignore[arg-type]
    )

    assert np.array_equal(first, second)


@pytest.mark.parametrize(
    ("length", "average_power", "k_factor", "mode", "correlation"),
    [
        (0, 1.0, 1.0, "static", 0.0),
        (4, 0.0, 1.0, "static", 0.0),
        (4, 1.0, -1.0, "static", 0.0),
        (4, 1.0, 1.0, "approximate_ar1", 1.0),
        (4, 1.0, 1.0, "paper_exact", 0.0),
    ],
)
def test_rician_rejects_invalid_model_parameters(
    length: int, average_power: float, k_factor: float, mode: str, correlation: float
) -> None:
    with pytest.raises(ValueError):
        generate_rician_coefficients(
            length,
            average_power=average_power,
            k_factor=k_factor,
            rng=np.random.default_rng(0),
            mode=mode,
            correlation=correlation,
        )
