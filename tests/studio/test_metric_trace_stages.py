"""Per-symbol decision stages served to the «Етапи обробки» tab."""

from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.repro.metric_isolation import (
    euclidean_branch_metric_rows,
    hamming_branch_metric_rows,
)
from hf_tcm.studio.metric_trace import _frontend_window


def _rows(symbols: np.ndarray, amplitude: float, weights: np.ndarray):
    return (
        hamming_branch_metric_rows(symbols, amplitude=amplitude),
        euclidean_branch_metric_rows(symbols, amplitude=amplitude, csi_weights=weights),
    )


def test_stages_recover_hard_decision_distances_and_weight() -> None:
    rng = np.random.default_rng(7)
    amplitude = 2.0
    phases = rng.integers(0, 8, 12)
    symbols = amplitude * np.exp(1j * phases * np.pi / 4) + 0.3 * (
        rng.standard_normal(12) + 1j * rng.standard_normal(12)
    )
    weights = rng.uniform(0.5, 9.0, 12)
    hamming, euclid = _rows(symbols, amplitude, weights)
    stages = _frontend_window(symbols, hamming, euclid, np.ones(12, bool), amplitude=amplitude)
    points = amplitude * np.exp(1j * np.arange(8) * np.pi / 4)
    for k, stage in enumerate(stages):
        distances = np.abs(symbols[k] - points) ** 2
        assert stage["hard_phase"] == int(np.argmin(distances))
        assert stage["distances"] == pytest.approx(distances.tolist())
        assert stage["csi_weight"] == pytest.approx(weights[k])
        assert stage["z"] == pytest.approx([symbols[k].real, symbols[k].imag])
        assert stage["pilot"] is False


def test_stages_reject_metrics_that_do_not_follow_from_z() -> None:
    symbols = np.array([1.0 + 0.1j, -0.2 + 0.9j])
    hamming, euclid = _rows(symbols, 1.0, np.array([8.0, 8.0]))
    bad_hamming = hamming.copy()
    bad_hamming[0, 0] += 1
    with pytest.raises(ValueError, match="Hamming"):
        _frontend_window(symbols, bad_hamming, euclid, np.ones(2, bool), amplitude=1.0)
    bad_euclid = euclid.copy()
    bad_euclid[1, 3] *= 1.5
    with pytest.raises(ValueError, match="Euclidean"):
        _frontend_window(symbols, hamming, bad_euclid, np.ones(2, bool), amplitude=1.0)


def test_pilot_symbols_carry_no_metric_check() -> None:
    symbols = np.array([1.0 + 0.0j, 0.0 + 1.0j])
    zeros = np.zeros((2, 16))
    stages = _frontend_window(
        symbols, zeros.astype(np.int8), zeros, np.array([False, False]), amplitude=1.0
    )
    assert [s["pilot"] for s in stages] == [True, True]
    assert all("csi_weight" not in s for s in stages)
