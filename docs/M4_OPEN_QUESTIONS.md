# M4 — невирішені математичні розбіжності та потрібні уточнення

**M6c clarification (2026-10-30):** the local [A](1)/(5) scans at printed
pp. 4–5 are available and their explicit update and quadrature algebra match
the independent deterministic checks documented in
`M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md`. This does not resolve the meaning of the
source posterior/index set, author quadrature/sample convention, or the
author mapping from `θ`/trellis hypotheses to `b`. SCI-02, SCI-03, and
SCI-METRIC-02 remain OPEN; no ADR is changed by this clarification.

**M6d source-evidence update:** readable local scans pp. 4–7 were checked.
[A](3)/(5), p. 5, explicitly defines `b=0…7` and phase increment `bπ/4`;
Figures 2–3, p. 6, show encoder labels and a four-node trellis but do not
provide an adequately legended complete edge/output-to-`b` mapping. The
source defines passband `U_s/U_c` signs, not their equivalence to ADR-012
complex I/Q. Eight samples are stated per signal element, not as an explicit
ADR-012 symbol window or sample origin. [A](1) uses `U⁰` and [A](2) uses
`U**`; the audited text gives different contexts without stating their
identity. Pages 1–3 lack separate readable page scans, so visual-only content
there is SOURCE_UNAVAILABLE. See `M6_AUTHOR_MAPPING_EVIDENCE_AUDIT.md` and
`M6_AUTHOR_CLARIFICATION_REQUEST.md`. No author response exists and no open
SCI question or ADR status is changed.

Це перелік питань до математичної специфікації, не пропозиція замінити авторські методи. Формули [B] і [C] нижче звірено безпосередньо за `references/Автореферат_1-1.pdf` і `references/Раздел_4.pdf`; для локалізації наведено друковані сторінки та PDF-сторінки. Їхня наявність у попередніх роботах **не доводить автоматично**, що параметри чи конвенції прийняті статтею 2026 року [A].

| Пріоритет | Невирішене питання | Розбіжність / чого бракує | Що потрібно для зняття |
|---|---|---|---|
| 1 | Значення `M` проти чотиристанового кодера | [A], с. 4, та [B], друк. с. 10 (PDF p. 12), задають `M=2^(ν+k)` як число станів дискретного параметра `θ`, пов'язаних з інформаційними символами та станом кодера. Чотири стани M1 — лише комбінації двох memory bits. За `ν=2,k=2` формула дає `M=16`; за `ν=3,k=2` — `M=32`. Обидва числові випадки відрізняються від 4; точний варіант залежить від авторського значення `ν`. | Встановити конвенцію [A] для `ν` (пам'ять 2 чи constraint length 3), значення `k` та множину гіпотез `θ` в конкретному такті. Доведено, що `M` не є кількістю чотирьох trellis states; число 16 є умовним на `ν=2,k=2`. |
| 2 | Posterior для конкретного 8PSK TCM | [B], (7), друк. с. 6 (PDF p. 8), є формулою для двох станів OPM; [B], друк. с. 11 (PDF p. 13), каже будувати узагальнену transition matrix за кодом і формувати posterior за аналогією з (7), для `α,β=1…M`. Це дає загальне правило, але не друкує заповнену матрицю саме для кодера [A]. | Вивести/перевірити `π_{β,α}` для авторського trellis і стану `θ`, встановити відповідність `m/M` у сумі [B] (15), [A] (1), і підтвердити порядок індексів. Не копіювати двостанову формулу ОРМ як готову матрицю TCM. |
| 3 | Коефіцієнти рекурсії [A], (1), та джерело [B], (15) | [B], друк. с. 10 (PDF p. 12), (15) має підтверджену ту саму загальну алгебраїчну форму, що [A], с. 4, (1), включно з posterior-зваженим залишком і додаванням regular component. Це доводить структурний збіг, але не числові коефіцієнти/initial conditions для [A]. | Потрібно підтвердити з повною легендою [A] значення й ролі `α′`, `K̃`, `C`, фільтрованих `U⁰`, initial estimates та `μ₀`. Не встановлювати невідомі числа з [B]. |
| 4 | Перемикач кумулянтів [B], (16)–(19) і його статус у [A] | [B], друк. с. 10–11 (PDF pp. 12–13), прямо задає пороговий вибір `K/K′`, вікно `Z`, posterior-зважені інновації та моменти оновлення. [A], (1) називає `K̃` квазістаціонарними кумулянтами, але перевірені сторінки [A] не друкують точний перемикач і його параметри. | Потрібен прямий доказ з повного тексту [A], що застосовується саме правило [B] (16)–(19), а також авторські `Z`, threshold, `K`, `K′`. Сам факт формули в [B] такого переносу не доводить. |
| 5 | Квадрат залишку в критеріях | На доступному зображенні [A](2), с. 4, та скані [B](20), друк. с. 11 (PDF p. 13), показника `2` після різниці не видно. Раніше документація помилково називала його явним. Для [B](7), друк. с. 6 (PDF p. 8), квадрат залишку окремо видно під коренем у нормі likelihood; це інший критерій. | Буквальний запис [A](2), задуманий математичний функціонал і квадратна реалізація M4.6 мають бути розділені. Чи мається на увазі квадрат залишку в [A](2), та як співвіднести це з [B](20), — відкрите авторське уточнення SCI-METRIC-02. |
| 6 | Дві нормалізації шуму й початкові умови | [A], (9)–(10), друк. с. 7: `α_fp=e^(−4/n)`, `σ_fp=√(2/n²·(1−e^(−8/n)))`. [C], (4.9)–(4.10), друк. с. 113 (PDF p. 5): той самий `α`, але `σ_fp=√(2/h̄²·(1−e^(−8/n)))`; на [C] p. 113 `h̄²` визначено як signal/noise ratio і формула виводиться для `P̄_s=1`. | Різниця нормалізацій підтверджена: формули [C] і [A] не тотожні без `h̄²=n²`, якого джерела не задають. Модуль `fluctuating_noise.py` реалізує коефіцієнти [A]; початкові умови [A] не вказує. | Нульові початкові квадратури в коді є явним проєктним припущенням, не формулою зі статті. Не переносити `h̄²` із [C] і не робити σ тотожними. Якщо буде знайдено початкову умову в повному [A], окремо звірити її з цим припущенням. |
| 7 | Fading-модель [C], (4.19)–(4.22), і [A] | [C], друк. с. 116 (PDF p. 8), задає `α_μ`, `σ_μ`, regular amplitude/phase та параметри `ε_μ,β_l,γ_l`. В [A], с. 5, (5)–(6), є I/Q коефіцієнти променів, але зазначений набір fading-рекурсії/параметрів не надрукований на перевірених сторінках. | Чи й як канал [A] успадковує цей закон із [C] — не доведено. Потрібне явне посилання/рівняння [A] і нормування; до того не переносити параметри (4.19)–(4.22) в [A]. |
| 8 | Табл. 4.1 [C], стан кодера й labeling | [C], табл. 4.1, друк. с. 127 (PDF p. 19), для стовпців `C₂,C₁,C₀,B` підтверджує `B=4C₂+2C₁+C₀`. Але той же рядок `X₀=0,X₁=1`, пам'ять `00` друкує вихід `011`; [C], `G₁` та рис. 4.5a, друк. с. 126 (PDF p. 18), при буквальному стані до зсуву дають `010` через відкладений `C₀`. | Арифметичне правило B підтверджене для таблиці [C]; таблиця станів має внутрішню суперечність із її `G₁`/схемою або неописану конвенцію. Вона не доводить авторське mapping [A], де с. 5 задає `b∈0…7`, `Δφ=π/4`, але не явний `B(C₂,C₁,C₀)`. | Потрібне уточнення часової конвенції/можливої помилки таблиці [C] і явна відповідність integer `b` вихідному кортежу в [A]. До того natural-binary labeling лишається проєктним baseline. |
| 9 | Вікно рішення, границі та глибина `η` | [A], (2), друк. с. 4, і [B], (20), друк. с. 11 (PDF p. 13), задають окно `f=r−η…r`; [A], с. 6, задає `η=20`. Алгоритм [B] також має блокову обробку через `n·f` у (17),(19), але це не автоматично параметри [A]. | Потрібно уточнити для [A] включення меж, стартові/кінцеві стани, traceback та вирівнювання рішень при `η=20`. Не переносити межі/скидання з [B] без підтвердження. |
| 10 | Канальний закон, часові затримки та чисельні параметри | [A], (3)–(6), друк. с. 5; шумове рекурсивне рівняння (9)–(10), с. 7. [C], (4.19)–(4.22), с. 116 та таблиця 4.1, с. 127, задають інші деталізовані параметри для свого розділу. | Структурна подібність I/Q/променів не доводить, що [A] використовує саме fading coefficients, затримки, powers чи таблицю з [C]. | Потрібні явні значення/конвенції з [A] для `L`, `τ_l`, часової дискретизації, розподілу та фаз; все невказане позначити як невідоме, не заповнювати даними [C]. |

### SCI-METRIC-02 — буквальний запис і квадрат залишку в [A](2)

- **Статус:** OPEN — потрібне авторське уточнення; це окреме питання і воно не змінює ADR-001.
- **Буквальний запис [A](2):** на доступному зображенні попередньої редакції, с. 4, після дужок `U−U**` показник `2` не читається. Користувач повідомив, що у в7 формула так само наведена без нього; DOCX в7 у робочій копії наразі відсутній, тому ця деталь в7 не перевірена незалежно.
- **[B](20):** доступний скан, друк. с. 11 (PDF p. 13), також не показує явного показника `2` після залишку. Попередні твердження документів про явний квадрат у [A](2) та [B](20) виправлені; потрібне уточнення високоякісного оригіналу/авторського запису.
- **Математична інтерпретація:** для дослідницької реконструкції застосовується squared-residual / least-squares функціонал, який раніше був прийнятий у ADR-001. Це інтерпретація для реконструкції, не буквальна транскрипція видимого запису; її підтримка саме [B](20) потребує звірки, оскільки в наявному скані явного квадрата також не видно.
- **Фактична реалізація M4.6:** `src/hf_tcm/decoding/paper_metric.py::compute_paper_metric()` підносить кожен I/Q залишок до квадрата й підсумовує. Код не змінюється автоматично; M4.6 не є доказом авторського задуму.
- **Потрібна відповідь:** чи формула [A](2) має означати суму квадратів I/Q залишків, попри відсутній показник у видимому записі; чи є в [B](20) пропущений/нечитабельний знак або інша інтерпретація; і чи підтверджує автор squared-residual функціонал для [A].

## Безпосередньо перевірено за PDF

- **[B] формула (7):** автореферат, друк. с. 6 (PDF p. 8). Це нормований posterior для двох двійкових гіпотез. Функція правдоподібності використовує евклідову норму I/Q залишку: сума квадратів стоїть під коренем, далі йдуть експонента та сума з переходами `π_{β,α}`. На друк. с. 11 (PDF p. 13) текст окремо говорить про узагальнення за матрицею переходів відповідного коду і posterior для `α,β=1…M`; готової числової матриці M1 8PSK TCM там не наведено.
- **[B] формула (15):** автореферат, друк. с. 10 (PDF p. 12). Її рекурсія має ту саму загальну форму, що [A], (1), друк. с. 4: згасання попередньої флуктуючої оцінки плюс posterior-зважені інновації, потім додавання регулярної компоненти. Це підтверджує структурну відповідність, але не автоматичну рівність параметрів і початкових умов.
- **[B] формули (16)–(19):** друк. с. 10 (PDF p. 12). Вони задають конкретну порогову зміну `K/K′` через `A`, усереднення з вікном `Z`, обчислення posterior-зваженої інновації й оновлення на блокових межах `n·f`. На друк. с. 11 (PDF p. 13) пояснена робота перемикача. У [A] явно названо квазістаціонарні кумулянти, але використання саме цього правила та його параметрів на перевірених сторінках [A] не показано.
- **[B] формула (20):** автореферат, друк. с. 11 (PDF p. 13), у доступному скані не показує явного квадрата після залишку; те саме спостерігається на зображенні попередньої редакції [A](2), с. 4. Це виправляє попереднє твердження про явний квадрат в обох формулах. Формула (7) — інший вираз із нормою під коренем. Задум [A](2) лишається відкритим у SCI-METRIC-02.
- **`M` і стани кодера:** [B], друк. с. 10 (PDF p. 12), визначає `M=2^(ν+k)` як число станів дискретного параметра, а текст пов'язує цей параметр з інформаційними символами та станом коду. Чотири стани M1 описують лише двобітову пам'ять кодера. Це різні множини; точне числове `M` потребує авторської конвенції `ν,k`, але `M` не слід називати чотирма станами trellis.
- **[C] шум:** розділ 4, друк. с. 113 (PDF p. 5), формули (4.9)–(4.10), за умови `P̄_s=1`, визначає `h̄²` як відношення сигнал/шум. Коефіцієнт `α=exp(−4/n)` збігається з [A], (10), с. 7. Нормалізації `σ` різні: в [A] знаменник `n²`, у [C] — `h̄²`; джерела не задають між ними тотожності.
- **[C] fading:** друк. с. 116 (PDF p. 8), формули (4.19)–(4.22), задають окремі fading-параметри `ε_μ`, `β_l`, `γ_l`, `φ₀`. Такого набору формул і параметрів на перевірених сторінках [A] немає; перенос у модель 2026 не доведений.
- **[C] таблиця 4.1 і labeling:** друк. с. 127 (PDF p. 19) підтверджує `B=4C₂+2C₁+C₀` для власних рядків таблиці. Водночас рядок `X₀=0,X₁=1`, memory `00` дає `011`, тоді як [C], друк. с. 126 (PDF p. 18), схема 4.5a та `G₁` дають `010` при буквальному стані до зсуву. Табличне маркування арифметично зрозуміле, але таблиця станів і схема мають невирішену суперечність. Для [A] доведено лише `b∈{0,…,7}` і `Δφ=π/4` на друк. с. 5 та гілкові числові мітки на с. 6; явна формула `B(C₂,C₁,C₀)` там не надрукована.

## Межі M4.1: структурні гіпотези

`src/hf_tcm/coding/hypotheses.py` містить рівно 16 проєктних рядків, отриманих у стабільному порядку з `build_trellis()` — по одній гілці для кожної з 4 пар `(стан пам'яті, вхідна пара)`. Це число гілок/комбінацій, тоді як стан пам'яті має лише 4 значення. `hypothesis_id=0…15` — локальний індекс рядка, не доведена індексація авторського `θ` і не розв'язання значення `M` у [A]/[B].

Стан M1 конвенційно записаний як `(u1[k−1],u1[k−2])`; вихід у порядку `(c2,c1,c0)` дорівнює `(u0,u1 XOR u1[k−2],u1[k−1])`, наступний стан — `(u1,u1[k−1])`. Функція дозволеності перевіряє лише наявність конкретної гілки в цій структурі. Вона не задає матрицю переходів із вагами, імовірнісну модель, posterior або estimator.

M4.1 фіксує тільки внутрішню конвенцію коду. Питання авторського labeling, стану `θ`, кількості й індексації його значень та posterior залишаються відкритими в SCI-02/SCI-03; цей підетап їх не закриває.

## Межі M4.2: загальна posterior-рекурсія

`src/hf_tcm/coding/posterior.py` утворює структурну матрицю дозволених переходів розміром 16×16: ребро `i→j` є дозволеним, якщо `next_state(i) == current_state(j)`. Її елементи — лише `0/1`; вони не є ймовірностями. `posterior_update()` реалізує загальне оновлення `p⁺_j ∝ L_j Σ_i p_i T_{ij}` і приймає prior, рядково-стохастичну матрицю ймовірностей переходу та likelihood лише як явні аргументи. Заборонені структурою ребра мають нульову вагу в переданій матриці.

Нормування та невід'ємність перевіряються; відхиляються не-нормований prior, не-рядково-стохастична матриця, ненульова вага забороненого ребра та нульова повна evidence. Рекурсія використовує log-space. Жоден розподіл, перехідна ймовірність чи функція likelihood не задані за замовчуванням.

Це інфраструктурне байєсівське оновлення поверх проєктної множини M4.1. Воно не задає likelihood з [B], не доводить точної реалізації [B], (7), для 8PSK TCM, не встановлює індексацію `hypothesis_id` як авторське `θ` і не реалізує estimator [A], (1). SCI-02/SCI-03 лишаються відкритими.

Попереднє твердження про відсутність PDF [B]/[C] було чинне для старого стану робочої копії й тепер замінене прямою перевіркою. Формули [A], (9)–(10), реалізовані окремо з документованими нульовими початковими умовами; це не знімає відкритих питань estimator, posterior, labeling і канальної моделі та не робить весь тракт paper-exact.

Невирішені питання SCI-02…04 лишаються відкритими, а реалізація M4 estimator — заблокованою згідно з `PLAN.md` та `NEXT_TASK.md`.

## M4.7o/B4a — accepted project posterior policy; source questions remain open

За явним рішенням користувача від 2026-10-28 прийнято ADR-003/004/005 як реконструктивну policy. Перехідна матриця локальних 16 edge hypotheses рівномірна по фактичних дозволених переходах; initial edge prior має support `current_state=(0,0)`; likelihood `exp(-beta*F_rx)` використовує aggregate project reconstruction metric і явний `beta>0`. Ізольований adapter не надає авторського mapping локальних гіпотез до `θ`, candidate predictions, metric generation чи posterior orchestration.

Для першого спостереження edge prior уже описує перший edge від початкового стану. Тому перший observation update виконується без transition; наступне observation застосовує `T` до попереднього edge posterior і likelihood до нового edge. Це визначає внутрішню project clock послідовність adapter-а, але не встановлює відповідність edge index до сигналового symbol/sample у receiver.

Прийняття ADR-003/004/005 **не закриває SCI-02 або SCI-03**: labeling/`θ` correspondence, авторська гіпотеза множина, параметри estimator і авторський posterior залишаються невирішеними. Воно також не закриває SCI-METRIC-02: `F_rx` не є `paper_metric.py` чи підтвердженням буквального [A](2).

**B4b integration gate: BLOCKED.** Потрібні окреме рішення/контракт для зв'язку першого і наступних edge-metric vectors із символами causal one-path estimator, кандидатного ordering/output mapping та provenance часових cutoff-ів. Метрики й predictions не генеруються тут, а posterior не підключається до `reconstruction_causal_step.py`.

### M4.7t/B5b — залишкові питання після ізольованого decoder-а

- **ADR-013:** прийнято 2026-10-28 як project conditional full four-state Viterbi над замороженими B4b costs. Це не авторський алгоритм і не joint optimum над невідомими channel trajectories. B4a posterior та [A](2) не є branch costs.
- **Final state / termination:** ADR-013 задає вільний досяжний кінцевий стан, без tail bits та без forced termination.
- **Tie policy / traceback:** survivor tie вибирає мінімальний `hypothesis_id`; final tie — мінімальний канонічний M1 state index; виконується повний traceback. Це проектна policy, не успадкована з M2.
- **U0/U\*\* та frame schedule:** відповідність B4b candidate prediction до source-defined `U0`/`U**` не доведена. B4d може оновлювати оцінки кожен символ, а `reconstruction_forward.py` тримає коефіцієнти сталими в межах кадру. Правило спільного frame scheduling відсутнє.
- **B4d → B5b integration (історичний статус B5a/B5b):** цей gate закрито для однієї повної independent sequence у M4.7u/B5c; adapter збирає exact B4c metrics із B4d immutable history та викликає B5b один раз. Automatic split-fragment stitching і frame scheduler залишаються поза реалізацією.
- **Frame handling:** decoder приймає один independent sequence. Для одного codeword, розділеного на reporting frames, costs/labels мають бути concatenated перед одним викликом; автоматичного frame scheduler/reset немає.
- **U0/U\*\* та forward schedule:** source mapping лишається відкритим; B4d per-symbol estimate і frame-constant forward coefficients досі не узгоджені.
- **B5b:** isolated decoder READY; integrated adaptive receiver та paper-exact B5/B6 лишаються BLOCKED. ADR-009/011 proposed; `eta=20` не визначає beam width/traceback depth. SCI-METRIC-02 лишається open.

### M4.7u/B5c — status update for frozen B4d metric history

B4d returns immutable per-symbol B4c diagnostics. The B5c adapter uses each
exact metric vector already consumed by that symbol's posterior, validates its
row-to-symbol, estimator-time, sample-window, cutoff, profile, and canonical
hypothesis-order provenance, freezes the `(F,16)` matrix, and calls B5b once.
It never recomputes metrics from the final estimator state. B4d split
continuation plus caller-side metric-history concatenation is tested; automatic
split-fragment stitching in B5c remains unsupported. This does not resolve
`U0`/`U**`, frame-constant versus symbol-varying forward scheduling, complex
fading, multipath, or statistical BER/SER gates. SCI-METRIC-02 remains open.

### M4.7v/B5d — segmented continuation status

Segmented processing is now implemented for one continuous buffer and one
independent sequence. B4d begins once with ADR-004 and continues across every
segment boundary using the returned state, posterior, and adjacent clocks; the
resulting exact metric rows are passed to one final B5b invocation. Deterministic
tests establish monolithic/segmented equality for F=1,2,4,6 with the specified
partitions and explicit parameter schedules. This does not equate processing
segments with independent sequences or reporting frames.

Still BLOCKED: integration with the frame-constant `reconstruction_forward.py`
convention; source-level `U0`/`U**` correspondence; general complex fading or
multipath; and statistical BER/SER evaluation. A later BER/SER study needs an
evaluation-layer reference bit sequence, declared channel/noise conditions,
matched baselines, independent repetitions, raw error counts, uncertainty
intervals, and sensitivity analysis. No new ADR is needed for the accepted
segmentation/continuation composition. SCI-METRIC-02 remains open.

### M5a — evaluation gates

- **BER/SER array measurement:** READY for strict equal-length post-decode
  arrays and raw-count pooling. No simulation trials were run.
- **SNR/noise scaling:** BLOCKED. M2's AWGN is symbol-rate with normalized
  `Es=1`; M3 has an 8-sample repeated baseband waveform and separate channel and
  noise APIs; the physical sample interval/energy and reconstructed observation
  covariance are not jointly specified.
- **Matched M2 baseline:** BLOCKED until observations, channel/CSI condition,
  noise realization/scaling, and termination/length policy are common.
- **Confidence intervals:** BLOCKED until a statistical policy is accepted.
  Draft ADR-014 proposes cluster bootstrap over independent coded sequences;
  no interval calculation or Monte Carlo execution is authorized here.
- **Performance claims:** no 1.5 dB replication or BER/SER gain is established.
  SCI-02, SCI-03, SCI-METRIC-02 and SCI-08 remain open.

### M5d — matched discrete control status

- **Narrow paired M2/B5 discrete-AWGN control:** READY under accepted ADR-015.
  Both algorithms consume one shared received buffer; M2 gets the exact
  mean-of-eight divided by explicit oracle gain `a`, B5 gets the raw eight
  samples and oracle-initialized frozen `(a,a)` estimate.
- **Effective discrete SNR-like label:** READY only as
  `gamma_b_eff=4a²/sigma_squared`; this is not physical HF `Eb/N0`.
- **Metric equivalence:** READY for the frozen correct-model control. B5 costs
  equal `8a²` times the M2 soft costs plus a candidate-independent centered
  energy term per symbol. Small seeded controls had matching unique paths.
- **General/adaptive CSI baseline, correlated noise, physical calibration:**
  BLOCKED; none is covered by ADR-015's narrow acceptance.
- **Monte Carlo, confidence intervals, BER-vs-SNR, or performance claims:**
  NOT RUN / BLOCKED. ADR-014 remains proposed.
- **Source status:** SCI-02, SCI-03 and SCI-METRIC-02 stay open;
  `paper_exact:false`, `receiver_enabled:false` remain unchanged.

### M5e adaptive-estimator diagnostic gate

- **Paired frozen/adaptive execution:** READY only for the isolated A/B/C
  controls in `M5_ADAPTIVE_ESTIMATOR_DIAGNOSTICS.md`. Adaptive updates change
  the estimate, posterior, and later-symbol metrics in tested examples; they
  do not guarantee fewer errors. One deterministic control produced worse C
  than B, so no monotonic improvement assumption is valid.
- **Paired statistical inference:** BLOCKED. ADR-014 remains proposed; the
  small controls do not justify BER/SER confidence intervals or performance
  statements. Predeclare run populations, seed streams, and cluster-level
  uncertainty policy before a Monte Carlo study.
- **Adaptive M2 comparison / general CSI parity:** BLOCKED. M2's accepted
  oracle-CSI control is not matched to non-oracle B/C initialization.
- **Science questions:** SCI-02, SCI-03, SCI-METRIC-02 remain open; no paper
  performance result is established.

### M5f current statistical status

- **ADR-014:** accepted by explicit user decision 2026-10-28. Paired
  independent-sequence cluster bootstrap, same B/C resample indices, pooled
  integer counts, 2000 replicates, 95% two-sided percentile intervals, and
  explicit seed are implemented.
- **One small paired experiment:** READY as an exploratory implementation
  check. It used 12 independent clusters and emitted `too_few_independent_runs`,
  `rare_error_count`, `degenerate_bootstrap_distribution`, and
  `bootstrap_interval_unreliable`. B had zero observed errors; C had more
  errors in this fixed setting. This is not a validated population comparison.
- **Future BER/SER curves or advantage claims:** BLOCKED pending a predeclared
  adequately sized experiment design, sensitivity plan, and explicit
  scientific review of the receiver assumptions. Confidence intervals from a
  small run do not remove those requirements.
- **Other gates:** physical HF Eb/N0, adaptive M2 CSI parity, complex fading,
  multipath, and paper-result reproduction remain BLOCKED. SCI-02, SCI-03 and
  SCI-METRIC-02 remain open; `paper_exact:false`, `receiver_enabled:false`.

### M5g proposed preregistration status

- **Design artifact:** READY for review only. `M5_PREREGISTERED_EXPERIMENT_DESIGN.md`
  and `configs/m5g_experiment_design_draft.json` are proposals and
  `execution_authorized=false`; M5g ran no pilot or confirmatory experiment.
- **M5f evidence:** preserved as exploratory; adaptive C was worse in all 12
  observed pairs, while B had zero observed errors. This does not estimate a
  population-level effect or authorize tuning.
- **Sample size:** BLOCKED until a separate pilot estimates paired
  between-sequence variation and the user approves the target absolute
  DeltaBER interval half-width and compute budget. Pilot/evaluation seeds are
  disjoint and pilot records cannot enter confirmation.
- **Grid/policy:** 0/5/10/15 dB and the 5 dB primary stratum, fixed M5f policy,
  F=256, and 30-run-per-stratum pilot are proposed only and require approval.
- **Multiplicity / external claims:** secondary strata are descriptive unless
  a simultaneous-inference policy is approved. Physical HF Eb/N0, adaptive
  M2 CSI parity, and paper performance reproduction remain BLOCKED. ADR-014
  remains accepted; no new ADR was proposed or accepted.

### M5b — smoke-evaluation status

- **Received-to-bits harness:** READY for deterministic L=1 real-channel
  controls with validated config, explicit real gain, explicit complex
  perturbation, and explicit receiver state/parameters.
- **Oracle initial CSI:** used only in noiseless control cases and labelled in
  each evaluation record. It does not establish an initialization policy for a
  general receiver.
- **Reference-data boundary:** READY; reference bits create the transmit-side
  test waveform and are compared only after decoding. They are absent from
  B5c/B5d operands/results.
- **M2 matched comparison and SNR calibration (at M5b):** BLOCKED pending
  common waveform/sample energy, noise/covariance, channel realization, CSI
  and termination contracts. Narrow oracle-CSI discrete controls were later
  authorized by ADR-015; physical SNR and adaptive comparison stay blocked.
- **Monte Carlo, confidence intervals, and performance claims:** not run.
  ADR-014 remains proposed; no bootstrap implementation or acceptance occurred.

### M5c — sample-energy/noise and matched-baseline gates

- M2's `Eb/N0` formula is symbol-rate: `N0=Es/(2·10^(Eb/N0/10))` for two
  information bits per coded 8PSK symbol. M3's ZOH repeats eight unscaled
  samples, so its discrete sample sum is eight times the symbol-rate sample
  energy. A physical `Es/Eb` needs a chosen complex-envelope convention and
  `Δt`; no conversion is silently assumed.
- M3's fluctuating-noise helper implements the specified AR(1) quadratures,
  but its `n` is caller-supplied and not automatically tied to ADR-012's
  samples/symbol. Under explicit `n=8`, zero deterministic initial state, and
  independent unit-normal innovations, the mean-of-eight complex variance is
  `0.018307879788`; the process is correlated and not AWGN.
- A shared-buffer M2 symbol mean is a candidate only. Its covariance, possible
  gain equalization, 90-degree coordinate convention, and CSI policy remain
  unaccepted. M2 has no CSI input, whereas B5 accepts initial estimates and
  updates them.
- Draft ADR-015 records energy, per-sample noise covariance, M2 observation,
  CSI and SNR-label choices. It remains **proposed**. SNR calibration and
  matched M2 comparison remain **BLOCKED**; ADR-014 remains proposed for
  uncertainty intervals. See `M5_NOISE_BASELINE_CALIBRATION_AUDIT.md`.

### M5h-prep validated pilot preparation

- **Candidate protocol/config validation:** READY. The standalone M5h pilot
  draft explicitly contains the 0/5/10/15 dB effective discrete gamma grid,
  primary 5 dB stratum, `a=0.75`, F=256, 30 sequences per stratum, B/C
  policies, origins, ADR-015 variances, and ADR-014 contract. These remain
  proposed candidate values.
- **Seed provenance and run isolation:** READY as a deterministic, domain-
  separated SeedSequence procedure with separate pilot/evaluation data, noise,
  and bootstrap namespaces and unique run/stratum IDs. No data or noise were
  generated in M5h-prep.
- **Execution:** BLOCKED. The draft retains `execution_authorized=false` and
  `design_status="proposed"`; the runner rejects before any callback.
- **Sample size / confirmatory inference:** BLOCKED pending explicit design
  approval, independent pilot results, approved absolute interval half-width
  and resource budget, bootstrap precision review, and a decision for handling
  numerical decoder failures in the estimand.
- M5f remains historical and unchanged; SCI-02, SCI-03, SCI-METRIC-02,
  `paper_exact:false`, and `receiver_enabled:false` remain unchanged. No new
  ADR is required unless the accepted science/statistical contract changes.


## M5h-run follow-up

The user approved and the bounded independent planning pilot completed under M5h; see `M5_INDEPENDENT_PILOT_REPORT.md`. The candidate design was executed as approved without altering its proposed draft or M5f artifacts. All 120 runs completed; the primary 5 dB pilot produced 30 paired records and `s_d=0.053093594133490844`, corresponding to candidate-only `R_approx=28` for epsilon=0.02. The pseudo-study precision diagnostic is not confirmatory precision evidence. Before a confirmatory study, decide the target precision and sample-size method/run count; treatment of missing decoder outputs for the confirmatory estimand; review of observed C coefficient-error-growth diagnostics and high paired DeltaBER as pilot findings without tuning from them; resource limits and a frozen design; and separate authorization. Confirmatory inference remains BLOCKED. No new ADR is needed unless a future decision changes an accepted scientific or statistical contract.


## M5i confirmatory design decision gate

M5i formalizes a candidate future design informed by M5h: effective discrete gamma_b=5 dB, F=256, R=100, epsilon=0.02 target, and fixed paired B/C policies. The 30 saved M5h primary checkpoints reproduce `s_d=0.053093594133490844` and `R_approx=28`. R=100 is a conservative operational recommendation with resource margin, not a CI-precision guarantee. See `M5_CONFIRMATORY_DESIGN_CONTRACT.md`.

The candidate validation and 100-ID reserved-evaluation seed manifest are READY for review. M5j remains BLOCKED pending the user's review of the single-profile scientific question, approval of precision/resource/failure policy, and separate immutable run-specific authorization. M5f and M5h stay historical and excluded from M5j. No new ADR is needed under the accepted contracts.

## M5j independent confirmatory result

The user separately authorized M5j. All 100 preregistered independent paired sequence clusters completed with no numerical failures; raw checkpoints were independently re-aggregated, unique IDs/received hashes and evaluation seeds were verified, and ADR-014 intervals were recomputed from saved counts. The primary 5 dB effective discrete gamma_b DeltaBER was 0.3655078125 (95% CI [0.35548681640625, 0.37578173828125]); the epsilon=0.02 target was met. This is limited to the fixed reconstructed_offline L=1 ADR-015 profile. See `M5_CONFIRMATORY_EVALUATION_REPORT.md`. It is not a physical HF Eb/N0 gain or paper-exact/general HF result.

## M5k post-confirmatory mechanism questions

The saved M5j checkpoints independently reproduce a positive fixed-policy contrast (`DeltaBER=+0.3655078125`, 95% ADR-014 CI `[0.35548681640625,0.37578173828125]`) for the sole fixed reconstructed L=1 ADR-015 discrete-AWGN profile. This does **not** identify why C performed worse. The read-only audit and H1–H8 diagnostic matrix are in `M5_POST_CONFIRMATORY_SCIENTIFIC_AUDIT.md`.

Implementation causality is supported by existing API/tests: each symbol's metrics use the pre-observation state; its current posterior and update use only that symbol's complete 8-sample window; the post-state is available to the next symbol; and B5b decodes the saved metric matrix once after the full sequence. Correct causality does not settle scientific model fidelity.

H1–H5 remain unresolved: no source-derived stability evidence for the frozen `alpha_prime/K_tilde` profile, no independent resolution of ADR-012 against source convention, no author-confirmed [A](1) innovation semantics, no authoritative correction scale/direction for M5j, and no source-confirmed mapping of the project-local 16 edge hypotheses to the author's estimator hypotheses. H6 is supported only as a code dependency of later metrics on earlier updates; its contribution to M5j BER is unresolved. H7 is a known gap between frame-constant forward coefficients and per-symbol adaptive state; its causal contribution is unresolved. H8 is a known ADR-005 pseudo-likelihood/source-likelihood distinction, with source intent and performance contribution unresolved.

M5j does not preserve per-symbol pre/post states, posterior vectors, innovations, or candidate-metric history (**HISTORY UNAVAILABLE**). Do not infer that history from final coefficients or recompute historical branch metrics from final estimates. Any future diagnostic needs its own question and protocol, fresh seeds, explicit per-symbol logging, and separate authorization; do not feed reference bits or true channel gain into recursion. SCI-02, SCI-03, and SCI-METRIC-02 remain open. ADR-009/011 remain proposed; `paper_exact:false` and `receiver_enabled:false` are unchanged. No new ADR is needed for this audit.

## M6a causal trace follow-up

The new deterministic evaluation trace verifies [A](1) algebra for the
explicit reconstructed operands, ADR-004 first-edge prior/no transition,
continuation transition/likelihood order, posterior normalization, pre-state
metric timing, post-state next-symbol availability, and segmented continuation.
It does not decide source semantics: SCI-02, SCI-03, and SCI-METRIC-02 remain
open. H1–H5 remain unresolved; H6 is verified as an implementation dependency,
not as the cause of M5j errors. H7/H8 are documented differences whose
performance contribution is unestablished. M5j historical per-symbol trace is
unavailable and is not reconstructed. See `M6_CAUSAL_ESTIMATOR_TRACE_CONTRACT.md`.

## M6b-prep status

The proposed, non-executable fresh-seed trace protocol and H1-H8 test matrix are recorded in `M6_FRESH_TRACE_DIAGNOSTIC_PROTOCOL.md` and `M6_ROOT_CAUSE_TEST_MATRIX.md`. This is preparation only: no seed stream, received sample, receiver call, or performance result was created. H1-H5 remain unresolved; H6 is supported as a code dependency only, with its M5j causal contribution unresolved; H7/H8 are documented model distinctions whose contribution remains unresolved. SCI-02, SCI-03, and SCI-METRIC-02 remain open. No ADR changed.

## M6b-run evidence boundary

The three authorized fresh-seed B/C traces corroborate only the code-level
causal ordering: first post-state divergence at symbol 0, next-symbol
pre-state/metric/posterior divergence at symbol 1, followed by later decoded
path differences. They do not identify a source-model defect or explain M5j's
errors. H1-H5 and SCI-02, SCI-03, SCI-METRIC-02 remain open; H6's
implementation dependency is supported while its decoded-error contribution
remains unresolved. H7/H8 remain model distinctions with contributions
unresolved. No ADR changed and no M5j conclusion is updated. See
`M6_FRESH_TRACE_DIAGNOSTIC_REPORT.md`.

## M6e deterministic update intervention

For the fixed reconstructed operands, an independent scalar oracle and the
existing [A](1) update API agree. Holding a deterministic next ADR-012 window,
ADR-002 16-edge order, beta, and squared-residual metric fixed, one update
changes subsequent candidate predictions and metric rows according to the
explicit [A](5) coefficient-delta identity. A separate fixed-prior
first-edge posterior changes consistently with those rows. These are
one-step implementation dependencies only; no full decode or M5j causal
contribution was tested. H1–H5, SCI-02, SCI-03, and SCI-METRIC-02 remain open;
H6 is supported as an implementation dependency, while its M5j error
contribution remains unresolved. See `M6_UPDATE_INTERVENTION_AUDIT.md`.

## M6f deterministic factorial ablation

For one fixed deterministic two-symbol input, B/A/K/C share the first-symbol
metrics, posterior, and innovation. The independent first-update state
decomposition is additive; at symbol 1, the actual B4d metric rows show the
quadratic factorial interaction predicted by the expanded squared residual.
Actual transition posteriors are distinct from the explicitly uniform
common-prior sensitivity. The transition intermediate `q` is unavailable as
a raw B4d output and is only independently derived from the common previous
posterior and ADR-003 matrix for an equality check. This supports H6 as an
implementation dependency in the reconstruction. H1–H5, H6's contribution
to M5j BER, H7/H8 contributions, SCI-02, SCI-03, and SCI-METRIC-02 remain
unresolved. No decoder or performance evidence was produced. See
`M6_FACTORIAL_UPDATE_ABLATION_REPORT.md`.

## M6g deterministic feedback audit clarification

On one fixed eight-symbol mathematical buffer, the current reconstruction's
closed-loop update -> next prediction/metric -> posterior -> later innovation
dependency is directly observed and checked against independent scalar
oracles. A separate common-operand replay freezes all eight B innovations
before replaying the other arms. B and A remain invariant across regimes;
K/C diverge after their own innovation differs from B's stream. Factorial
interactions also accumulate under common operands, demonstrating that
alpha/K recursive composition itself contributes to multistep interaction.
This is a deterministic implementation mechanism, not a performance
evaluation or historical M5j causal attribution. SCI-02, SCI-03, and
SCI-METRIC-02 remain open; no ADR or source claim changed.

## M6h posterior-weight intervention clarification

On the fixed M6g fixture, swapping own posterior weights for same-symbol B
weights while holding each arm's state/predictions/observation fixed changes
the innovation for A/K/C from symbol 1 onward. The multistep clamp replay
retains each arm's own posterior history but uses B weights only in the
correction operand; B/A remain trajectory-invariant and K/C develop later
state, metric, and posterior differences. This establishes reconstructed
algorithmic contrasts for one deterministic input only. H2-H5 author/source
semantics, H7/H8 causal contributions, and H6's contribution to M5j errors
remain unresolved. SCI-02, SCI-03, and SCI-METRIC-02 remain OPEN; no ADR or
receiver mathematics changed. See `M6_POSTERIOR_CLAMP_ABLATION_REPORT.md`.

## M7a policy-study proposal

M6 mechanisms motivate a fixed nine-arm alpha/K grid for independent
reconstructed-policy research, but no policy is yet selected or optimal.
M7a freezes separate TRAIN/VALIDATION/FINAL namespaces and the selection,
failure, and ADR-014 analysis rules without generating seeds or observations.
TRAIN authorization and decoder-pass/resource planning remain blocked;
VALIDATION and FINAL require later, separate approvals. SCI-02, SCI-03, and
SCI-METRIC-02 remain open; H2-H5 source questions and H6's M5j causal
contribution remain unresolved. No ADR or receiver mathematics changed. See
`M7_POLICY_STUDY_DESIGN.md`.

## M7c/M8a status clarification

M7's exploratory TRAIN selection is closed with frozen B as winner;
`ADAPTIVE_GAIN_NOT_ESTABLISHED` and `VALIDATION_NOT_EXECUTED`. This does not
close or reinterpret any source question. M8a proposes an anchored
reconstructed profile for future independent project research, but its draft
is unauthorized and no observations were generated. SCI-02, SCI-03, and
SCI-METRIC-02 remain OPEN; no ADR status changed; `paper_exact:false` and
`receiver_enabled:false` remain.

### M8c/M9a clarification

M8's recovered exploratory grid selected frozen B; the original M8 validation
was not executed. A read-only, post-selection paired summary for the M8
runner-up does not resolve source mapping, quadrature, innovation, correction,
likelihood, or variable-channel questions. M9a proposes a new fixed-policy
constant-gain comparison and remains unauthorized. The variable-channel
branch requires its own profile, decision gates, and dataset. SCI-02, SCI-03,
and SCI-METRIC-02 remain OPEN; no ADR status changed.

### M10a channel-model proposal

A controlled piecewise real-positive gain profile was designed for
evaluation only. It is a new project experimental model, not a source claim
or physical HF model. Its evaluation-side design was subsequently accepted as
ADR-016; production channel integration remains outside that decision. The
model and M10b result do not resolve SCI-02, SCI-03, or SCI-METRIC-02.

### M10 ADR-016 and M10b status

ADR-016 accepts `controlled_piecewise_real_gain_v1` only for evaluation-side
channel generation and analysis. M10b completed the authorized 100-cluster
fixed-policy study; the independent P1 paired interval crosses zero, so the
direction is unresolved under this design. This does not resolve SCI-02,
SCI-03, or SCI-METRIC-02, author mapping, physical channel behavior, or
historical M5j causation. Production channel integration remains outside the
decision; `paper_exact:false` and `receiver_enabled:false` remain.
