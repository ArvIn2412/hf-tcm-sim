from __future__ import annotations

import numpy as np
import pytest
from channel_truth_guard import PROJECT_ROOT, audit_source

from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward_snapshot import (
    snapshot_full_iq_for_forward,
)


def test_snapshot_is_an_immutable_copy_of_full_iq_with_exact_state_time() -> None:
    state = ReconstructionEstimatorState(
        fluctuating_iq=[[1.0, 2.0]], full_iq=[[7.0, -4.0]], time_index=15
    )

    snapshot = snapshot_full_iq_for_forward(state, estimator_time_index=15)

    assert snapshot.estimator_time_index == 15
    np.testing.assert_array_equal(snapshot.estimated_path_coefficients, [[7.0, -4.0]])
    assert not np.shares_memory(snapshot.estimated_path_coefficients, state.full_iq)
    assert not snapshot.estimated_path_coefficients.flags.writeable
    with pytest.raises(ValueError):
        snapshot.estimated_path_coefficients[0, 0] = 99.0


def test_snapshot_uses_full_estimate_instead_of_fluctuating_estimate() -> None:
    state = ReconstructionEstimatorState(
        fluctuating_iq=[[1.0, 2.0]], full_iq=[[7.0, -4.0]], time_index=3
    )

    snapshot = snapshot_full_iq_for_forward(state, estimator_time_index=3)

    assert not np.array_equal(snapshot.estimated_path_coefficients, state.fluctuating_iq)
    np.testing.assert_array_equal(snapshot.estimated_path_coefficients, state.full_iq)


def test_snapshot_requires_matching_explicit_estimator_time_index() -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[2.0, 3.0]], time_index=8)

    with pytest.raises(ValueError, match="must match state.time_index"):
        snapshot_full_iq_for_forward(state, estimator_time_index=9)


@pytest.mark.parametrize(
    "state",
    [
        object(),
        ReconstructionEstimatorState(
            [[1.0, 2.0], [3.0, 4.0]],
            [[5.0, 6.0], [7.0, 8.0]],
            time_index=1,
        ),
    ],
    ids=("not-estimator-state", "multiple-beams"),
)
def test_snapshot_rejects_non_state_and_invalid_beam_count(state: object) -> None:
    with pytest.raises(ValueError):
        snapshot_full_iq_for_forward(state, estimator_time_index=1)  # type: ignore[arg-type]


def test_snapshot_adapter_passes_estimated_receiver_truth_boundary_audit() -> None:
    module_path = (
        PROJECT_ROOT / "src" / "hf_tcm" / "receiver" / "reconstruction_forward_snapshot.py"
    )

    assert audit_source(module_path, module_path.read_text(encoding="utf-8")) == ()
