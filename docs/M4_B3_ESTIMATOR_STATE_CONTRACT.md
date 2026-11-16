# M4.7i/B3b-0 — explicit-operand крок стану реконструктивного оцінювача

**Статус:** isolated explicit-operand reconstruction state-step adapter, `L=1`. Це не повний estimator, не інтегрований B3b і не paper-exact система.

**Підстава:** ADR-007 прийнятий для `reconstructed_offline` рішенням користувача від 2026-10-26. Це проєктне рішення не визначає числових параметрів статті [A] і не закриває SCI-03/04 чи ADR-011.

## Що зберігає snapshot state

`hf_tcm.receiver.reconstruction_estimator_state.ReconstructionEstimatorState` має рівно такі поля:

| Поле | Тип і форма | Значення |
|---|---|---|
| `fluctuating_iq` | immutable `float64`, `(L,2)` | Флуктуюча `\(\widetilde{\mu}^{*(l)}_{j,i}\)` на `time_index`; колонки `I,Q`. Відповідає `previous_fluctuating` для наступного виклику recursion kernel. |
| `full_iq` | immutable `float64`, `(L,2)` | Повна `\(\mu^{*(l)}_{j,i}\)` на тому самому індексі. Значення передається явно під час початкової ініціалізації; крок повертає її за [A](1). |
| `time_index` | `int` | Явна абсолютна мітка дискретного індексу рекурсії. Це не sample index і не фізичний час. |

`L` — додатна кількість променів, виведена з масиву оцінок. Обидва масиви мусять мати однакову форму `(L,2)` і містити лише скінченні дійсні значення. Конструктор копіює дані у власні immutable буфери; окремі запуски не ділять стан. Немає значення за замовчуванням для оцінок або часу.

### Семантика формули (1)

Візуальна звірка скану [A](1), с. 4, та [B](15), друк. с. 10 (PDF p. 12), підтверджує: `\(\widetilde{\mu}^{*}\)` — флуктуюча складова; `\(\mu_0\)` — окрема регулярна складова; `\(\mu^{*}=\widetilde{\mu}^{*}+\mu_0\)` — повна оцінка. Це різні величини. `fluctuating_iq` зберігає `\(\widetilde{\mu}^{*}\)`, `full_iq` зберігає `\(\mu^{*}\)`, а `mu0` лишається явним параметром оновлення і не є полем state. Тому неоднозначності семантики контейнера немає.

Контейнер навмисно не зберігає `alpha_prime`, `k_tilde`, `mu0`, posterior, observations чи predictions: це сталі входи/дані кроку, а не накопичений mutable state. Їх значення та provenance належать явному `reconstructed_offline` config і майбутнім result records.

## Зв'язок із рекурсійним ядром

Фактичний API `update_quadrature_estimates()` у `receiver/paper_recursion.py` приймає такі форми:

| Аргумент | Один промінь | `L` променів |
|---|---:|---:|
| `previous_fluctuating` | `(2,)` | `(L,2)` |
| `alpha_prime` | scalar | scalar |
| `k_tilde` | `(2,)` | `(L,2)` |
| `posterior` | `(M,)` | `(L,M)` |
| `observed_iq` | `(2,)` | `(L,2)` |
| `predicted_iq` | `(M,2)` | `(L,M,2)` |
| `mu0` | `(2,)` | `(L,2)` |
| return value | дві пари `(2,)` | `(new_fluctuating, full_estimate)`, обидві `(L,2)` |

`M` — довжина переданого hypothesis axis; код не пов'язує її з авторським `theta` чи локальним `hypothesis_id`. Для state contract використовується пакетна форма `(L,2)`, навіть коли `L=1`, щоб контейнер мав одну однозначну форму.

На кроці `i`, `fluctuating_iq` є `previous_fluctuating`; явні `alpha_prime`, `k_tilde`, posterior, `observed_iq`, `predicted_iq` та `mu0` подаються caller-ом. Ядро повертає флуктуючу `\(\widetilde{\mu}^{*}_{i+1}\)` і повну `\(\mu^{*}_{i+1}=\widetilde{\mu}^{*}_{i+1}+\mu_0\)`. Ядро не приймає timestamps і не перевіряє часову узгодженість операндів. Caller має явно створити наступний snapshot з результатами та `time_index=i+1`; контейнер не має методу transition/update.

## M4.7i/B3b-0 explicit-operand state step (`L=1`)

`receiver/reconstruction_estimator_step.py::advance_reconstruction_estimator_state()` виконує один state transition і делегує всю числову операцію незміненому `update_quadrature_estimates()`. Усі параметри передаються keyword arguments без defaults: `time_index`, `next_time_index`, `alpha_prime`, `k_tilde`, `mu0`, `observed_iq`, `predicted_iq`, `posterior`.

Публічні форми для одного променя відповідають single-beam API `paper_recursion.py`: state та `k_tilde`/`mu0` — `(1,2)`; `observed_iq` — `(2,)`; `predicted_iq` — `(M,2)`; `posterior` — `(M,)`. Adapter додає leading beam axis до одно-променевих observations, predictions і posterior та передає ядру узгоджені batch форми `(1,2)`, `(1,M,2)`, `(1,M)`. Це дозволяє ядру використати його фактичну багатопроменеву гілку для `L=1`, без зміни API.

`time_index` має збігатися з `state.time_index`; caller явно передає `next_time_index`, який мусить дорівнювати `time_index+1`. Новий snapshot зберігає ядрові виходи `new_fluctuating` як `fluctuating_iq`, `full_estimate` як `full_iq`, а міткою часу — `next_time_index`. Старий immutable snapshot не змінюється. Adapter перевіряє часові мітки й очікувані форми; валідацію posterior, скінченності та обчислення виконує `paper_recursion.py`. `observed_iq` приймається лише як явно переданий operand: він не отримується з channel output або truth.

## M4.7j/B3c-0 послідовний запуск (`L=1`)

`receiver/reconstruction_estimator_sequence.py::run_reconstruction_estimator_sequence()` приймає явний `initial_state` і послідовність `ReconstructionEstimatorStepOperands`. Кожен елемент несе `time_index`, `next_time_index`, `alpha_prime`, `k_tilde`, `mu0`, `observed_iq`, `predicted_iq`, `posterior`; жоден операнд не має числового default. Runner не виводить operands з інших даних і кожен крок передає до `advance_reconstruction_estimator_state()`.

Для кожного елемента `time_index` мусить дорівнювати мітці поточного state, а `next_time_index` — бути рівно `time_index+1`. Тому пропуск, повторення чи перестановка абсолютних індексів відхиляються кроковим адаптером. Наступна рекурсія читає тільки попередній `fluctuating_iq`; `full_iq` кожного кроку — нова флуктуюча оцінка плюс саме той `mu0`, який переданий цьому кроку. `mu0` може змінюватися між кроками, не змінюючи попередню fluctuating estimate.

Результат завжди містить `final_state`. При `include_history=True`, `history` — immutable tuple з початкового state і всіх наступних state, кожен із власним абсолютним `time_index`; без запиту `history=None`. Самі state arrays immutable. Порожня послідовність повертає переданий початковий state. Окремий повторний запуск від цього самого immutable initial state починається без перенесення проміжного стану. Послідовність зберігає лише оцінки й часові мітки, не `ChannelTruth`.

Це **explicit-operand sequential reconstruction estimator, NOT complete paper-exact estimator**. Runner лишається ізольованим і не підключається до `reconstruction_forward.py`, CLI, pipeline чи decoder.

## Компоненти оцінки

- **Регулярний компонент `mu0`:** явний `(L,2)` параметр ADR-007. Не є окремим динамічним полем state.
- **Флуктуючий компонент:** збережена оцінка `fluctuating_iq`; ядро згасає попереднє значення через scalar `alpha_prime` та додає `k_tilde`-зважену posterior innovation.
- **Повна оцінка:** `full_iq`. Вихід кожного recursion step дорівнює новій флуктуючій оцінці плюс переданий `mu0`. Початкова повна оцінка конфігурується окремо; код не вимагає, щоб початкові `full_iq` і `fluctuating_iq + mu0` вже збігалися.

Контракт зберігає алгебру наявного `paper_recursion.py`; жодна формула або параметр [A](1) не змінюється.

## Ініціалізація, індекси та reset

`estimator.initial_estimates.fluctuating_iq`, `estimator.initial_estimates.full_iq`, `estimator.initial_time_index` і `estimator.time_rule` є обов'язковими явними config values. `time_rule` має значення `one_recursion_step_i_to_i_plus_1`. Початковий state створюється з двох масивів та індексу. Початковий індекс може бути будь-яким явним integer; автоматичний нульовий старт заборонений.

Усі snapshots мають однакову абсолютну вісь індексів: стан із міткою `i` відповідає оцінкам на `i`; один algebraic update має перейти тільки до `i+1`. Повторне використання індексу, пропуск кроку або прив'язка до sample/symbol координати не виводиться з контейнера. Потрібна часова конвенція задається зовнішнім caller/config і зберігається в provenance.

Reset створює новий state з явних початкових оцінок і `initial_time_index`. Стан попереднього запуску не переноситься і не мутується. Зміна input arrays після створення state не змінює snapshot. Контейнер не використовує RNG, channel generator, `ChannelTruth` чи `.truth`.

## Параметри та provenance

ADR-007 вимагає явних `alpha_prime`, `k_tilde`, `mu0`, початкових оцінок та часової конвенції. Числа не задані статтею [A] і не підтягуються автоматично з [B]/[C]. Кожне значення в конфігурації має provenance `status`, `source`, `note`, включно з `initial_time_index` та `time_rule`. Config є значенням джерела істини для запуску; майбутній result record мусить серіалізувати фактично використані значення, provenance, часову конвенцію й оцінки з їх абсолютним індексом.

B3a не додає result writer і не активує config-driven receiver. Поточна strict schema залишається неактивною: `receiver_enabled:false`, `paper_exact:false`. `source_faithful` відхиляє реконструктивні поля.

## Зв'язок із `reconstruction_forward.py`

`predict_reconstructed_aggregate_iq()` наразі приймає caller-supplied `estimated_path_coefficients` форми `(L,2)` і тримає одну пару коефіцієнтів на промінь сталими протягом усього кадру. B3b-0/B3c-0 не підключають state до цієї функції і не змінюють цю кадрову конвенцію. Для `L=1` M4.7k додає лише буквальне копіювання `full_iq` у форму її коефіцієнтів; чи є ці величини фізично тотожними path coefficients із [A](6), який snapshot стосується кадру та чи переходити до часово-змінних коефіцієнтів — окремі питання.

M4.7k додає лише ізольований `snapshot_full_iq_for_forward()` для `L=1`: копіює `full_iq` і переносить його `estimator_time_index`, не встановлюючи часову відповідність кадру. Повний контракт aggregate I/Q, відмінних clocks, causal cutoff і блокерів observation extraction наведено в `docs/M4_B3_SINGLE_PATH_INTEGRATION_CONTRACT.md`.

## M4.7n/B3c-4 — accepted ADR-012 causal symbol step

За явним рішенням користувача від 2026-10-28 ADR-012 прийнято вузько: `reconstructed_offline`, `L=1`, real-channel experiment, zero delay, rectangular ZOH 8 samples/symbol, per-sample `(-Im(received[n]), Re(received[n]))` та arithmetic mean рівно восьми samples. Це реконструктивна домовленість, не спостережний алгоритм, підтверджений [A].

`ReconstructionEstimatorState.time_index=i` мітить стан до спостереження; adapter вимагає, щоб caller явно подав його пару `(i, absolute symbol_index=f)`. Він не припускає `i=f` і не конвертує origins. Абсолютні sample labels символу перевіряються як `O+8f…O+8f+7`, де `O` явно передається. Після восьмого sample рівно один step `i→i+1` делегується `advance_reconstruction_estimator_state`; snapshot копіює лише `next_state.full_iq`, мітиться `i+1` і доступний не раніше символу `f+1`. Наступний caller pair має бути `(i+1,f+1)`.

`advance_real_one_path_symbol()` приймає `posterior`, `predicted_iq`, `alpha_prime`, `k_tilde` та `mu0` лише явно; caller також передає absolute sample cutoffs для posterior/prediction inputs, що мають бути не пізніше останнього sample поточного symbol. Це provenance labels, а не автоматичний аудит походження масивів. Adapter не створює posterior/predictions, не читає truth і не під'єднаний до `reconstruction_forward.py`, pipeline чи CLI. Forward pair лишається сталою на кадр. Середнє восьми samples не проголошується незалежним AWGN observation; covariance і temporal correlation лишаються відкритими.

Результат — **causal one-path explicit-posterior reconstruction step, NOT complete paper-exact receiver**. `paper_exact:false`, `receiver_enabled:false`; SCI-METRIC-02 і `paper_metric.py` не змінено.

## Чого бракує для B3b

Наявна observation boundary дозволяє лише aggregate received I/Q; вона не надає виміряне `observed_iq: (L,2)` окремо для кожного променя. Для B3b потрібні:

1. окреме рішення щодо per-path operands із aggregate `Y`, зокрема прийняття/відхилення запропонованого ADR-011 pseudo-observation і точні правила її формування;
2. noise reuse/correlation semantics для похибки aggregate cancellation та допустимий source/profile шуму;
3. правила відповідності `observed_iq`, `predicted_iq` форми `(L,M,2)` і posterior `(L,M)` кожному променю й абсолютному кроку `i`;
4. визначення, хто формує per-path posterior і predictions, із яким `M` та candidate indexing. ADR-003/004/005 тепер задають лише ізольовану локальну project policy для 16 edge hypotheses; вони не створюють per-path operands або author `θ` mapping;
5. часовий зв'язок coefficient estimates з кадрами B2b-2, затримками і reset-ами, не виводячи його з `ChannelTruth`.

Тому B3a state container і B3b-0 adapter **не є повним estimator** і не роблять B3b готовим автоматично навіть для одного променя. Adapter приймає `observed_iq`, posterior та predictions лише як явні operands; наукове походження per-path operand, posterior/predictions, noise handling і time alignment усе одно потребують окремих рішень. Aggregate observation не можна автоматично ототожнювати з окремим per-path operand, а жоден blocker не вирішується зміною конфігурації або контейнера.

## B4d sequence handoff

The sequence runner treats `ReconstructionEstimatorState.fluctuating_iq` and `full_iq` exactly as B4c does: the state before symbol `f` is frozen; B4c predictions use its `full_iq`; the [A](1) recursion consumes its `fluctuating_iq`; and the returned next state contains the next fluctuating/full pair at estimator tick `i+1`. The runner hands that exact state and B4c's posterior for `f` to the step for `f+1`. It never restarts from `mu0` or substitutes the full estimate for the fluctuating estimate.

A new independent sequence requires the ADR-004 initial edge prior once. A continuation requires the previous completed symbol's posterior and the already advanced state, with previous symbol/tick labels proving adjacency; it always begins in later-edge mode. History, when requested, is an immutable tuple of per-symbol B4c results and labels, and contains no received truth or generator state.
