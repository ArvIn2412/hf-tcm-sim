from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.evaluation.m7b_train_runner import historical_integrity_baseline
from hf_tcm.evaluation.m8a_anchored_study_design import (
    M8AExecutionBlocked,
    expected_sigma_squared,
    guard_m8a_execution,
    validate_m8a_anchored_study,
)
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
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
from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    run_reconstruction_posterior_estimator_sequence,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "m8a_anchored_study_draft.json"


def _draft() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _sequence_args(
    *,
    initial_state: ReconstructionEstimatorState,
    mu0: tuple[float, float],
    alpha: float,
    k_tilde: tuple[float, float],
    symbol_count: int = 3,
) -> dict[str, object]:
    samples = np.asarray(
        [complex(0.31 + 0.017 * n, -0.22 + 0.011 * n) for n in range(8 * symbol_count)],
        dtype=np.complex128,
    )
    return {
        "received": samples,
        "absolute_sample_indices": np.arange(samples.size, dtype=np.int64),
        "received_start_sample": 0,
        "symbol_origin_sample": 0,
        "first_symbol_index": 0,
        "sequence_origin_symbol_index": 0,
        "symbol_count": symbol_count,
        "symbol_indices": tuple(range(symbol_count)),
        "initial_state": initial_state,
        "initial_estimator_time_index": 0,
        "run_mode": "new_independent_sequence",
        "initial_prior": build_initial_reconstruction_prior(initial_state=(0, 0)),
        "previous_posterior": None,
        "continuation_from_symbol_index": None,
        "continuation_from_estimator_time_index": None,
        "beta": 0.7,
        "alpha_prime": alpha,
        "k_tilde": np.asarray([k_tilde], dtype=np.float64),
        "mu0": np.asarray([mu0], dtype=np.float64),
        "include_history": True,
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


def _manual_no_correction(
    initial_full: tuple[float, float], anchor: tuple[float, float], alpha: float, updates: int
) -> tuple[float, float]:
    state = [initial_full[index] - anchor[index] for index in range(2)]
    for _ in range(updates):
        state = [alpha * coordinate for coordinate in state]
    return tuple(state[index] + anchor[index] for index in range(2))


def test_m8a_draft_is_exact_and_stays_unauthorized() -> None:
    design = validate_m8a_anchored_study(_draft())
    draft_hash = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    assert (
        draft_hash
        == (CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + ".sha256"))
        .read_text(encoding="ascii")
        .strip()
    )
    assert design.design_status == "proposed"
    assert design.execution_authorized is False
    assert design.execution_scope == "none"
    assert len(design.candidates) == 8
    assert [candidate.candidate_id for candidate in design.candidates] == [
        "anch_a100_k025",
        "anch_a100_k050",
        "anch_a095_k025",
        "anch_a095_k050",
        "anch_a085_k025",
        "anch_a085_k050",
        "historical_frozen_B",
        "historical_combined_C",
    ]
    assert expected_sigma_squared() == pytest.approx(0.7115124735378853, abs=1e-15)
    assert design.training_sequence_count == 40
    assert design.validation_sequence_count == 40
    assert design.expected_training_decoder_passes == 320


def test_m7b_closeout_replays_saved_integer_counts_without_receiver_calls() -> None:
    output = ROOT / "outputs" / "m7b_train" / "m7_reconstructed_estimator_policy_study_v1"
    checkpoint_paths = sorted((output / "checkpoints").glob("run-*.json"))
    checkpoints = [json.loads(path.read_text(encoding="utf-8")) for path in checkpoint_paths]
    assert len(checkpoints) == 40
    assert len({row["run_id"] for row in checkpoints}) == 40
    assert len({row["received_sha256"] for row in checkpoints}) == 40
    assert all(row["status"] == "complete" for row in checkpoints)
    assert all(row["decoder_invocations"] == 9 for row in checkpoints)
    expected_ids = [row["candidate_id"] for row in checkpoints[0]["policies"]]
    totals = {
        candidate_id: {"bit_errors": 0, "total_bits": 0, "symbol_errors": 0, "total_symbols": 0}
        for candidate_id in expected_ids
    }
    pass_count = 0
    for checkpoint in checkpoints:
        reference_bits = checkpoint["evaluation_only"]["reference_information_bits"]
        reference_symbols = checkpoint["evaluation_only"]["reference_symbol_indices"]
        assert len(checkpoint["policies"]) == 9
        assert [row["candidate_id"] for row in checkpoint["policies"]] == expected_ids
        for row in checkpoint["policies"]:
            assert row["status"] == "complete_valid_output"
            assert row["decoder_invocations"] == 1
            counts = row["counts"]
            decoded_bits = row["decoded_information_bits"]
            decoded_symbols = row["decoded_symbol_indices"]
            assert counts["bit_errors"] == sum(
                a != b for a, b in zip(reference_bits, decoded_bits, strict=True)
            )
            assert counts["symbol_errors"] == sum(
                a != b for a, b in zip(reference_symbols, decoded_symbols, strict=True)
            )
            assert counts["total_bits"] == len(reference_bits) == 512
            assert counts["total_symbols"] == len(reference_symbols) == 256
            total = totals[row["candidate_id"]]
            for key in total:
                total[key] += counts[key]
            pass_count += 1
    assert pass_count == 360
    expected_totals = {
        "a100_k000": (478, 20480, 441, 10240),
        "a100_k050": (3050, 20480, 2333, 10240),
        "a100_k100": (4831, 20480, 3835, 10240),
        "a095_k000": (1903, 20480, 1559, 10240),
        "a095_k050": (7575, 20480, 6791, 10240),
        "a095_k100": (7357, 20480, 6799, 10240),
        "a085_k000": (4871, 20480, 4006, 10240),
        "a085_k050": (8545, 20480, 7502, 10240),
        "a085_k100": (8093, 20480, 7339, 10240),
    }
    assert {
        candidate_id: tuple(total.values()) for candidate_id, total in totals.items()
    } == expected_totals
    ranking = sorted(
        expected_ids,
        key=lambda candidate_id: (
            totals[candidate_id]["bit_errors"] / totals[candidate_id]["total_bits"],
            totals[candidate_id]["symbol_errors"] / totals[candidate_id]["total_symbols"],
            next(
                row["k_scale"]
                for row in checkpoints[0]["policies"]
                if row["candidate_id"] == candidate_id
            ),
            abs(
                1.0
                - next(
                    row["alpha_prime"]
                    for row in checkpoints[0]["policies"]
                    if row["candidate_id"] == candidate_id
                )
            ),
            candidate_id,
        ),
    )
    assert ranking[0] == "a100_k000"
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    selected = json.loads((output / "selected_policy.json").read_text(encoding="utf-8"))
    assert summary["status"] == "TRAIN_SELECTED_NOT_VALIDATED"
    assert summary["selected_candidate_id"] == "a100_k000"
    assert selected["status"] == "TRAIN_SELECTED_NOT_VALIDATED"
    assert selected["candidate_id"] == "a100_k000"
    integrity = json.loads((output / "integrity_manifest.json").read_text(encoding="utf-8"))
    assert all(
        hashlib.sha256((output / relative).read_bytes()).hexdigest() == digest
        for relative, digest in integrity.items()
    )
    assert hashlib.sha256(
        (ROOT / "configs" / "m7a_policy_study_draft.json").read_bytes()
    ).hexdigest() == ("6b5cffdd9c4f47241bf7d54ff5d58c93d65bc2759a35557e07e3a1f38dae841f")
    assert (
        hashlib.sha256((ROOT / "configs" / "m7b_train_approved_run.json").read_bytes()).hexdigest()
        == "7b29eaed0166765193b3f8bc16eae760826e1469a97025577573730113c87595"
    )
    approved = json.loads(
        (ROOT / "configs" / "m7b_train_approved_run.json").read_text(encoding="utf-8")
    )
    assert historical_integrity_baseline() == approved["historical_integrity_baseline"]


def test_m8a_unauthorized_guard_blocks_before_any_callbacks() -> None:
    calls: list[str] = []

    def rng_callback() -> None:
        calls.append("rng")

    def receiver_callback() -> None:
        calls.append("receiver")

    def data_callback() -> None:
        calls.append("data")

    with pytest.raises(M8AExecutionBlocked):
        guard_m8a_execution(
            _draft(),
            rng_callback=rng_callback,
            receiver_callback=receiver_callback,
            data_callback=data_callback,
        )
    assert calls == []


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update(execution_scope="m8b_train"), "execution_scope"),
        (
            lambda value: value["profile"].update(sigma_squared=0.5),
            "sigma_squared",
        ),
        (
            lambda value: value["anchored_profile"].update(nominal_prior_anchor_mu0=[0.75, 0.75]),
            "anchor",
        ),
        (
            lambda value: value["policy_grid"]["candidate_policies"].pop(),
            "candidate policies",
        ),
        (
            lambda value: value["policy_grid"]["candidate_policies"][1].update(
                candidate_id=value["policy_grid"]["candidate_policies"][0]["candidate_id"]
            ),
            "candidate policies",
        ),
        (
            lambda value: value["partitions"]["training"].update(sequence_count=39),
            "training.sequence_count",
        ),
        (
            lambda value: value["scientific_status"].update(
                author_mapping_status="AUTHOR_CONFIRMED"
            ),
            "author_mapping_status",
        ),
        (
            lambda value: value["partitions"]["validation"]["seed_namespaces"].update(
                data=value["partitions"]["training"]["seed_namespaces"]["data"]
            ),
            "distinct",
        ),
    ],
)
def test_m8a_invalid_design_is_rejected_before_callbacks(mutate, message: str) -> None:
    config = copy.deepcopy(_draft())
    mutate(config)
    calls: list[str] = []
    with pytest.raises(ValueError, match=message):
        guard_m8a_execution(
            config,
            rng_callback=lambda: calls.append("rng"),
            receiver_callback=lambda: calls.append("receiver"),
            data_callback=lambda: calls.append("data"),
        )
    assert calls == []


@pytest.mark.parametrize("alpha", [0.95, 0.85])
def test_zero_anchor_no_correction_has_geometric_decay(alpha: float) -> None:
    initial = (0.42, 0.91)
    expected = initial
    for updates in range(1, 9):
        expected = tuple(alpha * coordinate for coordinate in expected)
        assert expected == pytest.approx(
            tuple(alpha**updates * value for value in initial), abs=1e-15
        )
    assert expected == pytest.approx(_manual_no_correction(initial, (0.0, 0.0), alpha, 8))
    assert max(abs(value) for value in expected) < max(abs(value) for value in initial)


@pytest.mark.parametrize("alpha", [1.0, 0.95, 0.85])
def test_anchor_equal_to_initial_full_estimate_is_constant_for_k_zero(alpha: float) -> None:
    initial = (0.42, 0.91)
    assert _manual_no_correction(initial, initial, alpha, 12) == initial


def test_alpha_one_full_state_update_is_anchor_invariant() -> None:
    initial = (0.42, 0.91)
    innovation_sequence = ((0.12, -0.04), (-0.08, 0.2), (0.0, -0.11))
    k_tilde = (0.35, -0.2)
    trajectories = []
    for anchor in ((0.0, 0.0), initial):
        fluctuating = tuple(initial[i] - anchor[i] for i in range(2))
        full_states = [initial]
        for innovation in innovation_sequence:
            fluctuating = tuple(fluctuating[i] + k_tilde[i] * innovation[i] for i in range(2))
            full_states.append(tuple(fluctuating[i] + anchor[i] for i in range(2)))
        trajectories.append(full_states)
    np.testing.assert_allclose(trajectories[0], trajectories[1], rtol=0.0, atol=1e-15)


@pytest.mark.parametrize("alpha", [0.95, 0.85])
def test_production_sequence_has_same_initial_metrics_and_respects_anchor_lifecycle(
    alpha: float,
) -> None:
    initial_full = (0.42, 0.91)
    historical = ReconstructionEstimatorState([initial_full], [initial_full], 0)
    anchored = ReconstructionEstimatorState([[0.0, 0.0]], [initial_full], 0)

    historical_run = run_reconstruction_posterior_estimator_sequence(
        **_sequence_args(
            initial_state=historical,
            mu0=(0.0, 0.0),
            alpha=alpha,
            k_tilde=(0.0, 0.0),
        )
    )
    anchored_run = run_reconstruction_posterior_estimator_sequence(
        **_sequence_args(
            initial_state=anchored,
            mu0=initial_full,
            alpha=alpha,
            k_tilde=(0.0, 0.0),
        )
    )
    assert historical_run.history is not None and anchored_run.history is not None
    first_h = historical_run.history[0].b4c_result
    first_a = anchored_run.history[0].b4c_result
    np.testing.assert_array_equal(first_h.predicted_iq, first_a.predicted_iq)
    np.testing.assert_array_equal(
        first_h.candidate_result.metrics, first_a.candidate_result.metrics
    )
    np.testing.assert_array_equal(first_h.posterior, first_a.posterior)
    assert first_h.hypothesis_ids == tuple(range(16)) == first_a.hypothesis_ids

    for update_count, (row_h, row_a) in enumerate(
        zip(historical_run.history, anchored_run.history, strict=True), start=1
    ):
        assert row_h.first_sample_index == 8 * (update_count - 1)
        assert row_h.last_sample_index == 8 * update_count - 1
        assert row_h.b4c_result.candidate_result.prediction_cutoff_sample_index == (
            row_h.first_sample_index - 1
        )
        assert row_h.b4c_result.causal_step.posterior_data_cutoff_sample == row_h.last_sample_index
        assert row_a.b4c_result.candidate_result.metrics.shape == (16,)
        np.testing.assert_allclose(
            row_h.b4c_result.next_state.full_iq,
            [[0.42 * alpha**update_count, 0.91 * alpha**update_count]],
            rtol=0.0,
            atol=1e-14,
        )
        np.testing.assert_allclose(row_a.b4c_result.next_state.full_iq, [initial_full], atol=1e-14)


def test_production_alpha_one_full_trajectory_is_anchor_recenter_invariant() -> None:
    initial_full = (0.42, 0.91)
    historical_state = ReconstructionEstimatorState([initial_full], [initial_full], 0)
    anchored_state = ReconstructionEstimatorState([[0.0, 0.0]], [initial_full], 0)
    historical = run_reconstruction_posterior_estimator_sequence(
        **_sequence_args(
            initial_state=historical_state,
            mu0=(0.0, 0.0),
            alpha=1.0,
            k_tilde=(0.35, -0.2),
        )
    )
    anchored = run_reconstruction_posterior_estimator_sequence(
        **_sequence_args(
            initial_state=anchored_state,
            mu0=initial_full,
            alpha=1.0,
            k_tilde=(0.35, -0.2),
        )
    )
    assert historical.history is not None and anchored.history is not None
    for left, right in zip(historical.history, anchored.history, strict=True):
        np.testing.assert_allclose(left.b4c_result.predicted_iq, right.b4c_result.predicted_iq)
        np.testing.assert_allclose(
            left.b4c_result.candidate_result.metrics,
            right.b4c_result.candidate_result.metrics,
        )
        np.testing.assert_allclose(left.b4c_result.posterior, right.b4c_result.posterior)
        np.testing.assert_allclose(
            left.b4c_result.next_state.full_iq,
            right.b4c_result.next_state.full_iq,
            rtol=0.0,
            atol=1e-14,
        )


def test_nonunit_alpha_with_correction_has_anchor_dependent_full_update() -> None:
    initial = (0.42, 0.91)
    anchor = initial
    alpha = 0.85
    gain = (0.35, -0.2)
    innovation = (0.12, -0.08)

    def scalar_full_update(mu0: tuple[float, float]) -> tuple[float, float]:
        fluctuating = tuple(initial[index] - mu0[index] for index in range(2))
        next_fluctuating = tuple(
            alpha * fluctuating[index] + gain[index] * innovation[index] for index in range(2)
        )
        return tuple(next_fluctuating[index] + mu0[index] for index in range(2))

    zero_anchor = scalar_full_update((0.0, 0.0))
    nonzero_anchor = scalar_full_update(anchor)
    assert zero_anchor != pytest.approx(nonzero_anchor, abs=1e-15)


def test_sequence_receiver_api_has_no_reference_or_channel_truth_operand() -> None:
    parameters = inspect.signature(run_reconstruction_posterior_estimator_sequence).parameters
    assert "reference_bits" not in parameters
    assert "channel_truth" not in parameters
    assert "true_gain" not in parameters
