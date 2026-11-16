"""Integer-sample-delay discrete multipath summation kernel."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def apply_integer_delay_paths(
    transmitted_samples: NDArray[np.complexfloating],
    coefficient_history: NDArray[np.complexfloating],
    delays_samples: tuple[int, ...],
) -> tuple[NDArray[np.complex128], NDArray[np.complex128], NDArray[np.int64]]:
    """Return path contributions, their sum, and source-sample index matrix.

    For output sample n and path l: contribution[l,n] = h[l,n] x[n-d[l]],
    with x outside [0,N) equal to zero. The result timeline extends by max(delay).
    """
    tx = np.asarray(transmitted_samples, dtype=np.complex128)
    coeff = np.asarray(coefficient_history, dtype=np.complex128)
    delays = tuple(delays_samples)
    if tx.ndim != 1 or tx.size == 0 or not np.all(np.isfinite(tx)):
        raise ValueError("transmitted_samples must be a nonempty finite vector")
    if not delays or any(type(delay) is not int or delay < 0 for delay in delays):
        raise ValueError("delays_samples must contain non-negative integer sample delays")
    out_length = tx.size + max(delays)
    if coeff.shape != (len(delays), out_length) or not np.all(np.isfinite(coeff)):
        raise ValueError("coefficient_history shape must be (path_count, tx_length+max_delay)")
    times = np.arange(out_length, dtype=np.int64)
    source_indices = np.stack([times - delay for delay in delays], axis=0)
    contributions = np.zeros((len(delays), out_length), dtype=np.complex128)
    for path_index, indices in enumerate(source_indices):
        valid = (indices >= 0) & (indices < tx.size)
        contributions[path_index, valid] = coeff[path_index, valid] * tx[indices[valid]]
    faded = np.sum(contributions, axis=0, dtype=np.complex128)
    return contributions, faded, source_indices
