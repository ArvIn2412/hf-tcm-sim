from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.evaluation.m7a_policy_study_design import (
    M7AExecutionBlocked,
    guard_m7a_execution,
    load_m7a_policy_study,
    validate_m7a_policy_study,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/m7a_policy_study_draft.json"
M6G_TRACE = ROOT / "outputs/m6g_multistep_feedback_audit/deterministic_trace.json"
M6H_TRACE = ROOT / "outputs/m6h_posterior_clamp/deterministic_trace.json"


def _draft() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_draft_is_valid_and_contains_exact_nine_fixed_policies() -> None:
    design = load_m7a_policy_study(CONFIG_PATH)
    assert design.design_status == "proposed"
    assert design.execution_authorized is False
    assert design.execution_scope == "none"
    assert len(design.candidate_ids) == 9
    assert len(set(design.candidate_ids)) == 9
    assert design.candidate_ids[0] == "a100_k000"
    assert "a085_k100" in design.candidate_ids
    assert design.workload["training_unique_policy_decoder_passes_target"] == 360
    assert design.workload["validation_decoder_passes"] == 80
    assert design.workload["validation_optional_historical_C_decoder_passes"] == 40
    assert design.workload["final_decoder_passes"] == 200
    assert design.workload["final_optional_historical_C_decoder_passes"] == 100
    assert (
        design.workload["training_current_public_helper_passes_if_called_once_per_non_B_candidate"]
        == 640
    )
    policies = _draft()["policy_grid"]["candidate_policies"]
    assert policies[0] == {
        "candidate_id": "a100_k000",
        "alpha_prime": 1.0,
        "k_scale": 0.0,
        "k_tilde": [0.0, 0.0],
        "role": "historical_frozen_B",
    }
    assert policies[-1] == {
        "candidate_id": "a085_k100",
        "alpha_prime": 0.85,
        "k_scale": 1.0,
        "k_tilde": [0.35, -0.2],
        "role": "historical_C",
    }
    for item in policies:
        assert item["k_tilde"] == [0.35 * item["k_scale"], -0.2 * item["k_scale"]]


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("policy_grid", "alpha_prime_values"), [1.0, 0.9, 0.85]),
        (("shared_estimator", "beta"), 0.8),
        (("profile", "sigma_squared"), 0.5),
        (("sequence_design", "symbols_per_run_F"), 128),
        (("partitions", "training", "sequence_count"), 39),
        (("selection", "tie_break_order"), ["candidate_id"]),
        (("failure_policy", "zero_error_imputation"), True),
        (("scientific_status", "paper_exact"), True),
        (("partitions", "historical_data_excluded"), ["M5j"]),
        (("policy_grid", "candidate_policies"), []),
        (("policy_grid", "candidate_policies", 1, "k_tilde"), [0.2, 0.1]),
        (("clock_origins", "estimator_time_index_origin"), 2),
        (("sequence_design", "one_noise_realization_per_run_shared_by_all_policies"), False),
        (("workflow_gates", "validation_to_final_automatic"), True),
        (("resource_policy", "single_process"), False),
        (("design_status",), "approved"),
    ],
)
def test_invalid_design_contract_is_rejected(path, replacement) -> None:
    config = _draft()
    cursor = config
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement
    with pytest.raises(ValueError):
        validate_m7a_policy_study(config)


def test_seed_roots_are_separate_from_each_other_and_historical_partitions() -> None:
    config = _draft()
    config["partitions"]["validation"]["seed_namespaces"]["noise"] = config["partitions"][
        "training"
    ]["seed_namespaces"]["noise"]
    with pytest.raises(ValueError, match="seed namespace"):
        validate_m7a_policy_study(config)

    config = _draft()
    config["partitions"]["final"]["seed_namespaces"]["data"] = 2026110101
    with pytest.raises(ValueError, match="historical M5/M6"):
        validate_m7a_policy_study(config)


def test_execution_guard_blocks_before_rng_or_receiver_callbacks(monkeypatch) -> None:
    calls = {"data": 0, "noise": 0, "decoder": 0}

    def spy(name: str):
        def callback() -> None:
            calls[name] += 1

        return callback

    def forbidden_seed_sequence(*args, **kwargs):
        raise AssertionError("M7a validation must not create RNG streams")

    monkeypatch.setattr(np.random, "SeedSequence", forbidden_seed_sequence)
    callbacks = {name: spy(name) for name in calls}
    with pytest.raises(M7AExecutionBlocked, match="execution is unauthorized"):
        guard_m7a_execution(_draft(), callbacks=callbacks)
    assert calls == {"data": 0, "noise": 0, "decoder": 0}


def test_authorization_mutation_is_rejected_before_callbacks() -> None:
    calls = 0

    def callback() -> None:
        nonlocal calls
        calls += 1

    config = _draft()
    config["execution_authorized"] = True
    with pytest.raises(ValueError, match="draft must remain unauthorized"):
        validate_m7a_policy_study(config)
    with pytest.raises(ValueError, match="draft must remain unauthorized"):
        guard_m7a_execution(config, callbacks={"decoder": callback})
    assert calls == 0


def test_validation_and_final_do_not_chain_automatically() -> None:
    config = _draft()
    assert config["execution_scope"] == "none"
    assert config["workflow_gates"]["train_to_validation_automatic"] is False
    assert config["workflow_gates"]["validation_to_final_automatic"] is False
    assert config["partitions"]["validation"]["uses_new_seed_roots"] is True
    assert config["partitions"]["final"]["uses_new_seed_roots"] is True


def test_validation_does_not_mutate_config_or_trace_files() -> None:
    raw = CONFIG_PATH.read_bytes()
    config = _draft()
    before_config = json.dumps(config, sort_keys=True)
    m6g_before = hashlib.sha256(M6G_TRACE.read_bytes()).hexdigest()
    m6h_before = hashlib.sha256(M6H_TRACE.read_bytes()).hexdigest()
    validate_m7a_policy_study(config)
    assert json.dumps(config, sort_keys=True) == before_config
    assert CONFIG_PATH.read_bytes() == raw
    assert hashlib.sha256(M6G_TRACE.read_bytes()).hexdigest() == m6g_before
    assert hashlib.sha256(M6H_TRACE.read_bytes()).hexdigest() == m6h_before


def test_m6g_and_m6h_historical_traces_keep_recorded_hashes() -> None:
    assert hashlib.sha256(M6G_TRACE.read_bytes()).hexdigest() == (
        "67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75"
    )
    assert hashlib.sha256(M6H_TRACE.read_bytes()).hexdigest() == (
        "14bb8e891f5da49b5374804374e9fd1d28d32cbc74404e062651741708946e9f"
    )
