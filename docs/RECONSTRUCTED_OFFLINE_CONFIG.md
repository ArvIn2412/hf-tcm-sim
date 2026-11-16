# Конфігураційна схема `reconstructed_offline` (M4.7c/B0)

Це лише строгий формат запису проєктної реконструкції. `profile: reconstructed_offline` **ніколи не означає paper-exact**. Поточна схема вимагає `paper_exact: false` і `receiver_enabled: false`; вона не запускає receiver, likelihood, estimator чи search.

Loader/validator: `hf_tcm.reconstruction_config.load_reconstructed_offline_config()` та `validate_reconstructed_offline_config()`. Це окремо від M0 `load_scaffold_config()` і не підключено до CLI чи pipeline. Відсутні поля, невідомі ключі, невірні форми та невалідні числа викликають `ReconstructionConfigError`; схема нічого не домислює.

## Обов'язкові поля

| JSON path | Тип/форма | Перевірка |
|---|---|---|
| `schema_version` | integer | Рівно `1`. |
| `profile` | string | Рівно `reconstructed_offline`. |
| `paper_exact` | boolean | Має бути `false`. |
| `receiver_enabled` | boolean | Має бути `false`, оскільки receiver ще не інтегрований. |
| `candidate_index_space` | string | Явно `m4_1_hypothesis_id`; це локальний простір проєкту, не author `θ`. |
| `candidate_count` | integer | Явно `16`, звіряється з M4.1. Цим не стверджується авторське значення `M`. |
| `labeling.name`, `labeling.origin` | непорожні strings | Назва та походження задаються викликом конфігурації. |
| `labeling.bit_order` | permutation `c2,c1,c0` | Порядок підписує 8 значень `output_to_b`; жодне відображення не задається за замовчуванням. |
| `labeling.output_to_b` | 8 integer values | Перестановка `0…7` в явному порядку `bit_order`. Перевірка не приймає це за labeling статті. |
| `labeling.phase_offset_rad` | finite real | Значення передається явно. |
| `transition_model.name` | exact string | ADR-003 вимагає `adr003_uniform_allowed_edges`. |
| `transition_model.probabilities` | `(16,16)` finite real matrix | У канонічному порядку `HYPOTHESES`: `P(k|h)=1/d(h)` на структурно дозволених ребрах, 0 на інших. `d(h)` валідується з фактичної маски; validator перевіряє uniform support і row stochasticity. Це probability matrix, окрема від 0/1 adjacency. |
| `initial.state` | `[0,0]` | ADR-004 фіксує початковий encoder state. Інші стани відхиляються. |
| `initial.prior` | `(16,)` finite real | ADR-004: `1/4` лише на edge hypotheses із `current_state=(0,0)`, 0 на решті; перевіряється за канонічним порядком гіпотез, не за `hypothesis_id` семантикою чи `next_state`. |
| `likelihood.kind` | exact string | ADR-005 вимагає `exp_negative_beta_project_reconstruction_metric`; це project pseudo-likelihood від aggregate `F_rx`, не `[A](2)` і не `[B](7)`. |
| `likelihood.beta` | finite real `>0` | Обов'язкове явне значення; жодної шкали/variance не підставлено. |
| `estimator.alpha_prime` | finite real | Явно переданий коефіцієнт; validator не виводить його з джерел. |
| `estimator.k_tilde`, `estimator.mu0` | `(L,2)` finite real | `L` має дорівнювати явному `timebase.path_count`. Коефіцієнти не задаються схемою. |
| `estimator.initial_estimates.fluctuating_iq`, `.full_iq` | кожна `(L,2)` finite real | Обидві початкові оцінки мають бути явними; схема не обчислює одну з іншої. |
| `estimator.initial_time_index` | integer | Обов'язковий абсолютний індекс дискретного стану оцінювача; жоден початковий індекс не підставляється. Це не sample index і validator не конвертує його у фізичний час. |
| `estimator.time_rule` | string | Явно дорівнює `one_recursion_step_i_to_i_plus_1`; validator не приймає іншу cadence. Перетворення recursion index у sample/symbol time не задається цим полем. |
| `timebase.name` | непорожній string | Ім'я конкретної часової конвенції. |
| `timebase.path_count` | positive integer | Явне `L`, мусить збігтися з кількістю затримок. |
| `timebase.samples_per_symbol` | positive integer | Явно задана дискретизація. |
| `timebase.sample_rate_hz`, `symbol_rate_hz` | finite positive reals | Обидва обов'язкові; перевіряється рівність `sample_rate_hz = samples_per_symbol × symbol_rate_hz`. |
| `timebase.symbol_origin_sample` | integer | Явний початок symbol/sample координат. |
| `timebase.path_delays_samples` | `L` nonnegative integers | Затримки у відліках, без автоматичного перерахунку фізичних `τ_l`. |
| `observation_model.kind` | string | Дозволено `aggregate_received_iq` або вузький `adr012_l1_real_mean8`. ADR-012 kind вимагає явних `iq_rule="(-Im(received), Re(received))"`, `sample_reduction="arithmetic_mean_exactly_8"`, `waveform_rule="rectangular_zoh"`, а також `path_count=1`, delay `[0]`, 8 samples/symbol. Профіль лишається неактивним. |
| `observation_model.prediction_combination` | непорожній string | Явна назва проєктного правила складання прогнозу; алгоритм не реалізується. |
| `search.beam_width` | positive integer | Явне значення; не активує beam search. |
| `search.decision_lag_symbols` | nonnegative integer | Явне значення; не встановлює авторську межу рішення. |
| `assumption_provenance` | exact map з ключами нижче | Для кожного незалежного припущення потрібні явні `status`, `source`, `note`, кожне — непорожній рядок. |

`assumption_provenance` має окремий запис для: `candidate_index_space`, `candidate_count`, `labeling`, `transition_model`, `initial_state`, `initial_prior`, `likelihood_type`, `beta`, `alpha_prime`, `k_tilde`, `mu0`, `initial_estimates`, `estimator_time_index`, `estimator_time_rule`, `timebase`, `path_count`, `samples_per_symbol`, `sample_rate_hz`, `symbol_rate_hz`, `symbol_origin_sample`, `path_delays_samples`, `aggregate_observation_model`, `prediction_combination`, `beam_width`, `decision_lag_symbols`. Для ADR-003/004/005 provenance фіксує accepted decision 2026-10-28 і runtime parameter values (`beta`, metrics provenance); для ADR-012 запис `aggregate_observation_model` фіксує прийняте правило. Для кожного запису обов'язкові непорожні `status`, `source`, `note`. Додаткові або пропущені ключі відхиляються. Статус provenance є описом; validator не активує receiver.

## Режими та межі

`validate_receiver_profile_mode(config, requested_mode="source_faithful")` відхиляє `reconstructed_offline` profile та будь-які його reconstruction-specific fields. Для `requested_mode="reconstructed_offline"` функція перевіряє лише сумісність профілю; повна валідація виконується окремо. Обидві функції лише перевіряють configuration, не dispatch-ать і не запускають receiver.

Профіль не містить поля для `ChannelTruth`, channel generator state або фізичних per-path вимірів. Прийняті ADR-003/004/005 фіксують лише project transition/prior/pseudo-likelihood policy; це не математичне підтвердження [A]/[B] і не закриває SCI-02/SCI-03. ADR-012 accepted окремим рішенням 2026-10-28 тільки для точного L=1 real-channel bridge нижче; ADR-009/011 залишаються proposed.

## M4.7h/B3a: межа estimator state

Початковий snapshot може бути явно створений як `ReconstructionEstimatorState(fluctuating_iq, full_iq, time_index)`. Обидві оцінки мають форму `(L,2)` і зберігаються як незалежні immutable snapshots; `time_index` є абсолютною integer міткою кроку рекурсії. `paper_recursion.update_quadrature_estimates()` приймає попередню fluctuating оцінку на `i`, а повертає `(new_fluctuating, full_estimate)` тієї ж форми для наступного кроку `i+1`; контейнер не викликає це ядро й не виводить оцінку із параметрів.

`alpha_prime`, `k_tilde`, `mu0`, дві початкові оцінки та початковий індекс є явними обов'язковими config values з provenance. `estimator.time_rule` фіксує один recursion step `i→i+1`. Часова відповідність між рекурсійними індексами та sample/symbol координатами залишається окремою явною реконструктивною конвенцією. Майбутні result records мають зберігати значення параметрів/provenance і оцінки з `time_index`; ця схема лише валідовує конфігурацію, не генерує результат і не активує оцінювач. `receiver_enabled:false`, `paper_exact:false`; source-faithful режим відхиляє reconstruction settings.

Для M4.7d/B1 схема може зберегти явне маркування `labeling.name: "assumed_natural_binary"`, `bit_order: ["c2", "c1", "c0"]` і `output_to_b: [0,1,2,3,4,5,6,7]`. Ці config values самі по собі не активують adapter або receiver. ADR-002 прийнятий окремим user decision 2026-10-26 саме як проєктне припущення, не як авторський mapping. Profile лишається `paper_exact: false` та `receiver_enabled: false`.

M4.7e/B2a додає лише незалежну арифметику aggregate prediction та `project_reconstruction_metric` для явних, уже вирівняних receiver-side arrays. Цей API не є полем, що запускається конфігурацією: profile лишається вимкненим, а forward model, timebase, delays і coefficient prediction не визначені ним.

M4.7f/B2b-1 додає ізольований operator, якому caller явно передає per-path sample segments, nonnegative absolute sample starts, integer delays, output frame start/count та `edge_policy="zero_padding"`. ADR-008 прийнятий як проєктне рішення про `approximate_rectangular_8sps`, integer sample delays, явні межі кадру та `zero_padding`; B0 loader поки не має окремих полів frame start/count чи edge policy і не викликає operator. Фізичне `τ_l` автоматично не конвертується в samples.

Після прийняття ADR-002/006/008/010 gate відкритий для ізольованого B2b-2 project forward prediction із цими правилами, якщо всі потрібні values передаються явно. Це не активує конфігураційний receiver і не закриває B3/B4.

M4.7g/B2b-2 реалізує лише окрему функцію `predict_reconstructed_aggregate_iq`. Вона вимагає явно передані candidate output bits, labeling/bit-order, `timebase_profile="approximate_rectangular_8sps"`, правило `rectangular_zero_order_hold_8_samples_per_symbol`, symbol origin, frame start/count, integer sample delays, `edge_policy="zero_padding"` та receiver-side estimated coefficients `(L,2)`. Коефіцієнти — одна `(μ₁,μ₂)` пара на промінь, стала в межах усього кадру. B0 schema/loader не змінено і не викликає функцію; schema не стала запускним API та не отримала прихованих defaults. `receiver_enabled:false`, `paper_exact:false`, а source-faithful mode продовжує відхиляти reconstruction settings. Результат — project reconstruction baseband prediction, не авторська повна waveform-модель.

M4.7h/B3a додає лише типізований snapshot state; він не підключений до B2b-2. `reconstruction_forward.py` надалі вимагає caller-supplied `(L,2)` коефіцієнти, сталі протягом кадру. Жодне автоматичне оновлення стану в межах кадру не задане.

## ADR-012 configuration contract (inactive)

Для вузького observed-IQ bridge config може явно зберегти `observation_model.kind="adr012_l1_real_mean8"`, `iq_rule="(-Im(received), Re(received))"`, `sample_reduction="arithmetic_mean_exactly_8"` і `waveform_rule="rectangular_zoh"`. Validator перевіряє разом із `timebase.path_count=1`, `path_delays_samples=[0]` і `samples_per_symbol=8`. `timebase.symbol_origin_sample` задає `O`; кожний виклик adapter окремо передає `target_symbol_index=f`, absolute sample labels, buffer origin і pre-observation `time_index=i`. Validator не виводить ні `i` з `f`, ні часовий origin.

Статичний real `h=a` — тестове/дослідницьке обмеження, не параметр observed-IQ adapter. No noise variance чи independent-AWGN claim не додаються. Posterior та predictions усе ще мають бути caller-provided; `receiver_enabled:false`, `paper_exact:false` зберігаються. Ця конфігурація фіксує припущення й не запускає step.

Тестові fixture values у `tests/test_reconstruction_config.py` синтетичні й слугують лише перевірці форм/валідації; їх не можна копіювати як дослідницьку preset-конфігурацію.
