import inspect
import math

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.trellis import build_trellis
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
from hf_tcm.receiver.reconstruction_candidate_metrics import (
    generate_reconstruction_candidate_metrics,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
)
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_IQ_RULE,
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_WAVEFORM_RULE,
)


def operands(received: np.ndarray, state: ReconstructionEstimatorState, *, origin: int = 0):
    return {
        "received": received,
        "absolute_sample_indices": np.arange(origin, origin + received.size),
        "received_start_sample": origin,
        "symbol_origin_sample": origin,
        "target_symbol_index": 0,
        "state": state,
        "time_index": state.time_index,
        "profile": ADR012_PROFILE,
        "adr_profile": ADR012_PROFILE_ID,
        "path_count": 1,
        "path_delays_samples": (0,),
        "samples_per_symbol": 8,
        "iq_rule": ADR012_IQ_RULE,
        "waveform_rule": ADR012_WAVEFORM_RULE,
        "labeling_profile": ASSUMED_NATURAL_BINARY,
        "bit_order": OUTPUT_BIT_ORDER,
        "timebase_profile": APPROXIMATE_RECTANGULAR_8SPS,
        "symbol_to_sample_rule": RECTANGULAR_ZOH_RULE,
        "edge_policy": ZERO_PADDING,
    }


def manual_iq(bits: tuple[int, int, int], coefficients: np.ndarray) -> np.ndarray:
    b = bits[0] * 4 + bits[1] * 2 + bits[2]
    phase = b * math.pi / 4.0
    return np.array([-coefficients[0, 0] * math.sin(phase), coefficients[0, 1] * math.cos(phase)])


@pytest.mark.parametrize("amplitude", [0.75, 2.0])
def test_all_hypotheses_and_phases_match_independent_noiseless_metric(amplitude: float) -> None:
    state = ReconstructionEstimatorState(
        fluctuating_iq=np.array([[amplitude, amplitude]]),
        full_iq=np.array([[amplitude, amplitude]]),
        time_index=12,
    )
    selected = (1, 0, 1)
    b = selected[0] * 4 + selected[1] * 2 + selected[2]
    signal_iq = manual_iq(selected, state.full_iq)
    received = np.full(8, signal_iq[1] + 1j * -signal_iq[0], dtype=np.complex128)
    result = generate_reconstruction_candidate_metrics(**operands(received, state))

    expected_ids = tuple(h.hypothesis_id for h in HYPOTHESES)
    assert result.hypothesis_ids == expected_ids
    assert len(result.output_bits) == len(result.phase_indices) == 16
    assert set(result.phase_indices) == set(range(8))
    assert result.metrics.shape == (16,)
    assert result.sample_predictions_iq.shape == (16, 8, 2)
    assert not result.sample_predictions_iq.flags.writeable
    expected = []
    for hypothesis in HYPOTHESES:
        # Output bits are checked against the independent M1 trellis table.
        branch = next(
            item
            for item in build_trellis()
            if item.state == hypothesis.current_state and item.input_pair == hypothesis.input_bits
        )
        assert hypothesis.output_bits == branch.output
        predicted = manual_iq(hypothesis.output_bits, state.full_iq)
        expected.append(8.0 * float(np.sum((signal_iq - predicted) ** 2)))
    np.testing.assert_allclose(result.metrics, expected, rtol=0.0, atol=1e-14)
    assert np.count_nonzero(result.metrics == 0.0) >= 1
    for row, phase_index in enumerate(result.phase_indices):
        if phase_index == b:
            assert result.metrics[row] == 0.0
    assert result.target_symbol_index == 0
    assert result.sample_indices == tuple(range(8))
    assert result.estimator_time_index == 12
    assert result.prediction_cutoff_sample_index == -1
    assert result.metric_available_after_sample_index == 7
    assert result.profile_id == ADR012_PROFILE_ID
    assert b in result.phase_indices


def test_nonzero_sample_origin_and_target_symbol_select_exact_eight_samples() -> None:
    origin = 23
    symbol = 2
    first = origin + 8 * symbol
    values = np.array([complex(i, -2 * i) for i in range(8)], dtype=np.complex128)
    buffer = np.concatenate((np.array([90 + 90j] * 16), values, np.array([np.nan + 1j * np.nan])))
    state = ReconstructionEstimatorState(np.ones((1, 2)), np.ones((1, 2)), 5)
    args = operands(buffer, state, origin=origin)
    args["target_symbol_index"] = symbol
    result = generate_reconstruction_candidate_metrics(**args)
    assert result.sample_indices == tuple(range(first, first + 8))
    assert result.prediction_cutoff_sample_index == first - 1
    # A future NaN in the supplied buffer is not used by this symbol's metric.
    assert np.all(np.isfinite(result.metrics))


def test_sum_of_eight_sample_residuals_is_not_metric_of_the_mean() -> None:
    state = ReconstructionEstimatorState(np.zeros((1, 2)), np.ones((1, 2)), 0)
    received = np.array([complex(k, k * k) for k in range(8)], dtype=np.complex128)
    result = generate_reconstruction_candidate_metrics(**operands(received, state))
    bits = result.output_bits[0]
    predicted = manual_iq(bits, state.full_iq)
    observed = np.column_stack((-received.imag, received.real))
    expected_sum = float(np.sum((observed - predicted) ** 2))
    mean_metric = float(np.sum((observed.mean(axis=0) - predicted) ** 2))
    assert result.metrics[0] == pytest.approx(expected_sum)
    assert result.metrics[0] != pytest.approx(mean_metric)


def test_duplicate_output_bits_have_equal_metrics_and_hypothesis_permutation_is_equivariant() -> (
    None
):
    state = ReconstructionEstimatorState(np.ones((1, 2)), np.array([[0.8, 1.3]]), 9)
    received = np.array([1.4 + 0.2j] * 8)
    args = operands(received, state)
    canonical = generate_reconstruction_candidate_metrics(**args)
    for left in range(16):
        for right in range(left + 1, 16):
            if canonical.output_bits[left] == canonical.output_bits[right]:
                assert canonical.metrics[left] == canonical.metrics[right]
    permutation = tuple(reversed(canonical.hypothesis_ids))
    permuted = generate_reconstruction_candidate_metrics(**args, hypothesis_order=permutation)
    assert permuted.hypothesis_ids == permutation
    for index, hypothesis_id in enumerate(permutation):
        original = canonical.hypothesis_ids.index(hypothesis_id)
        assert permuted.output_bits[index] == canonical.output_bits[original]
        assert permuted.metrics[index] == canonical.metrics[original]


def test_inputs_are_unchanged_and_result_array_is_immutable() -> None:
    state = ReconstructionEstimatorState(np.ones((1, 2)), np.ones((1, 2)), 0)
    received = np.array([0.5 + 0.1j] * 8)
    received_before = received.copy()
    state_before = state.full_iq.copy()
    result = generate_reconstruction_candidate_metrics(**operands(received, state))
    np.testing.assert_array_equal(received, received_before)
    np.testing.assert_array_equal(state.full_iq, state_before)
    with pytest.raises(ValueError):
        result.metrics[0] = 10.0


@pytest.mark.parametrize(
    ("override", "message"),
    [
        (
            {
                "received": np.ones(7, dtype=np.complex128),
                "absolute_sample_indices": np.arange(7),
            },
            "complete target symbol",
        ),
        (
            {"absolute_sample_indices": np.array([0, 1, 2, 3, 4, 6, 5, 7])},
            "contiguous",
        ),
        ({"received": np.zeros((8, 1), dtype=np.complex128)}, "one-dimensional"),
        ({"path_count": 2}, "L=1"),
        ({"path_delays_samples": (1,)}, "zero-delay"),
        ({"profile": "source_faithful"}, "reconstructed_offline"),
        ({"iq_rule": "other"}, "iq_rule"),
        ({"samples_per_symbol": 4}, "8 samples"),
        ({"waveform_rule": "linear"}, "rectangular ZOH"),
        ({"timebase_profile": "other"}, "timebase_profile"),
        ({"received": np.array([0.0 + 0.0j] * 7 + [np.inf + 0.0j])}, "finite"),
    ],
)
def test_rejects_incomplete_or_unaccepted_operands(override, message: str) -> None:
    state = ReconstructionEstimatorState(np.ones((1, 2)), np.ones((1, 2)), 4)
    args = operands(np.zeros(8, dtype=np.complex128), state)
    args.update(override)
    with pytest.raises(ValueError, match=message):
        generate_reconstruction_candidate_metrics(**args)


def test_rejects_wrong_clock_and_hypothesis_order() -> None:
    state = ReconstructionEstimatorState(np.ones((1, 2)), np.ones((1, 2)), 4)
    args = operands(np.zeros(8, dtype=np.complex128), state)
    args["time_index"] = 5
    with pytest.raises(ValueError, match="state.time_index"):
        generate_reconstruction_candidate_metrics(**args)
    args = operands(np.zeros(8, dtype=np.complex128), state)
    with pytest.raises(ValueError, match="permutation"):
        generate_reconstruction_candidate_metrics(**args, hypothesis_order=(0,) * 16)
    wrong_beam_state = ReconstructionEstimatorState(np.ones((2, 2)), np.ones((2, 2)), 4)
    with pytest.raises(ValueError, match="L=1"):
        generate_reconstruction_candidate_metrics(
            **operands(np.zeros(8, dtype=np.complex128), wrong_beam_state)
        )


def test_api_has_no_truth_or_transmitted_symbol_inputs() -> None:
    parameters = inspect.signature(generate_reconstruction_candidate_metrics).parameters
    assert not {"truth", "channel_truth", "transmitted_bits", "phase_index"}.intersection(
        parameters
    )
