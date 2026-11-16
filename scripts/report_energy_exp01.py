"""Generate the research reports from completed, independently audited records."""

import json
from collections import Counter
from pathlib import Path

R = Path("outputs/scientific_exp_01")
D = Path("docs/research")
D.mkdir(exist_ok=True)
g = json.loads((R / "analysis/gains.json").read_text())
agg = json.loads((R / "analysis/aggregates.json").read_text())
rows = [
    json.loads(p.read_text())
    for p in R.glob("*/*/*/p*/t*/record.json")
    if (p.parent / "manifest.json").exists()
]
rows = [r for r in rows if r["phase"] in {"pilot", "confirmatory", "long"}]
counts = Counter((r["phase"], r["scenario"], r["sweep"]) for r in rows)
bits = sum(r["bits"] for r in rows)
phase_status = {
    p: json.loads((R / (p + "_execution.json")).read_text())
    for p in ["pilot", "confirmatory", "long"]
    if (R / (p + "_execution.json")).exists()
}
if (R / "pilot_initial_execution.json").exists():
    phase_status["pilot"] = json.loads((R / "pilot_initial_execution.json").read_text())
intro = "# SCIENTIFIC-EXP-01: експериментальна оцінка енергоефективності\n\nСтатус: **SCIENTIFIC_EXP_01_PARTIAL**. Фізичний Eb/N0 не калібрований; paper_exact:false. Погоджені squared Euclidean metric та complex AWGN використані без зміни алгоритмів.\n\n"
count_table = (
    "| Фаза | Канал | Sweep | Completed pairs | Information bits |\n|---|---|---|---:|---:|\n"
    + "\n".join(
        f"| {p} | {sc} | {sw} | {n} | {sum(r['bits'] for r in rows if (r['phase'], r['scenario'], r['sweep']) == (p, sc, sw))} |"
        for (p, sc, sw), n in sorted(counts.items())
    )
)
gaintable = "| Фаза | Канал | Sweep | Target BER | Порівняння | Eb Joint | Eb Separate | Gain dB | 95% CI dB | Valid bootstrap fraction | Статус |\n|---|---|---|---:|---|---:|---:|---:|---|---:|---|\n"
for a in g["analyses"]:

    def v(x):
        return "—" if x is None else f"{x:.5g}"

    energies = a.get("required_reference_eb_d", {})
    ci = a["bootstrap"]["confidence_interval_db"]
    req = a["required_gamma_db"]
    ej = None if req["joint"] is None else 10 ** (req["joint"] / 10)
    es = None if req["separate"] is None else 10 ** (req["separate"] / 10)
    gaintable += f"| {a['phase']} | {a['scenario']} | {a['sweep']} | {a['target_ber']} | Joint/{a['separate_arm']} | {v(ej)} | {v(es)} | {v(a['gain_db'])} | {ci if ci else 'не визначено'} | {a['bootstrap']['valid_fraction']:.3f} | {a['status']} |\n"
curve = "| Фаза / канал / sweep | γ_b,d (дБ) | Trials | Joint BER | B0 BER | B1 BER | Joint pair SER | B0 pair SER | Joint FER | B0 FER |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
for group in agg["groups"]:
    for p in group["points"]:
        fer = {
            arm: sum(
                r["frame_errors"][arm]
                for r in rows
                if r["phase"] == group["phase"]
                and r["scenario"] == group["scenario"]
                and r["sweep"] == group["sweep"]
                and r["gamma_db"] == p["gamma_db"]
            )
            / p["trials"]
            for arm in p["ber"]
        }
        curve += f"| {group['phase']}/{group['scenario']}/{group['sweep']} | {p['gamma_db']:g} | {p['trials']} | {p['ber']['joint']:.7g} | {p['ber']['b0']:.7g} | {p['ber'].get('b1', '—')} | {p['ser']['joint']:.7g} | {p['ser']['b0']:.7g} | {fer['joint']:.5g} | {fer['b0']:.5g} |\n"
method = (R / "METHOD.md").read_text("utf8")
rt = "\n".join(
    f"- {p}: {s['status']}, {s['completed_or_verified_pairs']} пар, {s['elapsed_seconds']:.2f} с у збереженому execution report."
    for p, s in phase_status.items()
)
main = (
    intro
    + "## Фактичний обсяг\n\n"
    + count_table
    + "\n\nПілот, основна серія й довгі контролі не об’єднувалися в одну вибірку. Усі наведені точки — completed pairs; planned main grid має680 пар.\n\n"
    + rt
    + "\n\n## Енергетичні результати\n\n"
    + gaintable
    + "\n\nЕнергії у таблиці наведені за reference σ_c²=1, у дискретних нормованих одиницях. Для amplitude sweep вони фактично змінювалися; для noise sweep це equivalent required energy, а фактична E_b,d=4 була постійною. Додатний Gain означає нижчу required energy Joint. PARTIAL — point estimate без валідного unconditional 95% bootstrap CI; conditional quantiles не підміняють CI.\n\n## BER/SER/FER\n\n"
    + curve
    + "\n\n## Нормування, методика й відтворення\n\n"
    + method
    + "\n\n## Обмеження й відповіді\n\n1. Перевагу оцінено лише там, де є виміряні перетини обох кривих. Point estimate без CI не є статистично достатнім доказом переваги.\n2. Таблиці розділяють AWGN, static і Rician; pilot Rician лишається exploratory.\n3–5. Фактичні величини gain, required energy і 95% CI наведені вище; «—» означає відсутність допустимого перетину.\n6. Gamma normalization однакова, але trial streams для двох sweeps незалежні. Точні same-seed waveform/decoded-bit тести пройшли AWGN/static/Rician. Відмінності отриманих mean curves — не доказ порушення масштабування й не доказ еквівалентності; таблиця sweep_comparison.json показує observed differences.\n7. Високий B0 BER у fading узгоджується з відсутністю його phase/ISI компенсації; скінченна сітка не доводить математичний asymptotic floor. Якщо немає crossing: ENERGY_GAIN_NOT_ESTIMABLE_FOR_TARGET.\n8. Інтерполяційна чутливість linear-BER збережена окремо як sensitivity, не заміняє preregistered log-BER analysis.\n9. 1,5 дБ статті не підтверджено. ARTICLE_1_5_DB_INSUFFICIENT_DATA; модельні дБ не фізичний gain.\n10. Залишаються відмінності active estimator, mapping, фізичної нормалізації та повних авторських параметрів.\n\n## Перевірки\n\nНезалежний replay: outputs/scientific_exp_01/independent_replay.json. Точні test/lint/fingerprint logs — outputs/scientific_exp_01/logs/. Криві PNG/SVG та їх manifest — analysis/plots/. Нові trial outputs не переписують історичні artifacts.\n\n## Відтворення\n\n`python scripts/run_energy_exp01.py pilot`, `python scripts/run_energy_exp01.py confirmatory`, `python scripts/run_energy_exp01.py long`. Existing completed records перевіряються й пропускаються; кожний додатковий запуск відновлення має свій wall budget, його не запускали автоматично для продовження main series після її ліміту. Аналіз: `python scripts/analyze_energy_exp01.py --replicates 1000`; audit: `python scripts/audit_energy_exp01.py`.\n"
)
(D / "SCIENTIFIC_EXP_01_FINAL_REPORT.md").write_text(main, "utf8")
(D / "SCIENTIFIC_EXP_01_ENERGY_GAIN_RESULTS.md").write_text(
    intro
    + gaintable
    + "\n\n"
    + curve
    + "\n\nСтатуси ESTIMATED/PARTIAL/NOT_ESTIMABLE стосуються модельної дискретної енергії. Усі CI pointwise. Неперетин target не замінено extrapolation.",
    "utf8",
)
(D / "SCIENTIFIC_EXP_01_STATISTICAL_VALIDATION.md").write_text(
    intro
    + count_table
    + "\n\n"
    + method
    + "\n\nПовні paired cluster bootstrap outputs, validity fractions, nonzero required-energy brackets і conditional-only quantiles наведені у analysis/gains.json. Перевірка errors та SHA independent від receiver функцій збережена в independent_replay.json. Zero BER не є точною нульовою ймовірністю.",
    "utf8",
)
(D / "SCIENTIFIC_EXP_01_ARTICLE_COMPARISON.md").write_text(
    "# SCIENTIFIC-EXP-01: порівняння зі статтею\n\nARTICLE_1_5_DB_INSUFFICIENT_DATA.\n\nСтаття 2026 повідомляє1,5дБ. Тут прийняті squared residual sum, complex iid AWGN і discrete γ_b,d — погоджені проєктні рішення, а не буквальна тотожність джерела. Приймач Joint використовує survivor-specific adaptive estimator; B0 не компенсує multipath; B1 має exact public static taps. Тому Joint/B0 — системний контраст повних алгоритмів.\n\nSource p*=0.05 не доведено тотожним decoded information-bit BER. Source N*=20000 не встановлює всіх denominator/realization правил. Поточна робота дає independent F256 clusters і окремі F20000 controls. Фізичні sample period/noise PSD/matched filter HF calibration не визначені. Фактичні модельні оцінки й невизначеність див. SCIENTIFIC_EXP_01_ENERGY_GAIN_RESULTS.md; вони не підтверджують і не спростовують фізичний source gain. paper_exact:false.\n",
    "utf8",
)
print("Reports", len(rows), "pairs", bits, "bits")
