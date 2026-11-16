# M6e — deterministic estimator-update intervention audit

**Classification:** deterministic evaluation-side intervention in the fixed
`reconstructed_offline` model. This is not Monte Carlo, tuning, performance
evidence, an author-mapping check, or an established explanation of historical
M5j errors. `paper_exact:false` and `receiver_enabled:false` remain unchanged.
No receiver mathematics, ADR, or scientific status was changed.

## 1. Intervention definition and operands

At one explicitly labeled symbol, the intervention starts from
`fluctuating_iq=(0.42,-0.91)`, `mu0=(0.31,-0.23)`, hence
`full_iq=(0.73,-1.14)`. It uses `alpha_prime=0.85`,
`K_tilde=(0.35,-0.2)`, an explicit current-symbol observation, an explicit
`(16,2)` prediction array, and a normalized current posterior. The
post-update coefficients are calculated by the existing
`paper_recursion.update_quadrature_estimates` API.

For the next symbol, the same fixed eight-sample `(I,Q)` array, the same 16
canonical `HYPOTHESES` rows, the same ADR-002 assumed-natural-binary mapping,
and the same squared-residual metric are evaluated from both coefficient
states. Only the estimator state changes. The two reported posterior rows use
the same fixed prior and `beta=0.7`, through the existing first-edge
observation update without a transition. This is a local sensitivity control,
not a closed-loop receiver or Viterbi decode.

The adapter is `src/hf_tcm/evaluation/reconstruction_update_intervention.py`.
It receives only explicit numeric estimator operands and a next-symbol
observed-IQ window. It does not receive reference bits, true gain,
`ChannelTruth`, or random generators. All inputs are copied/read-only in the
result. The adapter reports the posterior-weighted innovation as a **derived
scalar sum**, not as a raw B4c field.

## 2. Independent recursion oracle

For canonical hypothesis `h` and quadrature `j`, the independent scalar
oracle evaluates

`v_j = Σ_h p_h (y_j - U_h,j)`,

`x'_j = alpha_prime*x_j + K_tilde_j*v_j`,

`mu'_j = x'_j + mu0_j`.

The test oracle uses Python scalar loops and `math.fsum`; it does not invoke
the production recursion to form expected values. The production kernel is
then called separately and compared at `rtol=0`, `atol=1e-14`. Posterior
inputs are explicitly normalized and use 16 rows. The decomposition checked
is `full_iq = fluctuating_iq + mu0`.

One fully numeric two-quadrature fixture has current predictions
`U_h=((h-7.5)/10,(7.5-h)/25)`, uniform `p_h=1/16`, and observed
`y=(0.7,-0.6)`. Symmetry gives derived innovation `(0.7,-0.6)`. Thus

`x'=(0.85*0.42+0.35*0.7, 0.85*(-0.91)+(-0.2)*(-0.6))`
`=(0.602,-0.6535)`,

and `mu'=(0.912,-0.8835)`. The coefficient increment relative to the
pre-update fluctuating state is `(0.182,0.2565)`. The independent oracle and
production API agree within `1e-14`.

## 3. Prediction-delta identity

With the regular coefficient `mu0` held fixed, the full-coefficient change
equals the fluctuating-coefficient change. For every phase index
`b∈{0,…,7}`, the independent scalar oracle checks

`Delta U_s(b) = -Delta mu1*sin(b*pi/4)` and
`Delta U_c(b) =  Delta mu2*cos(b*pi/4)`.

The 16 project hypotheses map in canonical order to phase indices
`(0,2,4,6,2,0,6,4,1,3,5,7,3,1,7,5)`. The repeated phase values are
intentional project edges with equal output labels; edge IDs remain distinct.
These are ADR-002 project labels, not an author-confirmed mapping.

## 4. Metric-sensitivity audit

The specific code path uses
`F_h = Σ_{n=0}^{7} Σ_{j=1}^{2} (r[n,j]-U_h[j])²`, with a rectangular
eight-sample prediction for each phase and the exact project helper
`compute_project_reconstruction_metric`. It is the ADR-005 reconstructed
squared-residual metric; it is **not** asserted to be the source's ambiguous
[A](2) likelihood/metric.

For `d_h = U_after,h-U_before,h`, the independent scalar identity is

`F_after,h-F_before,h = Σ_n Σ_j [-2(r[n,j]-U_before,h[j])*d_h[j] + d_h[j]²]`.

Every one of the 16 rows is checked against independently calculated
predictions and metric values (`atol=1e-13` for metrics and `1e-12` for the
expanded metric-delta identity). The table below records the explicit
two-quadrature fixture above and the fixed received window used by the tests.

| edge | phase | `F_before` | `F_after` | `Delta F` |
|---:|---:|---:|---:|---:|
| 0 | 0 | 10.7354111111 | 6.9679391111 | -3.7674720000 |
| 1 | 2 | 6.3118111111 | 8.7025631111 | 2.3907520000 |
| 2 | 4 | 14.1554111111 | 9.6184391111 | -4.5369720000 |
| 3 | 6 | 6.3118111111 | 8.7025631111 | 2.3907520000 |
| 4 | 2 | 6.3118111111 | 8.7025631111 | 2.3907520000 |
| 5 | 0 | 10.7354111111 | 6.9679391111 | -3.7674720000 |
| 6 | 6 | 6.3118111111 | 8.7025631111 | 2.3907520000 |
| 7 | 4 | 14.1554111111 | 9.6184391111 | -4.5369720000 |
| 8 | 1 | 8.1694585153 | 7.5607828493 | -0.6086756659 |
| 9 | 3 | 10.5877637069 | 9.4349693729 | -1.1527943341 |
| 10 | 5 | 10.5877637069 | 9.4349693729 | -1.1527943341 |
| 11 | 7 | 8.1694585153 | 7.5607828493 | -0.6086756659 |
| 12 | 3 | 10.5877637069 | 9.4349693729 | -1.1527943341 |
| 13 | 1 | 8.1694585153 | 7.5607828493 | -0.6086756659 |
| 14 | 7 | 8.1694585153 | 7.5607828493 | -0.6086756659 |
| 15 | 5 | 10.5877637069 | 9.4349693729 | -1.1527943341 |

Some candidate costs decrease and others increase under the same update. This
is a deterministic local metric effect, not evidence that the update is
generally harmful or helpful.

## 5. Deterministic fixtures and observed summaries

No RNG is used. Current posterior is uniform for the innovation-direction
fixtures; the fixed next-observation window is
`[(n mod 4 - 1.5)/3, (n mod 5 - 2)/4]`, `n=0,…,7`. The adaptive update
coefficients and unequal initial I/Q coefficients are fixed above.

| Fixture | Derived innovation | `max_h |Delta F_h|` | `||Delta F||₂` | posterior L1 change |
|---|---:|---:|---:|---:|
| Zero innovation (all current predictions equal observation) | `(0,0)` | 2.545452 | 6.540289 | 0.257277 |
| Positive first quadrature | `(1,0)` | 4.011112 | 9.601434 | 0.849360 |
| Negative first quadrature | `(-1,0)` | 3.459288 | 11.721663 | 0.226253 |
| Second quadrature only | `(0,0.8)` | 0.704088 | 1.699992 | 0.192021 |
| Both quadratures | `(0.7,-0.6)` | 4.536972 | 9.960742 | 0.852804 |
| Frozen policy (`alpha=1`, `K̃=(0,0)`) | `(0.7,-0.6)` | 0 | 0 | 0 |

The zero-innovation case still changes the state because `alpha_prime=0.85`
multiplies the previous fluctuating coefficient. It isolates the forgetting
term; it is not a correction caused by innovation. Under the explicitly
frozen policy, both the state and all next-symbol metric rows remain exactly
unchanged.

## 6. Fixed-prior posterior sensitivity

For each fixture, one fixed, nonuniform prior `prior[h]=(h+1)/136` and
`beta=0.7` are applied to the before/after rows using the existing
`initial_reconstruction_observation_update` API (initial-edge update, no
transition). Both output vectors sum to one within `1e-13`; their hypothesis
order is canonical IDs `0…15`. An independent scalar `exp(-beta*(F-min(F)))`
oracle agrees within `1e-13`. The `||p_after-p_before||₁` values are descriptive
one-step sensitivities. This separates direct metric movement from this
fixed-prior posterior response; no posterior feedback is then fed into a
second estimator update.

## 7. Causality, checks, and levels of conclusion

The intervention records explicit current `symbol_index`, estimator tick,
sample origin, prediction cutoff, current-observation cutoff, and next metric
sample window. A test uses symbol index 4, estimator tick 9, origin 13:
prediction cutoff 44, observation cutoff 52, next window 53–60. The post-state
tick is 10. These labels are explicit; the adapter does not infer tick from
symbol index. Inputs are unchanged and output arrays are immutable.

| Level | M6e conclusion |
|---|---|
| 1. [A](1) implementation algebra | **Verified** for the supplied reconstructed operands against an independent scalar oracle. This does not settle author/source operand semantics. |
| 2. Update → next-symbol prediction | **Verified** exactly under [A](5) project transform and fixed ADR-002 phases. |
| 3. Prediction → local candidate metric | **Verified** for the ADR-005 eight-sample squared-residual metric; each of 16 rows has an independently checked delta. |
| 4. Metric → posterior | **Verified** as a fixed-prior first-edge, no-transition sensitivity at beta 0.7. |
| 5. Full decoding trajectory | **Not tested**; M6e does not decode or mutate frozen metric histories. |
| 6. Causal contribution to M5j BER | **Not established**; historical M5j per-symbol operands and metric histories remain unavailable. |

These results support an implementation-level causal chain for the chosen
reconstruction. They do not prove author intent, source fidelity, a causal
mechanism for historical C errors, or a general adaptive-estimator outcome.

## 8. Verification and limitations

Deterministic tests use `rtol=0`; recursion/prediction comparisons use
`atol=1e-14`, metric comparisons `atol=1e-13`, metric-delta expansion
`atol=1e-12`, and posterior comparisons `atol=1e-13`. Tests cover zero and
signed innovations, both quadratures, unequal coefficient values, frozen
policy, all eight phase indices/canonical edge alignment, metric deltas,
fixed-prior posterior normalization/sensitivity, explicit clocks, immutable
results, input preservation, invalid non-finite operands, and absence of
reference/truth/random-generator inputs.

No runtime/source mismatch was observed in the tested algebra path. Open
questions SCI-02, SCI-03, and SCI-METRIC-02 remain open. H1–H5 remain
unresolved; H6 is supported as an implementation dependency only; H7/H8 are
model distinctions whose contribution remains unresolved. The project mapping
is not author-confirmed and the receiver remains reconstructed, not paper-exact.

## 9. Follow-up factorial ablation

The two-symbol B/A/K/C component ablation was completed as M6f using the
actual sequence API and one fixed deterministic received buffer. Its
factorial state, metric, posterior, and limitation results are in
`M6_FACTORIAL_UPDATE_ABLATION_REPORT.md`. It does not upgrade M5j causal
claims or authorize a full decoder/performance study.
