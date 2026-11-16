"""T-05/T-06: Viterbi optimality and noiseless end-to-end frame recovery."""

from itertools import product

import numpy as np
import pytest

from hf_tcm.coding.encoder import INITIAL_STATE, encode
from hf_tcm.decoding.viterbi import decode_viterbi
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION
from hf_tcm.modulation.psk8 import demodulate, modulate


def _symbols_for(inputs: list[tuple[int, int]]) -> np.ndarray:
    outputs = encode(inputs)
    return modulate(outputs, profile=BASELINE_ASSUMPTION)


def _path_metric(inputs: tuple[tuple[int, int], ...], received: np.ndarray) -> float:
    candidate = _symbols_for(list(inputs))
    return float(np.sum(np.abs(received - candidate) ** 2))


def test_soft_viterbi_matches_exhaustive_best_path() -> None:
    sent = [(1, 0), (0, 1), (1, 1)]
    received = _symbols_for(sent) + np.asarray([0.08 + 0.02j, -0.03 + 0.07j, 0.04 - 0.06j])
    decoded = decode_viterbi(received, mode="soft")
    all_paths = list(product(((0, 0), (0, 1), (1, 0), (1, 1)), repeat=len(sent)))
    best_metric = min(_path_metric(path, received) for path in all_paths)

    assert decoded.path_metric == pytest.approx(best_metric)
    assert _path_metric(decoded.input_pairs, received) == pytest.approx(best_metric)


def test_hard_viterbi_matches_exhaustive_hamming_best_path() -> None:
    sent = [(1, 0), (0, 1), (1, 1)]
    symbols = _symbols_for(sent)
    received = symbols.copy()
    received[1] = _symbols_for([(0, 0), (1, 1), (0, 0)])[1]
    decoded = decode_viterbi(received, mode="hard")
    all_paths = list(product(((0, 0), (0, 1), (1, 0), (1, 1)), repeat=len(sent)))
    detected_labels = demodulate(received)

    def hard_metric(path: tuple[tuple[int, int], ...]) -> int:
        candidate_labels = encode(list(path))
        return sum(
            sum(a != b for a, b in zip(rx_label, tx_label, strict=True))
            for rx_label, tx_label in zip(detected_labels, candidate_labels, strict=True)
        )

    best_metric = min(hard_metric(path) for path in all_paths)

    assert decoded.path_metric == pytest.approx(best_metric)
    assert hard_metric(decoded.input_pairs) == best_metric


@pytest.mark.parametrize("mode", ["hard", "soft"])
def test_noiseless_channel_recovers_input_pairs(mode: str) -> None:
    sent = [(1, 0), (0, 1), (1, 1), (0, 0), (1, 0)]

    decoded = decode_viterbi(_symbols_for(sent), mode=mode)

    assert decoded.input_pairs == tuple(sent)
    assert decoded.initial_state == INITIAL_STATE


def test_final_state_constraint_is_respected() -> None:
    sent = [(0, 1), (1, 0)]

    decoded = decode_viterbi(_symbols_for(sent), mode="soft", final_state=(0, 1))

    assert decoded.final_state == (0, 1)


def test_viterbi_rejects_invalid_observations_and_modes() -> None:
    with pytest.raises(ValueError, match="mode"):
        decode_viterbi([], mode="adaptive")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        decode_viterbi([complex(float("nan"), 0.0)], mode="soft")
    with pytest.raises(ValueError, match="state"):
        decode_viterbi([], mode="soft", initial_state=(0, 2))
