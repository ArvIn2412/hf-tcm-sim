from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from test_matched_m2_b5_experiment import _configuration, _reference_bits

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.evaluation.error_metrics import (
    count_bit_errors,
    count_symbol_errors,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
)
from hf_tcm.evaluation.m5i_confirmatory_design import load_m5i_confirmatory_design
from hf_tcm.evaluation.m7b_train_runner import (
    M7BExecutionBlocked,
    _train_manifest,
    create_approved_m7b_config,
    guard_m7b_execution,
    independent_verify,
    run_policy_grid_on_received,
    validate_m7b_approved_config,
)
from hf_tcm.evaluation.reconstruction_adaptive_diagnostics import (
    run_adaptive_estimator_diagnostic,
)
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import symbols_to_iq_waveform
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER

ROOT = Path(__file__).parents[1]


def _approved_config() -> dict[str, object]:
    draft = json.loads((ROOT / "configs/m7a_policy_study_draft.json").read_text())
    value = copy.deepcopy(draft)
    value["design_status"] = "approved_training"
    value["execution_authorized"] = True
    value["execution_scope"] = "m7b_train_only"
    value["authorization_provenance"] = {
        "explicit_user_authorization": "explicit user authorization supplied through this Codex M7b instruction"
    }
    value["execution_limits"] = {
        "wall_clock_limit_seconds": 900,
        "rss_monitoring_budget_bytes": 1610612736,
        "worker_processes": 1,
        "multiprocessing": False,
    }
    value["runtime_provenance"] = {
        "draft_sha256": hashlib.sha256(
            (ROOT / "configs/m7a_policy_study_draft.json").read_bytes()
        ).hexdigest(),
        "approved_config_sha256": "test-fingerprint",
        "code_fingerprint": {"test": "fingerprint"},
        "git_revision": None,
        "reconstruction_configuration": load_m5i_confirmatory_design(
            ROOT / "configs/m5i_confirmatory_design_draft.json"
        ).as_dict()["reconstruction_configuration"],
    }
    value["output"] = {
        "experiment_id": "m7_reconstructed_estimator_policy_study_v1",
        "namespace": "outputs/m7b_train/m7_reconstructed_estimator_policy_study_v1",
        "schema_version": "m7b.train.v1",
    }
    return value


def test_approved_guard_rejects_before_rng_or_receiver_callbacks() -> None:
    value = _approved_config()
    value["execution_authorized"] = False
    calls: list[str] = []
    with pytest.raises(M7BExecutionBlocked, match="approved_training"):
        guard_m7b_execution(
            value,
            draft=json.loads((ROOT / "configs/m7a_policy_study_draft.json").read_text()),
            callbacks={
                name: lambda: calls.append(name) for name in ("rng", "data", "noise", "receiver")
            },
            executor=lambda: calls.append("executor"),
        )
    assert calls == []


def test_direct_nine_policy_orchestrator_matches_existing_b_and_c_api(monkeypatch) -> None:
    import hf_tcm.evaluation.reconstruction_adaptive_diagnostics as diagnostics

    count = 4
    bits = _reference_bits(count)
    symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    labels = [index_to_label(int(index), profile=BASELINE_ASSUMPTION) for index in symbols]
    baseband = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
    i_wave, q_wave = symbols_to_iq_waveform(baseband, samples_per_symbol=8)
    noise = np.asarray(
        [complex((index - 13) / 1000, (index % 5 - 2) / 1500) for index in range(32)],
        dtype=np.complex128,
    )
    received = 0.75 * (i_wave + 1j * q_wave) + noise
    config = _configuration(0.75, origin=23, initial_time=41)
    initial = ReconstructionEstimatorState([[0.42, 0.91]], [[0.42, 0.91]], 41)
    public = run_adaptive_estimator_diagnostic(
        run_id="m7b-equivalence-fixture",
        reference_information_bits=bits,
        real_channel_gain=0.75,
        sigma_squared=0.08,
        noise=noise,
        noise_seed=None,
        noise_stream_id=None,
        noise_provenance="pre-existing deterministic unit fixture",
        symbol_origin_sample=23,
        first_symbol_index=5,
        initial_estimator_time_index=41,
        configuration=config,
        mismatched_initial_state=initial,
        adaptive_alpha_prime=0.85,
        adaptive_k_tilde=np.asarray([[0.35, -0.2]]),
        adaptive_mu0=np.asarray([[0.0, 0.0]]),
        receiver_mode="monolithic",
        segment_partition=None,
    )

    calls: list[int] = []
    b4d_calls: list[dict[str, object]] = []
    original_decoder = diagnostics.decode_reconstruction_viterbi
    original_b4d = diagnostics.run_reconstruction_posterior_estimator_sequence

    def decoder_spy(*args, **kwargs):
        calls.append(1)
        return original_decoder(*args, **kwargs)

    def b4d_spy(**kwargs):
        b4d_calls.append(kwargs)
        return original_b4d(**kwargs)

    monkeypatch.setattr(diagnostics, "decode_reconstruction_viterbi", decoder_spy)
    monkeypatch.setattr(diagnostics, "run_reconstruction_posterior_estimator_sequence", b4d_spy)
    result = run_policy_grid_on_received(
        run_id="m7b-equivalence-fixture",
        received=received,
        reference_information_bits=bits,
        real_channel_gain=0.75,
        configuration=config,
        initial_state=initial,
        beta=0.7,
        symbol_origin_sample=23,
        first_symbol_index=5,
        initial_estimator_time_index=41,
    )
    assert len(calls) == 9
    assert len(b4d_calls) == 9
    assert all("reference_information_bits" not in call for call in b4d_calls)
    assert all("real_channel_gain" not in call and "ChannelTruth" not in call for call in b4d_calls)
    assert all(np.array_equal(call["received"], b4d_calls[0]["received"]) for call in b4d_calls)
    assert len(result) == 9
    assert result["a100_k000"].received_sha256 == public.received_sha256
    assert result["a085_k100"].received_sha256 == public.received_sha256
    for candidate_id, expected in (
        ("a100_k000", public.mismatched_frozen),
        ("a085_k100", public.mismatched_adaptive),
    ):
        actual = result[candidate_id]
        assert np.array_equal(actual.candidate_metrics, expected.candidate_metrics)
        assert np.array_equal(actual.posterior_history, expected.posterior_history)
        assert actual.decoded_hypothesis_path == expected.decoded_hypothesis_path
        assert np.array_equal(actual.decoded_information_bits, expected.decoded_information_bits)
        assert actual.evaluation.counts == expected.evaluation.counts
        assert np.array_equal(actual.final_state.full_iq, expected.final_state.full_iq)
        assert np.array_equal(
            actual.final_state.fluctuating_iq, expected.final_state.fluctuating_iq
        )
        assert tuple(row.estimator_time_index for row in actual.history) == tuple(
            row.estimator_time_index for row in expected.history
        )
        assert tuple(row.prediction_cutoff_sample_index for row in actual.history) == tuple(
            row.prediction_cutoff_sample_index for row in expected.history
        )
        assert np.array_equal(actual.initial_state.full_iq, expected.initial_state.full_iq)
        assert np.array_equal(
            actual.initial_state.fluctuating_iq, expected.initial_state.fluctuating_iq
        )
        assert np.allclose(actual.history[0].predicted_iq, expected.history[0].predicted_iq)
        assert np.allclose(
            actual.history[-1].pre_state.full_iq, expected.history[-1].pre_state.full_iq
        )
        assert np.allclose(
            actual.history[-1].post_state.full_iq, expected.history[-1].post_state.full_iq
        )
        assert np.allclose(actual.history[-1].full_increment, expected.history[-1].full_increment)
        assert np.allclose(actual.history[-1].posterior, expected.history[-1].posterior)
        assert actual.decoder_result.best_path_metric == expected.decoder_result.best_path_metric


def test_approved_config_freezes_exact_draft_and_train_only_seed_manifest() -> None:
    draft_path = ROOT / "configs/m7a_policy_study_draft.json"
    original = draft_path.read_bytes()
    draft = json.loads(original)
    m5i = load_m5i_confirmatory_design(
        ROOT / "configs/m5i_confirmatory_design_draft.json"
    ).as_dict()
    artifact_dir = ROOT / "tmp" / "m7b-approved-config-test"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    path = artifact_dir / "approved.json"
    try:
        approved = create_approved_m7b_config(
            draft=draft,
            reconstruction_configuration=m5i["reconstruction_configuration"],
            output_path=path,
        )
        validated = validate_m7b_approved_config(
            approved,
            draft=draft,
            approved_config_path=path,
        )
        assert validated["execution_scope"] == "m7b_train_only"
        assert draft_path.read_bytes() == original
        assert len(approved["run_manifest"]["runs"]) == 40
        first = approved["run_manifest"]["runs"][0]
        expected = np.random.SeedSequence(
            2026120101, spawn_key=(1295337521, 701, 0, 11)
        ).generate_state(1, dtype=np.uint64)[0]
        assert first["run_id"] == "m7_reconstructed_estimator_policy_study_v1:train:run-001"
        assert first["streams"]["data"]["derived_seed"] == int(expected)
        assert set(first["streams"]) == {"data", "noise", "experiment_metadata"}
        assert (
            approved["runtime_provenance"]["draft_file_sha256"]
            == hashlib.sha256(original).hexdigest()
        )
        assert approved["execution_limits"]["wall_clock_limit_seconds"] == 900
    finally:
        path.unlink(missing_ok=True)
        Path(f"{path}.sha256").unlink(missing_ok=True)
        artifact_dir.rmdir()


def test_m7a_grid_is_exact_and_reserved_validation_roots_are_not_derived() -> None:
    draft = json.loads((ROOT / "configs/m7a_policy_study_draft.json").read_text())
    policies = draft["policy_grid"]["candidate_policies"]
    assert len(policies) == 9
    assert [row["candidate_id"] for row in policies] == [
        "a100_k000",
        "a100_k050",
        "a100_k100",
        "a095_k000",
        "a095_k050",
        "a095_k100",
        "a085_k000",
        "a085_k050",
        "a085_k100",
    ]
    manifest = _train_manifest(draft)
    assert len(manifest["runs"]) == 40
    assert all(
        run["run_id"].endswith(f"run-{index:03d}")
        for index, run in enumerate(manifest["runs"], start=1)
    )
    assert all(
        set(run["streams"]) == {"data", "noise", "experiment_metadata"} for run in manifest["runs"]
    )
    assert "validation" not in json.dumps(manifest).lower()


def test_independent_verification_pools_synthetic_counts_and_applies_tie_breaks() -> None:
    draft = json.loads((ROOT / "configs/m7a_policy_study_draft.json").read_text())
    artifact_dir = ROOT / "tmp" / "m7b-independent-verifier-test"
    checkpoint_dir = artifact_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=False)
    reference_bits = np.zeros(512, dtype=np.int8)
    reference_symbols = encode_reference_symbol_indices(
        reference_bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    for run_index in range(1, 41):
        records = []
        for candidate_index, policy in enumerate(draft["policy_grid"]["candidate_policies"]):
            decoded_bits = reference_bits.copy()
            decoded_bits[:candidate_index] = 1
            state = (0, 0)
            path = []
            for pair in decoded_bits.reshape(-1, 2):
                input_pair = tuple(int(bit) for bit in pair)
                hypothesis = next(
                    item
                    for item in HYPOTHESES
                    if item.current_state == state and item.input_bits == input_pair
                )
                path.append(hypothesis.hypothesis_id)
                state = hypothesis.next_state
            decoded_symbols = decoded_path_symbol_indices(
                path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
            )
            bit_errors = count_bit_errors(reference_bits, decoded_bits)
            symbol_errors = count_symbol_errors(reference_symbols, decoded_symbols)
            records.append(
                {
                    "candidate_id": policy["candidate_id"],
                    "alpha_prime": policy["alpha_prime"],
                    "k_scale": policy["k_scale"],
                    "k_tilde": policy["k_tilde"],
                    "status": "complete_valid_output",
                    "decoder_invocations": 1,
                    "received_sha256": hashlib.sha256(f"received-{run_index}".encode()).hexdigest(),
                    "counts": {
                        "bit_errors": bit_errors,
                        "total_bits": 512,
                        "symbol_errors": symbol_errors,
                        "total_symbols": 256,
                    },
                    "decoded_information_bits": decoded_bits.tolist(),
                    "decoded_symbol_indices": decoded_symbols.tolist(),
                    "decoded_hypothesis_path": path,
                }
            )
        checkpoint = {
            "run_id": f"{draft['study_id']}:train:run-{run_index:03d}",
            "run_index": run_index,
            "seed_provenance": _train_manifest(draft)["runs"][run_index - 1]["streams"],
            "status": "complete",
            "received_sha256": records[0]["received_sha256"],
            "decoder_invocations": 9,
            "evaluation_only": {
                "reference_information_bits": reference_bits.tolist(),
                "reference_symbol_indices": reference_symbols.tolist(),
            },
            "policies": records,
        }
        (checkpoint_dir / f"run-{run_index:03d}.json").write_text(json.dumps(checkpoint))
    try:
        result = independent_verify(artifact_dir, draft)
        assert result["status"] == "TRAIN_SELECTED_NOT_VALIDATED"
        assert (
            result["run_count"]
            == result["unique_run_ids"]
            == result["unique_received_hashes"]
            == 40
        )
        assert result["decoder_invocations"] == 360
        assert result["policy_totals"][0]["bit_errors"] == 0
        assert result["selected_candidate_id"] == "a100_k000"
        assert [row["candidate_id"] for row in result["ranking"]] == [
            row["candidate_id"] for row in draft["policy_grid"]["candidate_policies"]
        ]
    finally:
        for path in checkpoint_dir.glob("*.json"):
            path.unlink()
        checkpoint_dir.rmdir()
        artifact_dir.rmdir()
