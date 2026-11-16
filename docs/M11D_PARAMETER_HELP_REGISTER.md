# M11d parameter help and provenance register

The registry retains 459 entries: Core 125, Runtime 258, Technical 76. The 27 selected-symbol trace entries are a separate runtime overlay, not additional registry records. On each active receiver, Inspector values are read from the configuration or the current actual F=32 trace; unavailable pre-run values are labeled unavailable rather than replaced with zero.

| Help identifier / field | Display / symbol | Value source and units | Fidelity |
|---|---|---|---|
| `runtime.F` | Кількість символів / F | trace input symbol count; symbols | PROJECT_RECONSTRUCTION |
| `runtime.samples_per_symbol` | Відліків на символ / N_s | trace config; samples/symbol | PROJECT_RECONSTRUCTION |
| `runtime.channel_gain` | Коефіцієнт каналу / a | shared fixture config; dimensionless | PROJECT_RECONSTRUCTION |
| `runtime.candidate_metrics` | Метрика кандидата / F_h | current symbol and edge trace; implementation units | SOURCE_UNRESOLVED for [A](2) square ambiguity |
| `runtime.posterior_weights` | Вага гіпотези / p_h | current receiver trace; normalized weight | PROJECT_RECONSTRUCTION (ADR-005) |
| `runtime.alpha_prime` | Коефіцієнт згасання / α′ | selected receiver config; dimensionless | SOURCE_PARTIAL equation role, project value |
| `runtime.K_tilde` | Коефіцієнт корекції / K̃ | selected receiver config; I/Q coefficients | SOURCE_PARTIAL equation role, project value |
| `runtime.mu0` | Опорний вектор / μ₀ | selected receiver config; I/Q units | PROJECT_RECONSTRUCTION |
| `runtime.innovation` | Інновація / ε[f] | selected symbol receiver trace; I/Q units | SOURCE_PARTIAL; project semantics |
| `runtime.estimator_pre_state` | Стан до update / s[f] | selected receiver trace; I/Q units | PROJECT_RECONSTRUCTION clock convention |
| `runtime.estimator_post_state` | Стан після update / s[f+1] | selected receiver trace; I/Q units | PROJECT_RECONSTRUCTION clock convention |
| `historical.M9b.delta_ber_ci` | ΔBER та 95% CI | archived M9b artifact; BER difference | Archived evidence, interval contains zero |
| `historical.M10b.primary_delta_ber_ci` | ΔBER та 95% CI | archived M10b artifact; BER difference | Archived evidence, interval contains zero |
| Phase increment | Крок фази / Δφ | article p.5: π/4 | SOURCE_EXACT_VERIFIED for increment only |
| Absolute phase | Абсолютний зсув / φ₀ | Project phase convention/ADR-002; no article-confirmed value | PROJECT_RECONSTRUCTION |

### Additional selected-symbol live fields

| Help identifier | Meaning/source | Fidelity |
|---|---|---|
| `runtime.encoder_state_before` | Actual encoder state before selected symbol | PROJECT_RECONSTRUCTION |
| `runtime.observed_iq` | Actual selected-symbol aggregate observation, ADR-012 convention | PROJECT_RECONSTRUCTION |
| `runtime.candidate_predictions` | Actual 16 predicted I/Q values for selected symbol | SOURCE_PARTIAL for [A](5), project mapping |
| `runtime.estimator_pre_state` / `runtime.estimator_post_state` | Actual causal pre/post trace states | PROJECT_RECONSTRUCTION clock convention |
| `runtime.innovation` | Actual project weighted-residual value; source semantics unresolved | SOURCE_PARTIAL |
| `runtime.viterbi_decision` | Actual selected traceback edge/state | PROJECT_RECONSTRUCTION |
| `runtime.reference_error_flags` | Actual comparison against this fixture's known reference bits | Evaluation-only fixture |

### Noise and phase help details

- The help card for `profile.sigma_squared` or `noise.sigma_squared` displays only the exact archived M9b/M10b configuration value and its config provenance. It says that the deterministic F=32 fixture does not define a variance.
- `profile.gamma_b_eff_db` and `noise.nominal_reference_gamma_b_eff_db` similarly identify the archived evaluation configuration. They are not presented as F=32 runtime channel parameters.
- The simulation summary and selected-symbol view expose `source.phase_increment` as `Δφ=π/4`, with a `?` card labeled `SOURCE_EXACT_VERIFIED` for that increment only. The explanation explicitly separates it from reconstructed absolute `φ₀`.

Every scientific help card includes a Ukrainian label, symbol, exact JSON value, unit, plain explanation, equation/use, effect, cited source and fidelity status. Technical metadata is labeled as metadata, without invented physical meaning. Controls are read-only; no range is shown unless the repository defines one. `?` works by mouse and keyboard; Escape and close return focus to the exact trigger. The formula card shows formula, actual trace operands and computed trace result. See the source matrix in `M11D_SOURCE_FIDELITY_AUDIT.md`.
