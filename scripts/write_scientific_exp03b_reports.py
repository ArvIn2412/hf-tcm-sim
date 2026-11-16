"""Build the SCIENTIFIC-EXP-03B report set from the frozen independent analysis."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_PATH = ROOT / "outputs/scientific_exp03b/analysis/independent_analysis.json"
REPORT_DIR = ROOT / "docs/research"
FIGURE_DIR = REPORT_DIR / "figures/SCIENTIFIC_EXP_03B"
TABLE_DIR = REPORT_DIR / "tables/SCIENTIFIC_EXP_03B"
PROTOCOL_SHA = "d553e65fdad020f4887d252bb29bd88311b84b596bbba1e14fd4a806e71068c6"


def read_analysis() -> dict[str, Any]:
    data = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
    if data.get("protocol_sha256") != PROTOCOL_SHA:
        raise ValueError("Analysis protocol hash does not match the frozen 03B protocol")
    if not data.get("inference_uses_confirmatory_trials_only") or data.get("preflight_included"):
        raise ValueError("Analysis must contain confirmatory trials only")
    return data


def n(value: Any, digits: int = 6) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "так" if value else "ні"
    return f"{float(value):.{digits}g}".replace(".", ",")


def interval(value: Any, digits: int = 6) -> str:
    if not value:
        return "—"
    return f"[{n(value[0], digits)}; {n(value[1], digits)}]"


def get_ci(point: dict[str, Any], path: tuple[str, ...]) -> Any:
    result: Any = point.get("bootstrap_95ci", {})
    for key in path:
        result = result.get(key, {}) if isinstance(result, dict) else None
    return result if result != {} else None


def series_point_rows(data: dict[str, Any]):
    for scenario, sweeps in data["metric_isolation"].items():
        for sweep, series in sweeps.items():
            for point in series["point_summaries"]:
                yield scenario, sweep, point


def create_point_tables(data: dict[str, Any]) -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    metric_path = TABLE_DIR / "metric_isolation_all_points.csv"
    with metric_path.open("w", newline="", encoding="utf-8-sig") as stream:
        fields = [
            "scenario",
            "sweep",
            "gamma_b_d_db",
            "trials",
            "bits_per_arm",
            "euclidean_bit_errors",
            "euclidean_ber",
            "euclidean_ber_ci95_low",
            "euclidean_ber_ci95_high",
            "euclidean_pair_ser",
            "euclidean_pair_ser_ci95_low",
            "euclidean_pair_ser_ci95_high",
            "euclidean_fer",
            "hamming_bit_errors",
            "hamming_ber",
            "hamming_ber_ci95_low",
            "hamming_ber_ci95_high",
            "hamming_pair_ser",
            "hamming_pair_ser_ci95_low",
            "hamming_pair_ser_ci95_high",
            "hamming_fer",
            "delta_ber_euclidean_minus_hamming",
            "delta_ber_ci95_low",
            "delta_ber_ci95_high",
            "tx_energy_discrete_mean_per_trial",
            "energy_per_information_bit_discrete",
            "pilot_symbols_per_trial",
            "payload_symbols_per_trial",
            "noise_variance_complex",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for scenario, sweep, p in series_point_rows(data):
            ber_ci = get_ci(p, ("ber",))
            ser_ci = get_ci(p, ("ser_information_pairs",))
            delta_ci = get_ci(p, ("paired_delta_ber", "euclidean_minus_hamming"))
            writer.writerow(
                {
                    "scenario": scenario,
                    "sweep": sweep,
                    "gamma_b_d_db": p["gamma_db"],
                    "trials": p["trials"],
                    "bits_per_arm": p["bits"],
                    "euclidean_bit_errors": p["bit_errors"]["euclidean"],
                    "euclidean_ber": p["ber"]["euclidean"],
                    "euclidean_ber_ci95_low": (ber_ci or {}).get("euclidean", [None, None])[0],
                    "euclidean_ber_ci95_high": (ber_ci or {}).get("euclidean", [None, None])[1],
                    "euclidean_pair_ser": p["ser_information_pairs"]["euclidean"],
                    "euclidean_pair_ser_ci95_low": (ser_ci or {}).get("euclidean", [None, None])[0],
                    "euclidean_pair_ser_ci95_high": (ser_ci or {}).get("euclidean", [None, None])[
                        1
                    ],
                    "euclidean_fer": p["fer"]["euclidean"],
                    "hamming_bit_errors": p["bit_errors"]["hamming"],
                    "hamming_ber": p["ber"]["hamming"],
                    "hamming_ber_ci95_low": (ber_ci or {}).get("hamming", [None, None])[0],
                    "hamming_ber_ci95_high": (ber_ci or {}).get("hamming", [None, None])[1],
                    "hamming_pair_ser": p["ser_information_pairs"]["hamming"],
                    "hamming_pair_ser_ci95_low": (ser_ci or {}).get("hamming", [None, None])[0],
                    "hamming_pair_ser_ci95_high": (ser_ci or {}).get("hamming", [None, None])[1],
                    "hamming_fer": p["fer"]["hamming"],
                    "delta_ber_euclidean_minus_hamming": p["paired_delta_ber"][
                        "euclidean_minus_hamming"
                    ],
                    "delta_ber_ci95_low": (delta_ci or [None, None])[0],
                    "delta_ber_ci95_high": (delta_ci or [None, None])[1],
                    "tx_energy_discrete_mean_per_trial": p["tx_energy_discrete"] / p["trials"],
                    "energy_per_information_bit_discrete": p["tx_energy_discrete"] / p["bits"],
                    "pilot_symbols_per_trial": (
                        p["total_signal_symbols"] - p["payload_signal_symbols"]
                    )
                    / p["trials"],
                    "payload_symbols_per_trial": p["payload_signal_symbols"] / p["trials"],
                    "noise_variance_complex": p["noise_variance_complex"],
                }
            )

    system_path = TABLE_DIR / "full_system_all_points.csv"
    with system_path.open("w", newline="", encoding="utf-8-sig") as stream:
        fields = [
            "scenario",
            "gamma_b_d_db",
            "trials",
            "bits_per_arm",
            "arm",
            "bit_errors",
            "ber",
            "ber_ci95_low",
            "ber_ci95_high",
            "information_pair_errors",
            "pair_ser",
            "pair_ser_ci95_low",
            "pair_ser_ci95_high",
            "fer",
            "fer_ci95_low",
            "fer_ci95_high",
            "tx_energy_discrete_mean_per_trial",
            "energy_per_information_bit_discrete",
            "noise_variance_complex",
            "runtime_wall_s_per_frame",
            "runtime_cpu_s_per_frame",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for scenario, summary in data["full_system_comparison"].items():
            for p in summary["point_summaries"]:
                for arm in summary["arms"]:
                    ber_ci = get_ci(p, ("ber", arm))
                    ser_ci = get_ci(p, ("ser_information_pairs", arm))
                    fer_ci = get_ci(p, ("fer", arm))
                    runtime = summary["runtime"][arm]
                    writer.writerow(
                        {
                            "scenario": scenario,
                            "gamma_b_d_db": p["gamma_db"],
                            "trials": p["trials"],
                            "bits_per_arm": p["bits"],
                            "arm": arm,
                            "bit_errors": p["bit_errors"][arm],
                            "ber": p["ber"][arm],
                            "ber_ci95_low": (ber_ci or [None, None])[0],
                            "ber_ci95_high": (ber_ci or [None, None])[1],
                            "information_pair_errors": p["pair_errors"][arm],
                            "pair_ser": p["ser_information_pairs"][arm],
                            "pair_ser_ci95_low": (ser_ci or [None, None])[0],
                            "pair_ser_ci95_high": (ser_ci or [None, None])[1],
                            "fer": p["fer"][arm],
                            "fer_ci95_low": (fer_ci or [None, None])[0],
                            "fer_ci95_high": (fer_ci or [None, None])[1],
                            "tx_energy_discrete_mean_per_trial": p["tx_energy_discrete"]
                            / p["trials"],
                            "energy_per_information_bit_discrete": p["tx_energy_discrete"]
                            / p["bits"],
                            "noise_variance_complex": p["noise_variance_complex"],
                            "runtime_wall_s_per_frame": runtime["wall_seconds_mean"],
                            "runtime_cpu_s_per_frame": runtime["cpu_seconds_mean"],
                        }
                    )


def metric_gain_table(data: dict[str, Any]) -> str:
    lines = [
        "| Сценарій A | Ціль BER | Eᵦ,d Евклід | Eᵦ,d Хемінг | Виграш, дБ | 95% paired bootstrap-ДІ | Валідні перетини | Лінійна інтерполяція, 95% ДІ | Висновок |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for scenario, sweeps in data["metric_isolation"].items():
        gain_targets = sweeps["amplitude_fixed_noise"]["metric_gain"]
        for target in ("0.05", "0.01", "0.001"):
            item = gain_targets[target]
            boot = item["bootstrap"]["log_ber"]
            linear = item["bootstrap"]["linear_ber"]["gain_db_ci95"]
            energy = item["required_energy_per_information_bit_discrete"]
            status = item["precision_assessment"]["status"]
            gain = n(item["gain_db_log_ber"], 5)
            lines.append(
                f"| `{scenario}` | {n(float(target))} | {n(energy.get('euclidean'), 5)} | {n(energy.get('hamming'), 5)} | {gain} | {interval(boot['gain_db_ci95'], 5)} | {n(boot['valid_fraction'] * 100, 4)}% | {interval(linear, 5)} | `{status}` |"
            )
    return "\n".join(lines)


def system_gain_table(data: dict[str, Any]) -> str:
    lines = [
        "| Канал B | Ціль BER | Separate arm | Eᵦ,d Joint | Eᵦ,d Separate | Gain Joint/Separate, дБ | 95% ДІ | Валідні перетини | Статус |",
        "|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for scenario, series in data["full_system_comparison"].items():
        for target in ("0.05", "0.01", "0.001"):
            for arm, item in series["energy_gain"][target].items():
                energy = item["required_energy_per_information_bit_discrete"]
                boot = item["bootstrap"]["log_ber"]
                lines.append(
                    f"| `{scenario}` | {n(float(target))} | `{arm.upper()}` | {n(energy.get('euclidean'), 5)} | {n(energy.get('hamming'), 5)} | {n(item['gain_db_log_ber'], 5)} | {interval(boot['gain_db_ci95'], 5)} | {n(boot['valid_fraction'] * 100, 4)}% | `{item['precision_assessment']['status']}` |"
                )
    return "\n".join(lines)


def metric_points_markdown(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    labels = {
        "awgn_direct": "AWGN direct control (без pilot frontend)",
        "awgn_pilot": "AWGN із pilot frontend",
        "static_pilot": "Статичний multipath [0,3], pilot frontend",
        "rician_period32": "Rician AR(1), cadence 32 — первинний режим",
        "rician_period8": "Rician AR(1), cadence 8 — sensitivity arm",
    }
    for scenario, sweeps in data["metric_isolation"].items():
        for sweep_name in ("amplitude_fixed_noise", "noise_fixed_amplitude"):
            label = (
                "зміна амплітуди, σ²c=0,05"
                if sweep_name == "amplitude_fixed_noise"
                else "зміна шуму, A=1"
            )
            chunks.extend(
                [
                    f"### {labels[scenario]} — {label}",
                    "",
                    "| γᵦ,d, дБ | n | Помилки бітів E/H | BER E [95% ДІ] | BER H [95% ДІ] | ΔBER=E−H [95% ДІ] | Парний SER E/H | FER E/H |",
                    "|---:|---:|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for p in sweeps[sweep_name]["point_summaries"]:
                ber_ci = p["bootstrap_95ci"]["ber"]
                delta_ci = p["bootstrap_95ci"]["paired_delta_ber"]["euclidean_minus_hamming"]
                chunks.append(
                    f"| {n(p['gamma_db'], 5)} | {p['trials']} | {p['bit_errors']['euclidean']}/{p['bit_errors']['hamming']} | "
                    f"{n(p['ber']['euclidean'], 5)} [{interval(ber_ci['euclidean'], 4)}] | "
                    f"{n(p['ber']['hamming'], 5)} [{interval(ber_ci['hamming'], 4)}] | "
                    f"{n(p['paired_delta_ber']['euclidean_minus_hamming'], 5)} [{interval(delta_ci, 4)}] | "
                    f"{n(p['ser_information_pairs']['euclidean'], 5)}/{n(p['ser_information_pairs']['hamming'], 5)} | "
                    f"{n(p['fer']['euclidean'], 4)}/{n(p['fer']['hamming'], 4)} |"
                )
            chunks.append("")
    return "\n".join(chunks)


def system_points_markdown(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    for scenario, series in data["full_system_comparison"].items():
        arms = series["arms"]
        chunks.extend(
            [
                f"### Канал `{scenario}` — повні системи, F=256, 100 парних кадрів/точку",
                "",
                "| γᵦ,d, дБ | "
                + " | ".join(f"BER {a.upper()} / парний SER / FER" for a in arms)
                + " |",
                "|---:|" + "---:|" * len(arms),
            ]
        )
        for p in series["point_summaries"]:
            values = [
                f"{n(p['ber'][a], 5)} / {n(p['ser_information_pairs'][a], 5)} / {n(p['fer'][a], 4)}"
                for a in arms
            ]
            chunks.append(f"| {n(p['gamma_db'], 5)} | " + " | ".join(values) + " |")
        chunks.append("")
    return "\n".join(chunks)


def figure_manifest() -> dict[str, Any]:
    entries = []
    for path in sorted(FIGURE_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".svg"}:
            continue
        raw = path.read_bytes()
        if path.suffix.lower() == ".png":
            if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) < 10_000:
                raise ValueError(f"PNG failed signature/content-size check: {path}")
            width = int.from_bytes(raw[16:20], "big")
            height = int.from_bytes(raw[20:24], "big")
            if width < 1000 or height < 600:
                raise ValueError(f"PNG resolution below 1000x600: {path}")
            dimensions: dict[str, Any] = {"width": width, "height": height}
        else:
            decoded = raw.decode("utf-8")
            if "<svg" not in decoded or "<path" not in decoded or len(raw) < 2000:
                raise ValueError(f"SVG failed vector-content check: {path}")
            dimensions = {"vector": True}
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                **dimensions,
            }
        )
    if len([x for x in entries if x["path"].endswith(".png")]) != 59:
        raise ValueError("Expected 59 PNG exports")
    if len([x for x in entries if x["path"].endswith(".svg")]) != 59:
        raise ValueError("Expected 59 SVG exports")
    out = FIGURE_DIR / "FIGURE_EXPORTS_MANIFEST.json"
    out.write_text(
        json.dumps({"figures": entries, "count": len(entries)}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {"count": len(entries), "path": out.relative_to(ROOT).as_posix()}


def write_report(name: str, text: str) -> None:
    (REPORT_DIR / name).write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    data = read_analysis()
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    create_point_tables(data)
    fig = figure_manifest()
    metric_table = metric_gain_table(data)
    system_table = system_gain_table(data)
    metric_full = metric_points_markdown(data)
    system_full = system_points_markdown(data)

    figure_ref = "figures/SCIENTIFIC_EXP_03B"
    write_report(
        "SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md",
        rf"""# SCIENTIFIC-EXP-03B — ізольоване порівняння метрик

## Висновок

За фіксованих умов A-E/A-H евклідова метрика має нижчий виміряний BER у всіх досліджених точках. Енергетичне порівняння можна підтвердити тільки там, де обидві криві перетинають target, наявні наперед задані суміжні точки з достатньою кількістю помилок, а не менше 95% paired cluster-bootstrap повторів мають допустимі перетини.

Основний поріг BER=0,05 дає статистично придатні модельні оцінки для AWGN direct, AWGN pilot і static multipath. Для primary Rician AR(1) pilot cadence 32 обидві криві лишаються вище 0,05 у всій сітці, тому **ENERGY_GAIN_NOT_ESTIMABLE**. Sensitivity cadence 8 перетинає поріг лише евклідова крива; парний виграш також не оцінюється.

**ΔBER = BER(Euclidean) − BER(Hamming)**; від'ємне значення сприяє евклідовій метриці. ДІ — 95% paired cluster bootstrap за незалежними кадрами, 5 000 повторів.

## Енергетичний результат, amplitude sweep

{metric_table}

Для енергетичних цілей застосовано log₁₀(BER)-інтерполяцію між фактичними суміжними точками. Додатний gain = 10log₁₀(Eᵦ,d,H/Eᵦ,d,E). Лінійна BER-інтерполяція наведена як sensitivity. Немає екстраполяції. Eᵦ,d — дискретна енергія на корисний інформаційний біт, з урахуванням переданої pilot-енергії в сумарній енергії; це не каліброване фізичне Eb/N0.

## Інтерпретація Rician AR(1)

У primary cadence-32 режимі діапазон евклідового BER становить {n(min(p["ber"]["euclidean"] for p in data["metric_isolation"]["rician_period32"]["amplitude_fixed_noise"]["point_summaries"]), 5)}–{n(max(p["ber"]["euclidean"] for p in data["metric_isolation"]["rician_period32"]["amplitude_fixed_noise"]["point_summaries"]), 5)}, а Хемінгового — {n(min(p["ber"]["hamming"] for p in data["metric_isolation"]["rician_period32"]["amplitude_fixed_noise"]["point_summaries"]), 5)}–{n(max(p["ber"]["hamming"] for p in data["metric_isolation"]["rician_period32"]["amplitude_fixed_noise"]["point_summaries"]), 5)}. На найвищій енергії ΔBER становить {n(data["metric_isolation"]["rician_period32"]["amplitude_fixed_noise"]["point_summaries"][-1]["paired_delta_ber"]["euclidean_minus_hamming"], 6)} з 95% ДІ {interval(data["metric_isolation"]["rician_period32"]["amplitude_fixed_noise"]["point_summaries"][-1]["bootstrap_95ci"]["paired_delta_ber"]["euclidean_minus_hamming"], 6)}. Це підтверджує нижчий BER евклідового декодера в межах виміряної сітки, але не визначає енергію для BER=0,05, 0,01 або 0,001 і не доводить асимптотичний error floor.

Cadence 8 — попередньо зафіксована sensitivity-гілка з більшими pilot overhead; вона не замінює primary cadence 32.

## Точки кривих

Усі фактичні точки для обох sweep-ів, разом із BER, SER інформаційних пар, FER, парним ΔBER та bootstrap-ДІ, наведено нижче. Машинно-читана таблиця: [`metric_isolation_all_points.csv`](tables/SCIENTIFIC_EXP_03B/metric_isolation_all_points.csv).

{metric_full}

## Графіки

- AWGN direct BER: [{figure_ref}/metric/awgn_direct/amplitude_fixed_noise/ber.png](figures/SCIENTIFIC_EXP_03B/metric/awgn_direct/amplitude_fixed_noise/ber.png) · [SVG](figures/SCIENTIFIC_EXP_03B/metric/awgn_direct/amplitude_fixed_noise/ber.svg)
- AWGN pilot BER: [{figure_ref}/metric/awgn_pilot/amplitude_fixed_noise/ber.png](figures/SCIENTIFIC_EXP_03B/metric/awgn_pilot/amplitude_fixed_noise/ber.png) · [SVG](figures/SCIENTIFIC_EXP_03B/metric/awgn_pilot/amplitude_fixed_noise/ber.svg)
- Static multipath BER: [{figure_ref}/metric/static_pilot/amplitude_fixed_noise/ber.png](figures/SCIENTIFIC_EXP_03B/metric/static_pilot/amplitude_fixed_noise/ber.png) · [SVG](figures/SCIENTIFIC_EXP_03B/metric/static_pilot/amplitude_fixed_noise/ber.svg)
- Rician primary BER: [{figure_ref}/metric/rician_period32/amplitude_fixed_noise/ber.png](figures/SCIENTIFIC_EXP_03B/metric/rician_period32/amplitude_fixed_noise/ber.png) · [SVG](figures/SCIENTIFIC_EXP_03B/metric/rician_period32/amplitude_fixed_noise/ber.svg)
- Rician sensitivity BER: [{figure_ref}/metric/rician_period8/amplitude_fixed_noise/ber.png](figures/SCIENTIFIC_EXP_03B/metric/rician_period8/amplitude_fixed_noise/ber.png) · [SVG](figures/SCIENTIFIC_EXP_03B/metric/rician_period8/amplitude_fixed_noise/ber.svg)

Всі рисунки та їхні SHA-256 перелічені в [{fig["path"]}](figures/SCIENTIFIC_EXP_03B/FIGURE_EXPORTS_MANIFEST.json).
""",
    )

    write_report(
        "SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md",
        f"""# SCIENTIFIC-EXP-03B — порівняння повних інформаційних технологій

Цей блок порівнює повні приймачі й не ізолює вплив метрики. Joint має адаптивну евклідову обробку; B0 — роздільну жорстку демодуляцію та метрику Хемінга; B1 — каналозалежну роздільну обробку з публічними номінальними taps у статичному сценарії. Тому Joint/B0 і Joint/B1 не можна називати чистим виграшем евклідової метрики.

## Оцінювання енергетичного виграшу

{system_table}

Для target 0,05 AWGN Joint/B0 має оцінку {n(data["full_system_comparison"]["awgn"]["energy_gain"]["0.05"]["b0"]["gain_db_log_ber"], 5)} дБ, 95% ДІ {interval(data["full_system_comparison"]["awgn"]["energy_gain"]["0.05"]["b0"]["bootstrap"]["log_ber"]["gain_db_ci95"], 5)} та {n(data["full_system_comparison"]["awgn"]["energy_gain"]["0.05"]["b0"]["bootstrap"]["log_ber"]["valid_fraction"] * 100, 4)}% допустимих bootstrap-перетинів. Це модельний дискретний системний контраст.

Для static multipath точкові оцінки Joint/B0 і Joint/B1 на target 0,05 дорівнюють відповідно {n(data["full_system_comparison"]["static"]["energy_gain"]["0.05"]["b0"]["gain_db_log_ber"], 5)} дБ та {n(data["full_system_comparison"]["static"]["energy_gain"]["0.05"]["b1"]["gain_db_log_ber"], 5)} дБ. Частки допустимих повторів {n(data["full_system_comparison"]["static"]["energy_gain"]["0.05"]["b0"]["bootstrap"]["log_ber"]["valid_fraction"] * 100, 4)}% та {n(data["full_system_comparison"]["static"]["energy_gain"]["0.05"]["b1"]["bootstrap"]["log_ber"]["valid_fraction"] * 100, 4)}% нижчі за заморожений поріг 95%, тому остаточний gain і 95% ДІ не встановлені: **INSUFFICIENT_PRECISION**.

У Rician AR(1) Joint перетинає BER=0,05, але B0 не перетинає його на виміряній сітці; системний виграш не оцінюється без екстраполяції. B1 у Rician не підтримується й не запускався. У AWGN target 0,01 та нижче немає спільного допустимого перетину для Joint/B0.

## Runtime

Середній виміряний wall/CPU час на кадр F=256:

| Канал | Приймач | Wall, с/кадр | CPU, с/кадр |
|---|---|---:|---:|
"""
        + "\n".join(
            f"| `{scenario}` | `{arm.upper()}` | {n(vals['wall_seconds_mean'], 6)} | {n(vals['cpu_seconds_mean'], 6)} |"
            for scenario, series in data["full_system_comparison"].items()
            for arm, vals in series["runtime"].items()
        )
        + f"""

Runtime залежить від цієї програмної реалізації та середовища виконання; він не є виміром затримки готового радіоприймача.

## Повні криві

Нижче наведено всі точки BER / SER інформаційних пар / FER. Повна таблиця також доступна в [`full_system_all_points.csv`](tables/SCIENTIFIC_EXP_03B/full_system_all_points.csv).

{system_full}

Візуалізації: `figures/SCIENTIFIC_EXP_03B/system/{{awgn,static,rician}}/`.
""",
    )

    write_report(
        "SCIENTIFIC_EXP_03B_ENERGY_GAIN.md",
        rf"""# SCIENTIFIC-EXP-03B — енергетичні оцінки

## Визначення

Для дискретних transmitted samples обчислено \(E_{{tx,d}}=\sum_n |x[n]|^2\), \(E_{{b,d}}=E_{{tx,d}}/N_{{payload\ bits}}\) та \(\gamma_{{b,d}}=10\log_{{10}}(E_{{b,d}}/\sigma_c^2)\). У primary A pilot cadence 32 кадр F=1024 містить 128 pilot і 896 інформаційних 8PSK-елементів (1792 корисні біти); pilot енергія включена в чисельник, а payload біти — у знаменник. Для cadence 8 pilot overhead більший; результати винесено окремо. У блоці B F=256 і задана сітка вимірюється за дискретною проєктною конвенцією.

\(\gamma_{{b,d}}\) — нормована дискретна шкала. Частота дискретизації, фізична форма імпульсу в смузі, шумова спектральна густина, matched filter та зв'язок sample-domain complex variance із фізичним \(N_0\) не встановлені; тому фізичне Eb/N0 не підтверджене.

## A: ізольований ефект метрики

{metric_gain_table(data)}

Ціль 0,05: точкові модельні оцінки підтверджують нижчу потрібну дискретну енергію евклідового декодера у AWGN direct, AWGN із pilot frontend та статичному multipath із pilot frontend. У primary Rician cadence 32 та для target 0,01/0,001 валідної парної оцінки gain немає. Для cadence 8 лише E перетинає 0,05, отже gain також не оцінюється.

## B: повна технологія Joint проти Separate

{system_gain_table(data)}

Тільки AWGN Joint/B0 при BER=0,05 пройшов заморожені критерії статистичної точності. Static point estimates при BER=0,05 не пройшли 95% crossing fraction; Rician та частина нижчих target не мають парного перетину. Інформаційна перевага B1 (відомі номінальні taps) відрізняється від практичного оцінювання каналу.

## Порівняння зі статейними 1,5 дБ

Стаття повідомляє 1,5 дБ за власним визначенням помилки, енергії й умов каналу. Цей експеримент використовує іншу project-defined дискретну шкалу, окремі A і B контрасти, F та pilot accounting. Точкова B AWGN оцінка 1,666 дБ має bootstrap інтервал, що включає 1,5 дБ, однак це не відтворення статті й не підтверджує її авторський результат. Жоден результат не підганявся до 1,5 дБ; `paper_exact:false` залишається незмінним.
""",
    )

    metric_trials = sum(p["trials"] for _, _, p in series_point_rows(data))
    system_trials = sum(
        len(s["point_summaries"]) * s["point_summaries"][0]["trials"]
        for s in data["full_system_comparison"].values()
    )
    metric_hash_statuses = [
        s["amplitude_fixed_noise"]["provenance"]["verification"]["independent_count_replay"]
        for s in data["metric_isolation"].values()
    ]
    system_hash_statuses = [
        s["provenance"]["verification"]["independent_count_replay"]
        for s in data["full_system_comparison"].values()
    ]
    write_report(
        "SCIENTIFIC_EXP_03B_STATISTICAL_VALIDATION.md",
        rf"""# SCIENTIFIC-EXP-03B — статистична валідація

## Обсяг і цілісність даних

- A, ізольовані метрики: {metric_trials:,} завершених парних trials (5 сценаріїв × два sweep-и; 300 незалежних trial clusters на energy point).
- B, повні системи: {system_trials:,} завершених парних кадрів (AWGN 2900, static 2900, Rician 2500; 100 кадрів на energy point).
- Разом: {metric_trials + system_trials:,} confirmatory trials. Pilot/preflight не входить до інференції.
- Frozen protocol SHA-256: `{PROTOCOL_SHA}`; аналіз обмежений confirmatory observations.
- Analysis JSON SHA-256: `{hashlib.sha256(ANALYSIS_PATH.read_bytes()).hexdigest()}`.
- Усі 13 confirmatory study manifests мають planned=completed і status=completed; trial IDs у межах кожної серії унікальні.
- Незалежний replay counts: A `{"PASS" if all(x == "PASS" for x in metric_hash_statuses) else "FAIL"}`; B `{"PASS" if all(x == "PASS" for x in system_hash_statuses) else "FAIL"}`. B nested record/array hashes, checkpoint chain і парні observation hashes пройшли loader verification.
- Системні сітки згруповано за замороженим `point_index`, а не exact float equality; виміряна \(\gamma_{{b,d}}\) перевірялась на допуск 1e−9 дБ. Це усунуло некоректне дроблення однієї енергетичної точки через floating-point roundoff без зміни records.

## Методи

BER = помилкові decoded payload bits / усі payload bits; SER = частка помилкових двобітових інформаційних пар; FER = частка кадрів щонайменше з однією помилкою. A paired \(\Delta BER=BER_E-BER_H\). У B парні різниці визначені між приймачами на одному observation.

Для інтервалів кривих використано 5 000 paired independent-trial cluster bootstrap повторів. Для gain bootstrap resamples усієї незалежної парної реалізації, не окремих бітів. Первинне перетинання — log₁₀(BER) проти виміряної енергії; linear BER наведено як sensitivity. Немає згладжування чи екстраполяції. Gain проходить критерій лише за обох суміжних bracketing points, не менше 200 errors на кожному arm у bracket і ≥95% допустимих bootstrap перетинів.

## Невизначеність та обмеження

Нульові виміряні помилки не трактуються як BER=0 probability; графіки мають нижню межу/попередження, а перетин target з нульовою помилкою в bracket є невизначеним за protocol. Rician cadence-32 A демонструє plateau у межах наявної сітки, але protocol не допускає називати його асимптотичним error floor. Серійна залежність усередині кадру не маскується псевдоресемплінгом бітів: одиницею bootstrap є trial/frame cluster.

Два confirmatory каталоги містять 6 272 661 612 байтів первинних даних разом із manifests і checkpoints (5,842 GiB). Незавершений повторний full scan через повільний OneDrive I/O було зупинено; trial outputs не змінено. Попередній незалежний analyzer provenance підтверджує повний array recount усіх metric records, парність і енергію для A, а для B — nested SHA manifests, checkpoint chain та independent count replay. Архівний пакет повторно перевірить CRC і SHA-256 кожного включеного файла.
""",
    )

    write_report(
        "SCIENTIFIC_EXP_03B_ARTICLE_COMPARISON.md",
        r"""# SCIENTIFIC-EXP-03B — зіставлення з науковою статтею

## Межі зіставлення

Головне джерело: І. Яковів, О. Гриненко, «Інформаційна технологія спільної процедури демодуляції та декодування радіосигналу» (2026), `references/Яковів_Гриненко_2026_в7 27-10-26(4).docx`; SHA-256 `4e41d33a898d2bfec2118a0cd11d3879ac01d4095264b14f7123bc9840d5f1e3`. Допоміжний аудит відповідності: [`ARTICLE_COMPLIANCE_FINAL_AUDIT.md`](ARTICLE_COMPLIANCE_FINAL_AUDIT.md). У ньому зафіксовано розбіжності формули метрики, оцінювача, шумової моделі та означення source error probability.

## Порівняння з 1,5 дБ

1,5 дБ — значення, повідомлене у статті. У SCIENTIFIC-EXP-03B метрика ізольована окремо від повного системного алгоритму; енергетична шкала \(\gamma_{{b,d}}\) дискретна й не відкалібрована як фізичне Eb/N0. BER target 0,05 використано як проектний критерій, а не як доведене ототожнення з авторським \(p^*_n\). Тому збіг чисел чи включення 1,5 у CI не означає відтворення авторського експерименту.

Результати A на target 0,05: AWGN direct — 2,867 дБ [2,820; 2,914]; AWGN із pilot frontend — 2,296 дБ [2,159; 2,424]; static multipath [0,3] — 2,437 дБ [2,337; 2,533]. Primary Rician AR(1) — `ENERGY_GAIN_NOT_ESTIMABLE`. Це власні модельні контрасти на заданій дискретній шкалі.

Повний системний B AWGN Joint/B0 дає 1,666 дБ [1,292; 2,002] при BER=0,05, що охоплює 1,5 дБ чисельно, але метрики/приймачі, моделі каналу, дискретна шкала та джерельне означення помилки не тотожні; отже **ARTICLE_1.5_DB_CONFIRMED = NO**. Статичні B estimates не пройшли crossing-fraction gate; у Rician немає парного target перетину для Joint/B0.

## Допустимий висновок

Дослід підтверджує перевагу метрики Евкліда над Хемінга за спільного pilot frontend на AWGN та static multipath у межах цільового BER=0,05. За Rician AR(1) нижчий BER Евкліда спостерігається в усіх виміряних енергетичних точках, однак досягнення BER=0,05 у primary metric arms не спостерігалося, тож енергетичний gain невизначений. Повний Joint receiver має окремий системний результат, який не приписується одній метриці. `paper_exact:false` не змінювалося.
""",
    )

    write_report(
        "THESIS_CHAPTER_4_FIGURES_AND_TABLES.md",
        f"""# Розділ 4 — реєстр рисунків і таблиць

Усі рисунки — з фактичних завершених confirmatory records. PNG — растровий експорт 300 dpi (перевірено мінімум 1000×600 px); SVG містить vector path. Повний каталог: `{figure_ref}/`; SHA-256 і розміри наведено у [`{fig["path"]}`](figures/SCIENTIFIC_EXP_03B/FIGURE_EXPORTS_MANIFEST.json). Усього 59 PNG + 59 SVG.

## Основні рисунки

| № | Назва | Файл PNG | Векторний SVG |
|---:|---|---|---|
| 4.1 | BER, AWGN direct, A-E/A-H | `{figure_ref}/metric/awgn_direct/amplitude_fixed_noise/ber.png` | `{figure_ref}/metric/awgn_direct/amplitude_fixed_noise/ber.svg` |
| 4.2 | BER, AWGN pilot frontend, A-E/A-H | `{figure_ref}/metric/awgn_pilot/amplitude_fixed_noise/ber.png` | `{figure_ref}/metric/awgn_pilot/amplitude_fixed_noise/ber.svg` |
| 4.3 | BER, static multipath [0,3], A-E/A-H | `{figure_ref}/metric/static_pilot/amplitude_fixed_noise/ber.png` | `{figure_ref}/metric/static_pilot/amplitude_fixed_noise/ber.svg` |
| 4.4 | BER, Rician AR(1), primary cadence 32 | `{figure_ref}/metric/rician_period32/amplitude_fixed_noise/ber.png` | `{figure_ref}/metric/rician_period32/amplitude_fixed_noise/ber.svg` |
| 4.5 | BER, Rician cadence-8 sensitivity | `{figure_ref}/metric/rician_period8/amplitude_fixed_noise/ber.png` | `{figure_ref}/metric/rician_period8/amplitude_fixed_noise/ber.svg` |
| 4.6 | Потрібна енергія та виграш метрики з 95% ДІ, AWGN із пілотним фронтендом | `{figure_ref}/metric/awgn_pilot/amplitude_fixed_noise/energy_gain.png` | `{figure_ref}/metric/awgn_pilot/amplitude_fixed_noise/energy_gain.svg` |
| 4.7 | BER повних систем AWGN | `{figure_ref}/system/awgn/ber.png` | `{figure_ref}/system/awgn/ber.svg` |
| 4.8 | BER повних систем static multipath | `{figure_ref}/system/static/ber.png` | `{figure_ref}/system/static/ber.svg` |
| 4.9 | BER повних систем Rician | `{figure_ref}/system/rician/ber.png` | `{figure_ref}/system/rician/ber.svg` |
| 4.10 | Час виконання повних приймачів, статичний канал | `{figure_ref}/system/static/runtime.png` | `{figure_ref}/system/static/runtime.svg` |

Примітка: конкретна кількість/назва рисунка в остаточному тексті дисертації може бути перенумерована за вимогами кафедри. У деяких графіках target BER позначено, але немає виміряного перетину; це навмисно — не є підставою для екстраполяції.

## Таблиці

| Таблиця | Вміст | Машинно-читаний файл |
|---|---|---|
| 4.1 | A: усі енергетичні точки двох sweep-ів, BER/SER/FER/ΔBER/ДІ | [`metric_isolation_all_points.csv`](tables/SCIENTIFIC_EXP_03B/metric_isolation_all_points.csv) |
| 4.2 | A: Eᵦ,d і gain за target BER та bootstrap-підтримка | [`SCIENTIFIC_EXP_03B_ENERGY_GAIN.md`](SCIENTIFIC_EXP_03B_ENERGY_GAIN.md) |
| 4.3 | B: усі криві BER/SER/FER і arms | [`full_system_all_points.csv`](tables/SCIENTIFIC_EXP_03B/full_system_all_points.csv) |
| 4.4 | B: енергетичний gain і час на кадр | [`SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md`](SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md) |
""",
    )

    write_report(
        "THESIS_CHAPTER_4_FINAL_DRAFT.md",
        r"""# РОЗДІЛ 4. ІМІТАЦІЙНЕ ДОСЛІДЖЕННЯ ТА ОЦІНЮВАННЯ ЕФЕКТИВНОСТІ

## 4.1 Мета та методика імітаційного моделювання

Метою дослідження було окремо оцінити вплив branch metric у декодері Вітербі та порівняти повні приймальні інформаційні технології. У контрольованому блоці A порівнювали декодери A-E (евклідова метрика) і A-H (метрика Хемінга). Пара формувалася на одному інформаційному кадрі, реалізації каналу й шуму та спільному результаті pilot frontend/equalizer. Кодова решітка, η=20, початковий стан і правила traceback не змінювались; відрізнялась метрика переходу. Окремий AWGN direct control не містив pilot/equalizer і не змішувався з pilot-frontend результатом.

У блоці B порівнювались повний адаптивний Joint receiver, роздільний B0 і, лише для підтримуваного статичного каналу, B1 із публічними номінальними taps. Цей контраст є системним: у ньому відрізняються оцінювання/оброблення каналу, а не тільки метрика.

Для A використано F=1024, 300 незалежних кадрів на кожну з 38 комбінацій сценарію й енергетичного рівня окремо для amplitude- та noise-sweep. У cadence-32 primary frontend 128 із 1024 сигналових елементів є pilot; корисне навантаження становить 896 елементів або 1792 інформаційні біти. У B використано F=256 і 100 незалежних кадрів на точку: AWGN 29 точок 0–14 дБ кроком 0,5 дБ; static multipath — така сама сітка; Rician — 25 точок 0–24 дБ кроком 1 дБ. Загалом завершено 22 800 пар A і 8 300 кадрів B, у сумі 31 100 confirmatory trials. Pilot/preflight дані не включались.

Для кожного кадру перераховано \(BER=N_{err,b}/N_{payload,b}\), \(SER_{pair}=N_{err,pair}/N_{payload,pair}\) і \(FER=N_{frames,error}/N_{frames}\). Парна різниця A визначена як \(\Delta BER=BER_E-BER_H\). Статистичну невизначеність оцінено 5 000-кратним paired cluster bootstrap із ресемплінгом цілих незалежних кадрів. Не виконувалась ресемплінгова псевдореплікація окремих бітів.

Дискретну енергію отримано безпосередньо з transmitted samples:

\[E_{tx,d}=\sum_n|x[n]|^2,\qquad E_{b,d}=\frac{E_{tx,d}}{N_{payload,b}},\qquad \gamma_{b,d}=10\log_{10}\frac{E_{b,d}}{\sigma_c^2}.\]

Pilot energy входить до \(E_{tx,d}\), тоді як знаменник містить тільки корисні інформаційні біти. Ця нормована sample-domain шкала є проєктною; фізичне Eb/N0 не встановлено.

## 4.2 Завадостійкість за різних метрик

У AWGN direct при BER=0,05 A-E потребував \(E_{b,d}=0,09694\), A-H — 0,18758, що відповідає модельному виграшу 2,8668 дБ (95% ДІ [2,8197; 2,9140], 100% допустимих bootstrap перетинів). При спільному pilot frontend AWGN оцінка становила 2,2960 дБ [2,1586; 2,4236]. Для статичного multipath [0,3] вона дорівнювала 2,4373 дБ [2,3375; 2,5335]. Усі наведені target 0,05 порівняння пройшли зафіксований критерій мінімуму помилок і bootstrap-перетинів.

У primary Rician AR(1) у кожній виміряній енергетичній точці BER A-E нижчий за A-H, і на найвищій точці \(\Delta BER=-0,05911\) (95% paired ДІ [−0,06052; −0,05770]). Водночас обидва BER залишились вище 0,05 у сітці; енергетичний gain для Rician не оцінюється. Отже нижчий BER у скінченному виміряному діапазоні не означає, що можна визначити горизонтальний енергетичний зсув цільового перетину.

Ціль 0,01 не дала допустимої парної оцінки gain: на частині сценаріїв лише A-E перетнув target, тоді як A-H не перетнув її; деякі окремі point estimates для E не замінюють парний gain. Ціль 0,001 була exploratory і не мала валідного спільного перетину.

## 4.3 Оцінювання енергетичної ефективності

Модельний gain визначався як \(G_d=10\log_{10}(E_{b,d,H}/E_{b,d,E})\), з log₁₀(BER)-інтерполяцією між фактичними сусідніми energy points. Лінійна BER-інтерполяція використовувалась лише як sensitivity analysis; екстраполяція заборонена. Для AWGN direct target 0,05 лінійний sensitivity дає 2,8295 дБ [2,8295; 2,8998]; для AWGN pilot — 2,278–2,493 дБ; static — 2,315–2,506 дБ. Інтервали та точкові оцінки залишаються в межах одного порядку і не змінюють висновок про додатний gain у цих сценаріях.

У Rician target-перетину немає, тому необхідна енергія та gain позначаються `ENERGY_GAIN_NOT_ESTIMABLE`. Високе BER і plateau в скінченній сітці не доводять асимптотичний error floor.

## 4.4 Багатопроменевість і райсівські завмирання

У статичному сценарії використано два промені із затримками [0,3] відліків; порівняння A застосовувало спільний pilot frontend та ISI equalization. У Rician AR(1) сценарії використано два промені, K=[4,1], середні потужності [1;0,25], фази LOS [0;0,7] рад, затримки [0,3] і \(\rho=0,98\) на комплексний відлік, як зафіксовано проєктним протоколом. Це саме модельні умови SCIENTIFIC-EXP-03B, а не універсальний опис КХ-каналу.

Для cadence-8 sensitivity у Rician A-E досягає BER=0,05 приблизно за \(\gamma_{b,d}=14,437\) дБ, але A-H не досягає target в межах виміряної сітки. Через це gain лишається невизначеним. Більший навчальний overhead є окремою причиною не об'єднувати cadence-8 із primary cadence-32.

## 4.5 Повний Joint проти роздільного приймання

У системному блоці B AWGN target 0,05 Joint/B0 дає 1,6664 дБ (95% paired bootstrap-ДІ [1,2921; 2,0016], 99,02% допустимих перетинів). На статичному multipath точкові Joint/B0 і Joint/B1 gain дорівнюють 5,4928 та 2,2388 дБ, але crossing fractions 94,68% і 94,94% не досягли заданого 95% порогу; тому ДІ та підтверджений gain не наводяться. B1 користувався номінальними відомими статичними taps і має іншу інформацію про канал.

У Rician Joint досягає target BER=0,05, тоді як B0 не досягає його до верхньої точки сітки; joint-system gain не оцінюється. Для B1 у Rician протокол не передбачав запуск. Це системні висновки, не ізольований вплив Евклідової метрики.

Середній receiver runtime на кадр F=256: AWGN Joint 0,807 с проти B0 0,0162 с; static Joint 3,198 с, B0 0,0156 с, B1 0,0581 с; Rician Joint 3,766 с проти B0 0,0159 с. Це runtime даної реалізації на даному host; не апаратна затримка. Значна обчислювальна вартість Joint є практичним компромісом.

## 4.6 Зіставлення зі статтею та обмеження

Стаття повідомляє виграш 1,5 дБ. У цьому досліді отримано інші, чітко розділені оцінки: A метрик та B повних систем. B AWGN точковий інтервал включає число 1,5 дБ, але це не є відтворенням статті, бо source error event/denominator, адаптивний оцінювач, канал/шум і фізичне енергетичне нормування не доведені тотожними. Результати не підганялись.

Основні обмеження: project-defined discrete \(\gamma_{b,d}\), скінченні сітки й кадри, дві задані multipath/fading моделі, Rician target non-crossing, системні static CI не пройшли crossing fraction gate, а B1 має каналозалежну інформаційну перевагу. Це відтворюване модельне дослідження для дисертації, але не доказ універсального енергетичного виграшу фізичних КХ-каналів або підтвердження статейних 1,5 дБ.

## Висновки розділу

За контрольованого спільного frontend евклідова branch metric дає статистично нижчий BER і вимірюваний позитивний discrete-energy gain на AWGN та static multipath при BER=0,05. На Rician AR(1) BER евклідового декодера нижчий у всіх точках, проте цільових перетинів для обох metric arms немає, тому енергетичний gain не встановлюється. Повний Joint receiver показав системний gain проти B0 в AWGN, тоді як інші системні estimates або не мають спільного перетину, або не пройшли заздалегідь зафіксований precision threshold. Фізичний Eb/N0 та відтворення статейного результату 1,5 дБ не підтверджені.

Числові таблиці всіх точок і рисунки наведені в [`SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md`](SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md), [`SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md`](SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md) та [`SCIENTIFIC_EXP_03B_THESIS_FIGURES_AND_TABLES.md`](SCIENTIFIC_EXP_03B_THESIS_FIGURES_AND_TABLES.md).
""",
    )

    write_report(
        "SCIENTIFIC_EXP_03B_FINAL_REPORT.md",
        rf"""# SCIENTIFIC-EXP-03B — фінальний звіт

## Статус

**SCIENTIFIC_EXP_03B_PARTIAL** — усі 31 100 confirmatory trial records завершені та незалежно агреговані; науковий висновок позитивний для частини контрольованих порівнянь, але повний перелік заявлених target/channel gains не оцінюється через відсутні перетини або не досягнуту bootstrap-підтримку. Нова статистична серія не запускалася.

| Показник | Висновок |
|---|---|
| Парні A-E/A-H observations та pilot frontend | VERIFIED за протоколом, trial provenance і однаковими hash-полями записів |
| Евклідова проти Хемінга, target BER=0,05 | Підтверджена енергетична перевага у AWGN direct, AWGN pilot і static pilot |
| Primary Rician AR(1), metric gain | `ENERGY_GAIN_NOT_ESTIMABLE`; обидва arms не перетинають target 0,05 |
| B Joint/B0, AWGN, BER=0,05 | 1,6664 дБ; 95% ДІ [1,2921; 2,0016]; 99,02% valid crossings |
| B static gains | Point estimates наявні, але не проходять наперед визначений ≥95% bootstrap gate |
| B Rician gain | `NOT_ESTIMABLE`; B0 не перетинає target |
| Фізичне Eb/N0 | NOT_VALIDATED |
| Результат статті 1,5 дБ | Не відтворено як статейний результат; числовий збіг CI не є доказом відтворення |
| `paper_exact` | `false`, незмінено |

## Протокол і дані

Confirmatory протокол SHA-256: `{PROTOCOL_SHA}`. Блок A: 22 800 парних кадрів, п'ять зафіксованих metric scenarios, два sweep-и, F=1024, 300 clusters на точку. Блок B: 8 300 paired frames, F=256, 100 на точку; AWGN 2900, static 2900, Rician 2500. Усі counts, seeds, arrays, hashes і series manifests залишені незмінними.

## Результати

### A — ізольований ефект метрики

{metric_gain_table(data)}

ΔBER=Euclidean−Hamming. На Rician cadence 32 primary при найвищій точці \(\gamma_{{b,d}}=37,6108\) дБ: BER(E)=0,12332, BER(H)=0,18243; ΔBER=−0,05911, 95% ДІ [−0,06052; −0,05770]. Проте обидві криві лишились вище BER=0,05, тож горизонтальний енергетичний gain не визначається.

### B — повні системи

{system_gain_table(data)}

### Стаття та фізична інтерпретація

Статейні 1,5 дБ використані тільки як зовнішнє порівняльне значення. Дискретне \(\gamma_{{b,d}}\) не має встановленого зв'язку з фізичним Eb/N0. Порівняння Joint/B0/B1 оцінює сукупні відмінності систем оброблення, а не чистий ефект метрики.

## Артефакти

- Метрики: [`SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md`](SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md).
- Системи: [`SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md`](SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md).
- Енергія: [`SCIENTIFIC_EXP_03B_ENERGY_GAIN.md`](SCIENTIFIC_EXP_03B_ENERGY_GAIN.md).
- Статистика: [`SCIENTIFIC_EXP_03B_STATISTICAL_VALIDATION.md`](SCIENTIFIC_EXP_03B_STATISTICAL_VALIDATION.md).
- Стаття: [`SCIENTIFIC_EXP_03B_ARTICLE_COMPARISON.md`](SCIENTIFIC_EXP_03B_ARTICLE_COMPARISON.md).
- Розділ 4: [`THESIS_CHAPTER_4_FINAL_DRAFT.md`](THESIS_CHAPTER_4_FINAL_DRAFT.md).
- Реальні точки: `tables/SCIENTIFIC_EXP_03B/*.csv`.
- PNG/SVG: `figures/SCIENTIFIC_EXP_03B/` (59 пар, маніфест з hash).
""",
    )

    print(
        json.dumps(
            {
                "protocol_sha256": PROTOCOL_SHA,
                "metric_points": sum(
                    len(sweep["point_summaries"])
                    for _, sweeps in data["metric_isolation"].items()
                    for sweep in sweeps.values()
                ),
                "system_points": sum(
                    len(s["point_summaries"]) for s in data["full_system_comparison"].values()
                ),
                "figure_files": fig["count"],
                "figure_manifest": fig["path"],
                "reports": 8,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
