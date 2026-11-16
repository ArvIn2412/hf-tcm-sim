from __future__ import annotations

import json
from pathlib import Path

from hf_tcm.evaluation.m11a_demo_studio import DEFENSE_DEMO_REQUEST, NOISE_FIXTURES

ROOT = Path(__file__).resolve().parents[1]


def test_m11c_manifest_keeps_historical_environment_as_immutable_metadata() -> None:
    manifest = (ROOT / "docs/DEMO_RELEASE_MANIFEST.md").read_text(encoding="utf-8")

    assert "| Python | 3.13.13 (" in manifest
    assert "NumPy 2.3.3; HTTP server" in manifest


def test_defense_demo_configuration_is_checked_separately_from_runtime_versions() -> None:
    configuration = json.loads(
        (ROOT / "configs/m9b_evaluation_approved_run.json").read_text(encoding="utf-8")
    )
    policies = {item["candidate_id"]: item for item in configuration["policies"]}

    assert len(DEFENSE_DEMO_REQUEST.bits) == 64
    assert DEFENSE_DEMO_REQUEST.receiver_mode == "compare"
    assert DEFENSE_DEMO_REQUEST.noise_fixture == "low_amplitude_a"
    assert NOISE_FIXTURES["low_amplitude_a"] == (
        "Re(w[n])=0.004*((n mod 5)-2); Im(w[n])=0.003*((3n mod 7)-3)"
    )
    assert configuration["profile"]["real_channel_gain"] == 0.75
    assert policies["historical_frozen_B"]["alpha_prime"] == 1.0
    assert policies["anch_a085_k025"]["alpha_prime"] == 0.85
    assert policies["anch_a085_k025"]["k_tilde"] == [0.0875, -0.05]
