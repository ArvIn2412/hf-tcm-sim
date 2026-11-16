# REPRO-10 — фінальне приймання Scientific Workspace

Дата перевірки: 2026-11-10.

## Вердикт

`REPRO_10_APPLICATION_READY_WITH_DOCUMENTED_EXCEPTION`.

Scientific Workspace запускається окремим entry point, виконує реальні REPRO transmitter/channel/receiver обчислення, показує receiver diagnostics, зберігає результати та дозволяє відкрити їх повторно. Історичний fingerprint відновлено до 694/694. Статус стосується готовності програми до практичної роботи з чітко задокументованими науковими обмеженнями; він не підтверджує повне відтворення статті.

Окремі наукові статуси: `paper_exact:false`, `ARTICLE_REPRODUCTION_INSUFFICIENT_DATA`, `ENERGY_GAIN_NOT_ESTIMABLE`. Заявлені в статті 1.5 dB не отримані моделюванням і не підставлялись у результати.

Приймальні статуси: `WINDOWS_LAUNCH_READY`, `GUI_END_TO_END_READY`, `SCIENTIFIC_VISUALIZATIONS_READY`, `VITERBI_EXPLORER_READY`, `RECEIVER_COMPARISON_READY`, `MONTE_CARLO_READY` (для перевіреного exploratory профілю), `RESULT_SAVE_LOAD_READY`, `LONG_FRAME_VIEWER_READY` (архівні I/Q відсутні й показані як unavailable), `EDGE_ACCEPTANCE_READY`, `HISTORICAL_INTEGRITY_READY`.

## Запуск та backend

Перевірена команда з кореня проєкту:

```powershell
python -m hf_tcm.repro.scientific_studio --port 18769 --no-browser
```

Перевірені HTTP-відповіді `/` і `/scientific` показують Scientific Workspace; `/api/health` повертає `ready`, не запускаючи receiver. Історичний `python -m hf_tcm.demo_studio` залишився окремим M11 launcher. Чиста інсталяція на новій Windows-машині не тестувалась; залежності описані в user guide та `pyproject.toml` (Python >=3.11, NumPy >=1.24).

## Фактичне GUI-приймання

Edge acceptance через `node scripts/qa_repro09b_scientific.js` пройшов на 1366×768 та 1920×1080. Перевірено запуск без автоматичного моделювання, налаштування, transmitter/channel/receiver переходи, синхронізацію вибраного символу з індексами `n=8k+i`, реальні графіки, save/load, receiver comparison, Viterbi explorer, stop/resume Monte Carlo, відкриття великого архіву й PNG-експорт із canvas.

- **Identity, F=32, без шуму:** 64 інформаційні біти; Joint, B0 і B1 мають 0 помилок; один спільний observation hash починається `84599f8db4c4c990`. Сценарій збережено й відкрито повторно.
- **Static multipath, затримки [0,3], F=32:** 259 прийнятих відліків; GUI показує delayed paths/ISI та фактичний augmented trellis 17 станів / 68 переходів. У контрольному прогоні Joint/B0/B1 мали 0/64 помилок. Hash спостереження для всіх трьох — `e5ce22117b404d442e4bc32fd6b12147b4687d8e5e714ae1619863e09dbf524c`.
- **Rician AR(1), F=32:** справжній channel generator і adaptive Joint/B0 виконані; B1 вимкнений як непідтримуваний. Контрольний кадр: Joint 0/64 bit errors, BER/SER 0/0; B0 7/64 bit errors, BER 0.109375, information-pair SER 0.28125; це один кадр, не оцінка якості. Спостереження має спільний hash `ab0d4ad36e0334baf7d64754830b4e59b13499024a25494d2aa04ba1dfa241c0`.
- **η=20 та решітка:** перевірено 4/16 Encoder A, вибір endpoint survivor і transition, а також 17/68 для `[0,3]`. Traceback-вікно містить 20 trellis transitions; окремий zoom має 20 complex samples. UI розрізняє emitted decisions, локальні survivor paths і реконструйований шлях. Візуальні числові дані беруться з decoder diagnostics.
- **Monte Carlo:** реальний GUI-запуск F=128, дві дисперсії sample-domain шуму `0.01` і `0.1`, по 5 незалежних paired trials на точку; зупинка після завершеної пари та resume завершили 10/10 пар без дублювання. Experiment `repro09b-resume-1794304586006`; BER Joint/B0: `0 / 0.140625` при `0.01`; `0.00078125 / 0.16484375` при `0.1`. Information-pair SER: `0 / 0.25`; `0.0015625 / 0.290625`. 95% paired trial-bootstrap CI для DeltaBER: `[-0.17578125, -0.10625]` та `[-0.2015625, -0.1328125]`. Manifest має 12 перевірених файлів, SHA-256 `36466dc35dcc88a362a00dfa92d5f4fc95d5e8d531dce14155ebf02db66b7249`. Статус — exploratory через п'ять незалежних realizations на точку. Це sample-domain noise variance, не Eb/N0.
- **PNG:** перевірено фактичне завантаження та PNG signature із canvas; файл, включений до acceptance manifest, має 3,147 байтів.
- **F=20,000 archive:** integrity-verified metrics і lazy Viterbi window відкриваються без повторного моделювання. У наявному архіві REPRO-08 metrics і REPRO-06C trace мають різні observation hashes, а I/Q traces відсутні. Інтерфейс явно повідомляє `same observation=false` та `signal unavailable`; їх не об'єднано й не реконструйовано. Тому це перевірений перегляд наявних метрик/діагностики, не повний I/Q replay.

Screenshots реальних екранів: [Viterbi explorer 1366×768](../../docs/screenshots/repro09b-viterbi-1366x768.png), [long-frame viewer 1920×1080](../../docs/screenshots/repro09b-long-frame-1920x1080.png). PNG graph export: `outputs/repro10/acceptance/hf-tcm-run-20261110-115613-8afe3624-chart-tx-k0.png` (SHA-256 `1d03733b6e39f891470018c88777a0115fdd6005af59bca90bf06d8264e0dd4b`). Перелік приймальних PNG з SHA збережено в `outputs/repro10/acceptance/manifest.json` (SHA-256 `43eb80d62d4635071677faa42c85b39292a11e4f52d4ad62f9de6c4d534361f9`, 8 записів; усі hashes перевірені).

## Історична цілісність і якість

- `python scripts/verify_repro06b_artifacts.py` — 694/694 fingerprints, 76/76 REPRO-06B files, 27 SVG XML documents.
- Початковий `src/hf_tcm/demo_studio.py` відновлено з валідного `chatgpt_review_bundle/02_PYTHON_SOURCE_AND_GUI.zip`. SHA-256 збігається з прийнятим fingerprint: `2f652479da237220358a1e0343cc4cbe591d0d88ea4ededfb4bb47b30acff815`. Науковий запуск залишено окремо в `hf_tcm.repro.scientific_studio`; перевірено `--help` і фактичний запуск.
- Scoped `ruff check` — PASS; `ruff format --check` — PASS (4 Python файли).
- Node syntax: `scientific.js`, `qa_repro09b_scientific.js`, `trellis_projector.js`, `signal_window.js` — PASS.
- `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro10-final -p no:cacheprovider` — **1174 passed in 153.40 s**.
- Root-wide Ruff не використовувався як gate через відомі ACL-protected дерева та сторонні generated-script findings. ACL-захищені тимчасові каталоги не видалялися.

## Наукові межі та висновок

Основний GUI-пайплайн порівнює адаптивний Joint REPRO-06C з B0 REPRO-04 на одному `ReceiverObservation`. B1 REPRO-08 є окремим channel-aware hard/Hamming контролем лише для підтримуваних identity/public-static channel profiles; B1 не вмикається для Rician. Монте-Карло GUI наразі порівнює Joint/B0, що відповідає перевіреному runner. Інтерфейс не видає `gamma_b,d` за фізичний Eb/N0, не робить заяву про виграш 1.5 dB і не ставить `paper_exact:true`.

Програма придатна для практичних відтворюваних досліджень у межах наявних project-defined профілів, із збереженням конфігурацій, seeds, hashes, receiver outputs та відкритих обмежень. Вона не є доказом точного відтворення статті; для дисертаційних висновків потрібні чітко визначені фізичні параметри/цільова ймовірність помилки та достатньо потужна preregistered довга серія.
