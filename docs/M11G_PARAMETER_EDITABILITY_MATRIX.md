# M11g — матриця параметрів і Channel Simulation Sandbox

## Поточний інтерфейс

| PARAMETER | SOURCE | CURRENT VALUE / RANGE | CURRENTLY EDITABLE | REQUIRES NEW MODEL | SCIENTIFIC STATUS |
|---|---|---|---|---|---|
| Information bits | `DemoRequest.bits`, `/api/demo`; client validator | A: 2–64 even bits; B: 2–256 even bits | Так | Ні для поточних меж | Explicit deterministic input |
| Encoder | A `coding/encoder.py`; B `coding/encoder_b.py` | A 4/16; B 16/64 | Так, B лише preview | Так для B receiver | A project reconstruction; B source-derived encoder only |
| Initial state | A canonical receiver contract; B source table Y | A=00; B state ID 0–15, default 0 | A ні; B preview так | Так для A arbitrary start/decoder termination | B custom start is preview convention; source reset zero |
| Receiver policy | `DemoRequest.receiver_mode` | compare / frozen / anchored | A так | Ні | Existing reconstructed policies; not paper-exact |
| `alpha_prime` | Request/config and recursion implementation | Existing default/policy values | Так у custom A run | Ні для current API | Project reconstruction |
| `K_tilde` I/Q | Request/config and recursion implementation | Existing default/policy values | Так у custom A run | Ні для current API | Project reconstruction |
| `beta` | Request/config and pseudo-likelihood | `beta > 0` | Так у custom A run | Ні для current API | ADR-005 reconstruction; SCI-03 open |
| `mu0` and initial estimator state | Anchored/frozen policy configuration | Anchored `mu0=(0.42,0.91)`, frozen `(0,0)`; policy-defined | Ні | Yes for user-editable estimator initialization and compatible policy contract | Project anchor/state convention; SCI-03 open |
| Deterministic noise fixture | `evaluation/m11a_demo_studio.py` | Listed fixture IDs | Так у supported A request | Ні для fixture selection | Demonstration perturbation; not stochastic AWGN/SNR |
| Channel gain | F=32 fixture trace `trace.input.channel_gain` | 0.75 in verified F=32 preset, read-only | Ні | New evaluation conditions and receiver study for generalization | Fixed demo value only |
| Noise amplitude / SNR / Eb/N0 | `channels/awgn.py` isolated | Not connected to Studio trace | Ні | Yes: normalization, sample conversion, evaluation contract | Not measured by current demo |
| Frame length F | `/api/demo` validation and fixed supported presets | UI A accepts 1–32 TCM symbols (2–64 bits); default F=32 | Through bit sequence | No within API cap; beyond requires API limit change | Demo length only; not experiment sample size |
| Samples per symbol | trace builder rectangular ZOH | 8; derived N=8F | Ні | Yes | Article-v7 trace convention; Chapter 4 method separately uses 4 |
| Viterbi depth η | Article-v7 statement; current conditional decoder | Current decoder is full-frame | Ні | Yes, finite-depth streaming/truncation implementation | Visual window is not decoder depth |
| Multipath count / delays / path gain | `channels/multipath.py::{MultipathConfig,PathSpec}` | Isolated module defaults/config | Ні | Yes: observation, timing and receiver contract | Not wired into Demo Studio |
| Rician K / LOS phase / fading correlation | `channels/rician.py`; approximate AR(1) mode | Isolated API | Ні | Yes: coefficient cadence, normalization, state semantics | Approximate channel module, not author-exact |
| Fluctuating noise correlation/state | `channels/fluctuating_noise.py` | Isolated generator | Ні | Yes: composition and receiver semantics | Not part of M11a trace channel |
| Metric/posterior | production reconstruction modules and immutable trace | Runtime values from selected A trace | Ні | Any mathematical change requires ADR/tests | Squared residual project interpretation; SCI-METRIC-02 open |

## Одиниці, перевірки та ефект зміни

| Parameter | Unit / constraint | Effect of change and help |
|---|---|---|
| Information bits / template / local file | bits; even count; A 2–64, B 2–256; only `0/1` | Changes the encoder input and all dependent outputs. A `?` beside the field explains grouping, limits, and no-padding behavior. |
| Encoder | categorical A or B | Selects actual A demo path or B encoder/trellis-only API. A `?` documents source and receiver availability. |
| Initial state | state ID; A fixed 0, B integer 0–15 | Changes the B preview state trajectory only. B `?` explains register order and that it does not enable receiver. |
| Receiver policy | categorical compare/frozen/anchored | Selects the existing A policy on a shared received buffer. No effect on B, where it is disabled. Existing Inspector `?` uses the parameter registry. |
| `alpha_prime`, `K_tilde` I/Q, `beta` | dimensionless project coefficients; API validates finite values and `beta > 0` | Affect only the existing custom A reconstruction. Their `?` buttons point to the parameter Inspector and source-status note. |
| `mu0` and initial estimator state | normalized I/Q coordinates; currently fixed by policy | Set the full-state anchor and initial trajectory under existing reconstructed policy; no UI override is exposed. |
| Noise fixture | named deterministic fixture; not an SNR unit | Selects the fixed perturbation vector. Its `?` states this is neither stochastic AWGN nor an SNR setting. |
| Gain / noise amplitude / SNR | gain is dimensionless; SNR would require dB and explicit normalization | Fixed/read-only today. No control implies these modules are not connected to the demo trace. |
| Frame length / samples per symbol | F in symbols; N in samples; current relation N=8F | F is derived from validated bit count; N is derived. Samples/symbol remains fixed at 8 in this trace path. |
| Viterbi depth | symbols/steps, source notation `η` | Current decoder uses the whole frame. Changing the viewing window does not change η or decoder behavior. |
| Multipath delays / path count | samples; count | Requires a composed channel forward model plus an observation/decoder contract. No current sliders are offered. |
| Rician K / correlation | K dimensionless; correlation model-dependent | Requires a specified coefficient cadence, normalization, and state semantics before UI editing. |

## Придатність наявних channel modules

`awgn.py`, `multipath.py`, `rician.py` і `fluctuating_noise.py` є окремими компонентами, але не входять до M11a Demo Studio signal path. Наявність модулів не означає інтегрованого receiver. Для multipath треба погодити symbol/sample observation operator; Rician — часовий крок коефіцієнта, масштабування та зв’язок прихованого стану з декодером; AWGN — нормування енергії і перерахунок Eb/N0/SNR для 8 samples/symbol; fluctuating noise — спільний тракт із channel і семантику оцінювача. Новий складний receiver тут не підключений.

## Окремий дизайн Channel Simulation Sandbox

1. Зберігати sandbox config як окремий, версійований experiment profile з hash, RNG namespace/seed, model ID, samples/symbol, energy normalization і source-status.
2. Розділити параметри forward channel (gain, noise/SNR, path count, delays, Rician K/phase, correlation) та decoder (policy, η). Не показувати редаговані поля, доки backend не споживає їх реально.
3. Побудувати й перевірити deterministic channel composition на малих фіксованих vectors; перевірити units, timing, power і independent scalar oracle.
4. Окреме наукове рішення/ADR має визначити спостереження decoder і стан channel estimator; окремі тести мають встановити сумісність із кожним encoder.
5. Лише після цього — окремий явно авторизований evaluation design із train/validation/final separation. Не записувати sandbox outputs у M5–M10.

Поточний GUI не містить декоративних sliders для цих неінтегрованих параметрів.
