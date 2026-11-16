"""Independently recount the frozen SCIENTIFIC-EXP-03A pilot checkpoints."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.metric_experiment import load_metric_study, verify_metric_study

PILOT_IDS = (
    "exp03a-pilot-awgn-direct-v1",
    "exp03a-pilot-awgn-pilot-v1",
    "exp03a-pilot-static-d3-v1",
    "exp03a-pilot-rician-ar1-v1",
    "exp03a-range2-awgn-direct-v1",
    "exp03a-range2-awgn-pilot-v1",
    "exp03a-range2-static-d3-v1",
    "exp03a-range2-rician-ar1-v1",
    "exp03a-range2-rician-pilot8-v1",
)
ROOT = Path("outputs/scientific-exp03a/metric-studies")


def _array_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rebuild_observation_hash(received: np.ndarray, configuration: dict) -> str:
    channel = configuration["channel_config"]
    count = len(received)
    observation = ReceiverObservation(
        received_samples=np.asarray(received, dtype=np.complex128),
        absolute_sample_index=np.arange(count, dtype=np.int64),
        sample_symbol_index=np.arange(count, dtype=np.int64) // 8,
        sample_local_index=np.arange(count, dtype=np.int64) % 8,
        samples_per_symbol=8,
        profile_id=channel["profile_id"],
        model_id="repro03_discrete_complex_baseband_v1",
        sampling_convention="discrete_complex_baseband_absolute_sample_index",
        boundary_policy=channel["boundary_policy"],
        output_length_policy=channel["output_length_policy"],
        noise_model=channel["noise_model"],
        noise_complex_variance=float(channel["noise_complex_variance"]),
    )
    return observation.sha256


def validate_one(experiment_id: str) -> dict:
    folder = ROOT / experiment_id
    manifest = verify_metric_study(folder)
    summary = load_metric_study(folder)
    config = summary["configuration"]
    if config["phase"] != "range_finding" or summary["confirmatory_series_executed"]:
        raise ValueError(f"{experiment_id}: pilot was mislabeled as confirmatory")
    output = {
        "experiment_id": experiment_id,
        "manifest_file_count": len(manifest["files"]),
        "completed": summary["completed_trials"],
        "planned": summary["planned_trials"],
        "paired_hashes_valid": True,
        "independent_recount": True,
        "observation_hashes_rebuilt": 0,
        "energy_recount": True,
        "curve_points": [],
        "mean_equalizer_diagnostics": {},
        "pilot_overhead_symbols_per_frame": None,
    }
    by_point: dict[int, dict[str, int]] = {}
    diagnostics: list[dict] = []
    conditional_noise_variances: list[float] = []
    equalized_residual_correlations: list[float] = []
    euclidean_decode_seconds: list[float] = []
    hamming_decode_seconds: list[float] = []
    for record_path in sorted((folder / "trials").glob("p*-t*.json")):
        row = json.loads(record_path.read_text(encoding="utf-8"))
        array_path = record_path.parent / row["array_file"]
        if _array_sha256(array_path) != row["array_file_sha256"]:
            raise ValueError(f"{experiment_id}: array checksum mismatch")
        with np.load(array_path, allow_pickle=False) as arrays:
            reference = arrays["reference_payload_pairs"].astype(np.int8)
            payload_mask = arrays["payload_mask"].astype(bool)
            tx = arrays["transmitted_samples"].astype(np.complex128)
            rx = arrays["received_samples"].astype(np.complex128)
            equalized = arrays["equalized_symbols"].astype(np.complex128)
            tx_by_symbol = tx.reshape(int(row["frame_symbols_total"]), 8)
            if not np.allclose(tx_by_symbol, tx_by_symbol[:, :1], rtol=0, atol=1e-14):
                raise ValueError(f"{experiment_id}: Tx samples are not the configured ZOH waveform")
            amplitude = float(row["amplitude"])
            if not np.allclose(np.abs(tx_by_symbol[:, 0]), amplitude, rtol=1e-12, atol=1e-14):
                raise ValueError(f"{experiment_id}: transmitted amplitude differs from the record")
            energy = float(np.sum(np.square(np.abs(tx))))
            payload_energy = float(np.sum(np.square(np.abs(tx_by_symbol[payload_mask]))))
            pilot_energy = float(np.sum(np.square(np.abs(tx_by_symbol[~payload_mask]))))
            bits = int(reference.size)
            eb = energy / bits
            gamma = 10.0 * math.log10(eb / float(row["noise_complex_variance"]))
            conditional_variance = arrays["output_noise_variance"].astype(np.float64)
            conditional_noise_variances.extend(
                float(value) for value in conditional_variance[np.isfinite(conditional_variance)]
            )
            residual = equalized - tx_by_symbol[:, 0]
            adjacent_payload = payload_mask[:-1] & payload_mask[1:]
            if np.any(adjacent_payload):
                left = residual[:-1][adjacent_payload]
                right = residual[1:][adjacent_payload]
                power = 0.5 * (np.mean(np.abs(left) ** 2) + np.mean(np.abs(right) ** 2))
                if power > 0:
                    equalized_residual_correlations.append(
                        float(abs(np.mean(left * np.conjugate(right)) / power))
                    )
            if not math.isclose(energy, float(row["transmit_energy_discrete"]), rel_tol=1e-12):
                raise ValueError(f"{experiment_id}: transmitted energy recount mismatch")
            if not math.isclose(
                payload_energy, float(row["payload_energy_discrete"]), rel_tol=1e-12
            ):
                raise ValueError(f"{experiment_id}: payload energy recount mismatch")
            if not math.isclose(pilot_energy, float(row["pilot_energy_discrete"]), rel_tol=1e-12):
                raise ValueError(f"{experiment_id}: pilot energy recount mismatch")
            if not math.isclose(eb, float(row["energy_per_payload_bit_discrete"]), rel_tol=1e-12):
                raise ValueError(f"{experiment_id}: Eb,d recount mismatch")
            if not math.isclose(gamma, float(row["gamma_b_discrete_db"]), rel_tol=1e-12):
                raise ValueError(f"{experiment_id}: gamma_b,d recount mismatch")
            if _rebuild_observation_hash(rx, config) != row["observation_sha256"]:
                raise ValueError(f"{experiment_id}: reconstructed ReceiverObservation SHA mismatch")
            output["observation_hashes_rebuilt"] += 1
            if row["observation_sha256"] != row["paired_observation_sha256"]:
                raise ValueError(f"{experiment_id}: paired observation mismatch")
            if row["frontend_output_sha256_euclidean"] != row["frontend_output_sha256_hamming"]:
                raise ValueError(f"{experiment_id}: paired frontend output mismatch")
            point = int(row["point_index"])
            tally = by_point.setdefault(
                point,
                {
                    "trials": 0,
                    "bits": 0,
                    "pairs": 0,
                    "gamma_b_discrete_db": float(row["gamma_b_discrete_db"]),
                    "amplitude": float(row["amplitude"]),
                    "noise_complex_variance": float(row["noise_complex_variance"]),
                    "e_bits": 0,
                    "h_bits": 0,
                    "e_pairs": 0,
                    "h_pairs": 0,
                    "e_frames": 0,
                    "h_frames": 0,
                },
            )
            tally["trials"] += 1
            tally["bits"] += bits
            tally["pairs"] += int(len(reference))
            for arm, decoded_key, prefix in (
                ("euclidean", "decoded_euclidean_pairs", "e"),
                ("hamming", "decoded_hamming_pairs", "h"),
            ):
                decoded = arrays[decoded_key].astype(np.int8)[payload_mask]
                errors = decoded != reference
                bit_errors = int(np.count_nonzero(errors))
                pair_errors = int(np.count_nonzero(np.any(errors, axis=1)))
                if bit_errors != int(row[arm]["bit_errors"]) or pair_errors != int(
                    row[arm]["pair_errors"]
                ):
                    raise ValueError(f"{experiment_id}: independent {arm} BER/SER recount mismatch")
                if not pair_errors <= bit_errors <= 2 * pair_errors:
                    raise ValueError(f"{experiment_id}: inconsistent information-pair/bit errors")
                tally[f"{prefix}_bits"] += bit_errors
                tally[f"{prefix}_pairs"] += pair_errors
                tally[f"{prefix}_frames"] += int(bit_errors > 0)
            output["paired_hashes_valid"] &= (
                row["observation_sha256"] == row["paired_observation_sha256"]
            )
            diagnostics.append(row["diagnostics_evaluator_only"])
        euclidean_decode_seconds.append(float(row["euclidean"]["runtime_seconds"]))
        hamming_decode_seconds.append(float(row["hamming"]["runtime_seconds"]))
        pilot_symbols = int(row["pilot_symbols"])
        if output["pilot_overhead_symbols_per_frame"] is None:
            output["pilot_overhead_symbols_per_frame"] = pilot_symbols
        elif output["pilot_overhead_symbols_per_frame"] != pilot_symbols:
            raise ValueError(f"{experiment_id}: inconsistent pilot overhead across trials")
    for point, counts in sorted(by_point.items()):
        output["curve_points"].append(
            {
                "energy_offset_db": config["energy_grid_db"][point],
                "gamma_b_discrete_db": counts["gamma_b_discrete_db"],
                "amplitude": counts["amplitude"],
                "noise_complex_variance": counts["noise_complex_variance"],
                "trials": counts["trials"],
                "bits": counts["bits"],
                "pairs": counts["pairs"],
                "ber_euclidean": counts["e_bits"] / counts["bits"],
                "ber_hamming": counts["h_bits"] / counts["bits"],
                "ser_pair_euclidean": counts["e_pairs"] / counts["pairs"],
                "ser_pair_hamming": counts["h_pairs"] / counts["pairs"],
                "fer_euclidean": counts["e_frames"] / counts["trials"],
                "fer_hamming": counts["h_frames"] / counts["trials"],
            }
        )
    if summary["completed_trials"] != len(list((folder / "trials").glob("p*-t*.json"))):
        raise ValueError(f"{experiment_id}: trial count does not match the checkpoint summary")
    numeric_diagnostics = (
        "clean_region_residual_isi_rms",
        "composite_gain_within_clean_window_rms_evaluator_only",
        "pilot_composite_gain_rmse_evaluator_only",
        "equalized_signal_residual_rms_evaluator_only",
        "equalizer_output_noise_variance_empirical_evaluator_only",
        "equalizer_output_noise_lag1_correlation_evaluator_only",
        "equalizer_output_noise_variance_conditional_mean_evaluator_only",
        "equalized_symbol_error_lag1_correlation_evaluator_only",
        "payload_gain_age_mean_symbols_evaluator_only",
        "payload_gain_age_max_symbols_evaluator_only",
    )
    for name in numeric_diagnostics:
        values = [
            abs(complex(*row[name]))
            if name.endswith("lag1_correlation_evaluator_only")
            else float(row[name])
            for row in diagnostics
            if row.get(name) is not None
        ]
        output["mean_equalizer_diagnostics"][name] = float(np.mean(values)) if values else None
    output["latest_invocation_runtime_seconds"] = summary["runtime_seconds_this_invocation"]
    output["stored_trial_wall_runtime_available"] = False
    output["mean_decoder_seconds"] = {
        "euclidean": float(np.mean(euclidean_decode_seconds)) if euclidean_decode_seconds else None,
        "hamming": float(np.mean(hamming_decode_seconds)) if hamming_decode_seconds else None,
    }
    output["mean_conditional_equalizer_noise_variance"] = (
        float(np.mean(conditional_noise_variances)) if conditional_noise_variances else None
    )
    output["mean_absolute_equalized_symbol_error_lag1_correlation"] = (
        float(np.mean(equalized_residual_correlations)) if equalized_residual_correlations else None
    )
    output["phase"] = summary["phase"]
    output["frontend_mode"] = config["frontend_mode"]
    output["channel_profile"] = config["channel_config"]["profile_id"]
    output["gain_analysis_status"] = summary["gain_analysis"]["status"]
    output["gain_db"] = summary["gain_analysis"]["gain_db"]
    output["bootstrap_valid_fraction"] = (
        summary["gain_analysis"].get("bootstrap", {}).get("valid_fraction")
    )
    return output


def main() -> int:
    results = [validate_one(experiment_id) for experiment_id in PILOT_IDS]
    destination = Path("outputs/scientific-exp03a/validation/independent_pilot_recount.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "validation": "PASS",
                "studies": len(results),
                "trial_records": sum(row["completed"] for row in results),
                "output": str(destination),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
