from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.evaluation.m5i_confirmatory_design import load_m5i_confirmatory_design
from hf_tcm.evaluation.m8a_anchored_study_design import validate_m8a_anchored_study
from hf_tcm.evaluation.m8b_train_runner import (
    M8BExecutionBlocked,
    _m8b_manifest,
    _mode_for_policy,
    create_approved_m8b_config,
    guard_m8b_execution,
    validate_approved_m8b,
)

ROOT = Path(__file__).resolve().parents[1]
DRAFT_PATH = ROOT / "configs/m8a_anchored_study_draft.json"


def _draft() -> dict[str, object]:
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def test_m8b_train_guard_blocks_before_any_execution_callback() -> None:
    value = _draft()
    calls: list[str] = []
    with pytest.raises(M8BExecutionBlocked, match="approved_training"):
        guard_m8b_execution(
            value,
            draft=value,
            callbacks={
                name: lambda name=name: calls.append(name)
                for name in ("rng", "data", "noise", "receiver")
            },
            executor=lambda: calls.append("executor"),
        )
    assert calls == []


def test_approved_config_inherits_exact_m8a_design_and_train_seeds(tmp_path: Path) -> None:
    original = DRAFT_PATH.read_bytes()
    draft = _draft()
    target = tmp_path / "m8b-approved.json"
    approved = create_approved_m8b_config(draft=draft, output_path=target)
    validate_approved_m8b(approved, draft=draft, approved_path=target)
    assert DRAFT_PATH.read_bytes() == original
    assert approved["execution_scope"] == "m8b_train_only"
    assert approved["output"]["schema_version"] == "m8b.train.v1"
    assert len(approved["run_manifest"]["runs"]) == 40
    assert len(draft["policy_grid"]["candidate_policies"]) == 8
    first = approved["run_manifest"]["runs"][0]
    assert first["run_id"].endswith("run-001")
    expected = np.random.SeedSequence(
        2027011001, spawn_key=(1295337521, 801, 0, 11)
    ).generate_state(1, dtype=np.uint64)[0]
    assert first["streams"]["data"]["derived_seed"] == int(expected)
    assert first["streams"]["data"]["instantiated"] is True
    assert first["streams"]["noise"]["instantiated"] is True
    assert first["streams"]["bootstrap"]["instantiated"] is False
    assert approved["run_manifest"]["validation_and_final_seeds_derived"] is False
    assert (
        approved["runtime_provenance"]["m8a_draft_file_sha256"]
        == hashlib.sha256(original).hexdigest()
    )
    assert [p["candidate_id"] for p in draft["policy_grid"]["candidate_policies"]] == [
        "anch_a100_k025",
        "anch_a100_k050",
        "anch_a095_k025",
        "anch_a095_k050",
        "anch_a085_k025",
        "anch_a085_k050",
        "historical_frozen_B",
        "historical_combined_C",
    ]


def test_approved_config_rejects_any_scientific_drift_before_callbacks(tmp_path: Path) -> None:
    draft = _draft()
    approved = copy.deepcopy(draft)
    approved.update(
        design_status="approved_training",
        execution_authorized=True,
        execution_scope="m8b_train_only",
        authorization_provenance={
            "explicit_user_authorization": "explicit user authorization through this M8b TRAIN Codex instruction"
        },
    )
    approved["profile"]["gamma_b_eff_db"] = 6.0
    with pytest.raises(M8BExecutionBlocked):
        validate_approved_m8b(approved, draft=draft, verify_fingerprint=False)


def test_draft_validator_and_fixed_policy_state_decompositions() -> None:
    draft = _draft()
    design = validate_m8a_anchored_study(draft)
    assert len(design.candidates) == 8
    for policy in draft["policy_grid"]["candidate_policies"]:
        full = np.asarray(policy["initial_full_iq"])
        fluctuating = np.asarray(policy["initial_fluctuating_iq"])
        anchor = np.asarray(policy["mu0"])
        np.testing.assert_array_equal(full, fluctuating + anchor)
        np.testing.assert_array_equal(full, np.asarray([0.42, 0.91]))
    assert draft["design_status"] == "proposed"
    assert draft["execution_authorized"] is False
    assert draft["execution_scope"] == "none"


def test_seed_manifest_contains_train_only_unique_stream_provenance() -> None:
    manifest = _m8b_manifest(_draft())
    assert len(manifest["runs"]) == 40
    ids = [row["run_id"] for row in manifest["runs"]]
    assert len(set(ids)) == 40
    assert manifest["partition_code"] == 801
    assert manifest["validation_and_final_seeds_derived"] is False
    assert manifest["reserved_streams_not_instantiated"] == ["bootstrap"]
    assert all(
        set(row["streams"]) == {"data", "noise", "bootstrap", "experiment_metadata"}
        for row in manifest["runs"]
    )


def test_deterministic_receiver_fixture_has_shared_initial_metrics_and_posterior(
    monkeypatch,
) -> None:
    """Small deterministic B4d/B5b fixture validates arm plumbing, not performance."""
    import hf_tcm.evaluation.reconstruction_adaptive_diagnostics as diagnostics

    draft = _draft()
    policies = draft["policy_grid"]["candidate_policies"]
    receiver_config = load_m5i_confirmatory_design(
        ROOT / "configs/m5i_confirmatory_design_draft.json"
    ).as_dict()["reconstruction_configuration"]
    bits = np.asarray([0, 1, 1, 0], dtype=np.int8)
    from hf_tcm.evaluation.error_metrics import encode_reference_symbol_indices
    from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
    from hf_tcm.modulation.psk8 import modulate
    from hf_tcm.receiver.iq import symbols_to_iq_waveform
    from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER

    symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    labels = [index_to_label(int(item), profile=BASELINE_ASSUMPTION) for item in symbols]
    i_wave, q_wave = symbols_to_iq_waveform(
        modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION), samples_per_symbol=8
    )
    received = np.asarray(0.75 * (i_wave + 1j * q_wave), dtype=np.complex128)
    calls: list[int] = []
    original = diagnostics.decode_reconstruction_viterbi

    def spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(diagnostics, "decode_reconstruction_viterbi", spy)
    results = []
    for policy in policies:
        results.append(
            _mode_for_policy(
                policy=policy,
                bits=bits,
                reference_symbols=symbols,
                received=received,
                received_hash=hashlib.sha256(received.tobytes()).hexdigest(),
                configuration=receiver_config,
                gain=0.75,
                beta=0.7,
                sample_origin=0,
                symbol_origin=0,
                time_origin=0,
            )
        )
    assert len(calls) == 8
    for result in results[1:]:
        np.testing.assert_array_equal(
            result.history[0].pre_state.full_iq, results[0].history[0].pre_state.full_iq
        )
        np.testing.assert_allclose(
            result.history[0].predicted_iq, results[0].history[0].predicted_iq, rtol=0.0, atol=1e-12
        )
        np.testing.assert_allclose(
            result.candidate_metrics[0], results[0].candidate_metrics[0], rtol=0.0, atol=1e-12
        )
        np.testing.assert_allclose(
            result.posterior_history[0], results[0].posterior_history[0], rtol=0.0, atol=1e-12
        )
    assert all(result.received_sha256 == results[0].received_sha256 for result in results)
    assert all(len(result.decoded_hypothesis_path) == 2 for result in results)


def test_alpha_one_anchor_recenter_matches_zero_anchor_on_deterministic_input() -> None:
    from hf_tcm.evaluation.error_metrics import encode_reference_symbol_indices
    from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
    from hf_tcm.modulation.psk8 import modulate
    from hf_tcm.receiver.iq import symbols_to_iq_waveform
    from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER

    receiver_config = load_m5i_confirmatory_design(
        ROOT / "configs/m5i_confirmatory_design_draft.json"
    ).as_dict()["reconstruction_configuration"]
    bits = np.asarray([0, 0, 1, 1, 1, 0], dtype=np.int8)
    symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    labels = [index_to_label(int(item), profile=BASELINE_ASSUMPTION) for item in symbols]
    i_wave, q_wave = symbols_to_iq_waveform(
        modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION), samples_per_symbol=8
    )
    received = np.asarray(0.75 * (i_wave + 1j * q_wave), dtype=np.complex128)
    digest = hashlib.sha256(received.tobytes()).hexdigest()
    anchored = {
        "candidate_id": "anchored-control",
        "alpha_prime": 1.0,
        "k_tilde": [0.0875, -0.05],
        "mu0": [0.42, 0.91],
        "initial_fluctuating_iq": [0.0, 0.0],
        "initial_full_iq": [0.42, 0.91],
    }
    zero_anchor = {
        **anchored,
        "candidate_id": "zero-anchor-control",
        "mu0": [0.0, 0.0],
        "initial_fluctuating_iq": [0.42, 0.91],
    }
    modes = [
        _mode_for_policy(
            policy=policy,
            bits=bits,
            reference_symbols=symbols,
            received=received,
            received_hash=digest,
            configuration=receiver_config,
            gain=0.75,
            beta=0.7,
            sample_origin=0,
            symbol_origin=0,
            time_origin=0,
        )
        for policy in (anchored, zero_anchor)
    ]
    np.testing.assert_allclose(
        modes[0].candidate_metrics, modes[1].candidate_metrics, rtol=0.0, atol=1e-12
    )
    np.testing.assert_allclose(
        modes[0].posterior_history, modes[1].posterior_history, rtol=0.0, atol=1e-12
    )
    np.testing.assert_allclose(
        modes[0].final_state.full_iq, modes[1].final_state.full_iq, rtol=0.0, atol=1e-12
    )
    assert modes[0].decoded_hypothesis_path == modes[1].decoded_hypothesis_path


def test_saved_m8b_attempt_stays_incomplete_without_error_imputation() -> None:
    from hf_tcm.evaluation.m8b_train_runner import independent_verify

    output = ROOT / "outputs/m8b_train/m8_anchored_reconstructed_adaptation_v1"
    verification = independent_verify(output, _draft())
    rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((output / "checkpoints").glob("run-*.json"))
    ]
    assert verification["status"] == "TRAIN_INCOMPLETE_OR_BLOCKED"
    assert verification["run_count"] == verification["unique_run_count"] == 40
    assert verification["unique_received_hash_count"] == 40
    assert verification["policy_record_count"] == 320
    assert verification["decoder_invocations"] == 0
    assert verification["selected_candidate_id"] is None
    assert all(
        record["status"] == "numerical_or_decoder_failure"
        for row in rows
        for record in row["policies"]
    )
    assert all(row["pooled_ber"] is None for row in verification["all_policy_totals"])
