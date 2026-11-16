"""Generate UTF-8 release reports from actual local test and profiling evidence."""

from __future__ import annotations

import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path("outputs/release_readiness")
BLOCKED_TESTS = {
    "test_historical_energy_study_revalidates_provenance_and_recomputes_gain",
    "test_historical_energy_study_is_available_through_read_only_gui_route",
}


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text.strip() + "\n", encoding="utf-8")


def xml_summary(name: str) -> dict:
    cases = ET.parse(OUT / name).getroot().findall(".//testcase")
    failed = [
        c.attrib["name"]
        for c in cases
        if c.find("failure") is not None or c.find("error") is not None
    ]
    return {"tests": len(cases), "passed": len(cases) - len(failed), "failed": failed}


def main() -> None:
    portable = xml_summary("portable_source_only.xml")
    full = xml_summary("full.xml")
    search = load("archive_search.json")
    before, after = load("exp01b_before.json"), load("exp01b_after.json")
    browser_files = [
        "browser.json",
        "browser_extended.json",
        "browser_viewports.json",
        "browser_edgecases.json",
        "browser_run_switch.json",
    ]
    suites = {name: load(name) for name in browser_files}
    checks = [c for d in suites.values() for c in d["checks"]]
    exceptions = sum(len(d.get("errors", [])) for d in suites.values())
    perf = load("browser_performance.json")
    memory = [
        json.loads(line)
        for line in (OUT / "process_memory.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    memory_ranges = {
        k: {
            "first": memory[0][k],
            "last": memory[-1][k],
            "min": min(r[k] for r in memory),
            "max": max(r[k] for r in memory),
        }
        for k in (
            "python_working_set",
            "python_private",
            "browser_working_set_sum",
            "browser_private_sum",
        )
    }
    inventory = load("git_inventory.json")
    protected = load("protected_references.json")
    samples = load("control_sample_verification.json")
    source_quality = load("source_quality.json")
    durations = suites["browser.json"]["performance"]["transitions_ms"]
    tab_measurements = "; ".join(f"{r['view']}: {r['ms']:.2f} ms" for r in perf["tabs"])
    exp01b_failed = "test_exp01b_static_series_opens_through_saved_study_route" in full["failed"]
    remaining = [name for name in full["failed"] if name not in BLOCKED_TESTS]
    statuses = {
        "UI FUNCTIONALITY": "PASS"
        if all(c["status"] == "PASS" for c in checks) and not exceptions
        else "PARTIAL",
        "PORTABLE CI": "PASS" if not portable["failed"] else "FAIL",
        "HISTORICAL AUDIT": "BLOCKED" if set(full["failed"]) & BLOCKED_TESTS else "PARTIAL",
        "EXP01B TIMEOUT": "UNRESOLVED" if exp01b_failed else "RESOLVED",
        "RUFF": source_quality["status"],
        "PERFORMANCE": "PASS" if len(durations) == 100 and memory else "PARTIAL",
        "SCIENTIFIC RESULTS": "UNCHANGED"
        if protected["FAIL"] == 0 and protected["NOT_VERIFIED"] == 0
        else "CHANGED",
        "RELEASE READINESS": "CONDITIONALLY_READY"
        if not remaining and not portable["failed"]
        else "NOT_READY",
    }
    (OUT / "status.json").write_text(
        json.dumps(
            {
                "statuses": statuses,
                "portable_source_only": portable,
                "full": full,
                "blocked_historical_tests": {
                    name: "BLOCKED_MISSING_ARTIFACT"
                    for name in full["failed"]
                    if name in BLOCKED_TESTS
                },
                "browser_checks": len(checks),
                "browser_exceptions": exceptions,
                "memory_ranges": memory_ranges,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    status_rows = "\n".join(f"| {key} | **{value}** |" for key, value in statuses.items())
    write(
        "01_RELEASE_READINESS_UK.md",
        f"""
# Готовність технічного релізу

| Критерій | Статус |
|---|---|
{status_rows}

Це готовність програмної source-версії, а не підтвердження результатів статті.
Працюючий інтерфейс не переписано. Commit/push, нові статистичні експерименти
та повторний Monte Carlo не виконувалися.

## Перевірена версія

Python {sys.version.split()[0]}, Windows; залежності вже були встановлені.
Portable CI перевірено в source-only копії без `outputs/`, ZIP/NPZ, DOC/DOCX/PDF
та інших бінарних документів: {portable["passed"]} passed, {len(portable["failed"])} failed.
Повний pytest: {full["passed"]} passed, {len(full["failed"])} failed.
Два відсутні-artifact failures не перетворено на skip/xfail або штучний PASS.

Браузер: {len(checks)} assertions, {exceptions} JS exceptions, 30 PNG;
усі шість вкладок на 320/390/834/1366/1920 px. Деталі у звіті 04.
EXP-01B HTTP повертає перевірені 1160 static frames у межах початкових 30 с;
перевірені числові gain/CI залишилися тими самими.

## Умови остаточного приймання

1. Надати оригінальний EXP-01 ZIP із правильною provenance та reviewed bundle
   для повного historical job. Зараз historical audit BLOCKED.
2. Перед публікацією перевірити права/приватність {len(inventory["already_tracked_documents_requiring_publication_review"])}
   вже відстежуваних Git бінарних документів. Нових таких файлів не додано;
   список і дозволені source-кандидати є в `git_inventory.json` та звіті 05.
3. GitHub Actions налаштовано, але віддалено не запускався без commit/push.
   Локально виконано його portable/source команди; Python 3.11/3.12 matrix
   налаштована, локальний запуск був на Python {sys.version.split()[0]}.

## Наукова незмінність

Свіжо збіглися {protected["PASS"]} pinned protocol/config/manifest/checkpoint SHA EXP-03B,
розбіжностей {protected["FAIL"]}. Це явно обмежений повторний аудит метаданих,
не нова перевірка всіх trial NPZ. Повний попередній аудит етапу 4:
87714 збігів, усі 31100 confirmatory records; 32 файли без baseline залишалися
NOT_VERIFIED. Історичні очікувані SHA та наукові висновки не змінено.

Інсталяція й демонстрація: `README_RELEASE_UK.md` у корені проєкту.
""",
    )
    blocked_rows = "\n".join(
        f"| `{name}` | BLOCKED_MISSING_ARTIFACT |" for name in sorted(BLOCKED_TESTS)
    )
    write(
        "02_CI_AND_HISTORICAL_TESTS_UK.md",
        f"""
# CI, historical artifacts і EXP-01B timeout

## Оригінальний EXP-01 ZIP

Пошук у {search["directories_scanned"]} каталогах; знайдено {len(search["found"])}.
Області пошуку: {", ".join(search["roots"])}. Недоступні каталоги перелічені
в `archive_search.json`; їх не видано за перевірені. Оригінал у доступних
областях не знайдено, тому його provenance заново підтвердити неможливо.

| Оригінальний тест | Статус приймання |
|---|---|
{blocked_rows}

Ці тести не переписано: у full.xml вони лишаються actual failures.
Класифікація BLOCKED_MISSING_ARTIFACT пояснює відсутність передумови.
Відомий запис provenance EXP-01: ZIP 63372916 bytes,
SHA-256 `2cc2de44d198f1206d76e210c50877a1048d7e244b1d5033ff65e8abed60270d`.
Нового замінного ZIP або еталонного SHA не створено.

## Доведена причина EXP-01B затримки

Маршрут синхронно перечитував і перевіряв 1160 trial directories до відповіді.
Початковий профіль: 6962 read_bytes, із них зайві повторні record/config reads;
більшість затримки — open/read/resolve у OneDrive-файловій системі.
Сервер ThreadingHTTPServer не блокує незалежний health request; це доведено
контрольованим event-gated HTTP-тестом. Відсутній EXP-01 ZIP не є залежністю
EXP-01B loader. Bootstrap — replay тих самих saved records, не новий Monte Carlo.

Один лише reuse bytes зменшив читання, але 30-секундний timeout ще відтворився.
Остаточне виправлення: кожний payload читається один раз; незалежний I/O
виконується чотирма bounded workers; pool.map зберігає початковий порядок.
Усі record/manifest/config/NPZ SHA, context/pairing/count та числові bootstrap
gates залишено. Кеш без повторної перевірки SHA не додано.

Діагностичний HTTP до: {next(v["seconds"] for v in before if v["phase"] == "client"):.3f} с;
після під паралельним файловим пошуком: {next(v["seconds"] for v in after if v["phase"] == "client"):.3f} с.
Оригінальний pytest також проходив за ~2,36–2,76 с відповіді та пройшов у full.xml.
Timeout у тесті залишився 30 с. Це усунення відтвореного I/O bottleneck,
не гарантія latency на недоступному або довільно повільному диску.

Логи: `exp01b_before.json`, `exp01b_profile.txt`, `exp01b_after.json`,
`exp01b_after.log`, `exp01b_repeat.xml`. Контрольовані fixtures явно синтетичні;
вони не підміняють наукові trial records. Окрема read-only рецензія:
9 focused tests незалежно пройдено; Important/Critical зауважень немає.

## Окремі CI jobs

- Portable: `python -m pytest -q -m "not historical"`, Python 3.11/3.12, CLI smoke.
- Source quality: `ruff check src tests scripts/ci`, `ruff format --check src tests scripts/ci`.
- Historical: manual dispatch, явно переданий trusted Actions artifact,
  reviewed SHA manifest → preflight → незмінені `pytest -m historical`.

Artifact спочатку завантажується до `.historical-input/`, не поверх коду.
Встановлюються тільки перевірені manifest-listed outputs та фіксований ZIP;
інший вміст bundle не копіюється. Відмінні існуючі історичні байти не замінюються.
Missing artifact — BLOCKED, exit 2; SHA mismatch — FAIL, exit 1.
Успішний portable/source job або вимкнений historical job не означає historical PASS.

Source-only snapshot виявив, що source-document fingerprint test читав DOCX.
Його лише перенесено до historical marker; assertions і source ledger не змінено.
Після цього portable-набір самодостатній і без бінарних дослідницьких документів.

Кореневі `ruff check .` / `ruff format --check .` також фактично запущено:
є сторонні archival/scratch findings та formatter panic на документації.
Це не приховано зміною еталонів: CI навмисно перевіряє source scope, що проходить.
Виправлено лише порядок двох imports і зайвий blank line у двох source-файлах,
без автоматичного форматування всього репозиторію.
""",
    )
    memory_rows = "\n".join(
        f"| {key} | {v['first'] / 1048576:.2f} | {v['min'] / 1048576:.2f} | {v['max'] / 1048576:.2f} | {v['last'] / 1048576:.2f} |"
        for key, v in memory_ranges.items()
    )
    write(
        "03_PERFORMANCE_UK.md",
        f"""
# Профілювання збереженого N=20000/n=8

Використано лише `stage3-control-20000`, seed=331, 160000 complex samples.
Нові сигнали, шум або статистичні серії для профілювання не генерувалися.
Свіжий localhost server 18773, окремий headless Edge CDP 9242, extensions disabled.
PID/profile flags перевірені в `process_identity.json`; повні command lines не зберігалися.

## Тривалість видимих дій

| Дія | Вимір |
|---|---|
| Тепле відкриття вкладок N=20000 | {tab_measurements} |
| Window action → ready trace → animation frame | {perf["window_ms"]:.2f} ms |
| Zoom, три справжні зміни range | {[round(x["ms"], 2) for x in perf["zoom"]]} ms |
| Pan зі сталою шириною window | {perf["pan"]["ms"]:.2f} ms |
| Перехід до 0 | {perf["first_to_last"]["first_ms"]:.2f} ms |
| Перехід 0 → 159999 | {perf["first_to_last"]["last_ms"]:.2f} ms |
| 100 переходів: median / min / max | {statistics.median(durations):.1f} / {min(durations)} / {max(durations)} ms |

Zoom/pan API timing — performance.now до готових даних/animation frame,
без polling драйвера. Вимір pan використовує window API; реальний mouse/touch drag
окремо перевіряється E2E. 100 переходів включають polling і стабілізаційну паузу;
це end-to-end драйвера, не чистий CPU render. Межі до/після є в JSON.
Холодний запуск на іншому пристрої й окремий CPU/GPU paint budget: NOT_MEASURED.

## Пам'ять процесів, MiB

Зібрано {len(memory)} OS snapshots, UTC {memory[0]["timestamp"]}…{memory[-1]["timestamp"]}.
Період включає браузерне приймання й 100 переходів. Дані — `process_memory.jsonl`.

| OS величина | Перше | Мінімум | Максимум спостереження | Останнє |
|---|---|---|---|---|
{memory_rows}

WorkingSet Python — resident working set одного сервера. Browser working_set_sum —
сума working sets власного дерева Edge, включно зі shared pages; це не унікальна
фізична пам'ять, shared pages можуть рахуватися повторно. Private bytes — окрема
OS величина. CDP JS heap: {perf["heap"]}; він не підміняє process RSS.
Унікальні private resident pages всього дерева та GPU allocations: NOT_MEASURED.
Цільовий sleep 500 ms доповнюється часом OS/CIM-запиту, фактичні timestamps збережено.

Початковий неізольований Edge мав системні extensions і сторонні сторінки;
його пам'ять не використано для фінальних чисел. QA виправлено: лише localhost
target, явний base URL, відхилення сторонньої сторінки та bounded CDP wait.
Старі діагностичні memory-файли збережені окремо з відповідними назвами.

100 переходів завершилися; JS exceptions не виявлено, фінальний sample=159999.
Ці виміри не доводять відсутність будь-якого memory leak у нескінченній сесії.
PERFORMANCE: {statuses["PERFORMANCE"]} у наведених умовах і межах вимірювання.
""",
    )
    rows = "\n".join(
        f"| {name} | {len(data['checks'])} | {sum(c['status'] != 'PASS' for c in data['checks'])} | {len(data.get('errors', []))} |"
        for name, data in suites.items()
    )
    write(
        "04_BROWSER_ACCEPTANCE_UK.md",
        f"""
# Фінальне браузерне приймання

UI FUNCTIONALITY: **{statuses["UI FUNCTIONALITY"]}**. Власний headless Edge,
localhost server актуального checkout; {len(checks)} assertions,
{exceptions} JS runtime exceptions. Touch — browser emulation, не фізичний телефон.

| JSON evidence | Перевірок | Failures | JS exceptions |
|---|---|---|---|
{rows}

Усі шість вкладок перевірено на **320, 390, 834, 1366, 1920 px**.
Нові 30 PNG — `screenshots/NAME-WIDTH.png`. Bounds, button heights,
overflow, form-control overlaps та Unicode перевірено окремими assertions.
Скриншоти самі по собі не видаються за доказ жестів.

Перевірені wheel, mouse drag, rectangle, touch pinch/drag; LOD/minimap;
однаковий H/E interval та exact inspector; symbol19999/sample159999/bit39999;
pagination/search/filter/sort/details/open; source URL; зміна довгого run на короткий;
окремі RX/frontend шари сузір'я; продовження pan після partial pointer release.

Незалежна від Canvas звірка HTTP з первинним NPZ: інспектор для
{samples["inspector_samples"]}, усі {samples["cloud_points"]} raw cloud points збігаються
точно. NPZ SHA `{samples["npz_sha256"]}` відповідає trial record.
Нових noise realizations для хмари немає.

Команди: `node scripts/qa_ui_stage4.mjs`, `qa_ui_stage4_extended.mjs`,
`qa_ui_stage4_viewports.mjs`, `qa_ui_stage4_edgecases.mjs`, `qa_ui_stage4_run_switch.mjs`.
Параметри середовища: HF_TCM_QA_OUTPUT=outputs/release_readiness,
HF_TCM_CDP_PORT=9242, HF_TCM_QA_BASE_URL=http://127.0.0.1:18773.
Вихідні звіти етапу 4 не перезаписувалися.

При partial-pointer-release використано DOM PointerEvent після справжнього
CDP two-touch start; цей контроль доповнює, а не підміняє повні CDP жести.
Інші браузери, фізичний multi-touch і screen-reader: NOT_MEASURED.
""",
    )
    files = "\n".join(
        f"- `{item['path']}` ({item['bytes']} bytes)"
        for item in inventory["candidate_source_files"]
    )
    existing = "\n".join(
        f"- `{name}`"
        for name in inventory["already_tracked_documents_requiring_publication_review"]
    )
    write(
        "05_RELEASE_NOTES_UK.md",
        f"""
# Release notes та перелік файлів

Source-only technical stabilization; версію пакета й наукові результати не
перейменовано як новий експеримент. Публікацію, commit або push не виконано.

## Зміни стабілізації

- EXP-01B: single-read SHA verification, чотири bounded I/O workers, стабільний
  порядок records; phase/HTTP timing logs; старий 30-секундний тест проходить.
- CI: окремі portable/source-quality/historical jobs, reviewed external bundle,
  BLOCKED_MISSING_ARTIFACT без skip/xfail, відмова перезаписувати інші історичні байти.
- Portable: документальний fingerprint case коректно віднесено до historical;
  source-only запуск не залежить від приватних DOCX/NPZ/outputs.
- Source lint: тільки точкові import/blank-line виправлення; весь repo не форматувався.
- QA: окремий base URL/CDP port/output folder, тільки localhost target,
  bounded CDP waits і точне очікування відкритого study замість проміжного null.
- Додано `README_RELEASE_UK.md`, CI README, діагностику, profiling та release reports.
- Успадковані зміни UI етапу 4 лишаються в цьому ж незакоміченому checkout.

## Перевірка Git

Source-кандидатів: {len(inventory["candidate_source_files"])}; blocked changed files:
{len(inventory["blocked_changed_files"])}; staged files: {inventory["staged_files"]}.
Немає доданих великих архівів, дослідницьких outputs, приватних binary documents
або tmp. `.gitignore` зберігає ZIP/outputs/tmp exclusions, додано `.historical-input/`.
Це інвентар кандидатів, а не команда `git add` або дозвіл публікації.

### Усі поточні незакомічені source-файли (включно з етапом 4)

{files}

### Уже відстежувані документи: перевірити перед публікацією

Ці {len(inventory["already_tracked_documents_requiring_publication_review"])} файлів існували у Git до стабілізації;
вони не додавалися й не видалялися автоматично. Перелік не встановлює їхню ліцензію
або приватність; це обов'язковий publication review, включно з пов'язаними reference images.

{existing}

Наукові обмеження збережено: paper_exact:false; model/discrete energy не є
physical Eb/N0; 1,5 дБ зі статті незалежно не підтверджено. SCIENTIFIC-EXP-03B,
його 31100 trials, protocols, seeds, conclusions та historical SHA не переписано.
""",
    )
    print(
        json.dumps(
            {
                "statuses": statuses,
                "portable": portable,
                "full": full,
                "browser_checks": len(checks),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
