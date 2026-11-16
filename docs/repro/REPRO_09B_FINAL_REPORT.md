# REPRO-09B — підсумковий звіт

Дата перевірки: 2026-11-10.

## Вердикт

**`REPRO_09B_SCIENTIFIC_GUI_PARTIAL`**. Scientific Workspace тепер має реальні trellis/survivor/traceback екрани, B1 для підтримуваних публічних статичних taps, завершений browser acceptance для stop/resume Monte Carlo та lazy viewer перевірених F=20,000 архівів. Історичний fingerprint лишився 693/694, тому загальний `READY` за критеріями milestone не заявляється.

### Уточнення команди запуску

Після первинного звіту з'ясувалося, що `--no-browser` не відкриває браузер, а корінь спільного сервера за замовчуванням показував M11. Додано окремий server default view для scientific entrypoint: він віддає Scientific Workspace і на `/`, і на `/scientific`; виклик `make_server()` зі старого demo launcher зберігає M11 root. Команду `python -m hf_tcm.repro.scientific_studio --port 18769` фактично запущено без `--no-browser`; вона відкрила браузер, а HTTP-перевірка підтвердила, що обидва маршрути віддають Scientific Workspace і `/` не містить M11 Demo. Також це перевірено HTTP-тестом і повторною Edge QA.

## Реально перевірені функції

- Запуск існуючого Scientific Workspace окремим entrypoint: `python -m hf_tcm.repro.scientific_studio --port 18769`. Команду запуску перевірено з автоматичним відкриттям браузера; сторінка не запускає симуляцію автоматично. Edge acceptance окремо перевірив і root `/`, і прямий `/scientific` маршрут.
- Одиничні запуски проходять через справжні REPRO-02 → REPRO-03 → Joint REPRO-06C / B0 REPRO-04. B1 викликає наявний REPRO-08 channel-aware hard receiver тільки на явних public static taps; Rician-профіль його відхиляє/вимикає. Усі підключені приймачі отримують один `ReceiverObservation`.
- Вітербі explorer показує реальні branch costs, cumulative state metrics, вибір/відмову переходів, local survivor traceback, emitted finite-depth decision та frame-flush semantics. Доданий destination-state selector для вибору конкретного survivor endpoint; click edge відкриває дані переходу.
- Для Encoder A відображається фактична решітка 4 states / 16 edges. Для затримок `[0,3]` відображається перевірена augmented trellis 17 states / 68 edges. Стан не підставляється для інших профілів.
- Навігація синхронізує symbol `k` між графіками; sample mapping — `n=8k+i`. Виправлено гонку, за якої Viterbi міг читати застаріле значення свого поля замість спільного індексу. 20-transition traceback окремий від 20-complex-sample zoom. Останні 3 delayed samples позначаються як tail, а не додатковий символ.
- Monte Carlo GUI викликає REPRO-07 runner (Joint+B0), показує фактичний прогрес, зупиняється на межі completed pair, відновлює за тим самим experiment ID та будує графіки тільки з завершених trials.
- Великий viewer перевіряє обидва архівні manifests і підвантажує лише вибраний Viterbi window. REPRO-08 metrics і REPRO-06C trace мають різні observation hashes (`same_observation=false`), тому GUI не склеює їх у фальшивий спільний сигнал. Архів не містить I/Q чисел; відсутні traces позначені як недоступні.

## Фактичні результати Edge QA

Сценарії пройшли через реальну Edge CDP взаємодію, не mock screenshots:

| Сценарій | Фактичний результат |
|---|---|
| Identity, F=32 | Joint 0/64 bit errors; B0 0/64; B1 0/64. 256 received samples. Observation SHA-256 `84599f8db4c4c990ddd4206b2f5ad1ab7eb104e5ba470d88e5de396db581a74e`. |
| Static multipath `[0,3]`, F=32 | Joint/B0/B1 — 0/64 bit errors у цьому noiseless fixture; 259 received samples; 17/68 trellis. Hash `e5ce22117b404d442e4bc32fd6b12147b4687d8e5e714ae1619863e09dbf524c`. |
| Rician AR(1) multipath, F=32 | Joint 0/64; B0 7/64 (BER 0.109375); B1 недоступний. Парність перевірена. Hash `ab0d4ad36e0334baf7d64754830b4e59b13499024a25494d2aa04ba1dfa241c0`. Це один короткий fixture, не твердження про якість алгоритму. |
| Monte Carlo stop/resume | F=128, `noise_variance=[0.01, 0.1]`, 5 незалежних paired trials на точку. Stop зберіг 2/10; resume завершив 10/10 без повторного зарахування. 1,280 порівняних бітів на точку. |

У завершеній exploratory серії:

| Комплексна sample-domain noise variance | Joint BER / pair SER | B0 BER / pair SER | ΔBER (Joint−B0), 95% paired cluster CI |
|---:|---:|---:|---:|
| 0.01 | 0/1280 = 0; 0/640 = 0 | 168/1280 = 0.13125; 144/640 = 0.225 | −0.13125; [−0.18203125, −0.08046875] |
| 0.1 | 6/1280 = 0.0046875; 5/640 = 0.0078125 | 181/1280 = 0.14140625; 156/640 = 0.24375 | −0.13671875; [−0.18671875, −0.096875] |

Фінальний browser run: `repro09b-resume-1794301801843`; 500 bootstrap повторів із ресемплюванням paired trials; його manifest містить 12 перевірених файлів. П'ять незалежних trials на рівень — лише exploratory GUI acceptance, не надійний висновок про перевагу. Noise вісь є комплексною sample-domain variance, не Eb/N0. B1 у цю MC серію не входив.

F=20,000 viewer відкрив наявні REPRO-08 metrics (40,000 bits; Joint BER 0.00052521, B0 BER 0.14575828) та окрему REPRO-06C trace (17/68). Їхні hash різняться, а archived signal samples відсутні; отже це не same-observation waveform comparison. Жодний дорогий F=20,000 simulation для viewer QA не запускався.

## Скриншоти та manifests

Edge QA пройшла у вікнах 1366×768 та 1920×1080. Реальні збережені screenshots:

- `docs/screenshots/repro09b-viterbi-1366x768.png` — Viterbi explorer / η=20.
- `docs/screenshots/repro09b-long-frame-1920x1080.png` — перевірений довгий архівний результат.

Screenshot SHA-256: `repro09b-viterbi-1366x768.png` — `79a7babacac7547c4b7ea3ca3d2f3f5112ac82156344bc7d98258cb5c443ab5e`; `repro09b-long-frame-1920x1080.png` — `7594977d02440fa5737f4a77d6c1cd34c6913fdd28e7e7aa1d6b7d5bf2eddf9b`.

Повторно перевірено manifests трьох фінальних Edge single runs (`load_run_summary`), 12 файлів завершеного Monte Carlo manifest (`verify_experiment`) і REPRO-08/REPRO-06C archive manifests (`load_long_frame_archive`). Всі hash перевірки пройшли; archived inputs лишилися розділені.

## Історична цілісність та перевірки

- Повний тестовий набір після root-route виправлення: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro09b-final-fix -p no:cacheprovider` — **1174 passed in 60.25 s**.
- Scoped Ruff: `ruff check src/hf_tcm/studio/scientific.py src/hf_tcm/studio/server.py src/hf_tcm/repro/scientific_studio.py src/hf_tcm/demo_studio.py tests/repro/test_scientific_workspace_09b.py` — passed.
- Scoped format: та сама п'ять Python-файлів через `ruff format --check` — passed.
- Node syntax: `node --check` для scientific.js, scientific_i18n.js та Edge QA script — passed.
- Edge QA driver: `node scripts/qa_repro09b_scientific.js` — passed усі перевірки, включно з root URL Scientific Workspace, двома viewport sizes та screenshots.
- `python scripts/verify_repro06b_artifacts.py` — 76/76 REPRO-06B root files і 27 SVG валідні; historical fingerprints **693/694**, єдиний failure: `historical:src/hf_tcm/demo_studio.py`.

Fingerprint-файл checker та expected hash не змінювалися. У checkout немає `.git` repository, а accepted pre-change bytes `demo_studio.py` не знайдено, тому exact historical файл відновити без підміни даних неможливо. Новий scientific launcher окремий, legacy CLI більше не має scientific flag; mismatch залишено видимим. M5–M10 outputs, source math і accepted ADR не змінювалися.

## Статуси

| Статус | Оцінка |
|---|---|
| `VITERBI_TRELLIS_VIEW` | READY |
| `SURVIVOR_EXPLORER` | READY |
| `ETA20_TRACEBACK_VIEW` | READY |
| `SYNCHRONIZED_SIGNAL_VIEW` | READY |
| `B1_GUI_INTEGRATION` | READY для підтримуваного public-static profile; Rician не підтримується |
| `MULTI_TRIAL_MONTE_CARLO_GUI` | READY для підключеного REPRO-07 Joint+B0 runner; результат тестового запуску exploratory |
| `MONTE_CARLO_STOP_RESUME` | READY, browser-verified 2/10 → 10/10 |
| `LONG_FRAME_VIEWER` | READY для перевірених архівних summaries/trace; повний waveform у них відсутній |
| `HISTORICAL_FINGERPRINTS_694` | PARTIAL — 693/694 |
| `EDGE_GUI_ACCEPTANCE` | READY для перевірених A–L сценаріїв у межах доступних архівів і профілів; не запускали дорогий F=20,000 симулятор |

Залишилися: відновити байт-у-байт accepted `demo_studio.py` з надійного джерела, якщо воно з'явиться; за потреби зберігати вибрані повні F=20,000 signal diagnostics для спільного viewer. B1 не входить у Monte Carlo GUI; Rician B1 недоступний; мала MC серія не є підтверджувальним дослідженням. Статейні обмеження, `paper_exact:false` і непідтверджений claim 1.5 dB збережені. **REPRO-10 не розпочато.**
