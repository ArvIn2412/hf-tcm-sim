"""Explicit 8PSK bit labeling; the scientific labeling remains unresolved."""

from collections.abc import Sequence

Label = tuple[int, int, int]
BASELINE_ASSUMPTION = "baseline_assumption"

# Natural binary order is only a reproducible project baseline, not paper labeling.
_BASELINE_LABELS: tuple[Label, ...] = (
    (0, 0, 0),
    (0, 0, 1),
    (0, 1, 0),
    (0, 1, 1),
    (1, 0, 0),
    (1, 0, 1),
    (1, 1, 0),
    (1, 1, 1),
)
_LABEL_TO_INDEX = {label: index for index, label in enumerate(_BASELINE_LABELS)}


def validate_profile(profile: str) -> None:
    if profile != BASELINE_ASSUMPTION:
        raise ValueError(f"Only the explicit {BASELINE_ASSUMPTION!r} labeling profile is available")


def normalize_label(label: Sequence[int]) -> Label:
    """Validate and normalize one three-bit label."""
    try:
        bits = tuple(label)
    except TypeError as exc:
        raise ValueError("label must contain exactly three integer bits (0 or 1)") from exc
    if len(bits) != 3 or any(type(bit) is not int or bit not in (0, 1) for bit in bits):
        raise ValueError("label must contain exactly three integer bits (0 or 1)")
    return bits  # type: ignore[return-value]


def label_to_index(label: Sequence[int], *, profile: str = BASELINE_ASSUMPTION) -> int:
    """Map a coded triple to its constellation index under a named profile."""
    validate_profile(profile)
    return _LABEL_TO_INDEX[normalize_label(label)]


def index_to_label(index: int, *, profile: str = BASELINE_ASSUMPTION) -> Label:
    """Map a constellation index back to its coded triple."""
    validate_profile(profile)
    if type(index) is not int or not 0 <= index < len(_BASELINE_LABELS):
        raise ValueError("index must be an integer from 0 through 7")
    return _BASELINE_LABELS[index]
