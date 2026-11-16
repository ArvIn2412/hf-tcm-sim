"""T-07: BER/SER denominator handling and BER SVG output."""

import pytest

from hf_tcm.analysis.errors import compute_error_metrics
from hf_tcm.analysis.plots import save_ber_svg


def test_error_metrics_count_only_requested_valid_steps(tmp_path) -> None:
    metrics = compute_error_metrics(
        tx_info_pairs=[(0, 0), (0, 1), (1, 1)],
        decoded_info_pairs=[(0, 0), (1, 1), (0, 0)],
        tx_labels=[(0, 0, 0), (0, 0, 1), (1, 1, 1)],
        detected_labels=[(0, 0, 0), (0, 1, 1), (0, 0, 0)],
        valid_steps=2,
    )

    assert metrics.bit_errors == 1
    assert metrics.info_bits_checked == 4
    assert metrics.ber == 0.25
    assert metrics.symbol_errors == 1
    assert metrics.symbols_checked == 2
    assert metrics.ser == 0.5


def test_error_metrics_reject_misaligned_or_invalid_frames() -> None:
    with pytest.raises(ValueError, match="same length"):
        compute_error_metrics([(0, 0)], [], [(0, 0, 0)], [(0, 0, 0)])
    with pytest.raises(ValueError, match="valid_steps"):
        compute_error_metrics([(0, 0)], [(0, 0)], [(0, 0, 0)], [(0, 0, 0)], valid_steps=2)


def test_ber_svg_records_zero_error_counts_and_labels(tmp_path) -> None:
    path = tmp_path / "ber.svg"

    save_ber_svg(path, [0.0, 2.0], [2, 0], [100, 100])

    svg = path.read_text(encoding="utf-8")
    assert "<svg" in svg
    assert "BER over AWGN" in svg
    assert "0/100" in svg
