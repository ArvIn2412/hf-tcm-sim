# HF-TCM-SIM — довідка для наступного агента

Стан описано за файлами робочої копії на 2026-11-16. Це карта проєкту, а не підтвердження, що всі історичні тести щойно повторно запускалися.

## Призначення та межі

HF-TCM-SIM — офлайнова академічна симуляція згорткового коду зі швидкістю `R=2/3`, 8PSK, модельних каналів, декодування Вітербі, оцінювання помилок і дослідницьких робочих процесів. Проєкт не керує SDR, радіопередавачами або БПЛА.

Головні наукові обмеження:

- `paper_exact:false`: наявні реалізації не слід називати точним відтворенням статті без окремого доказу.
- Значення 1,5 дБ зі статті не підтверджене як результат цього коду. Не підганяти моделі чи результати під нього.
- Реконструйовані/ізольовані алгоритми мають лишатися позначеними як такі; див. `docs/ASSUMPTIONS_AND_DECISIONS.md` та ADR-и.
- Не змінювати архівні протоколи, seeds, trials, вихідні масиви, графіки й фінальні наукові висновки SCIENTIFIC-EXP-03B.
- Не запускати великі статистичні серії без окремого дозволу й затвердженого протоколу.

## Спочатку прочитати

1. `AGENTS.md` — правила роботи Codex/агента.
2. `PLAN.md` — історія етапів і фактичні застереження. Останній запис UI у файлі — `UI-ARTICLE-ALIGNMENT-02`.
3. `NEXT_TASK.md` — може описувати старіший дослідницький контекст; звірити його з останнім записом `PLAN.md`, не починати автоматично новий етап.
4. `docs/TECHNICAL_SPECIFICATION.md`, `docs/ASSUMPTIONS_AND_DECISIONS.md`, потрібні розділи `docs/repro/` та `docs/research/`.
5. `UI_FINAL_ACCEPTANCE_UK.md` і `outputs/ui_article_alignment/UI_IMPLEMENTATION_REPORT_UK.md` — звіт про UI етапу 2, його обмеження й фактичні перевірки.

У PowerShell текст деяких UTF-8 файлів може відображатися з неправильним кодуванням залежно від термінала. Не переписувати документи лише через артефакт відображення.

## Структура коду

### Python-пакет `src/hf_tcm/`

| Підкаталог/файл | Відповідальність |
|---|---|
| `coding/` | Encoder A/B, trellis, гіпотези, ймовірності та posterior-процедури. |
| `modulation/` | 8PSK labeling/modulation. |
| `channels/` | AWGN, multipath, Rician fading, fluctuating noise та статистики каналу. |
| `decoding/` | branch metrics, Вітербі та ізольована реконструкція метрики статті. |
| `receiver/` | IQ-прогноз, estimation/receiver-процедури та ізольовані реконструйовані етапи. |
| `evaluation/` | BER/SER, paired studies, bootstrap, протоколи, runners і незалежні recount/audit. |
| `repro/` | Конфігурації, серіалізація, CLI та відтворювані експериментальні процедури; тут також `scientific_studio.py` і `metric_experiment.py`. |
| `studio/` | Локальний HTTP API та адаптери даних для GUI; `server.py`, `scientific.py`, `metric_trace.py`, завантажувачі історичних результатів. |
| `demo_studio.py` | Старіший інтерактивний демонстраційний frontend/launcher. Не плутати його з науковою стартовою сторінкою. |

### Frontend `src/hf_tcm/studio/static/`

- `scientific.html`, `scientific.css`, `scientific.js` — оболонка Scientific Workspace, стилі та основна поведінка.
- `article_workspace.js` — навігація шістьма вкладками, профілі/URL state та міст між старими й новими UI-секціями.
- `metric_parameters.js` — профілі й параметри/підказки запуску.
- `scientific_metric.js` — запуск metric-ізоляції, керування sample/sweep jobs, зупинка, адаптивна серія й оцінювання gain.
- `metric_live.js` — відображення збережених даних запуску: TX/RX, сузір’я, таблиця encoder, дві решітки та підсумки.
- `signal_window.js`, `trellis_projector.js`, `minimalist_state.js`, `scientific_ux.js` — допоміжні/суміжні UI-модулі; перед видаленням перевірити HTML-підключення й пошук посилань.
- `studio.html` тут немає як єдиного entrypoint: legacy сторінка — `index.html`; наукова — `scientific.html`.

### Тести, конфігурації, матеріали

- `tests/` — pytest-набір (на момент огляду 116 файлів `test_*.py`, не число окремих тест-функцій).
- `tests/studio/` — перевірки веб/API та UI data adapters; зокрема `test_metric_trace.py`.
- `scripts/` — browser QA, аудит відтворюваності, незалежний recount і пакування звітів. Не запускати runner, що генерує нові trials, лише для огляду коду.
- `configs/` — JSON-конфігурації/manifest-и наукових процедур; затверджені файли часто мають поруч `.sha256`.
- `docs/repro/`, `docs/research/`, `docs/figures/`, `docs/screenshots/` — специфікації, протоколи, звіти, таблиці та пояснення.
- `references/` — джерельні матеріали та їхні витяги.
- `outputs/` — великі результати експериментів, audit data, UI screenshots/logs. Поточний `.gitignore` ігнорує весь цей каталог.
- `tmp/` — scratch, pytest basetemp, browser профілі й проміжні audit/extraction дані. Не додавати весь каталог у Git. Частина перевірочних скриптів читає окремі baseline-файли з `tmp/`; див. нижче.

## Архітектура вебпрограми

Scientific Workspace стартує через `hf_tcm.repro.scientific_studio`, який створює локальний сервер із `hf_tcm.studio.server.make_server(..., default_view="scientific")`. Сервер — стандартний Python `http.server`, без окремого frontend build і без обов’язкового Node backend. За замовчуванням він прив’язаний до localhost. GET сторінки не повинен запускати симуляцію.

Шість вкладок поточної UI:

1. **Налаштування і запуск** — параметри, статейний/власний профілі, sample та Monte Carlo jobs.
2. **Передавач і канал** — передані/прийняті сигнали, параметри та таблиця джерельних даних.
3. **Сузір’я 8PSK** — ідеальні точки й точки з фактичних збережених RX/frontend масивів.
4. **Декодування та решітка Вітербі** — replay двох branch metrics на спільному джерелі спостережень; синхронні H/E вікна.
5. **Порівняння та енергетичний виграш** — BER/SER/FER, runtime та чесні gain statuses.
6. **Збережені дослідження** — відкриття/перегляд збережених запусків та історичних результатів.

Основні HTTP API згруповані в `server.py`: `/api/scientific/run`, `/api/scientific/runs`, `/api/scientific/experiments`, `/api/scientific/energy-studies`, `/api/scientific/metric-studies`, `/api/scientific/metric-trace`, `/api/scientific/traces`, `/api/scientific/samples`, `/api/scientific/viterbi`, `/api/scientific/jobs/{id}/stop`, та окремий read-only `/api/scientific/exp03b-results`. Точні параметри й валідацію дивитися в handler-ах, config-моделях і тестах, а не вгадувати зі списку.

Збережені study містять конфігурацію, JSON record/manifest і NPZ масиви без pickle; manifest перевіряє SHA-256. `metric_trace.py` перевіряє джерельні хеші й повторно програє наявний decoder, звіряючи відновлені біти зі збереженими. Це read-only адаптер візуалізації, не нова реалізація декодера.

### Парність «Хемінг / Евклід»

У блоці A дві гілки мають спільне збережене спостереження, frontend/CSI та trellis; відрізняється branch metric. Сирі RX I/Q спільні. Дані графіка беруться зі збереженого trial, а не генеруються лише для малюнка. Не плутати це з історичним порівнянням повних архітектур Joint/B0/B1.

Energy sweep окремий від одиничного показу. Числовий gain дозволений лише коли виміряні криві охоплюють target; без екстраполяції. Відсутність crossing дає `ENERGY_GAIN_NOT_ESTIMABLE`, а недостатня bootstrap точність — `INSUFFICIENT_PRECISION`. Адаптивне розширення потребує явного дозволу й створює нову окрему серію.

## Поточний стан і відомі межі

- Звіт етапу 2 фіксує 1295 пройдених pytest, browser QA desktop/mobile, живі збережені I/Q, replay решіток і consented energy extension. Це історичний запис звіту; у цій підготовці повний тестовий набір не запускався.
- Root-wide Ruff має відомі старі lint findings/traversal issue; див. звіт UI та `PLAN.md`. Не оголошувати lint green, спираючись лише на scoped перевірку.
- Історичний SHA аудит UI-звіту — PARTIAL: є файли без baseline manifest (`NOT_VERIFIED`). Використовувати саме записані статуси; не перетворювати відсутність baseline на PASS.
- **Етап 3 інтерактивності не виконаний.** Центральний navigator по всьому кадру (20 000 символів/160 000 відліків), довільний перехід у кінець, linked zoom/pan/brush, агреговані LOD-вікна, пагінація сотень study та повне mobile/browser acceptance треба перевіряти й реалізувати окремою фазою. Файл `TCM_SIM_STAGE3_INTERACTIVE_LAB_REDESIGN_UK.md` при попередній перевірці не знайдено; специфікація була надана користувачем у чаті.
- Попередня інвентаризація з `outputs/github_publish/file_inventory.json` зафіксувала приблизно 14,1 GB і архів понад 6 GB, але цей inventory зараз застарілий: вказані два root ZIP за тим шляхом не знайдені, а рекурсивний `rg` отримав `Access denied` на окремих каталогах. Не використовувати старий inventory як доказ фактичної наявності/розміру. Поточний відбір Git обов’язково перевірити через `git status`.
- Наразі папка **не є Git-репозиторієм** (`.git` відсутній), remote не налаштований; Git є, Git LFS 3.5.1 є, GitHub CLI `gh` під час перевірки не знайдено.

## Локальний запуск і перевірка

У PowerShell з кореня проєкту:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m hf_tcm.repro.scientific_studio --port 8765
```

Відкривається `http://127.0.0.1:8765/scientific`. Без автоматичного відкриття браузера додати `--no-browser`. Зупинка — `Ctrl+C`.

Перевірки за правилами `AGENTS.md`:

```powershell
python -m pytest -q
ruff check .
ruff format --check .
```

Для малих/цільових сценаріїв запускати лише тести, що не створюють нову масову дослідницьку серію. Перевірити їхні fixtures/output paths перед запуском.

## Підготовка до GitHub: важливо

Рекомендовано тримати у Git source, tests, configs, docs, references і scripts, а великі `outputs/` та scratch `tmp/` передавати окремо або вибірково. `.gitignore` містить `outputs/`, але **не** містить загального `tmp/`; тому сліпе `git add .` може захопити гігабайти тимчасових даних. Два baseline-файли `tmp/m11d-integrity-before.json` і `tmp/gui-energy-01b-edge-qa.json` існують і згадані старими audit/package scripts; якщо потрібні відповідні перевірки на новій машині — додати саме потрібні baseline-файли окремо, не весь `tmp/`.

За поточною документацією GitHub звичайний Git блокує файли понад 100 MiB. Межа одного Git LFS об’єкта залежить від плану: Free/Pro — 2 GB, Team — 4 GB, Enterprise Cloud — 5 GB. GitHub радить тримати репозиторій бажано до 1 GB і наполегливо рекомендує менше 5 GB. Архів понад 6 GB, якщо його буде знайдено/потрібно включити, не можна завантажити одним LFS-об’єктом; треба розділити його на частини відповідного ліміту або розмістити окремо. Також перевірити вміст на секрети та права на розповсюдження джерельних матеріалів.

## Команди для публікації коду на GitHub (PowerShell)

Спочатку створити на GitHub **порожній** репозиторій без README/license/gitignore та скопіювати його HTTPS URL. Потім із цієї папки виконати команди нижче. Вони навмисно виключають `tmp/` і `outputs/`; проєктні джерела, тести, конфіги й документація залишаються в індексі. Перегляньте staged list і розміри перед комітом.

```powershell
Set-Location 'C:\Users\grine\OneDrive\Desktop\Diplom_M\hf-tcm-sim'
git init -b main
git add -A -- . ':(exclude)tmp/**' ':(exclude)outputs/**'
git status --short
git diff --cached --check
git diff --cached --stat
```

Якщо список правильний і немає секретів/небажаних великих файлів:

```powershell
git commit -m "Initial HF-TCM-SIM project import"
git remote add origin 'https://github.com/OWNER/REPOSITORY.git'
git remote -v
git push -u origin main
```

Замість `OWNER/REPOSITORY` підставити свій акаунт/організацію та ім’я створеного репозиторію. Якщо remote вже існує, перевірити його через `git remote -v` і застосувати `git remote set-url origin ...`, не додавати другий `origin`.

Щоб включити повний архів експериментальних результатів, не використовувати бездумно `git add -f outputs`: спершу вирішити, які саме результати мають бути публічними, перевірити сумарний обсяг, LFS quotas, кожен розмір файлу, ліцензійні обмеження та секрети. Звіти містять відносні посилання на `outputs/`, тому для повної відтворюваності можна окремо опублікувати потрібні незмінні artifacts через GitHub Releases/LFS або інше сховище й задокументувати їхні SHA-256.

## Посилання на першоджерела GitHub про правила завантаження

- [Додавання локального коду до GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github?platform=windows)
- [Ліміти великих файлів та рекомендований розмір репозиторію](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Ліміти розміру об’єкта Git LFS](https://docs.github.com/en/enterprise-cloud%40latest/repositories/working-with-files/managing-large-files/about-git-large-file-storage)
