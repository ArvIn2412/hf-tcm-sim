"""T-08: an AWGN run with a fixed seed produces identical arrays and counts."""

import numpy as np

from hf_tcm.analysis.errors import compute_error_metrics
from hf_tcm.channels.awgn import add_awgn
from hf_tcm.coding.encoder import encode
from hf_tcm.decoding.viterbi import decode_viterbi
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION
from hf_tcm.modulation.psk8 import demodulate, modulate


def _run(seed: int) -> tuple[np.ndarray, tuple[int, int], float]:
    info = [(0, 1), (1, 1), (1, 0), (0, 0), (1, 1), (0, 1)]
    labels = encode(info)
    tx = modulate(labels, profile=BASELINE_ASSUMPTION)
    rx = add_awgn(tx, 5.0, rng=np.random.default_rng(seed))
    decoded = decode_viterbi(rx, mode="soft")
    metrics = compute_error_metrics(info, decoded.input_pairs, labels, demodulate(rx))
    return rx, (metrics.bit_errors, metrics.symbol_errors), metrics.ber


def test_fixed_seed_repeats_observations_and_error_counts() -> None:
    first_rx, first_counts, first_ber = _run(8675309)
    second_rx, second_counts, second_ber = _run(8675309)

    assert np.array_equal(first_rx, second_rx)
    assert first_counts == second_counts
    assert first_ber == second_ber
