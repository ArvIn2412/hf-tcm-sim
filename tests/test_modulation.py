"""T-03: normalized 8PSK constellation and explicit labeling round trip."""

import numpy as np
import pytest

from hf_tcm.modulation.labeling import (
    BASELINE_ASSUMPTION,
    index_to_label,
    label_to_index,
)
from hf_tcm.modulation.psk8 import constellation, demodulate, modulate


def test_constellation_is_normalized_and_uses_phase_offset() -> None:
    points = constellation(phase_offset=np.pi / 4)

    assert points.shape == (8,)
    assert len(set(points)) == 8
    assert np.allclose(np.abs(points), 1.0)
    expected_angles = np.pi / 4 + 2 * np.pi * np.arange(8) / 8
    assert np.allclose(points, np.exp(1j * expected_angles))


def test_baseline_labeling_is_bijective_and_round_trips_without_noise() -> None:
    labels = [index_to_label(index) for index in range(8)]
    symbols = modulate(labels, phase_offset=np.pi / 4)

    assert {label_to_index(label) for label in labels} == set(range(8))
    assert demodulate(symbols, phase_offset=np.pi / 4) == labels
    assert BASELINE_ASSUMPTION == "baseline_assumption"


@pytest.mark.parametrize("label", [(0, 0), (0, 0, 2), (0, 1, False)])
def test_modulate_rejects_invalid_labels(label: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        modulate([label])  # type: ignore[list-item]


@pytest.mark.parametrize("phase_offset", [float("nan"), float("inf")])
def test_constellation_rejects_non_finite_phase_offset(phase_offset: float) -> None:
    with pytest.raises(ValueError, match="phase_offset"):
        constellation(phase_offset)


def test_constellation_rejects_non_numeric_phase_offset() -> None:
    with pytest.raises(ValueError, match="phase_offset"):
        constellation("0")  # type: ignore[arg-type]


def test_only_explicit_baseline_profile_is_available() -> None:
    with pytest.raises(ValueError, match="baseline_assumption"):
        label_to_index((0, 0, 0), profile="gray")


def test_empty_modulation_still_validates_profile() -> None:
    with pytest.raises(ValueError, match="baseline_assumption"):
        modulate([], profile="gray")


def test_demodulate_rejects_non_finite_symbols() -> None:
    with pytest.raises(ValueError, match="finite"):
        demodulate([complex(float("nan"), 0.0)])
