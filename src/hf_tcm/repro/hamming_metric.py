"""Integer Hamming branch costs for canonical Encoder A edges."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.encoder import transition_table

EDGE_TABLE = transition_table()
EDGE_OUTPUTS = np.asarray([row[3] for row in EDGE_TABLE], dtype=np.int8)


def hamming_edge_costs(received_triple: object) -> NDArray[np.int8]:
    observed = np.asarray(received_triple)
    if (
        observed.shape != (3,)
        or observed.dtype.kind not in "iu"
        or np.any(observed > 1)
        or np.any(observed < 0)
    ):
        raise ValueError("received_triple must be three integer bits")
    return np.count_nonzero(EDGE_OUTPUTS != observed.astype(np.int8), axis=1).astype(np.int8)


def hamming_metric_matrix(received_triples: object) -> NDArray[np.int8]:
    triples = np.asarray(received_triples)
    if triples.ndim != 2 or triples.shape[1] != 3 or triples.dtype.kind not in "iu":
        raise ValueError("received_triples must have shape (F,3) and integer dtype")
    if np.any(triples < 0) or np.any(triples > 1):
        raise ValueError("received_triples may contain only 0 and 1")
    return np.count_nonzero(triples[:, None, :] != EDGE_OUTPUTS[None, :, :], axis=2).astype(np.int8)
