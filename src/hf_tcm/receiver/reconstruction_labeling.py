"""Explicit project reconstruction mapping from M1 output bits to 8PSK index.

This assumed profile is not a labeling established by article [A] and does not
identify the project's 16 hypotheses with the article's ``theta`` values.
"""

from collections.abc import Sequence

from hf_tcm.coding.hypotheses import Hypothesis
from hf_tcm.modulation.labeling import (
    BASELINE_ASSUMPTION,
    Label,
    label_to_index,
    normalize_label,
)

ASSUMED_NATURAL_BINARY = "assumed_natural_binary"
OUTPUT_BIT_ORDER = ("c2", "c1", "c0")


def _validate_profile_and_order(profile: str, bit_order: Sequence[str]) -> None:
    if type(profile) is not str or profile != ASSUMED_NATURAL_BINARY:
        raise ValueError(f"profile must be explicitly set to {ASSUMED_NATURAL_BINARY!r}")
    if (
        not isinstance(bit_order, Sequence)
        or isinstance(bit_order, (str, bytes))
        or tuple(bit_order) != OUTPUT_BIT_ORDER
    ):
        raise ValueError(f"bit_order must be explicitly set to {OUTPUT_BIT_ORDER!r}")


def output_bits_to_phase_index(
    output_bits: Sequence[int],
    *,
    profile: str,
    bit_order: Sequence[str],
) -> int:
    """Map an explicit M1 ``(c2, c1, c0)`` triple to ``b``.

    ``profile`` and ``bit_order`` are mandatory so callers cannot silently
    inherit this reconstruction assumption. The mapping delegates to M1's
    existing natural-binary label table rather than duplicating its logic.
    """
    _validate_profile_and_order(profile, bit_order)
    label: Label = normalize_label(output_bits)
    return label_to_index(label, profile=BASELINE_ASSUMPTION)


def hypothesis_to_phase_index(
    hypothesis: Hypothesis,
    *,
    profile: str,
    bit_order: Sequence[str],
) -> int:
    """Map a structural hypothesis through its output bits, never its ID."""
    if not isinstance(hypothesis, Hypothesis):
        raise TypeError("hypothesis must be a coding.Hypothesis")
    return output_bits_to_phase_index(
        hypothesis.output_bits,
        profile=profile,
        bit_order=bit_order,
    )
