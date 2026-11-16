"""Tests for the source-derived fluctuating additive-noise process."""

import importlib
import importlib.util
import math

import numpy as np
import pytest


def _noise_api():
    module_name = "hf_tcm.channels.fluctuating_noise"
    assert importlib.util.find_spec(module_name) is not None, (
        "fluctuating-noise module is not implemented yet"
    )
    module = importlib.import_module(module_name)
    return module.fluctuating_noise_coefficients, module.generate_fluctuating_noise


@pytest.mark.parametrize("n", [1, 8, 64, 1000])
def test_coefficients_follow_article_equations(n: int) -> None:
    coefficients, _ = _noise_api()

    alpha, sigma = coefficients(n)

    expected_alpha = math.exp(-4.0 / n)
    expected_sigma = math.sqrt((2.0 / (n**2)) * (1.0 - math.exp(-8.0 / n)))
    assert alpha == pytest.approx(expected_alpha, rel=1e-14)
    assert sigma == pytest.approx(expected_sigma, rel=1e-14)


def test_recurrence_uses_independent_normal_innovations_for_both_quadratures() -> None:
    coefficients, generate = _noise_api()
    length = 7
    n = 8
    seed = 3521
    alpha, sigma = coefficients(n)

    in_phase, quadrature = generate(
        length,
        n=n,
        rng=np.random.default_rng(seed),
    )
    innovations = np.random.default_rng(seed)
    z_i = innovations.standard_normal(length - 1)
    z_q = innovations.standard_normal(length - 1)
    expected_i = np.zeros(length)
    expected_q = np.zeros(length)
    for index in range(1, length):
        expected_i[index] = alpha * expected_i[index - 1] + sigma * z_i[index - 1]
        expected_q[index] = alpha * expected_q[index - 1] + sigma * z_q[index - 1]

    np.testing.assert_allclose(in_phase, expected_i, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(quadrature, expected_q, rtol=0.0, atol=0.0)
    assert not np.array_equal(in_phase, quadrature)


def test_process_is_reproducible_for_equal_seeds() -> None:
    _, generate = _noise_api()

    first_i, first_q = generate(128, n=8, rng=np.random.default_rng(1947))
    second_i, second_q = generate(128, n=8, rng=np.random.default_rng(1947))

    np.testing.assert_array_equal(first_i, second_i)
    np.testing.assert_array_equal(first_q, second_q)


def test_initial_conditions_and_output_lengths_are_explicit() -> None:
    _, generate = _noise_api()

    in_phase, quadrature = generate(
        1,
        n=8,
        rng=np.random.default_rng(1),
        initial_i=1.25,
        initial_q=-2.5,
    )

    assert in_phase.shape == (1,)
    assert quadrature.shape == (1,)
    assert in_phase.dtype == np.float64
    assert quadrature.dtype == np.float64
    assert in_phase[0] == 1.25
    assert quadrature[0] == -2.5

    default_i, default_q = generate(9, n=8, rng=np.random.default_rng(2))
    assert default_i.shape == (9,)
    assert default_q.shape == (9,)
    assert default_i[0] == 0.0
    assert default_q[0] == 0.0


def test_large_n_coefficients_and_sequence_remain_numerically_stable() -> None:
    coefficients, generate = _noise_api()
    n = 10**12

    alpha, sigma = coefficients(n)
    in_phase, quadrature = generate(2048, n=n, rng=np.random.default_rng(91))

    assert math.isfinite(alpha)
    assert math.isfinite(sigma)
    assert 0.0 < sigma < 1e-17
    assert sigma == pytest.approx(4e-18, rel=1e-10)
    assert np.all(np.isfinite(in_phase))
    assert np.all(np.isfinite(quadrature))


@pytest.mark.parametrize("n", [0, -1, True, 1.5, 10**400])
def test_coefficient_function_rejects_invalid_or_unrepresentable_n(n: object) -> None:
    coefficients, _ = _noise_api()

    with pytest.raises(ValueError, match="n"):
        coefficients(n)


def test_generator_rejects_invalid_length_rng_and_initial_values() -> None:
    _, generate = _noise_api()

    with pytest.raises(ValueError, match="length"):
        generate(0, n=8, rng=np.random.default_rng(3))
    with pytest.raises(ValueError, match="Generator"):
        generate(3, n=8, rng=3)
    with pytest.raises(ValueError, match="initial_i"):
        generate(3, n=8, rng=np.random.default_rng(3), initial_i=float("nan"))
    with pytest.raises(ValueError, match="initial_q"):
        generate(3, n=8, rng=np.random.default_rng(3), initial_q=float("inf"))
