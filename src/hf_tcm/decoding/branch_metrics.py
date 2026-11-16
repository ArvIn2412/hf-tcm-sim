"""Hard Hamming and soft Euclidean branch costs for M2 baselines."""

import math
from collections.abc import Sequence

from hf_tcm.modulation.labeling import normalize_label


def hard_branch_cost(received: Sequence[int], expected: Sequence[int]) -> int:
    """Return the Hamming distance between received and expected coded triples."""
    rx = normalize_label(received)
    candidate = normalize_label(expected)
    return sum(rx_bit != tx_bit for rx_bit, tx_bit in zip(rx, candidate, strict=True))


def soft_branch_cost(received: complex, expected: complex) -> float:
    """Return squared complex Euclidean distance for one trellis branch."""
    try:
        rx = complex(received)
        candidate = complex(expected)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("branch symbols must be finite complex numbers") from exc
    if not all(math.isfinite(part) for part in (rx.real, rx.imag, candidate.real, candidate.imag)):
        raise ValueError("branch symbols must be finite complex numbers")
    cost = float(abs(rx - candidate) ** 2)
    if not math.isfinite(cost):
        raise ValueError("soft branch cost is outside the supported numeric range")
    return cost
