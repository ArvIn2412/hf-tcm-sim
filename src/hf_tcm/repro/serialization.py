"""Portable JSON metadata and NumPy-array artifacts for transmitter runs."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.config import SCHEMA_VERSION
from hf_tcm.repro.transmitter import TransmitterResult

ARRAY_FIELDS = (
    "information_bits",
    "payload_input_pairs",
    "input_pairs",
    "coded_triples",
    "pre_states",
    "post_states",
    "state_history",
    "edge_ids",
    "phase_indices",
    "phase_values_rad",
    "symbols",
    "symbol_i",
    "symbol_q",
    "symbol_energies",
    "tx_samples",
    "absolute_sample_index",
    "sample_symbol_index",
    "sample_local_index",
    "sample_tx_i",
    "sample_tx_q",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"value of type {type(value).__name__} is not JSON serializable")


def _array_digest(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


def save_transmitter_result(result: TransmitterResult, output_dir: str | Path) -> dict[str, Any]:
    """Write a run without pickle; return its machine-readable manifest."""
    if not isinstance(result, TransmitterResult):
        raise TypeError("result must be a TransmitterResult")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    arrays = {name: getattr(result, name) for name in ARRAY_FIELDS}
    if any(not isinstance(array, np.ndarray) or array.dtype.hasobject for array in arrays.values()):
        raise ValueError("all serialized arrays must be numeric NumPy arrays")
    arrays_path = destination / "arrays.npz"
    np.savez_compressed(arrays_path, **arrays)
    arrays_meta = {
        name: {
            "shape": list(array.shape),
            "dtype": str(array.dtype),
            "sha256": _array_digest(array),
        }
        for name, array in arrays.items()
    }
    config = _jsonable(result.config_snapshot)
    source_metadata = _jsonable(result.source_metadata)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "encoder_id": result.encoder_id,
        "mapping_id": result.mapping_id,
        "mapping_status": result.mapping_status,
        "mapping_fingerprint": result.mapping_fingerprint,
        "source_spec_id": result.source_spec_id,
        "source_file_sha256": result.source_file_sha256,
        "source_fingerprint": result.source_fingerprint,
        "paper_exact": False,
        "receiver_enabled": False,
        "frame_symbols": int(len(result.payload_input_pairs)),
        "information_bit_count": int(len(result.information_bits)),
        "encoded_step_count": int(len(result.coded_triples)),
        "encoded_bit_count": int(result.coded_triples.size),
        "sample_count": int(len(result.tx_samples)),
        "samples_per_symbol": result.samples_per_symbol,
        "waveform_rule": result.waveform_rule,
        "initial_state": list(result.config_snapshot["initial_state"]),
        "final_state": list(result.final_state),
        "termination_metadata": _jsonable(result.termination_metadata),
        "source_metadata": source_metadata,
    }
    json_files = {
        "input_config.json": config,
        "mapping_table.json": _jsonable(result.mapping_table),
        "summary.json": summary,
    }
    for filename, content in json_files.items():
        (destination / filename).write_text(
            json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "config_sha256": hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "mapping_fingerprint": result.mapping_fingerprint,
        "source_fingerprint": result.source_fingerprint,
        "source_file_sha256": result.source_file_sha256,
        "arrays": arrays_meta,
        "container": {
            "file": arrays_path.name,
            "sha256": hashlib.sha256(arrays_path.read_bytes()).hexdigest(),
            "format": "numpy savez_compressed; allow_pickle=False on load",
        },
        "json_files": {
            filename: hashlib.sha256((destination / filename).read_bytes()).hexdigest()
            for filename in json_files
        },
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_transmitter_arrays(path: str | Path) -> dict[str, np.ndarray]:
    """Load only numeric NPZ arrays; pickle-backed objects are disabled."""
    with np.load(Path(path), allow_pickle=False) as archive:
        return {name: np.array(archive[name], copy=True) for name in archive.files}
