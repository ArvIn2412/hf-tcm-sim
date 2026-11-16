"""Hashed NPZ/JSON persistence for REPRO-05 receiver-only results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.joint_receiver import JointReceiverResult


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_joint_receiver_result(
    result: JointReceiverResult, output_dir: str | Path
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    decisions = result.diagnostics.get("decision_records", [])
    arrays = {
        name: getattr(result, name)
        for name in (
            "sample_indices",
            "sample_ranges",
            "unprocessed_sample_indices",
            "candidate_edge_ids",
            "candidate_source_states",
            "candidate_target_states",
            "candidate_input_pairs",
            "candidate_coded_triples",
            "candidate_phase_indices",
            "candidate_symbols",
            "candidate_estimator_state_used",
            "candidate_predictions",
            "metric_rows",
            "posterior_weights",
            "estimator_state_pre",
            "estimator_pre",
            "estimator_state_post",
            "estimator_post",
            "innovation",
            "viterbi_state_metrics",
            "survivor_edge_ids",
            "decoded_edge_ids",
            "decoded_state_path",
            "decoded_information_pairs",
            "decoded_information_bits",
            "decoded_frame_information_bits",
        )
    }
    arrays.update(
        {
            "decision_symbol_index": np.asarray(
                [row["symbol_index"] for row in decisions], dtype=np.int64
            ),
            "decision_available_at": np.asarray(
                [row["decision_available_at"] for row in decisions], dtype=np.int64
            ),
            "decision_traceback_depth_used": np.asarray(
                [row["traceback_depth_used"] for row in decisions], dtype=np.int64
            ),
            "decision_selected_edge_id": np.asarray(
                [row["edge_id"] for row in decisions], dtype=np.int16
            ),
            "decision_input_pairs": np.asarray(
                [row["input_pair"] for row in decisions], dtype=np.int8
            ).reshape((-1, 2)),
            "decision_source_states": np.asarray(
                [row["source_state"] for row in decisions], dtype=np.int8
            ).reshape((-1, 2)),
            "decision_target_states": np.asarray(
                [row["target_state"] for row in decisions], dtype=np.int8
            ).reshape((-1, 2)),
        }
    )
    npz_path = root / "joint_receiver_result.npz"
    np.savez_compressed(npz_path, **arrays)
    summary: dict[str, Any] = {
        "schema_version": "repro05-joint-receiver-v1",
        "receiver_config": result.receiver_config,
        "observation_sha256": result.observation_sha256,
        "config_sha256": result.config_sha256,
        "receiver_profile_id": result.receiver_profile_id,
        "metric_profile": result.metric_profile,
        "encoder_id": result.encoder_id,
        "mapping_id": result.mapping_id,
        "mapping_status": result.mapping_status,
        "mapping_fingerprint": result.mapping_fingerprint,
        "edge_order_id": result.edge_order_id,
        "output_npz_sha256": _sha(npz_path.read_bytes()),
        "output_arrays": {
            name: {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "sha256": _sha(np.ascontiguousarray(array).tobytes()),
            }
            for name, array in arrays.items()
        },
        "final_state": list(result.final_state),
        "final_path_metric": result.final_path_metric,
        "traceback_mode": result.traceback_mode,
        "decoder_depth": result.decoder_depth,
        "diagnostics": result.diagnostics,
        "reproducibility_metadata": result.reproducibility_metadata,
        "result_sha256": result.result_sha256,
        "paper_exact": False,
        "receiver_enabled": False,
    }
    summary_path = root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "repro05-joint-receiver-v1",
        "files": {
            npz_path.name: _sha(npz_path.read_bytes()),
            summary_path.name: _sha(summary_path.read_bytes()),
        },
        "observation_sha256": result.observation_sha256,
        "config_sha256": result.config_sha256,
        "result_sha256": result.result_sha256,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
