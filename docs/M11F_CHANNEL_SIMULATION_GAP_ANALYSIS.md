# M11f — аналіз готовності моделі каналу

**Рішення:** ізольовані channel-функції можна буде компонувати у sandbox після окремого наукового рішення й receiver contracts. У M11f до поточного шляху сигналу нічого з них не підключено.

| Параметр / модуль | Джерело в коді та фактична можливість | Поточне значення / редагування в Demo Studio | Чи потребує нової моделі | Науковий статус |
|---|---|---|---|---|
| Інформаційні біти | M11a `bits` input; preset визначає фіксовані послідовності | Приклад F=32 та інші наявні presets; arbitrary input не реалізований у M11f | Ні для ручного вводу, але UI/backend validation потрібні | Deterministic demonstration input |
| Кодер / trellis | `coding/encoder.py`, `coding/trellis.py` | A: 4 стани, 16 переходів; не перемикається на Code 2 | Так для B receiver; окремий модуль і сумісний decoder потрібні | A reconstructed project mapping; B source variant окремий |
| Початковий стан кодера | `INITIAL_STATE=(0,0)`; receiver state contracts | Фіксований для поточного сценарію, read-only | Так, лише після узгодження decoder termination/start policy | Source mapping incompletely established |
| `alpha_prime` (`α′`) | Anchored policy у `configs/m9b_evaluation_approved_run.json`; API `DemoRequest` | Anchored preset default `0.85`; editable для non-defense custom deterministic run; frozen B `1.0` read-only | Ні, існуюча recursion підтримує параметр | Project reconstruction; не авторське числове значення |
| `k_tilde` (`K̃I,K̃Q`) | Та сама policy config та API | Anchored default `(0.0875, -0.05)`; editable для non-defense custom run; frozen B `(0,0)` read-only | Ні для наявного recursion API | Project reconstruction; не авторська calibration |
| `beta` (`β`) | Та сама policy config; `reconstruction_likelihood` | Default `0.7`; editable для anchored custom run; receiver validates `β>0` | Ні для наявної pseudo-likelihood API | ADR-005 project pseudo-likelihood; SCI-03 remains OPEN |
| `mu0` (`μ₀`) та initial estimator state | Policy config і per-policy trace; sequence runner | Anchored `μ₀=(0.42,0.91)`, frozen B `(0,0)`; read-only | Ні для simulation API, але не exposed as Studio input | Project anchor/state convention, not author-confirmed; SCI-03 OPEN |
| Noise fixture selector | `evaluation/m11a_demo_studio.py::NOISE_FIXTURES` | `low_amplitude_a` за замовчуванням; deterministic preset options, selectable only in editable demo mode | Ні для fixture switching; physical stochastic noise still requires separate channel model | Deterministic demonstration fixture; not AWGN/SNR |
| Samples per symbol | M11a trace contract / rectangular ZOH | 8; не редагується | Так, downstream windows/metrics/decode cadence залежать від нього | Article-v7 trace convention; відповідна методика розділу 4 використовує 4 samples/symbol окремо |
| Frame length `F` | Demo API limits/presets and trace dimensions | F=32 у deterministic defense fixture; presets choose supported sizes | Ні для presets; довільний frame UI потребує API validation | Demonstration frame, not experiment sample |
| Channel gain `a` | M11a fixture config, `trace.input.channel_gain` | `0.75`, read-only in fixture | Ні для multiplication, але receiver assumptions/metrics need reevaluation for other gain conditions | Fixed deterministic fixture only |
| Noise fixture | M11a deterministic fixture (`noise_fixture`, `noise_formula`) | Preset selectable only where current UI allows; no random sampling | Ні для fixture selection; no SNR semantics inferred | Deterministic demonstration perturbation |
| AWGN / SNR (`Eb/N0`) | `channels/awgn.py` | Not wired into Studio | Так: must define signal energy and sample/symbol conversion and rerun receiver contract | Existing isolated stochastic module, no current GUI evidence |
| Multipath count, delays, powers | `channels/multipath.py::MultipathConfig`, `PathSpec` | Not wired; not editable | Так: ADR-012 currently requires a one-path zero-delay observation contract | Explicit configurable forward model, unintegrated |
| Rician K and LOS phase | `channels/rician.py`, path specs | Not wired; not editable | Так: select coefficient timing, scaling, and receiver state treatment | Existing static / approximate AR(1) coefficient generator |
| Correlation | `rician.py` approximate diffuse AR(1); `multipath.py` config | Not wired; not editable | Так: choose correlation process and distinguish from article fading semantics | Approximation explicitly labeled; not author-exact |
| Fluctuating noise process | `channels/fluctuating_noise.py` | Not wired; not editable | Yes for full signal/channel assembly | Article equations (9)–(10) quadrature process only; initial state is project choice |
| `N` / sample count | Derived as `8F` for current ZOH frame | For F=32: 256; read-only derived value | Yes if samples/symbol changes | Actual trace dimension |
| `η` / Viterbi depth | Article v7 p.6 states η=20; Chapter 4 p.129 describes depth 20 information packets | Current decoder processes the full frame; depth is not editable | Yes: needs an actual finite-depth streaming/truncation decoder, not a viewport option | Unresolved interpretation/implementation gap |
| Candidate metric and posterior | `receiver/reconstruction_candidate_metrics.py`, reconstruction posterior sequence | Frozen trace is shown; Studio does not alter these values | No UI-only change; math change needs accepted ADR and tests | Squared residual is project interpretation; SCI-METRIC-02 OPEN; posterior is not channel HMM posterior |

## Окремий дизайн: Channel Simulation Sandbox

Поточну Studio не розширювати декоративними slider-ами. Sandbox слід оформити як ізольований профіль експерименту, який не записує результати в M5–M10 і не підміняє історичні fixture.

1. **Конфігурація й provenance.** Окремий immutable config з моделлю, RNG seed, profile ID, sample rate convention, energy normalization та source status. На екрані показувати кожний вибір і його одиниці.
2. **Forward chain.** Передаваний `x[n]` → обрані `h_l[n]` та integer delays → received signal → окремий AWGN stage. `ChannelTruth` зберігати окремо від observation. Не передавати truth у estimator/decoder.
3. **Noise/SNR.** Явно обрати `Eb/N0` або sample-noise variance і перетворення між ними; визначити `Es`, bits/symbol та чи масштабуються 8 повторених ZOH-відліків. Не змішувати це з наявним deterministic noise fixture.
4. **Multipath/Rician.** Явні path count, delays (samples або symbols із точним перерахунком), average power, K, LOS phase та fading mode (`static` чи approximate AR(1)). Показувати збільшення довжини через zero-padded delayed tail.
5. **Correlation.** На першому етапі лише названий approximate AR(1) параметр і графік коефіцієнтів. Не маркувати його як статейний Markov process без окремого algebra/source audit.
6. **Receiver compatibility gate.** До запуску decoder відхиляти профіль, якщо порушений його observation contract; multipath чи нове sample cadence не можна мовчки агрегувати старим ADR-012 adapter-ом.
7. **Viterbi depth.** Окремий план streaming/traceback decoder, reference fixtures та depth semantics. Поки це не створено, UI мусить називати наявний результат `full-frame conditional Viterbi`.
8. **Ізоляція й валідація.** Нові результати зберігати в новому namespace з конфігураційними/seed hashes; тестувати forward module, truth boundary та receiver contract окремо. Жодного нового статистичного дослідження без узгодженого дизайну.

## Передумови до реалізації sandbox

- Рішення щодо того, як інтерпретувати канал статті й розділу 4, без злиття різних джерельних варіантів.
- Узгоджені фізичні/нормалізаційні одиниці для Eb/N0, Es і oversampling.
- Receiver, що коректно працює з часово-змінним багатопроменевим observation, або чітке обмеження sandbox лише forward-model без decoder.
- Явна межа `ChannelTruth`, causal доступу та генератора випадкових чисел.
- Test plan та окремий дозвіл на stochastic evaluation до будь-яких performance claims.

