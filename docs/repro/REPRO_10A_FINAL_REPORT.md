# REPRO-10A — фінальний звіт scientific correctness та GUI hotfix

## Статус

`REPRO_10A_SCIENTIFIC_HOTFIX_READY`. Final pytest, Ruff, Node, Edge QA, manifests and historical verifier passed. Статус не змінює `paper_exact:false` і не стверджує відтворення 1.5 dB.

## BER/SER висновок

У REPRO-10 `pair errors` були фактично hard 8PSK phase-symbol errors, тоді як BER рахувався на decoded information bits. Тому показники відповідали різним стадіям receiver. Історичний F=256 мав 56 bit errors, 47 information-pair errors і 60 hard-phase errors. F=32 мав 7 bit errors, 6 information-pair errors і 9 hard-phase errors. Незалежна перевірка підтвердила інваріант для узгоджених bit/pair counts. Backend receiver decisions та BER не змінювалися; додано явні різні SER поля, labels та read-only enrichment старих summaries.

## PNG/SVG та українські підписи

Повністю прозорий 300×310 PNG виникав, коли Edge експортував canvas до завершення асинхронного `drawAll()`. Експорт тепер чекає per-canvas completion flag, а renderers створюють непрозорий фон перед нанесенням реальних даних. Edge декодував та перевірив PNG content/alpha; PNG експорт перевірений для transmitted/received I/Q, Joint/Hamming metrics, BER та error chart. Решітка експортується у валідний SVG із 90 trace paths. Mojibake кнопки замінено коректним `Зберегти PNG`; text responses/HTML/JSON/SVG перевірені на UTF-8.

Графіки отримали заголовок у PNG, більш безпечний простір для назви й підпису осі та центрування довгої назви осі. Числові дані не downsample-ились для експорту й не змінювались.

## Контрольні запуски

Див. `outputs/repro10a/reference_control_summary.json`, manifests і traces у `outputs/repro10a/reference_runs/`:

- Identity, F=32, zero noise: Joint/B0/B1 кожен 0/64 bit errors, 0/32 information-pair errors і 0/32 phase errors. Observation SHA-256: `90ea6afdad78bbbb33464ece32e5fdcd21139a8f11f6570b84337b17c1f6aaf3`.
- Static multipath `[0,3]`, F=32, zero noise: received sample count 259; Joint/B0/B1 кожен 0 bit, pair і phase errors. Observation SHA-256: `44007abbe287094f21cf7ed07b486e2cb5b321a85add814101ba56b8b01ae1c5`.
- Rician AR(1) multipath, F=32, complex sample variance 0.005: Joint 0/64 bit errors, B0 1/64, pair counts 0 і 1 відповідно; phase errors 0 і 2. B1 не запускався. Observation SHA-256: `b7542ddc3ff1f3c2b42435a94d299f3744078660c5155d0d32253ac87279cd24`.

Edge acceptance додатково виконав реальні Identity/B1, static multipath/B1, Rician/B1 unavailable та paired Monte Carlo F=128: sample-domain variances 0.01 і 0.1, п'ять незалежних trials на рівень, stop після збереження поточної пари, resume до 10/10. Для цього QA seed Joint BER склав 0 і 0 на точках; B0 BER — 0.125 та 0.178125; information-pair SER Joint — 0 і 0, B0 — 0.2234375 та 0.3046875. DeltaBER — −0.125 та −0.178125; парні bootstrap CI відповідно [−0.144531, −0.105840] та [−0.226563, −0.138281]. Це малий exploratory pilot, не підтвердження статистичної переваги. Joint/B0 одержали однакові observation у кожній парі. Повні дані та QA у `outputs/repro10a/acceptance/gui_qa_report.json` і `outputs/repro10a/paired_experiment/`.

Long-frame viewer перевірив наявний F=20000 архів без повторного дорогого simulation: метрики доступні, I/Q відсутні, це чесно позначено; старі REPRO-08 summaries різних observations не об'єднуються.

Для наступної повноцінної Monte Carlo серії GUI має перевірені start/stop/resume та paired data pipeline, але виконаний тут pilot — лише exploratory (5 trials на noise point). Він не підтверджує перевагу алгоритму чи статтю; перед confirmatory study слід заздалегідь зафіксувати frame/trial design і ресурсний бюджет.

## Регресійна перевірка

Targeted: `tests/repro/test_information_pair_metrics_10a.py`, `tests/repro/test_scientific_workspace.py`, `tests/repro/test_scientific_workspace_09b.py`. Вони включають незалежний підрахунок помилок із trace arrays та read-only старого summary із перевіркою незмінності файлів.

Фінальні результати: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro10a-final-20261110 -p no:cacheprovider` — **1182 passed in 58.14 s**; `ruff check src tests` та `ruff format --check src tests` — PASS (261 files); scoped Ruff — PASS; Node syntax — PASS. Edge acceptance — **19/19 checks**, включно з 1366×768 та 1920×1080. `python scripts/verify_repro06b_artifacts.py` — 76/76 archived files, 27 SVG parsed, **694/694 historical M5–M10 fingerprints**, no failures. `python scripts/verify_repro10a_outputs.py` підтвердив manifests, PNG/SVG content та скриншоти. Історичні REPRO-02–10 output directories не редагувалися; hashes старих summary/traces підтверджені до/після read-only recount.

Післяфіксові Edge скриншоти: `docs/screenshots/repro10a-transmitter-1366x768.png`, `repro10a-channel-1366x768.png`, `repro10a-joint-1366x768.png`, `repro10a-separate-1366x768.png`, `repro10a-comparison-1366x768.png`, `repro10a-viterbi-1366x768.png`, `repro10a-monte-carlo-1366x768.png`, `repro10a-long-frame-1920x1080.png`, `repro10a-transmitter-1920x1080.png`, `repro10a-channel-1920x1080.png`.

Аудитний пакет створено у корені: `HF_TCM_SIM_REPRO_10A_AUDIT.zip`. Остаточні розмір/hash/file count наведені в кінцевому повідомленні. Вміст ZIP відкрито, кожен member звірено з manifest; PNG decoded і перевірені на видимий opaque вміст, SVG XML валідовано. Статус перевірки записано в `docs/BUILD_VERIFICATION.md`.

## Наукові межі

Математика transmitter, channel і receivers не змінювалась. Sample-domain noise variance не називається Eb/N0. B0 лишається окремим receiver без ISI compensation; B1 доступний лише у підтримуваних public static режимах; adaptive Joint не використовує EvaluationTruth. 1.5 dB — лише заява першоджерела; ніякого gain-fitting чи BER-vs-SNR досліду в цьому hotfix не було. Hotfix узгоджує класифікацію метрик і видимий графічний експорт, але не є підставою оголошувати повну статейну репродукцію або фінальну Monte Carlo серію готовою без окремого дослідження.
