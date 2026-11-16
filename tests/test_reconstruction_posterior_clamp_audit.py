from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.evaluation.reconstruction_multistep_feedback_audit import deterministic_feedback_fixture
from hf_tcm.evaluation.reconstruction_posterior_clamp_audit import (
    M6G_FIXTURE_SHA256,
    posterior_clamp_to_json,
    run_posterior_clamp_audit,
    write_posterior_clamp_json,
)

ROOT = Path(__file__).resolve().parents[1]
M6G_TRACE = ROOT / "outputs/m6g_multistep_feedback_audit/deterministic_trace.json"
ARMS = ("B", "A", "K", "C")


def _close(actual: np.ndarray, expected: np.ndarray, atol: float = 1e-10) -> None:
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=atol)


def _weighted(p: np.ndarray, y: np.ndarray, u: np.ndarray) -> np.ndarray:
    return np.asarray(
        [
            math.fsum(float(p[h]) * (float(y[j]) - float(u[h, j])) for h in range(16))
            for j in range(2)
        ]
    )


def _posterior_oracle(prior: np.ndarray, metrics: np.ndarray) -> np.ndarray:
    support = [index for index, value in enumerate(prior) if value > 0.0]
    best = min(float(metrics[index]) for index in support)
    weighted = [
        float(prior[index]) * math.exp(-0.7 * (float(metrics[index]) - best))
        if prior[index] > 0.0
        else 0.0
        for index in range(16)
    ]
    total = math.fsum(weighted)
    return np.asarray([value / total for value in weighted])


def _transition_oracle() -> np.ndarray:
    result = np.zeros((16, 16))
    for i, previous in enumerate(HYPOTHESES):
        following = [
            j
            for j, current in enumerate(HYPOTHESES)
            if previous.next_state == current.current_state
        ]
        for j in following:
            result[i, j] = 1.0 / len(following)
    return result


def test_fixture_and_immutable_m6g_source_are_verified() -> None:
    result = run_posterior_clamp_audit(m6g_trace_path=M6G_TRACE)
    assert result["fixture_sha256"] == M6G_FIXTURE_SHA256
    assert result["m6g_source_sha256"] == (
        "67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75"
    )
    assert deterministic_feedback_fixture().shape == (64,)
    assert tuple(result["same_state"]) == ARMS


def test_same_state_weight_swap_identities_and_first_symbol_agreement() -> None:
    result = run_posterior_clamp_audit(m6g_trace_path=M6G_TRACE)
    for arm in ARMS:
        rows = result["same_state"][arm]
        assert len(rows) == 8
        for row in rows:
            assert row["hypothesis_ids"] == list(range(16))
            assert row["finite"]
            assert abs(row["own_posterior_normalization_error"]) < 1e-12
            assert abs(row["b_posterior_normalization_error"]) < 1e-12
            own, clamp, y, pred, pown, pb = (
                np.asarray(row[key])
                for key in (
                    "epsilon_own",
                    "epsilon_clamp",
                    "observed_iq",
                    "own_predictions",
                    "own_posterior",
                    "b_posterior",
                )
            )
            _close(own, _weighted(pown, y, pred))
            _close(clamp, _weighted(pb, y, pred))
            _close(row["delta_epsilon_weights"], own - clamp)
            _close(
                row["delta_epsilon_weights"],
                np.asarray(
                    [
                        math.fsum(
                            float(pown[h] - pb[h]) * (float(y[j]) - float(pred[h, j]))
                            for h in range(16)
                        )
                        for j in range(2)
                    ]
                ),
            )
            _close(
                row["delta_epsilon_weights"],
                -np.asarray(
                    [
                        math.fsum(float(pown[h] - pb[h]) * float(pred[h, j]) for h in range(16))
                        for j in range(2)
                    ]
                ),
            )
            pred_delta = np.asarray(
                [
                    math.fsum(
                        float(pb[h])
                        * (float(row["b_predictions_same_symbol"][h][j]) - float(pred[h, j]))
                        for h in range(16)
                    )
                    for j in range(2)
                ]
            )
            _close(row["delta_epsilon_prediction"], pred_delta)
            _close(
                own - np.asarray(row["epsilon_b"]),
                np.asarray(row["delta_epsilon_weights"]) + pred_delta,
            )
            expected_own_post = np.asarray(
                [
                    result["arms"][arm]["alpha_prime"] * float(row["pre_fluctuating"][j])
                    + result["arms"][arm]["k_tilde"][j] * float(own[j])
                    for j in range(2)
                ]
            )
            expected_clamp_post = np.asarray(
                [
                    result["arms"][arm]["alpha_prime"] * float(row["pre_fluctuating"][j])
                    + result["arms"][arm]["k_tilde"][j] * float(clamp[j])
                    for j in range(2)
                ]
            )
            _close(row["one_step_own_post_fluctuating"], expected_own_post)
            _close(row["one_step_clamp_post_fluctuating"], expected_clamp_post)
        _close(rows[0]["epsilon_own"], rows[0]["epsilon_clamp"], atol=0.0)
        _close(rows[0]["epsilon_own"], result["b_reference_innovations"][0], atol=1e-12)


def test_b_and_a_are_invariant_across_closed_clamp_and_common_regimes() -> None:
    result = run_posterior_clamp_audit(m6g_trace_path=M6G_TRACE)
    for arm in ("B", "A"):
        for f in range(8):
            closed = result["m6g_closed_loop"][arm]["rows"][f]
            clamp = result["posterior_clamp"][arm]["rows"][f]
            common = result["m6g_common_operand"][arm]["rows"][f]
            for key in ("pre_fluctuating", "post_fluctuating", "metrics", "posterior"):
                _close(closed[key], clamp[key])
                _close(closed[key], common[key])


def test_multistep_clamp_uses_b_weights_but_retains_own_posterior_history() -> None:
    result = run_posterior_clamp_audit(m6g_trace_path=M6G_TRACE)
    for arm in ARMS:
        rows = result["posterior_clamp"][arm]["rows"]
        for f, row in enumerate(rows):
            _close(row["supplied_weights"], result["b_reference_posteriors"][f])
            assert row["supplied_weight_origin"] == "same_symbol_frozen_B_posterior"
            assert row["posterior_origin"] == (
                "ADR-004 first-edge update" if f == 0 else "own previous posterior via transition"
            )
            _close(row["posterior"], row["own_posterior"])
            assert row["raw_q"] == "unavailable"
            assert row["q_provenance"] == (
                "none_first_edge"
                if f == 0
                else "derived_from_own_previous_posterior @ ADR-003 transition"
            )
            assert math.fsum(float(value) for value in row["posterior"]) == pytest.approx(
                1.0, rel=0.0, abs=1e-12
            )
            assert row["finite"]


def test_clamp_posteriors_match_independent_first_edge_and_continuation_oracle() -> None:
    result = run_posterior_clamp_audit(m6g_trace_path=M6G_TRACE)
    transition = _transition_oracle()
    first_prior = np.asarray([0.25 if edge.current_state == (0, 0) else 0.0 for edge in HYPOTHESES])
    for arm in ARMS:
        previous = None
        for f, row in enumerate(result["posterior_clamp"][arm]["rows"]):
            prior = (
                first_prior
                if f == 0
                else np.asarray(
                    [
                        math.fsum(float(previous[i]) * float(transition[i, j]) for i in range(16))
                        for j in range(16)
                    ]
                )
            )
            _close(row["posterior_prior"], prior)
            _close(row["posterior"], _posterior_oracle(prior, np.asarray(row["metrics"])))
            expected_state = np.asarray(
                [
                    result["arms"][arm]["alpha_prime"] * float(row["pre_fluctuating"][j])
                    + result["arms"][arm]["k_tilde"][j] * float(row["supplied_innovation"][j])
                    for j in range(2)
                ]
            )
            _close(row["post_fluctuating"], expected_state)
            _close(row["post_full"], expected_state)
            previous = np.asarray(row["posterior"])


def test_trace_schema_shapes_clocks_and_no_reference_or_truth_leakage() -> None:
    result = run_posterior_clamp_audit(m6g_trace_path=M6G_TRACE)
    for arm in ARMS:
        for row in result["posterior_clamp"][arm]["rows"]:
            assert len(row["predictions"]) == 16
            assert len(row["metrics"]) == len(row["posterior"]) == 16
            assert row["sample_window"] == list(
                range(8 * row["symbol_index"], 8 * row["symbol_index"] + 8)
            )
            assert row["prediction_cutoff_sample"] == 8 * row["symbol_index"] - 1
            assert row["observation_cutoff_sample"] == 8 * row["symbol_index"] + 7
    encoded = json.dumps(result, allow_nan=False)
    assert "reference_bits" not in encoded
    assert "ChannelTruth" not in encoded
    assert result["decoder_invoked"] is False
    assert result["random_generation_invoked"] is False


def test_nonfinite_or_wrong_fixture_and_mutated_m6g_artifact_are_rejected(tmp_path) -> None:
    received = deterministic_feedback_fixture()
    wrong = received.copy()
    wrong[0] += 1.0
    with pytest.raises(ValueError, match="fixture SHA-256"):
        run_posterior_clamp_audit(received=wrong, m6g_trace_path=M6G_TRACE)
    nonfinite = received.copy()
    nonfinite[0] = complex(float("nan"), 0.0)
    with pytest.raises(ValueError, match="finite"):
        run_posterior_clamp_audit(received=nonfinite, m6g_trace_path=M6G_TRACE)
    altered = json.loads(M6G_TRACE.read_text(encoding="utf-8"))
    altered["fixture_sha256"] = "0" * 64
    fake = tmp_path / "altered.json"
    fake.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="source trace SHA-256"):
        run_posterior_clamp_audit(m6g_trace_path=fake)


def test_k_c_trajectory_differences_start_after_first_shared_update() -> None:
    result = run_posterior_clamp_audit(m6g_trace_path=M6G_TRACE)
    for arm in ("K", "C"):
        cl_rows = result["m6g_closed_loop"][arm]["rows"]
        clamp_rows = result["posterior_clamp"][arm]["rows"]
        assert cl_rows[0]["post_fluctuating"] == pytest.approx(
            clamp_rows[0]["post_fluctuating"], rel=0.0, abs=1e-12
        )
        assert cl_rows[1]["metrics"] == pytest.approx(clamp_rows[1]["metrics"], rel=0.0, abs=1e-12)
        assert (
            np.max(
                np.abs(
                    np.asarray(cl_rows[1]["post_fluctuating"])
                    - np.asarray(clamp_rows[1]["post_fluctuating"])
                )
            )
            > 1e-10
        )
        assert (
            np.max(np.abs(np.asarray(cl_rows[2]["metrics"]) - np.asarray(clamp_rows[2]["metrics"])))
            > 1e-10
        )
        assert (
            np.max(
                np.abs(np.asarray(cl_rows[2]["posterior"]) - np.asarray(clamp_rows[2]["posterior"]))
            )
            > 1e-10
        )


def test_m6h_trace_serialization_round_trip_and_m6g_hash_preservation(tmp_path) -> None:
    import hashlib

    before = hashlib.sha256(M6G_TRACE.read_bytes()).hexdigest()
    result = run_posterior_clamp_audit(m6g_trace_path=M6G_TRACE)
    payload = json.loads(posterior_clamp_to_json(result))
    assert payload["schema_version"] == "m6h.posterior-clamp.v1"
    assert tuple(payload["posterior_clamp"]) == ARMS
    assert tuple(payload["m6g_closed_loop"]) == ARMS
    assert tuple(payload["m6g_common_operand"]) == ARMS
    assert (
        sum(
            len(payload[regime][arm]["rows"])
            for regime in ("posterior_clamp", "m6g_closed_loop", "m6g_common_operand")
            for arm in ARMS
        )
        == 96
    )
    target = write_posterior_clamp_json(result, tmp_path / "trace.json")
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert not target.with_name(target.name + ".tmp").exists()
    after = hashlib.sha256(M6G_TRACE.read_bytes()).hexdigest()
    assert before == after == result["m6g_source_sha256"]
