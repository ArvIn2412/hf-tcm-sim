"""Hard-decision and soft-decision Viterbi decoding on the M1 trellis."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import numpy as np

from hf_tcm.coding.encoder import INITIAL_STATE, BitPair, State
from hf_tcm.coding.trellis import STATES, TrellisBranch, build_trellis
from hf_tcm.decoding.branch_metrics import hard_branch_cost, soft_branch_cost
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, Label, validate_profile
from hf_tcm.modulation.psk8 import demodulate, modulate

DecoderMode = Literal["hard", "soft"]


@dataclass(frozen=True, slots=True)
class DecodeResult:
    """Decoded information pairs and the selected trellis path."""

    input_pairs: tuple[BitPair, ...]
    state_path: tuple[State, ...]
    initial_state: State
    final_state: State
    path_metric: float
    mode: DecoderMode

    @property
    def decoded_bits(self) -> tuple[int, ...]:
        """Flatten decoded input pairs in ``(u0, u1)`` order."""
        return tuple(bit for pair in self.input_pairs for bit in pair)


def _state(value: Iterable[int], *, name: str) -> State:
    try:
        state = tuple(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be one of the four trellis states") from exc
    if (
        len(state) != 2
        or any(type(bit) is not int or bit not in (0, 1) for bit in state)
        or state not in STATES
    ):
        raise ValueError(f"{name} must be one of the four trellis states")
    return state  # type: ignore[return-value]


def _observations(values: Iterable[complex]) -> np.ndarray:
    try:
        received = np.asarray(tuple(values), dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("observations must be a finite 1-D numeric sequence") from exc
    if received.ndim != 1 or not np.all(np.isfinite(received)):
        raise ValueError("observations must be a finite 1-D numeric sequence")
    return received


def _branch_symbols(
    branches: tuple[TrellisBranch, ...], phase_offset: float, profile: str
) -> dict[Label, complex]:
    labels = tuple(dict.fromkeys(branch.output for branch in branches))
    points = modulate(labels, phase_offset=phase_offset, profile=profile)
    return dict(zip(labels, points.tolist(), strict=True))


def decode_viterbi(
    observations: Iterable[complex],
    *,
    mode: DecoderMode,
    initial_state: Iterable[int] = INITIAL_STATE,
    final_state: Iterable[int] | None = None,
    phase_offset: float = 0.0,
    profile: str = BASELINE_ASSUMPTION,
) -> DecodeResult:
    """Decode one symbol-rate frame; the default final state is unconstrained.

    No tail bits are added or discarded. The default baseline starts at state
    ``(0, 0)`` and selects the least-cost reachable ending state.
    """
    if mode not in ("hard", "soft"):
        raise ValueError("mode must be 'hard' or 'soft'")
    validate_profile(profile)
    start = _state(initial_state, name="initial_state")
    end = None if final_state is None else _state(final_state, name="final_state")
    received = _observations(observations)
    branches = build_trellis()
    symbols_by_label = _branch_symbols(branches, phase_offset, profile)
    hard_labels = (
        demodulate(received, phase_offset=phase_offset, profile=profile) if mode == "hard" else []
    )

    path_metrics: dict[State, float] = {start: 0.0}
    backpointers: list[dict[State, tuple[State, BitPair]]] = []
    for time_index, observation in enumerate(received):
        next_metrics: dict[State, float] = {}
        previous: dict[State, tuple[State, BitPair]] = {}
        for branch in branches:
            if branch.state not in path_metrics:
                continue
            if mode == "hard":
                cost = float(hard_branch_cost(hard_labels[time_index], branch.output))
            else:
                cost = soft_branch_cost(observation, symbols_by_label[branch.output])
            candidate = path_metrics[branch.state] + cost
            incumbent = next_metrics.get(branch.next_state)
            if incumbent is None or candidate < incumbent:
                next_metrics[branch.next_state] = candidate
                previous[branch.next_state] = (branch.state, branch.input_pair)
        path_metrics = next_metrics
        backpointers.append(previous)

    if end is None:
        selected_end = min(path_metrics, key=lambda state: (path_metrics[state], state))
    else:
        if end not in path_metrics:
            raise ValueError("final_state is unreachable for this frame")
        selected_end = end

    decoded_reversed: list[BitPair] = []
    states_reversed = [selected_end]
    state = selected_end
    for previous in reversed(backpointers):
        previous_state, input_pair = previous[state]
        decoded_reversed.append(input_pair)
        state = previous_state
        states_reversed.append(state)
    return DecodeResult(
        input_pairs=tuple(reversed(decoded_reversed)),
        state_path=tuple(reversed(states_reversed)),
        initial_state=start,
        final_state=selected_end,
        path_metric=float(path_metrics[selected_end]),
        mode=mode,
    )
