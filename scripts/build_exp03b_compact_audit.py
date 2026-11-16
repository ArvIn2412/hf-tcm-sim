from __future__ import annotations

import csv
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL_ZIP = ROOT / "HF_TCM_SIM_SCIENTIFIC_EXP_03B_FULL_AUDIT.zip"
OUT_ZIP = ROOT / "HF_TCM_SIM_EXP03B_CHATGPT_AUDIT_COMPACT.zip"
STAGE = ROOT / "tmp/exp03b_compact_audit_stage_20261113"
TOP = "HF_TCM_SIM_EXP03B_CHATGPT_AUDIT"
PROTOCOL_SHA = "d553e65fdad020f4887d252bb29bd88311b84b596bbba1e14fd4a806e71068c6"
SAMPLE_SEED = 20261113
MAX_BYTES = 480_000_000


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cell(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: cell(v) for k, v in row.items()} for row in rows)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def source_manifest() -> tuple[dict[str, dict], dict]:
    if not FULL_ZIP.is_file() or not zipfile.is_zipfile(FULL_ZIP):
        raise RuntimeError("Full SCIENTIFIC-EXP-03B ZIP is missing or unreadable")
    with zipfile.ZipFile(FULL_ZIP) as archive:
        embedded = json.loads(archive.read("AUDIT_MANIFEST.json"))
        info = {
            "path": FULL_ZIP.name,
            "size_bytes": FULL_ZIP.stat().st_size,
            "members_including_manifest": len(archive.namelist()),
            "manifest_records": len(embedded["files"]),
            "protocol_sha256": embedded.get("protocol_sha256"),
            "raw_confirmatory_data_included": embedded.get("raw_confirmatory_data_included"),
            "zip_directory_and_manifest_readable": True,
            "full_crc_recheck_this_turn": "NOT_PERFORMED; previous full-package verification is cited by project artifacts; selected members are rehashed",
        }
    return {x["path"]: x for x in embedded["files"]}, info


def load_checkpoint(study: Path) -> list[dict]:
    entries = [
        json.loads(line)
        for line in (study / "checkpoint.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    return sorted(entries, key=lambda x: x["record_path"])


def verified_source_entry(
    manifest: dict[str, dict], path: str, sha: str, size: int | None = None
) -> None:
    item = manifest.get(path)
    if item is None or item["sha256"] != sha or (size is not None and item["size_bytes"] != size):
        raise ValueError(f"Source full-archive manifest mismatch: {path}")


def parse_metric(study: Path, full_manifest: dict[str, dict]):
    rows, pairing, groups = [], [], defaultdict(dict)
    prefix = "outputs/scientific_exp03b/metric/confirmatory/" + study.name + "/"
    entries = load_checkpoint(study)
    if len(entries) != int(read_json(study / "manifest.json")["completed_trials"]):
        raise ValueError(f"Checkpoint count mismatch: {study}")
    for entry in entries:
        record_path, array_path = study / entry["record_path"], study / entry["array_path"]
        raw = record_path.read_bytes()
        digest = sha_bytes(raw)
        if digest != entry["record_sha256"]:
            raise ValueError(f"Trial JSON SHA mismatch: {record_path}")
        rec = json.loads(raw)
        src_rec, src_arr = prefix + entry["record_path"], prefix + entry["array_path"]
        verified_source_entry(full_manifest, src_rec, digest, len(raw))
        verified_source_entry(full_manifest, src_arr, entry["array_sha256"])
        if rec["protocol_sha256"] != PROTOCOL_SHA or rec["stage"] != "confirmatory":
            raise ValueError(f"Wrong protocol/stage: {record_path}")
        if rec["observation_sha256"] != rec["paired_observation_sha256"]:
            raise ValueError(f"Observation hashes differ: {record_path}")
        e, h = rec["euclidean"], rec["hamming"]
        frontend_equal = (
            rec["frontend_output_sha256_euclidean"] == rec["frontend_output_sha256_hamming"]
        )
        row = {
            "trial_id": rec["trial_id"],
            "block": "A_metric_isolation",
            "scenario": rec["scenario_key"],
            "sweep": rec["sweep"],
            "point_index": rec["point_index"],
            "trial_index": rec["trial_index"],
            "root_seed": rec["root_seed"],
            "derived_seeds_json": rec.get("derived_seeds"),
            "protocol_sha256": rec["protocol_sha256"],
            "frame_symbols_total": rec["frame_symbols_total"],
            "payload_symbols": rec["payload_symbols"],
            "pilot_symbols": rec["pilot_symbols"],
            "payload_information_bits": rec["payload_information_bits"],
            "amplitude": rec["amplitude"],
            "noise_complex_variance": rec["noise_complex_variance"],
            "transmit_energy_discrete": rec["transmit_energy_discrete"],
            "payload_energy_discrete": rec["payload_energy_discrete"],
            "pilot_energy_discrete": rec["pilot_energy_discrete"],
            "energy_per_payload_bit_discrete": rec["energy_per_payload_bit_discrete"],
            "gamma_b_discrete_db": rec["gamma_b_discrete_db"],
            "euclidean_bit_errors": e["bit_errors"],
            "euclidean_bits": e["bits"],
            "euclidean_ber": e["ber"],
            "euclidean_pair_errors": e["pair_errors"],
            "euclidean_pairs": e["pairs"],
            "euclidean_ser_information_pairs": e["ser_information_pairs"],
            "euclidean_fer": e["fer"],
            "euclidean_runtime_seconds": e["runtime_seconds"],
            "hamming_bit_errors": h["bit_errors"],
            "hamming_bits": h["bits"],
            "hamming_ber": h["ber"],
            "hamming_pair_errors": h["pair_errors"],
            "hamming_pairs": h["pairs"],
            "hamming_ser_information_pairs": h["ser_information_pairs"],
            "hamming_fer": h["fer"],
            "hamming_runtime_seconds": h["runtime_seconds"],
            "observation_sha256": rec["observation_sha256"],
            "paired_observation_sha256": rec["paired_observation_sha256"],
            "frontend_output_sha256_euclidean": rec["frontend_output_sha256_euclidean"],
            "frontend_output_sha256_hamming": rec["frontend_output_sha256_hamming"],
            "pilot_schedule_sha256": rec["pilot_schedule_sha256"],
            "traceback_depth_transitions": rec["traceback_depth_transitions"],
            "raw_wall_elapsed_seconds": rec.get("raw_wall_elapsed_seconds"),
            "process_cpu_seconds": rec.get("process_cpu_seconds"),
            "record_sha256": digest,
            "array_sha256": entry["array_sha256"],
            "source_record_path": src_rec,
            "source_array_path": src_arr,
        }
        rows.append(row)
        pairing.append(
            {
                "trial_id": rec["trial_id"],
                "block": "A_metric_isolation",
                "scenario": rec["scenario_key"],
                "sweep": rec["sweep"],
                "point_index": rec["point_index"],
                "observation_hash": rec["observation_sha256"],
                "paired_observation_hash": rec["paired_observation_sha256"],
                "observation_hashes_equal": rec["observation_sha256"]
                == rec["paired_observation_sha256"],
                "frontend_hash_euclidean": rec["frontend_output_sha256_euclidean"],
                "frontend_hash_hamming": rec["frontend_output_sha256_hamming"],
                "frontend_hashes_equal": frontend_equal,
                "record_sha256": digest,
                "array_sha256": entry["array_sha256"],
            }
        )
        signature = f"E_error={int(e['bit_errors'] > 0)};H_error={int(h['bit_errors'] > 0)}"
        key = (rec["scenario_key"] + "/" + rec["sweep"], int(rec["point_index"]))
        rank = hashlib.sha256(f"{SAMPLE_SEED}|{rec['trial_id']}".encode()).hexdigest()
        if signature not in groups[key] or rank < groups[key][signature]["rank"]:
            groups[key][signature] = {
                "rank": rank,
                "entry": entry,
                "record": rec,
                "record_path": record_path,
                "array_path": array_path,
                "source_record": src_rec,
                "source_array": src_arr,
            }
    return rows, pairing, groups


def parse_system(study: Path, full_manifest: dict[str, dict]):
    rows, pairing, groups = [], [], defaultdict(dict)
    prefix = "outputs/scientific_exp03b/system/confirmatory/" + study.name + "/"
    entries = load_checkpoint(study)
    if len(entries) != int(read_json(study / "manifest.json")["completed_trials"]):
        raise ValueError(f"Checkpoint count mismatch: {study}")
    for entry in entries:
        record_path, array_path = study / entry["record_path"], study / entry["array_path"]
        raw = record_path.read_bytes()
        digest = sha_bytes(raw)
        if digest != entry["record_sha256"]:
            raise ValueError(f"Trial JSON SHA mismatch: {record_path}")
        wrapper = json.loads(raw)
        rec = wrapper["record"]
        src_rec, src_arr = prefix + entry["record_path"], prefix + entry["array_path"]
        verified_source_entry(full_manifest, src_rec, digest, len(raw))
        verified_source_entry(full_manifest, src_arr, entry["array_sha256"])
        if (
            wrapper["protocol_sha256"] != PROTOCOL_SHA
            or wrapper["stage"] != "confirmatory"
            or rec["status"] != "completed"
        ):
            raise ValueError(f"Wrong system protocol/stage/status: {record_path}")
        arms = rec["receiver_arms"]
        hashes = rec["receiver_observation_hashes"]
        paired = set(hashes) == set(arms) and set(hashes.values()) == {rec["observation_sha256"]}
        row = {
            "trial_id": wrapper["trial_id"],
            "block": "B_full_system",
            "scenario": wrapper["scenario"],
            "sweep": rec["sweep"],
            "point_index": wrapper["point_index"],
            "trial_index": wrapper["trial_index"],
            "root_seed": rec.get("root_seed"),
            "derived_seeds_json": wrapper.get("derived_seeds"),
            "protocol_sha256": wrapper["protocol_sha256"],
            "receiver_arms_json": arms,
            "frame_symbols": rec["frame_symbols"],
            "information_bits": rec["bits"],
            "information_pairs": rec["pairs"],
            "amplitude": rec["amplitude"],
            "noise_complex_variance": rec["noise_variance"],
            "transmit_energy_discrete": rec["tx_energy"],
            "energy_per_information_bit_discrete": rec["eb_d"],
            "gamma_b_discrete_db": wrapper["gamma_db"],
            "gamma_backend_db": rec["gamma_db"],
            "gamma_measured_db": rec.get("gamma_measured_db"),
            "channel_settings_json": rec.get("channel_settings"),
            "channel_config_json": rec.get("channel_config"),
            "delays_json": rec.get("delays"),
            "path_powers_json": rec.get("path_powers"),
            "rician_k_json": rec.get("rician_k"),
            "correlation": rec.get("correlation"),
            "observation_sha256": rec["observation_sha256"],
            "receiver_observation_hashes_json": hashes,
            "raw_wall_elapsed_seconds": wrapper.get("raw_wall_elapsed_seconds"),
            "process_cpu_seconds": wrapper.get("process_cpu_seconds"),
            "record_sha256": digest,
            "array_sha256": entry["array_sha256"],
            "source_record_path": src_rec,
            "source_array_path": src_arr,
        }
        for arm in ("joint", "b0", "b1"):
            for suffix, source in (
                ("bit_errors", "bit_errors"),
                ("ber", "ber"),
                ("pair_errors", "pair_errors"),
                ("ser_information_pairs", "ser"),
                ("frame_errors", "frame_errors"),
                ("runtime_seconds", "runtime_seconds"),
                ("process_cpu_seconds", "receiver_process_cpu_seconds"),
            ):
                row[f"{arm}_{suffix}"] = rec.get(source, {}).get(arm, "")
            row[f"{arm}_bits"] = rec["bits"] if arm in arms else ""
            row[f"{arm}_pairs"] = rec["pairs"] if arm in arms else ""
            row[f"{arm}_fer"] = int(rec["frame_errors"][arm] > 0) if arm in arms else ""
        rows.append(row)
        pairing.append(
            {
                "trial_id": wrapper["trial_id"],
                "block": "B_full_system",
                "scenario": wrapper["scenario"],
                "sweep": rec["sweep"],
                "point_index": wrapper["point_index"],
                "observation_hash": rec["observation_sha256"],
                "receiver_observation_hashes_json": hashes,
                "receiver_hashes_equal": paired,
                "record_sha256": digest,
                "array_sha256": entry["array_sha256"],
            }
        )
        signature = ";".join(f"{arm}_error={int(rec['bit_errors'][arm] > 0)}" for arm in arms)
        key = ("B/" + wrapper["scenario"], int(wrapper["point_index"]))
        rank = hashlib.sha256(f"{SAMPLE_SEED}|{wrapper['trial_id']}".encode()).hexdigest()
        if signature not in groups[key] or rank < groups[key][signature]["rank"]:
            groups[key][signature] = {
                "rank": rank,
                "entry": entry,
                "record": wrapper,
                "record_path": record_path,
                "array_path": array_path,
                "source_record": src_rec,
                "source_array": src_arr,
            }
    return rows, pairing, groups


def energy_rows(snapshot: dict) -> list[dict]:
    out = []
    for scenario, sweeps in snapshot["metric_isolation"].items():
        section = sweeps["amplitude_fixed_noise"]
        for target, result in section["metric_gain"].items():
            ci = result["bootstrap"]["log_ber"].get("gain_db_ci95") or [None, None]
            out.append(
                {
                    "block": "A_metric_isolation",
                    "scenario": scenario,
                    "target_ber": float(target),
                    "comparison": "euclidean_vs_hamming",
                    "energy_1_discrete_eb": result[
                        "required_energy_per_information_bit_discrete"
                    ].get("euclidean"),
                    "energy_2_discrete_eb": result[
                        "required_energy_per_information_bit_discrete"
                    ].get("hamming"),
                    "gain_db": result.get("gain_db_log_ber"),
                    "ci95_low_db": ci[0],
                    "ci95_high_db": ci[1],
                    "valid_crossing_fraction": result["bootstrap"]["log_ber"]["valid_fraction"],
                    "linear_ber_ci95": result["bootstrap"]["linear_ber"].get("gain_db_ci95"),
                    "status": result["precision_assessment"]["status"],
                }
            )
    for scenario, section in snapshot["full_system_comparison"].items():
        for target, arm_results in section["energy_gain"].items():
            for arm, result in arm_results.items():
                ci = result["bootstrap"]["log_ber"].get("gain_db_ci95") or [None, None]
                out.append(
                    {
                        "block": "B_full_system",
                        "scenario": scenario,
                        "target_ber": float(target),
                        "comparison": f"joint_vs_{arm}",
                        "energy_1_discrete_eb": result[
                            "required_energy_per_information_bit_discrete"
                        ].get("euclidean"),
                        "energy_2_discrete_eb": result[
                            "required_energy_per_information_bit_discrete"
                        ].get("hamming"),
                        "gain_db": result.get("gain_db_log_ber"),
                        "ci95_low_db": ci[0],
                        "ci95_high_db": ci[1],
                        "valid_crossing_fraction": result["bootstrap"]["log_ber"]["valid_fraction"],
                        "linear_ber_ci95": result["bootstrap"]["linear_ber"].get("gain_db_ci95"),
                        "status": result["precision_assessment"]["status"],
                    }
                )
    return out


def write_samples(stage: Path, groups_all: list[dict], sample_seed: int) -> list[dict]:
    selected = []
    for groups in groups_all:
        for (stratum, point), patterns in sorted(groups.items()):
            for outcome, item in sorted(patterns.items()):
                if stratum.startswith("B/"):
                    block = "B_full_system"
                    scenario = stratum.split("/", 1)[1]
                    sweep = item["record"]["record"]["sweep"]
                    trial_id = item["entry"]["trial_id"]
                    outdir = stage / "06_PRIMARY_DATA_SAMPLES/selected_trials" / block / scenario
                else:
                    block = "A_metric_isolation"
                    scenario, sweep = stratum.split("/", 1)
                    trial_id = item["record"]["trial_id"]
                    outdir = (
                        stage / "06_PRIMARY_DATA_SAMPLES/selected_trials" / block / scenario / sweep
                    )
                outdir.mkdir(parents=True, exist_ok=True)
                json_out, npz_out = outdir / f"{trial_id}.json", outdir / f"{trial_id}.npz"
                copy_file(item["record_path"], json_out)
                copy_file(item["array_path"], npz_out)
                selected.append(
                    {
                        "trial_id": trial_id,
                        "block": block,
                        "scenario": scenario,
                        "sweep": sweep,
                        "point_index": point,
                        "outcome_pattern": outcome,
                        "selection_rank_sha256": item["rank"],
                        "source_record_path": item["source_record"],
                        "source_array_path": item["source_array"],
                        "source_record_sha256": item["entry"]["record_sha256"],
                        "source_array_sha256": item["entry"]["array_sha256"],
                        "included_record_path": json_out.relative_to(
                            stage / "06_PRIMARY_DATA_SAMPLES"
                        ).as_posix(),
                        "included_array_path": npz_out.relative_to(
                            stage / "06_PRIMARY_DATA_SAMPLES"
                        ).as_posix(),
                        "included_record_sha256": sha_file(json_out),
                        "included_array_sha256": sha_file(npz_out),
                        "array_size_bytes": npz_out.stat().st_size,
                    }
                )
    write_json(
        stage / "06_PRIMARY_DATA_SAMPLES/selection_protocol.json",
        {
            "selection_seed": sample_seed,
            "rule": "For each scenario/sweep/energy point and each observed per-arm bit-error-present signature, select the trial with minimum SHA256(seed|trial_id).",
            "selected_trial_count": len(selected),
            "selected_npz_bytes": sum(r["array_size_bytes"] for r in selected),
            "bias_control": "Selection covers each observed outcome signature rather than ranking by which algorithm won.",
        },
    )
    write_json(
        stage / "06_PRIMARY_DATA_SAMPLES/sample_manifest.json",
        {"schema_version": "exp03b-stratified-primary-sample-v1", "samples": selected},
    )
    write_csv(stage / "06_PRIMARY_DATA_SAMPLES/selected_trials.csv", selected)
    return selected


def make_report(metric_rows: list[dict], system_rows: list[dict], snapshot: dict) -> str:
    a, b = snapshot["metric_isolation"], snapshot["full_system_comparison"]
    lines = [
        "# SCIENTIFIC-EXP-03B — фінальний науковий звіт для незалежного аудиту",
        "",
        "## 1. Мета дослідження",
        "",
        "Виконано фінальний аналіз завершених confirmatory-даних для оцінювання (а) ізольованого впливу метрики Вітербі та (б) різниці повних інформаційних технологій приймання. Аналіз охоплює AWGN, статичну багатопроменевість і Rician AR(1). Основний цільовий рівень для енергетичних перетинів — BER=0,05; додатково перевірялися 0,01 і 0,001. Нові випробування не запускались, а результати не підганялись під 1,5 дБ.",
        "",
        "## 2. Архітектура інформаційної технології",
        "",
        "Передавач формує TCM/8PSK-послідовність зі згортковим кодом. Модель каналу формує спільне комплексне спостереження, включно з шумом і зафіксованими умовами поширення. У блоці A Евклідів і Хемінгів декодери працюють із тією самою послідовністю, спільним pilot frontend/equalizer, однаковими оцінками й решіткою, η=20 та правилом traceback; контраст призначений для ефекту метрики. У блоці B зіставлено адаптивний Joint Euclidean з Separate Hamming B0 та, у статичному сценарії, B1. Останній контраст охоплює одночасно відмінності алгоритмів приймання й не є чистим експериментом метрики.",
        "",
        "## 3. Протокол експериментів",
        "",
        f"Фактичні дані: блок A — {len(metric_rows):,} trials; блок B — {len(system_rows):,}; разом — {len(metric_rows) + len(system_rows):,}. Заморожений protocol SHA-256: `{PROTOCOL_SHA}`. Блок A: п'ять сценаріїв metric-ізоляції, amplitude/noise sweeps, F=1024 і 300 незалежних trial-кластерів на точку. Блок B: AWGN 2 900, static 2 900, Rician 2 500 paired frames, F=256, 100 на енергетичний рівень. Для інтервалів використано 5 000 paired independent-trial cluster bootstrap повторів. Основна інтерполяція — лінійна за log10(BER) між суміжними виміряними точками; linear-BER наведено як чутливість. Екстраполяції немає. Повні точкові криві й усі trial-level чисельники та знаменники входять до архіву.",
        "",
        "## 4. Результати блоку A — ізольоване порівняння метрик",
        "",
        "Для цілі BER=0,05 модельний gain визначався як 10log10(Eᵦ,H/Eᵦ,E). ΔBER подано як BER(E)−BER(H), отже від'ємне значення означає перевагу евклідової метрики. Значення Eᵦ є проєктною дискретною енергією на інформаційний біт.",
        "",
        "| Сценарій | Eᵦ,d E | Eᵦ,d H | Gain, дБ | 95% bootstrap-ДІ | Допустимі перетини | Статус |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for scenario in (
        "awgn_direct",
        "awgn_pilot",
        "static_pilot",
        "rician_period32",
        "rician_period8",
    ):
        est = a[scenario]["amplitude_fixed_noise"]["metric_gain"]["0.05"]
        e = est["required_energy_per_information_bit_discrete"].get("euclidean")
        h = est["required_energy_per_information_bit_discrete"].get("hamming")
        gain = est.get("gain_db_log_ber")
        ci = est["bootstrap"]["log_ber"].get("gain_db_ci95")
        vf = est["bootstrap"]["log_ber"]["valid_fraction"]
        lines.append(
            "| "
            + " | ".join(
                [
                    scenario,
                    f"{e:.6g}" if e is not None else "—",
                    f"{h:.6g}" if h is not None else "—",
                    f"{gain:.4f}" if gain is not None else "NOT_ESTIMABLE",
                    f"[{ci[0]:.4f}; {ci[1]:.4f}]" if ci else "—",
                    f"{vf:.2%}",
                    est["precision_assessment"]["status"],
                ]
            )
            + " |"
        )
    lines += [
        "",
        "Для `awgn_direct` gain дорівнює 2,8668 дБ (95% ДІ [2,8197; 2,9140], 100% допустимих bootstrap-перетинів); для `awgn_pilot` — 2,2960 дБ ([2,1586; 2,4236], 100%); для `static_pilot` — 2,4373 дБ ([2,3375; 2,5335], 100%). В усіх трьох визначених контрастах інтервали повністю вище нуля. Заміна інтерполяції на лінійну BER не змінює висновку; точні CI наведено в `energy_gain_summary.csv` та numeric snapshot.",
        "",
        "Для основного Rician cadence 32 при найвищій енергії γᵦ,d=37,6108 дБ маємо BER(E)=0,12332, BER(H)=0,18243, ΔBER=−0,05911; 95% парний ДІ для різниці [−0,06052; −0,05770]. Обидва BER більші за 0,05, тож gain для цілі не оцінюється (`ENERGY_GAIN_NOT_ESTIMABLE`). У cadence 8 ціль перетинає лише евклідова крива — парного перетину також немає. Отже, нижча BER в окремій точці не тотожна оцінюваному горизонтальному енергетичному виграшу.",
        "",
        "Для target 0,01 та 0,001 не отримано достатньо одночасних допустимих перетинів для стійкої оцінки gain. Там, де перетин відсутній або bootstrap crossing fraction нижчий за критерій, gain не повідомляється як підтверджене число.",
        "",
        "## 5. Результати блоку B — порівняння повних приймачів",
        "",
        "| Канал | Контраст | Gain при BER=0,05 | 95% ДІ | Valid crossings | Висновок |",
        "|---|---|---:|---:|---:|---|",
    ]
    for scenario in ("awgn", "static", "rician"):
        for arm in ("b0", "b1"):
            est = b[scenario]["energy_gain"]["0.05"].get(arm)
            if est is None:
                continue
            ci = est["bootstrap"]["log_ber"].get("gain_db_ci95")
            gain = est.get("gain_db_log_ber")
            lines.append(
                "| "
                + " | ".join(
                    [
                        scenario,
                        f"Joint/{arm.upper()}",
                        f"{gain:.4f} дБ" if gain is not None else "NOT_ESTIMABLE",
                        f"[{ci[0]:.4f}; {ci[1]:.4f}]" if ci else "—",
                        f"{est['bootstrap']['log_ber']['valid_fraction']:.2%}",
                        est["precision_assessment"]["status"],
                    ]
                )
                + " |"
            )
    lines += [
        "",
        "Для AWGN Joint/B0 gain=1,6664 дБ, 95% bootstrap-ДІ [1,2921; 2,0016], допустимі перетини — 99,02%; це єдиний системний target-контраст, який проходить зафіксований критерій точності. У static multipath точкові оцінки для Joint/B0 (5,4928 дБ; 94,68%) і Joint/B1 (2,2388 дБ; 94,94%) не проходять frozen поріг 95% bootstrap-перетинів — це недостатня точність, а не підтверджений gain. У Rician B0 не досягає BER=0,05; B1 для цього каналу не передбачений протоколом, тому Joint/B0 gain не визначається.",
        "",
        "Поточні BER/SER/FER за кожним енергетичним рівнем і receiver arm наведено в `02_ALL_TRIAL_AGGREGATES/full_system_all_points.csv`; повні чисельники по кожному кадру — у `system_trial_summary.csv`.",
        "",
        "## 6. Енергетична ефективність",
        "",
        "Використано Eₜₓ,d=Σₙ|x[n]|², Eᵦ,d=Eₜₓ,d/N_payload_bits і γᵦ,d=10log10(Eᵦ,d/σ²_c). У pilot-контрастах повна енергія transmitted samples включає training/pilot та payload, а знаменник — корисні payload інформаційні біти, тобто overhead враховано. У блоці B застосована заморожена discrete project convention. Фізична часова нормалізація, смуга, pulse shape, matched filter і зв'язок sample-domain variance з N₀ тут не визначені, тому фізичне Eb/N0 має статус NOT_VALIDATED.",
        "",
        "Для метрик gain=10log10(Eᵦ,H/Eᵦ,E); для систем — 10log10(Eᵦ,separate/Eᵦ,joint). Для оцінки приймаються лише bracketed виміряні перетини із зафіксованими умовами щодо помилкових лічильників, CI та частки валідних bootstrap-перетинів. Жоден неіснуючий перетин не екстраполюється.",
        "",
        "## 7. Статистична перевірка",
        "",
        "У парі використовуються одні й ті самі реалізації та observation; bootstrap ресемплює цілі незалежні trials, а не окремі біти. Пакет містить 31 100 рядків з помилками/знаменниками, seeds, енергіями, часами й хешами. `verify_audit.py` повторно агрегує всі counts, усі BER/SER/FER point tables і 5 000-кратний cluster bootstrap за включеним алгоритмом та зафіксованими seeds. Первинні NPZ входять для детермінованої outcome-stratified вибірки; прямий raw-array перерахунок для всіх кадрів не заявляється.",
        "",
        "## 8. Порівняння з результатом 1,5 дБ",
        "",
        "Статейний результат 1,5 дБ не підтверджений як точне відтворення. Системна AWGN оцінка 1,6664 дБ має CI, який чисельно містить 1,5 дБ, але це лише сумісність інтервалу з числом, а не доказ однакових умов. Стаття та цей проєкт відрізняються умовами каналу, визначенням порогу/помилки, структурою повних приймачів і енергетичною конвенцією. У блоці A оцінено ізольований ефект метрики; у блоці B — сукупний системний ефект. `paper_exact=false`.",
        "",
        "## 9. Обмеження дослідження",
        "",
        "- Дискретна γᵦ,d не є фізично валідованим Eb/N0; результати не доводять фізичне зменшення енергії передавання БПЛА.\n- Для Rician ціль BER=0,05 не перетнули обидва metric arms або пара Joint/B0; енергетичний gain не оцінюється.\n- Static full-system point gains не виконали frozen вимогу ≥95% допустимих bootstrap-перетинів.\n- B1 є окремим статичним інформаційним режимом із номінально доступними taps; не узагальнюється на всі канали.\n- Компактний архів містить counts усіх trials, але лише вибірку первинних сигналів. Масиви інших кадрів не перераховуються без повного архіву.",
        "",
        "## 10. Висновки для магістерської дисертації",
        "",
        "У виміряних AWGN та статичному pilot-контрастах ізольована заміна метрики Хемінга евклідовою дала нижчу BER і позитивний модельний energy shift при target BER=0,05, із 95% bootstrap-інтервалами вище нуля. Для Rician AR(1) зафіксовано нижчу BER евклідової метрики на максимальній виміряній енергії, однак target не досягнуто обома декодерами, тому gain не оцінюється. Для повних приймачів підтверджений gain при BER=0,05 є лише AWGN Joint/B0; static оцінки не пройшли поріг точності, а Rician перетину не має. Це свідчить про залежність результату від каналу й постановки та не обґрунтовує універсальну перевагу або фізичну енергоефективність.",
        "",
        "### Таблиці та повні дані",
        "",
        "- Trial-level Block A: `02_ALL_TRIAL_AGGREGATES/metric_trial_summary.csv`.\n- Trial-level Block B: `02_ALL_TRIAL_AGGREGATES/system_trial_summary.csv`.\n- Усі measured BER/SER/FER points: `02_ALL_TRIAL_AGGREGATES/metric_isolation_all_points.csv` і `full_system_all_points.csv`.\n- Energy gains, CI, crossing fractions, interpolation sensitivity: `03_RESULTS/energy_gain/energy_gain_summary.csv` та numeric snapshot.\n- Повний текст четвертого розділу: `08_THESIS/chapter_4_draft.md`.",
    ]
    return "\n".join(lines) + "\n"


def build_summary(snapshot: dict, metric_count: int, system_count: int, gains: list[dict]) -> dict:
    return {
        "experiment": "SCIENTIFIC-EXP-03B",
        "metric_trials": metric_count,
        "system_trials": system_count,
        "total_trials": metric_count + system_count,
        "metric_isolation": {
            "pairing_verified": True,
            "target_ber_0_05": {
                s: snapshot["metric_isolation"][s]["amplitude_fixed_noise"]["metric_gain"]["0.05"]
                for s in snapshot["metric_isolation"]
            },
        },
        "awgn": {
            "metric_direct_gain_db_target_0_05": snapshot["metric_isolation"]["awgn_direct"][
                "amplitude_fixed_noise"
            ]["metric_gain"]["0.05"].get("gain_db_log_ber"),
            "metric_pilot_gain_db_target_0_05": snapshot["metric_isolation"]["awgn_pilot"][
                "amplitude_fixed_noise"
            ]["metric_gain"]["0.05"].get("gain_db_log_ber"),
            "joint_b0_gain_db_target_0_05": snapshot["full_system_comparison"]["awgn"][
                "energy_gain"
            ]["0.05"]["b0"].get("gain_db_log_ber"),
        },
        "static_multipath": {
            "metric_pilot_gain_db_target_0_05": snapshot["metric_isolation"]["static_pilot"][
                "amplitude_fixed_noise"
            ]["metric_gain"]["0.05"].get("gain_db_log_ber"),
            "joint_b0_point_gain_db_target_0_05": snapshot["full_system_comparison"]["static"][
                "energy_gain"
            ]["0.05"]["b0"].get("gain_db_log_ber"),
            "joint_b1_point_gain_db_target_0_05": snapshot["full_system_comparison"]["static"][
                "energy_gain"
            ]["0.05"]["b1"].get("gain_db_log_ber"),
        },
        "rician_ar1": {
            "metric_gain_db_target_0_05": snapshot["metric_isolation"]["rician_period32"][
                "amplitude_fixed_noise"
            ]["metric_gain"]["0.05"].get("gain_db_log_ber"),
            "metric_gain_status": snapshot["metric_isolation"]["rician_period32"][
                "amplitude_fixed_noise"
            ]["metric_gain"]["0.05"]["precision_assessment"]["status"],
            "joint_b0_gain_db_target_0_05": snapshot["full_system_comparison"]["rician"][
                "energy_gain"
            ]["0.05"]["b0"].get("gain_db_log_ber"),
        },
        "energy_gain_db": {
            f"{r['block']}/{r['scenario']}/{r['comparison']}/BER={r['target_ber']:g}": r["gain_db"]
            for r in gains
        },
        "confidence_intervals": {
            f"{r['block']}/{r['scenario']}/{r['comparison']}/BER={r['target_ber']:g}": [
                r["ci95_low_db"],
                r["ci95_high_db"],
            ]
            for r in gains
        },
        "statistical_conclusions": {
            "bootstrap_replicates": snapshot["bootstrap_replicates"],
            "bootstrap_seed_root": snapshot["bootstrap_seed_root"],
            "metric_gain_confirmed_at_0_05": ["awgn_direct", "awgn_pilot", "static_pilot"],
            "rician_metric_gain": "ENERGY_GAIN_NOT_ESTIMABLE",
            "system_gain_precision_pass": ["awgn/joint_vs_b0/0.05"],
        },
        "audit_limitations": [
            "All 31,100 trials have trial-level counters, denominators, parameters, seeds and hash references; raw signal arrays are present only in the deterministic stratified sample.",
            "Non-sampled NPZ SHA values are bound to the full archive manifest but not re-read by this compact audit.",
            "Physical Eb/N0 is not validated; the energy axis is a project-defined discrete normalization.",
            "No gain is extrapolated outside observed BER brackets.",
            "The article's 1.5 dB is not claimed as reproduced.",
        ],
    }


def add_manifest(stage: Path, full_status: dict) -> dict:
    rows = []
    for path in sorted(
        p for p in stage.rglob("*") if p.is_file() and p.name != "AUDIT_MANIFEST.json"
    ):
        rows.append(
            {
                "path": path.relative_to(stage).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha_file(path),
            }
        )
    manifest = {
        "schema_version": "hf-tcm-exp03b-compact-audit-v1",
        "root_directory": TOP,
        "manifest_self_hash_excluded": True,
        "file_count_excluding_manifest": len(rows),
        "experiment": "SCIENTIFIC-EXP-03B",
        "protocol_sha256": PROTOCOL_SHA,
        "source_full_archive": full_status,
        "files": rows,
    }
    write_json(stage / "AUDIT_MANIFEST.json", manifest)
    return manifest


def zip_stage(stage: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
    ) as archive:
        for path in sorted(p for p in stage.rglob("*") if p.is_file()):
            archive.write(path, arcname=f"{TOP}/{path.relative_to(stage).as_posix()}")


def verify_zip(path: Path, manifest: dict) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("Duplicate member paths in compact ZIP")
        if archive.testzip() is not None:
            raise RuntimeError("Compact ZIP CRC test failed")
        expected = {f"{TOP}/{row['path']}": row for row in manifest["files"]}
        expected[f"{TOP}/AUDIT_MANIFEST.json"] = None
        if set(names) != set(expected):
            raise RuntimeError("ZIP paths differ from embedded audit manifest")
        embedded = json.loads(archive.read(f"{TOP}/AUDIT_MANIFEST.json"))
        if embedded != manifest:
            raise RuntimeError("Embedded audit manifest mismatch")
        for path_name, row in expected.items():
            if row is None:
                continue
            content = archive.read(path_name)
            if len(content) != row["size_bytes"] or sha_bytes(content) != row["sha256"]:
                raise RuntimeError(f"ZIP member SHA/size mismatch: {path_name}")


def main() -> None:
    if STAGE.exists() or OUT_ZIP.exists():
        raise RuntimeError("Refusing to overwrite an existing staging directory or compact ZIP")
    STAGE.mkdir(parents=True)
    full_manifest, full_status = source_manifest()
    protocol_path = ROOT / "configs/SCIENTIFIC_EXP_03B_PROTOCOL.json"
    protocol = read_json(protocol_path)
    if sha_file(protocol_path) != PROTOCOL_SHA:
        raise RuntimeError("Frozen protocol SHA does not match the experiment")
    snapshot = read_json(ROOT / "outputs/scientific_exp03b/analysis/independent_analysis.json")
    analysis = read_json(ROOT / "outputs/scientific_exp03b/analysis/independent_analysis.json")
    if (
        snapshot.get("protocol_sha256") != PROTOCOL_SHA
        or analysis.get("protocol_sha256") != PROTOCOL_SHA
    ):
        raise RuntimeError("Independent analysis is not tied to the frozen protocol")

    metric_rows, system_rows, pairing_rows, sample_groups = [], [], [], []
    metric_study_counts = {}
    for study in sorted((ROOT / "outputs/scientific_exp03b/metric/confirmatory").iterdir()):
        if not study.is_dir() or not (study / "checkpoint.jsonl").exists():
            continue
        meta = read_json(study / "manifest.json")
        if (
            meta.get("status") != "completed"
            or meta.get("protocol_sha256") != PROTOCOL_SHA
            or meta.get("completed_trials") != meta.get("planned_trials")
        ):
            raise RuntimeError(f"Metric manifest not completed or protocol mismatch: {study}")
        rows, paired, samples = parse_metric(study, full_manifest)
        metric_rows.extend(rows)
        pairing_rows.extend(paired)
        sample_groups.append(samples)
        metric_study_counts[study.name] = len(rows)
    system_study_counts = {}
    for study in sorted((ROOT / "outputs/scientific_exp03b/system/confirmatory").iterdir()):
        if not study.is_dir() or not (study / "checkpoint.jsonl").exists():
            continue
        meta = read_json(study / "manifest.json")
        if (
            meta.get("status") != "completed"
            or meta.get("protocol_sha256") != PROTOCOL_SHA
            or meta.get("completed_trials") != meta.get("planned_trials")
        ):
            raise RuntimeError(f"System manifest not completed or protocol mismatch: {study}")
        rows, paired, samples = parse_system(study, full_manifest)
        system_rows.extend(rows)
        pairing_rows.extend(paired)
        sample_groups.append(samples)
        system_study_counts[study.name] = len(rows)
    if (
        len(metric_rows) != 22800
        or len(system_rows) != 8300
        or len(metric_rows) + len(system_rows) != 31100
    ):
        raise RuntimeError(f"Unexpected trial totals A={len(metric_rows)} B={len(system_rows)}")
    all_ids = [x["trial_id"] for x in metric_rows + system_rows]
    if len(set(all_ids)) != len(all_ids):
        raise RuntimeError("Duplicate confirmatory trial IDs")
    if not all(
        x.get("observation_hashes_equal", x.get("receiver_hashes_equal", False))
        for x in pairing_rows
    ):
        raise RuntimeError("Observation pairing check failed")
    if not all(x.get("frontend_hashes_equal", True) for x in pairing_rows):
        raise RuntimeError("Metric front-end equality check failed")

    directories = [
        "00_START_HERE",
        "01_PROTOCOL/frozen_protocol/references",
        "01_PROTOCOL/configurations",
        "02_ALL_TRIAL_AGGREGATES",
        "03_RESULTS/metric_isolation",
        "03_RESULTS/joint_system",
        "03_RESULTS/energy_gain",
        "03_RESULTS/confidence_intervals",
        "03_RESULTS/statistical_tests",
        "04_FIGURES/BER",
        "04_FIGURES/SER_FER",
        "04_FIGURES/energy_gain",
        "04_FIGURES/comparisons",
        "05_SOURCE_CODE",
        "06_PRIMARY_DATA_SAMPLES",
        "07_VERIFICATION/tests",
        "07_VERIFICATION/integrity_checks",
        "07_VERIFICATION/original_file_hashes",
        "07_VERIFICATION/independent_recalculation",
        "08_THESIS",
    ]
    for name in directories:
        (STAGE / name).mkdir(parents=True, exist_ok=True)
    write_csv(STAGE / "02_ALL_TRIAL_AGGREGATES/metric_trial_summary.csv", metric_rows)
    write_csv(STAGE / "02_ALL_TRIAL_AGGREGATES/system_trial_summary.csv", system_rows)
    write_csv(STAGE / "02_ALL_TRIAL_AGGREGATES/observation_pairing_audit.csv", pairing_rows)
    write_json(
        STAGE / "02_ALL_TRIAL_AGGREGATES/trial_counts.json",
        {
            "metric_trials": len(metric_rows),
            "system_trials": len(system_rows),
            "total_trials": len(all_ids),
            "metric_studies": metric_study_counts,
            "system_studies": system_study_counts,
            "unique_trial_ids": len(set(all_ids)),
            "protocol_sha256": PROTOCOL_SHA,
        },
    )
    for name in ("metric_isolation_all_points.csv", "full_system_all_points.csv"):
        copy_file(
            ROOT / "docs/research/tables/SCIENTIFIC_EXP_03B" / name,
            STAGE / "02_ALL_TRIAL_AGGREGATES" / name,
        )
    for rel, dest in [
        (
            "outputs/scientific_exp03b/analysis/independent_analysis.json",
            "03_RESULTS/independent_analysis.json",
        ),
        (
            "outputs/scientific_exp03b/analysis/analysis_manifest.json",
            "03_RESULTS/analysis_manifest.json",
        ),
    ]:
        copy_file(ROOT / rel, STAGE / dest)
    gains = energy_rows(snapshot)
    write_csv(STAGE / "03_RESULTS/energy_gain/energy_gain_summary.csv", gains)

    original_hashes: list[dict] = []
    protocol_config = STAGE / "01_PROTOCOL/configurations/SCIENTIFIC_EXP_03B_PROTOCOL.json"
    copy_file(protocol_path, protocol_config)
    original_hashes.append(
        {
            "source_path": "configs/SCIENTIFIC_EXP_03B_PROTOCOL.json",
            "included_path": "01_PROTOCOL/configurations/SCIENTIFIC_EXP_03B_PROTOCOL.json",
            "size_bytes": protocol_path.stat().st_size,
            "sha256": sha_file(protocol_path),
        }
    )
    for rel in (
        "docs/research/SCIENTIFIC_EXP_03B_FROZEN_PROTOCOL.md",
        "docs/research/SCIENTIFIC_EXP_03B_PROTOCOL_AMENDMENT.md",
    ):
        src = ROOT / rel
        dst = STAGE / "01_PROTOCOL/frozen_protocol" / src.name
        copy_file(src, dst)
        original_hashes.append(
            {
                "source_path": rel,
                "included_path": dst.relative_to(STAGE).as_posix(),
                "size_bytes": src.stat().st_size,
                "sha256": sha_file(src),
            }
        )
    for rel in (
        "references/source_paper_2026.docx",
        "references/Яковів_Гриненко_2026_в7 27-10-26(4).docx",
        "references/Раздел_4.doc",
        "references/SHA256SUMS.txt",
        "references/README.md",
        "references/PAPER_EXTRACT_M1.md",
    ):
        src = ROOT / rel
        dst = STAGE / "01_PROTOCOL/frozen_protocol/references" / src.name
        copy_file(src, dst)
        original_hashes.append(
            {
                "source_path": rel,
                "included_path": dst.relative_to(STAGE).as_posix(),
                "size_bytes": src.stat().st_size,
                "sha256": sha_file(src),
            }
        )
    write_json(STAGE / "01_PROTOCOL/experiment_parameters.json", protocol)
    parameter_rows = []
    for scenario in protocol["metric_isolation"]["scenarios"]:
        parameter_rows.append(
            {
                "block": "A_metric_isolation",
                "scenario": scenario["id"],
                "channel_description": scenario["channel"],
                "frame_symbols": protocol["metric_isolation"]["frame_symbols"],
                "trials_per_point": protocol["metric_isolation"]["confirmatory_trials_per_point"],
                "energy_offsets_db": scenario["energy_offsets_db"],
                "sweeps": protocol["metric_isolation"]["sweeps"],
                "protocol_sha256": PROTOCOL_SHA,
            }
        )
    for scenario, grid in protocol["system_comparison"]["energy_grid_gamma_db"].items():
        parameter_rows.append(
            {
                "block": "B_full_system",
                "scenario": scenario,
                "channel_description": protocol["system_comparison"]["channel_profiles"][scenario],
                "frame_symbols": protocol["system_comparison"]["frame_symbols"],
                "trials_per_point": protocol["system_comparison"]["confirmatory_trials_per_point"],
                "gamma_grid_db": grid,
                "protocol_sha256": PROTOCOL_SHA,
            }
        )
    write_csv(STAGE / "01_PROTOCOL/experiment_parameters.csv", parameter_rows)

    report = make_report(metric_rows, system_rows, snapshot)
    (STAGE / "00_START_HERE/CHATGPT_FINAL_SCIENTIFIC_REPORT_UK.md").write_text(
        report, encoding="utf-8"
    )
    copy_file(
        STAGE / "00_START_HERE/CHATGPT_FINAL_SCIENTIFIC_REPORT_UK.md",
        ROOT / "CHATGPT_FINAL_SCIENTIFIC_REPORT_UK.md",
    )
    summary = build_summary(snapshot, len(metric_rows), len(system_rows), gains)
    write_json(STAGE / "00_START_HERE/KEY_RESULTS_SUMMARY.json", summary)
    write_json(ROOT / "KEY_RESULTS_SUMMARY.json", summary)
    scope = """# Обсяг аудиту та обмеження\n\nКомпактний пакет містить trial-level лічильники, знаменники, сценарії, енергетичні параметри, seeds, часи та hash references для всіх 31 100 confirmatory trials. За ними можна повторно агрегувати BER/SER/FER по кожній енергетичній точці, відтворити криві на рівні цілих frame counts, paired cluster bootstrap і перетини gain.\n\nПовні signal arrays усіх 31 100 кадрів не дублюються. Додана детермінована outcome-stratified вибірка повних JSON/NPZ дозволяє безпосередньо перерахувати помилки й енергію та перевірити спільність observations для кожної представленої пари. Для решти масивів компактний пакет зберігає SHA, пов'язаний з маніфестом повного архіву; їхній вміст повторно не читається з цього пакета. Отже, direct raw-array verification доступний для sample, тоді як counts/bootstrap можна перевірити для всіх trials.\n\nПовний ZIP `HF_TCM_SIM_SCIENTIFIC_EXP_03B_FULL_AUDIT.zip` наявний (6 369 224 917 байтів); його central directory та manifest відкриваються, міститься 87 543 file-hash rows плюс сам manifest. У цій роботі не повторювався повний CRC-прохід через увесь 6.37 GB вміст; перевірено SHA/розміри всіх record JSON при формуванні compact tables, зв'язок NPZ hashes з повним manifest, а також повний SHA для кожного включеного sample і компактного ZIP. Попередня project validation повідомляла успішну перевірку повного ZIP; це зазначено окремо від свіжої перевірки цього пакета.\n\n`paper_exact=false`. Дискретна γᵦ,d — проєктна нормалізована шкала, не валідований фізичний Eb/N0. Неоцінювані перетини не екстраполюються.\n"""
    (STAGE / "00_START_HERE/AUDIT_SCOPE_AND_LIMITATIONS.md").write_text(scope, encoding="utf-8")
    readme = f"""# SCIENTIFIC-EXP-03B — аудитний пакет для ChatGPT\n\nСпершу прочитайте `00_START_HERE/CHATGPT_FINAL_SCIENTIFIC_REPORT_UK.md`. Архів містить всі {len(metric_rows):,} trial-level records блоку A і {len(system_rows):,} блоку B (всього {len(all_ids):,}), усі точки BER/SER/FER, numeric snapshot із bootstrap, протокол і суттєвий Python-код. Вибіркові первинні NPZ сформовані детерміновано за outcome signatures кожної точки; протокол відбору й SHA записані.\n\nДля перевірки: встановити NumPy за `requirements_audit.txt`, виконати `python verify_audit.py` з кореня цього каталогу. Скрипт повторно агрегує всі counts, звіряє всі енергетичні точки, повторює 5 000 кластерних bootstrap повторів за зафіксованим seed derivation, перевіряє gain формули та перераховує raw arrays вибірки. Він не стверджує повний array-level recount 31 100 кадрів.\n\nFrozen protocol SHA-256: `{PROTOCOL_SHA}`. Фізичне Eb/N0 не валідовано; 1,5 дБ зі статті не оголошено відтвореним; `paper_exact=false`.\n"""
    (STAGE / "00_START_HERE/README_FOR_CHATGPT.md").write_text(readme, encoding="utf-8")
    (STAGE / "requirements_audit.txt").write_text("numpy>=1.26\n", encoding="utf-8")
    for rel in (
        "docs/research/SCIENTIFIC_EXP_03B_FINAL_REPORT.md",
        "docs/research/SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md",
        "docs/research/SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md",
        "docs/research/SCIENTIFIC_EXP_03B_ENERGY_GAIN.md",
        "docs/research/SCIENTIFIC_EXP_03B_STATISTICAL_VALIDATION.md",
        "docs/research/SCIENTIFIC_EXP_03B_ARTICLE_COMPARISON.md",
        "docs/research/THESIS_CHAPTER_4_FINAL_DRAFT.md",
        "docs/research/THESIS_CHAPTER_4_FIGURES_AND_TABLES.md",
    ):
        src = ROOT / rel
        dest = STAGE / "03_RESULTS" / src.name
        copy_file(src, dest)
        original_hashes.append(
            {
                "source_path": rel,
                "included_path": dest.relative_to(STAGE).as_posix(),
                "size_bytes": src.stat().st_size,
                "sha256": sha_file(src),
            }
        )
    copy_file(
        ROOT / "docs/research/THESIS_CHAPTER_4_FINAL_DRAFT.md",
        STAGE / "08_THESIS/chapter_4_draft.md",
    )
    copy_file(
        ROOT / "docs/research/THESIS_CHAPTER_4_FIGURES_AND_TABLES.md",
        STAGE / "08_THESIS/figures_and_tables.md",
    )

    # Copy the production bootstrap implementation and relevant scientific code/tests.
    for src in sorted((ROOT / "src/hf_tcm/repro").glob("*.py")):
        dest = STAGE / "05_SOURCE_CODE/src/hf_tcm/repro" / src.name
        copy_file(src, dest)
        original_hashes.append(
            {
                "source_path": src.relative_to(ROOT).as_posix(),
                "included_path": dest.relative_to(STAGE).as_posix(),
                "size_bytes": src.stat().st_size,
                "sha256": sha_file(src),
            }
        )
    for rel in (
        "src/hf_tcm/__init__.py",
        "scripts/analyze_scientific_exp03b.py",
        "scripts/reanalyze_scientific_exp03b_system.py",
        "scripts/run_scientific_exp03b.py",
        "scripts/render_scientific_exp03b_figures.py",
        "scripts/write_scientific_exp03b_reports.py",
        "tests/repro/test_scientific_exp03b_analysis.py",
        "tests/repro/test_scientific_exp03b_analysis_cli.py",
        "tests/repro/test_scientific_exp03b_infrastructure.py",
    ):
        src = ROOT / rel
        dest_rel = Path(rel).relative_to("src") if rel.startswith("src/") else Path(rel)
        dest = STAGE / "05_SOURCE_CODE" / dest_rel
        copy_file(src, dest)
        original_hashes.append(
            {
                "source_path": rel,
                "included_path": dest.relative_to(STAGE).as_posix(),
                "size_bytes": src.stat().st_size,
                "sha256": sha_file(src),
            }
        )
    copy_file(ROOT / "scripts/verify_exp03b_compact_audit.py", STAGE / "verify_audit.py")
    original_hashes.append(
        {
            "source_path": "scripts/verify_exp03b_compact_audit.py",
            "included_path": "verify_audit.py",
            "size_bytes": (ROOT / "scripts/verify_exp03b_compact_audit.py").stat().st_size,
            "sha256": sha_file(ROOT / "scripts/verify_exp03b_compact_audit.py"),
        }
    )
    for rel in (
        "outputs/scientific_exp03b/validation_logs/full_pytest_nocache.log",
        "outputs/scientific_exp03b/validation_logs/historical_fingerprints.log",
        "outputs/scientific_exp03b/validation_logs/ruff_scoped_check.log",
        "outputs/scientific_exp03b/validation_logs/ruff_scoped_format.log",
    ):
        src = ROOT / rel
        dest = STAGE / "07_VERIFICATION/tests" / src.name
        copy_file(src, dest)
        original_hashes.append(
            {
                "source_path": rel,
                "included_path": dest.relative_to(STAGE).as_posix(),
                "size_bytes": src.stat().st_size,
                "sha256": sha_file(src),
            }
        )
    write_json(STAGE / "07_VERIFICATION/integrity_checks/full_archive_status.json", full_status)
    copy_file(
        ROOT / "outputs/scientific_exp03b/analysis/analysis_manifest.json",
        STAGE / "07_VERIFICATION/integrity_checks/analysis_manifest.json",
    )
    write_csv(
        STAGE / "07_VERIFICATION/original_file_hashes/original_file_hashes.csv", original_hashes
    )

    # Select key real graph exports directly from the finished full archive.
    figure_manifest_path = "docs/research/figures/SCIENTIFIC_EXP_03B/FIGURE_EXPORTS_MANIFEST.json"
    figure_manifest = read_json(ROOT / figure_manifest_path)
    figure_map = {item["path"]: item for item in figure_manifest["figures"]}
    copy_file(ROOT / figure_manifest_path, STAGE / "04_FIGURES/source_figure_export_manifest.json")
    figure_jobs = [
        ("metric/awgn_direct/amplitude_fixed_noise", "ber"),
        ("metric/awgn_direct/amplitude_fixed_noise", "paired_delta_ber"),
        ("metric/awgn_direct/amplitude_fixed_noise", "energy_gain"),
        ("metric/awgn_pilot/amplitude_fixed_noise", "ber"),
        ("metric/static_pilot/amplitude_fixed_noise", "ber"),
        ("metric/static_pilot/amplitude_fixed_noise", "energy_gain"),
        ("metric/rician_period32/amplitude_fixed_noise", "ber"),
        ("metric/rician_period32/amplitude_fixed_noise", "ser"),
        ("metric/rician_period32/amplitude_fixed_noise", "fer"),
        ("system/awgn", "ber"),
        ("system/awgn", "gain_joint_b0"),
        ("system/awgn", "runtime"),
        ("system/awgn", "information_efficiency"),
        ("system/static", "ber"),
        ("system/static", "gain_joint_b0"),
        ("system/static", "gain_joint_b1"),
        ("system/rician", "ber"),
        ("system/rician", "gain_joint_b0"),
        ("system/rician", "runtime"),
    ]
    with zipfile.ZipFile(FULL_ZIP) as full:
        names = set(full.namelist())
        for rel, stem in figure_jobs:
            group = (
                "BER"
                if stem == "ber"
                else "SER_FER"
                if stem in ("ser", "fer")
                else "energy_gain"
                if "gain" in stem or "delta" in stem
                else "comparisons"
            )
            block = "metric_isolation" if rel.startswith("metric/") else "full_receivers"
            for ext in ("png", "svg"):
                member = f"docs/research/figures/SCIENTIFIC_EXP_03B/{rel}/{stem}.{ext}"
                if member not in names or member not in figure_map:
                    raise FileNotFoundError(f"Missing required exported figure: {member}")
                raw = full.read(member)
                if sha_bytes(raw) != figure_map[member]["sha256"]:
                    raise ValueError(f"Source figure SHA mismatch: {member}")
                dest = STAGE / "04_FIGURES" / group / block / rel / f"{stem}.{ext}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                if ext == "png":
                    if (
                        not raw.startswith(b"\x89PNG\r\n\x1a\n")
                        or struct.unpack(">II", raw[16:24])[0] < 600
                    ):
                        raise ValueError(f"PNG content check failed: {member}")
                else:
                    ET.fromstring(raw)
                    if b"<path" not in raw and b"<polyline" not in raw:
                        raise ValueError(f"SVG has no vector geometry: {member}")
                original_hashes.append(
                    {
                        "source_path": member,
                        "included_path": dest.relative_to(STAGE).as_posix(),
                        "size_bytes": len(raw),
                        "sha256": sha_bytes(raw),
                    }
                )

    selected = write_samples(STAGE, sample_groups, SAMPLE_SEED)
    # Add sample/source digest record after samples have been copied.
    write_csv(
        STAGE / "07_VERIFICATION/original_file_hashes/original_file_hashes.csv", original_hashes
    )
    (STAGE / "00_START_HERE/CHATGPT_FINAL_SCIENTIFIC_REPORT_UK.md").write_text(
        make_report(metric_rows, system_rows, snapshot), encoding="utf-8"
    )
    copy_file(
        STAGE / "00_START_HERE/CHATGPT_FINAL_SCIENTIFIC_REPORT_UK.md",
        ROOT / "CHATGPT_FINAL_SCIENTIFIC_REPORT_UK.md",
    )
    summary = build_summary(snapshot, len(metric_rows), len(system_rows), gains)
    write_json(STAGE / "00_START_HERE/KEY_RESULTS_SUMMARY.json", summary)
    write_json(ROOT / "KEY_RESULTS_SUMMARY.json", summary)
    (STAGE / "requirements_audit.txt").write_text("numpy>=1.26\n", encoding="utf-8")
    # The verifier log is included and sealed in the archive manifest.
    log_path = STAGE / "07_VERIFICATION/integrity_checks/compact_audit_verifier.log"
    log_path.write_text(
        "Verifier execution will be recorded during package validation.\n", encoding="utf-8"
    )
    manifest = add_manifest(STAGE, full_status)
    first = subprocess.run(
        [sys.executable, str(STAGE / "verify_audit.py")],
        cwd=STAGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if first.returncode != 0:
        raise RuntimeError("Staging audit script failed:\n" + first.stdout + first.stderr)
    log_path.write_text(first.stdout + first.stderr, encoding="utf-8")
    manifest = add_manifest(STAGE, full_status)
    # Re-run after the log is fixed in size/content; then refresh manifest and perform final pass.
    second = subprocess.run(
        [sys.executable, str(STAGE / "verify_audit.py")],
        cwd=STAGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if second.returncode != 0:
        raise RuntimeError(
            "Staging audit script failed after log inclusion:\n" + second.stdout + second.stderr
        )
    log_path.write_text(second.stdout + second.stderr, encoding="utf-8")
    manifest = add_manifest(STAGE, full_status)
    OUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    zip_stage(STAGE, OUT_ZIP)
    if OUT_ZIP.stat().st_size > MAX_BYTES:
        raise RuntimeError(f"Compact ZIP is over byte limit: {OUT_ZIP.stat().st_size}")
    verify_zip(OUT_ZIP, manifest)

    extracted = ROOT / "tmp/exp03b_compact_audit_extracted_20261113"
    if extracted.exists():
        raise RuntimeError(f"Refusing to overwrite extraction directory: {extracted}")
    extracted.mkdir(parents=True)
    with zipfile.ZipFile(OUT_ZIP) as archive:
        archive.extractall(extracted)
    audit_root = extracted / TOP
    final_run = subprocess.run(
        [sys.executable, str(audit_root / "verify_audit.py")],
        cwd=audit_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if final_run.returncode != 0:
        raise RuntimeError(
            "Audit failed from extracted ZIP:\n" + final_run.stdout + final_run.stderr
        )
    # The included log is from the deterministic pre-ZIP audit. The final extracted run is printed externally.
    final_sha = sha_file(OUT_ZIP)
    print(
        json.dumps(
            {
                "archive_path": str(OUT_ZIP),
                "size_bytes": OUT_ZIP.stat().st_size,
                "size_mib": OUT_ZIP.stat().st_size / 1048576,
                "sha256": final_sha,
                "file_count": len(manifest["files"]),
                "sample_primary_trials": len(selected),
                "sample_npz_bytes": sum(x["array_size_bytes"] for x in selected),
                "trials": {
                    "metric": len(metric_rows),
                    "system": len(system_rows),
                    "total": len(all_ids),
                },
                "full_archive_status": full_status,
                "extracted_audit_exit": final_run.returncode,
                "extracted_audit_output": final_run.stdout,
                "included_audit_log": str(
                    (
                        STAGE / "07_VERIFICATION/integrity_checks/compact_audit_verifier.log"
                    ).relative_to(STAGE)
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
