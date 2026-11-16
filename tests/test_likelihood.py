"""M4.3b tests for the isolated [B](7) log-likelihood component."""

import numpy as np
import pytest

from hf_tcm.coding.likelihood import log_likelihood_component


def test_log_likelihood_component_matches_manual_sum_of_quadrature_norms() -> None:
    result = log_likelihood_component(
        np.array([3.0, 0.0]),
        np.array([4.0, 2.0]),
        coefficient_c=0.5,
    )

    assert result == pytest.approx(3.5)


def test_log_likelihood_component_allows_zero_coefficient() -> None:
    assert log_likelihood_component([3.0, 4.0], [4.0, 3.0], coefficient_c=0.0) == 0.0


def test_log_likelihood_component_preserves_positive_coefficient_sign() -> None:
    assert log_likelihood_component([3.0], [4.0], coefficient_c=2.0) == pytest.approx(10.0)


def test_log_likelihood_component_preserves_negative_coefficient_sign() -> None:
    assert log_likelihood_component([3.0], [4.0], coefficient_c=-2.0) == pytest.approx(-10.0)


def test_log_likelihood_component_returns_zero_for_zero_residuals() -> None:
    assert log_likelihood_component([0.0, 0.0], [0.0, 0.0], coefficient_c=-9.0) == 0.0


def test_log_likelihood_component_is_stable_for_many_samples() -> None:
    residual_i = np.full(250_000, 3.0)
    residual_q = np.full(250_000, 4.0)

    result = log_likelihood_component(residual_i, residual_q, coefficient_c=0.001)

    assert result == pytest.approx(1250.0)


def test_log_likelihood_component_uses_stable_quadrature_norm() -> None:
    result = log_likelihood_component([1e308], [1e308], coefficient_c=0.5)

    assert np.isfinite(result)
    assert result == pytest.approx(np.hypot(1e308, 1e308) * 0.5)


@pytest.mark.parametrize(
    ("residual_i", "residual_q", "coefficient_c", "message"),
    [
        ([1.0], [1.0, 2.0], 1.0, "same shape"),
        ([[1.0]], [[1.0]], 1.0, "one-dimensional"),
        ([], [], 1.0, "at least one sample"),
        ([float("nan")], [0.0], 1.0, "finite"),
        ([0.0], [float("inf")], 1.0, "finite"),
        ([0.0], [0.0], float("nan"), "finite"),
        ([0.0], [0.0], float("inf"), "finite"),
    ],
)
def test_log_likelihood_component_rejects_invalid_inputs(
    residual_i: object,
    residual_q: object,
    coefficient_c: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        log_likelihood_component(residual_i, residual_q, coefficient_c=coefficient_c)  # type: ignore[arg-type]
