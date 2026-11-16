from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hf_tcm.evaluation.m10a_variable_gain_study_design import (
    DRAFT_PATH,
    M10AExecutionBlocked,
    guard_m10a_execution,
    validate_m10a_variable_gain_study,
)


def _draft() -> dict[str, object]:
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def test_draft_is_unauthorized_and_contains_exact_paired_three_profile_design() -> None:
    draft = _draft()
    design = validate_m10a_variable_gain_study(draft)

    assert design.study_id == "m10_controlled_piecewise_gain_v1"
    assert design.run_count == 100
    assert design.symbols_per_sequence == 256
    assert design.profile_ids == ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH")
    assert design.policy_ids == ("historical_frozen_B", "anch_a085_k025")
    assert design.expected_decoder_calls == 600
    assert design.expected_policy_records == 600
    assert design.expected_received_samples == 614400
    assert draft["design_status"] == "proposed"
    assert draft["execution_authorized"] is False
    assert draft["execution_scope"] == "none"
    assert len(draft["partition"]["planned_runs"]) == 100
    assert draft["partition"]["planned_runs"][0]["run_id"].endswith("run-001")
    assert draft["partition"]["planned_runs"][-1]["run_id"].endswith("run-100")


def test_guard_blocks_before_rng_noise_data_or_decoder_callbacks() -> None:
    calls: list[str] = []
    callbacks = {
        key: lambda key=key: calls.append(key)
        for key in ("rng", "data", "noise", "receiver", "decoder")
    }

    with pytest.raises(M10AExecutionBlocked, match="execution blocked"):
        guard_m10a_execution(_draft(), callbacks=callbacks, executor=lambda: calls.append("run"))

    assert calls == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda config: config["channel_profile"]["profiles"]["P1_HIGH_TO_LOW"]["segments"][
                1
            ].update(symbol_start=127),
            "switch",
        ),
        (lambda config: config["channel_profile"]["profiles"].pop("P2_LOW_TO_HIGH"), "profiles"),
        (lambda config: config["receiver_policies"][1].update(mu0=[0.0, 0.0]), "policies"),
        (lambda config: config["noise"].update(sigma_squared=0.6), "sigma_squared"),
        (lambda config: config["partition"]["seed_namespaces"].update(data=2027020101), "seed"),
        (lambda config: config["statistics"].update(primary_profile="P0_CONSTANT"), "primary"),
    ],
)
def test_scientific_design_mutations_fail_validation(mutation, message: str) -> None:
    draft = copy.deepcopy(_draft())
    mutation(draft)
    with pytest.raises(ValueError, match=message):
        validate_m10a_variable_gain_study(draft)


def test_validator_does_not_derive_or_materialize_seed_children() -> None:
    draft = _draft()
    before = json.dumps(draft, sort_keys=True)
    validate_m10a_variable_gain_study(draft)
    assert json.dumps(draft, sort_keys=True) == before
    assert draft["partition"]["seed_derivation"]["child_seeds_materialized"] is False
    assert all("derived_seed" not in run for run in draft["partition"]["planned_runs"])


def test_sidecar_matches_proposed_draft_bytes() -> None:
    sidecar = Path(f"{DRAFT_PATH}.sha256")
    import hashlib

    assert sidecar.is_file()
    assert (
        sidecar.read_text(encoding="ascii").strip()
        == hashlib.sha256(DRAFT_PATH.read_bytes()).hexdigest()
    )
