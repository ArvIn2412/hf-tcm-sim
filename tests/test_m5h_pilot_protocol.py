from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from hf_tcm.evaluation.m5h_pilot_protocol import (
    M5HPilotExecutionBlocked,
    derive_m5h_run_provenance,
    load_m5h_pilot_config,
    run_m5h_pilot,
    validate_m5h_pilot_config,
)


@pytest.fixture
def draft_mapping() -> dict[str, object]:
    path = Path(__file__).parents[1] / "configs/m5h_pilot_draft.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _approved_mapping(candidate: dict[str, object]) -> dict[str, object]:
    from hf_tcm.evaluation.m5h_pilot_protocol import approved_parameter_snapshot

    approved = copy.deepcopy(candidate)
    approved["design_status"] = "approved_for_pilot"
    approved["execution_authorized"] = True
    approved["execution_scope"] = "m5h_pilot_only"
    approved["purpose"] = (
        "authorized independent planning pilot, NOT confirmatory performance evidence, NOT paper-exact receiver, NOT physical HF Eb/N0 comparison"
    )
    approved["source_draft_sha256"] = "a" * 64
    approved["code_fingerprint"] = {"protocol.py": "b" * 64}
    approved["execution_limits"] = {
        "wall_clock_budget_seconds": 1800,
        "rss_ceiling_bytes": 1_610_612_736,
        "resource_poll_interval_seconds": 0.25,
        "available_memory_before_bytes": 5_714_800_000,
        "available_memory_measurement": "Windows GlobalMemoryStatusEx",
        "decoding_workers": 1,
        "output_size_target_bytes": 100 * 1024 * 1024,
        "limit_semantics": "observed by 0.25-second parent monitor; not an OS hard cap",
    }
    approved["authorization_provenance"] = {
        "explicit_user_approval": "explicit user approval through the current Codex execution instruction",
        "design_version": approved["design_version"],
        "source_draft_identifier": "M5h-independent-pilot-candidate",
        "source_draft_sha256": approved["source_draft_sha256"],
        "execution_date_time_utc": "2026-10-29T10:00:00+00:00",
        "code_revision_identifier": None,
        "code_revision_status": "unavailable: workspace is not a Git worktree",
        "code_fingerprint": approved["code_fingerprint"],
    }
    approved["approved_parameter_snapshot"] = approved_parameter_snapshot(approved)
    return approved


def test_draft_config_parses_round_trips_and_has_explicit_candidate_settings(
    draft_mapping: dict[str, object],
) -> None:
    serialized = json.dumps(draft_mapping, sort_keys=True)
    config = validate_m5h_pilot_config(json.loads(serialized))
    assert json.loads(serialized) == draft_mapping
    assert config.design_status == "proposed"
    assert config.execution_authorized is False
    assert config.run_count_per_stratum == 30
    assert config.symbols_per_run == 256
    assert config.samples_per_symbol == 8
    assert config.gamma_grid_db == (0.0, 5.0, 10.0, 15.0)
    assert config.primary_gamma_db == 5.0
    assert config.b_policy == {
        "alpha_prime": 1.0,
        "K_tilde": (0.0, 0.0),
        "mu0": (0.0, 0.0),
    }
    assert config.c_policy == {
        "alpha_prime": 0.85,
        "K_tilde": (0.35, -0.2),
        "mu0": (0.0, 0.0),
    }


def test_approved_run_config_requires_explicit_scope_provenance_and_snapshot(
    draft_mapping: dict[str, object],
) -> None:
    from hf_tcm.evaluation.m5h_pilot_protocol import validate_m5h_pilot_config

    approved = validate_m5h_pilot_config(_approved_mapping(draft_mapping))
    assert approved.design_status == "approved_for_pilot"
    assert approved.execution_authorized is True
    assert approved.execution_scope == "m5h_pilot_only"
    invalid = _approved_mapping(draft_mapping)
    invalid["approved_parameter_snapshot"]["symbols_per_run_F"] = 128
    with pytest.raises(ValueError, match="parameter snapshot"):
        validate_m5h_pilot_config(invalid)


def test_sigma_conversion_and_resource_counts_match_candidate(
    draft_mapping: dict[str, object],
) -> None:
    config = validate_m5h_pilot_config(draft_mapping)
    for stratum in config.strata:
        expected = 4 * config.real_channel_gain**2 / 10 ** (stratum.gamma_db / 10)
        assert math.isclose(stratum.sigma_squared, expected, rel_tol=1e-14)
    assert config.stratum(5.0).sigma_squared == pytest.approx(0.7115124735378853)
    assert config.workload == {
        "independent_sequences": 120,
        "tcm_symbols": 30_720,
        "information_bits": 61_440,
        "received_samples": 245_760,
        "decoder_passes_minimum": 240,
    }


def test_seed_provenance_is_deterministic_unique_and_namespace_separated(
    draft_mapping: dict[str, object],
) -> None:
    config = validate_m5h_pilot_config(draft_mapping)
    first = derive_m5h_run_provenance(config)
    second = derive_m5h_run_provenance(config)
    assert first == second
    assert len(first) == 120
    assert len({item.run_id for item in first}) == 120
    assert len({(item.stratum_id, item.run_index) for item in first}) == 120
    assert len({item.data_seed for item in first}) == 120
    assert len({item.noise_seed for item in first}) == 120
    assert not {item.data_seed for item in first} & {item.noise_seed for item in first}
    assert all(item.study_partition == "pilot" for item in first)
    assert all(item.sample_origin == 0 and item.symbol_origin == 0 for item in first)
    assert all(item.estimator_time_origin == 0 for item in first)
    assert all(item.bootstrap_seed not in {item.data_seed, item.noise_seed} for item in first)
    evaluation = derive_m5h_run_provenance(config, partition="evaluation")
    assert not {item.run_id for item in first} & {item.run_id for item in evaluation}
    assert not {item.data_seed for item in first} & {item.data_seed for item in evaluation}
    assert not {item.noise_seed for item in first} & {item.noise_seed for item in evaluation}
    assert {item.study_partition for item in evaluation} == {"evaluation"}


def test_missing_explicit_setting_is_rejected(draft_mapping: dict[str, object]) -> None:
    incomplete = copy.deepcopy(draft_mapping)
    del incomplete["sample_origins"]
    with pytest.raises(ValueError, match="sample_origins"):
        validate_m5h_pilot_config(incomplete)


def test_duplicate_run_id_is_rejected(draft_mapping: dict[str, object]) -> None:
    invalid = copy.deepcopy(draft_mapping)
    invalid["run_id_template"] = "same-id"
    with pytest.raises(ValueError, match="unique|run ID|run_id"):
        validate_m5h_pilot_config(invalid)


def test_unauthorized_draft_blocks_before_decoder_callback(
    draft_mapping: dict[str, object],
) -> None:
    config = validate_m5h_pilot_config(draft_mapping)
    calls = 0

    def spy(_request: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("decoder callback must not be reached")

    with pytest.raises(M5HPilotExecutionBlocked, match="execution_authorized"):
        run_m5h_pilot(config, execute_run=spy)
    assert calls == 0


def test_proposed_design_blocks_even_if_authorization_boolean_is_changed(
    draft_mapping: dict[str, object],
) -> None:
    candidate = copy.deepcopy(draft_mapping)
    candidate["execution_authorized"] = True
    with pytest.raises(ValueError, match="proposed config"):
        validate_m5h_pilot_config(candidate)


def test_invalid_design_status_and_adr014_contract_are_rejected(
    draft_mapping: dict[str, object],
) -> None:
    invalid_status = copy.deepcopy(draft_mapping)
    invalid_status["design_status"] = "invalid"
    with pytest.raises(ValueError, match="design_status"):
        validate_m5h_pilot_config(invalid_status)
    invalid_bootstrap = copy.deepcopy(draft_mapping)
    invalid_bootstrap["bootstrap_contract"]["replicates"] = 1000
    with pytest.raises(ValueError, match="ADR-014|bootstrap"):
        validate_m5h_pilot_config(invalid_bootstrap)


def test_seed_namespace_conflict_and_missing_b_c_parity_are_rejected(
    draft_mapping: dict[str, object],
) -> None:
    conflict = copy.deepcopy(draft_mapping)
    conflict["seed_derivation"]["namespace_scheme"]["evaluation"]["data"] = 2026102901
    with pytest.raises(ValueError, match="roots conflict"):
        validate_m5h_pilot_config(conflict)
    parity = copy.deepcopy(draft_mapping)
    parity["receiver_policies"]["C"]["beta_shared"] = 0.6
    with pytest.raises(ValueError, match="parity"):
        validate_m5h_pilot_config(parity)


def test_stratum_and_sample_rate_must_be_valid(draft_mapping: dict[str, object]) -> None:
    invalid_sigma = copy.deepcopy(draft_mapping)
    invalid_sigma["run_design"]["gamma_grid"][1]["sigma_squared"] *= 2
    with pytest.raises(ValueError, match="ADR-015"):
        validate_m5h_pilot_config(invalid_sigma)
    invalid_sps = copy.deepcopy(draft_mapping)
    invalid_sps["sample_origins"]["samples_per_symbol"] = 7
    with pytest.raises(ValueError, match="8 samples/symbol"):
        validate_m5h_pilot_config(invalid_sps)


def test_failure_record_is_retained_and_pooled_metrics_are_blocked(
    draft_mapping: dict[str, object],
) -> None:
    config = validate_m5h_pilot_config(_approved_mapping(draft_mapping))
    callback_calls = 0

    def failing_run(_request: object) -> object:
        nonlocal callback_calls
        callback_calls += 1
        raise ArithmeticError("decoder produced non-finite path metric")

    result = run_m5h_pilot(config, execute_run=failing_run)
    assert callback_calls == 120
    assert len(result.failure_records) == 120
    assert result.failure_records[0].exception_type == "ArithmeticError"
    assert result.pooled_metrics_status == "blocked_numerical_failures"
    assert result.completed_records == ()


def test_resume_skips_only_unique_known_completed_run_ids(
    draft_mapping: dict[str, object],
) -> None:
    config = validate_m5h_pilot_config(_approved_mapping(draft_mapping))
    from hf_tcm.evaluation.m5h_pilot_protocol import derive_m5h_run_provenance

    first_id = derive_m5h_run_provenance(config)[0].run_id
    calls: list[str] = []
    checkpoints: list[str] = []

    def execute(request: object) -> object:
        calls.append(request.provenance.run_id)
        return {"status": "stub"}

    def checkpoint(provenance: object, _status: str, _record: object) -> None:
        checkpoints.append(provenance.run_id)

    result = run_m5h_pilot(
        config,
        execute_run=execute,
        completed_run_ids=(first_id,),
        on_checkpoint=checkpoint,
    )
    assert result.skipped_run_count == 1
    assert len(calls) == len(checkpoints) == 119
    assert first_id not in calls
    assert result.status == "complete"


def test_resume_rejects_duplicate_or_unknown_run_ids_before_executor(
    draft_mapping: dict[str, object],
) -> None:
    config = validate_m5h_pilot_config(_approved_mapping(draft_mapping))
    calls = 0

    def execute(_request: object) -> object:
        nonlocal calls
        calls += 1
        return None

    with pytest.raises(M5HPilotExecutionBlocked, match="duplicate completed"):
        run_m5h_pilot(config, execute_run=execute, completed_run_ids=("x", "x"))
    with pytest.raises(M5HPilotExecutionBlocked, match="unknown completed"):
        run_m5h_pilot(config, execute_run=execute, completed_run_ids=("unknown",))
    assert calls == 0


def test_reference_data_is_not_a_pilot_config_operand(
    draft_mapping: dict[str, object],
) -> None:
    config = validate_m5h_pilot_config(draft_mapping)
    provenance = derive_m5h_run_provenance(config)[0]
    assert not hasattr(provenance, "reference_information_bits")
    assert not hasattr(provenance, "channel_truth")


def test_loader_reads_checked_in_draft() -> None:
    path = Path(__file__).parents[1] / "configs/m5h_pilot_draft.json"
    config = load_m5h_pilot_config(path)
    assert config.study_id == "M5h-independent-pilot-candidate"
