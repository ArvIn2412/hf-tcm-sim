from __future__ import annotations

import numpy as np

from hf_tcm.evaluation.m10a_variable_gain_study_design import (
    EXPECTED_SEED_ROOTS,
    PARTITION_CODE,
    PROTOCOL_WORD,
)
from hf_tcm.evaluation.m10b_independent_recount import (
    _checkpoint_seed_provenance,
    _summary_from_runs,
)


def _seed(master: int, index: int, code: int) -> dict[str, object]:
    spawn = [PROTOCOL_WORD, PARTITION_CODE, index, code]
    child = np.random.SeedSequence(master, spawn_key=tuple(spawn)).generate_state(
        1, dtype=np.uint64
    )[0]
    return {
        "master_seed": master,
        "spawn_key": spawn,
        "derived_seed": int(child),
        "generator": "PCG64",
        "initialized": False,
    }


def test_checkpoint_seed_flags_distinguish_plan_from_actual_rng_use() -> None:
    rows = {
        "data": _seed(EXPECTED_SEED_ROOTS["data"], 0, 11),
        "noise": _seed(EXPECTED_SEED_ROOTS["noise"], 0, 23),
        "metadata": _seed(EXPECTED_SEED_ROOTS["metadata"], 0, 41),
    }
    rows["data"]["initialized"] = True
    rows["noise"]["initialized"] = True
    assert _checkpoint_seed_provenance({"seed_provenance": rows}, 0)
    rows["noise"]["derived_seed"] = int(rows["noise"]["derived_seed"]) + 1
    assert not _checkpoint_seed_provenance({"seed_provenance": rows}, 0)


def test_independent_scalar_bootstrap_is_repeatable_and_run_clustered() -> None:
    runs = []
    for index in range(100):
        profiles = {}
        for profile_index, profile in enumerate(
            ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH")
        ):
            b = index % 5 + profile_index
            profiles[profile] = {
                "historical_frozen_B": {
                    "bit_errors": b,
                    "total_bits": 512,
                    "symbol_errors": b,
                    "total_symbols": 256,
                },
                "anch_a085_k025": {
                    "bit_errors": b + profile_index - 1,
                    "total_bits": 512,
                    "symbol_errors": b + profile_index - 1,
                    "total_symbols": 256,
                },
            }
        runs.append({"run_id": f"run-{index:03d}", "profiles": profiles})
    first = _summary_from_runs(runs, 1234)
    second = _summary_from_runs(runs, 1234)
    assert {
        key: value for key, value in first.items() if key != "bootstrap_wall_clock_seconds"
    } == {key: value for key, value in second.items() if key != "bootstrap_wall_clock_seconds"}
    assert first["cluster_count"] == 100
    assert first["profiles"]["P1_HIGH_TO_LOW"]["delta_bit_errors"] == 0
    assert first["bootstrap"]["replicates"] == 2000
    assert first["bootstrap"]["shared_run_indices_across_all_six_outputs"] is True
