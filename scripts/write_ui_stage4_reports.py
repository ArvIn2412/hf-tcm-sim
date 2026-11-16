"""Write stage-4 reports from measured evidence using explicit UTF-8."""

import json
import statistics
from pathlib import Path

OUT = Path("outputs/ui_interactivity_stage4")


def read(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text.strip() + "\n", encoding="utf-8")


def main() -> None:
    browser = read("browser.json")
    extended = read("browser_extended.json")
    viewport = read("browser_viewports.json")
    api = read("api_performance.json")
    history = read("historical.json")
    memory = read("server_memory.json")
    browser_perf = read("browser_performance.json")
    suites = {
        "Основний": browser,
        "Додатковий": extended,
        "П'ять ширин": viewport,
        "Крайові жести": read("browser_edgecases.json"),
        "Перемикання запусків": read("browser_run_switch.json"),
    }
    if not any(c["name"] == "100_transitions" for c in browser["checks"]):
        suites["100 переходів"] = {
            "checks": [
                c for c in read("stress_browser.json")["checks"] if c["name"] == "100_transitions"
            ],
            "errors": [],
        }
    matrix = []
    for suite, data in suites.items():
        for check in data["checks"]:
            matrix.append(f"| {suite} | `{check['name']}` | {check['status']} |")
    failures = [c for d in suites.values() for c in d["checks"] if c["status"] != "PASS"]
    times = browser.get("performance", {}).get("transitions_ms", [])
    if not times:
        times = read("stress_browser.json")["performance"]["transitions_ms"]
    counts = {suite: len(data["checks"]) for suite, data in suites.items()}
    write(
        "01_FINAL_IMPLEMENTATION_UK.md",
        f"""
# Реалізація та фактичний статус етапу 4

**IMPLEMENTATION: PARTIAL — функціональність UI реалізована; повне регресійне
приймання залишається незавершеним через наведені нижче історичні failures.**

Продовжено існуючу Scientific Workspace. Наукові алгоритми, seed збережених
запусків, 31 100 trials SCIENTIFIC-EXP-03B, конфігурації та протоколи не редагувалися.
Повний Monte Carlo не запускався; браузерні перевірки читають наявні спостереження.

| Компонент | Фактична реалізація |
|---|---|
| `scientific.html`, `layout4.js`, `stage4_layout.css` | Підключення модулів; сітка форми; мобільне меню; компактний навігатор; окремі поточний результат і наступний запуск |
| `lab_window.py`, `lab4.js` | Manifest/SHA-перевірене вікно; exact inspector; min/max LOD; 64 MiB LRU для масивів; overview; wheel, pan, brush, pinch; два режими TX/RX |
| `metric_trace.py`, `metric_live.js`, `trellis4.js` | Компактний trace без повних масок у браузері; спільні інтервали H/E; локальна решітка до 80 тактів; branch/accumulated inspector; приховування чисел |
| `constellation4.js` | Рівний масштаб I/Q, XY pan/zoom/brush/pinch, фільтр фаз, hard errors frontend, ideal/vectors, вибір відліку, fullscreen |
| `energy_view.py`, `energy_interactive.js` | BER/SER/FER з фактичних вимірів; log/linear, ДІ за наявності, допустимі crossings, hover, curve toggle, PNG/SVG/CSV |
| `study_catalog.py`, `study_catalog.js` | Серверна пагінація до 50 записів, пошук/фільтри/сортування, параметри, URL, desktop table і mobile details, збереження позиції |

## Кодування: причина та виправлення

Підтверджено локальним відтворенням: Windows PowerShell має
`$OutputEncoding.WebName = us-ascii`. Рядок «Привіт» у Python stdin надходив як
`3f3f3f3f3f3f0d0a`. Після явного UTF-8 —
`d09fd180d0b8d0b2d196d1820d0a`. Отже, літери втрачалися до запису файлу;
перекодування вже пошкоджених байтів їх не відновлює.

Шість звітів етапу 3 відновлено з первісного змісту попередньої роботи.
Нові звіти створює цей Python-скрипт із UTF-8 джерела через
`write_text(encoding='utf-8')`, без передавання кирилиці через PowerShell stdin.
Заголовок навігатора — явний український літерал. HTTP HTML/JSON мають UTF-8;
JSON використовує `ensure_ascii=False`. Є автоматичний тест джерел і Markdown.

## Обсяг перевірки

Браузерні набори: {counts}. Failures браузерних assertions: {len(failures)}.
Розміри: 320, 390, 834, 1366, 1920 CSS px. Одержано 30 нових PNG.
Докази — `browser.json`, `browser_extended.json`, `browser_viewports.json`;
жести перевірені зміною фактичних координат, а не наявністю PNG.

Portable pytest: 1258 passed, 53 deselected у перевіреному прогоні.
Останній повний pytest: 1308 passed, 3 failed; два failures через відсутній
`HF_TCM_SIM_SCIENTIFIC_EXP_01_ENERGY_AUDIT.zip`, один — timeout маршруту EXP-01B.
Root Ruff не green; scoped Ruff для змінених Python-файлів проходить.
Історичні SHA: {history}; загальний статус PARTIAL за наявності NOT_VERIFIED.

Повне приймання не оголошується COMPLETE. Деталі обмежень — у звіті 05.

## Фактично виконані команди перевірки

- `python -m pytest -q` — останній прогін: 1308 passed, 3 failed.
- `python -m pytest -q -m 'not historical'` — 1258 passed, 53 deselected.
- `python -m pytest -q tests/studio/test_stage4_integration.py tests/studio/test_metric_trace.py tests/studio/test_energy_view.py tests/studio/test_study_catalog.py` — 23 passed.
- `ruff check .` — FAIL: сторонні findings та ACL.
- `ruff format --check .` — FAIL: форматування сторонніх файлів і panic formatter.
- `ruff format --check src/hf_tcm/studio tests/studio scripts/audit_stage4_history.py scripts/measure_stage4.py scripts/write_ui_stage4_reports.py` — PASS.
- `node --check` для всіх `src/hf_tcm/studio/static/*.js` — PASS.
- Браузерні команди та їхні assertions наведені у звіті 04.
- `python scripts/audit_stage4_history.py`, потім `python scripts/audit_stage4_history.py --append-unverified` — свіжі SHA без зміни архівів.
""",
    )
    write(
        "02_FUNCTIONAL_ACCEPTANCE_MATRIX_UK.md",
        """
# Матриця функціонального приймання

PASS означає виконані наведені assertions у локальному Edge CDP.
Це не сертифікація всіх можливих пристроїв та історичних архівів.

| Вимога | Результат | Доказ / межа |
|---|---|---|
| Український UTF-8 | PASS | Positive-heading pytest, браузерні тексти, charset API, відтворена причина PowerShell |
| Responsive п'яти ширин | PASS | 30 bounds/overflow/button cases; додаткові перевірки основних control overlaps |
| Налаштування | PASS | Grid, compact runbar, окремі поточні/майбутні параметри, оцінка обсягу |
| TX/RX zoom/pan | PASS | Реальні wheel, mouse drag, Shift rectangle, touch drag/pinch; координати в JSON |
| LOD/overview | PASS | Fit 160000, 800 min/max buckets, overview brush, exact останній відлік; unit звірка NPZ |
| Сузір'я | PASS | XY gestures, phase filter, exact hover, point-to-inspector, рівні осі, fullscreen |
| BER/SER/FER | PASS | Спільний компонент; measured BER hover/log/toggle/touch/export перевірено окремо; FER з verified trial counts |
| Стани енергії | PASS | NOT_RUN для demo; окрема sweep не створює gain без перетину; зареєстровано всі 7 станів |
| H/E synchronization | PASS | Спільні SHA, точний збіг inspector з обома arms, однаковий range/scale; tail до 19999 |
| Збережені дослідження | PASS | Справжні сторінки 25 записів, пошук, фільтр, sort, details/open; без всього архіву в DOM |
| Deep links | PASS | Trace-only run_id та перевірений saved study_id; індекс і діапазон у URL |
| Кінець кадру | PASS | Символ 19999, відлік 159999, інформаційний біт 39999, pilot без інформаційного біта |
| Cancellation | PASS | Останній із швидких запитів перемагає; старі fetch скасовано; trace pending відділено від window pending |
| Performance | PARTIAL | Виміряні API/100 переходів/JS heap/RSS; повний RSS браузера NOT_MEASURED |
| Повна Python-регресія | FAIL | Два відсутні historical ZIP provenance failures та один historical route timeout |
| Root Ruff/format | FAIL | Сторонні findings/ACL; formatter падає на документації; scoped checks PASS |
| SCIENTIFIC-EXP-03B SHA | PARTIAL | Свіже порівняння з наявними еталонами; без еталона PASS не присвоюється |

## Окремі браузерні перевірки

| Набір | Перевірка | Статус |
|---|---|---|
"""
        + "\n".join(matrix),
    )
    api_rows = "\n".join(
        f"| {r['start']} | {r['count']} | {r['buckets']} | {r['bytes']} | {r['ms']:.3f} |"
        for r in api["api"]
    )
    write(
        "03_PERFORMANCE_REPORT.md",
        f"""
# Вимірювання швидкодії / Performance

Контроль: N=20 000, n=8, seed=331, 160 000 комплексних відліків,
збережений `stage3-control-20000`. Нові шумові реалізації не генерувалися.
Це вимірювання локального середовища під паралельним SHA-аудитом і тестами.

| Початок | Кількість відліків | Buckets RX I | JSON bytes | API ms |
|---|---|---|---|---|
{api_rows}

Відповіді мають charset UTF-8. Повний overview не передає сирі 160 000 I/Q.
Сервер читає NPZ для перевірки й кешування; це не disk-streaming NPZ.
LRU масивів — 64 MiB, окремий replay cache — до чотирьох записів.

100 послідовних переходів початок/кінець: count={len(times)},
median={statistics.median(times):.1f} ms, min={min(times)} ms, max={max(times)} ms.
Це end-to-end час тестового драйвера, включно з polling та паузою стабілізації,
а не чистий час рендерингу. Під час переходів не виявлено browser exceptions.
Швидке скасування: фінальне положення 159999, застарілий результат не застосовано.

Завантаження збереженої вкладки з measured sweep:
{extended["performance"]["saved_tab_load_ms"]} ms.
Тепле перемикання вкладок, browser performance.now до двох animation frames:
{browser_perf["tabs"]}.
Зміна window до готового trace й animation frame: {browser_perf["window_ms"]:.3f} ms.
Zoom без polling драйвера, action → completed trace → animation frame:
{[round(v["ms"], 3) for v in browser_perf["zoom"]]} ms.
Це вимірювання видимої дії, не окремий CPU-profiler paint/render budget.
Чистий CPU paint/render профіль: NOT_MEASURED.

Python-сервер, OS snapshot: WorkingSet={memory["WorkingSet64"]} bytes;
PeakWorkingSet={memory["PeakWorkingSet64"]} bytes;
PrivateMemorySize={memory["PrivateMemorySize64"]} bytes. Це різні OS величини.
Snapshot не є безперервним профілем RSS під час усіх 100 переходів.
Браузер: CDP JS heap = {browser.get("performance", {}).get("browserHeap", {})}.
Повна пам'ять процесів браузера: NOT_MEASURED. JS heap не підміняє process RSS.

Загальний PERFORMANCE: PARTIAL — параметри, яких середовище/драйвер не виміряв,
залишено NOT_MEASURED. Вихідні виміри: `api_performance.json`,
`server_memory.json`, `browser.json`, `browser_extended.json`, `browser_performance.json`.
""",
    )
    write(
        "04_BROWSER_TEST_RESULTS.md",
        f"""
# Результати браузерних E2E

Справжній Microsoft Edge через CDP, localhost. Основний набір:
`node scripts/qa_ui_stage4.mjs`; додатковий:
`node scripts/qa_ui_stage4_extended.mjs`; усі ширини:
`node scripts/qa_ui_stage4_viewports.mjs`. Крайові сценарії:
`node scripts/qa_ui_stage4_edgecases.mjs`, `node scripts/qa_ui_stage4_run_switch.mjs`.

Перевірки: {counts}. Кількість failures: {len(failures)}.
JS runtime exceptions: {sum(len(d.get("errors", [])) for d in suites.values())}.

Драйвер надсилає Input.dispatchMouseEvent та Input.dispatchTouchEvent і звіряє
реальні range/bounds. Сенсорні події — browser touch emulation; фізичний телефон
не використовувався. Клавіатурні Enter/Tab перевірені через Input.dispatchKeyEvent.
Для download потрібна user activation; PNG/SVG/CSV фактично завантажено й прочитано.
Окремий partial-pointer-release сценарій виконує DOM PointerEvent над станом
після справжнього CDP two-touch start: він перевіряє продовження одним пальцем
та доповнює повні CDP touch-жести, не підміняє їх.

Усім шести вкладкам перевірено ширини 320/390/834/1366/1920 px,
scrollWidth документа, bounds графіків, висоти видимих кнопок, Unicode.
Додатково перевірено відсутність перетинів основних form controls,
роботу мобільного меню, exact H/E mapping та wheel на кожній ширині.

Скриншоти: `screenshots/{{parameters,transmitter,constellation,viterbi,metric,saved}}-WIDTH.png`.
Файли PNG — візуальний додаток до assertions, не доказ жестів самі по собі.

Обмеження покриття: це один браузер; усі можливі комбінації кожної кнопки,
стану job і пристрою не перебрано. Screen-reader та фізичний multi-touch:
NOT_MEASURED. Історичні missing-artifact failures не приховувалися.
""",
    )
    write(
        "05_REMAINING_ISSUES_UK.md",
        """
# Залишкові проблеми та межі приймання

1. **Блокер повного регресійного приймання:** немає
   `HF_TCM_SIM_SCIENTIFIC_EXP_01_ENERGY_AUDIT.zip`. Два historical pytest
   падають на provenance loader / HTTP 409. Відсутній архів не замінено
   демонстраційними даними й перевірку SHA не послаблено.
2. **Нестабільна historical HTTP-перевірка EXP-01B:** останній повний прогін
   містить timeout `test_exp01b_static_series_opens_through_saved_study_route`.
   Попередній повний прогін цього завдання мав лише два missing-ZIP failures.
   Timeout відтворено також після завершення SHA-аудиту. Причину timeout
   не локалізовано; зелений повний набір не заявляється.
3. **Root lint/format не green:** сторонні файли та недоступні ACL каталоги;
   `ruff format --check .` завершується внутрішнім panic на документації.
   Змінені Python-файли проходять scoped checks; сторонні джерела не переписано.
4. **Історична доказовість PARTIAL:** для файлів без еталонного digest або
   недоступних артефактів немає підстав для PASS. Точні лічильники — `historical.json`.
5. **Performance PARTIAL:** повний browser process RSS, безперервний server RSS
   та окремий CPU paint/render профіль не виміряні. Час видимих zoom/tab дій
   виміряно через performance.now без polling; JS heap і snapshot RSS наведено
   як окремі величини. Числа для відсутніх вимірювань не вигадані.
6. **Межі детального перегляду:** waveform overview охоплює весь кадр;
   решітка показує максимум 80 тактів навколо вибору для читабельності й bounded API.
   Для коротших інтервалів її межі точно збігаються з waveform на рівні символів.
   Нечисловий overview не означає зміну branch metrics чи математичних результатів.
7. **Межі E2E:** один Edge/CDP, emulated touch, базова клавіатура. Фізичні
   touch-пристрої й screen-reader не перевірялися. Нових наукових висновків немає.

Невиправлених збоїв жестів або overflow у наведених фінальних браузерних
сценаріях не зафіксовано. Проте загальний етап лишається PARTIAL через
незелене повне регресійне приймання та наведені неповні вимірювання.
""",
    )
    write(
        "06_USER_GUIDE_UK.md",
        """
# Інструкція користувача лабораторії

Запуск: `python -m hf_tcm.repro.scientific_studio --no-browser`;
відкрийте `http://127.0.0.1:8765/scientific`.

На телефоні вибирайте вкладку у верхньому меню. «Поточний результат» містить
фактичні N і seed відкритого run. Форма «Наступний запуск» задає нову конфігурацію;
попередження вказує відмінність від поточних даних. Профіль, режим, ID,
повторення й запуск зібрано в одному блоці; другорядні параметри розкриваються.
Методологія та позначення [СТАТТЯ]/[ПРОЄКТ] доступні в поясненнях.

Навігатор: виберіть символ, відлік або біт, введіть індекс і натисніть
↵ («Перейти») або Enter. Стрілки — попередня/наступна позиція; +/− — масштаб;
↺ — початкове вікно. Для N=20000 останній символ 19999, відлік 159999.
У «Додаткових діях» — початок/кінець, помилки, playback, export, інспектор,
mapping та min/max overview. Інтервал playback у мілісекундах не є часом сигналу.

TX/RX: коліщатко масштабує навколо курсора, drag переміщує,
Shift+drag вибирає область, два пальці масштабує, один — переміщує.
Hover повертає точні TX/RX I/Q; click вибирає відлік. У меню графіка
перемикайте чотири смуги / порівняння TX/RX, приховуйте сигнали, Fit або fullscreen.
Overview показує весь кадр; перетягніть довільний діапазон для деталізації.
Жовте — pilot, червоне — помилки. LOD змінює лише графічне представлення.

Сузір'я: wheel, drag, Shift+drag та pinch працюють у координатах I/Q з рівним
масштабом осей. У фільтрах оберіть TX фазу, ideal points, vectors, errors.
Hover показує точні координати. Click синхронізує sample/symbol з інспектором
та обома решітками; fullscreen розгортає вкладку. Відліки беруться з відкритого run.

Решітки: H/E мають спільні k, інтервал і масштаб. Wheel масштабує обидві,
drag переміщує локальні scroll-контейнери. Числові підписи вимкнені за замовчуванням;
їх можна ввімкнути. Click ребра показує повні branch/accumulated metrics та рішення.
Для великого waveform інтервалу локальний trace обмежений 80 тактами.

Енергетичні криві: демонстраційний запуск залишає NOT_RUN. Для виміряних
кривих відкрийте збережений sweep або явно запустіть окрему серію.
Wheel/drag/Shift+drag/pinch працюють і тут. Доступні log/linear Y, curve toggles,
точні значення й ДІ за наявності, PNG/SVG/CSV. Нулі не показуються на log Y,
але залишаються в CSV. Gain без допустимого перетину BER не створюється.

Каталог: пошук за ID/датою/seed, додаткові фільтри та сортування,
серверні сторінки по 20/25/50 записів. «Деталі» відкривають параметри;
«Відкрити» використовує перевірений loader. URL містить study_id/study_kind
і для metric run — run_id, domain, index, start, span. Повернення зберігає список.
Архів «20 000 символів» без I/Q дозволяє числові результати й окремий trace;
він не створює вигаданого сузір'я. Відсутня provenance може блокувати loader.

SCI-обмеження зберігаються: paper_exact:false; дискретна шкала не є фізичним
Eb/N0; незалежного підтвердження 1,5 дБ зі статті немає.
""",
    )
    print(
        json.dumps(
            {"browser_counts": counts, "browser_failures": len(failures), "history": history}
        )
    )


if __name__ == "__main__":
    main()
