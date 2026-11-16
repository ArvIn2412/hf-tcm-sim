from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from hf_tcm.evaluation.m6b_trace_protocol import (
    M6BExecutionBlocked,
    deserialize_m6b_trace_payload,
    guarded_m6b_execution,
    load_m6b_trace_diagnostic_config,
    planned_m6b_seed_provenance,
    serialize_m6b_trace_payload,
    validate_m6b_trace_diagnostic_config,
    validate_m6b_trace_payload,
)

ROOT = Path(__file__).parents[1]
DRAFT = ROOT / "configs/m6b_trace_diagnostic_draft.json"


def _array(shape: tuple[int, ...], value: object = 0.0, *, dtype: str = "float64") -> dict:
    values = np.full(shape, value, dtype=dtype).tolist()
    return {"dtype": dtype, "shape": list(shape), "values": values}


def _symbol_row(index: int, edge: int = 0) -> dict:
    k_tilde = {
        "dtype": "float64",
        "shape": [1, 2],
        "values": [[0.35, -0.2]] if edge else [[0.0, 0.0]],
    }
    return {
        "absolute_symbol_index": index,
        "estimator_time_index": index,
        "sequence_local_position": index,
        "processing_segment_index": 0,
        "processing_segment_local_position": index,
        "sample_window": list(range(index * 8, index * 8 + 8)),
        "prediction_cutoff_sample_index": index * 8 - 1,
        "observation_cutoff_sample_index": index * 8 + 7,
        "pre_fluctuating_iq": _array((1, 2)),
        "pre_full_iq": _array((1, 2)),
        "mu0": _array((1, 2)),
        "observed_iq_mean": _array((2,)),
        "candidate_metrics": _array((16,)),
        "hypothesis_ids": list(range(16)),
        "phase_indices": [0] * 16,
        "edge_mode": "first_edge" if index == 0 else "later_edge",
        "posterior_input": _array((16,), 1 / 16),
        "posterior_input_kind": "adr004_initial_prior" if index == 0 else "previous_posterior",
        "posterior_transition_provenance": (
            "none_first_edge" if index == 0 else "adr003_transition_then_current_metric_likelihood"
        ),
        "posterior": _array((16,), 1 / 16),
        "transition_predicted_posterior_q": {"status": "unavailable", "value": None},
        "predicted_iq": _array((16, 2)),
        "alpha_prime": 1.0 if edge == 0 else 0.85,
        "k_tilde": k_tilde,
        "innovation_operand": _array((2,)),
        "innovation_provenance": "derived_from_actual_B4c_posterior_observation_prediction",
        "post_fluctuating_iq": _array((1, 2)),
        "post_full_iq": _array((1, 2)),
        "fluctuating_increment": _array((1, 2)),
        "full_increment": _array((1, 2)),
        "posterior_sum": 1.0,
        "posterior_normalized": True,
        "decoded_hypothesis_id": 0,
    }


def _mode_trace(name: str, digest: str) -> dict:
    return {
        "receiver_mode": name,
        "received_sha256": digest,
        "initial_state": {
            "fluctuating_iq": _array((1, 2)),
            "full_iq": _array((1, 2)),
        },
        "symbol_trace": [_symbol_row(index, int(name.endswith("adaptive"))) for index in range(32)],
        "frozen_metric_history": _array((32, 16)),
        "final_state": {"fluctuating_iq": _array((1, 2)), "full_iq": _array((1, 2))},
        "decoded_hypothesis_path": [0] * 32,
        "decoded_information_bits": [0] * 64,
        "best_conditional_path_cost": 0.0,
        "decoded_path_valid": True,
        "decode_call_count": 1,
    }


def _payload() -> dict:
    digest = "a" * 64
    return {
        "schema_version": 1,
        "experiment_id": "m6b_causal_trace_20261030_v1",
        "run_id": "m6b_causal_trace_20261030_v1:run-001",
        "config_sha256": "b" * 64,
        "software_provenance": {
            "python_version": "3.13.0",
            "numpy_version": "2.0.0",
            "platform": "test-platform",
            "file_sha256": {"src/hf_tcm/evaluation/reconstruction_causal_trace.py": "c" * 64},
        },
        "received_sha256": digest,
        "mode_B": _mode_trace("mismatched_frozen", digest),
        "mode_C": _mode_trace("mismatched_adaptive", digest),
        "paired_comparison": {
            "rtol": 1e-12,
            "atol": 1e-14,
            "first_post_state_divergence_symbol": None,
            "first_candidate_metric_divergence_symbol": None,
            "first_posterior_divergence_symbol": None,
            "decoded_path_divergence_positions": [],
        },
        "trace_integrity_status": "complete_valid_trace",
    }


def test_draft_is_valid_proposed_unauthorized_and_namespaced() -> None:
    config = load_m6b_trace_diagnostic_config(DRAFT)
    assert config.design_status == "proposed"
    assert config.execution_authorized is False
    assert config.execution_scope == "none"
    assert config.run_ids == tuple(
        f"{config.experiment_id}:run-{index:03d}" for index in range(1, 4)
    )
    assert config.output_root == "outputs/m6b_trace_diagnostics/m6b_causal_trace_20261030_v1"


def test_policies_gamma_clocks_and_seed_namespace_separation() -> None:
    raw = json.loads(DRAFT.read_text(encoding="utf-8"))
    validate_m6b_trace_diagnostic_config(raw)
    noise = raw["scientific_scope"]["noise"]
    assert noise["sigma_squared"] == pytest.approx(4 * 0.75**2 / 10 ** (5 / 10), rel=1e-14)
    assert raw["run_design"]["symbols_per_sequence_F"] == 32
    assert raw["run_design"]["information_bits_per_sequence"] == 64
    assert raw["clock_contract"]["absolute_sample_origin"] == 0
    assert raw["clock_contract"]["absolute_symbol_origin"] == 0
    assert raw["clock_contract"]["initial_estimator_time_index"] == 0
    provenance = planned_m6b_seed_provenance(validate_m6b_trace_diagnostic_config(raw))
    assert len(provenance) == 3
    assert [item["zero_based_run_index"] for item in provenance] == [0, 1, 2]
    all_roots = [
        stream["master_seed"] for record in provenance for stream in record["streams"].values()
    ]
    assert len(set(all_roots)) == 3
    assert all(
        record["streams"]["data"]["spawn_key"] != record["streams"]["noise"]["spawn_key"]
        for record in provenance
    )
    assert all(
        stream["derived_seed"] == "derive only after separate execution authorization"
        for record in provenance
        for stream in record["streams"].values()
    )


def test_authorization_guard_blocks_before_any_rng_data_noise_or_receiver_callback() -> None:
    config = json.loads(DRAFT.read_text(encoding="utf-8"))
    spy = Mock()
    with pytest.raises(M6BExecutionBlocked, match="design_status"):
        guarded_m6b_execution(config, on_authorized=spy)
    spy.assert_not_called()


def test_run_specific_approval_contract_matches_explicit_user_scope() -> None:
    spy = Mock(return_value="approved-callback-only")
    config = json.loads(DRAFT.read_text(encoding="utf-8"))
    approved = copy.deepcopy(config)
    approved["design_status"] = "approved_diagnostic"
    approved["execution_authorized"] = True
    approved["execution_scope"] = "m6b_trace_only"
    approved["authorization"] = {
        "explicit_user_approval": True,
        "authorization_id": "user_instruction_M6b-run_2026-10-30",
        "approved_at_utc": "2026-10-30T07:45:24Z",
        "source_draft_sha256": "a" * 64,
        "authorization_provenance": "explicit user authorization provided through this M6b-run Codex instruction",
    }
    approved["resource_policy"]["resource_limits"] = {
        "wall_clock_budget_seconds": 300,
        "process_rss_budget_bytes": 536870912,
        "rss_monitoring": "periodic_observational_not_hard_os_limit",
    }
    protocol = validate_m6b_trace_diagnostic_config(approved)
    assert protocol.design_status == "approved_diagnostic"
    assert protocol.execution_scope == "m6b_trace_only"
    assert guarded_m6b_execution(approved, on_authorized=spy) == "approved-callback-only"
    spy.assert_called_once()
    spy.reset_mock()

    incomplete = dict(config)
    incomplete.pop("seed_derivation")
    with pytest.raises(ValueError, match="keys mismatch"):
        guarded_m6b_execution(incomplete, on_authorized=spy)
    spy.assert_not_called()

    invalid_status = dict(config)
    invalid_status["design_status"] = "approved"
    with pytest.raises(ValueError, match="design_status"):
        guarded_m6b_execution(invalid_status, on_authorized=spy)
    spy.assert_not_called()

    unauthorized_approved_status = dict(config)
    unauthorized_approved_status["design_status"] = "approved_diagnostic"
    with pytest.raises(ValueError, match="approved diagnostic"):
        guarded_m6b_execution(unauthorized_approved_status, on_authorized=spy)
    spy.assert_not_called()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda c: c["receiver_policies"]["C"].update(alpha_prime=0.86), "B/C policies"),
        (lambda c: c["scientific_scope"]["noise"].update(sigma_squared=0.5), "sigma_squared"),
        (lambda c: c["clock_contract"].update(initial_estimator_time_index=1), "clock contract"),
        (lambda c: c["run_design"].update(planned_run_ids=["dup", "dup", "third"]), "run design"),
        (
            lambda c: c["seed_derivation"]["master_seed_roots"].update(noise=2026103001),
            "seed roots",
        ),
    ],
)
def test_protocol_rejects_policy_gamma_clock_duplicate_id_and_seed_conflict(
    mutate, message
) -> None:
    config = json.loads(DRAFT.read_text(encoding="utf-8"))
    mutate(config)
    with pytest.raises(ValueError, match=message):
        validate_m6b_trace_diagnostic_config(config)


def test_trace_payload_schema_roundtrip_and_integrity_hash() -> None:
    payload = _payload()
    original = json.loads(json.dumps(payload))
    serialized = serialize_m6b_trace_payload(payload)
    assert payload == original
    replay = deserialize_m6b_trace_payload(serialized)
    assert replay == validate_m6b_trace_payload(payload)
    assert serialize_m6b_trace_payload(replay) == serialized
    assert replay["mode_B"]["symbol_trace"][0]["transition_predicted_posterior_q"] == {
        "status": "unavailable",
        "value": None,
    }
    assert replay["mode_C"]["symbol_trace"][0]["innovation_provenance"].startswith(
        "derived_from_actual_B4c"
    )
    assert replay["mode_B"]["symbol_trace"][0]["edge_mode"] == "first_edge"
    assert replay["mode_B"]["symbol_trace"][1]["edge_mode"] == "later_edge"


def test_trace_payload_rejects_wrong_shape_nonfinite_and_fabricated_q() -> None:
    wrong_shape = _payload()
    wrong_shape["mode_B"]["symbol_trace"][0]["candidate_metrics"] = _array((15,))
    with pytest.raises(ValueError, match="shape"):
        serialize_m6b_trace_payload(wrong_shape)

    nonfinite = _payload()
    nonfinite["mode_C"]["symbol_trace"][0]["innovation_operand"]["values"][0] = np.inf
    with pytest.raises(ValueError, match="finite|NaN|Infinity"):
        serialize_m6b_trace_payload(nonfinite)

    invented_q = _payload()
    invented_q["mode_C"]["symbol_trace"][1]["transition_predicted_posterior_q"] = {
        "status": "available",
        "value": _array((16,), 1 / 16),
    }
    with pytest.raises(ValueError, match="unavailable"):
        serialize_m6b_trace_payload(invented_q)


def test_trace_payload_rejects_tampered_integrity_and_reference_leakage() -> None:
    serialized = serialize_m6b_trace_payload(_payload())
    envelope = json.loads(serialized)
    envelope["payload"]["mode_B"]["symbol_trace"][0]["observed_iq_mean"]["values"][0] = 9.0
    with pytest.raises(ValueError, match="integrity"):
        deserialize_m6b_trace_payload(json.dumps(envelope))

    leaked = _payload()
    leaked["mode_B"]["symbol_trace"][0]["reference_bits"] = [0, 1]
    with pytest.raises(ValueError):
        validate_m6b_trace_payload(leaked)


def test_protocol_module_does_not_import_receiver_or_generate_random_samples() -> None:
    path = ROOT / "src/hf_tcm/evaluation/m6b_trace_protocol.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(module.startswith("hf_tcm.receiver") for module in imports)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"PCG64", "default_rng", "generate_independent_complex_awgn"}.intersection(names)
