"""Scientific Workspace adapter for measured discrete-energy studies.

This module only binds GUI configuration and persistence to the established
REPRO energy trial and statistics APIs. It does not implement receiver math.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

from hf_tcm.repro.energy_experiment import EnergyTrialSpec, run_energy_trial
from hf_tcm.repro.energy_gain import estimate_energy_gain_db
from hf_tcm.repro.energy_statistics import analyze_energy_records

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_CHANNELS = {
    "identity",
    "awgn",
    "static_single_path",
    "static_multipath",
    "rician_ar1_multipath",
}


def calculate_single_run_energy_metrics(
    tx_samples: np.ndarray,
    *,
    information_bit_count: int,
    amplitude: float,
    noise_variance: float,
) -> dict[str, Any]:
    """Calculate energy from actual Tx samples under the project convention."""
    samples = np.asarray(tx_samples, dtype=np.complex128)
    if samples.ndim != 1 or samples.size == 0 or samples.size % 8:
        raise ValueError("transmitter trace must contain complete eight samples per symbol")
    if type(information_bit_count) is not int or information_bit_count <= 0:
        raise ValueError("information_bit_count must be a positive integer")
    if samples.size // 8 * 2 != information_bit_count:
        raise ValueError("payload count must be two information bits per symbol")
    if not math.isfinite(amplitude) or amplitude <= 0:
        raise ValueError("amplitude must be positive and finite")
    if not math.isfinite(noise_variance) or noise_variance < 0:
        raise ValueError("noise_variance must be finite and non-negative")
    energy = float(np.vdot(samples, samples).real)
    eb = energy / information_bit_count
    expected_eb = 4.0 * amplitude**2
    valid = bool(np.isclose(eb, expected_eb, rtol=1e-12, atol=1e-12))
    return {
        "tx_energy_discrete": energy,
        "energy_per_information_bit_discrete": eb,
        "amplitude": float(amplitude),
        "noise_variance_complex_per_sample": float(noise_variance),
        "gamma_b_d_db": float(10 * np.log10(eb / noise_variance)) if noise_variance > 0 else None,
        "information_bits_per_symbol": 2,
        "sample_count": int(samples.size),
        "symbol_count": int(samples.size // 8),
        "energy_relation_expected_4A2": expected_eb,
        "energy_relation_valid": valid,
        "energy_axis_unit": "discrete normalized signal energy per information bit",
        "noise_axis_unit": "complex sample-domain variance per sample",
    }


@dataclass(frozen=True, slots=True)
class EnergyStudyConfig:
    """Validated statistical-study settings captured from Scientific Workspace."""

    experiment_id: str
    frame_symbols: int
    gamma_grid_db: tuple[float, ...]
    trials_per_point: int
    root_seed: int
    target_ber: float
    time_budget_seconds: float
    sweep: Literal["amplitude", "noise"]
    receiver_arms: tuple[str, ...]
    channel_profile: str
    noise_variance: float
    amplitude: float
    delays_samples: tuple[int, ...] = (0,)
    path_coefficients: tuple[tuple[float, float], ...] = ((1.0, 0.0),)
    path_powers: tuple[float, ...] = (1.0,)
    rician_k_factors: tuple[float, ...] = (4.0,)
    los_phases_rad: tuple[float, ...] = (0.0,)
    fading_correlation: float = 0.98
    bootstrap_replicates: int = 500

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.experiment_id):
            raise ValueError("experiment_id must be a safe identifier")
        if type(self.frame_symbols) is not int or not 1 <= self.frame_symbols <= 20_000:
            raise ValueError("frame_symbols must be in [1, 20000]")
        if not self.gamma_grid_db or len(self.gamma_grid_db) > 21:
            raise ValueError("energy grid must contain 1 to 21 points")
        if any(not math.isfinite(value) for value in self.gamma_grid_db):
            raise ValueError("energy grid values must be finite")
        if len(set(self.gamma_grid_db)) != len(self.gamma_grid_db):
            raise ValueError("energy grid values must be unique")
        if type(self.trials_per_point) is not int or not 1 <= self.trials_per_point <= 1000:
            raise ValueError("trials_per_point must be in [1, 1000]")
        if type(self.root_seed) is not int or not 0 <= self.root_seed < 2**64:
            raise ValueError("root_seed must be an unsigned 64-bit integer")
        if not math.isfinite(self.target_ber) or not 0 < self.target_ber < 1:
            raise ValueError("target_ber must lie strictly between zero and one")
        if not math.isfinite(self.time_budget_seconds) or not 1 <= self.time_budget_seconds <= 7200:
            raise ValueError("time budget must be in [1, 7200] seconds")
        if self.sweep not in {"amplitude", "noise"}:
            raise ValueError("sweep must be amplitude or noise")
        if not math.isfinite(self.noise_variance) or self.noise_variance < 0:
            raise ValueError("noise variance must be finite and non-negative")
        if not math.isfinite(self.amplitude) or self.amplitude <= 0:
            raise ValueError("amplitude must be positive and finite")
        if self.sweep == "amplitude" and self.noise_variance <= 0:
            raise ValueError("amplitude sweep requires positive fixed noise variance")
        if self.channel_profile not in _CHANNELS:
            raise ValueError("unsupported Scientific Workspace channel profile")
        if "joint" not in self.receiver_arms or not set(self.receiver_arms) <= {
            "joint",
            "b0",
            "b1",
        }:
            raise ValueError("receiver_arms must include joint and use only joint/b0/b1")
        if not set(self.receiver_arms) & {"b0", "b1"} or len(set(self.receiver_arms)) != len(
            self.receiver_arms
        ):
            raise ValueError("select at least one separate receiver exactly once")
        if self.channel_profile == "rician_ar1_multipath" and "b1" in self.receiver_arms:
            raise ValueError("B1 is unavailable for Rician AR(1)")
        count = len(self.delays_samples)
        if not count or any(type(delay) is not int or delay < 0 for delay in self.delays_samples):
            raise ValueError("path delays must be non-negative integer samples")
        used_path_values = (
            (self.path_powers, self.rician_k_factors, self.los_phases_rad)
            if self.channel_profile == "rician_ar1_multipath"
            else (
                self.path_coefficients,
                self.path_powers,
                self.rician_k_factors,
                self.los_phases_rad,
            )
        )
        if any(len(values) != count for values in used_path_values):
            raise ValueError("path settings must match the number of delays")
        if self.channel_profile in {"identity", "awgn"} and self.delays_samples != (0,):
            raise ValueError("Identity and AWGN require one zero-delay path")
        if self.channel_profile == "static_single_path" and count != 1:
            raise ValueError("static single-path requires one path")
        if self.channel_profile == "static_multipath" and count < 2:
            raise ValueError("static multipath requires at least two paths")
        if self.channel_profile == "rician_ar1_multipath":
            if any(not math.isfinite(value) or value <= 0 for value in self.path_powers):
                raise ValueError("path powers must be positive and finite")
            if any(not math.isfinite(value) or value < 0 for value in self.rician_k_factors):
                raise ValueError("Rician K factors must be non-negative and finite")
            if not 0 <= self.fading_correlation < 1:
                raise ValueError("fading correlation must be in [0, 1)")
        else:
            for pair in self.path_coefficients:
                if len(pair) != 2 or not all(math.isfinite(value) for value in pair):
                    raise ValueError("static path coefficients must be finite I/Q pairs")
                if complex(*pair) == 0j:
                    raise ValueError("static path coefficients must be nonzero")
        if type(self.bootstrap_replicates) is not int or self.bootstrap_replicates < 100:
            raise ValueError("bootstrap_replicates must be at least 100")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EnergyStudyConfig:
        if not isinstance(raw, dict):
            raise ValueError("energy-study configuration must be an object")
        extra = set(raw) - set(cls.__dataclass_fields__)
        if extra:
            raise ValueError(f"unexpected energy-study field: {sorted(extra)[0]}")
        data = dict(raw)
        for name in (
            "gamma_grid_db",
            "receiver_arms",
            "delays_samples",
            "path_powers",
            "rician_k_factors",
            "los_phases_rad",
        ):
            if name in data:
                data[name] = tuple(data[name])
        if "path_coefficients" in data:
            data["path_coefficients"] = tuple(tuple(pair) for pair in data["path_coefficients"])
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid energy-study configuration: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key, value in result.items():
            if isinstance(value, tuple):
                result[key] = [list(item) if isinstance(item, tuple) else item for item in value]
        return result

    @property
    def scenario(self) -> str:
        if self.channel_profile == "rician_ar1_multipath":
            return "rician"
        return "static" if self.channel_profile.startswith("static_") else "awgn"

    @property
    def channel_settings(self) -> dict[str, Any]:
        return {
            "channel_profile": self.channel_profile,
            "delays_samples": self.delays_samples,
            "path_coefficients": self.path_coefficients,
            "path_powers": self.path_powers,
            "rician_k_factors": self.rician_k_factors,
            "los_phases_rad": self.los_phases_rad,
            "fading_correlation": self.fading_correlation,
        }


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".pending")
    temporary.write_bytes(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    )
    try:
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                # Windows scanners and cloud-sync clients can briefly hold the
                # destination while a checkpoint is atomically replaced.
                time.sleep(0.05 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def _manifest(root: Path) -> dict[str, Any]:
    files = {}
    for name in ("configuration.json", "study.json", "progress.json", "summary.json"):
        path = root / name
        if path.is_file():
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"schema_version": "gui-energy-study-v1", "files": files}


def _physical_energy_gain_guard(target_ber: float) -> dict[str, str]:
    try:
        estimate_energy_gain_db(
            [],
            [],
            target_ber=target_ber,
            x_axis_unit="gamma_b_d_db",
            physical_snr_defined=False,
        )
    except ValueError as exc:
        return {"status": "NOT_ESTIMABLE", "reason": str(exc)}
    raise RuntimeError("sample-domain energy guard unexpectedly accepted a physical gain")


def run_energy_study(
    config: EnergyStudyConfig,
    output_root: str | Path,
    *,
    stop_event: threading.Event | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run a bounded, resumable series of paired energy trials."""
    if not isinstance(config, EnergyStudyConfig):
        raise TypeError("config must be EnergyStudyConfig")
    root = Path(output_root).resolve() / config.experiment_id
    root.mkdir(parents=True, exist_ok=True)
    configuration = config.to_dict()
    trial_design = {
        key: value
        for key, value in configuration.items()
        if key not in {"target_ber", "time_budget_seconds", "bootstrap_replicates"}
    }
    config_hash = hashlib.sha256(_canonical(trial_design)).hexdigest()
    stored_path = root / "study.json"
    if stored_path.exists():
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        if stored.get("configuration_sha256") != config_hash:
            raise ValueError("saved study configuration differs; use a new identifier")
    else:
        _atomic_json(
            stored_path,
            {"experiment_id": config.experiment_id, "configuration_sha256": config_hash},
        )
    _atomic_json(root / "configuration.json", configuration)

    started = time.monotonic()
    planned = len(config.gamma_grid_db) * config.trials_per_point
    completed_records: list[dict[str, Any]] = []
    status = "completed"
    stop_reason = None
    for point_index, gamma in enumerate(config.gamma_grid_db):
        for trial_index in range(config.trials_per_point):
            if stop_event is not None and stop_event.is_set():
                status, stop_reason = "incomplete", "stopped_after_completed_trial"
                break
            if time.monotonic() - started >= config.time_budget_seconds:
                status, stop_reason = "incomplete", "time_budget_reached"
                break
            spec = EnergyTrialSpec(
                phase="gui",
                scenario=config.scenario,
                sweep=config.sweep,
                gamma_db=float(gamma),
                point_index=point_index,
                trial_index=trial_index,
                frame_symbols=config.frame_symbols,
                root_seed=config.root_seed,
                noise_reference_variance=(
                    config.noise_variance if config.sweep == "amplitude" else None
                ),
                amplitude_reference=(config.amplitude if config.sweep == "noise" else None),
                channel_settings=config.channel_settings,
                receiver_arms=config.receiver_arms,
            )
            record = run_energy_trial(spec, root)
            completed_records.append(record)
            update = {
                "completed_trials": len(completed_records),
                "planned_trials": planned,
                "point_index": point_index,
                "trial_index": trial_index,
                "status": "running",
            }
            _atomic_json(root / "progress.json", update)
            if progress_callback is not None:
                progress_callback(update)
        if status != "completed":
            break

    analyses: dict[str, Any] = {}
    if completed_records:
        for index, arm in enumerate(config.receiver_arms):
            if arm == "joint":
                continue
            analyses[arm] = analyze_energy_records(
                completed_records,
                config.target_ber,
                arm=arm,
                replicates=config.bootstrap_replicates,
                seed=(config.root_seed + 10_000 + index) % 2**64,
            )
    summary = {
        "schema_version": "gui-energy-study-result-v1",
        "experiment_id": config.experiment_id,
        "configuration_sha256": config_hash,
        "configuration": configuration,
        "physical_energy_gain": _physical_energy_gain_guard(config.target_ber),
        "status": status,
        "stop_reason": stop_reason,
        "planned_trials": planned,
        "completed_trials": len(completed_records),
        "elapsed_seconds": time.monotonic() - started,
        "exploratory": config.trials_per_point < 20,
        "target_ber": config.target_ber,
        "sweep": config.sweep,
        "channel_profile": config.channel_profile,
        "receiver_arms": list(config.receiver_arms),
        "records": completed_records,
        "analyses": analyses,
        "energy_gain_status_uk": (
            "Noise sweep визначає пороги за рівнем шуму; необхідну передану енергію з нього не оцінюємо."
            if config.sweep == "noise"
            else "Недостатньо незалежних кадрів для статистичної оцінки енергетичного виграшу; серія розвідувальна."
            if config.trials_per_point < 20
            else "Модельний дискретний виграш має 95% парний довірчий інтервал."
            if any(
                result.get("gain_db") is not None
                and result.get("bootstrap", {}).get("confidence_interval_db") is not None
                for result in analyses.values()
            )
            else "Є лише точкова модельна оцінка; валідного 95% інтервалу недостатньо."
            if any(result.get("gain_db") is not None for result in analyses.values())
            else "Недостатньо даних для визначення енергетичного виграшу."
        ),
    }
    _atomic_json(
        root / "progress.json",
        {
            "completed_trials": len(completed_records),
            "planned_trials": planned,
            "status": status,
            "stop_reason": stop_reason,
        },
    )
    _atomic_json(root / "summary.json", summary)
    _atomic_json(root / "manifest.json", _manifest(root))
    if progress_callback is not None:
        progress_callback(
            {
                "completed_trials": len(completed_records),
                "planned_trials": planned,
                "status": status,
                "experiment_id": config.experiment_id,
            }
        )
    return summary


def load_energy_study(study_dir: str | Path) -> dict[str, Any]:
    root = Path(study_dir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "gui-energy-study-v1":
        raise ValueError("unsupported energy-study manifest")
    for name, expected in manifest.get("files", {}).items():
        candidate = (root / name).resolve()
        if (
            root not in candidate.parents
            or hashlib.sha256(candidate.read_bytes()).hexdigest() != expected
        ):
            raise ValueError(f"energy-study integrity check failed: {name}")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    study = json.loads((root / "study.json").read_text(encoding="utf-8"))
    if summary.get("configuration_sha256") != study.get("configuration_sha256"):
        raise ValueError("energy-study configuration hash mismatch")
    configuration = json.loads((root / "configuration.json").read_text(encoding="utf-8"))
    try:
        parsed = EnergyStudyConfig.from_dict(configuration)
    except (TypeError, ValueError) as exc:
        raise ValueError("saved energy-study configuration is invalid") from exc
    trial_design = {
        key: value
        for key, value in configuration.items()
        if key not in {"target_ber", "time_budget_seconds", "bootstrap_replicates"}
    }
    if hashlib.sha256(_canonical(trial_design)).hexdigest() != study.get("configuration_sha256"):
        raise ValueError("energy-study frozen trial design hash mismatch")
    for row in summary.get("records", []):
        if not (
            row.get("observation_sha256")
            and all(
                value == row["observation_sha256"]
                for value in row.get("receiver_observation_hashes", {}).values()
            )
        ):
            raise ValueError("energy-study record contains unpaired receiver observations")
        trial_root = (
            root
            / str(row["phase"])
            / str(row["scenario"])
            / str(row["sweep"])
            / f"p{int(row['point_index']):02d}"
            / f"t{int(row['trial_index']):04d}"
        ).resolve()
        if root not in trial_root.parents:
            raise ValueError("energy-study trial path escapes its result directory")
        trial_manifest = json.loads((trial_root / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in trial_manifest["files"].items():
            candidate = (trial_root / name).resolve()
            if (
                trial_root not in candidate.parents
                or hashlib.sha256(candidate.read_bytes()).hexdigest() != expected
            ):
                raise ValueError(f"energy-study trial integrity check failed: {name}")
        record_on_disk = json.loads((trial_root / "record.json").read_text(encoding="utf-8"))
        if record_on_disk.get("observation_sha256") != row.get("observation_sha256"):
            raise ValueError("energy-study summary does not match its immutable trial record")
    summary["configuration"] = parsed.to_dict()
    return summary


def list_energy_studies(output_root: str | Path) -> list[dict[str, Any]]:
    root = Path(output_root)
    if not root.is_dir():
        return []
    studies = []
    for candidate in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if candidate.is_dir() and (candidate / "manifest.json").is_file():
            try:
                studies.append(load_energy_study(candidate))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
    return studies[:100]
