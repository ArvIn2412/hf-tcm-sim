"""Frame-level BER and 8PSK symbol-error counts for M2 baselines."""

from collections.abc import Iterable
from dataclasses import dataclass

from hf_tcm.coding.encoder import BitPair
from hf_tcm.modulation.labeling import normalize_label


@dataclass(frozen=True, slots=True)
class ErrorMetrics:
    """Raw bit and 8PSK symbol counts, with ratios derived from their denominators."""

    bit_errors: int
    info_bits_checked: int
    symbol_errors: int
    symbols_checked: int

    @property
    def ber(self) -> float:
        return self.bit_errors / self.info_bits_checked

    @property
    def ser(self) -> float:
        return self.symbol_errors / self.symbols_checked


def _pairs(values: Iterable[Iterable[int]], *, name: str) -> tuple[BitPair, ...]:
    try:
        pairs = tuple(tuple(pair) for pair in values)
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence of bit pairs") from exc
    if any(
        len(pair) != 2 or any(type(bit) is not int or bit not in (0, 1) for bit in pair)
        for pair in pairs
    ):
        raise ValueError(f"{name} must contain only pairs of integer bits")
    return pairs  # type: ignore[return-value]


def compute_error_metrics(
    tx_info_pairs: Iterable[Iterable[int]],
    decoded_info_pairs: Iterable[Iterable[int]],
    tx_labels: Iterable[Iterable[int]],
    detected_labels: Iterable[Iterable[int]],
    *,
    valid_steps: int | None = None,
) -> ErrorMetrics:
    """Count information-bit BER and hard 8PSK decision SER over valid steps.

    ``valid_steps`` trims the same suffix from the information and symbol
    sequences, allowing callers to exclude any explicitly added tail steps.
    M2 itself adds no termination bits.
    """
    tx_pairs = _pairs(tx_info_pairs, name="tx_info_pairs")
    rx_pairs = _pairs(decoded_info_pairs, name="decoded_info_pairs")
    tx_symbols = tuple(normalize_label(label) for label in tx_labels)
    rx_symbols = tuple(normalize_label(label) for label in detected_labels)
    lengths = {len(tx_pairs), len(rx_pairs), len(tx_symbols), len(rx_symbols)}
    if len(lengths) != 1:
        raise ValueError("input-pair and symbol sequences must have the same length")
    steps = len(tx_pairs) if valid_steps is None else valid_steps
    if type(steps) is not int or not 1 <= steps <= len(tx_pairs):
        raise ValueError("valid_steps must be a positive count within the frame")
    bit_errors = sum(
        tx_bit != rx_bit
        for tx_pair, rx_pair in zip(tx_pairs[:steps], rx_pairs[:steps], strict=True)
        for tx_bit, rx_bit in zip(tx_pair, rx_pair, strict=True)
    )
    symbol_errors = sum(
        tx_label != rx_label
        for tx_label, rx_label in zip(tx_symbols[:steps], rx_symbols[:steps], strict=True)
    )
    return ErrorMetrics(
        bit_errors=bit_errors,
        info_bits_checked=2 * steps,
        symbol_errors=symbol_errors,
        symbols_checked=steps,
    )
