"""Independent deterministic source-equation and convention audit controls."""

import math

import numpy as np

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.paper_recursion import update_quadrature_estimates
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    hypothesis_to_phase_index,
)
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_IQ_RULE,
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_WAVEFORM_RULE,
    extract_adr012_observed_iq,
)
from hf_tcm.receiver.reconstruction_posterior import (
    initial_reconstruction_observation_update,
    transition_reconstruction_posterior,
)


def test_a5_eight_angles_with_unequal_coefficients_match_manual_table() -> None:
    # Direct scalar oracle for mu1=2, mu2=4; it does not call iq_prediction.
    root2 = math.sqrt(2.0)
    expected = np.array(
        [
            [0.0, 4.0],
            [-root2, 2.0 * root2],
            [-2.0, 0.0],
            [-root2, -2.0 * root2],
            [0.0, -4.0],
            [root2, -2.0 * root2],
            [2.0, 0.0],
            [root2, 2.0 * root2],
        ]
    )
    actual = iq_quadratures_from_index(np.arange(8), np.full(8, 2.0), np.full(8, 4.0))
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-14)


def test_a5_equal_zero_and_negative_coefficients_preserve_signs() -> None:
    # Unequal coefficients expose component-order swaps; equal/zero/negative
    # values verify that the formula applies each signed scalar literally.
    root2 = math.sqrt(2.0)
    expected_unequal = np.array([-3.0 * root2 / 2.0, 5.0 * root2 / 2.0])
    np.testing.assert_allclose(
        iq_quadratures_from_index(1, 3.0, 5.0), expected_unequal, rtol=0.0, atol=1e-14
    )
    np.testing.assert_allclose(
        iq_quadratures_from_index(1, -2.0, -2.0), [root2, -root2], rtol=0.0, atol=1e-14
    )
    np.testing.assert_array_equal(iq_quadratures_from_index(5, 0.0, -3.0), [0.0, 3.0 * root2 / 2])


def test_adr012_complex_mapping_matches_a5_under_selected_theta_convention() -> None:
    amplitude = 1.7
    for b in range(8):
        theta = b * math.pi / 4.0
        y = amplitude * complex(math.cos(theta), math.sin(theta))
        observed = (-y.imag, y.real)
        predicted_from_selected_theta = (
            -amplitude * math.sin(theta),
            amplitude * math.cos(theta),
        )
        np.testing.assert_allclose(observed, predicted_from_selected_theta, rtol=0.0, atol=1e-14)


def test_adr012_api_maps_all_eight_complex_phase_samples() -> None:
    amplitude = 1.7
    for b in range(8):
        theta = b * math.pi / 4.0
        symbol = amplitude * complex(math.cos(theta), math.sin(theta))
        actual = extract_adr012_observed_iq(
            np.full(8, symbol, dtype=np.complex128),
            absolute_sample_indices=np.arange(8),
            received_start_sample=0,
            symbol_origin_sample=0,
            target_symbol_index=0,
            profile=ADR012_PROFILE,
            adr_profile=ADR012_PROFILE_ID,
            path_count=1,
            path_delays_samples=(0,),
            samples_per_symbol=8,
            iq_rule=ADR012_IQ_RULE,
            waveform_rule=ADR012_WAVEFORM_RULE,
        )
        expected = [-amplitude * math.sin(theta), amplitude * math.cos(theta)]
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-14)


def test_adr012_extracts_negative_imaginary_then_real_sample_mean() -> None:
    samples = np.array([complex(2.0 + i, -3.0 + 2.0 * i) for i in range(8)])
    actual = extract_adr012_observed_iq(
        samples,
        absolute_sample_indices=np.arange(8),
        received_start_sample=0,
        symbol_origin_sample=0,
        target_symbol_index=0,
        profile=ADR012_PROFILE,
        adr_profile=ADR012_PROFILE_ID,
        path_count=1,
        path_delays_samples=(0,),
        samples_per_symbol=8,
        iq_rule=ADR012_IQ_RULE,
        waveform_rule=ADR012_WAVEFORM_RULE,
    )
    # Means computed from the literal complex buffer, independently.
    assert actual[0] == -4.0
    assert actual[1] == 5.5


def test_manual_one_step_a1_oracle_matches_explicit_project_operands() -> None:
    previous = [0.4, -0.3]
    alpha_prime = 0.6
    k_tilde = [0.25, -0.5]
    mu0 = [0.1, 0.2]
    observed = [1.2, -0.4]
    predicted = np.zeros((16, 2), dtype=np.float64)
    predicted[0] = [0.2, -0.3]
    predicted[1] = [0.6, 0.1]
    posterior = np.zeros(16, dtype=np.float64)
    posterior[0], posterior[1] = 0.25, 0.75

    # Hand scalar-loop calculation: sum p_h (Y-U_h) = (0.7,-0.4).
    innovation = [0.0, 0.0]
    for hypothesis in range(16):
        for component in range(2):
            innovation[component] += posterior[hypothesis] * (
                observed[component] - predicted[hypothesis, component]
            )
    assert innovation == [0.7, -0.4]
    expected_fluctuating = [
        alpha_prime * previous[j] + k_tilde[j] * innovation[j] for j in range(2)
    ]
    expected_full = [expected_fluctuating[j] + mu0[j] for j in range(2)]

    actual_fluctuating, actual_full = update_quadrature_estimates(
        previous_fluctuating=previous,
        alpha_prime=alpha_prime,
        k_tilde=k_tilde,
        posterior=posterior,
        observed_iq=observed,
        predicted_iq=predicted,
        mu0=mu0,
    )
    np.testing.assert_allclose(expected_fluctuating, [0.415, 0.02], rtol=0.0, atol=1e-15)
    np.testing.assert_allclose(expected_full, [0.515, 0.22], rtol=0.0, atol=1e-15)
    np.testing.assert_allclose(actual_fluctuating, expected_fluctuating, rtol=0.0, atol=1e-15)
    np.testing.assert_allclose(actual_full, expected_full, rtol=0.0, atol=1e-15)
    np.testing.assert_allclose(actual_full, actual_fluctuating + mu0, rtol=0.0, atol=0.0)


def test_weighted_residual_equals_observation_minus_weighted_prediction() -> None:
    posterior = np.array([index + 1 for index in range(16)], dtype=np.float64)
    posterior /= posterior.sum()
    observed = np.array([0.35, -0.8])
    predicted = np.array([[index / 10.0, (7 - index) / 13.0] for index in range(16)])

    # Independent scalar-loop forms of the two candidate identities.
    weighted_residual = [0.0, 0.0]
    weighted_prediction = [0.0, 0.0]
    for h in range(16):
        for j in range(2):
            weighted_residual[j] += posterior[h] * (observed[j] - predicted[h, j])
            weighted_prediction[j] += posterior[h] * predicted[h, j]
    second_form = [observed[j] - weighted_prediction[j] for j in range(2)]
    np.testing.assert_allclose(posterior.sum(), 1.0, rtol=0.0, atol=1e-15)
    np.testing.assert_allclose(weighted_residual, second_form, rtol=0.0, atol=1e-15)


def test_first_edge_uses_prior_without_transition_and_continuation_transitions_once() -> None:
    initial_prior = np.zeros(16, dtype=np.float64)
    initial_prior[:4] = 0.25
    first = initial_reconstruction_observation_update(
        prior=initial_prior, candidate_metrics=np.zeros(16), beta=0.7
    )
    np.testing.assert_allclose(first, initial_prior, rtol=0.0, atol=0.0)
    assert math.isclose(float(first.sum()), 1.0, rel_tol=0.0, abs_tol=1e-15)

    metrics = np.arange(16, dtype=np.float64)
    actual = transition_reconstruction_posterior(first, metrics, beta=0.7)
    # Independent structural oracle: the first-edge support comprises two
    # branches into state 00 and two into state 10; one transition therefore
    # predicts 1/8 on each of those states' four outgoing edges.
    transitioned_support = (0, 1, 2, 3, 8, 9, 10, 11)
    raw = [math.exp(-0.7 * float(metrics[index])) / 8.0 for index in transitioned_support]
    normalizer = sum(raw)
    expected = np.zeros(16, dtype=np.float64)
    for index, weight in zip(transitioned_support, raw, strict=True):
        expected[index] = weight / normalizer
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-15)
    assert math.isclose(float(actual.sum()), 1.0, rel_tol=0.0, abs_tol=1e-15)


def test_canonical_sixteen_edge_and_project_phase_mapping_is_explicit() -> None:
    # Literal project M1 state/input enumeration and (c2,c1,c0) outputs.
    expected = [
        ((0, 0), (0, 0), (0, 0, 0), (0, 0), 0),
        ((0, 0), (0, 1), (0, 1, 0), (1, 0), 2),
        ((0, 0), (1, 0), (1, 0, 0), (0, 0), 4),
        ((0, 0), (1, 1), (1, 1, 0), (1, 0), 6),
        ((0, 1), (0, 0), (0, 1, 0), (0, 0), 2),
        ((0, 1), (0, 1), (0, 0, 0), (1, 0), 0),
        ((0, 1), (1, 0), (1, 1, 0), (0, 0), 6),
        ((0, 1), (1, 1), (1, 0, 0), (1, 0), 4),
        ((1, 0), (0, 0), (0, 0, 1), (0, 1), 1),
        ((1, 0), (0, 1), (0, 1, 1), (1, 1), 3),
        ((1, 0), (1, 0), (1, 0, 1), (0, 1), 5),
        ((1, 0), (1, 1), (1, 1, 1), (1, 1), 7),
        ((1, 1), (0, 0), (0, 1, 1), (0, 1), 3),
        ((1, 1), (0, 1), (0, 0, 1), (1, 1), 1),
        ((1, 1), (1, 0), (1, 1, 1), (0, 1), 7),
        ((1, 1), (1, 1), (1, 0, 1), (1, 1), 5),
    ]
    observed = [
        (
            hypothesis.current_state,
            hypothesis.input_bits,
            hypothesis.output_bits,
            hypothesis.next_state,
            hypothesis_to_phase_index(
                hypothesis, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
            ),
        )
        for hypothesis in HYPOTHESES
    ]
    assert [item.hypothesis_id for item in HYPOTHESES] == list(range(16))
    assert observed == expected
