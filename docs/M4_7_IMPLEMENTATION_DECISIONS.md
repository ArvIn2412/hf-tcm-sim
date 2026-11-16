# M4.7a — рішення та плани інтеграції адаптивного приймача

**Status:** historical M4.7 planning record with implementation decisions appended through M5a. Current accepted/proposed ADR states are recorded in ASSUMPTIONS_AND_DECISIONS.md.

Документ розділяє два несумісні результати: source-faithful реалізацію, яка чекає на авторські означення, та завершений offline реконструктивний режим з окремими проєктними ADR. Результати реконструкції не можна називати точним відтворенням [A]. Формули [B]/[C] нижче є історичним контекстом лише там, де це прямо зазначено; їхні коефіцієнти, маркування та моделі не переносяться в [A].

## Вихідна точка та правила доказовості

- `hypotheses.py` дає 16 структурних переходів encoder/trellis (4 стани пам'яті × 4 входи), а не 16 станів пам'яті і не доведену нумерацію `θ`.
- `posterior.py` задає лише загальну log-space Bayes-рекурсію. Prior, рядково-стохастична матриця та невід'ємні likelihoods є явними входами; маска дозволів `0/1` не є transition probabilities.
- `likelihood.py` обчислює лише `C·Σ hypot(r_I,r_Q)` з [B](7). Сторінка [B] не визначає знак/значення `C`; цей компонент не є доведеною likelihood для [A].
- `paper_recursion.py`, `iq_prediction.py` та `paper_metric.py` — ізольовані algebraic kernels. Вони не утворюють спільний receiver. `iq_prediction.py` буквально реалізує [A](5) лише для явно заданих `b, μ₁, μ₂`; `paper_metric.py` — суму квадратів [A](2) для однієї траєкторії, не `argmin`.
- [A](1)–(2) — друк. с. 4; [A](3)–(6) — с. 5; фазовий індекс та `η=20` описані на с. 6; шумові (9)–(10) — с. 7. Перевірені відповідності та межі див. `M4_EQUATION_TRACEABILITY.md`.
- [B](7), друк. с. 6 (PDF p. 8), — двостановий OPM приклад; узагальнення TCM описано окремо на друк. с. 11 (PDF p. 13). [B](15) — друк. с. 10 (PDF p. 12), (20) — друк. с. 11 (PDF p. 13). Це не доводить перенесення їхніх моделей на [A].
- [C](4.9)–(4.10), (4.19)–(4.22) та табл. 4.1 належать іншій роботі. Вони не встановлюють для [A] шумову нормалізацію, fading law або labeling. Зокрема, `σ` у [A] і [C] має різні нормалізації; у табл. 4.1 [C] є відкрита суперечність з її схемою/матрицею.
- `ChannelTruth` — evaluation/diagnostic дані симулятора. Estimated receiver має бачити лише `received` samples та власні оцінки/configuration; він не читає `.truth`, path coefficients із truth або симульовані per-path внески.

## Нерозв'язані зв'язки

### 1. Гіпотеза `θ` → фазовий індекс `b`

- **Джерело:** [A](3)–(6), друк. с. 5, задає `b` і `Δφ=π/4`; `iq_prediction.py` приймає `b` явно. [C], табл. 4.1, друк. с. 127 (PDF p. 19), підтверджує своє правило `B=4C₂+2C₁+C₀`, але має описану в `M4_OPEN_QUESTIONS.md` суперечність із [C], рис. 4.5a / `G₁`, друк. с. 126 (PDF p. 18).
- **Точно відомо:** у M1 вихідний кортеж має локальний порядок `(c₂,c₁,c₀)`; M4.1 зберігає його в кожному рядку гіпотези. [A](5) задає алгебру після того, як числовий `b` уже відомий.
- **Невідомо:** чи `b` утворюється безпосередньо з вихідних бітів, який порядок бітів застосувати, чи є фазовий зсув, і чи авторське `θ` збігається з одним з 16 рядків.
- **Чи виводиться:** ні. G(x) визначає encoder output, але не labeling 8PSK; приклад [C] не є доказом для [A].
- **Мінімальний інтерфейс:** source-faithful: тільки явний `b` до `iq_prediction`; adapter `θ→b` дозволений лише після підтвердженого mapping. Reconstruction: окремий `labeling_profile` із явною функцією `output_bits→b` та ім'ям профілю.
- **Перевірка:** exhaustive table для всіх 8 labels і 16 M4.1 hypotheses; для кожного профілю перевірити inverse consistency, encoder output та I/Q таблицю [A](5). Авторське твердження дозволене лише для окремо підтвердженої таблиці.
- **Вплив на BER:** високий. Перестановка фаз змінює відповідність гілки символу, демодуляцію та інформаційні помилки; напрям і величину зміни не можна передбачити без вимірювання.

### 2. Likelihood для posterior

- **Джерело:** [A](1) вимагає posterior ваги в рекурсії, але перевірені [A] с. 4–7 не дають завершеної likelihood-моделі для 8PSK TCM. [B](7), друк. с. 6 (PDF p. 8), задає OPM-компонент з експонентою від `C·Σ norm`; текст на друк. с. 11 (PDF p. 13) описує узагальнення, не повну числову модель для [A]. [A](2), с. 4, є квадратним metric, а не posterior likelihood.
- **Точно відомо:** чинний модуль повертає тільки log-компонент `[B](7)`, із явним `C`; знак і величина `C` невідомі. Kernel [A](2) обчислює суму квадратів.
- **Невідомо:** функція від залишку до `L_α`, зв'язок likelihood з `F`, знак/масштаб параметрів, нормування та узгодження [A](1) з [A](2).
- **Чи виводиться:** ні. Перетворення `exp(−βF)` чи Gaussian likelihood потребує нового припущення і не випливає з [A](1)/(2) або [B](7).
- **Мінімальний інтерфейс:** `likelihoods_for_candidates(observations, predictions, candidate_ids, model_parameters) -> nonnegative vector`, або log-likelihood-вектор із явно визначеним контрактом; функція не має обирати приховані `C/β`.
- **Перевірка:** ручне відтворення авторської формули після її уточнення; нормування posterior, zero-evidence та граничні залишки; окремий тест, що reconstruction likelihood не маркується як [A]/[B].
- **Вплив на BER:** критичний. Ваги змінюють оновлення оцінок і вибір траєкторії. BER reconstruction залежить від обраного масштабу likelihood; це слід звітувати та аналізувати чутливість.

### 3. Transition probabilities

- **Джерело:** [A](1), с. 4, містить posterior над дискретними кандидатами; [B](7), с. 6 (PDF p. 8), показує `π` для OPM, а TCM-узагальнення на с. 11 (PDF p. 13) лише вимагає відповідну transition matrix. M4.2 задає структурну 16×16 маску.
- **Точно відомо:** edge `h→g` структурно дозволений, коли `next_state(h)==current_state(g)`. `posterior_update` очікує окрему рядково-стохастичну матрицю та забороняє масу на недозволених ребрах.
- **Невідомо:** авторські `π_{β,α}`, орієнтація їхніх індексів відносно рядків коду, часовий крок та ймовірності входів.
- **Чи виводиться:** ні. Структура trellis обмежує support, але не розподіл ваг.
- **Мінімальний інтерфейс:** явна `transition_matrix[previous_hypothesis,next_hypothesis]`, пов'язана з версією labeling/гіпотез і перевірена на support та row-stochasticity.
- **Перевірка:** кожне ненульове ребро має відповідати дозволеному переходу; сума рядка дорівнює 1; hand-calculated posterior на малому прикладі; авторські значення — лише при наявності матриці/правила з [A].
- **Вплив на BER:** високий, бо переходи задають апріорну ймовірність допустимих послідовностей; реконструкція має порівняти мінімум дві явно зазначені моделі переходів.

### 4. Initial posterior та початкові умови дискретного стану

- **Джерело:** [A](1), с. 4, використовує попередній posterior; повний початковий prior і стартова конвенція на перевірених сторінках [A] не задані. M2 має проєктний `INITIAL_STATE=(0,0)`, але це не prior статті.
- **Точно відомо:** `posterior_update` вимагає явний нормований вектор довжини 16. Чотири стани пам'яті не тотожні 16 структурним гіпотезам. Кількість авторських `M` не остаточно встановлена.
- **Невідомо:** початковий розподіл `θ`, чи відомий encoder state, як ініціалізується перший кадр та чи треба розподіляти prior між гіпотезами з однакового стану.
- **Чи виводиться:** ні; з trellis немає інформації про prior. Формула `M=2^(ν+k)` у [B] не усуває невизначеність `ν/k` для [A].
- **Мінімальний інтерфейс:** `initial_distribution: (M,)` плюс явний `initial_state`/маска допустимих стартових кандидатів і метадані індексації.
- **Перевірка:** вручну перевірити нормування та support для кожного сценарію; перший крок posterior порівняти з незалежним підрахунком; sensitivity-test альтернативних початкових розподілів.
- **Вплив на BER:** суттєвий на коротких кадрах, після скидання стану та на межах вікна; для довгих кадрів згасання початкового впливу не гарантується без аналізу.

### 5. Per-path observations без `ChannelTruth`

- **Джерело:** [A](4), с. 5, задає сумарний прийнятий сигнал як суму path-внесків; [A](1)/(2), с. 4, використовує `U^{(l)}_{j,i}` із path-індексом. Докладніше provenance розглянуто в `M4_INTEGRATION_CONTRACT.md`.
- **Точно відомо:** поточний receiver має сумарні `ChannelOutput.received`; `ChannelOutput.truth` зберігає окремі coefficients/delays для діагностики. M4 kernels приймають per-path масиви явно, але не формують їх. Саме з сумарного виміру окремі шляхи без додаткових умов не відновлюються однозначно.
- **Невідомо:** який receiver-side оператор/спостерігач утворює окремі `U^{(l)}` у [A], чи мається на увазі фізична оцінка, внутрішня latent prediction, або авторська декомпозиція.
- **Чи виводиться:** ні. Віднімання симульованих path contributions або читання `truth.coefficients` — leakage, не оцінювання.
- **Мінімальний інтерфейс:** source-faithful receiver приймає `path_observations` лише від задокументованого estimator/source з provenance. Reconstruction приймає тільки aggregate `received_iq`; якщо для coefficient recursion потрібні per-ray operands, вони мусять бути окремо типізованими як **derived pseudo-observations**, з provenance формули й prior receiver estimates. Вони не є виміряними `U^{(l)}` з [A].
- **Перевірка:** integration test із фіксованими received samples та зміненим `ChannelTruth` має давати незмінний receiver output; AST/import/API guard блокує `ChannelTruth` і `.truth` у estimated path; synthetic aggregate model перевіряє шум/затримки без передачі path truth.
- **Вплив на BER:** критичний. Truth leakage штучно покращить BER; помилка в розділенні або неправильний aggregate model може як погіршити, так і оманливо покращити його.

### 6. `U⁰` / `U**` та candidate prediction

- **Джерело:** [A](1), с. 4, використовує `U⁰` у posterior-зважених innovations; [A](2), с. 4, використовує `U**(α)` у metric; [A](5), с. 5, задає лише I/Q перетворення для вже заданих `b, μ₁, μ₂`.
- **Точно відомо:** `iq_prediction.py` — локальне перетворення (5); `paper_recursion.py` приймає `predicted_iq` як явний масив `(M,2)` або `(L,M,2)`. Ні один модуль не будує часовий сигнал за кандидатною траєкторією.
- **Невідомо:** чи `U⁰` і `U**` є однією величиною; їхні часові індекси, умовність за `θ/α`, облік затримок/шуму, та побудова по всіх кандидатах.
- **Чи виводиться:** лише тригонометрична частина [A](5). Повне prediction правило не виводиться без `b` mapping, coefficients, затримок і сигналової дискретизації.
- **Мінімальний інтерфейс:** різні типізовані API: `predict_u0(...)` для innovation recursion і `predict_metric_candidate(...)` для `U**`; обидва приймають часові labels, coefficients/estimates та labeling profile явно. Не об'єднувати їх до доказу тотожності.
- **Перевірка:** ручні символічні приклади [A](5); delay impulse tests; незалежний побудований forward-model oracle; consistency tests між виходами й вхідними розмірностями рекурсії/метрики; окреме обґрунтування будь-якої рівності `U⁰=U**`.
- **Вплив на BER:** критичний. Кандидатні прогнози визначають innovations, likelihood/metric і branch ranking; систематичний фазовий/часовий зсув впливає на весь BER.

### 7. Path coefficients та параметри рекурсії

- **Джерело:** [A](3)–(6), с. 5, описує path I/Q складові; [A](1), с. 4, містить `α′`, `K̃`, posterior, `μ₀`; [A](9)–(10), с. 7, визначає окремий шумовий процес. [B](15) і [B](16)–(19), друк. с. 10–11 (PDF pp. 12–13), деталізують споріднену рекурсію/кумулянти для [B]. [C](4.19)–(4.22), друк. с. 116 (PDF p. 8), є окремою fading-моделлю.
- **Точно відомо:** M4.4 відтворює алгебру оновлення при явних входах; noise module реалізує тільки (9)–(10), з нульовим initial noise як позначеним проєктним вибором. Код рекурсії сам не визначає coefficient estimates.
- **Невідомо:** початкові оцінки path coefficients, `α′`, `K̃`, `μ₀`, їхні одиниці/масштаб, закон змінення coefficients, а також чи правило кумулянтів [B](16)–(19) використовується в [A].
- **Чи виводиться:** ні. Не запозичувати числа з [B]/[C] і не прирівнювати noise variance до fading coefficients.
- **Мінімальний інтерфейс:** receiver config задає source/profile, `initial_estimates`, `alpha_prime`, `k_tilde`, `mu0`; state store повертає estimates з origin/time labels. У source-faithful профілі конфігурація з невизначеними величинами не проходить readiness validation.
- **Перевірка:** ручні кроки [A](1) для скалярного/багатопроменевого прикладу; перевірка shape, posterior normalization і clock update `i→i+1`; receiver-only provenance test; окремі sensitivity runs для кожного реконструктивного параметра.
- **Вплив на BER:** критичний та потенційно time-varying; initial transient, коефіцієнтний масштаб і фільтр можуть змінити convergence і довгострокові помилки.

### 8. Часове вирівнювання: `f`, `i`, `τ_l`, sample rate

- **Джерело:** [A](2), с. 4, дає включний `f=r−η…r`, `i′[l]…i″[l]`; [A](3)–(6), с. 5, має затримки `τ_l`; [A](9)–(10), с. 7, визначає `n` як число відліків на тривалість елемента сигналу `T`.
- **Точно відомо:** M4.6 API зберігає явні `f` та `i` labels; за `η=20` це 21 `f` позиція. M3 `multipath.py` використовує цілочисельні `delay_samples`; `receiver/iq.py` має лише явно approximate rectangular ZOH, типово 8 samples/symbol.
- **Невідомо:** фізичне відображення `τ_l→samples`, початок/кінець symbols, який `i` відповідає `f`, oversampling та end padding в авторському receiver, alignment у posterior та момент прийняття рішення.
- **Чи виводиться:** ні. Не можна вивести число samples/symbol або границі кадру з самої суми (2). Одиниці M3 не є авторськими автоматично.
- **Мінімальний інтерфейс:** `Timebase(samples_per_symbol, sample_period, symbol_origin)` і явні path delays та inclusive windows; усі buffers несуть absolute sample/symbol labels. Source-faithful режим не підставляє M3 8 sps без джерельного підтвердження.
- **Перевірка:** impulse/step fixtures з відомими integer delays; перевірки включних меж і точного 21-symbol вікна; round-trip від symbol labels до sample ranges; перевірка відсутності зсуву на початку/кінці.
- **Вплив на BER:** високий. Один відлік або один символ зсуву може перекинути фазу/символ і створити систематичні помилки; фреймові краї впливають на частину символів.

### 9. `argmin` та traceback

- **Джерело:** [A](2), с. 4, записує мінімізацію `F(r)` за сумісними `θ` та обмеження `θ_{f[l]=f}`; [A], с. 6, задає `η=20`. [B](20), друк. с. 11 (PDF p. 13), підтверджує суму квадратів, але не встановлює для [A] boundary/tie conventions.
- **Точно відомо:** M4.6 дає `F` лише для однієї заданої послідовності. M2 Viterbi декодує окремий additive hard/soft branch cost по чотиристанному M1 trellis; він не мінімізує цей адаптивний path metric.
- **Невідомо:** множина допустимих θ sequence, exact survivor state, start/end constraints, tie-break, збереження/скидання історії estimator, та чи треба фіксовано-віконний delayed decision або повне кадрове рішення.
- **Чи виводиться:** постановка мінімуму є в [A](2), але виконуваний traceback не виводиться без θ-state mapping і temporal/state rules. Заміна на поточний M2 Viterbi не є наслідком формули.
- **Мінімальний інтерфейс:** окремий `decode_adaptive_frame(observations, initial_state, candidate_model, search_config) -> DecodeResult`; результат містить input bits, candidate path, delayed-decision index, metric та статус assumptions. Існуючий `decode_viterbi` лишається незмінним.
- **Перевірка:** brute-force oracle на коротких trellis кадрах; decoder має обрати мінімум із всіх допустимих кандидатів для короткого вікна; довший case перевіряє deterministic tie-break, survivor consistency, delay `η` і BER alignment.
- **Вплив на BER:** критичний. Pruning/tie/termination можуть змінити вибраний кадр. Для B необхідні тести чутливості до search width та окремі confidence intervals; не приписувати очікуваний виграш.

## План A — source-faithful, без заповнення прогалин

У цьому плані implementation gates залишаються закритими, доки відповідні факти не підтверджені повним текстом [A] або авторським уточненням. Якщо джерело не задає величину, її не підмінювати параметром [B]/[C] чи project default.

| Підетап | Залежить від | Мінімальна робота | Перевірки / критерій завершення |
|---|---|---|---|---|
| A0. Evidence gate | Немає | Оформити відповіді на SCI-02/03/04 з конкретними сторінками/рівняннями [A]: `M, θ, b`, likelihood/π/prior, path observations, coefficient states, timebase, traceback. | Кожна відповідь має цитату/сторінку або запис «не визначено — зупинка». Неперевірені [B]/[C] як підстановка заборонені. Без цього — **BLOCKED**, далі лише документаційні/ізольовані тести. |
| A1. Авторська множина `θ` і labeling adapter | A0: встановлені `M`, `θ` та `b` | Побудувати окремий immutable mapping від документованих encoder transitions до авторських candidates та `b`; не ототожнювати автоматично `hypothesis_id`. | Exhaustive golden table зі статті; `M` і всі переходи покриті; таблиця відтворює author outputs та правила меж кадру. |
| A2. Posterior model | A1 та джерельні `L`, `π`, prior | Реалізувати candidate likelihood і transition/prior adapter поверх загальної posterior-рекурсії; зберегти явний перехідний support. | Ручний крок за авторським прикладом/таблицею; normalization, zero cases; кожен `π` відповідає джерельному правилу. До конкретного posterior прикладу [A] статус лишається частковим. |
| A3. Receiver-side observations/timebase | Авторське визначення per-path `U` та таймбази | Визначити `f/i/τ_l/n`, sample boundaries і допустиме джерело `U^{(l)}` з raw received; не читати `ChannelTruth`. | Synthetic noiseless/path impulse tests із незалежним oracle; provenance test; абсолютні часові labels збігаються на всіх променях. Якщо [A] не задає шляховий спостерігач — далі **BLOCKED**. |
| A4. `U⁰`, `U**`, coefficient state | A1–A3 та авторські coefficient/initial rules | З'єднати (5) з source-defined candidate/time model; реалізувати coefficient update через наявний `paper_recursion.py`, передаючи всі підтверджені параметри явно. Не прирівнювати `U⁰` та `U**` без доказу. | Еталонні hand calculations [A](1),(3)–(6); один/кілька променів; clock `i→i+1`; no-truth test; чутливість лише як перевірка, не спосіб підігнати параметри. |
| A5. Metric candidate та traceback | A1–A4 | Використати [A](2) для candidate sequence і реалізувати argmin/traceback лише за встановлених state/boundary/tie rules. M2 Viterbi не переписувати. | Brute-force oracle на коротких кадрах підтверджує exact minimum; `η=20` — включні 21 positions; перевірки terminal/start state і tie-rule з джерела. |
| A6. Receiver boundary | A2–A5 | Додати ізольований adaptive receiver API; приймати received observations і scenario/config inputs, повертати decoded bits та diagnostics; не expose `ChannelTruth` усередині estimated path. | End-to-end synthetic vectors; повторюваність; залежність результату тільки від receiver inputs; M1–M3 regressions без змін. Назва **paper-faithful** можлива лише після закриття всіх джерельних gates. |
| A7. M5 gate | A6 | Тільки тоді виконувати BER/SER порівняння, парні seed, raw error counts та довірчі інтервали за планом M5. | Baselines та adaptive config відтворювані; no leakage; статистичний протокол зафіксований; жодне число на кшталт 1.5 dB не заявляється без незалежного доказу. |

**Стан плану A зараз:** A0 не пройдено. Реалізовані M4.1–M4.6 є ізольованими ядрами, але не підставою відкрити A1–A6. Частина A0 може виявитися принципово невизначеною у доступній статті; у такому разі source-faithful завершений receiver не можна заявити.

## План B — documented reconstruction для offline симулятора

Це окремий, непаперовий профіль. Він дозволяє закрити receiver тракт за новими ADR, ізолює всі project assumptions і не видає реконструкцію за [A]. План B є пропозицією, а не прийнятими рішеннями; перед реалізацією відповідні ADR мають бути погоджені й зафіксовані в `ASSUMPTIONS_AND_DECISIONS.md`.

| Підетап | Залежить від | Мінімальна робота | Перевірки / критерій завершення |
|---|---|---|---|
| B0. ADR та config profiles | Немає | ADR-002/006/007/008/010 прийняті 2026-10-26; ADR-003/004/005/012 прийняті 2026-10-28 лише як reconstruction choices; ADR-009/011 лишаються proposed. Окремий `reconstructed_offline` profile не змінює default M1–M3. | Config перевіряє точні прийняті choices; source-faithful profile не приймає реконструктивні defaults. Жоден accepted ADR не є доказом моделі [A]. |
| B1. Labeling та candidate adapter | B0 / ADR-002 | Як лише проєктний вибір, використати явний natural-binary `b=4c₂+2c₁+c₀` для кортежу M1 `(c₂,c₁,c₀)`; генерувати b з candidate branch, не з `hypothesis_id`. Ім'я профілю має містити `assumed`. | Golden table усіх 8 трійок; 16 branch mappings; round-trip label/index; profiles відхиляють невідомі назви. Тест не стверджує це як правило [A]. |
| B2. Received-only aggregate forward model | B1 / ADR-006,008 | Використовувати лише сумарні `received` I/Q. Створити project prediction із власних coefficient estimates/config, integer delays і явного timebase. Candidate score визначити окремо: `F_rx=Σ_{n,j}(Y_{j,n}−Σ_l Ũ_{j,n}^{(l)}(candidate))²` на configured window. Це **не** [A](2): там path-indexed observations; не подавати aggregate `Y` як кожне `U^{(l)}` і не переназивати цей metric `paper_metric`. | `ChannelTruth` mutation/inaccessibility test; noiseless delayed-path oracle; один і кілька променів; metric/profile явно позначені `project_reconstruction`. |
| B3. Явні coefficient updates | B2 / accepted ADR-007; окреме рішення ADR-011 потрібне для pseudo-path operands | Явно конфігурувати `α′`, `K̃`, `μ₀`, початкові fluctuating/full I/Q оцінки та початковий абсолютний `time_index`; не читати `ChannelTruth`. ADR-007 не задає псевдоспостережень. Для B3b потрібне окреме рішення про допустимий per-path operand із aggregate `Y`; запропоновані ADR-011 simultaneous cancellation pseudo-observations `Ỹ_l[n]=Y[n]−Σ_{q≠l} Ũ_q[n]` лишаються proposed і не реалізуються в B3a. Noise profile та всі значення мають явне provenance; не підміняти [A](9)–(10) нормалізацією [C] і не переносити [B](16)–(19) чи [C](4.19)–(4.22) без окремого рішення. | B3a: перевірити state initialization/shape/finite/time isolation і конфігураційну вимогу початкового індексу. B3b лише після визначення per-path inputs, posterior rows і noise handling; no-truth test та sensitivity до явних параметрів. |
| B4. Reconstruction posterior | B2–B3 / ADR-003,004,005 | Проєктна стартова умова: M2 `INITIAL_STATE=(0,0)`; prior рівномірний лише над 4 M4.1 гіпотезами з `current_state==(0,0)`, решта нульові. Проєктні transition probabilities: рівномірно по дозволених outgoing edges кожного рядка. Зробити likelihood `L_h=exp(−βF_rx,h)` з явним `β>0`, реалізувати log-space, не використовувати [B](7) як її обґрунтування. | Перевірити support/row sums, ручний posterior для 16 гіпотез із нульовими prior cells, extremes `β→small/large` без переповнення; окремі ADR sensitivity profiles. Ці формули мають мітку reconstruction. |
| B5. Candidate prediction & state lifecycle | B1–B4 / ADR-006…008 | Розділити receiver-side `U⁰` (innovation prediction) та `U**` (candidate/window prediction) типами й функціями; визначити для кожного path delays та межі. Застосовувати [A](5) тільки як локальний фазово-I/Q transform після assumed labeling. | Hand samples з b=0..7; затримка на імпульсі; clock continuity; lifecycle reset/frames; prediction tests відтворювані і не читають truth. |
| B6. Окремий adaptive traceback | B1–B5 / ADR-009 | Не модифікувати `decoding/viterbi.py`. Запропонований reconstruction: окремий fixed-lag beam search з вікном `η=20`, параметром `beam_width` у config, історією posterior/coefficient estimates у кожному survivor; deterministic tie-break за лексикографічним sequence of hypothesis IDs. `paper_metric.py` лишається exact scalar source kernel і не використовується для aggregate reconstruction metric. | Короткі кадри: вичерпний перебір є oracle для beam search при достатній ширині; tie/initial/final states; `η=20` delay; width sensitivity curve; determinism. Report містить `beam_width` і assumption profile. |
| B7. Integration та M5 gate | B2–B6 | Зібрати новий receiver entrypoint; M1–M3 baseline лишаються доступні окремо. Виконати paired-seed BER/SER порівняння, raw counts, intervals і sensitivity до всіх ADR параметрів. | Повторюваний run; no-truth isolation; regression tests; report чітко розрізняє M2 baseline, `reconstructed_offline` і точні ізольовані M4 algebra kernels. M5 готовий лише з опублікованими assumptions, sensitivity та статистично коректними інтервалами. |

### Проєктні рішення/пропозиції для плану B

| ADR | Тема | Обране рішення або неузгоджена пропозиція | Перевірка / межа твердження | Статус на 2026-10-26 |
|---|---|---|---|
| ADR-002 | 8PSK labeling та `θ→branch` | Прийнято `assumed_natural_binary`: `b=4*c2+2*c1+c0` для `(c2,c1,c0)`; не встановлює `hypothesis_id↔θ`. | Exhaustive table; не приписувати [A]. | accepted — user decision |
| ADR-003 | Transition model | `T[h,k]=1/d(h)` для структурно дозволених наступних edges, 0 для решти; `d(h)` обчислюється з фактичної 16×16 маски. | Manual structural mask, order, support, row sums, nonuniform rejection. Не [B](7) matrix і не mapping author `θ`. | accepted — user decision 2026-10-28 |
| ADR-004 | Initial state/prior | State `(0,0)`; prior `1/4` лише для гіпотез із `current_state=(0,0)`. Перше observation оновлює цей first-edge prior без transition. | Four active cells; first/second observation hand oracle; no off-by-one. Не авторський prior для `θ`. | accepted — user decision 2026-10-28 |
| ADR-005 | Likelihood | Project pseudo-likelihood proportional to `exp(−βF_rx,h)`, with explicit `β>0`; `F_rx` is aggregate reconstruction metric, not `paper_metric.py`. | Zero/equal metrics, beta sensitivity, large-value common shift and manual posterior; not a proved statistical model. | accepted — user decision 2026-10-28 |
| ADR-006 | Aggregate observation model | Приймається тільки aggregate received I/Q із receiver-side project prediction; не `ChannelTruth`, не окремі path measurements. | Test змін truth із незмінними receiver inputs; aggregate synthetic oracle. Метрика відрізняється від [A](2). | accepted — user decision |
| ADR-007 | Coefficients/initial estimates | `α′`, `K̃`, `μ₀`, початкові fluctuating/full I/Q оцінки кожного променя та початковий `time_index` обов'язково задаються явно. [A] не дає числових значень; автоматичне перенесення з [B]/[C] заборонене. Config/results мають фіксувати значення, provenance і часові правила; receiver не читає `ChannelTruth`. | Config completeness, shape/finite/time validation, hand update на переданих operands, no-truth test та sensitivity. Це accepted reconstruction choice, не джерельне підтвердження. | accepted — user decision 2026-10-26 |
| ADR-008 | Timebase/edge policy | Прийнято `approximate_rectangular_8sps`, explicit integer sample delays, frame boundaries і `zero_padding`. | Impulse/delay/window tests; project convention, не source-faithful timebase. | accepted — user decision |
| ADR-009 | Search/traceback | Separate fixed-lag beam search, `η=20`, явний width, deterministic lexicographic tie-break. | Brute-force oracle short frames; BER/survivor sensitivity до ширини. Не змінювати M2 Viterbi. | proposed |
| ADR-010 | Метрики та claims | Прийнято result/profile name `reconstructed_offline`, `paper_exact=false`, без непідтверджених claims. | Metadata assertion та paired-seed report audit; performance claims лише з незалежним обґрунтуванням. | accepted — user decision |
| ADR-011 | Pseudo-path operands для coefficient recursion | Одночасне cancellation-derived pseudo-observation з aggregate sample і попередніх оцінок; не фізичне per-path measurement. | One/two-path hand oracles, error/noise accounting, no-truth test. Source operands не paper-verified. | proposed |
| ADR-012 | L=1 real-channel observed-IQ bridge | `reconstructed_offline`; real-channel experiment; zero delay; rectangular ZOH 8 samples/symbol; map each sample `(-Im,Re)` and mean exactly eight; update after symbol completion; next state usable only for next symbol or later. | Absolute sample labels, explicit pre-state/symbol clocks and cutoffs; all-phase manual oracle; no truth; no hidden noise variance. Reconstruction convention, not [A] observation algorithm. | accepted — user decision 2026-10-28 |
| ADR-012 | L=1 real-channel observed-IQ bridge | `reconstructed_offline`; real-channel experiment; zero delay; rectangular ZOH 8 samples/symbol; map each sample `(-Im,Re)` and mean exactly eight; update after symbol completion; next state usable only for next symbol or later. | Absolute sample labels, explicit pre-state/symbol clocks and cutoffs; all-phase manual oracle; no truth; no hidden noise variance. Reconstruction convention, not [A] observation algorithm. | accepted — user decision 2026-10-28 |

## Критерії готовності до M5

**Source-faithful M5:** усі source-faithful gates A0–A6 закриті; відсутні реконструктивні assumptions у receiver; є незалежні формульні oracle tests, no-truth evidence та відтворюваний adaptive decode. За поточним станом це **BLOCKED**.

**Reconstruction M5:** ADR-002…011 прийняті; окремий profile і result metadata показують усі параметри; estimated receiver не читає `ChannelTruth`; aggregate metric/prediction, posterior і traceback мають ручні/synthetic oracles; search-width і параметрична sensitivity показані; M1–M3 regression лишається стабільним; paired-seed BER/SER та intervals мають raw counts. Це дозволяє M5 як **documented project reconstruction**, не як exact reproduction статті.

## M4.7b — межа `ChannelTruth` та тестового запуску

Архітектурний тест у `tests/test_channel_truth_boundary.py` охоплює такі production-модулі:

- усі Python-файли в `src/hf_tcm/receiver/`: поточні `__init__.py`, `iq.py`, `iq_prediction.py`, `paper_recursion.py` та нові receiver modules у цій директорії;
- усі Python-файли в `src/hf_tcm/decoding/`: поточні `__init__.py`, `branch_metrics.py`, `paper_metric.py`, `viterbi.py` та майбутній окремий adaptive decoder;
- `src/hf_tcm/coding/hypotheses.py`, `posterior.py`, `likelihood.py`, які формують M4 candidate/posterior boundary.

Нові estimated/decision modules мають розміщуватись у `receiver/` або `decoding/`, щоб автоматично потрапляти під guard. Якщо inference module з'явиться в іншому production package, його треба явно додати до `PROTECTED_CODING_MODULES`/тестового переліку до інтеграції.

Поза забороненою межею залишаються `channels/` (генератор і truth), `simulation/` та oracle/control code, `analysis/`/evaluation і `tests/fixtures` та інші тести. Їм дозволено використовувати `ChannelTruth` для генерації та перевірки. Позитивний тест читає симуляторний і oracle test source та підтверджує, що guard їх не блокує.

AST guard забороняє в protected modules: імпорт/посилання `ChannelTruth` (включно з alias через module attribute), читання `.truth`, імпорт/виклик відомих channel generators (`apply_multipath`, `generate_rician_coefficients`, `generate_fluctuating_noise`), а також прямий доступ NumPy Generator state через `.bit_generator.state` і legacy `.get_state()`/`.getstate()`. Негативний тест подає синтетичний receiver source з усіма цими порушеннями та перевіряє, що кожен клас виявлено.

**Обмеження:** це статичний AST guard і regression boundary, а не абсолютний захист від витоків. Він не доводить походження довільного `ndarray`, не бачить runtime/reflection (`eval`, `getattr`), перейменовані/серіалізовані дані, native extensions або значення, передані через невідомий wrapper. Для інтегрованого receiver надалі потрібні також API design без truth-полів, provenance/immutability tests та перевірка всього dataflow.

Тестовий запуск використовує `--basetemp .pytest-m4-7b-temp` усередині workspace. Каталог внесено до `.gitignore`; він є лише pytest scratch space, сторонні файли не видаляються. Команду й фактичний результат цього етапу записано в `docs/BUILD_VERIFICATION.md`.

## M4.7c/B0 — configuration-only profile

Додано окрему strict schema/validation для `reconstructed_offline`, описану в `docs/RECONSTRUCTED_OFFLINE_CONFIG.md`. Конфігурація мусить явно задавати labeling/origin, перехідну матрицю, початкові state/prior, likelihood type/β, `α′`, `K̃`, `μ₀`, initial estimates, timebase/rates/delays, aggregate observation model, search width/decision lag і provenance кожного припущення. Validation не задає значень за замовчуванням. `paper_exact` і `receiver_enabled` фіксовані як `false`; schema не запускається через CLI/pipeline.

За явними рішеннями користувача прийняті як проєктні припущення ADR-002, ADR-006, ADR-007, ADR-008 і ADR-010 (2026-10-26), а ADR-012 — лише для вузького L=1 causal observed-IQ bridge (2026-10-28). ADR-003, ADR-004, ADR-005, ADR-009 та ADR-011 лишаються **proposed**. Валідація конфігурації перевіряє повноту/типи/структурні обмеження, але сама не приймає жодного ADR.

### Checklist рішень ADR

- [x] **ADR-002:** прийнято лише reconstruction mapping `assumed_natural_binary`, `b=4*c2+2*c1+c0`; це не доказ `θ→branch/b` у [A].
- [x] **ADR-003:** uniform mass over each row's structurally allowed edges.
- [x] **ADR-004:** initial state `(0,0)` and first-edge prior support.
- [x] **ADR-005:** explicit-beta aggregate pseudo-likelihood.
- [x] **ADR-006:** тільки aggregate received I/Q; estimated receiver не читає `ChannelTruth`/`.truth`/generator state.
- [x] **ADR-007:** явні `α′`, `K̃`, `μ₀`, початкові оцінки та час; source values не домислюються, provenance обов'язкове.
- [x] **ADR-008:** `approximate_rectangular_8sps`, integer sample delays, явні frame boundaries, `zero_padding`.
- [ ] **ADR-009:** traceback/search method, width, lag, ties і terminal rules.
- [x] **ADR-010:** `reconstructed_offline`, `paper_exact=false`, без непідтверджених claims.
- [ ] **ADR-011:** чи потрібні derived pseudo-path operands, точне правило та модель похибки.
- [x] **ADR-012:** вузький causal L=1 real-channel aggregate-to-observation rule, прийнятий рішенням користувача 2026-10-28; див. контракт нижче.

Базові ADR-002/006/007/008/010 прийнято 2026-10-26; ADR-003/004/005/012 — окремим рішенням 2026-10-28 у визначеному обсязі. Усі вони є project assumptions, не підтвердженням авторської моделі [A]. ADR-009/011 лишаються proposed. `beta` є обов'язковим runtime parameter, не значенням за замовчуванням.

## M4.7d/B1 — ізольований reconstruction labeling adapter

Додано `receiver/reconstruction_labeling.py` як чистий adapter без викликів із CLI, конфігураційного loader або pipeline. Він вимагає явні `profile="assumed_natural_binary"` і `bit_order=("c2", "c1", "c0")`. Для кожного output triple результат дорівнює M1 mapping `label_to_index((c2,c1,c0), profile="baseline_assumption")`, тотожному цілочисельному запису `b=4*c2+2*c1+c0`. Реалізація повторно використовує таблицю M1, не копіює arithmetic mapping. `hypothesis_to_phase_index` читає лише `Hypothesis.output_bits`; `hypothesis_id` не бере участі.

**Наукова межа:** `assumed_natural_binary` — прийняте проєктне припущення ADR-002, а не підтверджене [A] labeling. Перевірка локальних 16 M4.1 branches доводить лише узгодженість adapter-а з виходами M1; вона не доводить відповідність цих гіпотез авторському `theta` чи авторському числу кандидатів. SCI-02 лишається OPEN щодо [A]. ADR-003/004/005/009/011 лишаються **proposed**; ADR-007 accepted лише для явних reconstruction parameters і не усуває source-faithful прогалин. Adapter не змінює `paper_exact: false` / `receiver_enabled: false`, не активує B0 конфігурацію та не додає posterior, likelihood, prediction чи adaptive decoding.

Схема B0 допускає це явне ім'я та явні `bit_order`/`output_to_b` значення; конфігураційний формат не потребує послаблення і не приймає ADR. Запис значень у config не підключає цей adapter до receiver.

Тести покривають усі 8 triples і 16 hypotheses, golden table, тотожність із M1 baseline, сумісність фаз `b=0…7` з ізольованим `iq_prediction.py`, відсутність залежності від порядку enumeration/`hypothesis_id`, а також строгі profile, bit-order і bit validation. Модуль розміщений у `receiver/`, тому входить до AST ChannelTruth guard; його алгоритм не імпортує та не читає `ChannelTruth`.

## M4.7e/B2a — aggregate-I/Q prediction sum та project residual metric

Додано незалежний `receiver/reconstruction_aggregate.py`. `sum_estimated_path_predictions` приймає тільки явний масив `(L,N,2)` із вже вирівняними estimated path predictions і повертає `(N,2)` після стійкого сумування за `L`. `compute_project_reconstruction_metric` приймає явно передані aggregate received/predicted масиви однакової непорожньої форми `(N,2)` та повертає `Σ(received−predicted)²`. Обидві функції перевіряють форми, скінченність і числовий діапазон; входи не змінюються. Жодного broadcasting немає.

Критерій називається **`project_reconstruction_metric`**, оскільки його aggregate operands не збігаються з path-indexed operands [A](2). Він не викликає `paper_metric.py`, не додає нормування/ваг і не є `paper_exact_metric`. Path arrays є лише receiver-side estimated candidate predictions; модуль не сприймає їх як окремо виміряні шляхи й не приймає simulated contributions/`ChannelTruth`.

Це лише арифметика для вже вирівняних входів, не повний forward model. Немає часової моделі, delays/alignment, `b` generation, coefficient estimates, likelihood, posterior, pseudo-observations, пошуку чи інтеграції. Схема лишається `paper_exact: false`, `receiver_enabled: false`; ADR-002/006/007/008/010 прийняті тільки як проєктні рішення, ADR-003/004/005/009/011 лишаються **proposed**.

## M4.7g/B2b-2 — project reconstruction forward prediction

Додано `receiver/reconstruction_forward.py::predict_reconstructed_aggregate_iq` як чисту функцію без config loader, CLI чи pipeline integration. Вона приймає candidate `output_bits` у порядку `(c2,c1,c0)`, explicit receiver-side estimated path coefficients `(L,2)` у порядку `(μ₁,μ₂)`, integer `path_delays_samples`, `symbol_origin_sample`, output frame start/count та явні `labeling_profile`, `bit_order`, `timebase_profile`, `symbol_to_sample_rule` і `edge_policy`.

API підтримує тільки coefficients, сталі для кожного шляху в межах усього переданого кадру; sample-indexed/per-symbol coefficients не підтримуються. Кожен symbol у named profile `approximate_rectangular_8sps` займає рівно вісім послідовних sample labels за явним rule `rectangular_zero_order_hold_8_samples_per_symbol`. Початок першого symbol — `symbol_origin_sample`; delay і frame clipping делегуються B2b-1 alignment kernel-у з `zero_padding`; результатом є aggregate `(N,2)`, складений B2a aggregator-ом.

Повторно використані `reconstruction_labeling.py`, `iq_prediction.py`, `reconstruction_alignment.py` і `reconstruction_aggregate.py`; формули та індексація цих ядер не скопійовані. Це **PROJECT RECONSTRUCTION forward model** для baseband I/Q. [A](5) local transform не є повним passband waveform [A](3)–(6), і результат не ототожнюється з `U⁰` чи `U**`. Відсутні фазовий offset (π/4 — лише крок), coefficient estimation, ChannelTruth, likelihood/posterior, pseudo-observations і decoder.

B0 schema не змінювалася: вона вже містить назву timebase, explicit `samples_per_symbol`, symbol origin і integer path delays; новий forward API вимагає точні named profile/rule та frame values як аргументи, не підставляючи їх з прихованого default. `receiver_enabled:false`, `paper_exact:false` і source-faithful rejection збережені. Інтеграційні тести перевіряють `b=0…7`, один/два шляхи, delays/edges, aggregate metric, coefficient/path permutation invariance, input immutability та no-truth API boundary.

**Статус B2b-2:** ізольований forward prediction — **READY — IMPLEMENTED**. Це не повний receiver і не закриття B3/B4. ADR-007 прийнятий для явних reconstruction parameters; B3b усе ще блокується невизначеними per-path operands і рішенням ADR-011. B4 блокується переходами/prior/likelihood (ADR-003/004/005) та search/traceback (ADR-009). П'ять прийнятих ADR є project assumptions, не доказ моделі [A].

## M4.7h/B3a — затвердження ADR-007 і стан оцінювача

ADR-007 прийнято окремим явним рішенням користувача від 2026-10-26 для реконструкції. B3a додає лише контейнер snapshot-стану з двома явними `(L,2)` масивами оцінок та абсолютним `time_index`, плюс явний `estimator.initial_time_index` у неактивній конфігурації. `fluctuating_iq` — це `\(\widetilde{\mu}^{*}\)`, `full_iq` — `\(\mu^{*}\)`, а регулярна `\(\mu_0\)` є окремим параметром. Переходи між індексами задає лише caller як `i → i+1`; контейнер сам не оновлює коефіцієнти.

Контракт і межі описано в `docs/M4_B3_ESTIMATOR_STATE_CONTRACT.md`. B3a не вирішує ADR-011: повний B3b не має визначеного per-path observation operand із наявної aggregate observation boundary, доки не прийняте окреме рішення й не визначено його часову та noise-конвенцію. `receiver_enabled:false`, `paper_exact:false`, source-faithful guard і відсутність CLI/pipeline dispatch зберігаються.

## M4.7i/B3b-0 — isolated explicit-operand state step

`receiver/reconstruction_estimator_step.py::advance_reconstruction_estimator_state()` приймає лише `L=1`, state `(1,2)`, per-beam `k_tilde`/`mu0` `(1,2)`, явні `observed_iq (2,)`, `predicted_iq (M,2)`, `posterior (M,)`, alpha та обидва індекси `i`, `i+1`. Він перевіряє узгодження clock, додає batch axes і делегує арифметику `update_quadrature_estimates()`; повертає новий immutable state із `\(\widetilde{\mu}^{*}_{i+1}\)` та `\(\mu^{*}_{i+1}\)`. Ручні тести перевіряють [A](1), включно з двома послідовними кроками. `observed_iq` не отримується з channel output.

Це **explicit-operand reconstruction state-step adapter, NOT paper-exact estimator**. Adapter не формує posterior, likelihood, candidate mapping, predictions чи pseudo-path observations, не змінює B2b-2 кадрові коефіцієнти й не підключається до CLI/pipeline. Повний B3b лишається заблокованим operand/noise/time provenance і inference рішеннями. SCI-METRIC-02 щодо [A](2) у в7 залишається відкритим; `paper_metric.py` не змінено.

## M4.7j/B3c-0 — explicit-operand sequential reconstruction estimator

`receiver/reconstruction_estimator_sequence.py::run_reconstruction_estimator_sequence()` приймає явний immutable initial state та послідовність `ReconstructionEstimatorStepOperands` для `L=1`. Кожен step зберігає caller-provided `time_index`, `next_time_index`, `alpha_prime`, `k_tilde`, `mu0`, `observed_iq`, `predicted_iq`, `posterior`; runner не має числових defaults і кожен step передає незміненому `advance_reconstruction_estimator_state()`.

Безперервність перевіряється state-step contract: `time_index` дорівнює поточному state, `next_time_index=time_index+1`. Пропущені, повторені або переставлені labels відхиляються. За `include_history=True` результат містить immutable tuple з початкового та всіх наступних snapshots із відповідними абсолютними `time_index`; інакше зберігається тільки фінальний state. Для порожньої послідовності повертається initial state. Повторний запуск починається з переданого state і не ділить проміжні snapshot states.

Кожен step читає попередній `fluctuating_iq`, ніколи попередній `full_iq`; вихід `full_iq` дорівнює новій флуктуючій оцінці плюс `mu0` цього кроку. Тому `mu0` може змінюватися між кроками відповідно до наданих operands. Ручні тести незалежно обчислюють [A](1) для двох і трьох кроків, включно з нульовими innovations та змінними posterior, `alpha_prime`, `k_tilde` і `mu0`.

Це **explicit-operand sequential reconstruction estimator, NOT complete paper-exact estimator**. `observed_iq`, predictions і posterior залишаються тестовими explicit operands; runner не отримує aggregate observation, не будує inference data та не підключений до forward model, CLI, pipeline чи decoder. SCI-METRIC-02 залишається відкритим; `paper_metric.py` і статуси ADR не змінювалися. `paper_exact:false`, `receiver_enabled:false`.

## M4.7k/B3c-1 — L=1 aggregate / estimator / forward contract

Створено `docs/M4_B3_SINGLE_PATH_INTEGRATION_CONTRACT.md`. Висновок за [A](3)–(6) і M3 API: aggregate real passband `Y(t_i)` у [A](4) не ототожнюється автоматично з complex baseband `ChannelOutput.received` чи його real/imaginary частинами. `split_iq()` не реалізує потрібну quadrature demodulation, scaling, windowing або noise transform. Тому L=1 `observed_iq` adapter наразі **BLOCKED** на окремий receiver-side transform, абсолютні sample/symbol/estimator clocks, update cadence та noise/covariance normalization. Запропоновано draft ADR-012, не прийнятий; ADR-011 для multipath лишається proposed.

Додано `receiver/reconstruction_forward_snapshot.py::snapshot_full_iq_for_forward()`: для state `(1,2)` створює immutable copy саме з `full_iq`, tagged явним `estimator_time_index`, який має збігатися з immutable state timestamp. Це **READY як value/timestamp adapter**, але не містить sample/symbol/frame mapping. Forward prediction далі тримає coefficient pair незмінною протягом caller-supplied frame; snapshot не підключений до forward API, pipeline чи CLI.

Estimator `time_index`, sample index і symbol index залишаються різними шкалами; не встановлено, чи рекурсійний tick sample-level або symbol-level. Causal use вимагає, щоб observations, posterior та snapshot були доступні до prediction cutoff; майбутні дані в past prediction/state дозволені лише після окремої специфікації smoothing regime. `reconstructed_offline` цього дозволу не надає. ADR-статуси 001/002/006/007/008/010 accepted, 003/004/005/009/011 proposed, ADR-012 proposed draft; `paper_exact:false`, `receiver_enabled:false`. SCI-METRIC-02 і `paper_metric.py` без змін.

## M4.7l/B3c-2 — controlled M3 baseband / [A](5) compatibility

Нова `tests/test_m3_baseband_reconstruction_compatibility.py` використовує one-path static M3 channel, zero delay/no AWGN, всі `b=0…7` та дві явні ненульові пари `(mu1,mu2)`. Тест не читає `ChannelOutput.truth`: контрольний статичний `h` відновлюється окремо з заданих channel controls лише для математичного oracle. Для M3 `z=h·exp(jbπ/4)`, а формула [A](5) дає `(-mu1 sin(bπ/4), mu2 cos(bπ/4))`. Це не raw `(Re z, Im z)`. З явним test-only `h`, фіксована дійсна конверсія — `(-mu1 Im(z/h), mu2 Re(z/h))`; forward API збігається з [A](5) і повторює кожну пару 8 разів/символ. Це establishes synthetic algebraic compatibility, **not** a production observed-IQ bridge.

В актуальній робочій копії окремий DOCX v7 відсутній; формули перевірені за доступним unversioned `source_paper_2026.docx`/сканом сторінки 5, тож version-specific підтвердження v7 лишається обмеженим. L=1 bridge і causal integration заблоковані receiver-side `ĥ`/demodulation, observation/noise normalization, sample-symbol-estimator clock mapping, cutoff та frame-to-snapshot rule. ADR-012 і ADR-011 proposed; жодний ADR не прийнятий у цьому підетапі.

### M4.7m/B3c-3 — special noiseless real-channel check

Нові контрольні тести використовують M3 constellation/baseband/IQ helpers із явними sample arrays `received=a·exp(jbπ/4)`, `a=0.75,2.0`, без ChannelTruth. За `mu1=mu2=a`, simple `(-Im,Re)` координатна ротація збігається з [A](5) і forward API для всіх восьми фаз. Для двох комплексних контрольних `h` вона не збігається; це не general fading bridge. Додано вузьке формулювання ADR-012 і запропоновану symbol-block cadence, обидва не прийняті. Який із восьми відліків/який reducer утворює recursion operand та noise covariance лишаються відкритими.

### M4.7n/B3c-4 — accepted ADR-012 та causal one-path explicit-posterior step

Рішення користувача від 2026-10-28 приймає тільки ADR-012: у `reconstructed_offline`, `L=1`, real-channel experiment, zero delay та rectangular ZOH 8 samples/symbol визначено `(-Im(received[n]),Re(received[n]))` і arithmetic mean рівно восьми sample positions на symbol. Це реконструктивне припущення, не observation algorithm підтверджений [A]. Одне оновлення виконується після sample `O+8f+7`; snapshot доступний лише для `f+1` чи пізнішого.

Додано `receiver/reconstruction_observation.py` для явної перевірки профілю, labels, повноти вікна і скінченності вибраних samples. `receiver/reconstruction_causal_step.py` явно отримує обидва часові labels, cutoff sample для posterior/prediction, `posterior`, `predicted_iq`, `alpha_prime`, `k_tilde`, `mu0`; cutoff-и не можуть бути пізніше останнього sample поточного symbol. Adapter делегує state update чинному explicit step і повертає immutable next state та snapshot лише з `full_iq`. Clocks не конвертуються неявно: наступний виклик caller має спарити `i+1` із `f+1`. Код не читає ChannelTruth, не створює posterior/predictions і не інтегрується з forward, pipeline, CLI чи decoder. `reconstruction_forward.py` лишає coefficients сталими протягом кадру.

Config validator/docs зберігають ADR-012 observation profile без активації (`receiver_enabled:false`, `paper_exact:false`). Усереднення не оголошене independent AWGN; covariance лишається відкритою. Результат: **causal one-path explicit-posterior reconstruction step, NOT complete paper-exact receiver**. На M4.7o ADR-003/004/005 тепер прийняті як reconstruction policy, але B4b integrated posterior link лишається окремим етапом через невизначеність candidate metric/posterior clock pairing. ADR-009 і ADR-011 proposed.

## M4.7f/B2b-1 — ізольований sample-index alignment operator

Додано `receiver/reconstruction_alignment.py::align_estimated_path_predictions`. Вхід — variable-length segments per ray `(N_l,2)`, їхні явні nonnegative absolute `segment_start_indices`, nonnegative integer `delays_samples`, `frame_start_sample`, positive `frame_sample_count` та обов'язковий `edge_policy="zero_padding"`. Вихід має форму `(L,N,2)`, де рядок `n` відповідає sample label `frame_start_sample+n`.

Проєктна індексна конвенція: рядок `k` входу променя `l` належить sample label `segment_start_indices[l]+k`; delay зсуває його до `segment_start_indices[l]+k+delays_samples[l]`. Копіюються лише точки в напіввідкритий вихідний інтервал `[frame_start_sample, frame_start_sample+frame_sample_count)`. Незаповнені вихідні комірки нульові; shifted input поза кадром обрізається. Входи не мутуються, різні `N_l` дозволені.

Це project-reconstruction operator, сумісний із integer-sample shift конвенцією M3 `apply_multipath`; це не доведена часова модель [A]. `samples_per_symbol`, фізичне `τ_l→samples`, sample rate, phase/bit conventions не задаються та не виводяться. `ChannelTruth` і симульовані path contributions не читаються. Результат має форму, сумісну з B2a `sum_estimated_path_predictions`.

На етапі M4.7f B0 має `path_delays_samples`, але не має edge policy, frame start/count чи provenance aligned candidate predictions. Тоді ADR-003/004/005 ще були proposed і повна інтеграція блокувалася posterior policy, ADR-011 та decoder. Поточний статус policy зафіксовано у M4.7o нижче; forward frame/pipeline integration усе ще не реалізована. `paper_exact: false`, `receiver_enabled: false` і source-faithful не змінені.

## M4.7o/B4a — isolated reconstruction posterior adapter

За явним рішенням користувача від 2026-10-28 прийнято тільки ADR-003/004/005 із policy, наведеними в таблиці ADR вище. `receiver/reconstruction_posterior.py` перевіряє канонічний порядок `HYPOTHESES`, будує probability matrix із фактичної structural mask та рахує `1/d(h)` із кожного рядка. Поточний trellis дає degree чотири, але це значення не зашите. Функція початкового prior використовує саме `current_state=(0,0)`.

Likelihood adapter приймає повний `(16,)` aggregate reconstruction metric і explicit `beta>0`; shared log-shift зберігає normalized posterior. Перша emission застосовується до початкового first-edge prior без переходу. Далі adapter викликає незмінену `coding.posterior.posterior_update()` для переходу попереднього edge posterior і emission наступного edge. Ручний двокроковий тест фіксує цю cadence, permutation-consistency та нульові cells.

`F_rx` не є `[A](2)`/`paper_metric.py`; це project pseudo-likelihood, не підтверджена статистична модель. Adapter не генерує candidate metrics/predictions і не інтегрується до `reconstruction_causal_step.py`, CLI, pipeline чи decoder. SCI-02, SCI-03 і SCI-METRIC-02 залишаються відкритими. Статус: **isolated reconstruction posterior adapter, NOT author-exact posterior, NOT integrated adaptive receiver**.

**B4b integration gate: BLOCKED** до окремого контракту для зіставлення кожного per-symbol metric vector з canonical candidate/output order, estimator/symbol clock, першим edge та causal cutoff. ADR-009 search/traceback і ADR-011 multipath operands лишаються proposed; `paper_exact:false`, `receiver_enabled:false`.

## M4.7q/B4c ? explicit single-symbol posterior-estimator composition

The isolated API in `receiver/reconstruction_posterior_estimator_step.py` composes the implemented B4b candidate metric result, B4a posterior functions, existing [A](5) IQ kernel, ADR-012 causal one-path step and immutable forward snapshot. Its complete inputs include one explicit prior mode, beta, estimator parameters, state/time labels, absolute sample labels, profile conventions and exact sample cutoffs. It accepts no current posterior operand; it derives that posterior from the current symbol metric and either the B4a initial prior (without transition) or previous posterior (transition then emission).

Canonical hypothesis ordering is verified across metric IDs, M1 output bits, assumed phase labels, B4a posterior and recursion predictions. The `(16,2)` recursion predictions from pre-observation `full_iq` are checked against the B4b `(16,8,2)` ZOH predictions. The existing causal step extracts the mean of eight selected ADR-012 I/Q samples and delegates the sole state transition to `reconstruction_estimator_step.py`.

Clock labels are never inferred: caller supplies symbol `f`, estimator time `i`, origin `O`, prediction cutoff `O+8f-1` and posterior/observation cutoff `O+8f+7`. The next estimator state at `i+1` is marked usable from `f+1`. Integration gate for this one-symbol adapter is READY within the accepted reconstructed profile; sequence automation and B5/B6 are not included. Result naming: **isolated causal single-path reconstruction posterior-estimator step, NOT paper-exact receiver, NOT decoded-bit output**. ADR-009/011 remain proposed; `paper_exact:false`, `receiver_enabled:false`, SCI-METRIC-02 open.

## M4.7r/B4d ? causal sequence scheduler and continuation

Implemented `run_reconstruction_posterior_estimator_sequence()` as a thin ordered caller of the B4c step. Its required schedule contains explicit absolute consecutive `symbol_indices`, first symbol, count, sample origin `O`, contiguous absolute sample labels, initial state and estimator time. The accepted B4c sample mapping `O+8f` is used directly. The buffer is exactly `8N` complex samples starting at `O+8f0`; at step `k`, only the prefix ending at that symbol is passed onward. No future symbol data reaches that B4c invocation.

`new_independent_sequence` requires its sequence origin to equal the first requested symbol and an ADR-004 prior. Its first update has no transition. `continuation` requires the posterior after the immediately preceding symbol, the next estimator state, and predecessor symbol/time indices; the first step performs one transition and then the current emission. Duplicate, skipped, mismatched sample/symbol, and estimator-time schedules are rejected. A caller-supplied initial pair establishes `i0` separately from `f0`; both tick once per symbol thereafter.

`alpha_prime` and `k_tilde/mu0` can be explicit constants or full length-N schedules; beta and all profile settings remain explicit. The runner returns final state/posterior/labels and optional immutable per-symbol history. It has no frame reset behavior; frames can only be reporting partitions over a continuous run. Split-run continuation is supported with the successor buffer and prior outputs. This does not establish a frame-constant forward-model schedule, a decoder, or a paper-exact estimator.

Status: **isolated causal single-path reconstruction posterior-estimator sequence runner, NOT paper-exact receiver, NOT decoded-bit output**. The explicit contiguous-buffer sequence-runner gate is READY for this narrow profile. B5 is not complete: frame/edge scheduling, delays/boundaries, and the separate `U0`/`U**` prediction lifecycle remain to be specified; no frame-constant forward-model equivalence is claimed. B6 remains blocked on ADR-009 fixed-lag search, width/tie-break, survivor state, termination and traceback. B7/M5 remain blocked on paired-seed BER/SER counts, intervals and sensitivity study. ADR-009/011 proposed, `paper_exact:false`, `receiver_enabled:false`, SCI-METRIC-02 open.

## M4.7s/B5a — path contract, no decoder

`coding.hypothesis_path.validate_hypothesis_edge_path()` is a structural validator for an explicitly supplied path. It validates the initial state, canonical integer hypothesis IDs, first-edge source state and pairwise `previous.next_state == following.current_state`; it returns matching `HYPOTHESES` records in input order. It has no metric input, search, survivor selection, final-state rule, traceback or decoded-bit API.

Contract verification confirms all 16 `HYPOTHESES` rows equal `build_trellis()` and `encode_step()` outputs. Structural support equals `ALLOWED_HYPOTHESIS_TRANSITIONS`, while ADR-003 transition probabilities remain separately row-normalized. Candidate order is the immutable B4b/B4a row order; phase remains derived from each edge's output bits.

B4b's `(F,16)` `F_rx` is the local cost matrix for the **accepted conditional policy** only after the causal B4d matrix is frozen for a separate path pass. Such costs depend on estimator history. Viterbi dynamic programming is exact for the resulting frozen additive conditional objective, but not a joint optimum over unknown channel histories. B4a posterior is not a branch cost and [A](2) is a different open paper metric. The earlier B5a proposal is superseded by the user acceptance of ADR-013 in M4.7t.

`M4.7t/B5b` implements this separate path pass in `decoding/reconstruction_viterbi.py::decode_reconstruction_viterbi()`. Its required inputs are frozen finite nonnegative `candidate_metrics (F,16)`, canonical `HYPOTHESES`, `initial_state=(0,0)`, `sequence_mode="new_independent_sequence"`, `profile="reconstructed_offline"`, and independent consecutive edge, absolute-symbol, and estimator-time labels. Continuation is rejected; no hidden reset or clock mapping is provided.

For every edge at row `t`, the DP adds `C[t,h]` to the survivor cost at `h.current_state` and competes for `h.next_state`. Exact same-state ties choose the smallest canonical hypothesis ID; the final free-state selection uses minimum cost, then canonical M1 state index. Tail bits/forced termination are absent. Full traceback is validated through `validate_hypothesis_edge_path()` and returns edge IDs, `input_pairs (F,2)`, `decoded_bits (2F,)`, `state_path (F+1 states)`, survivor costs `(F,4)`, and predecessor edge IDs `(F,4)` (`-1` means unreachable). Input and returned arrays are not mutated and returned diagnostics are read-only. Accumulation overflow raises an error.

ADR-013 was accepted by explicit user decision on 2026-10-28. The result is **isolated conditional reconstruction Viterbi decoder, NOT paper-exact joint receiver, NOT integrated adaptive receiver**. The DP minimizes only a frozen B4b additive objective conditioned on B4d's causal history; it does not optimize unknown channel trajectories jointly, use B4a posterior as branch cost, or implement [A](2). One call is one independent sequence. Costs across reporting frames must be concatenated to keep one path; no frame scheduler or B4d orchestration is implemented. `U0`/`U**` and frame-constant forward-model compatibility remain source/integration questions. ADR-009/011 remain proposed; ADR-013 accepted; `paper_exact:false`, `receiver_enabled:false`, SCI-METRIC-02 open.

## M4.7u/B5c — isolated end-to-end single-path composition

Added `receiver/reconstruction_conditional_decode.py` as a composition layer
only. B4d already supplies immutable per-symbol history containing the exact
B4c candidate metrics and their canonical order, labels, cutoffs, and profile
provenance. The adapter copies those actual rows into immutable `(F,16)` costs;
it does not recompute B4b after B4d or alter B4a, B4c, B4d, or B5b. It invokes
the existing conditional Viterbi exactly once for the entire explicitly
declared independent sequence.

The wrapper requires the first absolute symbol to be the declared independent
trellis origin, initial encoder state `(0,0)`, and separate sample/symbol/
estimator labels. It rejects continuation rather than silently resetting.
B4d split continuation plus caller-side row concatenation and one B5b call is
tested, but automatic split stitching is not implemented. Frame labels remain
reporting metadata and do not reset the path or estimator. No new ADR was
needed; accepted ADR-013 defines the existing conditional path objective.

Result status: **isolated end-to-end single-path reconstructed receiver, NOT
paper-exact joint receiver, NOT general multipath receiver**. The forward model
remains unchanged and frame scheduling, `U0`/`U**` source mapping, general
complex fading, multipath, and statistical BER/SER evaluation remain blocked or
out of scope. ADR-009/011 remain proposed; SCI-02/SCI-03/SCI-METRIC-02 remain
open; `paper_exact:false` and `receiver_enabled:false` remain unchanged.

## M4.7v/B5d — segmented B4d continuation with one final B5b pass

Added `receiver/reconstruction_segmented_decode.py`. Its explicit segment
descriptors partition one complete received buffer by absolute first symbol,
sample-buffer offset, and positive symbol count. The first segment runs B4d in
independent mode with ADR-004 prior; every later segment runs B4d continuation
with the previous final estimator state/posterior and predecessor clock labels.
The adapter copies exact metric and posterior rows from each immutable B4d
history, retains segment and sequence positions, then calls B5b exactly once.
It adds no new posterior, likelihood, estimator, or Viterbi math.

Continuous symbol/sample labels and contiguous nonoverlapping segment offsets
are checked. The estimator tick is caller-initialized and advances once per
symbol, independently of absolute symbol labels. Per-symbol records include
segment index/local position and sequence position; boundary records contain
absolute symbol/sample ranges, buffer offsets, and estimator clocks.

Tests compare monolithic B5c and segmented B5d for F=1, 2, 4, and 6 with the
requested partitions, including uneven six-symbol partitions and varying
explicit per-symbol recursion schedules. The comparison covers frozen metrics,
per-symbol posterior history, final state/posterior, decoded path/bits, and
conditional path cost. Spy tests confirm exactly one initial run, continuation
at every later segment, exact state/posterior handoff, and one final B5b call.
This is **isolated segmented single-path reconstruction decode, NOT
paper-exact joint receiver, NOT general frame-constant channel integration**.
No new ADR was required. Frame-constant forward scheduling and statistical
BER/SER remain out of scope; `paper_exact:false`, `receiver_enabled:false`,
ADR-009/011 proposed, and SCI-METRIC-02 open remain unchanged.

## M5a — evaluation contract and isolated error counts

`hf_tcm.evaluation.error_metrics` is a post-decode measurement layer. It
strictly compares equal-length information-bit vectors and coded 8PSK symbol
index vectors, pools raw run counts, and derives BER/SER from the pooled
denominators. The symbol mapping uses M1 output triples and ADR-002 for both
reference and decoded edge paths. It does not accept truth through receiver
APIs, run an experiment, compute intervals, or change M1–M4 behavior.

M2 matched comparison and SNR scaling are BLOCKED because M2 consumes normalized
symbol-rate observations under its own AWGN convention, while B5c/B5d consumes
eight-sample windows with explicit channel estimates and ADR-005 beta. See
`M5_EVALUATION_PROTOCOL.md` for the audited conventions and proposed
uncertainty policy. ADR-014 is proposed only for future cluster-bootstrap
intervals; all existing ADR statuses remain unchanged.

## M5b — received-to-bits smoke harness

Added `evaluation/reconstruction_smoke_experiment.py`, which validates the
inactive reconstruction config, creates a complex received buffer from explicit
M1/ADR-002 symbols, rectangular 8-sample ZOH, a real gain, and an exact supplied
complex perturbation array, then composes either the existing B5c monolithic or
B5d segmented entry point with M5a. All run operands and provenance are
explicit. Reference bits remain within this evaluation-side function and are
not sent to either receiver API. The result retains read-only reference and
received arrays, receiver outputs, counts, rates, clocks, config provenance,
and initial CSI/perturbation provenance.

Correct-model zero-error controls use explicit oracle-initialized `full_iq` and
`fluctuating_iq` equal to `(a,a)`, `alpha_prime=1`, `K_tilde=0`, and `mu0=0`.
Those values are test/run inputs, not automatically sourced truth. Perturbations
are literal finite arrays and are not interpreted as AWGN or AR(1). B5c/B5d
equivalence and pooled-count arithmetic are checked, but no inference about
robustness or performance follows. Matched M2 and SNR-calibrated statistical
experiments remain BLOCKED; ADR-014 remains proposed and no interval is
calculated.

## M5c — sample-energy/noise audit and baseline readiness

Audited M1's unit-magnitude 8PSK, M3's unscaled 8-sample ZOH, M2's symbol-rate
AWGN equation and metrics, and the explicit M3 fluctuating-noise AR(1) helper.
Added evaluation-only deterministic diagnostics for sample energy, complete
block energies, means/component powers, and covariance-derived mean power.
They neither assign physical units nor enter B5c/B5d.

At fixed real gain `a`, symbol-rate discrete signal energy is `a²`; the
8-sample ZOH discrete sum is `8a²`; physical energy additionally needs a
declared sampled complex-envelope normalization and `Δt`. M2 uses
`N0=Es/(2·10^(Eb/N0/10))` with real/imag variance `N0/2` on symbol samples.
The M3 AR(1) process is not AWGN, and its `n` parameter is not automatically
the ADR-012 samples-per-symbol. A same-buffer symbol mean is not yet a matched
M2 observation because the reducer covariance and CSI/gain compensation are
not specified by the M2 API.

ADR-015 is accepted for the narrow M5d discrete control: `reconstructed_offline`,
L=1, positive real gain `a`, zero delay, normalized 8PSK, rectangular ZOH at
8 samples/symbol, and iid circular complex AWGN with explicit per-sample power
`sigma_squared` and I/Q component variance `sigma_squared/2`. Evaluation
generates noise once; M2 and B5 share the same immutable received buffer. M2
uses the mean of eight samples divided by oracle `a`. B5 uses raw samples and
oracle-initialized `(a,a)` with frozen `alpha_prime=1`, `K_tilde=0`, `mu0=0`.
The only SNR-like label is `effective discrete gamma_b=4a²/sigma_squared`;
physical HF `Eb/N0`, adaptive CSI parity, and general matched comparisons are
still blocked.

`evaluation.matched_m2_observation` and
`evaluation.matched_m2_b5_experiment` implement this as an isolated paired
control using the existing M2 soft decoder, B5c/B5d, and M5a metrics. Under
the fixed correct-model estimates, B5 branch costs equal M2 soft costs scaled
by `8a²` plus a candidate-independent per-symbol offset. Small unique-optimum
controls agree; this is not a performance claim. ADR-014 remains proposed,
confidence intervals and sweeps remain blocked. SCI-02, SCI-03 and
SCI-METRIC-02 remain open; accepted ADRs, `paper_exact:false`, and
`receiver_enabled:false` are unchanged.

## M5f — accepted ADR-014 and exploratory paired B/C inference

ADR-014 was explicitly accepted by the user on 2026-10-28. The implementation
resamples complete independent coded sequences, preserves paired B/C counts
using the same cluster indices, pools integer counts inside each replicate,
and reports two-sided 95% percentile bounds from 2000 PCG64 bootstrap draws
with `numpy.quantile(method="linear")`. The explicit bootstrap seed and
resample-index matrix are retained. Warning thresholds are heuristics and are
not criteria for a validated study; see `M5_BOOTSTRAP_STATISTICAL_CONTRACT.md`.

The one fixed M5f study is exploratory: 12 independent runs, F=32,
`a=0.75`, `sigma_squared=0.08`, `beta=0.7`, explicit mismatched state
`(0.42,0.91)`, B frozen at `(1,0,0)`, C at
`alpha_prime=0.85`, `K_tilde=(0.35,-0.2)`, `mu0=(0,0)`. Each run creates one
sample-level ADR-015 AWGN realization shared by B and C. Separate SeedSequence
roots are used for data and noise; bootstrap uses its own explicit seed. No
parameter was tuned on these runs. B had no observed errors and C had more
errors in this one setting. The intervals are flagged exploratory and do not
validate a general advantage or disadvantage.

Accepted ADRs remain 001/002/003/004/005/006/007/008/010/012/013/014/015;
proposed ADRs remain 009/011. SCI-02/SCI-03/SCI-METRIC-02 remain open and
`paper_exact:false`, `receiver_enabled:false` remain unchanged.
