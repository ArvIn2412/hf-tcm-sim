"""M4.4: isolated algebraic recursion kernel for quadrature estimates."""

import numpy as np
import pytest

from hf_tcm.receiver.paper_recursion import update_quadrature_estimates


def test_single_beam_matches_manual_posterior_weighted_recursion() -> None:
    fluctuating, full = update_quadrature_estimates(
        previous_fluctuating=[1.0, 2.0],
        alpha_prime=0.5,
        k_tilde=[2.0, -1.0],
        posterior=[0.25, 0.75],
        observed_iq=[10.0, 20.0],
        predicted_iq=[[8.0, 24.0], [6.0, 16.0]],
        mu0=[0.5, 3.0],
    )

    np.testing.assert_allclose(fluctuating, [7.5, -1.0])
    np.testing.assert_allclose(full, [8.0, 2.0])


def test_multiple_beams_use_independent_iq_and_posterior_rows() -> None:
    fluctuating, full = update_quadrature_estimates(
        previous_fluctuating=[[1.0, 2.0], [-1.0, 4.0]],
        alpha_prime=0.5,
        k_tilde=[[1.0, 2.0], [3.0, 4.0]],
        posterior=[[1.0, 0.0], [0.5, 0.5]],
        observed_iq=[[5.0, 7.0], [10.0, 20.0]],
        predicted_iq=[[[4.0, 9.0], [6.0, 5.0]], [[8.0, 18.0], [12.0, 22.0]]],
        mu0=[[0.0, 0.0], [0.2, -0.5]],
    )

    np.testing.assert_allclose(fluctuating, [[1.5, -3.0], [-0.5, 2.0]])
    np.testing.assert_allclose(full, [[1.5, -3.0], [-0.3, 1.5]])


def test_posterior_weights_must_be_normalized_per_beam() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        update_quadrature_estimates(
            previous_fluctuating=[[0.0, 0.0], [0.0, 0.0]],
            alpha_prime=1.0,
            k_tilde=[[1.0, 1.0], [1.0, 1.0]],
            posterior=[[0.5, 0.5], [0.2, 0.2]],
            observed_iq=[[0.0, 0.0], [0.0, 0.0]],
            predicted_iq=[[[0.0, 0.0], [1.0, 1.0]], [[0.0, 0.0], [1.0, 1.0]]],
            mu0=[[0.0, 0.0], [0.0, 0.0]],
        )


def test_zero_k_tilde_keeps_only_previous_fluctuating_component() -> None:
    fluctuating, full = update_quadrature_estimates(
        previous_fluctuating=[2.0, -4.0],
        alpha_prime=0.25,
        k_tilde=[0.0, 0.0],
        posterior=[0.4, 0.6],
        observed_iq=[7.0, 9.0],
        predicted_iq=[[1.0, 2.0], [3.0, 4.0]],
        mu0=[0.5, 1.5],
    )

    np.testing.assert_allclose(fluctuating, [0.5, -1.0])
    np.testing.assert_allclose(full, [1.0, 0.5])


def test_zero_residuals_add_no_innovation() -> None:
    fluctuating, full = update_quadrature_estimates(
        previous_fluctuating=[1.0, 2.0],
        alpha_prime=0.5,
        k_tilde=[3.0, -2.0],
        posterior=[0.3, 0.7],
        observed_iq=[5.0, 6.0],
        predicted_iq=[[5.0, 6.0], [5.0, 6.0]],
        mu0=[-1.0, 4.0],
    )

    np.testing.assert_allclose(fluctuating, [0.5, 1.0])
    np.testing.assert_allclose(full, [-0.5, 5.0])


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"previous_fluctuating": [1.0]}, "previous_fluctuating"),
        ({"k_tilde": [1.0]}, "k_tilde"),
        ({"posterior": [[0.5, 0.5]]}, "posterior"),
        ({"observed_iq": [1.0]}, "observed_iq"),
        ({"predicted_iq": [[1.0, 2.0]]}, "predicted_iq"),
        ({"mu0": [1.0]}, "mu0"),
    ],
)
def test_rejects_invalid_iq_and_hypothesis_dimensions(
    overrides: dict[str, object], message: str
) -> None:
    parameters: dict[str, object] = {
        "previous_fluctuating": [0.0, 0.0],
        "alpha_prime": 1.0,
        "k_tilde": [1.0, 1.0],
        "posterior": [0.5, 0.5],
        "observed_iq": [0.0, 0.0],
        "predicted_iq": [[1.0, 1.0], [2.0, 2.0]],
        "mu0": [0.0, 0.0],
    }
    parameters.update(overrides)

    with pytest.raises(ValueError, match=message):
        update_quadrature_estimates(**parameters)  # type: ignore[arg-type]


def test_rejects_non_finite_estimates_and_posterior() -> None:
    with pytest.raises(ValueError, match="finite"):
        update_quadrature_estimates(
            previous_fluctuating=[0.0, float("inf")],
            alpha_prime=1.0,
            k_tilde=[1.0, 1.0],
            posterior=[0.5, 0.5],
            observed_iq=[0.0, 0.0],
            predicted_iq=[[0.0, 0.0], [0.0, 0.0]],
            mu0=[0.0, 0.0],
        )
