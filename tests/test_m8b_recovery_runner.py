from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.evaluation.error_metrics import encode_reference_symbol_indices
from hf_tcm.evaluation.m5i_confirmatory_design import load_m5i_confirmatory_design
from hf_tcm.evaluation.m8b_recovery_runner import (
    ORIGINAL_APPROVED,
    ORIGINAL_OUTPUT,
    M8BRecoveryBlocked,
    _policy_call,
    create_approved_recovery_config,
    guard_recovery_execution,
    require_original_received_hash,
    resolve_clock_origins,
    validate_recovery_config,
)
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER


def test_recovery_module_exposes_explicit_clock_resolution_before_replay() -> None:
    spec = importlib.util.find_spec("hf_tcm.evaluation.m8b_recovery_runner")
    assert spec is not None, "M8b recovery needs an isolated, testable recovery runner"


ROOT = Path(__file__).resolve().parents[1]
DRAFT_PATH = ROOT / "configs/m8a_anchored_study_draft.json"


def _draft() -> dict[str, object]:
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def _receiver_config() -> dict[str, object]:
    return load_m5i_confirmatory_design(
        ROOT / "configs/m5i_confirmatory_design_draft.json"
    ).as_dict()["reconstruction_configuration"]


def test_clock_root_cause_has_exact_api_based_resolution() -> None:
    draft = _draft()
    receiver_config = _receiver_config()
    assert "clock_origins" not in draft
    with pytest.raises(KeyError, match="clock_origins"):
        draft["clock_origins"]
    origins = resolve_clock_origins(draft, receiver_config)
    assert origins["absolute_sample_origin"] == 0
    assert origins["absolute_symbol_origin"] == 0
    assert origins["estimator_time_index_origin"] == 0
    assert origins["provenance"]["m8a_explicit_clock_origins_field"] is False
    assert "B4d new_independent_sequence" in origins["provenance"]["symbol_origin"]


def test_clock_resolution_rejects_nonzero_config_origin_without_fallback() -> None:
    config = copy.deepcopy(_receiver_config())
    config["timebase"]["symbol_origin_sample"] = 3
    with pytest.raises(M8BRecoveryBlocked, match="zero sample/tick origins"):
        resolve_clock_origins(_draft(), config)


def test_recovery_snapshot_reuses_exact_original_design_seeds_and_hashes() -> None:
    draft_bytes = DRAFT_PATH.read_bytes()
    original_config_bytes = ORIGINAL_APPROVED.read_bytes()
    original_summary_bytes = (ORIGINAL_OUTPUT / "summary.json").read_bytes()
    target = ROOT / "configs/m8b_train_recovery_test_snapshot.json"
    sidecar = Path(f"{target}.sha256")
    assert not target.exists() and not sidecar.exists()
    try:
        approved = create_approved_recovery_config(output_config_path=target)
        validate_recovery_config(approved, config_path=target)
    finally:
        target.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
    assert DRAFT_PATH.read_bytes() == draft_bytes
    assert ORIGINAL_APPROVED.read_bytes() == original_config_bytes
    assert (ORIGINAL_OUTPUT / "summary.json").read_bytes() == original_summary_bytes
    assert approved["design_status"] == "approved_training_recovery"
    assert approved["execution_scope"] == "m8b_train_recovery_only"
    assert approved["execution_authorized"] is True
    assert approved["recovery_provenance"]["original_decoder_calls"] == 0
    assert len(approved["run_manifest"]["runs"]) == 40
    assert approved["run_manifest"] == json.loads(original_config_bytes)["run_manifest"]
    assert approved["output"]["namespace"].endswith("_attempt2")
    assert approved["runtime_provenance"]["current_source_fingerprint_sha256"]


def test_unauthorized_recovery_blocks_before_rng_and_receiver_callbacks() -> None:
    callbacks: list[str] = []
    invalid = {
        "design_status": "approved_training",
        "execution_authorized": True,
        "execution_scope": "m8b_train_only",
    }
    with pytest.raises(Exception):
        guard_recovery_execution(
            invalid,
            callbacks={
                name: lambda name=name: callbacks.append(name) for name in ("rng", "receiver")
            },
            executor=lambda: callbacks.append("executor"),
        )
    assert callbacks == []


def test_received_replay_hash_mismatch_is_a_hard_predecode_gate() -> None:
    with pytest.raises(Exception, match="RECEIVED_REPLAY_MISMATCH"):
        require_original_received_hash("run-001", "a" * 64, "b" * 64)
    require_original_received_hash("run-001", "a" * 64, "a" * 64)


def test_real_m8b_conditional_decode_smoke_for_all_eight_policies(monkeypatch) -> None:
    import hf_tcm.receiver.reconstruction_conditional_decode as conditional_module
    from hf_tcm.evaluation.m8b_recovery_runner import RECOVERY_OUTPUT

    draft = _draft()
    receiver_config = _receiver_config()
    clocks = resolve_clock_origins(draft, receiver_config)
    bits = np.asarray([0, 1, 1, 0, 0, 0, 1, 1], dtype=np.int8)
    symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    received = np.asarray(
        [complex((index - 15) / 90.0, ((index % 5) - 2) / 110.0) for index in range(32)],
        dtype=np.complex128,
    )
    received.setflags(write=False)
    received_hash = hashlib.sha256(received.tobytes()).hexdigest()
    original_conditional = conditional_module.decode_reconstruction_viterbi
    decoder_calls: list[int] = []

    def decoder_spy(*args, **kwargs):
        decoder_calls.append(1)
        return original_conditional(*args, **kwargs)

    monkeypatch.setattr(conditional_module, "decode_reconstruction_viterbi", decoder_spy)
    import hf_tcm.evaluation.m8b_recovery_runner as recovery

    original_api = recovery.decode_reconstruction_conditional_sequence
    from hf_tcm.evaluation.m7b_train_runner import _historical_tree_hash

    recovery_output_hash_before = _historical_tree_hash(RECOVERY_OUTPUT)
    captured_calls: list[dict[str, object]] = []
    captured_results = []

    def conditional_spy(**kwargs):
        captured_calls.append(kwargs)
        result = original_api(**kwargs)
        captured_results.append(result)
        return result

    monkeypatch.setattr(recovery, "decode_reconstruction_conditional_sequence", conditional_spy)
    records = [
        _policy_call(
            policy=policy,
            received=received,
            reference_bits=bits,
            reference_symbols=symbols,
            received_hash=received_hash,
            receiver_configuration=receiver_config,
            clock_origins=clocks,
            true_gain_for_evaluation=0.75,
        )
        for policy in draft["policy_grid"]["candidate_policies"]
    ]
    assert len(records) == 8
    assert decoder_calls == [1] * 8
    assert len(captured_calls) == 8
    assert all("reference_bits" not in call and "true_gain" not in call for call in captured_calls)
    assert all(
        "channel_truth" not in call and "ChannelTruth" not in call for call in captured_calls
    )
    assert all(record["status"] == "complete_valid_output" for record in records)
    assert all(record["counts"]["total_bits"] == 8 for record in records)
    assert all(record["counts"]["total_symbols"] == 4 for record in records)
    assert all(record["received_sha256"] == received_hash for record in records)
    assert all(record["candidate_metrics_shape"] == [4, 16] for record in records)
    for policy, record, invocation in zip(
        draft["policy_grid"]["candidate_policies"], records, captured_calls, strict=True
    ):
        assert record["mu0"] == next(
            p["mu0"]
            for p in draft["policy_grid"]["candidate_policies"]
            if p["candidate_id"] == record["candidate_id"]
        )
        assert record["initial_full_iq"] == [0.42, 0.91]
        assert np.asarray(invocation["mu0"]).tolist() == [policy["mu0"]]
        assert invocation["initial_estimator_state"].full_iq.tolist() == [policy["initial_full_iq"]]
        assert invocation["initial_estimator_state"].fluctuating_iq.tolist() == [
            policy["initial_fluctuating_iq"]
        ]
        assert len(record["metric_clock_provenance"]) == 4
        for local, provenance in enumerate(record["metric_clock_provenance"]):
            assert provenance["absolute_symbol_index"] == local
            assert provenance["estimator_time_index"] == local
            assert provenance["sample_indices"] == list(range(local * 8, local * 8 + 8))
            assert provenance["prediction_cutoff_sample_index"] == local * 8 - 1
            assert provenance["observation_cutoff_sample_index"] == local * 8 + 7
            assert provenance["hypothesis_ids"] == list(range(16))
    # Compare the orchestrator adapter with direct existing API invocations on
    # the same deterministic fixture for anchored and historical frozen arms.
    for index in (0, 6):
        kwargs = captured_calls[index]
        direct = original_api(**kwargs)
        orchestrated = captured_results[index]
        assert np.array_equal(
            direct.decoder_result.decoded_bits, orchestrated.decoder_result.decoded_bits
        )
        assert direct.decoder_result.hypothesis_ids == orchestrated.decoder_result.hypothesis_ids
        assert np.array_equal(direct.candidate_metrics, orchestrated.candidate_metrics)
        assert np.array_equal(
            direct.final_estimator_state.full_iq, orchestrated.final_estimator_state.full_iq
        )
        assert direct.final_estimator_state.time_index == 4
        assert np.allclose(
            direct.final_estimator_state.fluctuating_iq + np.asarray(kwargs["mu0"]),
            direct.final_estimator_state.full_iq,
            rtol=0.0,
            atol=1e-14,
        )
    assert decoder_calls == [1] * 10
    assert _historical_tree_hash(RECOVERY_OUTPUT) == recovery_output_hash_before
