# M6f — deterministic two-symbol factorial update ablation

**Result classification:** deterministic factorial ablation of the fixed
reconstructed estimator. This is **NOT** historical M5j root-cause proof, an
optimized receiver, performance evidence, or a paper-exact implementation.
No random generator, Monte Carlo, decoder, BER/SER calculation, or receiver
mathematics change was used. `paper_exact:false` and `receiver_enabled:false`
remain in force.

## 1. Question and fixed four-arm design

The intervention separates the two terms in the implemented update
`s_after = alpha_prime*s_before + K_tilde ⊙ epsilon`:

- **B — frozen:** `alpha_prime=1.0`, `K_tilde=(0,0)`.
- **A — alpha-only:** `alpha_prime=0.85`, `K_tilde=(0,0)`.
- **K — correction-only:** `alpha_prime=1.0`, `K_tilde=(0.35,-0.2)`.
- **C — combined:** `alpha_prime=0.85`, `K_tilde=(0.35,-0.2)`.

A and K name ablation arms only. Coefficients are the fixed historical M5j
policy values; they were not selected or changed in this audit. All arms use
one caller-supplied 16-sample complex buffer, ADR-004 first prior, beta 0.7,
the same zero `mu0`, ADR-002 project labeling, ADR-005 metric, ADR-012
observation convention and B4d sequence API.

Initial state in every arm is `fluctuating_iq=full_iq=(0.42,0.91)`. The main
fixture has sample origin 0, symbol origin 0, first symbol 0, and estimator
tick 0. Its absolute sample labels are 0…15; symbol windows are 0…7 and 8…15.
The two clocks are explicit inputs to B4d and are not inferred from one
another.

## 2. Explicit deterministic two-symbol fixture

No RNG is used. The 16 input samples are the fixed values below; equivalently,
for `n=0,…,15`,
`z[n]=(n−7)/20 + j*((n mod 5)−2)/25`. The two rows are the eight samples
consumed by each symbol. The input hash is
`59663708e2b8c9c7003a605aece3b7fd28d7c0afa42e22c6b0d670e6068d0331`.

| Symbol | Explicit complex received samples |
|---:|---|
| 0 | `-0.35-0.08j`, `-0.30-0.04j`, `-0.25+0.00j`, `-0.20+0.04j`, `-0.15+0.08j`, `-0.10-0.08j`, `-0.05-0.04j`, `0.00+0.00j` |
| 1 | `0.05+0.04j`, `0.10+0.08j`, `0.15-0.08j`, `0.20-0.04j`, `0.25+0.00j`, `0.30+0.04j`, `0.35+0.08j`, `0.40-0.08j` |

ADR-012 converts each complex sample to `(-Im, Re)`. The first-edge prior is
the ADR-004 distribution with probability 1/4 on each of canonical edges
0–3 and zero elsewhere. The actual second-symbol posterior uses the existing
continuation transition and ADR-005 likelihood API.

An additional clock-only control uses the same 16 values with sample origin
13 and estimator tick origin 7. It confirms windows 13–20 and 21–28, prediction
cutoffs 12 and 20, observation cutoffs 20 and 28, and ticks 7 then 8.

## 3. First-symbol shared invariants and independent update oracle

The four B4d sequence calls receive the same immutable sample array, same
initial state and same ADR-004 prior. At symbol 0, all 16 metric entries and
all posterior entries are exactly equal across arms. The independent scalar
innovation oracle is

`epsilon_j = Σ_h p_h (observed_j - predicted_h,j)`.

It gives `epsilon=(-0.012410694762863833,-0.11176378772962557)` for this
fixture. All four arms have this same innovation because their pre-state,
candidate row and posterior agree before their first update. **No invariant
failure occurred.**

Using initial fluctuating state `s=(0.42,0.91)`,

| Component | Independent value |
|---|---:|
| `Delta_alpha=(0.85−1)*s` | `(-0.063,-0.1365)` |
| `Delta_K=(0.35,-0.2) ⊙ epsilon` | `(-0.004343743167002341,0.022352757545925115)` |
| `Delta_total=Delta_alpha+Delta_K` | `(-0.06734374316700234,-0.11414724245407493)` |
| `s_A−s_B` | equals `Delta_alpha` within `1e-12` |
| `s_K−s_B` | equals `Delta_K` within `1e-12` |
| `s_C−s_B` | equals `Delta_total` within `1e-12` |
| `s_C−s_A−s_K+s_B` | `(−5.55e−17,0)`, zero within `1e-12` |

Actual first post-update fluctuating states are B `(0.42,0.91)`, A
`(0.357,0.7735)`, K `(0.4156562568329977,0.9323527575459252)`, and C
`(0.3526562568329976,0.7958527575459251)`. This additive factorial identity
is for a single update with shared operands; it does not imply additive
metrics or posterior, and does not hold as a general closed-loop identity
when subsequent innovations diverge.

## 4. Second symbol and metric contrasts

The sequence API carries each symbol-0 post-state forward as symbol-1's
pre-state. That carried state is the state used to form symbol-1's predictions
and local metrics; the sequence result does not separately persist a second
pre-state object. The independent scalar prediction and metric oracle matches
the B4d row for each arm and all 16 canonical hypotheses.

The exact metric in this path is the ADR-005 reconstructed squared residual
over the eight observed `(I,Q)` samples, with each ZOH candidate prediction
repeated eight times. It is not an assertion about source [A](2). For each
edge, the table gives `F_B,F_A,F_K,F_C`, the three contrasts from B, and the
factorial interaction `F_C−F_A−F_K+F_B`.

| edge | `F_B` | `F_A` | `F_K` | `F_C` | `Delta F_alpha` | `Delta F_K` | `Delta F_C` | interaction |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3.889200 | 2.542218 | 4.138183 | 2.742383 | -1.346982 | 0.248983 | -1.146817 | -0.048818 |
| 1 | 1.918000 | 1.531432 | 1.889308 | 1.507119 | -0.386568 | -0.028692 | -0.410881 | 0.004378 |
| 2 | 10.441200 | 8.111418 | 10.851123 | 8.472523 | -2.329782 | 0.409923 | -1.968677 | -0.048818 |
| 3 | 1.985200 | 1.588552 | 1.955813 | 1.563544 | -0.396648 | -0.029387 | -0.421656 | 0.004378 |
| 4 | 1.918000 | 1.531432 | 1.889308 | 1.507119 | -0.386568 | -0.028692 | -0.410881 | 0.004378 |
| 5 | 3.889200 | 2.542218 | 4.138183 | 2.742383 | -1.346982 | 0.248983 | -1.146817 | -0.048818 |
| 6 | 1.985200 | 1.588552 | 1.955813 | 1.563544 | -0.396648 | -0.029387 | -0.421656 | 0.004378 |
| 7 | 10.441200 | 8.111418 | 10.851123 | 8.472523 | -2.329782 | 0.409923 | -1.968677 | -0.048818 |
| 8 | 2.218159 | 1.454200 | 2.311711 | 1.525533 | -0.763959 | 0.093552 | -0.692627 | -0.022220 |
| 9 | 6.851123 | 5.392220 | 7.058477 | 5.577353 | -1.458903 | 0.207354 | -1.273770 | -0.022220 |
| 10 | 6.898641 | 5.432610 | 7.105503 | 5.617252 | -1.466031 | 0.206862 | -1.281389 | -0.022220 |
| 11 | 2.265677 | 1.494590 | 2.358738 | 1.565431 | -0.771087 | 0.093061 | -0.700246 | -0.022220 |
| 12 | 6.851123 | 5.392220 | 7.058477 | 5.577353 | -1.458903 | 0.207354 | -1.273770 | -0.022220 |
| 13 | 2.218159 | 1.454200 | 2.311711 | 1.525533 | -0.763959 | 0.093552 | -0.692627 | -0.022220 |
| 14 | 2.265677 | 1.494590 | 2.358738 | 1.565431 | -0.771087 | 0.093061 | -0.700246 | -0.022220 |
| 15 | 6.898641 | 5.432610 | 7.105503 | 5.617252 | -1.466031 | 0.206862 | -1.281389 | -0.022220 |

For candidate prediction displacements `d_alpha` and `d_K` from B, expansion
of the squared residual gives

`F_C−F_A−F_K+F_B = 2*8*Σ_j d_alpha[j]*d_K[j]`.

An independent scalar-loop test checks this identity on every edge. The
interaction is nonzero for this fixture (maximum absolute value
`0.04881842248`), although the coefficient-state interaction was zero up to
round-off. This is the expected quadratic metric interaction; no posterior
or metric additivity is assumed.

## 5. Actual posterior and fixed-common-prior sensitivity

At symbol 0, B4d reports `first_edge`: ADR-004 prior times current metric
likelihood, without a transition. All four posterior rows match exactly. At
symbol 1, B4d reports `later_edge`: previous posterior, ADR-003 transition,
then ADR-005 likelihood. All actual posterior rows are finite and normalized;
canonical IDs remain 0…15.

The sequence API does not export the intermediate transition-predicted prior
`q`. The actual `q` field is therefore marked **UNAVAILABLE**. For an
independent invariant check only, `previous_posterior @ transition_matrix` is
derived from the common symbol-0 posterior and ADR-003 matrix and separately
checked by a scalar loop. It is identical across all four arms:

`q=(0.018382112565×4, 0×4, 0.231617887435×4, 0×4)`.

This is a derived audit quantity, not a raw exported B4d operand. The actual
symbol-1 posterior remains the posterior returned by B4d. The table reports
its four arm posteriors and the alpha-only, correction-only, combined, and
interaction contrasts.

| edge | `p_B` | `p_A` | `p_K` | `p_C` | `Delta p_alpha` | `Delta p_K` | `Delta p_C` | interaction |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.010900481 | 0.016234145 | 0.009737881 | 0.014849290 | 0.005333664 | -0.001162599 | 0.003948809 | -0.000222255 |
| 1 | 0.043321406 | 0.032939315 | 0.047004155 | 0.035256039 | -0.010382091 | 0.003682749 | -0.008065367 | -0.001366024 |
| 2 | 0.000111070 | 0.000329123 | 0.000088652 | 0.000268973 | 0.000218053 | -0.000022418 | 0.000157902 | -0.000037733 |
| 3 | 0.041330754 | 0.031648252 | 0.044866100 | 0.033890656 | -0.009682502 | 0.003535345 | -0.007440098 | -0.001292942 |
| 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 8 | 0.442414060 | 0.438096810 | 0.440656147 | 0.438543175 | -0.004317250 | -0.001757913 | -0.003870885 | 0.002204278 |
| 9 | 0.017273468 | 0.027821986 | 0.015887445 | 0.025717810 | 0.010548517 | -0.001386023 | 0.008444342 | -0.000718152 |
| 10 | 0.016708363 | 0.027046392 | 0.015372971 | 0.025009476 | 0.010338028 | -0.001335392 | 0.008301113 | -0.000701524 |
| 11 | 0.427940398 | 0.425883978 | 0.426386649 | 0.426464581 | -0.002056420 | -0.001553748 | -0.001475817 | 0.002134351 |
| 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 13 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

A separate **fixed-common-prior sensitivity** applies the same uniform
`(1/16,…,1/16)` prior, beta, and ADR-005 likelihood to each symbol-1 metric
row without a transition. This deliberately differs from the actual
continuation posterior, whose derived prior is sparse `q`. The fixed-prior
posterior interaction is also nonzero (maximum absolute value
`0.00182143324`); it must not be substituted for the actual B4d posterior.
Both posterior constructions were checked against independent scalar
normalization; all vectors sum to one within `1e-13`.

## 6. Zero-innovation control

For an explicit control with all 16 predictions equal to the observation,
`epsilon=(0,0)`. The production recursion gives:

- B: state unchanged.
- A: state becomes `0.85*s` through alpha decay.
- K: state unchanged because the correction operand is zero.
- C: state becomes `0.85*s` through alpha decay.

Thus zero innovation does not mean zero total update when `alpha_prime≠1`.
This is an algebraic property of the specified recurrence, not evidence of
instability.

## 7. Causal interpretation and limits

1. **Direct alpha contribution:** independently equal to
   `(0.85−1)*s_before` at the shared first symbol.
2. **Direct innovation correction:** independently equal to
   `K_tilde⊙epsilon` with the same first-symbol posterior and operands.
3. **Metric interaction:** nonzero because squared residuals are quadratic in
   the changed prediction, despite additive first-update state effects.
4. **Posterior response:** normalized nonlinear mapping of metric and prior;
   actual continuation and fixed-common-prior sensitivity are reported
   separately.
5. **Continuing feedback:** these two-symbol runs demonstrate the concrete
   state-to-next-row dependency. The arms may carry different posteriors and
   therefore can receive different future innovations in longer sequences;
   this fixture does not generalize beyond two symbols.
6. **Causal scope:** the calculations establish counterfactual differences
   for this deterministic reconstructed input only. They do not establish
   universal estimator instability, optimality of any policy, author-method
   defect, physical HF behavior, or a cause of M5j errors.

The 16 phase labels are project ADR-002 hypotheses, not author-confirmed
mapping. ADR-005 remains the pseudo-likelihood. SCI-02, SCI-03 and
SCI-METRIC-02 remain open. H1–H5 remain unresolved; H6 is supported as an
implementation dependency only; H7/H8 remain model distinctions with
unresolved contributions. No M5f/M5h/M5j/M6b data, hash, result, or
fingerprint was changed.

## 8. Deterministic test coverage and next test

Tests independently calculate the scalar recursion, first-edge prior,
continuation transition and likelihood, all 16 A(5) predictions, squared
metrics and metric interaction, posterior normalization and contrasts, and
the zero-innovation control. They also check first-row invariance under a
change to only the second symbol's samples, canonical edge order, 8-sample
clock windows/cutoffs, nonzero absolute origin, immutable inputs/results, and
that the adapter has no reference-bit, channel-truth, or RNG inputs. No full
decoder is invoked.

At the time of this M6f report, the smallest suggested follow-up was a
deterministic multi-fixture ablation. It was not authorized by that report.

## M6h posterior-weight follow-up

M6h uses the fixed M6g eight-symbol mathematical fixture, not this M6f
two-symbol input. The same-state test changes only weights from each arm's
own posterior to frozen B weights while holding that arm's state, predictions,
observation, and symbol fixed. The separate multistep replay retains each
arm's own posterior history and applies same-symbol B weights only to the
correction. It is not the M6g full common-innovation replay. The M6f
first-update decomposition remains unchanged; K/C downstream differences
are fixture-specific deterministic contrasts, not evidence about M5j error
causation. See `M6_POSTERIOR_CLAMP_ABLATION_REPORT.md`.

## M6g multistep continuation

The follow-up deterministic eight-symbol audit was subsequently run as a
separate stage. It preserves the four M6f arms and compares the actual
arm-specific B4d closed loop with an evaluation-only replay driven by the
pre-frozen eight-symbol innovation vector from B. B and A are invariant
between regimes; K/C diverge after their innovations differ. Factorial
interactions accumulate under common-operand replay as well as closed loop,
so later interaction is not attributable solely to posterior feedback.
Full per-symbol values, provenance, oracle checks, and interpretation are in
`M6_MULTISTEP_POSTERIOR_FEEDBACK_AUDIT.md`. These results remain
deterministic reconstructed-model diagnostics, not M5j causal proof.
