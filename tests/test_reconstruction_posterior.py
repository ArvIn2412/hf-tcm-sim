"""Independent oracles for the isolated reconstruction posterior adapters."""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.posterior import ALLOWED_HYPOTHESIS_TRANSITIONS, posterior_update


def test_uniform_transition_probabilities_preserve_structural_order_and_support() -> None:
    from hf_tcm.receiver.reconstruction_posterior import build_reconstruction_transition_matrix

    probabilities = build_reconstruction_transition_matrix()
    assert probabilities.shape == (16, 16)
    assert [h.hypothesis_id for h in HYPOTHESES] == list(range(16))
    expected_support = np.array(
        [
            [previous.next_state == following.current_state for following in HYPOTHESES]
            for previous in HYPOTHESES
        ],
        dtype=bool,
    )
    np.testing.assert_array_equal(expected_support, ALLOWED_HYPOTHESIS_TRANSITIONS)
    np.testing.assert_array_equal(probabilities > 0.0, expected_support)
    np.testing.assert_array_equal(probabilities[~expected_support], 0.0)
    degrees = expected_support.sum(axis=1)
    np.testing.assert_array_equal(degrees, np.full(16, 4))
    np.testing.assert_allclose(probabilities.sum(axis=1), np.ones(16), atol=0.0)
    for row, degree in enumerate(degrees):
        np.testing.assert_allclose(probabilities[row, expected_support[row]], 1.0 / degree)
    assert not probabilities.flags.writeable


def test_initial_prior_is_uniform_only_on_edges_with_current_state_zero_zero() -> None:
    from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior

    prior = build_initial_reconstruction_prior(initial_state=(0, 0))
    expected_support = np.array([h.current_state == (0, 0) for h in HYPOTHESES])
    assert prior.shape == (16,)
    assert int(np.count_nonzero(prior)) == 4
    np.testing.assert_array_equal(prior[expected_support], np.full(4, 0.25))
    np.testing.assert_array_equal(prior[~expected_support], np.zeros(12))
    assert not prior.flags.writeable


def test_first_observation_update_does_not_apply_a_transition() -> None:
    from hf_tcm.receiver.reconstruction_posterior import (
        build_initial_reconstruction_prior,
        initial_reconstruction_observation_update,
    )

    initial_prior = build_initial_reconstruction_prior(initial_state=(0, 0))
    metrics = np.full(16, 40.0)
    metrics[:4] = [3.0, 2.0, 1.0, 0.0]
    likelihood = np.exp(-(metrics[:4] - metrics[:4].min()))
    expected = np.zeros(16)
    expected[:4] = likelihood / likelihood.sum()
    posterior = initial_reconstruction_observation_update(
        prior=initial_prior,
        candidate_metrics=metrics,
        beta=1.0,
    )
    np.testing.assert_allclose(posterior, expected, rtol=1e-14, atol=1e-15)
    np.testing.assert_array_equal(posterior[4:], 0.0)


def test_zero_metrics_yield_equal_likelihood_and_beta_changes_relative_weights() -> None:
    from hf_tcm.receiver.reconstruction_posterior import reconstruction_likelihood

    np.testing.assert_array_equal(reconstruction_likelihood(np.zeros(16), beta=2.0), np.ones(16))
    metrics = np.arange(16, dtype=np.float64)
    likelihood_1 = reconstruction_likelihood(metrics, beta=1.0)
    likelihood_2 = reconstruction_likelihood(metrics, beta=2.0)
    assert likelihood_1[0] == likelihood_2[0] == 1.0
    assert likelihood_1[1] > likelihood_1[2]
    assert likelihood_2[1] < likelihood_1[1]
    np.testing.assert_array_equal(
        reconstruction_likelihood(np.full(16, 3.25), beta=0.7), np.ones(16)
    )


def test_large_metrics_use_shared_log_shift_without_all_zero_likelihood() -> None:
    from hf_tcm.receiver.reconstruction_posterior import reconstruction_likelihood

    metrics = np.array([1e300 + index * 1e285 for index in range(16)])
    likelihood = reconstruction_likelihood(metrics, beta=1.0)
    assert likelihood[0] == 1.0
    assert np.all(np.isfinite(likelihood))
    assert np.all(likelihood >= 0.0)
    assert np.count_nonzero(likelihood) >= 1


def test_large_metrics_on_reachable_support_keep_nonzero_evidence() -> None:
    from hf_tcm.receiver.reconstruction_posterior import (
        build_initial_reconstruction_prior,
        transition_reconstruction_posterior,
    )

    prior = build_initial_reconstruction_prior(initial_state=(0, 0))
    metrics = np.full(16, 1e300)
    metrics[4] = 0.0  # unreachable from the initial edge distribution
    metrics[8] += 1e285
    posterior = transition_reconstruction_posterior(prior, metrics, beta=1.0)
    assert np.isfinite(posterior).all()
    assert np.isclose(posterior.sum(), 1.0)
    assert posterior[0] > 0.0
    assert posterior[4] == 0.0


def test_transition_posterior_uses_coding_posterior_and_normalizes_zero_cells() -> None:
    from hf_tcm.receiver.reconstruction_posterior import (
        build_initial_reconstruction_prior,
        reconstruction_likelihood,
        transition_reconstruction_posterior,
    )

    prior = build_initial_reconstruction_prior(initial_state=(0, 0))
    metrics = np.linspace(0.0, 4.0, 16)
    got = transition_reconstruction_posterior(prior, metrics, beta=0.8)
    expected = posterior_update(
        initial_distribution=prior,
        transition_matrix=_manual_transition_matrix(),
        likelihoods=reconstruction_likelihood(metrics, beta=0.8),
    )
    np.testing.assert_allclose(got, expected, rtol=1e-14, atol=1e-15)
    assert np.all(got[4:8] == 0.0)
    assert np.all(got[12:16] == 0.0)
    assert np.isclose(got.sum(), 1.0)


def test_manual_two_observation_recursion_has_no_first_edge_shift() -> None:
    from hf_tcm.receiver.reconstruction_posterior import (
        build_initial_reconstruction_prior,
        initial_reconstruction_observation_update,
        reconstruction_likelihood,
        transition_reconstruction_posterior,
    )

    initial = build_initial_reconstruction_prior(initial_state=(0, 0))
    first_metrics = np.full(16, 30.0)
    first_metrics[:4] = [3.0, 2.0, 1.0, 0.0]
    first_likelihood = np.exp(-(first_metrics[:4] - first_metrics[:4].min()))
    first_expected = np.zeros(16)
    first_expected[:4] = first_likelihood / first_likelihood.sum()
    after_first = initial_reconstruction_observation_update(
        prior=initial,
        candidate_metrics=first_metrics,
        beta=1.0,
    )
    np.testing.assert_allclose(after_first, first_expected)

    second_metrics = np.full(16, 20.0)
    second_metrics[10] = 0.0
    second_metrics[0] = 1.0
    transition = _manual_transition_matrix()
    predictive = first_expected @ transition
    second_likelihood = reconstruction_likelihood(second_metrics, beta=0.5)
    unnormalized = predictive * second_likelihood
    second_expected = unnormalized / unnormalized.sum()
    after_second = transition_reconstruction_posterior(
        after_first,
        second_metrics,
        beta=0.5,
    )
    np.testing.assert_allclose(after_second, second_expected, rtol=1e-14, atol=1e-15)
    assert after_second[10] > after_second[8]
    assert after_second[0] > 0.0
    assert np.isclose(after_second.sum(), 1.0)


def test_permutation_consistency_of_transition_posterior() -> None:
    from hf_tcm.receiver.reconstruction_posterior import (
        build_initial_reconstruction_prior,
        build_reconstruction_transition_matrix,
        transition_reconstruction_posterior,
    )

    prior = build_initial_reconstruction_prior(initial_state=(0, 0))
    metrics = np.linspace(0.1, 5.0, 16)
    transition = build_reconstruction_transition_matrix()
    canonical = transition_reconstruction_posterior(prior, metrics, beta=0.4)
    permutation = np.array([7, 2, 13, 0, 15, 4, 9, 1, 12, 5, 10, 3, 14, 6, 8, 11])
    np.testing.assert_allclose(
        build_reconstruction_transition_matrix(hypothesis_order=permutation.tolist()),
        transition[np.ix_(permutation, permutation)],
    )
    permuted_prior = build_initial_reconstruction_prior(
        initial_state=(0, 0),
        hypothesis_order=permutation.tolist(),
    )
    np.testing.assert_array_equal(permuted_prior, prior[permutation])
    permuted = transition_reconstruction_posterior(
        prior[permutation],
        metrics[permutation],
        beta=0.4,
        hypothesis_order=permutation.tolist(),
    )
    np.testing.assert_allclose(permuted, canonical[permutation], rtol=1e-14, atol=1e-15)


@pytest.mark.parametrize("beta", [0.0, -1.0, float("nan"), float("inf"), True, 10**400])
def test_likelihood_rejects_invalid_beta(beta: object) -> None:
    from hf_tcm.receiver.reconstruction_posterior import reconstruction_likelihood

    with pytest.raises(ValueError, match="beta"):
        reconstruction_likelihood(np.zeros(16), beta=beta)


@pytest.mark.parametrize(
    "metrics",
    [
        np.zeros(15),
        np.full(16, np.nan),
        np.full(16, np.inf),
        np.full(16, -1.0),
        np.array([0] * 15 + [10**400], dtype=object),
    ],
)
def test_likelihood_rejects_invalid_metrics(metrics: np.ndarray) -> None:
    from hf_tcm.receiver.reconstruction_posterior import reconstruction_likelihood

    with pytest.raises(ValueError):
        reconstruction_likelihood(metrics, beta=1.0)


def test_initial_prior_rejects_non_adr004_initial_state() -> None:
    from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior

    with pytest.raises(ValueError, match="initial_state"):
        build_initial_reconstruction_prior(initial_state=(1, 0))


def test_reconstruction_probability_adapter_has_no_truth_or_bit_operands() -> None:
    from hf_tcm.receiver import reconstruction_posterior

    source = inspect.getsource(reconstruction_posterior)
    assert "ChannelTruth" not in source
    assert ".truth" not in source
    assert (
        "rng"
        not in inspect.signature(reconstruction_posterior.reconstruction_likelihood).parameters
    )


def _manual_transition_matrix() -> np.ndarray:
    """Independent hand construction from state equality, not adapter output."""
    result = np.zeros((16, 16), dtype=np.float64)
    for row, previous in enumerate(HYPOTHESES):
        destinations = [
            column
            for column, following in enumerate(HYPOTHESES)
            if previous.next_state == following.current_state
        ]
        for column in destinations:
            result[row, column] = 1.0 / len(destinations)
    return result
