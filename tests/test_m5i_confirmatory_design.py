from __future__ import annotations

import copy
import hashlib
import json
import statistics
from pathlib import Path

import pytest

from hf_tcm.evaluation.m5i_confirmatory_design import (
    M5IExecutionBlocked,
    build_m5i_seed_manifest,
    guard_m5i_execution,
    load_m5i_confirmatory_design,
    validate_m5i_confirmatory_design,
    validate_m5i_seed_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
DRAFT_PATH = ROOT / "configs" / "m5i_confirmatory_design_draft.json"
PILOT_OUTPUT = ROOT / "outputs" / "m5h_independent_pilot" / "20261029T180438711965Z"


def _draft() -> dict[str, object]:
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def test_valid_draft_round_trip_and_immutable_snapshot() -> None:
    design = load_m5i_confirmatory_design(DRAFT_PATH)
    round_trip = validate_m5i_confirmatory_design(json.loads(design.canonical_json))
    assert round_trip.canonical_json == design.canonical_json
    assert round_trip.fingerprint == design.fingerprint
    with pytest.raises((AttributeError, TypeError)):
        design.design_status = "approved"  # type: ignore[misc]


def test_primary_gamma_sigma_and_frozen_workload() -> None:
    design = load_m5i_confirmatory_design(DRAFT_PATH)
    data = design.as_dict()
    assert data["primary_condition"]["gamma_b_eff_db"] == 5.0
    assert data["primary_condition"]["sigma_squared"] == pytest.approx(
        4 * 0.75**2 / 10 ** (5 / 10), abs=1e-15
    )
    assert data["run_design"]["run_count"] == 100
    assert data["run_design"]["symbols_per_run_F"] == 256
    assert data["compute_workload"] == {
        "independent_sequences": 100,
        "tcm_symbols": 25_600,
        "information_bits": 51_200,
        "received_complex_samples": 204_800,
        "decoder_passes_minimum": 200,
    }


def test_b_and_c_have_equal_initial_state_and_fixed_only_policy_difference() -> None:
    data = load_m5i_confirmatory_design(DRAFT_PATH).as_dict()
    assert data["receiver_policies"]["shared"] == {
        "initial_full_iq": [0.42, 0.91],
        "initial_fluctuating_iq": [0.42, 0.91],
        "beta": 0.7,
        "mu0": [0.0, 0.0],
    }
    assert data["receiver_policies"]["B"] == {
        "policy": "frozen",
        "alpha_prime": 1.0,
        "K_tilde": [0.0, 0.0],
        "mu0": [0.0, 0.0],
    }
    assert data["receiver_policies"]["C"] == {
        "policy": "adaptive",
        "alpha_prime": 0.85,
        "K_tilde": [0.35, -0.2],
        "mu0": [0.0, 0.0],
    }
    assert data["pairing_contract"]["only_difference"] == "estimator update policy"


def test_manifest_has_100_deterministic_unique_planned_ids_and_seed_provenance() -> None:
    design = load_m5i_confirmatory_design(DRAFT_PATH)
    first = build_m5i_seed_manifest(design)
    second = build_m5i_seed_manifest(design)
    assert first == second
    validate_m5i_seed_manifest(first, design)
    planned = first["planned_runs"]
    assert len(planned) == 100
    ids = [item["run_id"] for item in planned]
    assert len(ids) == len(set(ids)) == 100
    assert [item["run_index"] for item in planned] == list(range(100))
    assert all(item["stratum_index"] == 1 for item in planned)
    assert all(item["partition"] == "evaluation" for item in planned)
    assert len({item["data"]["derived_seed"] for item in planned}) == 100
    assert len({item["noise"]["derived_seed"] for item in planned}) == 100
    assert not {item["data"]["derived_seed"] for item in planned}.intersection(
        item["noise"]["derived_seed"] for item in planned
    )
    assert set(first["seed_namespace_master_seeds"]) == {
        "data",
        "noise",
        "bootstrap",
    }
    assert first["seed_namespace_master_seeds"] == {
        "data": 2026110101,
        "noise": 2026110102,
        "bootstrap": 2026110103,
    }


def test_saved_planned_manifest_passes_exact_design_and_code_validation() -> None:
    design = load_m5i_confirmatory_design(DRAFT_PATH)
    manifest_path = ROOT / "configs" / "m5i_confirmatory_run_manifest_draft.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_m5i_seed_manifest(manifest, design)
    assert (
        manifest["manifest_status"]
        == "planned IDs and seed provenance only; no data/noise generated"
    )
    assert manifest["design_fingerprint"] == design.fingerprint


def test_evaluation_manifest_seeds_do_not_reuse_any_pilot_checkpoint_seed() -> None:
    manifest = build_m5i_seed_manifest(load_m5i_confirmatory_design(DRAFT_PATH))
    evaluation_seeds = set()
    for run in manifest["planned_runs"]:
        evaluation_seeds.add(run["data"]["derived_seed"])
        evaluation_seeds.add(run["noise"]["derived_seed"])
    evaluation_seeds.add(manifest["bootstrap"]["derived_seed"])
    pilot_seeds = set()
    for path in (PILOT_OUTPUT / "checkpoints").glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))["record"]
        pilot_seeds.update((record["data_seed"], record["noise_seed"], record["bootstrap_seed"]))
    assert len(evaluation_seeds) == 201
    assert evaluation_seeds.isdisjoint(pilot_seeds)


def test_evaluation_roots_match_only_reserved_evaluation_namespace() -> None:
    data = load_m5i_confirmatory_design(DRAFT_PATH).as_dict()
    pilot_draft = json.loads(
        (ROOT / "configs" / "m5h_pilot_draft.json").read_text(encoding="utf-8")
    )
    namespaces = pilot_draft["seed_derivation"]["namespace_scheme"]
    assert data["seed_derivation"]["master_seeds"] == namespaces["evaluation"]
    assert data["seed_derivation"]["master_seeds"] != namespaces["pilot"]


def test_mutating_returned_json_does_not_mutate_immutable_design_snapshot() -> None:
    design = load_m5i_confirmatory_design(DRAFT_PATH)
    data = design.as_dict()
    data["receiver_policies"]["C"]["alpha_prime"] = 0.01
    assert design.as_dict()["receiver_policies"]["C"]["alpha_prime"] == 0.85
    assert design.fingerprint == "6e42b5003e3804c89266cd78dcf3702d9d8159ed4ed46b81acf962bbff4db1e4"


def test_no_unsupported_gamma_label_or_tuning_policy_is_accepted() -> None:
    changed = _draft()
    changed["secondary_analyses"]["historical_gamma_diagnostics_db"] = [0, 10, 20]
    with pytest.raises(ValueError, match="historical pilot gamma"):
        validate_m5i_confirmatory_design(changed)
    changed = _draft()
    changed["tuning_policy"]["automatic_tuning"] = True
    with pytest.raises(ValueError, match="tuning_policy"):
        validate_m5i_confirmatory_design(changed)


def test_pilot_source_artifact_hashes_match_without_modifying_pilot_outputs() -> None:
    data = load_m5i_confirmatory_design(DRAFT_PATH).as_dict()
    hashes = data["pilot_evidence_provenance"]
    for field, filename in {
        "approved_run_config_sha256": "approved_run_config.json",
        "execution_manifest_sha256": "execution_manifest.json",
        "summary_sha256": "summary.json",
        "precision_diagnostic_sha256": "precision_diagnostic_5db.json",
    }.items():
        digest = hashlib.sha256((PILOT_OUTPUT / filename).read_bytes()).hexdigest()
        assert hashes[field] == digest
    checkpoints = sorted((PILOT_OUTPUT / "checkpoints").glob("*.json"))
    pairs = [(path.name, hashlib.sha256(path.read_bytes()).hexdigest()) for path in checkpoints]
    aggregate = hashlib.sha256(json.dumps(pairs, separators=(",", ":")).encode()).hexdigest()
    assert len(checkpoints) == 120
    assert hashes["checkpoint_count"] == 120
    assert hashes["ordered_checkpoint_name_hash_pairs_sha256"] == aggregate


def test_pilot_recorded_variability_exactly_matches_saved_summary() -> None:
    summary = json.loads((PILOT_OUTPUT / "summary.json").read_text(encoding="utf-8"))
    records = []
    for path in (PILOT_OUTPUT / "checkpoints").glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))["record"]
        if record["gamma_b_eff_db"] == 5.0 and record["status"] == "completed":
            records.append(record)
    differences = [
        (record["c_bit_errors"] - record["b_bit_errors"]) / (2 * record["F"]) for record in records
    ]
    sd = statistics.stdev(differences)
    saved = summary["primary_5db_run_level_variability"]
    assert len(records) == 30
    assert sd == pytest.approx(0.053093594133490844, abs=1e-16)
    assert sd == saved["sample_standard_deviation_s_d"]
    assert saved["R_approx"] == 28


def test_execution_guard_blocks_before_any_stochastic_or_decoder_callback() -> None:
    design = load_m5i_confirmatory_design(DRAFT_PATH)
    calls: list[str] = []
    callbacks = {
        "data": lambda: calls.append("data"),
        "noise": lambda: calls.append("noise"),
        "decoder": lambda: calls.append("decoder"),
    }
    with pytest.raises(M5IExecutionBlocked):
        guard_m5i_execution(design, callbacks=callbacks)
    assert calls == []


def test_invalid_missing_or_mutated_candidate_is_rejected() -> None:
    original = _draft()
    missing = copy.deepcopy(original)
    del missing["bootstrap_contract"]
    with pytest.raises(ValueError, match="missing"):
        validate_m5i_confirmatory_design(missing)
    for path, value in [
        (("design_status",), "approved_for_pilot"),
        (("execution_authorized",), True),
        (("execution_scope",), "m5h_pilot_only"),
        (("run_design", "run_count"), 99),
        (("primary_condition", "gamma_b_eff_db"), 10.0),
        (("primary_condition", "sigma_squared"), 0.225),
    ]:
        changed = copy.deepcopy(original)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with pytest.raises(ValueError):
            validate_m5i_confirmatory_design(changed)


def test_invalid_status_and_execution_permission_never_reach_callbacks() -> None:
    bad = _draft()
    bad["design_status"] = "approved_for_confirmatory"
    with pytest.raises(ValueError):
        validate_m5i_confirmatory_design(bad)
    design = load_m5i_confirmatory_design(DRAFT_PATH)
    assert design.as_dict()["execution_authorized"] is False
    assert design.as_dict()["execution_scope"] == "none"


def test_failure_and_stopping_policy_retains_failures_high_ber_and_unstable_finite_runs() -> None:
    data = load_m5i_confirmatory_design(DRAFT_PATH).as_dict()
    policy = data["numerical_failure_policy"]
    assert policy["missing_valid_B_or_C_output"] == "retain failure; block full-design inference"
    assert policy["retry_with_new_seed"] is False
    assert policy["silent_exclusion"] is False
    assert policy["zero_or_max_error_imputation"] is False
    assert policy["finite_unstable_trajectory"] == "retain valid decoded output and diagnostics"
    assert policy["high_BER"] == "retain all observed errors"
    assert data["stopping_rule"]["result_dependent_early_stop"] is False
    assert data["stopping_rule"]["automatic_run_count_increase"] is False
    assert data["stopping_rule"]["planned_run_count"] == 100


def test_adr014_policy_and_no_reference_data_leakage() -> None:
    data = load_m5i_confirmatory_design(DRAFT_PATH).as_dict()
    contract = data["bootstrap_contract"]
    assert contract["adr"] == "ADR-014"
    assert contract["independent_cluster"] == "one complete coded TCM sequence"
    assert contract["paired_same_index_B_C_resampling"] is True
    assert contract["replicates"] == 2000
    assert contract["confidence_level"] == 0.95
    assert contract["interval"] == "two-sided percentile"
    assert contract["quantile_method"] == "numpy.quantile(method='linear')"
    assert contract["pooled_integer_counts"] is True
    assert contract["explicit_independent_bootstrap_seed"] is True
    assert contract["metrics"] == ["ber_b", "ber_c", "delta_ber", "ser_b", "ser_c", "delta_ser"]
    assert contract["preserve_warning_flags"] is True
    assert contract["zero_interval_interpretation"] == "CI=[0,0] is not proof of true zero BER"
    assert (
        contract["includes_zero_interpretation"]
        == "CI including zero is not evidence of receiver equivalence"
    )
    assert data["output_contract"]["reference_bits_or_ChannelTruth_passed_to_decoder"] is False
    assert data["output_contract"]["pilot_records_enter_confirmatory_sample"] is False


def test_duplicate_run_ids_are_rejected() -> None:
    design = load_m5i_confirmatory_design(DRAFT_PATH)
    manifest = build_m5i_seed_manifest(design)
    manifest["planned_runs"][1]["run_id"] = manifest["planned_runs"][0]["run_id"]
    with pytest.raises(ValueError, match="duplicate"):
        validate_m5i_seed_manifest(manifest, design)


def test_no_stochastic_arrays_or_receiver_output_in_planned_manifest() -> None:
    manifest = build_m5i_seed_manifest(load_m5i_confirmatory_design(DRAFT_PATH))
    encoded = json.dumps(manifest).lower()
    assert "received_buffer" not in encoded
    assert "reference_bits" not in encoded
    assert "bit_errors" not in encoded
    assert "noise_samples" not in encoded
