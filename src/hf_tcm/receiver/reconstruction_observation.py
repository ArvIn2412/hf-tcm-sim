"""Explicit observed-I/Q extraction for the narrow accepted ADR-012 profile."""

from __future__ import annotations

from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]

ADR012_PROFILE = "reconstructed_offline"
ADR012_PROFILE_ID = "adr012_l1_real_mean8"
ADR012_IQ_RULE = "adr012_minus_imaginary_real_mean8"
ADR012_WAVEFORM_RULE = "rectangular_zoh"
ADR012_SAMPLES_PER_SYMBOL = 8


def _absolute_integer(value: object, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer absolute index")
    return int(value)


def extract_adr012_observed_iq(
    received: ArrayLike,
    *,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    target_symbol_index: int,
    profile: str,
    adr_profile: str,
    path_count: int,
    path_delays_samples: tuple[int, ...] | list[int],
    samples_per_symbol: int,
    iq_rule: str,
    waveform_rule: str,
) -> FloatArray:
    """Return ``(mean(-Im(received)), mean(Re(received)))`` for one symbol.

    The caller supplies a one-dimensional aggregate complex buffer and its
    absolute labels. Only the selected eight samples are inspected for
    finiteness, so later buffer values cannot affect this observation.
    """
    samples_iq = extract_adr012_observed_iq_samples(
        received,
        absolute_sample_indices=absolute_sample_indices,
        received_start_sample=received_start_sample,
        symbol_origin_sample=symbol_origin_sample,
        target_symbol_index=target_symbol_index,
        profile=profile,
        adr_profile=adr_profile,
        path_count=path_count,
        path_delays_samples=path_delays_samples,
        samples_per_symbol=samples_per_symbol,
        iq_rule=iq_rule,
        waveform_rule=waveform_rule,
    )
    return np.mean(samples_iq, axis=0, dtype=np.float64)


def extract_adr012_observed_iq_samples(
    received: ArrayLike,
    *,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    target_symbol_index: int,
    profile: str,
    adr_profile: str,
    path_count: int,
    path_delays_samples: tuple[int, ...] | list[int],
    samples_per_symbol: int,
    iq_rule: str,
    waveform_rule: str,
) -> FloatArray:
    """Return the eight per-sample ADR-012 ``(-Im, Re)`` observations."""
    start = _absolute_integer(received_start_sample, name="received_start_sample")
    origin = _absolute_integer(symbol_origin_sample, name="symbol_origin_sample")
    symbol = _absolute_integer(target_symbol_index, name="target_symbol_index")
    if symbol < 0:
        raise ValueError("target_symbol_index must be non-negative")
    if profile != ADR012_PROFILE:
        raise ValueError("profile must be 'reconstructed_offline' for ADR-012")
    if adr_profile != ADR012_PROFILE_ID:
        raise ValueError("adr_profile must be the exact accepted ADR-012 L=1 profile")
    if isinstance(path_count, (bool, np.bool_)) or not isinstance(path_count, Integral):
        raise ValueError("path_count must be integer 1 for ADR-012")
    if int(path_count) != 1:
        raise ValueError("ADR-012 requires L=1")
    delays = tuple(path_delays_samples)
    if (
        len(delays) != 1
        or isinstance(delays[0], (bool, np.bool_))
        or not isinstance(delays[0], Integral)
        or int(delays[0]) != 0
    ):
        raise ValueError("ADR-012 requires exactly one zero-delay path")
    if samples_per_symbol != ADR012_SAMPLES_PER_SYMBOL:
        raise ValueError("ADR-012 requires exactly 8 samples per symbol")
    if iq_rule != ADR012_IQ_RULE:
        raise ValueError("iq_rule must select the exact ADR-012 I/Q mapping and mean")
    if waveform_rule != ADR012_WAVEFORM_RULE:
        raise ValueError("ADR-012 requires rectangular ZOH")

    try:
        samples = np.asarray(received)
        labels_raw = np.asarray(absolute_sample_indices)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("received and absolute_sample_indices must be arrays") from exc
    if samples.ndim != 1 or not np.iscomplexobj(samples):
        raise ValueError("received must be a one-dimensional complex aggregate buffer")
    if labels_raw.ndim != 1 or labels_raw.shape != samples.shape:
        raise ValueError("absolute_sample_indices must label every received buffer element")
    if labels_raw.dtype.kind not in "iu" or labels_raw.dtype.kind == "b":
        raise ValueError("absolute_sample_indices must contain integer labels")
    labels = labels_raw.astype(np.int64, copy=False)
    expected_buffer_labels = np.arange(start, start + samples.size, dtype=np.int64)
    if not np.array_equal(labels, expected_buffer_labels):
        raise ValueError("absolute_sample_indices must be contiguous from received_start_sample")

    first_sample = origin + ADR012_SAMPLES_PER_SYMBOL * symbol
    target_labels = np.arange(
        first_sample, first_sample + ADR012_SAMPLES_PER_SYMBOL, dtype=np.int64
    )
    if first_sample < start or target_labels[-1] >= start + samples.size:
        raise ValueError("received buffer does not contain the complete target symbol window")
    offset = first_sample - start
    window = samples[offset : offset + ADR012_SAMPLES_PER_SYMBOL]
    if window.shape != (ADR012_SAMPLES_PER_SYMBOL,):
        raise ValueError("received buffer does not contain the complete target symbol window")
    if not np.array_equal(labels[offset : offset + ADR012_SAMPLES_PER_SYMBOL], target_labels):
        raise ValueError("sample indices do not match symbol origin and target symbol")
    if not np.all(np.isfinite(window.real)) or not np.all(np.isfinite(window.imag)):
        raise ValueError("target received symbol window must contain only finite samples")

    return np.column_stack((-window.imag, window.real)).astype(np.float64, copy=True)
