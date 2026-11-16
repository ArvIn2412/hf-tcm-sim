"""Versioned project reconstruction from Encoder A edges to 8PSK indices."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.encoder import EncoderResult, transition_table
from hf_tcm.repro.identifiers import MAPPING_ID, MAPPING_STATUS


def _immutable(values: object, dtype: np.dtype) -> NDArray:
    owned = np.array(values, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(owned.shape)


def _phase_index(triple: tuple[int, int, int]) -> int:
    c2, c1, c0 = triple
    return 4 * c2 + 2 * c1 + c0


@dataclass(frozen=True, slots=True)
class EdgeMapping:
    mapping_id: str
    status: str
    edge_ids: NDArray[np.int16]
    phase_indices: NDArray[np.int8]
    fingerprint: str
    table: tuple[dict[str, object], ...]


def build_edge_mapping(encoded: EncoderResult) -> EdgeMapping:
    """Map output triples through ADR-002; edge ID does not choose the phase."""
    canonical = transition_table()
    full_table = tuple(
        {
            "edge_id": edge_id,
            "state": list(state),
            "input": list(pair),
            "output": list(output),
            "next_state": list(next_state),
            "phase_index": _phase_index(output),
        }
        for edge_id, state, pair, output, next_state in canonical
    )
    canonical_json = json.dumps(
        {
            "mapping_id": MAPPING_ID,
            "status": MAPPING_STATUS,
            "input_bit_order": ["c2", "c1", "c0"],
            "edge_order": "REPRO-01 state/input order",
            "table": full_table,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    phases = np.empty(len(encoded.edge_ids), dtype=np.int8)
    edge_ids = np.asarray(encoded.edge_ids, dtype=np.int16)
    for row, edge_value in enumerate(edge_ids):
        edge_id = int(edge_value)
        if not 0 <= edge_id < len(canonical):
            raise ValueError("encoder result contains an invalid edge_id")
        _, state, pair, output, _ = canonical[edge_id]
        if tuple(encoded.pre_states[row]) != state:
            raise ValueError("edge_id does not match the encoder pre-state")
        if tuple(encoded.input_pairs[row]) != pair:
            raise ValueError("edge_id does not match the encoder input pair")
        if tuple(encoded.coded_triples[row]) != output:
            raise ValueError("edge_id does not match the encoded output triple")
        phases[row] = _phase_index(tuple(int(bit) for bit in encoded.coded_triples[row]))
    return EdgeMapping(
        mapping_id=MAPPING_ID,
        status=MAPPING_STATUS,
        edge_ids=_immutable(edge_ids, np.dtype(np.int16)),
        phase_indices=_immutable(phases, np.dtype(np.int8)),
        fingerprint=fingerprint,
        table=full_table,
    )
