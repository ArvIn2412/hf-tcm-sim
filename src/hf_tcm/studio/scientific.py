"""REPRO-09 real-run adapter, persistence, and bounded trace access."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from hf_tcm.repro.adaptive_multipath_config import (
    AdaptiveMultipathReceiverConfig,
    AdaptivePathConfig,
)
from hf_tcm.repro.adaptive_multipath_io import verify_adaptive_result
from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver
from hf_tcm.repro.augmented_trellis import build_augmented_trellis
from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.encoder import STATE_ORDER, transition_table
from hf_tcm.repro.finite_viterbi import ViterbiConfig, run_viterbi
from hf_tcm.repro.information_pair_metrics import evaluate_information_pair_errors
from hf_tcm.repro.metric_experiment import MetricStudyConfig, run_metric_study
from hf_tcm.repro.paired_experiment import ExperimentConfig, run_paired_experiment
from hf_tcm.repro.receiver_config import ReceiverFrontEndConfig, SeparateReceiverConfig
from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.repro08_channel_aware_hard import (
    PublicStaticTap,
    Repro08HardReceiverConfig,
    run_channel_aware_hard_receiver,
)
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter
from hf_tcm.studio.energy import (
    EnergyStudyConfig,
    calculate_single_run_energy_metrics,
    run_energy_study,
)

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_DEFAULT_OUTPUT = Path("outputs/repro09")


@dataclass(frozen=True, slots=True)
class ScientificRunConfig:
    """Small, explicit GUI contract for a single paired scientific run."""

    run_id: str = ""
    frame_symbols: int = 256
    source_seed: int = 20261109
    channel_seed: int = 90209
    amplitude: float = 1.0
    channel_profile: Literal[
        "identity", "awgn", "static_single_path", "static_multipath", "rician_ar1_multipath"
    ] = "identity"
    noise_variance: float = 0.0
    delays_samples: tuple[int, ...] = (0,)
    path_coefficients: tuple[tuple[float, float], ...] = ((1.0, 0.0),)
    path_powers: tuple[float, ...] = (1.0, 0.25)
    rician_k_factors: tuple[float, ...] = (4.0, 1.0)
    los_phases_rad: tuple[float, ...] = (0.0, 0.7)
    fading_correlation: float = 0.98
    traceback_depth: int = 20
    include_b1: bool = False
    output_root: str = str(_DEFAULT_OUTPUT)
    schema_version: str = "repro09-single-run-v1"

    def __post_init__(self) -> None:
        if self.run_id and not _RUN_ID.fullmatch(self.run_id):
            raise ValueError("run_id must contain only safe filename characters")
        if type(self.frame_symbols) is not int or not 1 <= self.frame_symbols <= 20_000:
            raise ValueError("frame_symbols must be an integer in [1, 20000]")
        for name, value in (("source_seed", self.source_seed), ("channel_seed", self.channel_seed)):
            if type(value) is not int or not 0 <= value < 2**64:
                raise ValueError(f"{name} must be an unsigned 64-bit integer")
        if not math.isfinite(self.amplitude) or self.amplitude <= 0:
            raise ValueError("amplitude must be positive and finite")
        if self.channel_profile not in {
            "identity",
            "awgn",
            "static_single_path",
            "static_multipath",
            "rician_ar1_multipath",
        }:
            raise ValueError("unsupported channel_profile")
        if not math.isfinite(self.noise_variance) or self.noise_variance < 0:
            raise ValueError("noise_variance must be finite and non-negative")
        if self.channel_profile == "awgn" and self.noise_variance <= 0:
            raise ValueError("awgn profile requires positive sample-domain noise variance")
        if type(self.traceback_depth) is not int or self.traceback_depth < 1:
            raise ValueError("traceback_depth must be a positive integer")
        if type(self.include_b1) is not bool:
            raise ValueError("include_b1 must be a boolean")
        if self.include_b1:
            if self.channel_profile == "rician_ar1_multipath":
                raise ValueError("B1 supports only public static channel profiles")
            if max(self.delays_samples, default=0) >= 8:
                raise ValueError("B1 requires public static path delays below 8 samples")
        if self.channel_profile in {"identity", "awgn", "static_single_path"}:
            if len(self.delays_samples) != 1 or self.delays_samples[0] != 0:
                raise ValueError("single-path profiles require delays_samples=(0,)")
        if self.channel_profile == "identity" and self.noise_variance != 0:
            raise ValueError("identity profile requires zero noise; select awgn for noise")
        if any(type(delay) is not int or delay < 0 for delay in self.delays_samples):
            raise ValueError("delays_samples must be non-negative integer sample delays")
        if not self.delays_samples or max(self.delays_samples) > 15:
            raise ValueError("GUI adaptive profiles support delays up to 15 samples")
        count = len(self.delays_samples)
        if self.channel_profile in {"identity", "awgn", "static_single_path", "static_multipath"}:
            if len(self.path_coefficients) != count:
                raise ValueError("path_coefficients count must match delays_samples")
            if any(
                len(pair) != 2
                or not all(math.isfinite(float(v)) for v in pair)
                or complex(*pair) == 0j
                for pair in self.path_coefficients
            ):
                raise ValueError("path coefficients must be finite, nonzero [real, imag] pairs")
        if self.channel_profile == "rician_ar1_multipath":
            if not (
                len(self.path_powers)
                == len(self.rician_k_factors)
                == len(self.los_phases_rad)
                == count
            ):
                raise ValueError("Rician path parameter lists must match delays_samples")
            if any(not math.isfinite(x) or x <= 0 for x in self.path_powers):
                raise ValueError("path_powers must be positive and finite")
            if any(not math.isfinite(x) or x < 0 for x in self.rician_k_factors):
                raise ValueError("Rician K factors must be non-negative and finite")
            if not 0 <= self.fading_correlation < 1:
                raise ValueError("fading_correlation must be in [0,1)")
        if self.schema_version != "repro09-single-run-v1":
            raise ValueError("unsupported REPRO-09 run schema")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ScientificRunConfig:
        if not isinstance(values, dict):
            raise ValueError("run configuration must be a JSON object")
        extras = set(values) - set(cls.__dataclass_fields__)
        if extras:
            raise ValueError(f"unexpected run configuration field: {sorted(extras)[0]}")
        data = dict(values)
        for name in ("delays_samples", "path_powers", "rician_k_factors", "los_phases_rad"):
            if name in data:
                data[name] = tuple(data[name])
        if "path_coefficients" in data:
            data["path_coefficients"] = tuple(tuple(pair) for pair in data["path_coefficients"])
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid run configuration: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for name in (
            "delays_samples",
            "path_coefficients",
            "path_powers",
            "rician_k_factors",
            "los_phases_rad",
        ):
            data[name] = [list(item) if isinstance(item, tuple) else item for item in data[name]]
        return data


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _configs(
    config: ScientificRunConfig, frame: int
) -> tuple[
    TransmitterConfig, ChannelConfig, AdaptiveMultipathReceiverConfig, SeparateReceiverConfig
]:
    tx = TransmitterConfig(
        source_mode="seeded_random",
        frame_symbols=frame,
        seed=config.source_seed,
        amplitude=config.amplitude,
    )
    if config.channel_profile == "rician_ar1_multipath":
        paths = tuple(
            ChannelPathConfig(delay, power, k, phase)
            for delay, power, k, phase in zip(
                config.delays_samples,
                config.path_powers,
                config.rician_k_factors,
                config.los_phases_rad,
                strict=True,
            )
        )
        fading_mode = "rician_ar1"
        channel_mode = "rician_ar1"
        adaptive_paths = tuple(
            AdaptivePathConfig(delay, average_power=power, k_factor=k, los_phase_rad=phase)
            for delay, power, k, phase in zip(
                config.delays_samples,
                config.path_powers,
                config.rician_k_factors,
                config.los_phases_rad,
                strict=True,
            )
        )
    else:
        coefficient_pairs = (
            ((1.0, 0.0),)
            if config.channel_profile in {"identity", "awgn"}
            else config.path_coefficients
        )
        paths = tuple(
            ChannelPathConfig(
                delay, float(abs(complex(*pair)) ** 2), 0.0, constant_coefficient=complex(*pair)
            )
            for delay, pair in zip(config.delays_samples, coefficient_pairs, strict=True)
        )
        fading_mode = "constant"
        channel_mode = "unknown_static"
        adaptive_paths = tuple(
            AdaptivePathConfig(delay, prior_mean=complex(*pair), prior_variance=1.0)
            for delay, pair in zip(config.delays_samples, coefficient_pairs, strict=True)
        )
    noise_model = "complex_awgn_sample_domain" if config.noise_variance > 0 else "none"
    channel = ChannelConfig(
        profile_id=config.channel_profile,
        paths=paths,
        fading_mode=fading_mode,
        noise_model=noise_model,
        noise_complex_variance=config.noise_variance,
        fading_seed=config.channel_seed,
        noise_seed=(config.channel_seed + 1) % 2**64,
        correlation=config.fading_correlation if fading_mode == "rician_ar1" else 0.0,
    )
    adaptive = AdaptiveMultipathReceiverConfig(
        expected_symbol_count=frame,
        paths=adaptive_paths,
        channel_mode=channel_mode,
        observation_noise_variance=config.noise_variance,
        amplitude=config.amplitude,
        correlation=config.fading_correlation if channel_mode == "rician_ar1" else 1.0,
        metric_profile="squared_euclidean",
        decoder_mode="finite_depth",
        traceback_depth=config.traceback_depth,
        trace_output_mode="compact",
    )
    separate = SeparateReceiverConfig(
        expected_symbol_count=frame,
        front_end=ReceiverFrontEndConfig(amplitude=config.amplitude),
        decoder_mode="finite_depth",
        traceback_depth=config.traceback_depth,
        trace_output_mode="compact",
    )
    return tx, channel, adaptive, separate


def _finite_diagnostics(metric_rows: np.ndarray, frame: int, traceback_depth: int):
    return run_viterbi(
        metric_rows,
        ViterbiConfig(
            initial_state=(0, 0),
            decoder_mode="finite_depth",
            traceback_depth=traceback_depth,
            expected_symbol_count=frame,
            trace_output_mode="full",
        ),
    )


def _decision_arrays(decisions: object, *, expanded: bool = False) -> dict[str, np.ndarray]:
    rows = tuple(decisions)
    edge_name = "expanded_edge_id" if expanded else "edge_id"
    return {
        "symbol_index": np.asarray([row.symbol_index for row in rows], dtype=np.int64),
        "available_at": np.asarray([row.decision_available_at for row in rows], dtype=np.int64),
        "traceback_depth": np.asarray([row.traceback_depth_used for row in rows], dtype=np.int16),
        "edge_id": np.asarray([getattr(row, edge_name) for row in rows], dtype=np.int32),
        "input_pairs": np.asarray([row.input_pair for row in rows], dtype=np.int8).reshape((-1, 2)),
    }


def run_scientific_run(config: ScientificRunConfig) -> dict[str, Any]:
    """Run the real REPRO-02/03/04/06C pipeline and persist one paired result."""
    if not isinstance(config, ScientificRunConfig):
        raise TypeError("config must be ScientificRunConfig")
    run_id = config.run_id or f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("run_id must contain only safe filename characters")
    root = (Path(config.output_root) / run_id).resolve()
    root.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    tx_config, channel_config, joint_config, separate_config = _configs(
        config, config.frame_symbols
    )
    transmitter = run_transmitter(tx_config)
    channel = run_channel(transmitter, channel_config)
    observation = channel.receiver_observation
    # Receivers receive only the same public ReceiverObservation object.
    joint_started = time.perf_counter()
    joint = run_adaptive_multipath_receiver(observation, joint_config)
    joint_seconds = time.perf_counter() - joint_started
    separate_started = time.perf_counter()
    separate = run_separate_receiver(observation, separate_config)
    separate_seconds = time.perf_counter() - separate_started
    # Read-only Viterbi replays retain node metrics and predecessor edges for the UI.
    # They use exactly the already-computed branch rows and are checked against each
    # receiver's returned decoded path; they cannot change receiver decisions.
    separate_viterbi = _finite_diagnostics(
        separate.hamming_branch_metrics, config.frame_symbols, config.traceback_depth
    )
    if not np.array_equal(separate_viterbi.decoded_edge_ids, separate.decoded_edge_ids):
        raise RuntimeError("read-only B0 Viterbi diagnostics do not reproduce decoder output")
    b1 = None
    b1_viterbi = None
    b1_seconds = None
    if config.include_b1:
        if config.channel_profile in {"identity", "awgn"}:
            coefficients = ((1.0, 0.0),)
            delays = (0,)
        else:
            coefficients = config.path_coefficients
            delays = config.delays_samples
        b1_config = Repro08HardReceiverConfig(
            expected_symbol_count=config.frame_symbols,
            taps=tuple(
                PublicStaticTap(delay_samples=delay, coefficient=complex(*pair))
                for delay, pair in zip(delays, coefficients, strict=True)
            ),
            traceback_depth=config.traceback_depth,
            amplitude=config.amplitude,
        )
        b1_started = time.perf_counter()
        b1 = run_channel_aware_hard_receiver(observation, b1_config)
        b1_seconds = time.perf_counter() - b1_started
        b1_viterbi = _finite_diagnostics(
            b1.hamming_branch_metrics, config.frame_symbols, config.traceback_depth
        )
        if not np.array_equal(b1_viterbi.decoded_edge_ids, b1.decoded_edge_ids):
            raise RuntimeError("read-only B1 Viterbi diagnostics do not reproduce decoder output")
    ref_bits = transmitter.information_bits
    ref_phases = transmitter.phase_indices
    sep_eval = evaluate_separate_receiver(separate, ref_bits, ref_phases)
    sep_pair_eval = evaluate_information_pair_errors(ref_bits, separate.decoded_information_bits)
    joint_bits = np.asarray(joint.decoded_information_bits[: len(ref_bits)], dtype=np.int8)
    joint_pair_eval = evaluate_information_pair_errors(ref_bits, joint_bits)
    joint_bit_mask = joint_bits != ref_bits
    joint_edges_phase = np.asarray(
        [row[3][0] * 4 + row[3][1] * 2 + row[3][2] for row in transition_table()],
        dtype=np.int8,
    )
    joint_phases = joint_edges_phase[
        np.asarray(joint.decoded_edge_ids[: len(ref_phases)], dtype=np.int64)
    ]
    joint_symbol_mask = joint_phases != ref_phases
    b1_evaluation = None
    b1_phase_errors = None
    if b1 is not None:
        b1_bits = np.asarray(b1.decoded_information_bits[: len(ref_bits)], dtype=np.int8)
        b1_pair_eval = evaluate_information_pair_errors(ref_bits, b1_bits)
        b1_bit_mask = b1_bits != ref_bits
        b1_phases = joint_edges_phase[
            np.asarray(b1.decoded_edge_ids[: len(ref_phases)], dtype=np.int64)
        ]
        b1_phase_errors = b1_phases != ref_phases
        b1_evaluation = {
            "profile_id": b1.receiver_profile_id,
            "observation_sha256": b1.observation_sha256,
            "decoder_mode": b1.decoder_mode,
            "traceback_depth": b1.traceback_depth,
            "compared_bits": int(len(ref_bits)),
            "bit_errors": int(np.count_nonzero(b1_bit_mask)),
            "ber": float(np.mean(b1_bit_mask)),
            "compared_information_pairs": b1_pair_eval.compared_pairs,
            "information_pair_errors": b1_pair_eval.pair_errors,
            "information_pair_ser": b1_pair_eval.pair_ser,
            "information_pair_error_positions": b1_pair_eval.pair_error_positions.tolist(),
            "compared_phase_symbols": int(len(ref_phases)),
            "phase_symbol_errors": int(np.count_nonzero(b1_phase_errors)),
            "phase_symbol_ser": float(np.mean(b1_phase_errors)),
            "phase_symbol_error_positions": np.flatnonzero(b1_phase_errors).tolist(),
            "symbol_metric_semantics": "decoded_encoder_edge_phase",
            "compared_symbols": int(len(ref_phases)),
            "symbol_errors": int(np.count_nonzero(b1_phase_errors)),
            "ser": float(np.mean(b1_phase_errors)),
            "bit_error_positions": np.flatnonzero(b1_bit_mask).tolist(),
            "symbol_error_positions": np.flatnonzero(b1_phase_errors).tolist(),
            "runtime_seconds": float(b1_seconds),
            "channel_information": "explicit_public_static_taps",
        }
    ended = time.perf_counter()
    config_dict = config.to_dict()
    config_dict["run_id"] = run_id
    config_bytes = json.dumps(
        config_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    traces = {
        "information_bits": transmitter.information_bits,
        "input_pairs": transmitter.payload_input_pairs,
        "coded_triples": transmitter.coded_triples,
        "pre_states": transmitter.pre_states,
        "post_states": transmitter.post_states,
        "edge_ids": transmitter.edge_ids,
        "phase_indices": transmitter.phase_indices,
        "phase_values_rad": transmitter.phase_values_rad,
        "symbols": transmitter.symbols,
        "tx_samples": transmitter.tx_samples,
        "received_samples": observation.received_samples,
        "hamming_metrics": separate.hamming_branch_metrics,
        "hard_phase_indices": separate.hard_phase_indices,
        "joint_metrics": joint.branch_metric_rows,
        "joint_estimator_means": joint.estimator_mean_by_symbol_node,
        "joint_covariance_diag": joint.estimator_covariance_diag_by_symbol_node,
        "joint_decoded_bits": joint.decoded_information_bits,
        "joint_decoded_edges": joint.decoded_edge_ids,
        "joint_survivor_edges": joint.diagnostics["survivor_edges_by_symbol_node"],
        "joint_path_metrics": joint.survivor_path_metrics,
        "joint_decision_symbol_index": np.asarray(
            [row.symbol_index for row in joint.decisions], dtype=np.int64
        ),
        "joint_decision_available_at": np.asarray(
            [row.decision_available_at for row in joint.decisions], dtype=np.int64
        ),
        "joint_decision_traceback_depth": np.asarray(
            [row.traceback_depth_used for row in joint.decisions], dtype=np.int16
        ),
        "joint_decision_expanded_edge_id": np.asarray(
            [row.expanded_edge_id for row in joint.decisions], dtype=np.int32
        ),
        "b0_survivor_edges": separate_viterbi.survivor_edge_ids,
        "b0_path_metrics": separate_viterbi.state_metrics[1:],
        "b0_decision_symbol_index": np.asarray(
            [row.symbol_index for row in separate_viterbi.decisions], dtype=np.int64
        ),
        "b0_decision_available_at": np.asarray(
            [row.decision_available_at for row in separate_viterbi.decisions], dtype=np.int64
        ),
        "b0_decision_traceback_depth": np.asarray(
            [row.traceback_depth_used for row in separate_viterbi.decisions], dtype=np.int16
        ),
        "b0_decision_edge_id": np.asarray(
            [row.edge_id for row in separate_viterbi.decisions], dtype=np.int16
        ),
        "separate_decoded_bits": separate.decoded_information_bits,
        "separate_decoded_edges": separate.decoded_edge_ids,
        "sample_index": observation.absolute_sample_index,
        "sample_symbol_index": observation.sample_symbol_index,
        "path_contributions": channel.evaluation_truth.path_contributions,
        "noise_samples": channel.evaluation_truth.noise_samples,
        "channel_coefficients": channel.evaluation_truth.coefficients,
    }
    if b1 is not None and b1_viterbi is not None:
        traces.update(
            {
                "b1_hamming_metrics": b1.hamming_branch_metrics,
                "b1_hard_phase_indices": b1.hard_phase_indices,
                "b1_decoded_bits": b1.decoded_information_bits,
                "b1_decoded_edges": b1.decoded_edge_ids,
                "b1_survivor_edges": b1_viterbi.survivor_edge_ids,
                "b1_path_metrics": b1_viterbi.state_metrics[1:],
                "b1_decision_symbol_index": np.asarray(
                    [row.symbol_index for row in b1_viterbi.decisions], dtype=np.int64
                ),
                "b1_decision_available_at": np.asarray(
                    [row.decision_available_at for row in b1_viterbi.decisions], dtype=np.int64
                ),
                "b1_decision_traceback_depth": np.asarray(
                    [row.traceback_depth_used for row in b1_viterbi.decisions], dtype=np.int16
                ),
                "b1_decision_edge_id": np.asarray(
                    [row.edge_id for row in b1_viterbi.decisions], dtype=np.int16
                ),
            }
        )
    joint_trellis = build_augmented_trellis((0, 0), config.delays_samples)
    base_edges = [
        {
            "edge_id": int(edge_id),
            "source_state": list(source),
            "source_state_id": STATE_ORDER.index(source),
            "input_pair": list(pair),
            "coded_triple": list(coded),
            "target_state": list(target),
            "target_state_id": STATE_ORDER.index(target),
            "phase_index": int(4 * coded[0] + 2 * coded[1] + coded[2]),
        }
        for edge_id, source, pair, coded, target in transition_table()
    ]
    joint_nodes = [
        {
            "node_id": int(node.node_id),
            "encoder_state": list(node.encoder_state),
            "previous_phase_history": list(node.phase_history),
        }
        for node in joint_trellis.nodes
    ]
    joint_edges = [
        {
            "edge_id": int(edge.expanded_edge_id),
            "source_node_id": int(edge.source_node_id),
            "target_node_id": int(edge.target_node_id),
            "base_edge_id": int(edge.base_edge_id),
            "input_pair": list(edge.input_pair),
            "coded_triple": list(edge.coded_triple),
            "phase_index": int(edge.phase_index),
        }
        for edge in joint_trellis.edges
    ]
    with (root / "traces.npz.tmp").open("wb") as stream:
        np.savez_compressed(stream, **{k: np.asarray(v) for k, v in traces.items()})
    os.replace(root / "traces.npz.tmp", root / "traces.npz")
    truth_arrays = {
        "transmitter_information_bits": channel.evaluation_truth.transmitter_information_bits,
        "coefficients": channel.evaluation_truth.coefficients,
        "path_contributions": channel.evaluation_truth.path_contributions,
        "noise_samples": channel.evaluation_truth.noise_samples,
        "faded_signal": channel.evaluation_truth.faded_signal,
    }
    with (root / "evaluation_truth.npz.tmp").open("wb") as stream:
        np.savez_compressed(stream, **truth_arrays)
    os.replace(root / "evaluation_truth.npz.tmp", root / "evaluation_truth.npz")
    energy_metrics = calculate_single_run_energy_metrics(
        transmitter.tx_samples,
        information_bit_count=len(ref_bits),
        amplitude=config.amplitude,
        noise_variance=config.noise_variance,
    )
    summary: dict[str, Any] = {
        "schema_version": "repro09-run-result-v1",
        "metric_labels_version": "information-pair-and-phase-ser-v1",
        "run_id": run_id,
        "status": "completed",
        "frame_symbols": config.frame_symbols,
        "information_bit_count": int(len(ref_bits)),
        "sample_count": int(len(observation.received_samples)),
        "energy": energy_metrics,
        "receiver_observation_sha256": observation.sha256,
        "transmitter_fingerprint": transmitter.source_fingerprint,
        "mapping_id": transmitter.mapping_id,
        "mapping_fingerprint": transmitter.mapping_fingerprint,
        "paper_exact": False,
        "article_energy_gain_claim_db": 1.5,
        "energy_gain_status": "ENERGY_GAIN_NOT_ESTIMABLE_FROM_SINGLE_FRAME",
        "channel": {
            "profile_id": observation.profile_id,
            "config": channel.config_snapshot,
            "sample_count": int(len(observation.received_samples)),
            "truth_is_receiver_input": False,
        },
        "joint": {
            "profile_id": joint.receiver_profile_id,
            "observation_sha256": joint.observation_sha256,
            "decoder_mode": joint.decoder_mode,
            "traceback_depth": joint.traceback_depth,
            "compared_bits": int(len(ref_bits)),
            "bit_errors": int(np.count_nonzero(joint_bit_mask)),
            "ber": float(np.mean(joint_bit_mask)),
            "compared_information_pairs": joint_pair_eval.compared_pairs,
            "information_pair_errors": joint_pair_eval.pair_errors,
            "information_pair_ser": joint_pair_eval.pair_ser,
            "information_pair_error_positions": joint_pair_eval.pair_error_positions.tolist(),
            "compared_phase_symbols": int(len(ref_phases)),
            "phase_symbol_errors": int(np.count_nonzero(joint_symbol_mask)),
            "phase_symbol_ser": float(np.mean(joint_symbol_mask)),
            "phase_symbol_error_positions": np.flatnonzero(joint_symbol_mask).tolist(),
            "symbol_metric_semantics": "decoded_encoder_edge_phase",
            "compared_symbols": int(len(ref_phases)),
            "symbol_errors": int(np.count_nonzero(joint_symbol_mask)),
            "ser": float(np.mean(joint_symbol_mask)),
            "bit_error_positions": np.flatnonzero(joint_bit_mask).tolist(),
            "symbol_error_positions": np.flatnonzero(joint_symbol_mask).tolist(),
            "runtime_seconds": float(joint_seconds),
            "runtime_scope": "complete_receiver_call",
            "trellis_state_count": joint.trellis_state_count,
            "trellis_edge_count": joint.trellis_edge_count,
        },
        "separate": {
            "profile_id": "repro04_original_separate_hamming_b0",
            "observation_sha256": separate.observation_sha256,
            "decoder_mode": separate.traceback_mode,
            "traceback_depth": separate.decoder_depth,
            "compared_bits": sep_eval.compared_information_bit_count,
            "bit_errors": sep_eval.bit_errors,
            "ber": sep_eval.ber,
            "compared_information_pairs": sep_pair_eval.compared_pairs,
            "information_pair_errors": sep_pair_eval.pair_errors,
            "information_pair_ser": sep_pair_eval.pair_ser,
            "information_pair_error_positions": sep_pair_eval.pair_error_positions.tolist(),
            "compared_phase_symbols": sep_eval.compared_symbol_count,
            "phase_symbol_errors": sep_eval.symbol_errors,
            "phase_symbol_ser": sep_eval.ser,
            "phase_symbol_error_positions": sep_eval.symbol_error_positions.tolist(),
            "symbol_metric_semantics": "hard_demodulated_8psk_phase_symbol",
            "compared_symbols": sep_eval.compared_symbol_count,
            "symbol_errors": sep_eval.symbol_errors,
            "ser": sep_eval.ser,
            "bit_error_positions": sep_eval.bit_error_positions.tolist(),
            "symbol_error_positions": sep_eval.symbol_error_positions.tolist(),
            "runtime_seconds": float(separate_seconds),
            "runtime_scope": "complete_receiver_call",
        },
        "b1": b1_evaluation,
        "trellises": {
            "encoder_a": {"state_count": 4, "edges": base_edges},
            "joint": {
                "state_count": joint.trellis_state_count,
                "edge_count": joint.trellis_edge_count,
                "channel_memory_symbols": joint_trellis.memory_symbols,
                "delays_samples": list(config.delays_samples),
                "nodes": joint_nodes,
                "edges": joint_edges,
            },
        },
        "paired_observation_verified": joint.observation_sha256
        == separate.observation_sha256
        == observation.sha256
        and (b1 is None or b1.observation_sha256 == observation.sha256),
        "receiver_inputs_excluded_evaluation_truth": True,
        "elapsed_seconds": float(ended - started),
        "configuration": config_dict,
        "receiver_configurations": {
            "joint": joint_config.to_dict(),
            "separate": separate_config.to_dict(),
            "b1": b1.receiver_config if b1 is not None else None,
        },
        "source_status": "v7_article primary per references inventory; exact source semantics remain partial",
        "noise_convention": "complex sample-domain variance per REPRO-03; not physical Eb/N0",
    }
    _atomic_json(root / "configuration.json", config_dict)
    _atomic_json(root / "summary.json", summary)
    files = {
        name: _sha((root / name).read_bytes())
        for name in ("configuration.json", "summary.json", "traces.npz", "evaluation_truth.npz")
    }
    manifest = {
        "schema_version": "repro09-manifest-v1",
        "run_id": run_id,
        "configuration_sha256": _sha(config_bytes),
        "receiver_observation_sha256": observation.sha256,
        "files": files,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
    }
    _atomic_json(root / "manifest.json", manifest)
    return summary


def load_run_summary(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        candidate = (root / name).resolve()
        if root not in candidate.parents or _sha(candidate.read_bytes()) != expected:
            raise ValueError(f"run artifact hash mismatch: {name}")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    if summary.get("metric_labels_version") != "information-pair-and-phase-ser-v1":
        summary = _add_information_pair_metrics_from_saved_bits(root, summary)
    return summary


def _add_information_pair_metrics_from_saved_bits(
    root: Path, summary: dict[str, Any]
) -> dict[str, Any]:
    """Enrich old summaries in memory without rewriting their hashed source files."""
    try:
        with np.load(root / "traces.npz", allow_pickle=False) as arrays:
            reference = arrays["information_bits"]
            decoded = {
                "joint": arrays["joint_decoded_bits"],
                "separate": arrays["separate_decoded_bits"],
            }
            if "b1_decoded_bits" in arrays.files:
                decoded["b1"] = arrays["b1_decoded_bits"]
            for name, bits in decoded.items():
                payload = np.asarray(bits[: reference.size], dtype=np.int8)
                if payload.shape != reference.shape:
                    continue
                metrics = evaluate_information_pair_errors(reference, payload)
                arm = summary.get(name)
                if not isinstance(arm, dict):
                    continue
                arm.update(
                    compared_information_pairs=metrics.compared_pairs,
                    information_pair_errors=metrics.pair_errors,
                    information_pair_ser=metrics.pair_ser,
                    information_pair_error_positions=metrics.pair_error_positions.tolist(),
                    phase_symbol_errors=arm.get("symbol_errors"),
                    phase_symbol_ser=arm.get("ser"),
                    phase_symbol_error_positions=arm.get("symbol_error_positions", []),
                    compared_phase_symbols=arm.get("compared_symbols"),
                    symbol_metric_semantics=(
                        "hard_demodulated_8psk_phase_symbol"
                        if name == "separate"
                        else "decoded_encoder_edge_phase"
                    ),
                )
    except (OSError, KeyError, ValueError):
        # Old archives may not contain decoder bit arrays. Keep their measured fields
        # intact and let the UI report pair statistics as unavailable.
        pass
    summary["metric_labels_version"] = "information-pair-and-phase-ser-v1"
    summary["pair_metrics_recomputed_from_saved_bits"] = True
    return summary


def trace_window(
    run_dir: str | Path, *, start_symbol: int, symbol_count: int = 20
) -> dict[str, Any]:
    """Return a bounded plot window; persisted arrays remain full precision."""
    if type(start_symbol) is not int or start_symbol < 0:
        raise ValueError("start_symbol must be a non-negative integer")
    if type(symbol_count) is not int or not 1 <= symbol_count <= 256:
        raise ValueError("symbol_count must be in [1,256]")
    root = Path(run_dir).resolve()
    summary = load_run_summary(root)
    stop_symbol = min(summary["frame_symbols"], start_symbol + symbol_count)
    if start_symbol >= stop_symbol:
        raise ValueError("start_symbol is outside the saved frame")
    sample_start, sample_stop = start_symbol * 8, stop_symbol * 8
    with np.load(root / "traces.npz", allow_pickle=False) as data:
        sample_stop = min(sample_stop, len(data["received_samples"]))
        if stop_symbol == summary["frame_symbols"]:
            sample_stop = len(data["received_samples"])
        result: dict[str, Any] = {
            "run_id": summary["run_id"],
            "start_symbol": start_symbol,
            "stop_symbol": stop_symbol,
            "sample_start": sample_start,
            "sample_stop": sample_stop,
            "absolute_sample_indices": data["sample_index"][sample_start:sample_stop].tolist(),
            "received_i": data["received_samples"][sample_start:sample_stop].real.tolist(),
            "received_q": data["received_samples"][sample_start:sample_stop].imag.tolist(),
            "tx_i": data["tx_samples"][
                sample_start : min(sample_stop, len(data["tx_samples"]))
            ].real.tolist(),
            "tx_q": data["tx_samples"][
                sample_start : min(sample_stop, len(data["tx_samples"]))
            ].imag.tolist(),
            "information_bits": data["information_bits"][
                start_symbol * 2 : stop_symbol * 2
            ].tolist(),
            "input_pairs": data["input_pairs"][start_symbol:stop_symbol].tolist(),
            "coded_triples": data["coded_triples"][start_symbol:stop_symbol].tolist(),
            "phase_indices": data["phase_indices"][start_symbol:stop_symbol].tolist(),
            "pre_states": data["pre_states"][start_symbol:stop_symbol].tolist(),
            "post_states": data["post_states"][start_symbol:stop_symbol].tolist(),
            "hard_phase_indices": data["hard_phase_indices"][start_symbol:stop_symbol].tolist(),
            "joint_metrics": data["joint_metrics"][start_symbol:stop_symbol].tolist(),
            "hamming_metrics": data["hamming_metrics"][start_symbol:stop_symbol].tolist(),
            "path_contributions_i": data["path_contributions"][
                :, sample_start:sample_stop
            ].real.tolist(),
            "path_contributions_q": data["path_contributions"][
                :, sample_start:sample_stop
            ].imag.tolist(),
            "noise_i": data["noise_samples"][sample_start:sample_stop].real.tolist(),
            "noise_q": data["noise_samples"][sample_start:sample_stop].imag.tolist(),
            "edge_ids": data["edge_ids"][start_symbol:stop_symbol].tolist(),
            "joint_decoded_edges": data["joint_decoded_edges"][start_symbol:stop_symbol].tolist(),
            "separate_decoded_edges": data["separate_decoded_edges"][
                start_symbol:stop_symbol
            ].tolist(),
            "joint_diagnostics_available": "joint_survivor_edges" in data.files,
            "b0_diagnostics_available": "b0_survivor_edges" in data.files,
            "b1_diagnostics_available": "b1_survivor_edges" in data.files,
        }
        trace_keys = {
            "joint_metrics": "joint_metrics",
            "joint_survivor_edges": "joint_survivor_edges",
            "joint_path_metrics": "joint_path_metrics",
            "b0_metrics": "hamming_metrics",
            "b0_survivor_edges": "b0_survivor_edges",
            "b0_path_metrics": "b0_path_metrics",
            "b1_metrics": "b1_hamming_metrics",
            "b1_survivor_edges": "b1_survivor_edges",
            "b1_path_metrics": "b1_path_metrics",
        }
        for output_key, archive_key in trace_keys.items():
            key = archive_key
            if key not in data.files:
                continue
            array = data[key]
            if array.ndim and array.shape[0] >= stop_symbol:
                result[output_key] = array[start_symbol:stop_symbol].tolist()
        for prefix in ("joint", "b0", "b1"):
            for suffix in (
                "decision_symbol_index",
                "decision_available_at",
                "decision_traceback_depth",
                "decision_expanded_edge_id",
                "decision_edge_id",
            ):
                key = f"{prefix}_{suffix}"
                if key in data.files:
                    result[key] = data[key].tolist()
    return result


def trace_sample_window(
    run_dir: str | Path, *, sample_start: int, sample_count: int = 20
) -> dict[str, Any]:
    """Return an exact bounded sample window, including channel tail indices."""
    if type(sample_start) is not int or sample_start < 0:
        raise ValueError("sample_start must be a non-negative integer")
    if type(sample_count) is not int or not 1 <= sample_count <= 160:
        raise ValueError("sample_count must be in [1,160]")
    root = Path(run_dir).resolve()
    summary = load_run_summary(root)
    with np.load(root / "traces.npz", allow_pickle=False) as data:
        stop = min(sample_start + sample_count, len(data["received_samples"]))
        if sample_start >= stop:
            raise ValueError("sample_start is outside the saved received frame")
        rx = data["received_samples"][sample_start:stop]
        tx = data["tx_samples"][sample_start : min(stop, len(data["tx_samples"]))]
        return {
            "run_id": summary["run_id"],
            "sample_start": sample_start,
            "sample_stop": stop,
            "absolute_sample_indices": data["sample_index"][sample_start:stop].tolist(),
            "symbol_indices": data["sample_symbol_index"][sample_start:stop].tolist(),
            "local_sample_indices": (data["sample_index"][sample_start:stop] % 8).tolist(),
            "tx_i": tx.real.tolist(),
            "tx_q": tx.imag.tolist(),
            "received_i": rx.real.tolist(),
            "received_q": rx.imag.tolist(),
            "noise_i": data["noise_samples"][sample_start:stop].real.tolist(),
            "noise_q": data["noise_samples"][sample_start:stop].imag.tolist(),
            "path_contributions_i": data["path_contributions"][:, sample_start:stop].real.tolist(),
            "path_contributions_q": data["path_contributions"][:, sample_start:stop].imag.tolist(),
            "tail_sample": [
                index >= summary["frame_symbols"] * 8 for index in range(sample_start, stop)
            ],
        }


def viterbi_window(
    run_dir: str | Path,
    *,
    receiver: str,
    symbol_index: int,
    traceback_depth: int = 20,
    survivor_state: int | None = None,
) -> dict[str, Any]:
    """Expose actual decoder rows, emitted decisions, and a local survivor traceback."""
    if receiver not in {"joint", "b0", "b1"}:
        raise ValueError("receiver must be joint, b0, or b1")
    if type(symbol_index) is not int or symbol_index < 0:
        raise ValueError("symbol_index must be a non-negative integer")
    if type(traceback_depth) is not int or traceback_depth < 1:
        raise ValueError("traceback_depth must be positive")
    root = Path(run_dir).resolve()
    summary = load_run_summary(root)
    frame = int(summary["frame_symbols"])
    if symbol_index >= frame:
        raise ValueError("symbol_index is outside the information frame")
    start = max(0, symbol_index - traceback_depth + 1)
    with np.load(root / "traces.npz", allow_pickle=False) as data:
        survivor_key = f"{receiver}_survivor_edges"
        path_metric_key = f"{receiver}_path_metrics"
        metric_key = (
            "joint_metrics"
            if receiver == "joint"
            else "hamming_metrics"
            if receiver == "b0"
            else "b1_hamming_metrics"
        )
        required = {survivor_key, path_metric_key, metric_key}
        if not required.issubset(data.files):
            return {
                "available": False,
                "reason": "saved result predates decoder diagnostics",
                "run_id": summary["run_id"],
                "receiver": receiver,
                "symbol_index": symbol_index,
                "traceback_depth": traceback_depth,
            }
        survivor = data[survivor_key][start : symbol_index + 1]
        state_metrics = data[path_metric_key][start : symbol_index + 1]
        metric_window = data[metric_key][start : symbol_index + 1]
        if survivor_state is not None and (
            type(survivor_state) is not int or not 0 <= survivor_state < state_metrics.shape[1]
        ):
            raise ValueError("survivor_state is outside the trellis state range")
        metric_rows = data[metric_key][symbol_index]
        graph = (
            summary["trellises"]["joint"]["edges"]
            if receiver == "joint"
            else summary["trellises"]["encoder_a"]["edges"]
        )
        by_id = {int(edge["edge_id"]): edge for edge in graph}
        endpoint = int(np.argmin(state_metrics[-1])) if survivor_state is None else survivor_state
        local_path = []
        node = endpoint
        for offset in range(len(survivor) - 1, -1, -1):
            edge_id = int(survivor[offset, node])
            edge = by_id.get(edge_id)
            if edge is None:
                break
            local_path.append({**edge, "symbol_index": start + offset})
            node = int(edge["source_node_id"] if receiver == "joint" else edge["source_state_id"])
        local_path.reverse()

        arrival_decision = None
        selected_symbol_decision = None
        decision_index_key = f"{receiver}_decision_symbol_index"
        available_key = f"{receiver}_decision_available_at"
        depth_key = f"{receiver}_decision_traceback_depth"
        decision_edge_key = (
            "joint_decision_expanded_edge_id"
            if receiver == "joint"
            else f"{receiver}_decision_edge_id"
        )
        if {decision_index_key, available_key, depth_key, decision_edge_key}.issubset(data.files):
            for pos, (source_index, available_at) in enumerate(
                zip(data[decision_index_key], data[available_key], strict=True)
            ):
                record = {
                    "symbol_index": int(source_index),
                    "decision_available_at": int(available_at),
                    "traceback_depth_used": int(data[depth_key][pos]),
                    "edge_id": int(data[decision_edge_key][pos]),
                }
                if available_at == symbol_index:
                    arrival_decision = record
                if source_index == symbol_index:
                    selected_symbol_decision = record

        decoded_edges_key = (
            "joint_decoded_edges"
            if receiver == "joint"
            else "separate_decoded_edges"
            if receiver == "b0"
            else "b1_decoded_edges"
        )
        reconstructed_edge = (
            int(data[decoded_edges_key][symbol_index]) if decoded_edges_key in data.files else None
        )
        per_edge = []
        for edge in graph:
            edge_id = int(edge["edge_id"])
            per_edge.append({**edge, "branch_metric": float(metric_rows[edge_id])})
        traceback_steps = []
        for offset, symbol in enumerate(range(start, symbol_index + 1)):
            traceback_steps.append(
                {
                    "symbol_index": symbol,
                    "branch_metrics": metric_window[offset].tolist(),
                    "state_metrics": state_metrics[offset].tolist(),
                    "survivor_edge_ids_by_destination": survivor[offset].tolist(),
                }
            )
        return {
            "available": True,
            "run_id": summary["run_id"],
            "receiver": receiver,
            "symbol_index": symbol_index,
            "sample_start": 8 * symbol_index,
            "sample_stop": min(
                8 * (symbol_index + 1)
                + max(
                    summary["channel"]["config"]["paths"][i]["delay_samples"]
                    for i in range(len(summary["channel"]["config"]["paths"]))
                ),
                summary["sample_count"],
            ),
            "window_start_symbol": start,
            "window_stop_symbol": symbol_index + 1,
            "traceback_depth_requested": traceback_depth,
            "traceback_window_transitions": symbol_index - start + 1,
            "endpoint_state_id": endpoint,
            "endpoint_metric": float(state_metrics[-1, endpoint]),
            "traceback_local_survivor_path": local_path,
            "traceback_steps": traceback_steps,
            "emitted_decision_on_this_arrival": arrival_decision,
            "emitted_decision_for_selected_symbol": selected_symbol_decision,
            "reconstructed_edge_from_emitted_bits": reconstructed_edge,
            "transitions": per_edge,
            "state_metrics": state_metrics[-1].tolist(),
        }


def load_long_frame_archive() -> dict[str, Any]:
    """Verify and describe preserved long-frame artifacts without joining unlike runs."""
    root08 = Path("outputs/repro08/phase_c_long_frame_bounded_v1").resolve()
    manifest08 = json.loads((root08 / "manifest.json").read_text(encoding="utf-8"))
    actual08 = {name: _sha((root08 / name).read_bytes()) for name in manifest08["files"]}
    if actual08 != manifest08["files"]:
        raise ValueError("REPRO-08 long-frame manifest integrity failure")
    trial = json.loads((root08 / "trial.json").read_text(encoding="utf-8"))
    config = json.loads((root08 / "config.json").read_text(encoding="utf-8"))
    frame = int(config["frame_symbols"])
    if frame != 20_000 or int(trial["compared_bits"]) != 40_000:
        raise ValueError("REPRO-08 long-frame result has an unexpected frame contract")

    root06 = Path("outputs/repro06c/reference_20000").resolve()
    verify_adaptive_result(root06)
    summary06 = json.loads((root06 / "summary.json").read_text(encoding="utf-8"))
    if int(summary06["receiver_config"]["expected_symbol_count"]) != frame:
        raise ValueError("REPRO-06C reference trace has an unexpected frame length")
    return {
        "status": "verified",
        "repro08_metrics": {
            "experiment_id": trial["experiment_id"],
            "frame_symbols": frame,
            "compared_bits": int(trial["compared_bits"]),
            "joint": {
                "bit_errors": int(trial["joint_bit_errors"]),
                "ber": int(trial["joint_bit_errors"]) / int(trial["compared_bits"]),
                "pair_symbol_errors": int(trial["joint_pair_symbol_errors"]),
                "ser": int(trial["joint_pair_symbol_errors"]) / int(trial["compared_symbols"]),
                "runtime_seconds": float(trial["joint_seconds"]),
                "error_positions": trial["joint_bit_error_positions"],
            },
            "separate": {
                "bit_errors": int(trial["separate_bit_errors"]),
                "ber": int(trial["separate_bit_errors"]) / int(trial["compared_bits_separate"]),
                "pair_symbol_errors": int(trial["separate_pair_symbol_errors"]),
                "ser": int(trial["separate_pair_symbol_errors"]) / int(trial["compared_symbols"]),
                "runtime_seconds": float(trial["separate_seconds"]),
                "error_positions": trial["separate_bit_error_positions"],
            },
            "observation_sha256": trial["observation_sha256"],
            "noise_variance_complex_per_sample": float(trial["noise_variance_complex_per_sample"]),
            "channel_profile": trial["channel_profile"],
            "manifest_sha256": _sha((root08 / "manifest.json").read_bytes()),
            "source": "outputs/repro08/phase_c_long_frame_bounded_v1",
        },
        "repro06c_trace": {
            "frame_symbols": frame,
            "trellis_state_count": int(summary06["trellis_state_count"]),
            "trellis_edge_count": int(summary06["trellis_edge_count"]),
            "observation_sha256": summary06["observation_sha256"],
            "manifest_sha256": _sha((root06 / "manifest.json").read_bytes()),
            "source": "outputs/repro06c/reference_20000",
            "signal_samples_available": False,
            "evaluation_truth_available": False,
        },
        "same_observation": trial["observation_sha256"] == summary06["observation_sha256"],
        "joined_comparison_allowed": trial["observation_sha256"] == summary06["observation_sha256"],
    }


def long_frame_viterbi_window(
    *, symbol_index: int, traceback_depth: int = 20, survivor_state: int | None = None
) -> dict[str, Any]:
    """Load only the requested REPRO-06C decoder window from its verified archive."""
    archive = load_long_frame_archive()
    frame = archive["repro06c_trace"]["frame_symbols"]
    if type(symbol_index) is not int or not 0 <= symbol_index < frame:
        raise ValueError("symbol_index is outside the archived long frame")
    if type(traceback_depth) is not int or traceback_depth < 1:
        raise ValueError("traceback_depth must be positive")
    root = Path("outputs/repro06c/reference_20000").resolve()
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    config = summary["receiver_config"]
    trellis = build_augmented_trellis(
        tuple(config["initial_state"]),
        tuple(path["delay_samples"] for path in config["paths"]),
    )
    edges = [
        {
            "edge_id": int(edge.expanded_edge_id),
            "source_node_id": int(edge.source_node_id),
            "target_node_id": int(edge.target_node_id),
            "base_edge_id": int(edge.base_edge_id),
            "input_pair": list(edge.input_pair),
            "coded_triple": list(edge.coded_triple),
            "phase_index": int(edge.phase_index),
        }
        for edge in trellis.edges
    ]
    nodes = [
        {
            "node_id": int(node.node_id),
            "encoder_state": list(node.encoder_state),
            "previous_phase_history": list(node.phase_history),
        }
        for node in trellis.nodes
    ]
    start = max(0, symbol_index - traceback_depth + 1)
    with np.load(root / "adaptive_receiver.npz", allow_pickle=False) as data:
        survivor = data["survivor_edges_by_symbol_node"][start : symbol_index + 1]
        path_metrics = data["survivor_path_metrics"][start : symbol_index + 1]
        metric_rows = data["branch_metric_rows"][start : symbol_index + 1]
        if survivor_state is not None and (
            type(survivor_state) is not int or not 0 <= survivor_state < path_metrics.shape[1]
        ):
            raise ValueError("survivor_state is outside the trellis state range")
        endpoint = int(np.argmin(path_metrics[-1])) if survivor_state is None else survivor_state
        by_id = {edge["edge_id"]: edge for edge in edges}
        local_path = []
        node = endpoint
        for offset in range(len(survivor) - 1, -1, -1):
            edge = by_id[int(survivor[offset, node])]
            local_path.append({**edge, "symbol_index": start + offset})
            node = int(edge["source_node_id"])
        local_path.reverse()
        steps = [
            {
                "symbol_index": start + offset,
                "branch_metrics": metric_rows[offset].tolist(),
                "state_metrics": path_metrics[offset].tolist(),
                "survivor_edge_ids_by_destination": survivor[offset].tolist(),
            }
            for offset in range(len(survivor))
        ]
        decision_index = data["decision_symbol_index"]
        decision_at = data["decision_available_at"]
        decision_depth = data["decision_traceback_depth"]
        decision_edge = data["decision_expanded_edge_id"]
        emitted = next(
            (
                {
                    "symbol_index": int(decision_index[i]),
                    "decision_available_at": int(decision_at[i]),
                    "traceback_depth_used": int(decision_depth[i]),
                    "edge_id": int(decision_edge[i]),
                }
                for i in range(len(decision_index))
                if int(decision_index[i]) == symbol_index
            ),
            None,
        )
        arrival = next(
            (
                {
                    "symbol_index": int(decision_index[i]),
                    "decision_available_at": int(decision_at[i]),
                    "traceback_depth_used": int(decision_depth[i]),
                    "edge_id": int(decision_edge[i]),
                }
                for i in range(len(decision_index))
                if int(decision_at[i]) == symbol_index
            ),
            None,
        )
        decoded_edge = int(data["decoded_edge_ids"][symbol_index])
        row = data["branch_metric_rows"][symbol_index]
        per_edge = [{**edge, "branch_metric": float(row[edge["edge_id"]])} for edge in edges]
    return {
        "available": True,
        "run_id": "repro06c-reference-20000",
        "receiver": "joint",
        "symbol_index": symbol_index,
        "sample_start": 8 * symbol_index,
        "sample_stop": min(8 * (symbol_index + 1) + 3, frame * 8 + 3),
        "signal_samples_available": False,
        "window_start_symbol": start,
        "window_stop_symbol": symbol_index + 1,
        "traceback_depth_requested": traceback_depth,
        "traceback_window_transitions": symbol_index - start + 1,
        "endpoint_state_id": endpoint,
        "endpoint_metric": float(path_metrics[-1, endpoint]),
        "traceback_local_survivor_path": local_path,
        "traceback_steps": steps,
        "emitted_decision_on_this_arrival": arrival,
        "emitted_decision_for_selected_symbol": emitted,
        "reconstructed_edge_from_emitted_bits": decoded_edge,
        "trellis_nodes": nodes,
        "trellis_edges": edges,
        "transitions": per_edge,
        "state_metrics": path_metrics[-1].tolist(),
    }


class ScientificJobManager:
    """Single worker prevents accidental concurrent long adaptive receiver runs."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="repro09")
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, Future[dict[str, Any]]] = {}
        self._stop_events: dict[str, threading.Event] = {}

    def submit(self, config: ScientificRunConfig) -> str:
        with self._lock:
            if any(job["status"] in {"queued", "running"} for job in self._jobs.values()):
                raise RuntimeError("a scientific run is already active")
            job_id = uuid.uuid4().hex
            self._jobs[job_id] = {"job_id": job_id, "status": "queued", "progress": 0.0}
            self._futures[job_id] = self._executor.submit(self._execute, job_id, config)
            return job_id

    def submit_experiment(self, config: ExperimentConfig) -> str:
        with self._lock:
            if any(job["status"] in {"queued", "running"} for job in self._jobs.values()):
                raise RuntimeError("a scientific run is already active")
            job_id = uuid.uuid4().hex
            stop_event = threading.Event()
            self._stop_events[job_id] = stop_event
            self._jobs[job_id] = {"job_id": job_id, "status": "queued", "progress": 0.0}
            self._futures[job_id] = self._executor.submit(
                self._execute_experiment, job_id, config, stop_event
            )
            return job_id

    def submit_energy_study(self, config: EnergyStudyConfig, output_root: str | Path) -> str:
        with self._lock:
            if any(job["status"] in {"queued", "running"} for job in self._jobs.values()):
                raise RuntimeError("a scientific computation is already active")
            job_id = uuid.uuid4().hex
            stop_event = threading.Event()
            self._stop_events[job_id] = stop_event
            planned = len(config.gamma_grid_db) * config.trials_per_point
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "progress": 0.0,
                "planned_trials": planned,
                "completed_trials": 0,
                "energy_study": True,
            }
            self._futures[job_id] = self._executor.submit(
                self._execute_energy_study, job_id, config, Path(output_root), stop_event
            )
            return job_id

    def submit_metric_study(self, config: MetricStudyConfig, output_root: str | Path) -> str:
        with self._lock:
            if any(job["status"] in {"queued", "running"} for job in self._jobs.values()):
                raise RuntimeError("a scientific computation is already active")
            job_id = uuid.uuid4().hex
            stop_event = threading.Event()
            self._stop_events[job_id] = stop_event
            planned = len(config.energy_grid_db) * config.trials_per_point
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "progress": 0.0,
                "planned_trials": planned,
                "completed_trials": 0,
                "metric_study": True,
            }
            self._futures[job_id] = self._executor.submit(
                self._execute_metric_study, job_id, config, Path(output_root), stop_event
            )
            return job_id

    def _execute_metric_study(
        self,
        job_id: str,
        config: MetricStudyConfig,
        output_root: Path,
        stop_event: threading.Event,
    ) -> dict[str, Any]:
        with self._lock:
            self._jobs[job_id]["status"] = "running"

        def progress(update: dict[str, Any]) -> None:
            with self._lock:
                job = self._jobs[job_id]
                job.update(update)
                job["progress"] = min(
                    1.0,
                    int(update.get("completed_trials", 0))
                    / max(1, int(update.get("planned_trials", 1))),
                )

        try:
            result = run_metric_study(
                config, output_root, stop_event=stop_event, progress_callback=progress
            )
            with self._lock:
                self._jobs[job_id].update(
                    status=result["status"],
                    progress=float(result["completed_trials"] / max(1, result["planned_trials"])),
                    experiment_id=result["experiment_id"],
                    result=result,
                )
            return result
        except Exception as exc:
            with self._lock:
                self._jobs[job_id].update(status="failed", error=f"{type(exc).__name__}: {exc}")
            raise

    def _execute_energy_study(
        self,
        job_id: str,
        config: EnergyStudyConfig,
        output_root: Path,
        stop_event: threading.Event,
    ) -> dict[str, Any]:
        with self._lock:
            self._jobs[job_id]["status"] = "running"

        def progress(update: dict[str, Any]) -> None:
            with self._lock:
                job = self._jobs[job_id]
                job.update(update)
                job["progress"] = min(
                    1.0,
                    int(update.get("completed_trials", 0))
                    / max(1, int(update.get("planned_trials", 1))),
                )

        try:
            result = run_energy_study(
                config, output_root, stop_event=stop_event, progress_callback=progress
            )
            with self._lock:
                self._jobs[job_id].update(
                    status=result["status"],
                    progress=float(result["completed_trials"] / max(1, result["planned_trials"])),
                    experiment_id=result["experiment_id"],
                    result=result,
                )
            return result
        except Exception as exc:
            with self._lock:
                self._jobs[job_id].update(status="failed", error=f"{type(exc).__name__}: {exc}")
            raise

    def _execute_experiment(
        self, job_id: str, config: ExperimentConfig, stop_event: threading.Event
    ) -> dict[str, Any]:
        with self._lock:
            self._jobs[job_id]["status"] = "running"

        def progress(update: dict[str, Any]) -> None:
            with self._lock:
                job = self._jobs[job_id]
                job.update(update)
                total = max(1, int(update.get("planned_trials", 1)))
                job["progress"] = min(1.0, int(update.get("completed_trials", 0)) / total)

        try:
            result = run_paired_experiment(
                config,
                resume=True,
                progress=False,
                stop_event=stop_event,
                progress_callback=progress,
            )
            with self._lock:
                self._jobs[job_id].update(
                    status="completed" if result["status"] == "completed" else "incomplete",
                    progress=float(result["completed_trials"] / max(1, result["planned_trials"])),
                    experiment_id=result["experiment_id"],
                    result=result,
                )
            return result
        except Exception as exc:
            with self._lock:
                self._jobs[job_id].update(status="failed", error=f"{type(exc).__name__}: {exc}")
            raise

    def _execute(self, job_id: str, config: ScientificRunConfig) -> dict[str, Any]:
        with self._lock:
            self._jobs[job_id]["status"] = "running"
        try:
            result = run_scientific_run(config)
            with self._lock:
                self._jobs[job_id].update(
                    status="completed", progress=1.0, run_id=result["run_id"], result=result
                )
            return result
        except Exception as exc:
            with self._lock:
                self._jobs[job_id].update(status="failed", error=f"{type(exc).__name__}: {exc}")
            raise

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._jobs[job_id]) if job_id in self._jobs else None

    def stop(self, job_id: str) -> bool:
        with self._lock:
            event = self._stop_events.get(job_id)
            if event is None or self._jobs.get(job_id, {}).get("status") != "running":
                return False
            event.set()
            self._jobs[job_id]["stop_requested"] = True
            return True


JOBS = ScientificJobManager()
