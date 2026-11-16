"""Authorized M10b paired evaluation for the ADR-016 gain schedules.

The runner is evaluation-only. Gain truth stays in this module and its
checkpoints; receiver calls receive only the profile-specific received vector
and the already frozen receiver policy.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.coding.encoder import INITIAL_STATE
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.evaluation.controlled_piecewise_real_gain import (
    apply_symbol_gain_schedule,
    build_gain_schedule,
)
from hf_tcm.evaluation.error_metrics import (
    ErrorCounts,
    count_bit_errors,
    count_symbol_errors,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
)
from hf_tcm.evaluation.m7b_train_runner import (
    _atomic_json,
    _historical_tree_hash,
    _sha256_file,
)
from hf_tcm.evaluation.m8b_train_runner import _process_rss_windows
from hf_tcm.evaluation.m9b_fixed_policy_evaluation_runner import (
    _receiver_configuration,
    _receiver_kwargs,
    resolve_m9_clock_origins,
)
from hf_tcm.evaluation.m10a_variable_gain_study_design import (
    DRAFT_PATH,
    EXPECTED_SEED_ROOTS,
    PARTITION_CODE,
    PROTOCOL_WORD,
    STUDY_ID,
    validate_m10a_variable_gain_study,
)
from hf_tcm.evaluation.matched_m2_b5_experiment import generate_independent_complex_awgn
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import symbols_to_iq_waveform
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
)

ROOT = Path(__file__).resolve().parents[3]
ACCEPTED_DECISION_PATH = ROOT / "configs/adr_016_controlled_piecewise_real_gain.json"
DECISION_DOC_PATH = ROOT / "docs/M10_PROPOSED_SCIENTIFIC_DECISION.md"
APPROVED_PATH = ROOT / "configs/m10b_variable_gain_approved_run.json"
OUTPUT_PATH = ROOT / "outputs/m10b_variable_gain/m10_controlled_piecewise_gain_v1"
SCHEMA = "m10b.variable-gain-evaluation.v1"
EXPECTED_DRAFT_SHA256 = "80ec2ea30e04bfeb02508380b94f29bb08140a1906fa61816d137ed56798066f"
EXPECTED_DECISION_SHA256 = "1dee34b2f608c2abea03c332135cbc67a5726326378b06ba2a7bc117763dd178"
EXPECTED_DECISION_JSON_SHA256 = "63f36a948c8147f76872e4d00e953e7eba50fff9338dcb6a141e4c82a65b9bb4"
EXPECTED_APPROVED_SCOPE = "m10b_variable_gain_only"
WALL_CLOCK_BUDGET_SECONDS = 900
RSS_MONITORING_BUDGET_BYTES = 1_610_612_736
BOOTSTRAP_REPLICATES = 2000
CONFIDENCE_LEVEL = 0.95
POLICY_IDS = ("historical_frozen_B", "anch_a085_k025")
PROFILE_LABELS = ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH")
NOISE_VARIANCE = 0.7115124735378853
SOURCE_PATHS = (
    "configs/m10a_variable_gain_study_draft.json",
    "configs/adr_016_controlled_piecewise_real_gain.json",
    "docs/M10_PROPOSED_SCIENTIFIC_DECISION.md",
    "src/hf_tcm/evaluation/m10a_variable_gain_study_design.py",
    "src/hf_tcm/evaluation/controlled_piecewise_real_gain.py",
    "src/hf_tcm/evaluation/m10b_variable_gain_runner.py",
    "src/hf_tcm/evaluation/m9b_fixed_policy_evaluation_runner.py",
    "src/hf_tcm/evaluation/m8b_train_runner.py",
    "src/hf_tcm/evaluation/m7b_train_runner.py",
    "src/hf_tcm/evaluation/matched_m2_b5_experiment.py",
    "src/hf_tcm/evaluation/error_metrics.py",
    "src/hf_tcm/evaluation/paired_cluster_bootstrap.py",
    "src/hf_tcm/receiver/reconstruction_posterior_estimator_sequence.py",
    "src/hf_tcm/receiver/reconstruction_posterior_estimator_step.py",
    "src/hf_tcm/receiver/reconstruction_candidate_metrics.py",
    "src/hf_tcm/receiver/reconstruction_posterior.py",
    "src/hf_tcm/receiver/reconstruction_conditional_decode.py",
    "src/hf_tcm/receiver/reconstruction_forward.py",
    "src/hf_tcm/receiver/reconstruction_observation.py",
    "src/hf_tcm/receiver/iq_prediction.py",
    "src/hf_tcm/receiver/paper_recursion.py",
    "src/hf_tcm/receiver/reconstruction_labeling.py",
    "src/hf_tcm/receiver/iq.py",
    "src/hf_tcm/decoding/reconstruction_viterbi.py",
    "src/hf_tcm/coding/encoder.py",
    "src/hf_tcm/coding/hypotheses.py",
    "src/hf_tcm/modulation/psk8.py",
    "src/hf_tcm/modulation/labeling.py",
    "src/hf_tcm/reconstruction_config.py",
)
RUNTIME_FIELDS = {
    "authorization_provenance",
    "accepted_decision_provenance",
    "runtime_provenance",
    "execution_limits",
    "output",
    "run_manifest",
    "historical_integrity_baseline",
    "preflight",
}


class M10BExecutionBlocked(RuntimeError):
    """Raised when an M10b authorization or integrity gate fails."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha256_value(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _git_provenance() -> dict[str, str | None]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return {"revision": None, "status": "unavailable: workspace is not a Git worktree"}
    revision = result.stdout.strip()
    return {"revision": revision or None, "status": "available" if revision else "unavailable"}


def _write_sidecar(path: Path, digest: str) -> None:
    sidecar = Path(f"{path}.sha256")
    with sidecar.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(digest + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_m10a_draft_fingerprint(draft: Mapping[str, Any]) -> str:
    """Validate the immutable M10a bytes and design before any RNG work."""
    validate_m10a_variable_gain_study(draft)
    if not DRAFT_PATH.is_file() or not Path(f"{DRAFT_PATH}.sha256").is_file():
        raise M10BExecutionBlocked("M10a draft or checksum sidecar is missing")
    actual = _sha256_file(DRAFT_PATH)
    sidecar = Path(f"{DRAFT_PATH}.sha256").read_text(encoding="ascii").strip()
    if actual != EXPECTED_DRAFT_SHA256 or sidecar != actual:
        raise M10BExecutionBlocked("M10a draft hash/sidecar mismatch; blocked before RNG")
    if json.loads(DRAFT_PATH.read_text(encoding="utf-8")) != dict(draft):
        raise M10BExecutionBlocked("in-memory M10a draft differs from frozen bytes")
    return actual


def load_and_validate_accepted_decision(
    draft: Mapping[str, Any], decision_path: str | Path = ACCEPTED_DECISION_PATH
) -> dict[str, Any]:
    """Fail closed unless ADR-016 exactly accepts the evaluation-only model."""
    path = Path(decision_path)
    sidecar = Path(f"{path}.sha256")
    if not path.is_file() or not sidecar.is_file() or not DECISION_DOC_PATH.is_file():
        raise M10BExecutionBlocked("accepted ADR-016 record, doc, or checksum is missing")
    digest = _sha256_file(path)
    doc_digest = _sha256_file(DECISION_DOC_PATH)
    if (
        digest != EXPECTED_DECISION_JSON_SHA256
        or sidecar.read_text(encoding="ascii").strip() != digest
    ):
        raise M10BExecutionBlocked("ADR-016 decision fingerprint mismatch")
    if doc_digest != EXPECTED_DECISION_SHA256:
        raise M10BExecutionBlocked("accepted ADR-016 document fingerprint mismatch")
    decision = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": "adr-016.evaluation-channel-decision.v1",
        "decision_id": "ADR-016",
        "status": "ACCEPTED_EVALUATION_ONLY",
        "accepted_date": "2026-10-30",
        "authorization_provenance": "explicit user authorization through the M10 scientific-decision gate and M10b evaluation instruction",
        "scope": "evaluation-side channel generation and analysis only",
        "profile_id": "controlled_piecewise_real_gain_v1",
        "equation": "y[n] = a[floor(n/8)] * x[n] + w[n]",
        "frame_symbols": 256,
        "samples_per_symbol": 8,
        "switch_symbol_index": 128,
        "switch_sample_index": 1024,
        "nominal_gain": 0.75,
        "low_gain": 0.60,
        "high_gain": math.sqrt(0.765),
        "mean_squared_gain": 0.5625,
        "sigma_squared": NOISE_VARIANCE,
        "receiver_math_changed": False,
        "production_channel_integration": False,
        "paper_exact": False,
        "receiver_enabled": False,
        "adr_015_modified": False,
        "source_mapping_status": "SOURCE_UNRESOLVED",
    }
    if decision != expected:
        raise M10BExecutionBlocked("ADR-016 accepted scope/parameters differ from M10a")
    validate_m10a_draft_fingerprint(draft)
    if draft["channel_profile"]["profile_id"] != decision["profile_id"]:
        raise M10BExecutionBlocked("accepted decision does not match the M10a channel profile")
    return decision


def _derive_seed(master_seed: int, spawn_key: Sequence[int]) -> int:
    sequence = np.random.SeedSequence(master_seed, spawn_key=tuple(spawn_key))
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def build_run_manifest(draft: Mapping[str, Any]) -> dict[str, Any]:
    """Materialize deterministic seed provenance, without initializing RNGs."""
    validate_m10a_draft_fingerprint(draft)
    partition = draft["partition"]
    runs = []
    child_seeds: list[int] = []
    for planned in partition["planned_runs"]:
        index = int(planned["run_index"])
        streams: dict[str, Any] = {}
        for name, code in (("data", 11), ("noise", 23), ("metadata", 41)):
            root_name = "metadata" if name == "metadata" else name
            master = int(EXPECTED_SEED_ROOTS[root_name])
            spawn = [PROTOCOL_WORD, PARTITION_CODE, index, code]
            seed = _derive_seed(master, spawn)
            child_seeds.append(seed)
            streams[name] = {
                "master_seed": master,
                "spawn_key": spawn,
                "derived_seed": seed,
                "generator": "PCG64",
                "initialized": False,
            }
        runs.append(
            {
                "run_id": planned["run_id"],
                "run_index": index,
                "streams": streams,
            }
        )
    bootstrap_seed = _derive_seed(
        int(EXPECTED_SEED_ROOTS["bootstrap"]), [PROTOCOL_WORD, PARTITION_CODE, 0, 37]
    )
    child_seeds.append(bootstrap_seed)
    if len(child_seeds) != len(set(child_seeds)):
        raise M10BExecutionBlocked("M10 child seeds collide across M10 domains")
    roots = set(EXPECTED_SEED_ROOTS.values())
    if len(roots) != 4:
        raise M10BExecutionBlocked("M10 seed roots are not distinct")
    if roots.intersection({2027011001, 2027011002, 2027011003, 2027011004}):
        raise M10BExecutionBlocked("M10 seed roots overlap M8 TRAIN namespace")
    if roots.intersection({2027020101, 2027020102, 2027020103, 2027020104}):
        raise M10BExecutionBlocked("M10 seed roots overlap M9 evaluation namespace")
    return {
        "partition": "EVALUATION",
        "partition_code": PARTITION_CODE,
        "run_index_origin": 0,
        "run_order": "ascending run_index 0..99",
        "generator": "PCG64",
        "protocol_version_word": PROTOCOL_WORD,
        "stream_codes": {"data": 11, "noise": 23, "bootstrap": 37, "metadata": 41},
        "runs": runs,
        "bootstrap": {
            "master_seed": int(EXPECTED_SEED_ROOTS["bootstrap"]),
            "spawn_key": [PROTOCOL_WORD, PARTITION_CODE, 0, 37],
            "derived_seed": bootstrap_seed,
            "generator": "PCG64",
            "initialized": False,
        },
    }


def _source_file_manifest() -> dict[str, str]:
    manifest: dict[str, str] = {}
    for relative in SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise M10BExecutionBlocked(f"runtime source file is missing: {relative}")
        manifest[relative] = _sha256_file(path)
    return manifest


def _historical_baseline() -> dict[str, Any]:
    from hf_tcm.evaluation.m9b_fixed_policy_evaluation_runner import (
        _historical_baseline as m9_baseline,
    )

    result = m9_baseline()
    extra = {
        "M9b_approved_config": "configs/m9b_evaluation_approved_run.json",
        "M9b_outputs": "outputs/m9b_fixed_policy_evaluation/m9_fixed_anchored_vs_frozen_v1",
        "M9_closeout": "docs/M9_FIXED_POLICY_CLOSEOUT.md",
        "M9_report": "docs/M9_FIXED_POLICY_EVALUATION_REPORT.md",
        "M9_design": "docs/M9_FIXED_POLICY_COMPARISON_DESIGN.md",
        "M10a_draft": "configs/m10a_variable_gain_study_draft.json",
        "M10a_draft_sha256": "configs/m10a_variable_gain_study_draft.json.sha256",
    }
    for name, relative in extra.items():
        result[name] = _historical_tree_hash(ROOT / relative)
    return result


def build_approved_config(
    draft: Mapping[str, Any],
    decision: Mapping[str, Any],
    *,
    preflight: Mapping[str, Any],
    output_namespace: str = "outputs/m10b_variable_gain/m10_controlled_piecewise_gain_v1",
) -> dict[str, Any]:
    """Construct (but do not write) the frozen M10b-only approval snapshot."""
    draft_hash = validate_m10a_draft_fingerprint(draft)
    accepted = load_and_validate_accepted_decision(draft)
    if dict(decision) != accepted:
        raise M10BExecutionBlocked("accepted decision changed between preflight and config freeze")
    if preflight.get("status") != "PASS" or preflight.get("experimental_samples_used") is not False:
        raise M10BExecutionBlocked("real deterministic integration preflight did not pass")
    if output_namespace != OUTPUT_PATH.relative_to(ROOT).as_posix():
        raise M10BExecutionBlocked("M10b output namespace differs from the frozen namespace")
    receiver_config = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver_config)
    source_manifest = _source_file_manifest()
    environment = {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "git": _git_provenance(),
    }
    config = copy.deepcopy(dict(draft))
    config.update(
        design_status="approved_evaluation",
        execution_authorized=True,
        execution_scope=EXPECTED_APPROVED_SCOPE,
    )
    config["authorization_provenance"] = {
        "explicit_user_authorization": "explicit user authorization through this M10 instruction",
        "scope": "M10b controlled variable-gain evaluation only; no other experiment or partition",
    }
    config["accepted_decision_provenance"] = {
        "decision_id": "ADR-016",
        "status": "ACCEPTED_EVALUATION_ONLY",
        "decision_json": ACCEPTED_DECISION_PATH.relative_to(ROOT).as_posix(),
        "decision_json_sha256": _sha256_file(ACCEPTED_DECISION_PATH),
        "decision_document": DECISION_DOC_PATH.relative_to(ROOT).as_posix(),
        "decision_document_sha256": _sha256_file(DECISION_DOC_PATH),
        "m10a_draft_sha256": draft_hash,
    }
    config["runtime_provenance"] = {
        "m10a_draft_sha256": draft_hash,
        "approved_config_hash_stored_in_sidecar": True,
        "source_file_manifest": source_manifest,
        "runtime_source_fingerprint_sha256": _sha256_value(source_manifest),
        "environment": environment,
        "receiver_configuration_source": "M5i accepted reconstructed_offline configuration",
        "receiver_configuration_sha256": _sha256_value(receiver_config),
        "clock_origins": clocks.as_dict(),
        "output_schema": SCHEMA,
    }
    config["preflight"] = dict(preflight)
    config["execution_limits"] = {
        "wall_clock_budget_seconds": WALL_CLOCK_BUDGET_SECONDS,
        "rss_monitoring_budget_bytes": RSS_MONITORING_BUDGET_BYTES,
        "rss_semantics": "periodic monitoring only; not a hard OS memory limit",
        "process_count": 1,
        "multiprocessing": False,
        "atomic_checkpoint_after_every_run": True,
        "stop_at_safe_run_boundary_on_budget": True,
        "bootstrap_time_measured_separately": True,
    }
    config["output"] = {
        "namespace": output_namespace,
        "schema_version": SCHEMA,
        "integrity_manifest_excludes_itself": True,
        "resume_policy": "no resume; exact-fingerprint recovery requires separate authorization",
    }
    config["run_manifest"] = build_run_manifest(draft)
    config["historical_integrity_baseline"] = _historical_baseline()
    return config


def _strip_runtime(config: Mapping[str, Any]) -> dict[str, Any]:
    design = {
        key: copy.deepcopy(value) for key, value in config.items() if key not in RUNTIME_FIELDS
    }
    design.update(design_status="proposed", execution_authorized=False, execution_scope="none")
    return design


def validate_approved_config(
    approved: object,
    *,
    draft: Mapping[str, Any],
    config_path: str | Path = APPROVED_PATH,
    verify_file: bool = True,
) -> dict[str, Any]:
    """Validate scientific equivalence, decision, fingerprints, and scope."""
    if not isinstance(approved, Mapping):
        raise M10BExecutionBlocked("M10b approved config must be an object")
    validate_m10a_draft_fingerprint(draft)
    decision = load_and_validate_accepted_decision(draft)
    if (
        approved.get("design_status") != "approved_evaluation"
        or approved.get("execution_authorized") is not True
        or approved.get("execution_scope") != EXPECTED_APPROVED_SCOPE
    ):
        raise M10BExecutionBlocked("M10b approved authorization scope mismatch")
    if approved.get("authorization_provenance", {}).get("explicit_user_authorization") != (
        "explicit user authorization through this M10 instruction"
    ):
        raise M10BExecutionBlocked("M10b user-authorization provenance mismatch")
    if _strip_runtime(approved) != dict(draft):
        raise M10BExecutionBlocked("approved M10b scientific design differs from M10a")
    accepted_provenance = approved.get("accepted_decision_provenance", {})
    if accepted_provenance.get("decision_id") != decision["decision_id"] or accepted_provenance.get(
        "decision_json_sha256"
    ) != _sha256_file(ACCEPTED_DECISION_PATH):
        raise M10BExecutionBlocked("approved config does not match accepted ADR-016")
    runtime = approved.get("runtime_provenance", {})
    source_manifest = _source_file_manifest()
    if runtime.get("source_file_manifest") != source_manifest:
        raise M10BExecutionBlocked("M10b runtime source fingerprint changed")
    if runtime.get("runtime_source_fingerprint_sha256") != _sha256_value(source_manifest):
        raise M10BExecutionBlocked("M10b runtime source digest mismatch")
    expected_environment = {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "git": _git_provenance(),
    }
    if runtime.get("environment") != expected_environment:
        raise M10BExecutionBlocked("M10b runtime environment differs from approved snapshot")
    if approved.get("run_manifest") != build_run_manifest(draft):
        raise M10BExecutionBlocked("M10b run IDs/seeds differ from M10a")
    if approved.get("historical_integrity_baseline") != _historical_baseline():
        raise M10BExecutionBlocked("M10b historical artifacts differ from frozen baseline")
    if approved.get("preflight", {}).get("status") != "PASS":
        raise M10BExecutionBlocked("M10b deterministic real-integration preflight is absent")
    if verify_file:
        path = Path(config_path)
        sidecar = Path(f"{path}.sha256")
        if not path.is_file() or not sidecar.is_file():
            raise M10BExecutionBlocked("M10b approved snapshot or hash sidecar is missing")
        digest = _sha256_file(path)
        if sidecar.read_text(encoding="ascii").strip() != digest:
            raise M10BExecutionBlocked("M10b approved config checksum mismatch")
        if json.loads(path.read_text(encoding="utf-8")) != dict(approved):
            raise M10BExecutionBlocked("in-memory approved M10b config differs from snapshot")
    return dict(approved)


def prepare_approved_config(
    *,
    draft_path: str | Path = DRAFT_PATH,
    decision_path: str | Path = ACCEPTED_DECISION_PATH,
    output_config_path: str | Path = APPROVED_PATH,
) -> dict[str, Any]:
    """Run real deterministic preflight and freeze the approved snapshot."""
    draft_file = Path(draft_path)
    draft = json.loads(draft_file.read_text(encoding="utf-8"))
    if draft_file.resolve() != DRAFT_PATH.resolve():
        raise M10BExecutionBlocked("M10a draft path must be the frozen repository draft")
    validate_m10a_draft_fingerprint(draft)
    decision = load_and_validate_accepted_decision(draft, decision_path)
    smoke = run_real_integration_smoke(draft, decision)
    approved = build_approved_config(draft, decision, preflight=smoke)
    target = Path(output_config_path)
    if target.resolve() != APPROVED_PATH.resolve():
        raise M10BExecutionBlocked("approved M10b config must use the frozen config path")
    if target.exists() or Path(f"{target}.sha256").exists():
        raise M10BExecutionBlocked("M10b approved config already exists; no overwrite")
    _atomic_json(target, approved, exclusive=True)
    _write_sidecar(target, _sha256_file(target))
    return approved


def _array_bytes(values: NDArray[Any]) -> bytes:
    return np.asarray(values, dtype="<c16", order="C").tobytes(order="C")


def _array_sha256(values: NDArray[Any]) -> str:
    return hashlib.sha256(_array_bytes(values)).hexdigest()


def _encode_complex(values: NDArray[np.complex128]) -> str:
    return base64.b64encode(_array_bytes(values)).decode("ascii")


def _decode_complex(encoded: str, *, expected_count: int) -> NDArray[np.complex128]:
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) != expected_count * 16:
        raise ValueError("serialized complex vector has an invalid byte count")
    return np.frombuffer(raw, dtype="<c16").astype(np.complex128, copy=True)


def _waveform_from_bits(bits: NDArray[np.int8]) -> tuple[NDArray[np.int64], NDArray[np.complex128]]:
    symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    labels = [index_to_label(int(item), profile=BASELINE_ASSUMPTION) for item in symbols]
    baseband = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
    in_phase, quadrature = symbols_to_iq_waveform(baseband, samples_per_symbol=8)
    waveform = np.asarray(in_phase + 1j * quadrature, dtype=np.complex128, order="C")
    if waveform.shape != (2048,) or not np.all(np.isfinite(waveform)):
        raise ValueError("M10 waveform must be finite complex128 with 2048 samples")
    waveform.setflags(write=False)
    return np.asarray(symbols, dtype=np.int64), waveform


def _receiver_policy_rows(draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in draft["receiver_policies"]]


def _check_clock_contract(result: Any, *, expected_origin: int = 0) -> None:
    if len(result.metric_provenance) != 256:
        raise ValueError("B4d metric provenance must contain exactly 256 symbols")
    for index, row in enumerate(result.metric_provenance):
        first_sample = expected_origin + index * 8
        if (
            row.absolute_symbol_index != index
            or row.estimator_time_index != index
            or row.sample_indices != tuple(range(first_sample, first_sample + 8))
            or row.prediction_cutoff_sample_index != first_sample - 1
            or row.observation_cutoff_sample_index != first_sample + 7
            or row.hypothesis_ids != tuple(range(16))
        ):
            raise ValueError("B4d absolute clock/canonical edge provenance mismatch")


def _decode_one(
    *,
    policy: Mapping[str, Any],
    received: NDArray[np.complex128],
    reference_bits: NDArray[np.int8],
    reference_symbols: NDArray[np.int64],
    received_sha256: str,
    receiver_configuration: Mapping[str, Any],
    clocks: Any,
) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    from hf_tcm.receiver.reconstruction_conditional_decode import (
        decode_reconstruction_conditional_sequence,
    )

    kwargs = _receiver_kwargs(
        policy=policy,
        received=received,
        receiver_configuration=receiver_configuration,
        clocks=clocks,
    )
    forbidden = {
        "channel_truth",
        "ChannelTruth",
        "true_gain",
        "gain_schedule",
        "switch_index",
        "reference_bits",
        "reference_symbols",
        "correct_path",
        "true_per_symbol_gain",
    }
    if forbidden.intersection(kwargs):
        raise ValueError("oracle/channel-truth input leaked into receiver invocation")
    result = decode_reconstruction_conditional_sequence(**kwargs)
    count = reference_symbols.size
    if result.candidate_metrics.shape != (count, 16) or not np.all(
        np.isfinite(result.candidate_metrics)
    ):
        raise FloatingPointError("candidate metric array must be finite with shape (256,16)")
    if result.final_posterior.shape != (16,) or not np.all(np.isfinite(result.final_posterior)):
        raise FloatingPointError("final posterior must contain 16 finite values")
    posterior_sum = float(np.sum(result.final_posterior))
    if not np.isclose(posterior_sum, 1.0, rtol=0.0, atol=1e-12):
        raise FloatingPointError("final posterior is not normalized")
    _check_clock_contract(result, expected_origin=clocks.absolute_sample_origin)
    path = tuple(int(item) for item in result.decoder_result.hypothesis_ids)
    path_rows = validate_hypothesis_edge_path(path, initial_state=INITIAL_STATE)
    decoded_bits = np.asarray(result.decoder_result.decoded_bits, dtype=np.int8)
    decoded_symbols = decoded_path_symbol_indices(
        path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    if decoded_bits.shape != (512,) or decoded_symbols.shape != (256,) or len(path) != 256:
        raise ValueError("conditional Viterbi output dimensions are invalid")
    expected_bits = np.asarray([bit for row in path_rows for bit in row.input_bits], dtype=np.int8)
    if not np.array_equal(decoded_bits, expected_bits):
        raise ValueError("decoder bits do not match its canonical M1 edge path")
    final_state = result.final_estimator_state
    full = np.asarray(final_state.full_iq, dtype=np.float64)
    fluctuating = np.asarray(final_state.fluctuating_iq, dtype=np.float64)
    if not np.all(np.isfinite(full)) or not np.all(np.isfinite(fluctuating)):
        raise FloatingPointError("final estimator coefficients are non-finite")
    if not np.allclose(
        fluctuating + np.asarray(policy["mu0"], dtype=np.float64)[None, :],
        full,
        atol=1e-12,
        rtol=0.0,
    ):
        raise FloatingPointError("full/fluctuating/anchor decomposition failed")
    counts = ErrorCounts(
        bit_errors=count_bit_errors(reference_bits, decoded_bits),
        total_bits=int(reference_bits.size),
        symbol_errors=count_symbol_errors(reference_symbols, decoded_symbols),
        total_symbols=int(reference_symbols.size),
    )
    bit_halves = []
    symbol_halves = []
    for symbol_start, symbol_stop in ((0, 128), (128, 256)):
        bit_start, bit_stop = 2 * symbol_start, 2 * symbol_stop
        bit_halves.append(
            {
                "symbol_interval_half_open": [symbol_start, symbol_stop],
                "decoded_bit_interval_half_open": [bit_start, bit_stop],
                "bit_errors": count_bit_errors(
                    reference_bits[bit_start:bit_stop], decoded_bits[bit_start:bit_stop]
                ),
                "total_bits": bit_stop - bit_start,
                "symbol_errors": count_symbol_errors(
                    reference_symbols[symbol_start:symbol_stop],
                    decoded_symbols[symbol_start:symbol_stop],
                ),
                "total_symbols": symbol_stop - symbol_start,
                "interpretation": "descriptive segment of one full-frame conditional Viterbi traceback; not an online prefix result",
            }
        )
        symbol_halves.append((symbol_start, symbol_stop))
    record = {
        "candidate_id": policy["candidate_id"],
        "alpha_prime": policy["alpha_prime"],
        "k_tilde": list(policy["k_tilde"]),
        "mu0": list(policy["mu0"]),
        "initial_fluctuating_iq": list(policy["initial_fluctuating_iq"]),
        "initial_full_iq": list(policy["initial_full_iq"]),
        "beta": policy["beta"],
        "status": "complete_valid_output",
        "decoder_invocations": 1,
        "received_sha256": received_sha256,
        "counts": {
            "bit_errors": counts.bit_errors,
            "total_bits": counts.total_bits,
            "symbol_errors": counts.symbol_errors,
            "total_symbols": counts.total_symbols,
        },
        "decoded_information_bits": decoded_bits.astype(int).tolist(),
        "decoded_symbol_indices": decoded_symbols.astype(int).tolist(),
        "decoded_hypothesis_path": list(path),
        "decoder_path_cost": float(result.decoder_result.best_path_metric),
        "candidate_metrics_shape": [256, 16],
        "final_posterior_sum": posterior_sum,
        "posterior_normalized": True,
        "final_full_iq": full.tolist(),
        "final_fluctuating_iq": fluctuating.tolist(),
        "coefficient_diagnostics": {
            "finite_final_full_iq": True,
            "finite_final_fluctuating_iq": True,
            "final_full_norm": float(np.linalg.norm(full)),
            "final_fluctuating_norm": float(np.linalg.norm(fluctuating)),
            "per_symbol_coefficient_trajectory": "unavailable from the conditional decode API",
        },
        "segment_diagnostics": bit_halves,
        "metric_clock_provenance": [
            {
                "absolute_symbol_index": row.absolute_symbol_index,
                "estimator_time_index": row.estimator_time_index,
                "sample_indices": list(row.sample_indices),
                "prediction_cutoff_sample_index": row.prediction_cutoff_sample_index,
                "observation_cutoff_sample_index": row.observation_cutoff_sample_index,
                "hypothesis_ids": list(row.hypothesis_ids),
            }
            for row in result.metric_provenance
        ],
    }
    return record, result, kwargs


def _smoke_fixture() -> tuple[
    NDArray[np.int8], NDArray[np.int64], NDArray[np.complex128], NDArray[np.complex128]
]:
    bits = np.asarray([(3 * index + 1) % 2 for index in range(512)], dtype=np.int8)
    symbols, waveform = _waveform_from_bits(bits)
    noise = np.asarray(
        [
            complex(((index * 3) % 19 - 9) / 1000, ((index * 7) % 23 - 11) / 1200)
            for index in range(2048)
        ],
        dtype=np.complex128,
    )
    noise.setflags(write=False)
    return bits, symbols, waveform, noise


def run_real_integration_smoke(
    draft: Mapping[str, Any], decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Call the actual M10 receiver orchestration on deterministic data only."""
    load_and_validate_accepted_decision(draft)
    if decision.get("decision_id") != "ADR-016":
        raise M10BExecutionBlocked("real smoke requires accepted ADR-016")
    from hf_tcm.receiver import reconstruction_conditional_decode as conditional_module
    from hf_tcm.receiver.reconstruction_conditional_decode import (
        decode_reconstruction_conditional_sequence,
    )

    bits, symbols, waveform, noise = _smoke_fixture()
    receiver_config = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver_config)
    if "clock_origins" in draft:
        raise M10BExecutionBlocked("M10a must not gain an invented clock_origins field")
    policies = _receiver_policy_rows(draft)
    calls = 0
    original = conditional_module.decode_reconstruction_viterbi

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    conditional_module.decode_reconstruction_viterbi = counted
    orchestrator_calls = 0
    direct_calls = 0
    try:
        for profile_id in PROFILE_LABELS:
            schedule = build_gain_schedule(profile_id)
            received = apply_symbol_gain_schedule(waveform, noise, schedule)
            if received.shape != (2048,) or received.dtype != np.complex128:
                raise ValueError("M10 smoke received buffer shape/dtype mismatch")
            expected_switch = schedule[128] * waveform[1024] + noise[1024]
            if received[1024] != expected_switch:
                raise ValueError("M10 switch does not begin at sample 1024")
            received_hash = _array_sha256(received)
            decoded_for_pair = []
            for policy in policies:
                record, result, kwargs = _decode_one(
                    policy=policy,
                    received=received,
                    reference_bits=bits,
                    reference_symbols=symbols,
                    received_sha256=received_hash,
                    receiver_configuration=receiver_config,
                    clocks=clocks,
                )
                orchestrator_calls += 1
                if record["status"] != "complete_valid_output":
                    raise ValueError(
                        "M10 deterministic real receiver smoke returned invalid output"
                    )
                decoded_for_pair.append((policy, result))
                direct = decode_reconstruction_conditional_sequence(**kwargs)
                direct_calls += 1
                np.testing.assert_array_equal(
                    result.decoder_result.decoded_bits, direct.decoder_result.decoded_bits
                )
                np.testing.assert_array_equal(result.candidate_metrics, direct.candidate_metrics)
                np.testing.assert_array_equal(
                    result.final_estimator_state.full_iq,
                    direct.final_estimator_state.full_iq,
                )
                np.testing.assert_array_equal(
                    result.decoder_result.hypothesis_ids,
                    direct.decoder_result.hypothesis_ids,
                )
                if kwargs["beta"] != 0.7 or kwargs["initial_estimator_time_index"] != 0:
                    raise ValueError("M10 B4d smoke policy or clock configuration mismatch")
                if kwargs["first_symbol_index"] != 0 or kwargs["received_start_sample"] != 0:
                    raise ValueError("M10 B4d sample/symbol origins must resolve to zero")
                if kwargs["initial_estimator_state"].full_iq.tolist() != [[0.42, 0.91]]:
                    raise ValueError("M10 receiver initial full state mismatch")
                if np.asarray(kwargs["mu0"]).tolist() != [policy["mu0"]]:
                    raise ValueError("M10 receiver anchor mismatch")
                if result.candidate_metrics.shape != (256, 16):
                    raise ValueError("M10 smoke metric shape mismatch")
                if result.final_posterior.shape != (16,) or not np.isclose(
                    np.sum(result.final_posterior), 1.0, atol=1e-12, rtol=0.0
                ):
                    raise ValueError("M10 smoke posterior is invalid")
            if decoded_for_pair[0][1].candidate_metrics[0].shape != (16,):
                raise ValueError("M10 canonical 16-edge metric ordering failed")

        # Alter only future samples and check that the first two local metric
        # rows are unchanged; this is a deterministic causal-cutoff check.
        sample_prefix = np.asarray(noise + waveform, dtype=np.complex128)
        sample_prefix.setflags(write=False)
        policy = policies[0]
        kwargs_a = _receiver_kwargs(
            policy=policy,
            received=sample_prefix,
            receiver_configuration=receiver_config,
            clocks=clocks,
        )
        changed = np.array(sample_prefix, copy=True)
        changed[16:] += 0.125 - 0.25j
        changed.setflags(write=False)
        kwargs_b = dict(kwargs_a)
        kwargs_b["received"] = changed
        result_a = decode_reconstruction_conditional_sequence(**kwargs_a)
        result_b = decode_reconstruction_conditional_sequence(**kwargs_b)
        np.testing.assert_array_equal(
            result_a.candidate_metrics[:2], result_b.candidate_metrics[:2]
        )
    finally:
        conditional_module.decode_reconstruction_viterbi = original
    if calls != orchestrator_calls + direct_calls + 2:
        raise ValueError(
            "M10 real smoke decoder invocation counter mismatch: "
            f"actual={calls}, orchestrator={orchestrator_calls}, direct={direct_calls}"
        )
    return {
        "status": "PASS",
        "fixture": "deterministic 512-bit TCM/256-symbol ZOH fixture with explicit complex noise",
        "experimental_samples_used": False,
        "profile_ids": list(PROFILE_LABELS),
        "policy_ids": [row["candidate_id"] for row in policies],
        "profile_policy_invocations": orchestrator_calls,
        "direct_api_comparison_invocations": direct_calls,
        "causal_cutoff_auxiliary_invocations": 2,
        "decoder_invocation_count": calls,
        "candidate_metric_shape": [256, 16],
        "posterior_shape": [16],
        "switch_symbol_index": 128,
        "switch_sample_index": 1024,
        "clocks": resolve_m9_clock_origins(receiver_config).as_dict(),
        "same_waveform_and_noise_across_profiles": True,
        "receiver_arguments_exclude_truth": True,
        "causal_cutoff_checks": True,
        "m8b_clock_origins_regression": True,
        "direct_api_equivalence": True,
    }


def _profile_records_for_summary(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": checkpoint["run_id"],
        "profiles": {
            profile["profile_id"]: {
                row["candidate_id"]: row["counts"]
                for row in profile["policies"]
                if row.get("status") == "complete_valid_output"
            }
            for profile in checkpoint["profiles"]
        },
    }


def _contrast_point(records: Sequence[Mapping[str, Any]], profile_id: str) -> dict[str, Any]:
    b_bits = a_bits = b_symbols = a_symbols = 0
    for row in records:
        profiles = row["profiles"][profile_id]
        b = profiles["historical_frozen_B"]
        anchor = profiles["anch_a085_k025"]
        b_bits += int(b["bit_errors"])
        a_bits += int(anchor["bit_errors"])
        b_symbols += int(b["symbol_errors"])
        a_symbols += int(anchor["symbol_errors"])
    return {
        "historical_frozen_B": {
            "bit_errors": b_bits,
            "total_bits": len(records) * 512,
            "ber": b_bits / (len(records) * 512),
            "symbol_errors": b_symbols,
            "total_symbols": len(records) * 256,
            "ser": b_symbols / (len(records) * 256),
        },
        "anch_a085_k025": {
            "bit_errors": a_bits,
            "total_bits": len(records) * 512,
            "ber": a_bits / (len(records) * 512),
            "symbol_errors": a_symbols,
            "total_symbols": len(records) * 256,
            "ser": a_symbols / (len(records) * 256),
        },
        "delta_bit_errors": a_bits - b_bits,
        "delta_ber": (a_bits - b_bits) / (len(records) * 512),
        "delta_symbol_errors": a_symbols - b_symbols,
        "delta_ser": (a_symbols - b_symbols) / (len(records) * 256),
    }


def _joint_bootstrap(records: Sequence[Mapping[str, Any]], bootstrap_seed: int) -> dict[str, Any]:
    count = len(records)
    rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    indices = rng.integers(0, count, size=(BOOTSTRAP_REPLICATES, count), dtype=np.int64)
    contrasts = np.empty((BOOTSTRAP_REPLICATES, 8), dtype=np.float64)
    for replicate, selected in enumerate(indices):
        points = [
            _contrast_point([records[int(index)] for index in selected], profile)
            for profile in PROFILE_LABELS
        ]
        deltas = [point["delta_ber"] for point in points]
        delta_sers = [point["delta_ser"] for point in points]
        contrasts[replicate] = (
            deltas[0],
            deltas[1],
            deltas[2],
            delta_sers[0],
            delta_sers[1],
            delta_sers[2],
            deltas[1] - deltas[0],
            deltas[2] - deltas[1],
        )
    scalar = _joint_bootstrap_scalar(records, bootstrap_seed)
    alpha = (1.0 - CONFIDENCE_LEVEL) / 2.0
    bounds = np.quantile(contrasts, [alpha, 1.0 - alpha], axis=0, method="linear")
    names = (
        "DeltaBER_P0",
        "DeltaBER_P1",
        "DeltaBER_P2",
        "DeltaSER_P0",
        "DeltaSER_P1",
        "DeltaSER_P2",
        "DeltaBER_P1_minus_P0",
        "DeltaBER_P2_minus_P1",
    )
    intervals = {
        name: [float(bounds[0, index]), float(bounds[1, index])] for index, name in enumerate(names)
    }
    if hashlib.sha256(indices.tobytes()).hexdigest() != scalar["indices_sha256"]:
        raise M10BExecutionBlocked("M10 paired-bootstrap scalar index oracle mismatch")
    for name, interval in intervals.items():
        if not np.allclose(interval, scalar["intervals"][name], rtol=0.0, atol=1e-15):
            raise M10BExecutionBlocked(f"M10 paired-bootstrap scalar oracle mismatch for {name}")
    return {
        "method": "ADR-014 paired full-run cluster bootstrap",
        "cluster_unit": "one run containing P0/P1/P2 and both policies",
        "replicates": BOOTSTRAP_REPLICATES,
        "confidence_level": CONFIDENCE_LEVEL,
        "interval": "percentile",
        "quantile_method": "numpy.quantile(method='linear')",
        "generator": "PCG64",
        "shared_run_index_resampling": True,
        "resample_index_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
        "intervals": intervals,
        "independent_scalar_oracle": scalar,
    }


def _joint_bootstrap_scalar(
    records: Sequence[Mapping[str, Any]], bootstrap_seed: int
) -> dict[str, Any]:
    count = len(records)
    rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    indices = rng.integers(0, count, size=(BOOTSTRAP_REPLICATES, count), dtype=np.int64)
    names = (
        "DeltaBER_P0",
        "DeltaBER_P1",
        "DeltaBER_P2",
        "DeltaSER_P0",
        "DeltaSER_P1",
        "DeltaSER_P2",
        "DeltaBER_P1_minus_P0",
        "DeltaBER_P2_minus_P1",
    )
    columns: list[list[float]] = [[] for _ in names]
    for selected in indices:
        bit_deltas = [0, 0, 0]
        symbol_deltas = [0, 0, 0]
        for index in selected:
            row = records[int(index)]
            for profile_index, profile_id in enumerate(PROFILE_LABELS):
                pair = row["profiles"][profile_id]
                bit_deltas[profile_index] += int(pair["anch_a085_k025"]["bit_errors"]) - int(
                    pair["historical_frozen_B"]["bit_errors"]
                )
                symbol_deltas[profile_index] += int(pair["anch_a085_k025"]["symbol_errors"]) - int(
                    pair["historical_frozen_B"]["symbol_errors"]
                )
        ber = [value / (count * 512) for value in bit_deltas]
        ser = [value / (count * 256) for value in symbol_deltas]
        values = (*ber, *ser, ber[1] - ber[0], ber[2] - ber[1])
        for column, value in zip(columns, values, strict=True):
            column.append(value)
    alpha = (1.0 - CONFIDENCE_LEVEL) / 2.0
    intervals = {
        name: [
            float(np.quantile(values, alpha, method="linear")),
            float(np.quantile(values, 1.0 - alpha, method="linear")),
        ]
        for name, values in zip(names, columns, strict=True)
    }
    return {
        "indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
        "intervals": intervals,
    }


def summarize_m10b_checkpoints(
    records: Sequence[Mapping[str, Any]], *, bootstrap_seed: int
) -> dict[str, Any]:
    """Pool raw counts and compute joint-profile paired intervals."""
    if len(records) != 100 or len({row.get("run_id") for row in records}) != 100:
        raise ValueError("complete M10 summary requires exactly 100 unique run clusters")
    points = {profile: _contrast_point(records, profile) for profile in PROFILE_LABELS}
    for profile, point in points.items():
        if point["historical_frozen_B"]["total_bits"] != 51200:
            raise ValueError(f"M10 B bit denominator mismatch for {profile}")
        if point["anch_a085_k025"]["total_bits"] != 51200:
            raise ValueError(f"M10 anchored bit denominator mismatch for {profile}")
        if point["historical_frozen_B"]["total_symbols"] != 25600:
            raise ValueError(f"M10 B symbol denominator mismatch for {profile}")
    bootstrap = _joint_bootstrap(records, bootstrap_seed)
    return {
        "status": "M10_EVALUATION_COMPLETE_VERIFIED",
        "cluster_count": len(records),
        "primary_profile": "P1_HIGH_TO_LOW",
        "primary_estimand": "pooled raw-count DeltaBER_P1 = BER(anch_a085_k025,P1) - BER(historical_frozen_B,P1)",
        "primary_delta_ber": points["P1_HIGH_TO_LOW"]["delta_ber"],
        "primary_95_percent_ci": bootstrap["intervals"]["DeltaBER_P1"],
        "contrasts": points,
        "profiles": points,
        "difference_in_differences": {
            "P1_minus_P0_delta_ber": points["P1_HIGH_TO_LOW"]["delta_ber"]
            - points["P0_CONSTANT"]["delta_ber"],
            "P2_minus_P1_delta_ber": points["P2_LOW_TO_HIGH"]["delta_ber"]
            - points["P1_HIGH_TO_LOW"]["delta_ber"],
        },
        "bootstrap": bootstrap,
    }


def _expected_policy_record(policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: policy[key]
        for key in (
            "candidate_id",
            "alpha_prime",
            "k_tilde",
            "mu0",
            "initial_fluctuating_iq",
            "initial_full_iq",
            "beta",
        )
    }


def independent_verify(
    directory: str | Path,
    approved: Mapping[str, Any],
    draft: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild received buffers and independently recount saved decoded arrays."""
    root = Path(directory)
    files = sorted((root / "checkpoints").glob("run-*.json"))
    checkpoints = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    planned_runs = approved["run_manifest"]["runs"]
    expected_ids = [row["run_id"] for row in planned_runs]
    if [row.get("run_id") for row in checkpoints] != expected_ids[: len(checkpoints)]:
        raise ValueError("M10 run IDs are missing, duplicated, or out of order")
    if len(checkpoints) != 100:
        return {
            "status": "M10_INCOMPLETE_OR_BLOCKED",
            "completed_runs": len(checkpoints),
            "run_count_expected": 100,
            "failures": [],
        }
    policies = _receiver_policy_rows(draft)
    seen_runs: set[str] = set()
    received_hashes: set[str] = set()
    all_counts: dict[str, dict[str, dict[str, int]]] = {
        profile: {
            policy["candidate_id"]: {
                "bit_errors": 0,
                "symbol_errors": 0,
                "total_bits": 0,
                "total_symbols": 0,
            }
            for policy in policies
        }
        for profile in PROFILE_LABELS
    }
    total_decoder_calls = 0
    failures: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    from hf_tcm.coding.hypotheses import HYPOTHESES

    for index, (checkpoint, planned) in enumerate(zip(checkpoints, planned_runs, strict=True)):
        if (
            checkpoint.get("run_index") != index
            or checkpoint.get("seed_provenance") != planned["streams"]
        ):
            raise ValueError("M10 run index/seed provenance differs from frozen run manifest")
        if checkpoint.get("approved_config_sha256") != _sha256_file(APPROVED_PATH):
            raise ValueError("M10 checkpoint config fingerprint mismatch")
        if (
            checkpoint.get("runtime_source_fingerprint_sha256")
            != approved["runtime_provenance"]["runtime_source_fingerprint_sha256"]
        ):
            raise ValueError("M10 checkpoint runtime fingerprint mismatch")
        if checkpoint.get("status") != "complete" or len(checkpoint.get("profiles", [])) != 3:
            failures.append({"run_id": checkpoint["run_id"], "reason": checkpoint.get("status")})
            continue
        seen_runs.add(checkpoint["run_id"])
        bits = np.asarray(
            checkpoint["evaluation_only"]["reference_information_bits"], dtype=np.int8
        )
        symbols = np.asarray(
            checkpoint["evaluation_only"]["reference_symbol_indices"], dtype=np.int64
        )
        if bits.shape != (512,) or symbols.shape != (256,):
            raise ValueError("M10 saved reference shapes are invalid")
        data_seed = int(planned["streams"]["data"]["derived_seed"])
        data_rng = np.random.Generator(np.random.PCG64(data_seed))
        regenerated_bits = data_rng.integers(0, 2, size=512, dtype=np.int8)
        noise_seed = int(planned["streams"]["noise"]["derived_seed"])
        regenerated_noise = np.asarray(
            generate_independent_complex_awgn(
                sample_count=2048,
                sigma_squared=NOISE_VARIANCE,
                seed=noise_seed,
                stream_id=f"M10b:EVALUATION:{checkpoint['run_id']}:shared-noise",
            ).noise,
            dtype=np.complex128,
            order="C",
        )
        if not np.array_equal(bits, regenerated_bits):
            raise ValueError("M10 transmitted bits do not reproduce from frozen data seed")
        expected_symbols, expected_waveform = _waveform_from_bits(bits)
        if not np.array_equal(symbols, expected_symbols):
            raise ValueError(
                "M10 saved reference symbols differ from independent M1/labeling replay"
            )
        waveform = _decode_complex(
            checkpoint["evaluation_only"]["waveform_iq_base64"], expected_count=2048
        )
        noise = _decode_complex(
            checkpoint["evaluation_only"]["noise_iq_base64"], expected_count=2048
        )
        if not np.array_equal(waveform, expected_waveform):
            raise ValueError("M10 saved waveform differs from independent encoded waveform")
        if _array_sha256(waveform) != checkpoint["evaluation_only"]["waveform_sha256"]:
            raise ValueError("M10 waveform hash mismatch")
        if _array_sha256(noise) != checkpoint["evaluation_only"]["noise_sha256"]:
            raise ValueError("M10 shared noise hash mismatch")
        if not np.array_equal(noise, regenerated_noise):
            raise ValueError("M10 shared noise does not reproduce from frozen noise seed")
        profile_rows = {row["profile_id"]: row for row in checkpoint["profiles"]}
        if tuple(profile_rows) != PROFILE_LABELS:
            raise ValueError("M10 profile order/IDs mismatch")
        run_pair: dict[str, Any] = {"run_id": checkpoint["run_id"], "profiles": {}}
        for profile_id in PROFILE_LABELS:
            profile_row = profile_rows[profile_id]
            schedule = build_gain_schedule(profile_id)
            received = apply_symbol_gain_schedule(waveform, noise, schedule)
            received_hash = _array_sha256(received)
            if profile_row.get("received_sha256") != received_hash:
                raise ValueError(f"M10 reconstructed {profile_id} received hash mismatch")
            received_hashes.add(received_hash)
            if (
                profile_row.get("gain_schedule_sha256")
                != hashlib.sha256(np.asarray(schedule, dtype="<f8").tobytes()).hexdigest()
            ):
                raise ValueError("M10 gain-schedule fingerprint mismatch")
            policy_rows = profile_row.get("policies", [])
            if [row.get("candidate_id") for row in policy_rows] != list(POLICY_IDS):
                raise ValueError("M10 policy order/IDs mismatch")
            run_pair["profiles"][profile_id] = {}
            for record, policy in zip(policy_rows, policies, strict=True):
                total_decoder_calls += int(record.get("decoder_invocations", 0))
                for key, expected in _expected_policy_record(policy).items():
                    if record.get(key) != expected:
                        raise ValueError(f"M10 policy {policy['candidate_id']} {key} mismatch")
                if (
                    record.get("status") != "complete_valid_output"
                    or record.get("decoder_invocations") != 1
                ):
                    failures.append(
                        {
                            "run_id": checkpoint["run_id"],
                            "profile_id": profile_id,
                            "candidate_id": policy["candidate_id"],
                            "reason": record.get("status"),
                        }
                    )
                    continue
                if record.get("received_sha256") != received_hash:
                    raise ValueError("M10 policy used a different profile-specific received vector")
                decoded_bits = np.asarray(record["decoded_information_bits"], dtype=np.int8)
                decoded_symbols = np.asarray(record["decoded_symbol_indices"], dtype=np.int64)
                path = tuple(int(edge) for edge in record["decoded_hypothesis_path"])
                if (
                    decoded_bits.shape != (512,)
                    or decoded_symbols.shape != (256,)
                    or len(path) != 256
                ):
                    raise ValueError("M10 decoded outputs have incorrect dimensions")
                from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path

                validate_hypothesis_edge_path(path, initial_state=INITIAL_STATE)
                path_bits = np.asarray(
                    [bit for edge in path for bit in HYPOTHESES[edge].input_bits], dtype=np.int8
                )
                path_symbols = decoded_path_symbol_indices(
                    path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
                )
                if not np.array_equal(path_bits, decoded_bits) or not np.array_equal(
                    path_symbols, decoded_symbols
                ):
                    raise ValueError("M10 decoded arrays differ from canonical Viterbi path")
                counts = {
                    "bit_errors": count_bit_errors(bits, decoded_bits),
                    "total_bits": 512,
                    "symbol_errors": count_symbol_errors(symbols, decoded_symbols),
                    "total_symbols": 256,
                }
                if counts != record.get("counts"):
                    raise ValueError("M10 stored errors differ from independent raw-array recount")
                diagnostics = record.get("coefficient_diagnostics", {})
                if (
                    not diagnostics.get("finite_final_full_iq")
                    or not diagnostics.get("finite_final_fluctuating_iq")
                    or not record.get("posterior_normalized")
                ):
                    raise ValueError("M10 coefficient/posterior diagnostics invalid")
                aggregate = all_counts[profile_id][policy["candidate_id"]]
                for name in aggregate:
                    aggregate[name] += counts[name]
                run_pair["profiles"][profile_id][policy["candidate_id"]] = {
                    "bit_errors": counts["bit_errors"],
                    "symbol_errors": counts["symbol_errors"],
                    "total_bits": counts["total_bits"],
                    "total_symbols": counts["total_symbols"],
                }
            if len(run_pair["profiles"][profile_id]) != 2:
                failures.append(
                    {
                        "run_id": checkpoint["run_id"],
                        "profile_id": profile_id,
                        "reason": "missing valid policy",
                    }
                )
        if all(len(run_pair["profiles"].get(profile, {})) == 2 for profile in PROFILE_LABELS):
            paired_rows.append(run_pair)
        if checkpoint.get("decoder_invocations") != sum(
            int(row.get("decoder_invocations", 0))
            for profile in checkpoint["profiles"]
            for row in profile["policies"]
        ):
            raise ValueError("M10 checkpoint decoder invocation total mismatch")
    complete = (
        len(seen_runs) == 100
        and len(paired_rows) == 100
        and len(received_hashes) == 300
        and total_decoder_calls == 600
        and not failures
    )
    return {
        "status": "M10_EVALUATION_COMPLETE_VERIFIED" if complete else "M10_INCOMPLETE_OR_BLOCKED",
        "run_count": len(checkpoints),
        "unique_run_count": len(seen_runs),
        "unique_received_hash_count": len(received_hashes),
        "profile_received_buffer_count": len(received_hashes),
        "valid_paired_run_count": len(paired_rows),
        "policy_record_count": sum(
            len(row.get("policies", [])) for cp in checkpoints for row in cp.get("profiles", [])
        ),
        "decoder_invocations": total_decoder_calls,
        "decoder_invocations_expected": 600,
        "failure_count": len(failures),
        "failures": failures,
        "pooled_counts": all_counts,
        "paired_run_counts": paired_rows,
    }


def _checkpoint_path(directory: Path, run_id: str) -> Path:
    return directory / "checkpoints" / f"{run_id.rsplit(':', 1)[-1]}.json"


def _output_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): _sha256_file(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "integrity_manifest.json"
    }


def _failure_policy_record(
    policy: Mapping[str, Any], received_hash: str | None, exc: Exception
) -> dict[str, Any]:
    record = _expected_policy_record(policy)
    record.update(
        status="numerical_or_decoder_failure",
        decoder_invocations=0,
        received_sha256=received_hash,
        exception_type=type(exc).__name__,
        detail=str(exc),
    )
    return record


def _generate_run_inputs(
    planned: Mapping[str, Any],
) -> tuple[NDArray[np.int8], NDArray[np.int64], NDArray[np.complex128], NDArray[np.complex128]]:
    data_seed = int(planned["streams"]["data"]["derived_seed"])
    noise_seed = int(planned["streams"]["noise"]["derived_seed"])
    data_rng = np.random.Generator(np.random.PCG64(data_seed))
    bits = data_rng.integers(0, 2, size=512, dtype=np.int8)
    symbols, waveform = _waveform_from_bits(bits)
    noise = generate_independent_complex_awgn(
        sample_count=2048,
        sigma_squared=NOISE_VARIANCE,
        seed=noise_seed,
        stream_id=f"M10b:EVALUATION:{planned['run_id']}:shared-noise",
    ).noise
    noise = np.asarray(noise, dtype=np.complex128, order="C")
    noise.setflags(write=False)
    return bits, symbols, waveform, noise


def _run_checkpoint(
    *,
    planned: Mapping[str, Any],
    draft: Mapping[str, Any],
    approved: Mapping[str, Any],
    receiver_config: Mapping[str, Any],
    clocks: Any,
    decoder_counter: Callable[[], int],
    config_hash: str,
) -> dict[str, Any]:
    bits, symbols, waveform, noise = _generate_run_inputs(planned)
    common = {
        "reference_information_bits": bits.astype(int).tolist(),
        "reference_symbol_indices": symbols.astype(int).tolist(),
        "waveform_iq_base64": _encode_complex(waveform),
        "noise_iq_base64": _encode_complex(noise),
        "waveform_sha256": _array_sha256(waveform),
        "noise_sha256": _array_sha256(noise),
        "waveform_serialization": "C-order little-endian complex128; raw bytes",
        "noise_serialization": "C-order little-endian complex128; raw bytes",
        "sigma_squared": NOISE_VARIANCE,
    }
    profiles = []
    calls_at_start = decoder_counter()
    policies = _receiver_policy_rows(draft)
    for profile_id in PROFILE_LABELS:
        schedule = build_gain_schedule(profile_id)
        received = apply_symbol_gain_schedule(waveform, noise, schedule)
        received_hash = _array_sha256(received)
        profile_row: dict[str, Any] = {
            "profile_id": profile_id,
            "gain_schedule_sha256": hashlib.sha256(
                np.asarray(schedule, dtype="<f8").tobytes()
            ).hexdigest(),
            "received_sha256": received_hash,
            "received_shape": [2048],
            "received_dtype": "complex128",
            "policies": [],
        }
        for policy in policies:
            before = decoder_counter()
            try:
                record, _, _ = _decode_one(
                    policy=policy,
                    received=received,
                    reference_bits=bits,
                    reference_symbols=symbols,
                    received_sha256=received_hash,
                    receiver_configuration=receiver_config,
                    clocks=clocks,
                )
                calls = decoder_counter() - before
                if calls != 1:
                    raise RuntimeError(f"expected one decoder call; observed {calls}")
                profile_row["policies"].append(record)
            except Exception as exc:
                calls = decoder_counter() - before
                failed = _failure_policy_record(policy, received_hash, exc)
                failed["decoder_invocations"] = calls
                profile_row["policies"].append(failed)
        profiles.append(profile_row)
    total_calls = decoder_counter() - calls_at_start
    return {
        "schema_version": SCHEMA,
        "run_id": planned["run_id"],
        "run_index": planned["run_index"],
        "status": "complete"
        if all(
            len(profile["policies"]) == 2
            and all(
                policy.get("status") == "complete_valid_output" for policy in profile["policies"]
            )
            for profile in profiles
        )
        else "incomplete",
        "approved_config_sha256": config_hash,
        "runtime_source_fingerprint_sha256": approved["runtime_provenance"][
            "runtime_source_fingerprint_sha256"
        ],
        "seed_provenance": {
            name: {**value, "initialized": name in ("data", "noise")}
            for name, value in planned["streams"].items()
        },
        "decoder_invocations": total_calls,
        "evaluation_only": common,
        "profiles": profiles,
    }


def execute_m10b(
    *,
    approved_config_path: str | Path = APPROVED_PATH,
    draft_path: str | Path = DRAFT_PATH,
    output_path: str | Path = OUTPUT_PATH,
) -> dict[str, Any]:
    """Execute exactly the frozen 100-run M10b evaluation, or report incomplete."""
    approved_path = Path(approved_config_path)
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    validate_approved_config(approved, draft=draft, config_path=approved_path, verify_file=True)
    out = Path(output_path)
    if out.resolve() != OUTPUT_PATH.resolve():
        raise M10BExecutionBlocked("M10b output path differs from approved namespace")
    if out.exists():
        raise M10BExecutionBlocked("M10b output namespace already exists; no implicit resume")
    receiver_config = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver_config)
    baseline_before = _historical_baseline()
    if baseline_before != approved["historical_integrity_baseline"]:
        raise M10BExecutionBlocked("historical integrity changed before M10 RNG")
    if approved["preflight"].get("status") != "PASS":
        raise M10BExecutionBlocked("M10 real integration smoke must pass before RNG")

    out.mkdir(parents=True, exist_ok=False)
    config_hash = _sha256_file(approved_path)
    _atomic_json(out / "approved_run_config_snapshot.json", approved, exclusive=True)
    _atomic_json(out / "approved_run_config.sha256", {"sha256": config_hash}, exclusive=True)
    _atomic_json(
        out / "manifest.json",
        {
            "schema_version": SCHEMA,
            "experiment_id": STUDY_ID,
            "approved_config_sha256": config_hash,
            "m10a_draft_sha256": EXPECTED_DRAFT_SHA256,
            "accepted_decision_id": "ADR-016",
            "accepted_decision_fingerprint": EXPECTED_DECISION_SHA256,
            "runtime_source_fingerprint": approved["runtime_provenance"]["source_file_manifest"],
            "planned_run_ids": [row["run_id"] for row in approved["run_manifest"]["runs"]],
            "seed_provenance": approved["run_manifest"],
            "real_integration_smoke": approved["preflight"],
            "other_partition_executed": False,
        },
        exclusive=True,
    )
    conditional_module = __import__(
        "hf_tcm.receiver.reconstruction_conditional_decode",
        fromlist=["decode_reconstruction_viterbi"],
    )
    original_decoder = conditional_module.decode_reconstruction_viterbi
    decoder_calls = 0

    def counted_decoder(*args: Any, **kwargs: Any) -> Any:
        nonlocal decoder_calls
        decoder_calls += 1
        return original_decoder(*args, **kwargs)

    conditional_module.decode_reconstruction_viterbi = counted_decoder
    start = time.perf_counter()
    completed = 0
    generation_failures = 0
    numerical_failures = 0
    rss_peak: int | None = None
    rss_unverified = False
    stop_reason = "all_planned_runs_completed"
    try:
        for planned in approved["run_manifest"]["runs"]:
            elapsed = time.perf_counter() - start
            if elapsed >= WALL_CLOCK_BUDGET_SECONDS:
                stop_reason = "wall_clock_budget_reached"
                break
            rss = _process_rss_windows(os.getpid())
            if rss is None:
                rss_unverified = True
            else:
                rss_peak = max(rss_peak or 0, int(rss))
                if rss >= RSS_MONITORING_BUDGET_BYTES:
                    stop_reason = "rss_monitoring_budget_reached"
                    break
            path = _checkpoint_path(out, planned["run_id"])
            if path.exists():
                raise M10BExecutionBlocked("M10 checkpoint already exists; no resume")
            before = decoder_calls
            try:
                checkpoint = _run_checkpoint(
                    planned=planned,
                    draft=draft,
                    approved=approved,
                    receiver_config=receiver_config,
                    clocks=clocks,
                    decoder_counter=lambda: decoder_calls,
                    config_hash=config_hash,
                )
            except Exception as exc:
                generation_failures += 1
                checkpoint = {
                    "schema_version": SCHEMA,
                    "run_id": planned["run_id"],
                    "run_index": planned["run_index"],
                    "status": "received_generation_failure",
                    "approved_config_sha256": config_hash,
                    "runtime_source_fingerprint_sha256": approved["runtime_provenance"][
                        "runtime_source_fingerprint_sha256"
                    ],
                    "seed_provenance": planned["streams"],
                    "decoder_invocations": decoder_calls - before,
                    "failure": {"exception_type": type(exc).__name__, "detail": str(exc)},
                }
            calls_run = decoder_calls - before
            checkpoint["decoder_invocations"] = calls_run
            if checkpoint.get("status") != "complete":
                numerical_failures += sum(
                    policy.get("status") != "complete_valid_output"
                    for profile in checkpoint.get("profiles", [])
                    for policy in profile.get("policies", [])
                )
            _atomic_json(path, checkpoint, exclusive=True)
            completed += 1
    finally:
        conditional_module.decode_reconstruction_viterbi = original_decoder
    evaluation_elapsed = time.perf_counter() - start

    try:
        verification = independent_verify(out, approved, draft)
    except Exception as exc:
        verification = {
            "status": "M10_VERIFICATION_FAILED",
            "error": {"exception_type": type(exc).__name__, "detail": str(exc)},
            "completed_runs": completed,
        }
        status = "M10_VERIFICATION_FAILED"
    else:
        status = verification.get("status", "M10_VERIFICATION_FAILED")
    if verification.get("status") == "M10_EVALUATION_COMPLETE_VERIFIED":
        bootstrap_seed = int(approved["run_manifest"]["bootstrap"]["derived_seed"])
        bootstrap_start = time.perf_counter()
        summary = summarize_m10b_checkpoints(
            verification["paired_run_counts"], bootstrap_seed=bootstrap_seed
        )
        summary["bootstrap_wall_clock_seconds"] = time.perf_counter() - bootstrap_start
        status = "M10_EVALUATION_COMPLETE_VERIFIED"
    else:
        summary = None
        if status != "M10_VERIFICATION_FAILED":
            status = "M10_INCOMPLETE_OR_BLOCKED"
    history_after = _historical_baseline()
    if history_after != baseline_before:
        status = "M10_VERIFICATION_FAILED"
        verification["status"] = status
        verification["historical_integrity_match"] = False
    else:
        verification["historical_integrity_match"] = True
    expected_calls = 600
    if decoder_calls != expected_calls and status == "M10_EVALUATION_COMPLETE_VERIFIED":
        status = "M10_VERIFICATION_FAILED"
        verification["status"] = status
        verification["decoder_call_counter_match"] = False
    else:
        verification["decoder_call_counter_match"] = decoder_calls == expected_calls
    final_summary = {
        "schema_version": SCHEMA,
        "status": status,
        "classification": "controlled variable-gain evaluation of two fixed policies; not physical HF performance and not paper-exact",
        "approved_config_sha256": config_hash,
        "m10a_draft_sha256": EXPECTED_DRAFT_SHA256,
        "accepted_decision_id": "ADR-016",
        "accepted_decision_fingerprint": EXPECTED_DECISION_SHA256,
        "runtime_source_fingerprint_sha256": approved["runtime_provenance"][
            "runtime_source_fingerprint_sha256"
        ],
        "planned_run_clusters": 100,
        "completed_run_clusters": completed,
        "received_profile_buffers": verification.get("profile_received_buffer_count", 0),
        "policy_records": verification.get("policy_record_count", 0),
        "decoder_invocations": decoder_calls,
        "decoder_invocations_expected": 600,
        "generation_failures": generation_failures,
        "numerical_or_decoder_failure_count": numerical_failures,
        "independent_verification": {
            key: value for key, value in verification.items() if key != "paired_run_counts"
        },
        "statistics": summary,
        "resource": {
            "evaluation_wall_clock_seconds": evaluation_elapsed,
            "bootstrap_wall_clock_seconds": None,
            "completed_run_clusters": completed,
            "decoder_invocations": decoder_calls,
            "rss_peak_bytes_observed": rss_peak,
            "rss_status": "RSS_UNVERIFIED"
            if rss_unverified or rss_peak is None
            else "periodic_monitor_observed",
            "wall_clock_budget_seconds": WALL_CLOCK_BUDGET_SECONDS,
            "rss_monitoring_budget_bytes": RSS_MONITORING_BUDGET_BYTES,
            "single_process": True,
            "multiprocessing": False,
            "stop_reason": stop_reason,
        },
        "historical_integrity": {
            "before": baseline_before,
            "after": history_after,
            "unchanged": history_after == baseline_before,
        },
        "other_experiments_or_partitions_executed": False,
    }
    if summary is not None:
        final_summary["resource"]["bootstrap_wall_clock_seconds"] = summary.get(
            "bootstrap_wall_clock_seconds"
        )
    _atomic_json(
        out / "independent_verification.json",
        final_summary["independent_verification"],
        exclusive=True,
    )
    if summary is not None:
        _atomic_json(out / "bootstrap_summary.json", summary["bootstrap"], exclusive=True)
    else:
        _atomic_json(
            out / "bootstrap_summary.json", {"status": "not_computed_incomplete"}, exclusive=True
        )
    _atomic_json(out / "summary.json", final_summary, exclusive=True)
    _atomic_json(out / "integrity_manifest.json", _output_hashes(out), exclusive=True)
    integrity_match = json.loads(
        (out / "integrity_manifest.json").read_text(encoding="utf-8")
    ) == _output_hashes(out)
    if not integrity_match:
        final_summary["status"] = "M10_VERIFICATION_FAILED"
        _atomic_json(out / "summary.json", final_summary)
        _atomic_json(out / "integrity_manifest.json", _output_hashes(out))
        status = "M10_VERIFICATION_FAILED"
    return final_summary


def guard_m10b_execution(
    value: object,
    *,
    accepted_decision: Mapping[str, Any] | None,
    callbacks: Mapping[str, Callable[[], object]],
    executor: Callable[[], object],
) -> object:
    """Require an exact approved snapshot before running any side effects."""
    if not isinstance(value, Mapping):
        raise M10BExecutionBlocked("M10b execution blocked: config object absent")
    if (
        value.get("design_status") != "approved_evaluation"
        or value.get("execution_authorized") is not True
        or value.get("execution_scope") != EXPECTED_APPROVED_SCOPE
    ):
        raise M10BExecutionBlocked("M10b execution blocked: approved scope missing")
    if accepted_decision is None or accepted_decision.get("decision_id") != "ADR-016":
        raise M10BExecutionBlocked("M10b execution blocked: accepted ADR-016 required")
    if any(name not in callbacks or not callable(callbacks[name]) for name in ("rng", "receiver")):
        raise M10BExecutionBlocked("M10b RNG/receiver guard callbacks are required")
    return executor()
