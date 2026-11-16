from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.evaluation.reconstruction_causal_trace import (
    compare_reconstruction_causal_traces,
    run_reconstruction_causal_trace_pair,
    summarize_reconstruction_causal_trace_pair,
)
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import combine_iq, symbols_to_iq_waveform
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState


def _received(count: int) -> np.ndarray:
    # Literal, deterministic complex fixture. No RNG, reference bits, or channel-truth input.
    sample = np.arange(8 * count, dtype=np.float64)
    return (0.11 + 0.003 * sample) + 1j * (-0.07 + 0.002 * sample)


def _trace(count: int = 6, *, partition: tuple[int, ...] | None = None):
    received = _received(count)
    labels = np.arange(103, 103 + received.size, dtype=np.int64)
    state = ReconstructionEstimatorState([[0.42, 0.91]], [[0.42, 0.91]], 41)
    result = run_reconstruction_causal_trace_pair(
        received=received,
        absolute_sample_indices=labels,
        received_start_sample=103,
        symbol_origin_sample=63,
        first_symbol_index=5,
        initial_estimator_time_index=41,
        initial_state=state,
        beta=0.7,
        sequence_id="deterministic-fixture",
        adaptive_alpha_prime=0.85,
        adaptive_k_tilde=np.asarray([[0.35, -0.2]]),
        adaptive_mu0=np.zeros((1, 2)),
        segment_partition=partition,
    )
    return received, result


def test_trace_copies_actual_b4d_rows_and_separates_clocks_and_cutoffs() -> None:
    _, result = _trace(4)
    assert result.frozen.sequence_id == result.adaptive.sequence_id
    assert len(result.frozen.history) == len(result.adaptive.history) == 4
    for offset, (frozen, adaptive) in enumerate(
        zip(result.frozen.history, result.adaptive.history, strict=True)
    ):
        symbol = 5 + offset
        assert frozen.absolute_symbol_index == adaptive.absolute_symbol_index == symbol
        assert frozen.estimator_time_index == adaptive.estimator_time_index == 41 + offset
        assert (
            frozen.sample_window
            == adaptive.sample_window
            == tuple(range(63 + 8 * symbol, 71 + 8 * symbol))
        )
        assert frozen.prediction_cutoff_sample_index == 63 + 8 * symbol - 1
        assert frozen.observation_cutoff_sample_index == 63 + 8 * symbol + 7
        assert frozen.edge_mode == ("first_edge" if offset == 0 else "later_edge")
        assert (
            frozen.hypothesis_ids
            == tuple(range(16))
            == tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)
        )
        assert frozen.posterior_input_kind == (
            "adr004_initial_prior" if offset == 0 else "previous_posterior"
        )
        assert frozen.posterior_sum == pytest.approx(1.0, abs=1e-12)
        assert frozen.posterior_normalized
        assert frozen.predicted_iq.shape == (16, 2)
        assert frozen.sample_predictions_iq.shape == (16, 8, 2)
        assert frozen.candidate_metrics.shape == (16,)


def test_manual_a1_oracle_state_decomposition_and_frozen_invariance() -> None:
    _, result = _trace(2)
    frozen, adaptive = result.frozen, result.adaptive
    for row in frozen.history:
        np.testing.assert_array_equal(row.pre_state.full_iq, frozen.initial_state.full_iq)
        np.testing.assert_array_equal(row.post_state.full_iq, frozen.initial_state.full_iq)
    row = adaptive.history[0]
    posterior_weighted_innovation = np.sum(
        row.posterior[:, None] * (row.observed_iq[None, :] - row.predicted_iq), axis=0
    )
    expected = (
        0.85 * row.pre_state.fluctuating_iq[0]
        + np.asarray([0.35, -0.2]) * posterior_weighted_innovation
    )
    np.testing.assert_allclose(row.post_state.fluctuating_iq[0], expected, rtol=0, atol=1e-13)
    np.testing.assert_allclose(
        row.post_state.full_iq,
        row.post_state.fluctuating_iq + row.mu0,
        rtol=0,
        atol=1e-13,
    )
    assert np.linalg.norm(row.fluctuating_increment) > 0


def test_independent_first_edge_and_continuation_posterior_oracle() -> None:
    _, result = _trace(2)
    rows = result.adaptive.history
    first = rows[0]
    initial_support = np.asarray(
        [hypothesis.current_state == (0, 0) for hypothesis in HYPOTHESES], dtype=bool
    )
    prior = np.zeros(16, dtype=np.float64)
    prior[initial_support] = 0.25
    first_likelihood = np.exp(-0.7 * (first.candidate_metrics - first.candidate_metrics.min()))
    first_oracle = prior * first_likelihood
    first_oracle /= first_oracle.sum()
    np.testing.assert_allclose(first.posterior, first_oracle, rtol=0, atol=1e-13)

    continuation = rows[1]
    transition = np.zeros((16, 16), dtype=np.float64)
    for previous_id, previous in enumerate(HYPOTHESES):
        successors = [
            index
            for index, following in enumerate(HYPOTHESES)
            if following.current_state == previous.next_state
        ]
        for successor in successors:
            transition[previous_id, successor] = 1.0 / len(successors)
    predicted = first_oracle @ transition
    likelihood = np.exp(
        -0.7 * (continuation.candidate_metrics - continuation.candidate_metrics.min())
    )
    continuation_oracle = predicted * likelihood
    continuation_oracle /= continuation_oracle.sum()
    np.testing.assert_allclose(continuation.posterior, continuation_oracle, rtol=0, atol=1e-13)
    assert continuation.posterior_transition_provenance == (
        "adr003_transition_then_current_metric_likelihood"
    )
    assert continuation.transition_predicted_posterior is None


def test_trace_comparison_reports_first_state_and_metric_divergence() -> None:
    _, result = _trace(6)
    comparison = compare_reconstruction_causal_traces(result, rtol=1e-12, atol=1e-14)
    assert comparison.first_estimator_state_divergence_symbol == 5
    assert comparison.first_candidate_metric_divergence_symbol == 6
    assert comparison.received_sha256_equal
    assert comparison.initial_state_equal
    assert comparison.posterior_differing_symbols == (6, 7, 8, 9, 10)
    assert comparison.decoded_edge_differing_symbols == (9, 10)


def test_compact_trace_summary_reports_updates_metrics_and_final_decode() -> None:
    _, pair = _trace(6)
    summary = summarize_reconstruction_causal_trace_pair(pair, rtol=1e-12, atol=1e-14)
    assert summary["first_estimator_state_divergence_symbol"] == 5
    assert summary["first_candidate_metric_divergence_symbol"] == 6
    rows = summary["per_symbol"]
    assert len(rows) == 6
    assert rows[0]["frozen_metric_row_equal"] is True
    assert rows[0]["adaptive_update_norm"] > 0.0
    assert rows[0]["adaptive_posterior_sum"] == pytest.approx(1.0)
    assert summary["adaptive_final"]["decoded_path_valid"] is True


def test_current_update_cannot_change_current_frozen_metric_row() -> None:
    _, pair = _trace(2)
    np.testing.assert_array_equal(
        pair.frozen.history[0].candidate_metrics,
        pair.adaptive.history[0].candidate_metrics,
    )
    assert pair.frozen.history[0].post_state.time_index == 42
    assert pair.adaptive.history[0].post_state.time_index == 42
    assert pair.frozen.history[1].pre_state.time_index == 42
    assert pair.adaptive.history[1].pre_state.time_index == 42
    assert not np.allclose(
        pair.frozen.history[1].candidate_metrics,
        pair.adaptive.history[1].candidate_metrics,
        rtol=1e-12,
        atol=1e-14,
    )


def test_candidate_prediction_is_independently_rebuilt_from_pre_state() -> None:
    _, pair = _trace(1)
    row = pair.adaptive.history[0]
    phase_angle = np.asarray(row.phase_indices, dtype=np.float64) * np.pi / 4.0
    expected = np.column_stack(
        (
            -row.pre_state.full_iq[0, 0] * np.sin(phase_angle),
            row.pre_state.full_iq[0, 1] * np.cos(phase_angle),
        )
    )
    np.testing.assert_allclose(row.predicted_iq, expected, rtol=0, atol=1e-14)
    np.testing.assert_allclose(
        row.sample_predictions_iq,
        np.repeat(expected[:, None, :], 8, axis=1),
        rtol=1e-14,
        atol=1e-14,
    )


def test_future_samples_cannot_change_an_earlier_completed_trace_row() -> None:
    first_received, first_pair = _trace(2)
    changed_future = first_received.copy()
    changed_future[8:] += np.asarray([0.3 - 0.1j] * 8)
    state = ReconstructionEstimatorState([[0.42, 0.91]], [[0.42, 0.91]], 41)
    changed_pair = run_reconstruction_causal_trace_pair(
        received=changed_future,
        absolute_sample_indices=np.arange(103, 119, dtype=np.int64),
        received_start_sample=103,
        symbol_origin_sample=63,
        first_symbol_index=5,
        initial_estimator_time_index=41,
        initial_state=state,
        beta=0.7,
        sequence_id="future-change",
        adaptive_alpha_prime=0.85,
        adaptive_k_tilde=[[0.35, -0.2]],
        adaptive_mu0=[[0.0, 0.0]],
    )
    for original, changed in (
        (first_pair.frozen.history[0], changed_pair.frozen.history[0]),
        (first_pair.adaptive.history[0], changed_pair.adaptive.history[0]),
    ):
        np.testing.assert_array_equal(original.candidate_metrics, changed.candidate_metrics)
        np.testing.assert_array_equal(original.posterior, changed.posterior)
        np.testing.assert_array_equal(original.post_state.full_iq, changed.post_state.full_iq)


@pytest.mark.parametrize("count", [1, 2, 4, 6])
@pytest.mark.parametrize("gain", [0.75, 2.0])
def test_deterministic_noiseless_real_gain_fixtures(count: int, gain: float) -> None:
    labels_8psk = [((index >> 2) & 1, (index >> 1) & 1, index & 1) for index in range(count)]
    in_phase, quadrature = symbols_to_iq_waveform(np.asarray(modulate(labels_8psk)))
    received = gain * combine_iq(in_phase, quadrature)
    if count >= 2:
        received = received.copy()
        received[9] += 0.012 - 0.006j  # explicit deterministic complex perturbation
    first_symbol, origin, start = 0, 37, 37
    labels = np.arange(start, start + received.size, dtype=np.int64)
    initial = ReconstructionEstimatorState([[0.42, 0.91]], [[0.42, 0.91]], 12)
    pair = run_reconstruction_causal_trace_pair(
        received=received,
        absolute_sample_indices=labels,
        received_start_sample=start,
        symbol_origin_sample=origin,
        first_symbol_index=first_symbol,
        initial_estimator_time_index=12,
        initial_state=initial,
        beta=0.7,
        sequence_id=f"fixture-{count}-{gain}",
        adaptive_alpha_prime=0.85,
        adaptive_k_tilde=[[0.35, -0.2]],
        adaptive_mu0=[[0.0, 0.0]],
    )
    assert len(pair.adaptive.history) == count
    assert pair.frozen.decoded_path_valid and pair.adaptive.decoded_path_valid


def test_segmented_trace_matches_monolithic_trace_and_decodes_once() -> None:
    _, monolithic = _trace(6)
    _, segmented = _trace(6, partition=(2, 1, 3))
    assert monolithic.frozen.decode_call_count == segmented.frozen.decode_call_count == 1
    assert monolithic.adaptive.decode_call_count == segmented.adaptive.decode_call_count == 1
    for left_mode, right_mode in (
        (monolithic.frozen, segmented.frozen),
        (monolithic.adaptive, segmented.adaptive),
    ):
        np.testing.assert_array_equal(
            left_mode.frozen_metric_history, right_mode.frozen_metric_history
        )
        assert left_mode.decoded_hypothesis_path == right_mode.decoded_hypothesis_path
        expected_segment_labels = ((0, 0), (0, 1), (1, 0), (2, 0), (2, 1), (2, 2))
        for index, (left, right) in enumerate(
            zip(left_mode.history, right_mode.history, strict=True)
        ):
            np.testing.assert_array_equal(left.pre_state.full_iq, right.pre_state.full_iq)
            np.testing.assert_array_equal(left.post_state.full_iq, right.post_state.full_iq)
            np.testing.assert_array_equal(left.posterior, right.posterior)
            np.testing.assert_array_equal(left.innovation_operand, right.innovation_operand)
            assert (right.segment_index, right.segment_local_position) == expected_segment_labels[
                index
            ]


def test_trace_is_immutable_finite_and_rejects_invalid_inputs() -> None:
    received, result = _trace(1)
    with pytest.raises(ValueError):
        result.adaptive.history[0].candidate_metrics[0] = 4.0
    received[0] = complex(np.nan, 0.0)
    assert np.all(np.isfinite(result.adaptive.history[0].observed_iq))
    with pytest.raises(ValueError, match="finite"):
        _trace_with_bad_input()


def _trace_with_bad_input():
    received = _received(1)
    received[0] = complex(np.inf, 0.0)
    return run_reconstruction_causal_trace_pair(
        received=received,
        absolute_sample_indices=np.arange(8),
        received_start_sample=0,
        symbol_origin_sample=0,
        first_symbol_index=0,
        initial_estimator_time_index=0,
        initial_state=ReconstructionEstimatorState([[0.1, 0.2]], [[0.1, 0.2]], 0),
        beta=1.0,
        sequence_id="invalid",
        adaptive_alpha_prime=0.8,
        adaptive_k_tilde=[[0.2, 0.3]],
        adaptive_mu0=[[0.0, 0.0]],
    )


def test_trace_module_has_no_reference_or_channel_truth_receiver_inputs() -> None:
    path = Path(__file__).parents[1] / "src/hf_tcm/evaluation/reconstruction_causal_trace.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "reference_bits",
        "reference_information_bits",
        "true_channel_gain",
        "ChannelTruth",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert forbidden.isdisjoint(names)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert all("m5j" not in module and "m5h" not in module for module in imported_modules)
    assert not {"default_rng", "PCG64", "generate_independent_complex_awgn"}.intersection(names)


def test_trace_does_not_mutate_historical_m5_artifacts() -> None:
    root = Path(__file__).parents[1]
    paths = (
        root / "outputs/m5j_confirmatory/20261029T-run",
        root / "outputs/m5h_independent_pilot/20261029T180438711965Z",
        root / "outputs/m5f_paired_monte_carlo_records.json",
    )

    def digest(path: Path) -> str:
        files = (
            (path,)
            if path.is_file()
            else tuple(sorted(item for item in path.rglob("*") if item.is_file()))
        )
        state = hashlib.sha256()
        for item in files:
            relative = item.name if path.is_file() else item.relative_to(path).as_posix()
            state.update(relative.encode("utf-8"))
            state.update(b"\0")
            state.update(item.read_bytes())
        return state.hexdigest()

    before = tuple(digest(path) for path in paths)
    _trace(1)
    after = tuple(digest(path) for path in paths)
    assert after == before
