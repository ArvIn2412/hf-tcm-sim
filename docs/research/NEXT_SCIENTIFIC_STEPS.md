# Наступні наукові кроки A–H

Дата: 2026-11-10. **Це пропозиція, не дозвіл виконання.** SCIENTIFIC-EXP-01 та жодну нову Monte Carlo серію під час GUI-UX-02 не запускати. Переходи потребують виконання критерію попереднього кроку та окремого погодження обчислювальної серії. Невиявлена перевага або неможливість фізичного оцінювання — допустимий висновок.

Мета: отримати захищені висновки про конкретне спільне/роздільне приймання TCM–8PSK у заданому модельному каналі; енергетичний результат розглядати лише за виконаних умов нормалізації, fairness та статистичної ідентифікованості. Позначення [СТАТТЯ], [ПРОЄКТ], [УТОЧНИТИ] обов'язкові. Контекст БПЛА не передбачає hardware/flight experiments.

## A. Зафіксувати питання й докази

- **Мета:** відділити перевірку project algorithms, source reproduction та фізичний energy gain.
- **Входи:** readiness audit, актуальний v7 source crosswalk, REPRO-07/08 configs/checkpoints/reports, claim matrix, доступне офіційне завдання (якщо надане).
- **Код:** не змінювати receiver; лише read-only manifest/count audit за потреби, без RNG. Офіційне завдання не підмінювати проєктним ТЗ.
- **Конфігурація:** draft study ID/version, primary estimand `DeltaBER=BER_A-BER_B`, означення information-pair SER, CSI table, pilot/final partitions і frozen scientific flags.
- **Виходи:** proposed protocol, evidence inventory, список unresolved source items, явно обрана гіпотеза.
- **Готово, коли:** кожне завдання має перевірний outcome; історичні M5–M10, pilot та confirmatory дані розділені; немає обіцяного виграшу.
- **Бюджет:** документація/читання збережених даних; 0 нових trials/decoder calls. Залежності: немає.

## B. Узгодити нормалізацію та похибкову подію

- **Мета:** точно визначити, чи доступний лише discrete gamma_b,d, чи можна коректно вводити фізичний Eb/N0.
- **Входи:** `repro08_energy.py`, source (8)–(10), waveform/channel APIs; дані про pulse, sample interval, filtering/N0 та error target від джерела/керівника.
- **Код:** якщо достатньо даних — ізольовані conversion helpers та незалежні dimensional/variance tests; не міняти існуючу sample-domain конвенцію. Якщо недостатньо — зберегти blocker і виконувати лише project study.
- **Конфігурація:** amplitude, s=8, 2 payload bits/transition, sigma_c²; одиниці/definitions/параметри фізичного контракту або явний `physical_snr_defined:false`. Target BER погодити до перегляду final curves; p*=0.05 не прирівнювати до payload BER.
- **Виходи:** normalization decision та derivation, target-event register, tests або обґрунтований NOT_ESTIMABLE.
- **Готово, коли:** всі перетворення мають одиниці/джерело; scaling s/A/noise перевірено; немає мовчазної заміни sample variance на N0.
- **Бюджет:** 0 stochastic trials; лише малі deterministic fixtures. Залежності: A. Фізична гілка може лишитися blocked, не блокуючи чесний discrete study.

## C. Визначити методологічно зіставний baseline

- **Мета:** відокремити full-algorithm A/B0 contrast від метрики та channel-information effects.
- **Входи:** B0 floor audit; B1 static public-tap API; 06B/06C estimator/prior configs.
- **Код:** для static common-CSI study потрібна явна B1 arm інтеграція в isolated paired runner з незалежними tests/observation hashes; для unknown fading спочатку окремий design адаптивного separate front end. Не називати такого baseline вже реалізованим.
- **Конфігурація:** A=06B або A=06C, B=B0/B1 з різними явними labels; спільні public CSI/prior/power/delays, однакові s=8, η=20, termination/flush, payload interval. Допустиме рішення — лишити A/B0 як порівняння цілісних алгоритмів з обмеженням.
- **Виходи:** receiver information table, validated draft configs та arm-selection contract.
- **Готово, коли:** немає truth leakage, mismatched CSI прихованої під назвою «чиста метрика», B1 unknown-fading config відхиляється.
- **Бюджет:** 0 MC; детерміновані small-frame fixtures та відповідні regression tests. Залежності: A, B для означень осі/метрик.

## D. Детерміновані контроли й ресурсна калібровка

- **Мета:** перевірити actual pair і оцінити витрати перед серією.
- **Входи:** frozen candidate configs C, existing identity/static/slow-Rician fixtures, F=20,000 resource reports.
- **Код:** reuse існуючого runner, за потреби додати clock/RSS/disk instrumentation; математику не tune під fixtures.
- **Конфігурація:** Identity, no-noise static `[0,3]`, supported slow Rician; F=32/256, окремий bounded F=20,000 resource check після погодження; exact IDs/seeds і max pair count.
- **Виходи:** hashes, decoded counts, tail/η checks, actual elapsed/peak RSS/disk measurements та прогноз бюджету.
- **Готово, коли:** true paired hashes, controls не мають неочікуваних failures, збережені всі denominators, timeout/stop behavior пояснено. Control failure повертає до C, не маскується більшою серією.
- **Бюджет:** плановий cap для нового довгого pair — 600 s і 2 GB outputs, не гарантія hard timeout; максимум один F=20,000 pair на resource-check revision. Точне число deterministic controls фіксується до запуску. Залежності: C; виконання resource pair окремо погоджується.

## E. Окремий range-finding / precision pilot

- **Мета:** знайти інформативний діапазон та оцінити trial-level variance, failures/zero errors/витрати, не доводити гіпотезу.
- **Входи:** D; старі REPRO-07/08 pilots як planning evidence.
- **Код:** paired runner з validated selected arm, existing ratio-of-sums і cluster bootstrap; планувати коректне поводження з zero-error cells, не звітувати вироджений bootstrap як rare-event bound.
- **Конфігурація:** окремий `pilot` namespace/seed root; кандидат F=256, 3 точки, 20 trials/point (60 pairs), 5,000 bootstrap replicates, summary-only/selected traces. Grid визначити для вибраного baseline; старі noise values не автоматичні author defaults.
- **Виходи:** measured points/CI, counts, independent cluster count, resource/failure report, запропонована final sample size за погодженою точністю та max budget.
- **Готово, коли:** є достатньо informative errors/independent trials для оцінки precision; якщо всі точки нульові, дозволено лише окремий новий range-finding design. Pilot data не включати у final inference.
- **Бюджет:** кандидат max 60 pairs, 2,400 s, 2 GB; реалістичність уточнити після D. Якщо поточна пара перевищує межу, завершення на pair boundary може перевищити wall cap. Залежності: D та окреме погодження.

## F. Незалежна зафіксована довгокадрова серія

- **Мета:** оцінити primary contrast з погодженою точністю на визначеному профілі без добору результату.
- **Входи:** E variance/resources, B normalization status, C fixed arms, підтверджений computing budget.
- **Код:** за потреби isolated design validator/guard для prospective confirmatory режиму: тепер `ExperimentConfig` має лише smoke/pilot/long_frame; не вигадувати існуючий `confirmatory` enum. Resume/stop/count semantics reuse і перевірити.
- **Конфігурація:** F=20,000 як проєктний довгий кадр, не доведений author N* denominator; fixed grid, R за pilot+precision, independent final IDs/seeds; failure rules і max pairs/time/disk, fixed stopping. Немає optional stop за значущістю/desired dB.
- **Виходи:** checkpointed trial records, pooled counts, paired trial-cluster CIs, manifests, actual resource report, primary conclusion включно з «не встановлено».
- **Готово, коли:** всі заплановані trials завершені або прозоро позначено incomplete; failures не трактовані як нуль; CI/precision відповідають preregistered правилу. Недостатній budget — менший обсяг твердження, не вигадана точність.
- **Бюджет:** визначається лише після E; див. арифметику нижче. Це не запуск за поточним документом. Залежності: A–E; фізичний Eb/N0 не обов'язковий для discrete ΔBER, але обов'язковий для фізичного energy claim.

## G. Горизонтальний зсув за спільного target BER

- **Мета:** оцінити виграш лише якщо експеримент і осі роблять його ідентифікованим.
- **Входи:** B фізичний контракт, F matched curves, наперед визначений decoded BER target.
- **Код:** `estimate_energy_gain_db` має guard, linear interpolation між adjacent measured points без extrapolation; окремо реалізувати/перевірити paired-cluster recomputation crossings і invalid-crossing accounting для gain CI, якщо це ще не виконано.
- **Конфігурація:** однакова target event, physical axis unit, interpolation method, seed/replicates/confidence; не прирівнювати discrete gamma shift до фізичного energy gain.
- **Виходи:** target crossings/ΔdB/CI/частка invalid bootstrap crossings або `ENERGY_GAIN_NOT_ESTIMABLE` з причиною.
- **Готово, коли:** обидві measured curves обрамлюють target, немає множинного/відсутнього crossing, method uncertainty прозора. 1,5 дБ не target для tuning.
- **Бюджет:** read-only postprocessing saved clusters; 0 receiver calls. Якщо бракує bracketing — новий окремо погоджений study, а не extrapolation. Залежності: B physical gate і F.

## H. Актуалізувати магістерську та матеріали захисту

- **Мета:** привести 4 розділи, анотацію й висновки до фактичної доказової бази.
- **Входи:** офіційне завдання/кафедральний шаблон, A–G outcomes, fresh GUI acceptance, актуальні outputs/checks.
- **Код:** receiver не змінювати; read-only plotting/export tools лише з frozen data.
- **Конфігурація:** final evidence manifest, figure/table numbering, claims IDs та джерела; окремі M5–M10 historical і REPRO study namespaces.
- **Виходи:** актуалізовані 4 розділи, українська/потрібна закладом інша анотація, claim matrix, measured figures, limitations, appendix із configs/commands і сценарій захисту.
- **Готово, коли:** кожне твердження має evidence, жодне джерельне число не подано як власний результат, placeholders заповнені перевіреними даними; фізичний gain може чесно лишитися неоціненим.
- **Бюджет:** 0 MC/receiver calls; артефактне оформлення та незалежна перевірка тексту. Залежності: A та фактичні доступні outcomes B–G, без вимоги позитивного виграшу.

## Орієнтир часу, а не benchmark

REPRO-06C reference виміряв **152.96 s** для одного adaptive F=20,000 decode і 28,031,692 bytes compressed trace. Peak RAM не виміряний. REPRO-08 мав один pair за 147.804 s; REPRO-07 joint arm одного pair — приблизно 238.66 s. Розкид забороняє видавати 153 s за універсальну швидкість або лінійну гарантію.

Арифметика при умовних **153 s/pair** наведена тільки для планування A/B0 послідовного запуску; не враховує другий дорогий adaptive arm, Tx/channel/I/O/bootstrap, нагрів, зміни frame/trellis або host load:

| Кандидат | Кількість pairs | 153 s × pairs | Повні traces по 28.0 MB, грубо |
|---|---:|---:|---:|
| Один resource pair | 1 | 2.55 хв | 28 MB |
| 20 trials × 3 точки | 60 | 2.55 год | 1.68 GB |
| 100 trials × 3 точки | 300 | 12.75 год | 8.4 GB |
| 100 trials × 5 точок | 500 | 21.25 год | 14.0 GB |

При одиничному спостереженні 238.66 s для 300 pairs арифметика вже близько 19.9 год. Плановий wall cap не дорівнює прогнозу і має включати резерв/правило зупинки. Це достатня причина спочатку виміряти D та залишати summary-only плюс небагато selected traces. Водночас summaries не скасовують allocation діагностичних масивів усередині receiver; RAM вимірювати окремо. Короткий F=256 pilot має свої виміряні витрати, не переносити на нього 153 s від F=20,000. Ніякого worker pool чи нового сервісу за цим планом не встановлювати.

## Один конкретний наступний запит Codex

> **SCIENTIFIC-EXP-01-PREP — лише дизайн, без виконання.** Прочитай PLAN/NEXT_TASK, ці три readiness документи та актуальний source crosswalk. Створи ізольований proposed протокол одного primary paired дослідження: зафіксуй A/B0 як повні алгоритми або аргументовано запропонуй static common-CSI A/B1; випиши інформацію кожного receiver, definitions BER/pair-SER, discrete gamma_b,d та physical blockers, pilot/final seed namespaces, sample-size/precision procedure, stopping/failure rules і resource budget за вимірюваннями. Перевір фактичну сумісність запропонованих полів з ExperimentConfig; розбіжності випиши як майбутні зміни, не реалізуй і не приховуй. Збережи proposed protocol/config draft поза історичними outputs. Не викликай RNG, transmitter/channel/receiver, decoder, Monte Carlo; не міняй production mathematics, ADR, історичні artifacts або прапорці fidelity. Заверши reviewable design та переліком питань, які реально блокують виконання. Не запускай серію автоматично.

Цей запит рекомендується як наступна окрема фаза; він **не виконувався** в GUI-UX-02. Поточні `PLAN.md`/`NEXT_TASK.md` цей документ не змінює.
