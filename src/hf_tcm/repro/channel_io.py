"""Load a previously saved REPRO-02 transmitter result with integrity checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.serialization import ARRAY_FIELDS
from hf_tcm.repro.transmitter import TransmitterResult


def _array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def load_transmitter_result(directory: str | Path) -> TransmitterResult:
    """Load and verify all REPRO-02 arrays before constructing the typed contract."""
    root = Path(directory)
    try:
        manifest: dict[str, Any] = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
        config = json.loads((root / "input_config.json").read_text(encoding="utf-8"))
        mapping = json.loads((root / "mapping_table.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid REPRO-02 transmitter bundle: {root}") from exc
    with np.load(root / "arrays.npz", allow_pickle=False) as bundle:
        arrays = {name: np.array(bundle[name], copy=True) for name in bundle.files}
    if set(arrays) != set(ARRAY_FIELDS):
        raise ValueError("transmitter bundle array field set is incomplete or unexpected")
    metadata = manifest.get("arrays", {})
    if set(metadata) != set(arrays):
        raise ValueError("transmitter manifest does not enumerate all arrays")
    for name, array in arrays.items():
        entry = metadata[name]
        if list(array.shape) != entry.get("shape") or str(array.dtype) != entry.get("dtype"):
            raise ValueError(f"transmitter array shape/dtype mismatch: {name}")
        if _array_sha256(array) != entry.get("sha256"):
            raise ValueError(f"transmitter array SHA-256 mismatch: {name}")
    if summary.get("paper_exact") is not False or summary.get("receiver_enabled") is not False:
        raise ValueError("transmitter fidelity flags are not the frozen REPRO-02 values")
    if (
        manifest.get("container", {}).get("sha256")
        != hashlib.sha256((root / "arrays.npz").read_bytes()).hexdigest()
    ):
        raise ValueError("transmitter NPZ container SHA-256 mismatch")
    return TransmitterResult(
        **arrays,
        final_state=tuple(summary["final_state"]),
        termination_metadata=summary["termination_metadata"],
        source_metadata=summary["source_metadata"],
        config_snapshot=config,
        encoder_id=summary["encoder_id"],
        mapping_id=summary["mapping_id"],
        mapping_status=summary["mapping_status"],
        mapping_table=tuple(mapping),
        mapping_fingerprint=summary["mapping_fingerprint"],
        source_spec_id=summary["source_spec_id"],
        source_file_sha256=summary["source_file_sha256"],
        source_fingerprint=summary["source_fingerprint"],
        waveform_rule=summary["waveform_rule"],
        samples_per_symbol=int(summary["samples_per_symbol"]),
        paper_exact=False,
        receiver_enabled=False,
    )
