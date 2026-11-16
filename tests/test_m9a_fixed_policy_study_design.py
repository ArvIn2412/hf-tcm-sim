from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hf_tcm.evaluation.m9a_fixed_policy_study_design import (
    M9AExecutionBlocked,
    guard_m9a_execution,
    validate_m9a_fixed_policy_study,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/m9a_fixed_policy_study_draft.json"


def _draft() -> dict[str, object]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_m9a_draft_freezes_two_policies_profile_and_unmaterialized_seed_plan() -> None:
    value = _draft()
    design = validate_m9a_fixed_policy_study(value)

    assert design.design_status == "proposed"
    assert design.execution_authorized is False
    assert design.execution_scope == "none"
    assert design.run_count == 100
    assert design.symbols_per_sequence == 256
    assert [row.candidate_id for row in design.policies] == [
        "historical_frozen_B",
        "anch_a085_k025",
    ]
    assert design.expected_decoder_calls == 200
    assert design.expected_policy_records == 200
    assert design.expected_received_samples == 204800

    manifest = value["partition"]["planned_runs"]
    assert len(manifest) == 100
    for zero_index, run in enumerate(manifest):
        assert run["run_index"] == zero_index
        assert (
            run["run_id"] == f"m9_fixed_anchored_vs_frozen_v1:evaluation:run-{zero_index + 1:03d}"
        )
        assert set(run["streams"]) == {"data", "noise", "metadata"}
        for stream, code in (("data", 11), ("noise", 23), ("metadata", 41)):
            entry = run["streams"][stream]
            assert entry["spawn_key"] == [1295337521, 901, zero_index, code]
            assert "derived_seed" not in entry
            assert entry["child_stream_materialized"] is False
    bootstrap = value["partition"]["bootstrap_stream"]
    assert bootstrap["spawn_key"] == [1295337521, 901, 0, 37]
    assert bootstrap["child_stream_materialized"] is False


def test_unauthorized_m9_guard_blocks_before_any_rng_or_decoder_callback() -> None:
    value = _draft()
    callbacks: list[str] = []
    spies = {
        name: lambda name=name: callbacks.append(name)
        for name in ("rng", "data", "noise", "decoder")
    }
    with pytest.raises(M9AExecutionBlocked, match="proposed / false / none"):
        guard_m9a_execution(value, callbacks=spies, executor=lambda: callbacks.append("execute"))
    assert callbacks == []


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update(execution_authorized=True), "execution_authorized"),
        (lambda value: value["policies"][1].update(k_tilde=[0.35, -0.2]), "anch_a085_k025"),
        (lambda value: value["profile"].update(sigma_squared=0.5), "sigma_squared"),
        (lambda value: value["partition"].update(run_count=99), "run_count"),
        (
            lambda value: value["partition"]["seed_namespaces"].update(data=2027011001),
            "seed namespace",
        ),
    ],
)
def test_m9_validator_rejects_design_drift(mutate, message: str) -> None:
    value = copy.deepcopy(_draft())
    mutate(value)
    with pytest.raises(ValueError, match=message):
        validate_m9a_fixed_policy_study(value)
