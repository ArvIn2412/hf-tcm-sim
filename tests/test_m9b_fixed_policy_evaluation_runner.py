from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hf_tcm.evaluation.m9a_fixed_policy_study_design import validate_m9a_fixed_policy_study
from hf_tcm.evaluation.m9b_fixed_policy_evaluation_runner import (
    DRAFT_PATH,
    EXPECTED_DRAFT_SHA256,
    M9BExecutionBlocked,
    _historical_baseline,
    _receiver_configuration,
    build_run_manifest,
    create_approved_m9b_config,
    guard_m9b_execution,
    resolve_m9_clock_origins,
    run_real_integration_smoke,
    validate_approved_m9b,
)


def _draft() -> dict[str, object]:
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def test_m9a_draft_is_frozen_and_seed_manifest_matches_exact_design() -> None:
    draft_bytes = DRAFT_PATH.read_bytes()
    assert hashlib.sha256(draft_bytes).hexdigest() == EXPECTED_DRAFT_SHA256
    draft = _draft()
    design = validate_m9a_fixed_policy_study(draft)
    manifest = build_run_manifest(draft)
    assert [p.candidate_id for p in design.policies] == [
        "historical_frozen_B",
        "anch_a085_k025",
    ]
    assert len(manifest["runs"]) == 100
    assert [row["run_index"] for row in manifest["runs"]] == list(range(100))
    assert manifest["runs"][0]["run_id"].endswith("run-001")
    assert manifest["runs"][-1]["run_id"].endswith("run-100")
    assert manifest["stream_codes"] == {
        "data": 11,
        "noise": 23,
        "bootstrap": 37,
        "metadata": 41,
    }
    assert manifest["runs"][0]["streams"]["data"]["spawn_key"] == [
        1295337521,
        901,
        0,
        11,
    ]
    assert manifest["bootstrap"]["spawn_key"] == [1295337521, 901, 0, 37]
    assert all(
        stream["initialized"] is False
        for row in manifest["runs"]
        for stream in row["streams"].values()
    )
    assert manifest["bootstrap"]["initialized"] is False
    assert DRAFT_PATH.read_bytes() == draft_bytes


def test_m9_clocks_are_resolved_from_m5i_and_b4d_not_assumed_from_draft() -> None:
    draft = _draft()
    assert "clock_origins" not in draft
    clocks = resolve_m9_clock_origins(_receiver_configuration())
    assert clocks.absolute_sample_origin == 0
    assert clocks.absolute_symbol_origin == 0
    assert clocks.estimator_time_index_origin == 0
    assert "B4d new_independent_sequence" in clocks.provenance["symbol_origin"]
    assert "M5i accepted" in clocks.provenance["sample_origin"]
    assert "no default fallback" in clocks.provenance["m9a_clock_origins_field"]


def test_real_receiver_integration_smoke_calls_adapter_and_direct_api(monkeypatch) -> None:
    import hf_tcm.receiver.reconstruction_conditional_decode as conditional_module

    original = conditional_module.decode_reconstruction_viterbi
    calls: list[int] = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(conditional_module, "decode_reconstruction_viterbi", counted)
    result = run_real_integration_smoke(_draft(), _receiver_configuration())
    assert result["status"] == "PASS"
    assert result["experimental_sample_used"] is False
    assert result["initial_predictions_identical"] is True
    assert result["candidate_metrics_shape"] == [4, 16]
    assert result["posterior_shape"] == [16]
    assert result["receiver_arguments_exclude_truth"] is True
    assert result["orchestrator_decodes"] == 2
    assert result["direct_api_comparison_decodes"] == 2
    assert calls == [1, 1, 1, 1]


def test_approved_snapshot_has_m9b_only_scope_and_no_circular_hash(tmp_path: Path) -> None:
    before = _historical_baseline()
    draft_bytes = DRAFT_PATH.read_bytes()
    target = tmp_path / "m9b-approved.json"
    approved = create_approved_m9b_config(draft=_draft(), output_config_path=target)
    assert approved["design_status"] == "approved_evaluation"
    assert approved["execution_authorized"] is True
    assert approved["execution_scope"] == "m9b_evaluation_only"
    assert approved["runtime_provenance"]["m9a_draft_sha256"] == EXPECTED_DRAFT_SHA256
    assert len(approved["run_manifest"]["runs"]) == 100
    assert approved["execution_limits"]["wall_clock_budget_seconds"] == 900
    assert approved["execution_limits"]["rss_monitoring_budget_bytes"] == 1_610_612_736
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    assert Path(f"{target}.sha256").read_text(encoding="ascii").strip() == digest
    validated = validate_approved_m9b(
        approved, draft=_draft(), config_path=target, verify_file=True
    )
    assert validated == approved
    assert _historical_baseline() == before
    assert DRAFT_PATH.read_bytes() == draft_bytes


def test_unauthorized_draft_blocks_before_rng_or_receiver_callbacks() -> None:
    calls: list[str] = []
    callbacks = {
        name: lambda name=name: calls.append(name) for name in ("rng", "receiver", "data", "noise")
    }
    with pytest.raises(M9BExecutionBlocked, match="authorization scope mismatch"):
        guard_m9b_execution(
            _draft(),
            draft=_draft(),
            callbacks=callbacks,
            executor=lambda: calls.append("executor"),
        )
    assert calls == []


def test_approved_guard_rejects_fingerprint_and_policy_drift_before_executor(
    tmp_path: Path,
) -> None:
    approved = create_approved_m9b_config(
        draft=_draft(), output_config_path=tmp_path / "approved.json"
    )
    changed = copy.deepcopy(approved)
    changed["policies"][1]["k_tilde"] = [0.35, -0.2]
    calls: list[str] = []
    callbacks = {name: lambda: calls.append(name) for name in ("rng", "receiver")}
    with pytest.raises(M9BExecutionBlocked, match="scientific design"):
        guard_m9b_execution(
            changed,
            draft=_draft(),
            callbacks=callbacks,
            executor=lambda: calls.append("executor"),
        )
    assert calls == []


def test_generation_contract_is_exactly_two_paired_decodes_without_other_partitions() -> None:
    draft = _draft()
    design = validate_m9a_fixed_policy_study(draft)
    assert design.expected_decoder_calls == 200
    assert design.expected_policy_records == 200
    assert design.expected_received_samples == 204800
    assert draft["partition"]["seed_namespaces"] == {
        "data": 2027020101,
        "noise": 2027020102,
        "bootstrap": 2027020103,
        "metadata": 2027020104,
    }
    assert draft["workload"]["decoder_passes"] == 200
    assert draft["scientific_limitations"]["policy_selected_posthoc_from_M8"] is True
