# Scientific open issues & decisions / Наукові невизначеності

**Правило:** документи зі статті не виправляються мовчки. Кожне припущення має бути у конфігурації експерименту; кожне погоджене рішення оформлюється записом ADR.

| ID | Тема | Статус | Де шукати |
|---|---|---|---|
| SCI-01 | Реконструктивна інтерпретація адаптивної метрики | ACCEPTED reconstruction interpretation: squared-residual criterion; буквальний запис [A](2) лишається невирішеним окремим SCI-METRIC-02; paper-exact декодер також залежить від SCI-02…04 | стаття, с. 4, формула (2); с. 5; `M4_OPEN_QUESTIONS.md` |
| SCI-02 | 8PSK labeling, порядок C2/C1/C0, зсув π/4, termination | OPEN, потрібен explicit baseline | с. 5–6, рисунки 2–3 |
| SCI-03 | ???????????? ???????????, ?????????, ????????? ??????? ? ????????? ????? | OPEN, ?????? ?????? paper-exact estimator; M4.4 ???????? ???? ???? ??? ?????????? ?????? | ?. 4, ??????????? ?????; ???. [4], [15] |
| SCI-04 | L, затримки, відносна енергія променів, Rician K, кореляція | OPEN, блокує paper-exact channel | с. 3, 5–7 |
| SCI-05 | Фізичний зміст p′ₙ=5·10⁻² | OPEN | с. 6 |
| SCI-06 | Еталонний алгоритм, BER-рівень, методика 1,5 дБ | OPEN | с. 7 |
| SCI-07 | Імпульсна форма, семплова дискретизація 8/символ і синхронізація | OPEN | с. 5–6 |
| SCI-08 | Число незалежних запусків, статистична похибка | OPEN | с. 6–7 |

## Прийняті проєктні припущення (не твердження статті)

- SCI-02 M1 baseline: використовується явне natural-binary відображення `m = 4*c2 + 2*c1 + c0`, доступне як профіль `baseline_assumption`; реконструктивний профіль `assumed_natural_binary` прийнято окремо в ADR-002 нижче. Порядок виходу `(c2,c1,c0)` і стан `(u1[k−1],u1[k−2])` трактуються за формулами в `MATHEMATICAL_MODEL.md`; початковий стан кодера — `(0,0)`, termination не додається. `phase_offset` M1 задається викликом явно та за замовчуванням дорівнює `0`. Ці маркування не підтверджені як авторські; SCI-02 залишається OPEN щодо статті [A].
- M2 baseline: використовує `Es=1`, `k_info=2`, явний `numpy.random.Generator`, початковий стан `(0,0)`, без tail-бітів та без обмеження кінцевого стану. Hard branch cost — Hamming відстань між 8PSK labels; soft branch cost — квадрат комплексної евклідової відстані. `BER` рахує помилки декодованих інформаційних бітів; `SER` рахує помилки nearest-point 8PSK рішення до декодера. Це P0 контрольні алгоритми, не твердження про повне відтворення статті.
- M3 channel baseline: усі затримки цілочисельні й задані у відліках; середні потужності шляхів, K-фактори та LOS-фази передаються явно й не виводяться зі статті. Статичний Rician і `approximate_ar1` — окремі профілі; AR(1) застосовується лише до diffuse-компонента. `approximate_rectangular` використовує 8-відліковий zero-order hold без pulse shaping або синхронізації. SCI-04 та SCI-07 залишаються OPEN, тож ці профілі не називаються paper-exact.
- M4.4 [??????]: `receiver/paper_recursion.py` ????????? ??????????? ????? [A](1)/[B](15) ??? ???? ????????? ??, K?, posterior, ??????????? ?????????? ??????, ???????????????/???????????? I/Q ?? ??; posterior ??? ???? ?????????? ?? ?????? ???????. ?????????? ???? ? ????? ???????? ?? ????????? ???????. ??????: exact algebraic recursion kernel, NOT complete paper-exact estimator; SCI-03 ??????????? OPEN.
- APP-01: перший контрольний режим використовує complex baseband по **одному відліку на символ**, потім окремий waveform mode з 8 відліками.
- APP-02: Python >=3.11, NumPy/SciPy/Matplotlib/pytest, модульна структура `src`.
- APP-03: `ChannelTruth` може зберігатися для тестів, але не доступний `estimated` приймачу.
- APP-04: для порівняння однакові seed, дані та канальні реалізації (paired comparisons).
- APP-05: експериментальні криві супроводжувати raw counts та довірчими інтервалами.

### ADR-001 — Реконструктивна інтерпретація адаптивної метрики (SCI-01)

- Date / Автор погодження: 2026-10-26 / за прямим запитом користувача.
- Пов'язана вимога: FR-15 / SCI-01.
- Джерело: надана стаття, с. 4, формула (2), та пояснювальний текст на с. 5.
- Що відомо з джерела: видимий запис [A](2) задає мінімізацію за вікном `f=r−η…r`, променями `l=1…L`, відліками та двома квадратурами `j=1,2`; у доступному зображенні попередньої редакції показника `2` після `U−U**` не видно. На с. 5 текст характеризує перехід від Hamming до метрик Евклідового простору. Доступний скан [B](20) також не показує явного показника `2` після залишку. Буквальний зміст формул відкритий у SCI-METRIC-02.
- Що саме обрано: для дослідницької реконструкції SCI-01 тлумачиться як накопичений squared-residual / least-squares критерій за вікном спостереження. Це прийнята інтерпретація, а не підтверджене буквальним символом у [A](2) відтворення. Одновідлікова метрика M2 `|y−S|²` є baseline і сама по собі не реалізує формулу (2).
- Альтернативи: буквальне сумування непіднесених до квадрата залишків або squared-residual інтерпретація; автор має підтвердити задум, а не редактор коду обирати формулу за контекстом.
- Наслідки: реконструктивна інтерпретація визначена, але її відповідність буквальному [A](2) відкрита. Побудова прогнозів `U**`, точні індексні відповідності та paper-exact adaptive decoder також лишаються залежними від SCI-02…04.
- Які тести додано: жодних; це документальне наукове тлумачення без зміни алгоритмічного коду.
- Статус: accepted — лише реконструктивна інтерпретація SCI-01; це не закриває SCI-METRIC-02. M4 залишається заблокованим іншими відкритими питаннями.

## ADR для reconstructed_offline

**M6c source clarification (2026-10-30; not an ADR):** the local [A] scans
confirm the printed algebra of [A](1) and [A](5), and the project kernels
match independent deterministic arithmetic for explicit operands. The scans
do not establish ADR-012's complex-to-I/Q observation convention, the
source-to-project `θ`/edge/`b` mapping, source numerical estimator parameters,
or physical units/time origin. Existing ADR-002 and ADR-012 remain accepted
reconstruction decisions only; no decision or status changed in M6c.

**M6d source-evidence clarification (2026-10-30; not an ADR):** local [A]
evidence defines `b=0…7`, its additive `bπ/4` phase contribution, and the
passband sine/cosine equations. It does not identify the encoder-edge to `b`
table, complex-baseband I/Q convention, or project sample/update cutoffs.
Figures 2–3 show code/trellis structure without a complete author-labeling
table. The source distinguishes `U⁰` in (1) and `U**` in (2), without a
verified identity. Existing ADR-002 natural-binary and ADR-012 `(-Im,Re)`
choices remain project reconstructions; [B]/[C] evidence is external-only.
No author response was received, no ADR was accepted, and SCI-02/SCI-03/
SCI-METRIC-02 remain open. Full locator inventory and pp. 1–3 scan-coverage
limitation are documented in `M6_AUTHOR_MAPPING_EVIDENCE_AUDIT.md`.

Рішення користувача від **2026-10-26** приймає ADR-002, ADR-006, ADR-007, ADR-008 і ADR-010 лише як проєктні припущення дослідницької реконструкції. Окремі рішення від **2026-10-28** приймають ADR-003/004/005 для reconstruction posterior policy, ADR-012 для вузького L=1 causal real-channel bridge, ADR-013 для conditional full four-state Viterbi на frozen B4b costs, ADR-014 для paired cluster bootstrap та ADR-015 для вузького paired discrete-AWGN M2/B5 control. Це не підтвердження авторської моделі [A]/[B] і не закриває SCI-02, SCI-03 чи SCI-METRIC-02. Поточні proposed ADR: 009/011.

| ADR | Тема | Рішення або запропонований варіант | Статус |
|---|---|---|---|
| ADR-002 | Labeling та `θ→branch/b` | Прийнято профіль `assumed_natural_binary`: `b=4*c2+2*c1+c0` для виходу `(c2,c1,c0)`; це не mapping, підтверджений [A], і не встановлює `hypothesis_id↔θ`. | accepted — user decision 2026-10-26 |
| ADR-003 | Transition probabilities | Для кожної попередньої локальної edge hypothesis рядок має рівні `1/d(h)` лише на дозволених наступних edges, 0 поза structural support. Рядки стохастичні; `d` рахується з фактичної маски. | accepted — user decision 2026-10-28 |
| ADR-004 | Initial state/prior | Початковий encoder state `(0,0)`; prior рівномірний лише серед edge hypotheses, у яких `current_state=(0,0)`; решта мають 0. | accepted — user decision 2026-10-28 |
| ADR-005 | Reconstruction likelihood | `L_h∝exp(−beta F_rx,h)`, явний `beta>0`; `F_rx` є aggregate reconstruction metric, не `paper_metric` [A](2). Це project pseudo-likelihood, не підтверджена статистична модель [A]/[B]. | accepted — user decision 2026-10-28 |
| ADR-006 | Observation model | Приймаються лише aggregate received I/Q і receiver-side project prediction; `ChannelTruth` та прихований стан генератора не доступні estimated receiver-у. Окремі per-path вимірювання не стверджуються. | accepted — user decision 2026-10-26 |
| ADR-007 | Estimator parameters and provenance | `α′`, `K̃`, `μ₀` та початкові I/Q оцінки кожного променя є явними обов'язковими reconstruction values; числові значення не виводяться з [A] і не копіюються з [B]/[C]. Оцінки та оновлення не використовують `ChannelTruth`; значення, походження і часова конвенція відтворювані в config та майбутніх result records. | accepted — user decision 2026-10-26 |
| ADR-008 | Timebase | `approximate_rectangular_8sps`; затримки — явні integer sample values; межі вихідного кадру задаються явно; edge policy — `zero_padding`. Це проєктна конвенція, не [A]. | accepted — user decision 2026-10-26 |
| ADR-009 | Search/traceback | Окремий fixed-lag beam search із явним width і tie-break. | proposed |
| ADR-010 | Claims/metrics | Результати маркуються `reconstructed_offline`, `paper_exact=false`; жодних непідтверджених paper-exact або performance claims. | accepted — user decision 2026-10-26 |
| ADR-011 | Pseudo-path operands | Одночасне cancellation-derived pseudo-observation з aggregate sample і попередніх оцінок, не фізичне per-path вимірювання. | proposed |
| ADR-012 | L=1 aggregate-to-observed-I/Q mapping | Для `reconstructed_offline`, `L=1`, real channel assumption, zero delay, rectangular ZOH 8 samples/symbol: per-sample `(-Im(received[n]), Re(received[n]))`, середнє рівно восьми sample values на завершений symbol, один causal update після восьмого sample; новий snapshot лише для наступного symbol. Це реконструктивне припущення, не спостережний алгоритм [A]. | accepted — user decision 2026-10-28 |
| ADR-013 | Conditional full four-state Viterbi | For `reconstructed_offline`, freeze B4b costs `(F,16)` in canonical `HYPOTHESES` order and minimize their sum over valid paths. This is conditional on the frozen estimator history, not a joint channel-trajectory optimum or author algorithm. Start `(0,0)`, free final state, no termination/tails, full traceback. Exact survivor ties choose minimum `hypothesis_id`; exact final ties choose minimum canonical M1 state index. | accepted — user decision 2026-10-28 |
| ADR-014 | Statistical uncertainty for BER/SER | Paired cluster bootstrap over independent full coded-sequence runs; resample the same run indices for B/C, pool integer BER/SER counts per replicate, use two-sided 95% percentile intervals with 2000 explicit-seed replicates, preserve raw run records, and emit explicit small/rare/degenerate-sample warnings. | accepted — explicit user decision 2026-10-28 |
| ADR-015 | Sample energy, noise calibration, matched observation and CSI | Narrow accepted control: normalized 8PSK, real `a>0`, zero-delay ZOH 8 samples/symbol, iid circular complex AWGN per sample with explicit `sigma_squared>0` and component variances `sigma_squared/2`; M2 uses mean of the same eight received samples divided by oracle `a`; B5 uses the same raw samples with oracle-initialized `(a,a)` and frozen recursion (`alpha_prime=1`, `K_tilde=0`, `mu0=0`). Label only `effective discrete gamma_b=4a²/sigma_squared`; do not call it physical Eb/N0. `beta` is not noise precision. General CSI, correlated noise, and physical calibration remain outside this decision. | accepted — explicit user decision 2026-10-28 |
| ADR-016 | Controlled piecewise real-gain evaluation extension | `controlled_piecewise_real_gain_v1`, `y[n]=a[floor(n/8)]x[n]+w[n]`, `L=1`, zero delay, real positive per-symbol gain, exact P0/P1/P2 schedules, fixed ADR-015 noise variance; evaluation-side generation and analysis only. Does not change the receiver, production channel integration, or source-fidelity claims. | accepted — explicit user decision 2026-10-30; evaluation-only |

### ADR-012 — вузький причинний L=1 observed-IQ bridge

- **Рішення користувача від 2026-10-28:** прийнято тільки цей ADR. Профіль — `reconstructed_offline`, один шлях, real-channel experiment, zero delay та rectangular ZOH із 8 samples/symbol.
- **Спостереження:** для кожного абсолютного sample `n` застосувати `(-Im(received[n]), Re(received[n]))`; observed vector одного symbol `f` є арифметичним середнім цих перетворених значень для рівно восьми sample labels `symbol_origin_sample + 8f, ..., symbol_origin_sample + 8f + 7`.
- **Час:** estimator виконує один крок після отримання восьмого sample symbol `f`. До виклику caller явно подає estimator `time_index` і target absolute `symbol_index` та засвідчує, що state є станом до спостереження `f`; API не конвертує origins між шкалами. Snapshot після `i→i+1` дозволений тільки для symbol `f+1` чи пізніших. Заборонені майбутні samples.
- **Межа знань:** `a`, `h`, передані bits/phase та `ChannelTruth` не є аргументами observed-IQ чи estimator adapter. Відомий real coefficient дозволений лише для незалежного simulation oracle. Конверсія не ділить на `h`; загальний complex channel не покривається.
- **Шум:** усереднення — визначений детермінований operator, але не твердження незалежного AWGN. Noise covariance/temporal correlation лишається відкритою для likelihood і статистичних висновків; variance не підставляється.
- **Обмеження:** це реконструктивне припущення, не алгоритм спостереження, підтверджений [A]. Не приймає ADR-011 і не задає posterior, likelihood, transitions, initialization policy чи decoder.
- **Статус:** accepted — user decision 2026-10-28; `paper_exact=false`, `receiver_enabled=false`.

### Формальний запис прийнятих рішень

Для прийнятих ADR дата та підстава зафіксовані окремо нижче. Обрані значення є тільки project reconstruction choices; першоджерело [A] їх не підтверджує.

#### ADR-003 — uniform probability on allowed local edge transitions

- **Обрано:** у canonical `HYPOTHESES` order рядок `h` — previous edge, колонка `k` — next edge. Для фактичної структурної маски `A[h,k]`, `d(h)=Σ_k A[h,k]`, `T[h,k]=A[h,k]/d(h)`. Заборонені edges мають нульову ймовірність.
- **Перевірена структура:** у поточному M1-порядку 16 edge hypotheses; фактичний `d(h)` обчислюється з `ALLOWED_HYPOTHESIS_TRANSITIONS`, а не задається константою. Поточний API дає `d(h)=4` для всіх рядків, але код не припускає цього.
- **Межа:** це рівномірна реконструктивна перехідна модель, не авторська матриця для `θ`; SCI-02/SCI-03 відкриті.
- **Статус:** accepted — user decision 2026-10-28.

#### ADR-004 — initial edge prior

- **Обрано:** encoder initial state дорівнює `(0,0)`. У canonical 16-edge ordering початковий prior має `1/4` на кожній гіпотезі з `current_state=(0,0)` і `0` на інших. `hypothesis_id` лише відображає стабільний рядок і не визначає support; `next_state` також не використовується.
- **Час першого спостереження:** `π₀` уже розподіляє **перший edge**. Для першого emission metric `F₀` обчислюється `p₀(h) ∝ π₀(h)L₀(h)` без transition. Для `t≥1`: `q_t(k)=Σ_h p_{t−1}(h)T[h,k]`, потім `p_t(k)∝q_t(k)L_t(k)`. Це запобігає зсуву на один edge; local edge `t` ще не ототожнюється з author `θ` чи signal symbol.
- **Статус:** accepted — user decision 2026-10-28; mapping локальних edge hypotheses до авторського `θ` не підтверджено.

#### ADR-005 — aggregate reconstruction pseudo-likelihood

- **Обрано:** для явного вектора aggregate reconstruction metrics `F_rx,h≥0` і обов'язкового явного `beta>0`, відносні likelihood weights пропорційні `exp(-beta*F_rx,h)`. Спільний log-shift до exponentiation не змінює normalized posterior.
- **Metric boundary:** `F_rx` формується/передається зовні як aggregate receiver-side reconstruction metric; він не є `decoding/paper_metric.py` і не успадковує невизначений `[A](2)`.
- **Статистична межа:** це project pseudo-likelihood, а не доведена [A]/[B] likelihood чи Gaussian noise model. Немає прихованої variance.
- **Статус:** accepted — user decision 2026-10-28; SCI-02/SCI-03 та SCI-METRIC-02 залишаються відкритими.

#### ADR-002 — reconstruction labeling

- **Обрано:** тільки явний профіль `assumed_natural_binary`; для output order `(c2,c1,c0)`, `b=4*c2+2*c1+c0`.
- **Межа:** це не доводить відповідність локальних 16 M4.1 hypotheses авторським `theta` і не змінює M1 conventions.
- **Статус:** accepted — user decision 2026-10-26.

#### ADR-006 — aggregate observation boundary

- **Обрано:** estimated receiver працює лише з aggregate received I/Q та власними receiver-side project predictions; `ChannelTruth`, `.truth`, channel generator state та simulated path contributions не використовуються як estimated inputs.
- **Межа:** окремі path measurements не заявляються.
- **Статус:** accepted — user decision 2026-10-26.

#### ADR-008 — reconstruction timebase and frame edges

- **Обрано:** profile `approximate_rectangular_8sps`, explicit integer sample delays, explicit output frame boundaries і `zero_padding` edge policy.
- **Межа:** це реконструктивна sample-level convention, а не підтверджена часова модель статті [A]. Фізичні `τ_l` автоматично не переводяться в samples.
- **Статус:** accepted — user decision 2026-10-26.

#### ADR-010 — result naming and claims

- **Обрано:** profile/result label `reconstructed_offline`, поле `paper_exact=false`, без непідтверджених paper-exact або performance claims.
- **Межа:** це не активує receiver (`receiver_enabled` лишається `false`) і не підтверджує заявлений у статті BER gain.
- **Статус:** accepted — user decision 2026-10-26.

#### ADR-007 — explicit reconstruction estimator parameters

- **Обрано:** `alpha_prime`, `k_tilde`, `mu0` і початкові fluctuating/full I/Q оцінки є явними обов'язковими значеннями конфігурації для кожного з `L` променів. Початковий абсолютний індекс оцінок теж задається явно.
- **Походження:** [A] не задає числових значень цих параметрів. Значення не запозичуються автоматично з [B] чи [C]. Конфігурація має окремо фіксувати `status`, `source`, `note` для кожного параметра, початкових оцінок та часової конвенції.
- **Межа даних:** ініціалізація й будь-яке майбутнє оновлення estimated state не читають `ChannelTruth`, `.truth`, channel generator або RNG state.
- **Часова конвенція:** стан на індексі `i` є входом алгебраїчного ядра [A](1); його виходи мають індекс `i+1`. Мапування цього дискретного індексу на символи/відліки має бути явним поза ядром.
- **Результати:** майбутній result record мусить містити фактичні значення параметрів та provenance, часову конвенцію й оцінки з їх абсолютним індексом. У B3a result writer не додається.
- **Статус:** accepted — явне рішення користувача від 2026-10-26 для `reconstructed_offline`; це не приймає ADR-011 і не підтверджує [A].

#### ADR-012 — вузький L=1 aggregate baseband observation mapping

- **Прийняте рішення користувача 2026-10-28:** для `reconstructed_offline`, `L=1`, real-channel experiment, zero delay та rectangular ZOH 8 samples/symbol кожен aggregate sample перетворюється на `(-Im(received[n]), Re(received[n]))`; `observed_iq` одного symbol є arithmetic mean рівно восьми відліків.
- **Clock/cutoff:** absolute sample labels для symbol `f` — `O+8f…O+8f+7`, де `O` явно заданий symbol origin. Один update виконується після отримання останнього відліку. Caller явно задає estimator index `i`, який позначає state до спостереження `f`; неявного mapping `i=f` немає. Після `i→i+1` snapshot доступний лише від `f+1`.
- **Межа знань:** `a`, `h`, `ChannelTruth`, `.truth` і transmitted phase не є аргументами adapter. Simulation fixture може знати `a` для oracle; це координатна конвенція, не ділення на true h. Загальний complex channel не підтримується.
- **Шум:** середнє є лише детермінованим operator; воно не оголошує samples незалежним AWGN і не задає прихованої variance. Noise covariance/correlation залишається відкритою для likelihood/statistics.
- **Не вирішено:** posterior, likelihood, transition/initial-posterior policy, multipath pseudo-observations (ADR-011) та decoder не додаються. Це project assumption, не спостережний алгоритм підтверджений [A].
- **Статус:** accepted — user decision 2026-10-28; `paper_exact=false`, `receiver_enabled=false`.

## Шаблон нового рішення (ADR)

```md
### ADR-XXX — Назва
- Date / Автор погодження:
- Пов'язана вимога: FR-xx / SCI-xx
- Джерело: стаття, сторінка/формула або інше вказане джерело
- Що відомо з джерела:
- Що саме обрано:
- Альтернативи:
- Наслідки (для BER, порівнянності, фізичної точності):
- Які тести додано:
- Статус: proposed / accepted / superseded
```

### M4.7p/B4b ? isolated candidate metrics (implementation boundary)

The accepted narrow ADR-012 profile is used only for a one-symbol `reconstructed_offline`, L=1, real-channel experiment with zero delay and rectangular ZOH at 8 samples/symbol. For each local edge hypothesis, candidate phase comes from that hypothesis's `output_bits` via `assumed_natural_binary`; hypothesis IDs remain row metadata, not phase indices. Candidate prediction uses the pre-observation `full_iq` snapshot. The observed operand is the eight separate per-sample `(-Im,Re)` pairs, and `F_rx` is their aggregate squared residual against the existing forward model. The estimator recursion's mean-of-eight observation is not substituted for this metric.

This remains a project reconstruction metric, distinct from [A](2) and `paper_metric.py`. It is supplied to the accepted B4a posterior adapter only as an aligned vector; it does not perform posterior update, coefficient update, sequence decoding, or information-bit traceback. A candidate-metric vector is insufficient to recover information bits because it evaluates one local edge at a time and does not select a temporally consistent path or apply traceback/termination rules. SCI-METRIC-02 remains open. ADR-009 and ADR-011 remain proposed; `paper_exact:false` and `receiver_enabled:false` remain in force.

### M4.7q/B4c ? single-symbol posterior-estimator integration boundary

B4c composes accepted project assumptions only for one explicit symbol in the narrow ADR-012 profile. The caller supplies one of two mutually exclusive posterior inputs: first-edge initial prior or later-edge previous posterior. First edge applies the current emission without transition; later edge applies the transition then current emission. The resulting current-edge posterior weights residuals against `(16,2)` predictions. Each hypothesis row is aligned across `HYPOTHESES`, its M1 `output_bits`, assumed-natural-binary phase, B4b metric, and [A](5) prediction. Repeated output-bit edges may share predictions.

Predictions use pre-observation `full_iq`; observations use exactly the eight target-symbol samples, with their arithmetic mean supplied to the [A](1) recursion. The current posterior is generated from current metrics and is not used to build its own candidate metrics/predictions. The explicit clock/cutoff contract is `prediction cutoff=O+8f-1`, `observation/posterior cutoff=O+8f+7`; caller supplies estimator tick `i` separately from symbol `f`; the successor state `i+1` is available only for `f+1` or later. This is an isolated project reconstruction step, not evidence that the correspondence or emission model is specified by [A]. No decoder or bit output is provided. SCI-METRIC-02 remains open; ADR-009/011 remain proposed; `paper_exact:false`, `receiver_enabled:false`.

### M4.7r/B4d ? sequence scheduling, initialization and continuation

The new runner handles one continuous buffer containing exact contiguous complex samples for the requested absolute consecutive symbols. `symbol_origin_sample=O` means absolute symbol `f` occupies `O+8f..O+8f+7`, matching B4c. Caller supplies the initial estimator time and first absolute symbol as a pair; both advance one per completed symbol without assuming equality. The runner checks sample labels/cutoffs and sends only the prefix available through the current symbol to B4c.

`new_independent_sequence` explicitly declares that its first requested symbol is the trellis sequence origin and uses ADR-004 once, with no first transition. `continuation` explicitly identifies the preceding symbol and estimator tick and supplies their posterior plus the state already advanced from that symbol; it performs one transition on the first newly processed symbol. No arbitrary mid-trellis fragment is silently initialized. Frame segmentation is reporting-only; it does not reset posterior or state. Recursive operands can be constant or provided as complete per-symbol schedules. These are execution contracts around accepted assumptions, not new author-specified signal/noise rules.

### M4.7t/B5b — accepted conditional reconstruction Viterbi

M1 `build_trellis()` and `HYPOTHESES` use the same state-major/input-pair-major ordering. A path is valid when the first edge starts at its explicit initial memory state and every adjacent pair satisfies `previous.next_state == following.current_state`. One edge is one TCM symbol and contains the two input bits recoverable for that symbol. IDs are canonical row labels, not phase indices; phase still comes from `output_bits` through ADR-002.

B4b `F_rx[f,h]` can define fixed additive branch costs only after a caller freezes the completed causal `(F,16)` matrix and explicitly adopts the conditional objective. Since B4b uses the pre-observation estimator state generated by past observations/posteriors, the resulting conditional Viterbi pass is not a joint optimization over unknown channel/estimator trajectories. B4a posterior is normalized history-dependent mass, not a branch cost; `[A](2)` is a separate unresolved paper metric.

**ADR-013 was explicitly accepted by the user on 2026-10-28.** For a separate `reconstructed_offline` pass, the decoder accepts frozen B4b costs of shape `(F,16)` in canonical hypothesis order and minimizes their additive sum over structurally valid paths. It starts at `(0,0)`, allows any reachable final state, adds no tail bits and performs full traceback. Exact equal survivor costs into one state select the minimum canonical `hypothesis_id`; exact equal final costs select the minimum state index in M1 `STATES` order. Input pairs `(F,2)` and flattened information bits `(2F,)` come from the selected hypotheses' `input_bits`. This is conditional on the frozen estimator history, not a joint channel-trajectory optimum or an author algorithm. It does not use B4a posterior as a branch cost, and it does not establish [A](2). ADR-009/011 remain proposed; SCI-METRIC-02 remains open; `paper_exact:false`, `receiver_enabled:false`.

### ADR-016 — controlled piecewise real-gain evaluation extension

Accepted by explicit user decision on 2026-10-30, scoped only to the
evaluation-side profile `controlled_piecewise_real_gain_v1`. Its exact
equation, P0/P1/P2 schedules, fixed-noise convention, pairing assumptions,
channel-truth boundary, limitations, and decision provenance are recorded in
[`M10_PROPOSED_SCIENTIFIC_DECISION.md`](M10_PROPOSED_SCIENTIFIC_DECISION.md) and
machine-readable form in
[`adr_016_controlled_piecewise_real_gain.json`](../configs/adr_016_controlled_piecewise_real_gain.json).
The document and JSON have separate SHA-256 sidecars. ADR-016 does not alter
ADR-015, `reconstructed_offline`, receiver or decoder mathematics, or enable a
production channel/receiver mode. It makes no physical HF or paper-exact claim.
The exact M10b execution remains governed by a separate approved run snapshot.

### M5f — ADR-014 accepted and paired cluster-bootstrap implemented

**ADR-014 status:** accepted by explicit user decision 2026-10-28. The policy
resamples complete independent coded sequences as clusters, applies the same
resampled indices to paired B/C records, pools raw integer counts per
replicate, and reports two-sided 95% percentile intervals from 2000 explicit-
seed replicates. It retains raw run records and warns on small, rare-error,
all-zero, identical, imbalanced, or degenerate samples. The quantile
convention is NumPy `quantile(method="linear")`. This is a project evaluation
policy, not an author algorithm or proof of a performance gain.

The fixed M5f exploratory run has 12 independent sequences of 32 symbols at
`a=0.75`, `sigma_squared=0.08`, `beta=0.7`, mismatched initial I/Q `(0.42,0.91)`,
and C update operands `alpha_prime=0.85`, `K_tilde=(0.35,-0.2)`, `mu0=(0,0)`.
Data/noise/bootstrap streams use separate explicit seeds. B/C share each
run's received samples, initial state, clocks, profile and pseudo-likelihood;
B uses `(alpha_prime,K_tilde,mu0)=(1,0,0)`. The fixed configuration was not
tuned on the evaluation outcomes. The experiment makes no general BER
advantage claim.

### M5g — proposed preregistered design

`docs/M5_PREREGISTERED_EXPERIMENT_DESIGN.md` and
`configs/m5g_experiment_design_draft.json` specify a proposed future paired
study. The JSON is deliberately non-executable and authorizes no runs. M5f's
unfavorable C result (189/768 bit errors and 181/384 symbol errors versus
zero observed errors for B) is preserved and is not used to tune C. The design
proposes a 0/5/10/15 dB effective discrete gamma grid at fixed `a=0.75`, a
5 dB primary DeltaBER contrast, and a separate pilot/evaluation seed protocol.
The sample-size gate remains BLOCKED pending approval of an absolute CI
half-width and compute budget, plus pilot variability. No stochastic run was
performed for M5g. ADR statuses remain unchanged: accepted
001/002/003/004/005/006/007/008/010/012/013/014/015; proposed 009/011.
`paper_exact:false`, `receiver_enabled:false`, SCI-02, SCI-03, and
SCI-METRIC-02 remain unchanged/open.

All other decisions remain unchanged: accepted ADR-001/002/003/004/005/006/
007/008/010/012/013/014/015; proposed ADR-009/011. SCI-02, SCI-03 and
SCI-METRIC-02 remain open; `paper_exact:false`, `receiver_enabled:false`
remain unchanged.

### M7a independent reconstructed policy-study proposal

M7a proposes, but does not execute, a fixed nine-policy alpha/K study for
the reconstructed_offline L=1 ADR-015 profile. Its candidates are project
policies and none is author-attributed or presumed optimal. M6 deterministic
mechanism results motivate the grid but do not establish M5j's BER cause.
Training selection, validation, and any future final evaluation use separate
new seed namespaces; every later partition requires a separate approval.
No ADR is accepted or modified. Source questions SCI-02, SCI-03, and
SCI-METRIC-02 remain open; `paper_exact:false` and `receiver_enabled:false`
remain in force.

### M7c closeout and M8a anchored reconstruction proposal

M7's 40-sequence exploratory TRAIN grid selected frozen B. A read-only
checkpoint replay reproduced the nine-policy raw-count ranking; the historical
M7b artifacts keep their original `TRAIN_SELECTED_NOT_VALIDATED` status. No
VALIDATION was run because the frozen B winner would create a B-versus-B
contrast, and the runner-up was not promoted after observing TRAIN. The
closeout is `EXPLORATORY_GRID_COMPLETED; TRAIN_WINNER_FROZEN_B;
ADAPTIVE_GAIN_NOT_ESTABLISHED; VALIDATION_NOT_EXECUTED`.

M8a proposes, without accepting an ADR, the evaluation-only label
`anchored_reconstructed_offline`, using receiver-side `mu0=(0.42,0.91)` and
initial fluctuating state `(0,0)` while preserving the initial full estimate
`(0.42,0.91)`. This is a project research variant, not an author-defined
anchor or oracle CSI. For the existing recursion, `full_(n+1) =
alpha_prime*full_n + (1-alpha_prime)*mu0 + K_tilde elementwise eps_n`;
therefore zero anchor with K=0 decays toward zero for `0<=alpha_prime<1`,
while anchor equal to the initial full estimate with K=0 holds the full
estimate constant. These are algebraic consequences only and do not prove
statistical stability or performance. M8a's eight-arm draft is unauthorized;
no streams or observations were generated. No receiver mathematics, accepted
ADR, or open SCI status changed. `paper_exact:false` and
`receiver_enabled:false` remain.

### M8c closeout / M9a proposal clarification

The M8 recovery checkpoints independently reproduce frozen B as the winner
and the original status remains `TRAIN_SELECTED_NOT_VALIDATED`. Its
post-selection `anch_a085_k025` paired contrast is descriptive only; M8
validation was not executed. M9a proposes a separately fixed two-policy,
constant-gain comparison on new independent samples, but is
`proposed / false / none`; no samples or child RNG streams were generated.
The M9 candidate was identified post hoc from M8 and is not source-aligned.
Variable-channel models remain separate future questions. No ADR was
accepted, and SCI-02/SCI-03/SCI-METRIC-02 remain open.

### M9 closeout / M10a proposed channel extension

The independent M9b fixed comparison was confirmed from saved checkpoints:
anchored BER/SER point estimates were lower than frozen B, while both paired
95% cluster-bootstrap intervals included zero. This does not establish
superiority, equivalence, or noninferiority; see
`docs/M9_FIXED_POLICY_CLOSEOUT.md`.

M10a proposes `controlled_piecewise_real_gain_v1` as a distinct evaluation-
side channel extension. It is not part of `reconstructed_offline` and is not
a physical HF model. P0/P1/P2 have the same frame-average squared gain, but
P0 differs in gain distribution and equal frame energy does not imply equal
local SNR. A pure deterministic adapter and unauthorized design validator
were added; no RNG or observations were generated. The proposed decision is
unaccepted; no ADR, including ADR-015, is changed. Production integration and
M10b execution require an explicit scientific decision and separate user
authorization. `paper_exact:false`, `receiver_enabled:false`, accepted and
proposed ADRs, and open SCI questions are unchanged.
