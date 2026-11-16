"""M4.2 infrastructure for a normalized finite-state Bayes recursion."""

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.posterior import (
    ALLOWED_HYPOTHESIS_TRANSITIONS,
    build_allowed_transition_matrix,
    posterior_update,
)


def _explicit_fixture_transition() -> np.ndarray:
    """Synthetic test fixture: each row selects its first structurally allowed edge."""
    transition = np.zeros((16, 16), dtype=np.float64)
    for row, allowed in enumerate(ALLOWED_HYPOTHESIS_TRANSITIONS):
        transition[row, int(np.flatnonzero(allowed)[0])] = 1.0
    return transition


def _transition_with_negative_entry() -> np.ndarray:
    transition = _explicit_fixture_transition()
    transition[0, 0] = -0.1
    transition[0, 1] += 1.1
    return transition


def _transition_with_non_finite_entry() -> np.ndarray:
    transition = _explicit_fixture_transition()
    transition[0, 0] = np.nan
    return transition


def test_allowed_transition_matrix_is_binary_and_matches_m41_hypotheses() -> None:
    allowed = build_allowed_transition_matrix()

    assert allowed.shape == (16, 16)
    assert np.array_equal(allowed, ALLOWED_HYPOTHESIS_TRANSITIONS)
    assert set(np.unique(allowed)) <= {0, 1}
    for row, current in enumerate(HYPOTHESES):
        expected = [current.next_state == following.current_state for following in HYPOTHESES]
        assert allowed[row].tolist() == expected
        assert int(np.sum(allowed[row])) == 4


def test_posterior_update_matches_hand_calculated_two_hypothesis_case() -> None:
    prior = np.zeros(16)
    prior[0] = 1.0
    transition = _explicit_fixture_transition()
    transition[0] = 0.0
    transition[0, :4] = (0.1, 0.2, 0.3, 0.4)
    likelihood = np.ones(16)
    likelihood[:4] = (2.0, 1.0, 0.0, 0.0)

    posterior = posterior_update(prior, transition, likelihood)

    expected = np.zeros(16)
    expected[:2] = (0.5, 0.5)
    np.testing.assert_allclose(posterior, expected)
    assert posterior.sum() == pytest.approx(1.0)


def test_posterior_update_accepts_zero_probabilities_and_preserves_support() -> None:
    prior = np.zeros(16)
    prior[0] = 1.0
    transition = _explicit_fixture_transition()
    likelihood = np.zeros(16)
    likelihood[0] = 1.0

    posterior = posterior_update(prior, transition, likelihood)

    expected = np.zeros(16)
    expected[0] = 1.0
    np.testing.assert_array_equal(posterior, expected)


def test_posterior_update_is_stable_for_extreme_likelihood_scales() -> None:
    prior = np.zeros(16)
    prior[0] = 1.0
    transition = _explicit_fixture_transition()
    transition[0] = 0.0
    transition[0, :4] = (0.1, 0.2, 0.3, 0.4)
    likelihood = np.ones(16)
    likelihood[:4] = (1e300, 2e300, 3e300, 4e300)

    posterior = posterior_update(prior, transition, likelihood)

    np.testing.assert_allclose(posterior[:4], (1 / 30, 2 / 15, 0.3, 8 / 15))
    assert np.all(np.isfinite(posterior))
    assert posterior.sum() == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("prior", "transition", "likelihood", "message"),
    [
        (np.full(16, 1 / 15), _explicit_fixture_transition(), np.ones(16), "sum to 1"),
        (
            np.r_[-0.1, np.full(15, 1.1 / 15)],
            _explicit_fixture_transition(),
            np.ones(16),
            "non-negative",
        ),
        (np.full(16, 1 / 16), np.eye(15), np.ones(16), "shape"),
        (np.full(16, 1 / 16), np.full((16, 16), 1 / 16), np.ones(16), "forbidden"),
        (np.full(16, 1 / 16), _transition_with_negative_entry(), np.ones(16), "non-negative"),
        (np.full(16, 1 / 16), _transition_with_non_finite_entry(), np.ones(16), "finite"),
        (np.full(16, 1 / 16), np.zeros((16, 16)), np.ones(16), "row-stochastic"),
        (np.full(16, 1 / 16), _explicit_fixture_transition() * 0.5, np.ones(16), "row-stochastic"),
        (np.full(16, 1 / 16), _explicit_fixture_transition(), np.full(16, -1.0), "non-negative"),
        (np.full(16, 1 / 16), _explicit_fixture_transition(), np.zeros(16), "zero evidence"),
    ],
)
def test_posterior_update_rejects_invalid_models(
    prior: np.ndarray,
    transition: np.ndarray,
    likelihood: np.ndarray,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        posterior_update(prior, transition, likelihood)


def test_posterior_update_requires_all_model_inputs_explicitly() -> None:
    with pytest.raises(TypeError):
        posterior_update()  # type: ignore[call-arg]
