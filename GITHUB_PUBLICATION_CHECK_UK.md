# Контрольована підготовка GitHub-публікації HF-TCM-SIM

**Рішення: REQUIRES_REVIEW.** Дата: 16.11.2026.

Технічний source-набір підготовлений до контрольованого staging, але публікацію
поточної Git history не погоджено: 20 уже відстежуваних документів мають непідтверджені
права/походження, частина містить персональні контакти, локальні шляхи або матеріали
іншого проєкту. У репозиторії немає відстежуваного LICENSE/COPYING. Ліцензію не
призначено автоматично. Це перевірка локальних матеріалів і доказів дозволу,
а не юридичний висновок про порушення чи підтвердження ліцензії.

Прочитано `01_RELEASE_READINESS_UK.md`, `05_RELEASE_NOTES_UK.md`,
`git_inventory.json` та `README_RELEASE_UK.md`. Нижче відокремлені свіжі перевірки
від раніше зібраного browser evidence. Нової моделі, Monte Carlo, commit, tag,
release, push або staging не виконано. Історія Git та бінарні оригінали не змінені.

## 1. Контроль версії та складу змін

HEAD: `87e6702f1244cad6dd390d2047412ec983ebabed`.
Початкові **56/56** source-кандидатів за шляхом і SHA-256 точно збігаються
з `outputs/release_readiness/git_inventory.json`: доданих, зниклих чи змінених
кандидатів відносно цього інвентарю немає. Це включає успадковані зміни етапу 4.
Усі менші 2 MB; бінарних дослідницьких файлів серед них немає.
Новий результат цієї задачі — тільки цей Markdown, тому після його створення
очікується **57** кандидатів. `git diff --cached --name-only` порожній.

`git check-ignore` підтвердив виключення `outputs/`, `tmp/`, `.historical-input/`,
`.env`, `.env.local` і ZIP. `.gitignore` не впливає на раніше закомічені файли.
Жоден із 20 документів не змінено і не виключено з index автоматично.
Поточний `git diff --name-only HEAD -- configs docs/research` порожній.

## 2. Publication review усіх 20 документів

Для кожного файла зафіксовані SHA-256 і розмір у локальному
`outputs/release_readiness/publication/documents.json`. Витягнуті тексти й metadata
зберігаються **тільки в ignored outputs**, не додаються до Git і не є матеріалами
для відкритого release asset. Email та повні локальні шляхи тут не дублюються.

OOXML перевірено як ZIP: CRC, XML текст, properties, comments, relationships,
медіа та список embedded OLE. PDF — текст усіх сторінок і metadata. Для scan №15
переглянуто всі шість сторінок на contact sheet. RTF перевірено з декодуванням
Unicode/cp1251; для legacy DOC №19 доступне лише витягування printable strings.
Повної антивірусної перевірки OLE, OCR та всіх прихованих бінарних полів не було:
вони **NOT_VERIFIED**. OLE-об’єкти не запускалися. Відсутність email-збігів не
дорівнює відсутності всіх персональних даних.

У жодному з 20 файлів не знайдено явного дозвільного license notice.
Ім’я в metadata саме по собі не встановлює власника прав; потрібне підтвердження
користувача/правовласника. `EXCLUDE_RECOMMENDED` — рекомендація для майбутнього
публічного source snapshot, а не вже виконане видалення або переписування history.

### 01. `conference_2026_11_12/01_Презентація_КХ_8PSK_спільна_демодуляція.pptx`

**REQUIRES_REVIEW.** Матеріал HF-TCM-SIM; у титулі незаповнені ПІБ/установа. Один рисунок побайтово збігається з рисунком рукопису №13/20; права на його повторне поширення не підтверджені.

Рекомендація: Не включати у source-only публікацію без підтвердження авторства, прав на рисунок і шаблон.

SHA-256: `d2f142689d427cff867e03c8b1c2ed2ff2a680ba9238d8a5dfd2978bfafabd17`; 131012 bytes.

### 02. `conference_2026_11_12/02_Текст_доповіді_5-7_хв.docx`

**REQUIRES_REVIEW.** Сценарій виступу HF-TCM-SIM; ПІБ/установа залишені placeholders, creator — матеріали конференції. Явної ліцензії немає.

Рекомендація: Для запуску не потрібний; залишити приватно до підтвердження власника.

SHA-256: `5a4ac6a66c193929ac69ffb31b89dbfae6cbd9a150a379fc2d23243a4e54532d`; 9578 bytes.

### 03. `conference_2026_11_12/03_Питання_та_відповіді.docx`

**REQUIRES_REVIEW.** Питання/відповіді HF-TCM-SIM; ідентифікованих контактів у витягнутому тексті немає. Ліцензія та право публікації не підтверджені.

Рекомендація: Для source-only релізу не потрібний; публікувати лише після рішення власника.

SHA-256: `6aca81a55adcc3d9e8d8ea2fa46ff7527d74963a2c0ed47eb9a5b34089f9461a`; 8524 bytes.

### 04. `conference_2026_11_12_input/examples/Горбач_доповідь_передзахист.pptx`

**EXCLUDE_RECOMMENDED.** Чужий приклад передзахисту: названий інший доповідач; lastModifiedBy містить ще одне стороннє ім’я, присутні шаблон та ілюстрації. Авторство шаблону/рисунків не встановлено.

Рекомендація: Виключити з майбутнього публічного source snapshot; потрібен дозвіл власників для поширення.

SHA-256: `348d882815634b0df52cc16ea924b1db95a26cb361d0b2580b3f930e7ae9b081`; 935207 bytes.

### 05. `conference_2026_11_12_input/examples/Питання_та_відповіді.docx`

**EXCLUDE_RECOMMENDED.** Питання до іншої роботи про NIDS/атаки; сторонні числові результати й матеріали. Metadata python-docx не встановлює автора або ліцензію.

Рекомендація: Не є залежністю симулятора; не включати в публічний snapshot.

SHA-256: `151c09521642dcddb37b7685f18f9dd5e1a9917738359baf31ec5f66771bf48a`; 43586 bytes.

### 06. `conference_2026_11_12_input/examples/Текст_доповіді.docx`

**EXCLUDE_RECOMMENDED.** Текст чужої доповіді, інший доповідач названий у змісті; інша тема дослідження. Ліцензії/дозволу немає.

Рекомендація: Не включати в публічний snapshot без окремого дозволу.

SHA-256: `0c91adfbdc4176551cbcd24f4eb9480ecb0fe8e191fd6d89d992d5625ce582ec`; 40905 bytes.

### 07. `conference_2026_11_12_input/sources/Yakoviv_Hrynenko_UA v2(2).rtf`

**EXCLUDE_RECOMMENDED.** RTF рукопису двох авторів; декодовано Unicode/cp1251, знайдено локальний шлях. RTF містить не лише простий текст; вкладені об’єкти повністю не сертифіковані.

Рекомендація: Зберегти незмінним у приватному науковому архіві; потрібна згода правовласників.

SHA-256: `4f37672a7426742883e3c8a08cf971a57b85d2e11d6fdb96c1907687fe7b38f0`; 916522 bytes.

### 08. `conference_2026_11_12_input/sources/preview/Yakoviv_Hrynenko_RTF_render.pdf`

**EXCLUDE_RECOMMENDED.** PDF-похідна того ж рукопису, 3 сторінки, названі два автори; metadata Author — загальний користувач Windows. Похідний PDF не доводить дозвіл на поширення.

Рекомендація: Не включати source-only публікацію; дозволи ті самі, що для оригіналу.

SHA-256: `38bbd6a9060a6f216d611335bcac94a83f36d074f12b0b7103faac0bd6140931`; 167872 bytes.

### 09. `docs/TECHNICAL_SPECIFICATION_v1.0.docx`

**REQUIRES_REVIEW.** Технічне завдання проєкту; імена авторів статті наведені як джерело, приватних контактів у витягнутому тексті немає. Є Markdown-версія; підтвердження ліцензії DOCX відсутнє.

Рекомендація: DOCX для запуску не потрібний; достатньо погодженої текстової специфікації.

SHA-256: `32042e34f95256f0ca1985505a84c62a466a88461f2ec4227867632ab03fafde`; 34093 bytes.

### 10. `docs/copyright/debug/media_only.docx`

**EXCLUDE_RECOMMENDED.** Debug-пакет із текстом сторонньої програми NIDS-Core і стороннім lastModifiedBy; 5 зображень візуально показують HF-TCM-SIM, тобто текст і медіа не відповідають одне одному. Це не фінальний документ.

Рекомендація: Виключити з публічного snapshot; не виправляти оригінал і не видавати за власний.

SHA-256: `dcca325511fce9ea69324afccc09827a7e372533ee0e934e25d915b679eacc67`; 893016 bytes.

### 11. `docs/copyright/debug/roundtrip_xml.docx`

**EXCLUDE_RECOMMENDED.** Другий debug-пакет NIDS-Core; той самий сторонній lastModifiedBy та п’ять зображень. Технічний roundtrip не змінює походження/прав.

Рекомендація: Виключити з публічного snapshot.

SHA-256: `b8a7ddcae5902d4abed11c4824e6a358a1619d14d976906fcad10822539da143`; 554205 bytes.

### 12. `docs/copyright/debug/xml_only.docx`

**EXCLUDE_RECOMMENDED.** Текст уже про HF-TCM-SIM, але metadata зберегла сторонній lastModifiedBy; 5 медіафайлів побайтово спільні з №11 і візуально показують NIDS. Заміна XML не очищає походження вкладень.

Рекомендація: Виключити debug-пакет; для публічного документа потрібен новий погоджений матеріал, оригінал не змінювати.

SHA-256: `68020d7519e79bbdb249f3d0a7f76a2ef9e78d4698c9684c5db15c2925db6427`; 553010 bytes.

### 13. `references/alternate_versions/Яковів_Гриненко_2026_в7 27-10-26(6).docx`

**EXCLUDE_RECOMMENDED.** Чернетка статті двох авторів: 2 різні email у тексті, 24 збіги локальних шляхів; 97 OLE-вкладень та 84 медіафайли. Metadata містить ім’я редактора.

Рекомендація: Приватний еталон для historical fingerprint; не санітизувати оригінал, потрібна згода на публікацію.

SHA-256: `190163b9f123e99648ce9dc2d57cb4fdcc24a8a675001009da41cb0ecf6f9a87`; 229003 bytes.

### 14. `references/source_paper_2026.docx`

**EXCLUDE_RECOMMENDED.** Основний першоджерельний DOCX: 2 email, 2 збіги локальних шляхів, імена авторів/редактора; 97 OLE-вкладень та 84 медіафайли.

Рекомендація: Залишити незмінним зовнішнім historical input; не змінювати еталонний SHA.

SHA-256: `a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8`; 228348 bytes.

### 15. `references/supervisor/4.pdf`

**EXCLUDE_RECOMMENDED.** 6 сторінок рукописних конспектів: текстовий шар відсутній; усі 6 переглянуті на render contact sheet. Видно формули/схеми й дату; авторство та згода невідомі, повного OCR немає.

Рекомендація: Особисті конспекти керівника: зберігати приватно, не включати source snapshot.

SHA-256: `97b8868bbb3cd48a7113fa89615bac5286f185957f9441d7159b9f7d548a5904`; 33594192 bytes.

### 16. `references/supervisor/Раздел_4.pdf`

**EXCLUDE_RECOMMENDED.** 42-сторінковий сторонній розділ дисертації, автор у PDF metadata; явного дозволу/ліцензії не знайдено. Зміст не є програмним кодом проєкту.

Рекомендація: Виключити з публічного source snapshot, залишити бібліографічне посилання за потреби.

SHA-256: `fa802b480e6d49089847867aacb2702231df758d1c990320b3d471202951f77d`; 1313542 bytes.

### 17. `references/supervisor/Яковів_Гриненко_2026_в3_24_10_2026.docx`

**EXCLUDE_RECOMMENDED.** Інша чернетка статті: 2 email, 2 локальні шляхи, імена авторів/редактора; 97 OLE-вкладень та 84 медіафайли.

Рекомендація: Приватний науковий оригінал, дозвіл на поширення не встановлено.

SHA-256: `2f070e438f1d8fa4a6cd84e3e6cab24c560ba55670c93ec759a6f4fe82e76b58`; 228353 bytes.

### 18. `references/Автореферат_1-1.pdf`

**EXCLUDE_RECOMMENDED.** 18-сторінковий автореферат стороннього автора; ПІБ автора, керівника, опонентів і адреса установи. Публічна наявність/цитування не встановлює ліцензію цього файла.

Рекомендація: Не включати файл без підтверджених прав; бібліографічні відомості відокремити від копії документа.

SHA-256: `4976650c8b66dcb19591fe994123273bad44554fa316ed1ccfaa56e4ba17d2c7`; 719801 bytes.

### 19. `references/Раздел_4.doc`

**EXCLUDE_RECOMMENDED.** Legacy DOC стороннього розділу; назва та текст читаються з UTF16/cp1251 рядків, 36 збігів локальних шляхів. Повний CFB/Word parser недоступний: приховані поля/вкладення NOT_VERIFIED.

Рекомендація: Виключити з публічного snapshot; незмінний приватний оригінал, повна очистка не стверджується.

SHA-256: `e877a9272da0e8baa0e4eb21256acf1e2112428d3dbf14472d9b12d3239cfd59`; 2179584 bytes.

### 20. `references/Яковів_Гриненко_2026_в7 27-10-26(4).docx`

**EXCLUDE_RECOMMENDED.** Ще одна версія статті: 2 email, 24 локальні шляхи, 97 OLE-вкладень і 84 медіафайли; імена авторів/редактора.

Рекомендація: Приватний науковий оригінал; не змінювати історичні байти/SHA.

SHA-256: `4e41d33a898d2bfec2118a0cd11d3879ac01d4095264b14f7123bc9840d5f1e3`; 225022 bytes.

## 3. Додаткові ризики публікації та вибір способу

- 7 уже відстежуваних PNG у `references/key_pages/` і
  `conference_2026_11_12_input/sources/preview/` є зображеннями першоджерел.
  Для них потрібне те саме рішення про права, що для відповідних оригіналів.
- Презентація №01 містить побайтово спільний рисунок зі статейними №13/20;
  debug №11/12 мають 5 спільних медіафайлів NIDS. У №10 навпаки HF-TCM-SIM
  screenshots поєднані з текстом NIDS. Переглянуто contact sheet усіх 23
  растрових вкладень №01/04/10/11/12. Власна назва документа не
  усуває залежність від сторонніх ілюстрацій.
- Відстежувані текстові copyright scripts/logs і paths-файли також варто
  залишити поза новим source snapshot або погодити окремо: там є матеріали
  документального workflow, які не потрібні для запуску веблабораторії.
- Потрібна обрана власником ліцензія на власний код і окремі дозволи на
  матеріали співавторів. Автоматичне оголошення MIT/іншої ліцензії не виконано.

**Для звичайного push цієї гілки:** якщо файли залишаються в попередніх комітах,
вони доступні через history. Навіть майбутній `git rm --cached` не усуне це.
Тому не виконувати публічний push до вирішення прав на всі reachable copies.

Можливі рішення користувача: (а) підтвердити письмово право публікації всіх
наявних матеріалів і ліцензію коду; (б) погодити новий чистий source-only
репозиторій/snapshot без перенесення старої history, з приватним незмінним
архівом першоджерел; (в) окремо погодити план очистки history. Жоден варіант
автоматично не реалізовано. Приватний remote може бути проміжним місцем CI
лише після окремого дозволу і перевірки його видимості.

## 4. Перевірка секретів

Перевірено 1084 tracked paths; прочитано **860 текстових файлів** поточного дерева
та untracked source-кандидатів. Ознак приватних ключів, GitHub/AWS/Google/Slack
токенів, credential URL або підозрілих літеральних credential assignments:
**0 findings**. Відстежуваних `.env`, PEM/PFX/KEY чи SSH private-key шляхів немає.
Окремо перевірено текстові patches усіх **4 reachable commits**, 14 495 553 bytes:
private-key/GitHub/AWS/Google/credential-URL patterns — 0 findings.

Це евристична перевірка, не математичний доказ відсутності всіх секретів.
Спеціалізованого gitleaks/trufflehog тут немає; бінарні та видалені unreachable
об’єкти повністю не декодовано. Персональні email в документах не є API-секретами,
але залишаються publication-ризиком. Сирі знайдені контакти не внесені в цей звіт.

## 5. CI, Python та свіжа регресія

| Перевірка | Фактичний результат |
|---|---|
| Workflow YAML | PASS: `portable`, `source-quality`, `historical-audit` — окремі jobs |
| Portable source-only, Python 3.13.13 | **1266 passed, 54 deselected**, 63.62 s |
| Повний pytest, Python 3.13 | **1318 passed, 2 failed**, 79.002 s |
| Python 3.11 локально | **NOT_VERIFIED**: `py -3.11 --version` — No suitable runtime |
| Python 3.12 локально | **NOT_VERIFIED**: `py -3.12 --version` — No suitable runtime |
| `ruff check src tests scripts/ci` | PASS, exit 0 |
| `ruff format --check src tests scripts/ci` | PASS, exit 0 |
| `ruff check .` | FAIL, exit 1; historical/scratch findings |
| `ruff format --check .` | FAIL, exit 101; historical/scratch traversal/panic |
| `git diff --check` | PASS |
| GitHub Actions remote | **NOT_VERIFIED**, push не виконувався |

Launcher реєструє тільки 3.13 і 3.14. Каталоги Python311/312 існують як залишки
Doc/Lib/Scripts, але виконуваних `python.exe` немає. Версії або залежності не
встановлювалися. Збережений старий commit про matrix не замінює свіжу перевірку
поточних 56 кандидатів на 3.11/3.12.

Два failures — незмінені tests
`test_historical_energy_study_revalidates_provenance_and_recomputes_gain` та
`test_historical_energy_study_is_available_through_read_only_gui_route`.
Причина — відсутній оригінальний EXP-01 ZIP; classification:
**BLOCKED_MISSING_ARTIFACT**, не PASS/skip/xfail. EXP-01B timeout test проходить
у повній регресії. Оригінальний ZIP не створювався і не підмінявся.

Portable matrix у workflow — Python 3.11/3.12 на Ubuntu; source quality — окремий
job; historical — тільки `workflow_dispatch` з явним прапорцем і довіреним
same-repository input artifact. SHA/provenance preflight відмовляє при
відсутньому bundle (exit 2) або hash mismatch (exit 1), original historical
assertions збережені. У звичайному push цей job буде **SKIPPED/NOT_RUN**, не PASS.
Свіжий локальний `py -3.13 scripts/ci/verify_historical_bundle.py` повернув
**exit 2 / BLOCKED_MISSING_ARTIFACT** через відсутній reviewed manifest;
лог — `outputs/release_readiness/publication/historical_preflight.log`.
Права workflow read-only: contents/actions read. `secrets.GITHUB_TOKEN` —
стандартне посилання Actions, не вшитий токен. Reviewed bundle повинен бути
перевірений людиною: self-consistent manifest не доводить незалежне походження.

Свіжі логи: `outputs/release_readiness/publication/{full.xml,pytest.log,checks.json,
source_lint.log,source_format.log,ruff_check.log,ruff_format.log}`.
Portable snapshot: `outputs/release_readiness/portable_source_only.*`.
Попередні 97 browser assertions/0 JS exceptions із release-readiness тут
цитуються як попереднє evidence; браузерний набір у цій задачі не запускався.

## 6. Наукова незмінність

Математичні модулі, метрики, декодери, seeds та числові результати цією задачею
не змінювалися. У попередньому source diff `energy_experiment.py` — тільки
перестановка import, `atomic_io.py` — тільки видалений порожній рядок.
Заморожені configs/protocols не мають Git diff. Еталонні expected SHA не
редагувалися. Повторний Monte Carlo не запускався.

Свіжий read-only rehash за незмінним baseline: **87714 PASS, 0 FAIL, 32 NOT_VERIFIED**; confirmatory JSON records: **31100**.
Файли без еталонного SHA не зараховано як PASS. Це підтверджує незмінність
наявних зафіксованих EXP-03B артефактів, але не усуває EXP-01 missing ZIP.
Загальний historical audit лишається **PARTIAL/BLOCKED**, не повний PASS.
Evidence: `outputs/release_readiness/publication/historical_rehash.{json,csv}`.

## 7. Точний allowlist для staging

**Нижче лише підготовлені команди. Вони не виконані.** Зараз index порожній.
Це 56 перевірених source-кандидатів плюс цей звіт = **57 файлів**, без outputs,
архівів, приватних документів, тимчасових файлів чи змін frozen configs.
Виконувати тільки після рішення щодо publication-ризиків і окремої згоди
користувача на наступний крок. Такий staging не робить стару history безпечною.

```powershell
git status --short
git diff --check
git add -- '.github/workflows/ci.yml'
git add -- '.gitignore'
git add -- 'PLAN.md'
git add -- 'README.md'
git add -- 'README_RELEASE_UK.md'
git add -- 'scripts/audit_stage4_history.py'
git add -- 'scripts/ci/README.md'
git add -- 'scripts/ci/find_exp01_archive.py'
git add -- 'scripts/ci/portable_source_check.py'
git add -- 'scripts/ci/release_inventory.py'
git add -- 'scripts/ci/run_source_quality.py'
git add -- 'scripts/ci/verify_control_samples.py'
git add -- 'scripts/ci/verify_historical_bundle.py'
git add -- 'scripts/ci/verify_protected_references.py'
git add -- 'scripts/ci/write_release_readiness.py'
git add -- 'scripts/diagnose_exp01b_http.py'
git add -- 'scripts/measure_stage4.py'
git add -- 'scripts/measure_stage4_browser.mjs'
git add -- 'scripts/profile_release_memory.ps1'
git add -- 'scripts/qa_ui_stage3.mjs'
git add -- 'scripts/qa_ui_stage4.mjs'
git add -- 'scripts/qa_ui_stage4_edgecases.mjs'
git add -- 'scripts/qa_ui_stage4_extended.mjs'
git add -- 'scripts/qa_ui_stage4_run_switch.mjs'
git add -- 'scripts/qa_ui_stage4_viewports.mjs'
git add -- 'scripts/stage4_cdp.mjs'
git add -- 'scripts/write_ui_stage4_reports.py'
git add -- 'src/hf_tcm/repro/atomic_io.py'
git add -- 'src/hf_tcm/repro/energy_experiment.py'
git add -- 'src/hf_tcm/studio/energy_view.py'
git add -- 'src/hf_tcm/studio/historical_energy.py'
git add -- 'src/hf_tcm/studio/lab_window.py'
git add -- 'src/hf_tcm/studio/metric_trace.py'
git add -- 'src/hf_tcm/studio/server.py'
git add -- 'src/hf_tcm/studio/static/article_workspace.js'
git add -- 'src/hf_tcm/studio/static/constellation4.js'
git add -- 'src/hf_tcm/studio/static/energy_interactive.js'
git add -- 'src/hf_tcm/studio/static/lab4.js'
git add -- 'src/hf_tcm/studio/static/layout4.js'
git add -- 'src/hf_tcm/studio/static/metric_live.js'
git add -- 'src/hf_tcm/studio/static/scientific.html'
git add -- 'src/hf_tcm/studio/static/scientific.js'
git add -- 'src/hf_tcm/studio/static/scientific_metric.js'
git add -- 'src/hf_tcm/studio/static/scientific_ux.js'
git add -- 'src/hf_tcm/studio/static/sequence_navigator.js'
git add -- 'src/hf_tcm/studio/static/stage4_layout.css'
git add -- 'src/hf_tcm/studio/static/study_catalog.js'
git add -- 'src/hf_tcm/studio/static/trellis4.js'
git add -- 'src/hf_tcm/studio/study_catalog.py'
git add -- 'tests/conftest.py'
git add -- 'tests/studio/test_energy_view.py'
git add -- 'tests/studio/test_historical_http_stability.py'
git add -- 'tests/studio/test_metric_trace.py'
git add -- 'tests/studio/test_stage4_integration.py'
git add -- 'tests/studio/test_study_catalog.py'
git add -- 'tests/test_ci_historical_preflight.py'
git add -- 'GITHUB_PUBLICATION_CHECK_UK.md'
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
git diff --cached
```

Зіставити `--name-status` із наведеними 57 шляхами. Зупинитися при будь-якому
неочікуваному файлі; `git add -A` або `git add .` не використовувати.
У новому чистому repository перелік мусить окремо включати **весь** погоджений
базовий код/config/tests: ці 57 шляхів є delta існуючої гілки, а не повним
набором для самостійної нової інсталяції.

## 8. Пропонований commit і release notes

Пропонований subject:

```text
Stabilize scientific lab interactions and separate portable historical CI
```

Пропонований body:

```text
Complete responsive signal/constellation/energy interactions, shared navigation,
LOD windows, deep links and server-paged saved studies in the existing lab.
Stabilize EXP-01B verified I/O without changing scientific calculations.
Separate portable tests, scoped source quality and artifact-gated historical audit.
Add release instructions, diagnostics and publication review.

Validated locally: 1266 portable passed; full 1318 passed and two EXP-01 cases
blocked by missing original archive. Python 3.11/3.12 current-tree runs pending.
No new Monte Carlo or frozen scientific data/protocol/SHA changes.
```

Умовні release notes: адаптивний існуючий інтерфейс, реальні window/LOD/жести,
синхронний H/E inspector і trellis, інтерактивне сузір’я за RX I/Q, енергетичні
графіки з допустимими gain intersections, серверна пагінація/deep links;
EXP-01B I/O diagnosis/fix; окремі CI jobs; `README_RELEASE_UK.md`.
Великі архіви й дослідницькі outputs не є source-релізом.

Обмеження залишаються: historical EXP-01 BLOCKED; root-wide Ruff не green;
current-tree Python 3.11/3.12 ще не перевірені; права на документи/ілюстрації
та ліцензія коду потребують рішення. `paper_exact:false`, незалежного доказу
статейних 1.5 dB немає; модельна дискретна шкала не є фізичним Eb/N0.
Технічний реліз не є новим науковим підтвердженням результатів.

Після погодження scope, rights і staging, але **лише після окремого дозволу
на commit**, майбутня команда:

```powershell
git commit -m "Stabilize scientific lab interactions and separate portable historical CI"
```

Tag/release/version number не пропонуються як уже погоджені й не створювалися.

## 9. План GitHub Actions після окремо дозволеного push

1. Перед будь-яким push перевірити remote, branch і видимість репозиторію;
   для публічного remote спочатку вирішити всі reachable-history ризики.
2. Лише після окремого дозволу користувача на push погодженої гілки запустити
   push; підстановка `$branch` нижче визначається поточною гілкою, не main навмання.
3. Перевірити **обидва** portable matrix jobs (3.11/3.12), source-quality та CLI
   smoke на тому самому commit SHA; зберегти URLs/run IDs/logs.
4. Звичайний push не запускає historical job: статус NOT_RUN/SKIPPED не
   зараховувати як historical PASS. До отримання справжнього ZIP аудит BLOCKED.
5. Після окремого дозволу на historical dispatch і отримання reviewed bundle
   запустити manual workflow; перевірити SHA/provenance gate і original tests.
   Відсутній ZIP — BLOCKED, mismatch — FAIL. Не замінювати дані та не
   перезапускати Monte Carlo заради green.

Команди читання remote/CI (жодна тут не виконана віддалено):

```powershell
git branch --show-current
git remote -v
gh repo view --json nameWithOwner,visibility,defaultBranchRef
$branch = git branch --show-current
gh run list --workflow ci.yml --branch $branch --limit 5
# Підставити фактичний ID потрібного run на погодженому SHA:
gh run view <RUN_ID> --json headSha,event,status,conclusion,jobs,url
gh run watch <RUN_ID> --exit-status
gh run view <RUN_ID> --log-failed
```

Після окремого дозволу **на push** (не до нього):

```powershell
$branch = git branch --show-current
git push --set-upstream origin $branch
```

Після окремого дозволу **на historical dispatch** та перевіреного artifact:

```powershell
gh workflow run ci.yml --ref <APPROVED_BRANCH> -f run_historical_audit=true -f historical_artifact_run_id=<TRUSTED_RUN_ID> -f historical_artifact_name=hf-tcm-historical-inputs
```

Змінювати видимість репозиторію, переписувати history, створювати release/tag,
завантажувати архіви, встановлювати нові сервіси або публікувати приватні
матеріали без окремого рішення не можна. Точний наступний крок — рішення
власника щодо прав/ліцензії та способу source-only публікації.
