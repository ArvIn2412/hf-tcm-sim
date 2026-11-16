from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hf_tcm.evaluation.m10a_variable_gain_study_design import DRAFT_PATH
from hf_tcm.evaluation.m10b_variable_gain_runner import (
    ACCEPTED_DECISION_PATH,
    M10BExecutionBlocked,
    build_run_manifest,
    guard_m10b_execution,
    load_and_validate_accepted_decision,
    run_real_integration_smoke,
    summarize_m10b_checkpoints,
    validate_m10a_draft_fingerprint,
)


def _draft() -> dict[str, object]:
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def test_m10a_draft_fingerprint_and_sidecar_are_unchanged() -> None:
    draft = _draft()
    assert validate_m10a_draft_fingerprint(draft) == (
        "80ec2ea30e04bfeb02508380b94f29bb08140a1906fa61816d137ed56798066f"
    )


def test_accepted_adr016_matches_evaluation_only_channel_model() -> None:
    decision = load_and_validate_accepted_decision(_draft(), ACCEPTED_DECISION_PATH)
    assert decision["decision_id"] == "ADR-016"
    assert decision["status"] == "ACCEPTED_EVALUATION_ONLY"
    assert decision["profile_id"] == "controlled_piecewise_real_gain_v1"
    assert decision["receiver_math_changed"] is False


def test_run_manifest_uses_only_frozen_m10a_roots_and_spawn_rule() -> None:
    manifest = build_run_manifest(_draft())
    assert len(manifest["runs"]) == 100
    assert manifest["runs"][0]["run_id"].endswith("run-001")
    assert manifest["runs"][-1]["run_id"].endswith("run-100")
    assert manifest["runs"][0]["streams"]["data"]["spawn_key"] == [
        1295337521,
        1001,
        0,
        11,
    ]
    assert manifest["runs"][99]["streams"]["noise"]["spawn_key"] == [
        1295337521,
        1001,
        99,
        23,
    ]
    assert manifest["bootstrap"]["spawn_key"] == [1295337521, 1001, 0, 37]


def test_unauthorized_or_mismatched_run_blocks_before_rng_or_receiver() -> None:
    calls: list[str] = []
    callbacks = {name: lambda name=name: calls.append(name) for name in ("rng", "receiver")}
    with pytest.raises(M10BExecutionBlocked):
        guard_m10b_execution(
            _draft(),
            accepted_decision=None,
            callbacks=callbacks,
            executor=lambda: calls.append("execute"),
        )
    assert calls == []


def test_real_integration_smoke_runs_all_six_policy_profile_pairs() -> None:
    draft = _draft()
    decision = load_and_validate_accepted_decision(draft, ACCEPTED_DECISION_PATH)
    smoke = run_real_integration_smoke(draft, decision)
    assert smoke["status"] == "PASS"
    assert smoke["profile_policy_invocations"] == 6
    assert smoke["direct_api_comparison_invocations"] == 6
    assert smoke["causal_cutoff_checks"] is True
    assert smoke["receiver_arguments_exclude_truth"] is True
    assert smoke["m8b_clock_origins_regression"] is True


def test_raw_summary_pools_three_profiles_and_joint_bootstrap() -> None:
    records = []
    for index in range(100):
        per_profile = {}
        for profile_index, profile_id in enumerate(
            ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH")
        ):
            b = index % 7 + profile_index
            anchored = b + (profile_index - 1)
            per_profile[profile_id] = {
                "historical_frozen_B": {
                    "bit_errors": b,
                    "symbol_errors": b,
                    "total_bits": 512,
                    "total_symbols": 256,
                },
                "anch_a085_k025": {
                    "bit_errors": anchored,
                    "symbol_errors": anchored,
                    "total_bits": 512,
                    "total_symbols": 256,
                },
            }
        records.append({"run_id": f"unit-{index:03d}", "profiles": per_profile})

    summary = summarize_m10b_checkpoints(records, bootstrap_seed=12345)
    assert summary["cluster_count"] == 100
    assert summary["primary_profile"] == "P1_HIGH_TO_LOW"
    assert summary["bootstrap"]["replicates"] == 2000
    assert summary["bootstrap"]["quantile_method"] == "numpy.quantile(method='linear')"
    assert summary["bootstrap"]["shared_run_index_resampling"] is True
    assert summary["profiles"]["P1_HIGH_TO_LOW"]["delta_bit_errors"] == 0
    assert summary["difference_in_differences"]["P2_minus_P1_delta_ber"] > 0


def test_draft_is_unchanged_by_validation() -> None:
    before = DRAFT_PATH.read_bytes()
    draft = copy.deepcopy(_draft())
    validate_m10a_draft_fingerprint(draft)
    assert DRAFT_PATH.read_bytes() == before
    assert Path(f"{DRAFT_PATH}.sha256").is_file()
