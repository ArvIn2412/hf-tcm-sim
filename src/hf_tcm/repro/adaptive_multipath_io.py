"""NPZ/JSON persistence for adaptive REPRO-06C results (no evaluation truth)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.adaptive_multipath_receiver import AdaptiveMultipathReceiverResult


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_adaptive_result(
    result: AdaptiveMultipathReceiverResult, output_dir: str | Path
) -> dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    decisions = result.decisions
    arrays = {
        "branch_metric_rows": result.branch_metric_rows,
        "survivor_path_metrics": result.survivor_path_metrics,
        "estimator_mean_by_symbol_node": result.estimator_mean_by_symbol_node,
        "estimator_covariance_diag_by_symbol_node": result.estimator_covariance_diag_by_symbol_node,
        "decoded_information_pairs": result.decoded_information_pairs,
        "decoded_information_bits": result.decoded_information_bits,
        "decoded_edge_ids": result.decoded_edge_ids,
        "decoded_state_path": result.decoded_state_path,
        "decision_symbol_index": np.asarray(
            [row.symbol_index for row in decisions], dtype=np.int64
        ),
        "decision_available_at": np.asarray(
            [row.decision_available_at for row in decisions], dtype=np.int64
        ),
        "decision_traceback_depth": np.asarray(
            [row.traceback_depth_used for row in decisions], dtype=np.int64
        ),
        "decision_expanded_edge_id": np.asarray(
            [row.expanded_edge_id for row in decisions], dtype=np.int32
        ),
        "decision_input_pairs": np.asarray(
            [row.input_pair for row in decisions], dtype=np.int8
        ).reshape((-1, 2)),
        "innovation_energy_by_symbol_node": result.diagnostics["innovation_energy_by_symbol_node"],
        "survivor_edges_by_symbol_node": result.diagnostics["survivor_edges_by_symbol_node"],
        "predicted_samples_on_emitted_decisions": result.diagnostics[
            "predicted_samples_on_emitted_decisions"
        ],
    }
    npz_path = root / "adaptive_receiver.npz"
    np.savez_compressed(npz_path, **arrays)
    summary: dict[str, Any] = {
        "schema_version": "repro06c-adaptive-result-v1",
        "receiver_config": result.receiver_config,
        "receiver_profile_id": result.receiver_profile_id,
        "observation_sha256": result.observation_sha256,
        "config_sha256": result.config_sha256,
        "result_sha256": result.result_sha256,
        "metric_profile": result.metric_profile,
        "trellis_state_count": result.trellis_state_count,
        "trellis_edge_count": result.trellis_edge_count,
        "decoder_mode": result.decoder_mode,
        "traceback_depth": result.traceback_depth,
        "survivor_buffer_max_rows": result.survivor_buffer_max_rows,
        "final_path_metric": result.final_path_metric,
        "diagnostics": {
            key: value
            for key, value in result.diagnostics.items()
            if not isinstance(value, np.ndarray)
        },
        "arrays": {
            key: {"shape": list(value.shape), "dtype": str(value.dtype)}
            for key, value in arrays.items()
        },
        "npz_sha256": sha256_file(npz_path),
        "reproducibility_metadata": result.reproducibility_metadata,
        "paper_exact": False,
        "receiver_enabled": False,
    }
    summary_path = root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    files = {npz_path.name: sha256_file(npz_path), summary_path.name: sha256_file(summary_path)}
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"schema_version": "repro06c-adaptive-result-v1", "files": files},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {**files, manifest_path.name: sha256_file(manifest_path)}


def verify_adaptive_result(output_dir: str | Path) -> dict[str, str]:
    root = Path(output_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    actual = {name: sha256_file(root / name) for name in manifest["files"]}
    if actual != manifest["files"]:
        raise ValueError("REPRO-06C output manifest integrity failure")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    if summary["npz_sha256"] != actual["adaptive_receiver.npz"]:
        raise ValueError("REPRO-06C output array file hash mismatch")
    with np.load(root / "adaptive_receiver.npz", allow_pickle=False) as archive:
        if set(archive.files) != set(summary["arrays"]):
            raise ValueError("REPRO-06C output array schema mismatch")
        for name, metadata in summary["arrays"].items():
            value = archive[name]
            if list(value.shape) != metadata["shape"] or str(value.dtype) != metadata["dtype"]:
                raise ValueError(f"REPRO-06C array schema mismatch: {name}")
    return actual
