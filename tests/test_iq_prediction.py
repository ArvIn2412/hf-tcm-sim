"""M4.5b tests for the literal [A](5) quadrature transform."""

import numpy as np
import pytest

from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index


def test_all_eight_indices_match_manual_values_from_equation_five() -> None:
    # Explicit test coefficients mu_1=2, mu_2=4; Delta_phi=pi/4.
    expected = np.array(
        [
            [0.0, 4.0],
            [-np.sqrt(2.0), 2.0 * np.sqrt(2.0)],
            [-2.0, 0.0],
            [-np.sqrt(2.0), -2.0 * np.sqrt(2.0)],
            [0.0, -4.0],
            [np.sqrt(2.0), -2.0 * np.sqrt(2.0)],
            [2.0, 0.0],
            [np.sqrt(2.0), 2.0 * np.sqrt(2.0)],
        ]
    )

    actual = iq_quadratures_from_index(np.arange(8), np.full(8, 2.0), np.full(8, 4.0))

    np.testing.assert_allclose(actual, expected, atol=1e-14)


@pytest.mark.parametrize(
    ("b", "expected"),
    [
        (0, [0.0, 4.0]),
        (2, [-2.0, 0.0]),
        (4, [0.0, -4.0]),
        (6, [2.0, 0.0]),
    ],
)
def test_special_angles_preserve_the_printed_signs(b: int, expected: list[float]) -> None:
    np.testing.assert_allclose(iq_quadratures_from_index(b, 2.0, 4.0), expected, atol=1e-14)


def test_zero_coefficients_produce_zero_quadratures_for_every_index() -> None:
    actual = iq_quadratures_from_index(np.arange(8), np.zeros(8), np.zeros(8))

    np.testing.assert_array_equal(actual, np.zeros((8, 2)))


def test_negative_coefficients_keep_the_literal_multipliers() -> None:
    actual = iq_quadratures_from_index(1, -2.0, -4.0)

    np.testing.assert_allclose(actual, [np.sqrt(2.0), -2.0 * np.sqrt(2.0)])


def test_multiple_beams_use_explicit_index_and_coefficient_per_beam() -> None:
    actual = iq_quadratures_from_index(
        np.array([1, 2, 7]),
        np.array([2.0, 1.0, -2.0]),
        np.array([4.0, 3.0, -6.0]),
    )

    expected = np.array(
        [
            [-np.sqrt(2.0), 2.0 * np.sqrt(2.0)],
            [-1.0, 0.0],
            [-np.sqrt(2.0), -3.0 * np.sqrt(2.0)],
        ]
    )
    np.testing.assert_allclose(actual, expected, atol=1e-14)


@pytest.mark.parametrize("invalid_b", [True, 1.0, -1, 8, "1"])
def test_rejects_non_integer_or_out_of_range_indices(invalid_b: object) -> None:
    with pytest.raises(ValueError, match="b"):
        iq_quadratures_from_index(invalid_b, 1.0, 1.0)


def test_rejects_invalid_index_array_type_and_dimensions() -> None:
    with pytest.raises(ValueError, match="b"):
        iq_quadratures_from_index(np.array([0.0, 1.0]), [1.0, 1.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="b"):
        iq_quadratures_from_index(np.zeros((1, 1), dtype=int), [[1.0]], [[1.0]])
    with pytest.raises(ValueError, match="b"):
        iq_quadratures_from_index(np.array([], dtype=int), np.array([]), np.array([]))


@pytest.mark.parametrize(
    ("mu1", "mu2"),
    [
        ([1.0, 2.0], [1.0]),
        ([1.0, 2.0], [1.0, 2.0, 3.0]),
        ([True, False], [1.0, 2.0]),
        (np.array([1.0, np.inf]), [1.0, 2.0]),
        (np.array([1.0 + 1.0j, 2.0 + 0.0j]), [1.0, 2.0]),
    ],
)
def test_rejects_invalid_coefficient_values_and_dimensions(mu1: object, mu2: object) -> None:
    with pytest.raises(ValueError, match="mu1|mu2"):
        iq_quadratures_from_index(np.array([0, 1]), mu1, mu2)


def test_single_index_requires_scalar_coefficients() -> None:
    with pytest.raises(ValueError, match="shape"):
        iq_quadratures_from_index(1, [2.0], 4.0)
