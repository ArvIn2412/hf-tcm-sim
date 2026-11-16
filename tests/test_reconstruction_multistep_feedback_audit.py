from __future__ import annotations

import json
import math

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.evaluation.reconstruction_multistep_feedback_audit import (
    FEEDBACK_ARMS,
    feedback_audit_to_json,
    run_reconstruction_multistep_feedback_audit,
    write_feedback_audit_json,
)


def _fixture() -> np.ndarray:
    return np.asarray(
        [
            complex(
                (index - 31) / 40.0 + ((index % 7) - 3) / 100.0,
                (((3 * index) % 11) - 5) / 30.0,
            )
            for index in range(64)
        ],
        dtype=np.complex128,
    )


def _assert_close(actual: np.ndarray, expected: np.ndarray, atol: float = 1e-11) -> None:
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=atol)


EXPECTED_PHASES = (0, 2, 4, 6, 2, 0, 6, 4, 1, 3, 5, 7, 3, 1, 7, 5)


def _phase_prediction(full: np.ndarray, edge: int) -> np.ndarray:
    phase = EXPECTED_PHASES[edge] * math.pi / 4.0
    return np.asarray([-full[0] * math.sin(phase), full[1] * math.cos(phase)])


def _oracle_metric(received: np.ndarray, position: int, full: np.ndarray) -> np.ndarray:
    result = []
    for edge in range(16):
        prediction = _phase_prediction(full, edge)
        residuals = []
        for sample in range(position * 8, (position + 1) * 8):
            observed = (-float(received[sample].imag), float(received[sample].real))
            residuals.extend((observed[axis] - prediction[axis]) ** 2 for axis in range(2))
        result.append(math.fsum(residuals))
    return np.asarray(result)


def _oracle_posterior(prior: np.ndarray, metrics: np.ndarray) -> np.ndarray:
    support = [index for index, probability in enumerate(prior) if probability > 0]
    best = min(float(metrics[index]) for index in support)
    weighted = [
        float(prior[index]) * math.exp(-0.7 * (float(metrics[index]) - best))
        if prior[index] > 0
        else 0.0
        for index in range(16)
    ]
    total = math.fsum(weighted)
    return np.asarray([value / total for value in weighted])


def _oracle_transition() -> np.ndarray:
    result = np.zeros((16, 16))
    for previous_index, previous in enumerate(HYPOTHESES):
        following = [
            index
            for index, current in enumerate(HYPOTHESES)
            if previous.next_state == current.current_state
        ]
        for index in following:
            result[previous_index, index] = 1.0 / len(following)
    return result


def test_fixed_fixture_and_four_policies_are_deterministic() -> None:
    received = _fixture()
    assert received.shape == (64,)
    assert tuple(FEEDBACK_ARMS) == ("B", "A", "K", "C")
    assert FEEDBACK_ARMS["B"].alpha_prime == 1.0
    assert FEEDBACK_ARMS["A"].alpha_prime == 0.85
    assert FEEDBACK_ARMS["K"].k_tilde == (0.35, -0.2)
    result = run_reconstruction_multistep_feedback_audit(received=received)
    assert (
        result.fixture_sha256 == "99df8784d417cd9d615c389d088f717f0735f4af6accb282fcff82a547629969"
    )
    assert tuple(result.closed_loop.arms) == ("B", "A", "K", "C")
    assert tuple(result.common_operand.arms) == ("B", "A", "K", "C")
    assert all(len(result.closed_loop.arms[name].rows) == 8 for name in FEEDBACK_ARMS)


def test_first_step_shared_operands_and_additive_state_decomposition() -> None:
    result = run_reconstruction_multistep_feedback_audit(received=_fixture())
    rows = {name: result.closed_loop.arms[name].rows[0] for name in FEEDBACK_ARMS}
    for name in ("A", "K", "C"):
        _assert_close(rows[name].metrics, rows["B"].metrics, atol=0.0)
        _assert_close(rows[name].posterior, rows["B"].posterior, atol=0.0)
        _assert_close(
            rows[name].own_posterior_innovation, rows["B"].own_posterior_innovation, atol=0.0
        )
    assert result.common_operand.arms["C"].rows[0].supplied_innovation_origin == (
        "frozen_B_actual_closed_loop_innovation"
    )
    for regime in (result.closed_loop, result.common_operand):
        b, a, k, c = (regime.arms[name].rows[0].post_fluctuating for name in ("B", "A", "K", "C"))
        _assert_close(c - a - k + b, np.zeros(2), atol=1e-12)
    _assert_close(
        result.common_operand.arms["B"].rows[-1].post_fluctuating,
        result.closed_loop.arms["B"].rows[-1].post_fluctuating,
        atol=1e-12,
    )


def test_common_operand_replay_keeps_b_and_a_trajectories_invariant() -> None:
    result = run_reconstruction_multistep_feedback_audit(received=_fixture())
    for name in ("B", "A"):
        closed = result.closed_loop.arms[name].rows
        common = result.common_operand.arms[name].rows
        for left, right in zip(closed, common, strict=True):
            _assert_close(left.pre_fluctuating, right.pre_fluctuating)
            _assert_close(left.metrics, right.metrics)
            _assert_close(left.posterior, right.posterior)
            _assert_close(left.post_fluctuating, right.post_fluctuating)
    assert result.common_operand.arms["K"].rows[1].supplied_innovation_origin == (
        "frozen_B_actual_closed_loop_innovation"
    )


def test_multistep_interactions_and_feedback_contrasts_are_explicit() -> None:
    result = run_reconstruction_multistep_feedback_audit(received=_fixture())
    assert len(result.closed_loop.interactions) == 8
    assert len(result.common_operand.interactions) == 8
    assert len(result.feedback_contrasts) == 8
    assert np.max(np.abs(result.common_operand.interactions[0].post_state)) < 1e-12
    assert any(
        np.max(np.abs(item.post_state)) > 1e-10 for item in result.common_operand.interactions[1:]
    )
    assert np.max(np.abs(result.feedback_contrasts[0].state_post_by_arm["C"])) < 1e-12


def test_q_provenance_and_clock_labels_are_not_implicit() -> None:
    result = run_reconstruction_multistep_feedback_audit(
        received=_fixture(), symbol_origin_sample=31, first_symbol_index=4, estimator_time_origin=7
    )
    row = result.closed_loop.arms["C"].rows[0]
    assert row.symbol_index == 4
    assert row.estimator_time_index == 7
    assert row.sample_window == tuple(range(63, 71))
    assert row.prediction_cutoff_sample == 62
    assert row.observation_cutoff_sample == 70
    assert row.q_provenance == "initial_prior_directly_supplied; no transition q"
    assert not row.raw_q_exported
    assert result.closed_loop.arms["C"].rows[1].q_provenance == (
        "derived_from_previous_posterior_and_ADR003_transition"
    )


def test_no_random_generation_decoder_or_truth_input() -> None:
    result = run_reconstruction_multistep_feedback_audit(received=_fixture())
    assert result.decoder_invoked is False
    assert result.random_generation_invoked is False


def test_all_rows_match_independent_scalar_metric_posterior_and_update_oracles() -> None:
    received = _fixture()
    result = run_reconstruction_multistep_feedback_audit(received=received)
    transition = _oracle_transition()
    first_prior = np.asarray([0.25 if edge.current_state == (0, 0) else 0.0 for edge in HYPOTHESES])
    for audit in (result.closed_loop, result.common_operand):
        for arm in FEEDBACK_ARMS:
            previous_posterior = None
            for position, row in enumerate(audit.arms[arm].rows):
                metrics = _oracle_metric(received, position, row.pre_full)
                _assert_close(row.metrics, metrics)
                prior = (
                    first_prior
                    if position == 0
                    else np.asarray(
                        [
                            math.fsum(
                                float(previous_posterior[i]) * float(transition[i, j])
                                for i in range(16)
                            )
                            for j in range(16)
                        ]
                    )
                )
                posterior = _oracle_posterior(prior, metrics)
                _assert_close(row.posterior_prior, prior)
                _assert_close(row.posterior, posterior)
                assert math.fsum(float(value) for value in row.posterior) == pytest.approx(
                    1.0, rel=0.0, abs=1e-12
                )
                predictions = np.asarray(
                    [_phase_prediction(row.pre_full, edge) for edge in range(16)]
                )
                _assert_close(row.predictions, predictions)
                observed = np.asarray(
                    [
                        math.fsum(
                            -float(received[index].imag)
                            if axis == 0
                            else float(received[index].real)
                            for index in range(position * 8, (position + 1) * 8)
                        )
                        / 8.0
                        for axis in range(2)
                    ]
                )
                epsilon = np.asarray(
                    [
                        math.fsum(
                            float(posterior[edge])
                            * (float(observed[axis]) - float(predictions[edge, axis]))
                            for edge in range(16)
                        )
                        for axis in range(2)
                    ]
                )
                _assert_close(row.own_posterior_innovation, epsilon)
                supplied = (
                    epsilon
                    if audit.regime == "CLOSED_LOOP"
                    else result.reference_innovations[position]
                )
                _assert_close(row.supplied_innovation, supplied)
                policy = FEEDBACK_ARMS[arm]
                next_state = np.asarray(
                    [
                        policy.alpha_prime * float(row.pre_fluctuating[axis])
                        + policy.k_tilde[axis] * float(supplied[axis])
                        for axis in range(2)
                    ]
                )
                _assert_close(row.post_fluctuating, next_state)
                _assert_close(row.post_full, next_state)
                assert row.hypothesis_ids == tuple(range(16))
                assert row.sample_window == tuple(range(position * 8, position * 8 + 8))
                assert row.prediction_cutoff_sample == position * 8 - 1
                assert row.observation_cutoff_sample == position * 8 + 7
                assert row.edge_mode == ("first_edge" if position == 0 else "later_edge")
                assert row.finite
                previous_posterior = posterior


def test_factorial_interactions_and_feedback_contrasts_match_row_arithmetic() -> None:
    result = run_reconstruction_multistep_feedback_audit(received=_fixture())
    for audit in (result.closed_loop, result.common_operand):
        for position, interaction in enumerate(audit.interactions):
            b, a, k, c = (audit.arms[key].rows[position] for key in ("B", "A", "K", "C"))
            _assert_close(
                interaction.pre_state,
                c.pre_fluctuating - a.pre_fluctuating - k.pre_fluctuating + b.pre_fluctuating,
            )
            _assert_close(
                interaction.post_state,
                c.post_fluctuating - a.post_fluctuating - k.post_fluctuating + b.post_fluctuating,
            )
            _assert_close(interaction.metrics, c.metrics - a.metrics - k.metrics + b.metrics)
            _assert_close(
                interaction.posterior, c.posterior - a.posterior - k.posterior + b.posterior
            )
    for position, contrast in enumerate(result.feedback_contrasts):
        for arm in FEEDBACK_ARMS:
            closed = result.closed_loop.arms[arm].rows[position]
            common = result.common_operand.arms[arm].rows[position]
            _assert_close(
                contrast.state_pre_by_arm[arm], closed.pre_fluctuating - common.pre_fluctuating
            )
            _assert_close(
                contrast.state_post_by_arm[arm], closed.post_fluctuating - common.post_fluctuating
            )
            _assert_close(contrast.metric_by_arm[arm], closed.metrics - common.metrics)
            _assert_close(contrast.posterior_by_arm[arm], closed.posterior - common.posterior)


def test_future_windows_do_not_change_previously_frozen_rows() -> None:
    received = _fixture()
    original = run_reconstruction_multistep_feedback_audit(received=received)
    changed = received.copy()
    changed[40:] += np.asarray(
        [complex(index / 17.0, -index / 19.0) for index in range(24)],
        dtype=np.complex128,
    )
    altered = run_reconstruction_multistep_feedback_audit(received=changed)
    for regime_name in ("closed_loop", "common_operand"):
        left_regime = getattr(original, regime_name)
        right_regime = getattr(altered, regime_name)
        for arm in FEEDBACK_ARMS:
            for position in range(5):
                left = left_regime.arms[arm].rows[position]
                right = right_regime.arms[arm].rows[position]
                _assert_close(left.metrics, right.metrics, atol=0.0)
                _assert_close(left.posterior, right.posterior, atol=0.0)
                _assert_close(left.post_fluctuating, right.post_fluctuating, atol=0.0)


def test_input_and_trace_arrays_are_immutable_and_invalid_buffers_rejected() -> None:
    received = _fixture()
    original = received.copy()
    result = run_reconstruction_multistep_feedback_audit(received=received)
    np.testing.assert_array_equal(received, original)
    with pytest.raises(ValueError):
        result.closed_loop.arms["C"].rows[2].metrics[0] = 0.0
    with pytest.raises(ValueError, match="shape"):
        run_reconstruction_multistep_feedback_audit(received=received[:63])
    nonfinite = received.copy()
    nonfinite[0] = complex(float("nan"), 0.0)
    with pytest.raises(ValueError, match="finite"):
        run_reconstruction_multistep_feedback_audit(received=nonfinite)


def test_evaluation_adapter_has_no_rng_truth_bits_or_decoder_dependency() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src/hf_tcm/evaluation/reconstruction_multistep_feedback_audit.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "default_rng",
        "SeedSequence",
        "ChannelTruth",
        "reference_bits",
        "viterbi_decode",
    ):
        assert forbidden not in source


def test_trace_json_round_trip_and_atomic_write(tmp_path) -> None:
    result = run_reconstruction_multistep_feedback_audit(received=_fixture())
    encoded = feedback_audit_to_json(result)
    payload = json.loads(encoded)
    assert payload["schema_version"] == "m6g.feedback-trace.v1"
    assert payload["fixture_sha256"] == result.fixture_sha256
    assert tuple(payload["closed_loop"]["arms"]) == tuple(FEEDBACK_ARMS)
    assert (
        sum(
            len(payload[regime]["arms"][arm]["rows"])
            for regime in ("closed_loop", "common_operand")
            for arm in FEEDBACK_ARMS
        )
        == 64
    )
    assert len(payload["closed_loop"]["arms"]["B"]["frozen_metric_matrix"]) == 8
    assert len(payload["closed_loop"]["arms"]["B"]["rows"][0]["metrics"]) == 16
    target = write_feedback_audit_json(result, tmp_path / "trace.json")
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert not target.with_name(target.name + ".tmp").exists()
