"""B3a tests for explicit receiver-side estimator state."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from channel_truth_guard import audit_source, is_protected_module

from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_SOURCE = PROJECT_ROOT / "src/hf_tcm/receiver/reconstruction_estimator_state.py"


def test_explicit_initialization_preserves_iq_estimates_and_absolute_time() -> None:
    fluctuating = np.array([[0.1, -0.2], [0.3, 0.4]])
    full = np.array([[1.1, 0.8], [1.3, 1.4]])

    state = ReconstructionEstimatorState(
        fluctuating_iq=fluctuating,
        full_iq=full,
        time_index=17,
    )

    np.testing.assert_array_equal(state.fluctuating_iq, fluctuating)
    np.testing.assert_array_equal(state.full_iq, full)
    assert state.time_index == 17
    assert state.fluctuating_iq.shape == state.full_iq.shape == (2, 2)
    assert state.fluctuating_iq.flags.writeable is False
    assert state.full_iq.flags.writeable is False


def test_state_owns_immutable_snapshots_and_separate_runs_are_isolated() -> None:
    initial = np.array([[0.25, -0.5]])
    first = ReconstructionEstimatorState(initial, initial + 1.0, time_index=0)
    second = ReconstructionEstimatorState(initial * 2.0, initial * 3.0, time_index=0)
    initial[:] = 99.0

    np.testing.assert_array_equal(first.fluctuating_iq, [[0.25, -0.5]])
    np.testing.assert_array_equal(first.full_iq, [[1.25, 0.5]])
    np.testing.assert_array_equal(second.fluctuating_iq, [[0.5, -1.0]])
    assert not np.shares_memory(first.fluctuating_iq, second.fluctuating_iq)
    with pytest.raises(ValueError):
        first.fluctuating_iq.setflags(write=True)


@pytest.mark.parametrize(
    ("fluctuating", "full", "time_index", "message"),
    [
        ([0.0, 0.0], [[0.0, 0.0]], 0, r"shape \(L, 2\)"),
        ([[0.0, 0.0]], [[0.0, 0.0], [1.0, 1.0]], 0, "matching shape"),
        ([], [], 0, "at least one beam"),
        ([[0.0, float("nan")]], [[0.0, 0.0]], 0, "finite"),
        ([[0.0, 0.0]], [[0.0, float("inf")]], 0, "finite"),
        ([[0.0, 1.0j]], [[0.0, 0.0]], 0, "finite real array"),
        ([[0.0, 0.0]], [[0.0, 0.0]], True, "integer"),
        ([[0.0, 0.0]], [[0.0, 0.0]], 1.5, "integer"),
    ],
)
def test_rejects_invalid_estimates_and_timestamps(
    fluctuating: object,
    full: object,
    time_index: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ReconstructionEstimatorState(
            fluctuating_iq=fluctuating,
            full_iq=full,
            time_index=time_index,  # type: ignore[arg-type]
        )


def test_container_is_covered_by_existing_truth_and_rng_state_guard() -> None:
    assert is_protected_module(STATE_SOURCE)
    assert audit_source(STATE_SOURCE, STATE_SOURCE.read_text(encoding="utf-8")) == ()
