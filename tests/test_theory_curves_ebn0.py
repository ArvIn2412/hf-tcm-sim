"""Analytic references and the end-to-end Eb/N0 convention check (plan P0-4)."""

from __future__ import annotations

import math

import pytest

from hf_tcm.evaluation.ebn0_validation import validate_point
from hf_tcm.evaluation.theory_curves import (
    es_n0_from_amplitude,
    mpsk_symbol_error_approximation,
    mpsk_symbol_error_probability,
    q_function,
    qpsk_bit_error_probability,
    reference_table,
    tcm4_8psk_dominant_term_ber,
    wilson_interval,
)


def test_q_function_known_values() -> None:
    assert q_function(0.0) == pytest.approx(0.5)
    assert q_function(1.959963984540054) == pytest.approx(0.025, rel=1e-9)


def test_craig_integral_matches_closed_forms() -> None:
    # BPSK: Ps = Q(sqrt(2 Es/N0)); QPSK: Ps = 2Q(x) - Q(x)^2 with x = sqrt(Es/N0).
    for es_n0 in (0.5, 2.0, 8.0):
        assert mpsk_symbol_error_probability(es_n0, order=2) == pytest.approx(
            q_function(math.sqrt(2 * es_n0)), rel=1e-6
        )
        x = q_function(math.sqrt(es_n0))
        assert mpsk_symbol_error_probability(es_n0, order=4) == pytest.approx(
            2 * x - x * x, rel=1e-6
        )


def test_8psk_approximation_converges_at_high_snr() -> None:
    es_n0 = 10 ** (18 / 10)
    exact = mpsk_symbol_error_probability(es_n0)
    assert mpsk_symbol_error_approximation(es_n0) == pytest.approx(exact, rel=1e-3)


def test_convention_and_reference_rows() -> None:
    assert es_n0_from_amplitude(1.0, 0.05) == pytest.approx(160.0)
    row = reference_table([6.0])[0]
    assert row["qpsk_uncoded_ber"] == pytest.approx(qpsk_bit_error_probability(10**0.6))
    assert row["tcm4_8psk_soft_dominant_ber"] < row["qpsk_uncoded_ber"]
    assert tcm4_8psk_dominant_term_ber(10**0.6) == pytest.approx(
        0.5 * q_function(math.sqrt(4 * 10**0.6))
    )


def test_wilson_interval_contains_estimate() -> None:
    low, high = wilson_interval(50, 1000)
    assert low < 0.05 < high
    with pytest.raises(ValueError):
        wilson_interval(5, 0)


@pytest.mark.parametrize("eb_n0_db", [2.0, 6.0])
def test_project_axis_equals_eb_n0_for_uncoded_8psk(eb_n0_db: float) -> None:
    point = validate_point(eb_n0_db, symbols=8000, seed=4242)
    assert point.measured_gamma_b_db == pytest.approx(eb_n0_db, abs=1e-9)
    assert point.theory_inside_ci95
    assert point.measured_noise_variance == pytest.approx(1.0, rel=0.03)


def test_project_code_has_ungerboeck_4_state_distances() -> None:
    """d^2 parallel = 4 Es and d^2 non-parallel = 2 + (2 - sqrt 2) + 2 = 4.586 Es."""
    import heapq

    import numpy as np

    from hf_tcm.repro.encoder import transition_table

    points = np.exp(1j * np.pi / 4 * np.arange(8))
    edges: dict[object, list[tuple[int, object]]] = {}
    for edge in transition_table():
        out = edge[3]
        edges.setdefault(edge[1], []).append((4 * out[0] + 2 * out[1] + out[2], edge[4]))

    def distance(a: int, b: int) -> float:
        return float(abs(points[a] - points[b]) ** 2)

    parallel = min(
        distance(a[0], b[0])
        for s in edges
        for a in edges[s]
        for b in edges[s]
        if a != b and a[1] == b[1]
    )
    queue = [
        (distance(a[0], b[0]), a[1], b[1])
        for s in edges
        for a in edges[s]
        for b in edges[s]
        if a[1] != b[1]
    ]
    heapq.heapify(queue)
    done: set[tuple[object, object]] = set()
    non_parallel = math.inf
    while queue:
        d, s1, s2 = heapq.heappop(queue)
        if s1 == s2:
            non_parallel = d
            break
        if (s1, s2) in done:
            continue
        done.add((s1, s2))
        for a in edges[s1]:
            for b in edges[s2]:
                heapq.heappush(queue, (d + distance(a[0], b[0]), a[1], b[1]))
    assert parallel == pytest.approx(4.0)
    assert non_parallel == pytest.approx(6.0 - math.sqrt(2.0))
