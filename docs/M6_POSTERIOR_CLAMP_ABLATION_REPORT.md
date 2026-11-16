# M6h — deterministic posterior-clamp ablation

**Classification:** deterministic posterior-weight intervention and feedback
audit. This is **not** proof of historical M5j root cause, an optimized
receiver, performance evidence, or a paper-exact implementation. No RNG,
noise/channel generation, full Viterbi decode, BER/SER calculation, or tuning
was used. Receiver mathematics and accepted ADRs remain unchanged.

## 1. Question, fixture, and fixed arms

M6h separates the effect of swapping posterior weights while holding one
symbol's state/predictions/observation fixed from the effect of carrying that
weight clamp through an eight-symbol estimator trajectory.

The received buffer is exactly the M6g complex128 fixture, defined for
n=0,...,63 by:

    Re(z[n]) = (n-31)/40 + ((n mod 7)-3)/100
    Im(z[n]) = (((3*n) mod 11)-5)/30

It contains 64 deterministic values, eight 8-sample windows, and no random
draws. Its SHA-256 is
99df8784d417cd9d615c389d088f717f0735f4af6accb282fcff82a547629969.
Origins are absolute sample 0, absolute symbol 0, and estimator tick 0.
Initial full/fluctuating IQ is (0.42, 0.91), mu0=(0,0), beta=0.7, and edge
order is the fixed reconstructed ADR-002 order.

| Arm | alpha′ | K̃ |
|---|---:|---:|
| B frozen | 1.00 | (0, 0) |
| A alpha-only | 0.85 | (0, 0) |
| K correction-only | 1.00 | (0.35, -0.2) |
| C combined | 0.85 | (0.35, -0.2) |

These are the fixed M6g/M5j policy values, not selected or optimized values.

## 2. B posterior reference and source integrity

The eight reference vectors p_B[f] are read from the B CLOSED_LOOP posterior
rows in M6g deterministic_trace.json, with h=0,...,15 in stored canonical
order. Each vector is finite and normalized; M6g labels f=0 as first_edge
(ADR-004 prior, no transition) and f=1,...,7 as later_edge (continuation).
The same-symbol posterior is available only after that symbol's observation,
at cutoff 8f+7; it is supplied only to the update after that cutoff and is not
used for an earlier symbol.

M6g trace SHA-256 before and after M6h is
67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75. The M6g
file was read-only. It contains no explicit observed-IQ mean field, so the
mean Y[f] is re-derived from the exact same fixed complex buffer using
ADR-012; this is recorded as derived observation input, not a persisted M6g
field. No transmitted bits or channel truth are used. The B posterior is a
frozen reconstructed-receiver posterior, not a correct-edge oracle.

## 3. Same-state weight swap

For each arm and f, both calculations use the M6g CLOSED_LOOP arm's same
pre-state, own predictions U_own, same observed mean Y, and same symbol.
Only posterior weights differ:

    epsilon_own   = sum_h p_own[h] * (Y - U_own[h])
    epsilon_clamp = sum_h p_B[f,h] * (Y - U_own[h])

The independent scalar loop verifies both identities:

    epsilon_own - epsilon_clamp
      = sum_h (p_own[h] - p_B[f,h]) * (Y - U_own[h])
      = -sum_h (p_own[h] - p_B[f,h]) * U_own[h]

The second form follows because both posterior vectors sum to one. With the
same-symbol B predictions,

    epsilon_clamp - epsilon_B
      = sum_h p_B[f,h] * (U_B[h] - U_own[h])

and epsilon_own-epsilon_B equals the sum of this prediction contrast and the
weight-only contrast. All identities pass componentwise at absolute
tolerance 1e-10; the computed decomposition residual is zero for the reported
examples.

At f=1, the K example is:

| Operand | I | Q |
|---|---:|---:|
| epsilon_own | 0.00866927995 | 0.11541028219 |
| epsilon_clamp | 0.00720807252 | 0.09047370913 |
| epsilon_B | 0.00720807252 | 0.11184652485 |
| weight-only epsilon_own-epsilon_clamp | 0.00146120743 | 0.02493657306 |
| prediction contrast epsilon_clamp-epsilon_B | 0 | -0.02137281572 |

At f=1, the C example is:

| Operand | I | Q |
|---|---:|---:|
| epsilon_own | 0.01474532483 | 0.05062536524 |
| epsilon_clamp | 0.00987686164 | 0.00019673041 |
| epsilon_B | 0.00720807252 | 0.11184652485 |
| weight-only epsilon_own-epsilon_clamp | 0.00486846319 | 0.05042863483 |
| prediction contrast epsilon_clamp-epsilon_B | 0.00266878912 | -0.11164979445 |

The tables show that a weight-only contrast and a prediction contrast are
distinct on the same arm state; neither alone is a BER or causal performance
claim. The one-step clamped post-state uses the existing production
update_quadrature_estimates API with B weights and the arm's own observation
and predictions. It is not fed back into the historical M6g row.

Across symbols, maximum norm of the weight-only innovation contrast is 0 for
B, 0.0563773148 for A, 0.0431901527 for K, and 0.0632673805 for C. The maximum
same-state prediction contrast norm is 0, 0.4956201426, 0.0364882441, and
0.5848668776 respectively. A has nonzero local innovation contrasts, but its
K̃ is zero, so these do not change its update state.

## 4. Multistep posterior-clamp semantics

For each arm, the evaluation-only replay computes that arm's current
predictions, ADR-005 metrics, posterior, and own innovation from its own
state/history. At f=0 it applies the ADR-004 initial edge prior. At f>=1 it
computes the posterior from that arm's previous posterior through the
continuation transition and current metric row. The arm's own posterior is
retained for all subsequent posterior updates and diagnostics.

Only the correction operand uses the same-symbol B weights:

    epsilon_supplied[f] = sum_h p_B[f,h] * (Y_own[f] - U_own[f,h])

The actual existing [A](1) update function receives p_B[f], that arm's own
Y/U operands, its fixed alpha/K, and mu0. It does **not** receive epsilon_B
and does not receive another arm's predictions. The arm's own posterior is
not overwritten. This is distinct from M6g COMMON_OPERAND, which supplied
the complete frozen B innovation vector.

Raw continuation q is unavailable from the production API. The clamp trace
records raw_q=unavailable; an optional q used for provenance is separately
derived from that arm's previous posterior times the ADR-003 transition
matrix. The actual posterior is produced by the existing transition
posterior API, not by treating that derived q as a persisted receiver field.

## 5. Three-way comparison and per-symbol results

For the following table, weight columns give norm(epsilon_own-epsilon_clamp)
from the same-state intervention. State, metric, and posterior columns give
the maximum componentwise absolute CLOSED_LOOP minus POSTERIOR_CLAMP
contrast at that symbol. The first-step values are zero as expected. The
state update differs after f=1 for K/C; the resulting metric and posterior
differences first appear at f=2.

| f | Weight delta A | Weight delta K | Weight delta C | State D K | State D C | max abs metric D K | max abs metric D C | max abs posterior D K | max abs posterior D C |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 0.0393127370 | 0.0249793475 | 0.0506630945 | 0.005013468 | 0.010228655 | 0 | 0 | 0 | 0 |
| 2 | 0.0563773148 | 0.0292380424 | 0.0632673805 | 0.010476166 | 0.020562795 | 0.091435081 | 0.147441097 | 0.003607051 | 0.006779927 |
| 3 | 0.0101216634 | 0.0116519175 | 0.0092129845 | 0.012411712 | 0.017621959 | 0.156416622 | 0.203940022 | 0.003174721 | 0.005122006 |
| 4 | 0.0321961893 | 0.0431901527 | 0.0284242217 | 0.004219007 | 0.009932846 | 0.188051647 | 0.159572723 | 0.006601045 | 0.002685523 |
| 5 | 0.0081428186 | 0.0168840004 | 0.0119970537 | 0.001299624 | 0.011720433 | 0.077162307 | 0.110091232 | 0.005625352 | 0.000783976 |
| 6 | 0.0223708246 | 0.0121687307 | 0.0304566304 | 0.001182174 | 0.017665577 | 0.027169034 | 0.152296852 | 0.002474662 | 0.001875883 |
| 7 | 0.0267217319 | 0.0055147204 | 0.0415812469 | 0.002362360 | 0.026161372 | 0.026349708 | 0.253795857 | 0.001469473 | 0.007333170 |

Three-way maxima for CLOSED_LOOP minus CLAMP and CLAMP minus M6g
COMMON_OPERAND are:

| Arm | max state norm CL−clamp | max abs metric CL−clamp | max abs posterior CL−clamp | max state norm clamp−common | max abs metric clamp−common | max abs posterior clamp−common |
|---|---:|---:|---:|---:|---:|---:|
| B | 0 | 0 | 0 | 0 | 0 | 0 |
| A | 0 | 0 | 0 | 0 | 0 | 0 |
| K | 0.0124117118 | 0.1880516468 | 0.0066010453 | 0.0101246559 | 0.1536245831 | 0.0051866457 |
| C | 0.0261613720 | 0.2537958567 | 0.0073331702 | 0.2107521541 | 1.7524000295 | 0.0336392021 |

Across the three schemes B is invariant because it supplies its own posterior
as the B clamp and has zero K. A is invariant in state, metrics, and posterior
because K̃=0; its same-state epsilon values differ, but they do not enter the
state update. K and C show finite, fixture-specific differences. No sign or
magnitude was used to choose coefficients.

## 6. Independent checks and clocks

The scalar-loop tests independently calculate both IQ components of own and
clamped innovations, the normalized-weight identity, the prediction-only
identity, and the additive decomposition. They also check one-step update
arithmetic, all 16 candidate entries, squared-residual rows, ADR-004 first
edge, manually constructed ADR-003 continuation matrix, normalized
posterior, own posterior history, same-symbol B weights, state handoff, and
frozen M6g metrics.

For symbol f, the trace uses sample window 8f,...,8f+7, prediction cutoff
8f-1, and observation/posterior cutoff 8f+7. B's same-symbol posterior is
only applied after this observation cutoff. No future posterior is used.
All clamp posterior sums are within 1e-12 of one; all recorded trace values
are finite. No decoder ran.

## 7. Scientific interpretation and H1–H8

- **A — direct weighting effect:** established on a common arm state and
  common own predictions for this fixed buffer. It is nonzero for A/K/C
  starting at f=1; B is zero.
- **B — prediction-difference effect under B weights:** separately measured
  as epsilon_clamp-epsilon_B on the same symbol and common observation.
- **C — multistep trajectory propagation:** established for K/C in this
  reconstructed replay; B/A remain invariant. This contrast includes
  subsequent state, metrics, and posterior changes.
- **D — historical M5j BER cause:** remains **UNRESOLVED**. M5j per-symbol
  traces are unavailable; M6h uses the unrelated fixed M6g deterministic
  buffer and computes no BER.

| Hypothesis | M6h update |
|---|---|
| H1 fixed alpha/K effects | **SUPPORTED** for these deterministic local and multistep effects; parameter quality/optimality and M5j contribution unresolved. |
| H2 author quadrature convention | **UNRESOLVED**. |
| H3 source innovation semantics | **UNRESOLVED**. |
| H4 source correction convention | **UNRESOLVED**; only reconstructed arithmetic is checked. |
| H5 project posterior-weight sensitivity | **SUPPORTED** as measured project-level sensitivity; author edge-to-phase mapping remains **UNRESOLVED**. |
| H6 update/weights affect later metrics and posterior | **SUPPORTED** as reconstructed computational dependency; M5j causal contribution remains **UNRESOLVED**. |
| H7 frame-constant versus per-symbol model | Remains a documented distinction; causal contribution **UNRESOLVED**. |
| H8 ADR-005 versus source-faithful likelihood | Remains a documented distinction; causal contribution **UNRESOLVED**. |

No open SCI question or ADR status changed. The B reference posterior is not
ground truth and no result supports an author-method defect, universal
adaptive harm, physical HF performance, or an improved receiver policy.

## 8. Artifacts, verification, and next study

The complete trace is stored in
outputs/m6h_posterior_clamp/deterministic_trace.json. It contains fixture and
M6g provenance hashes, all B/A/K/C rows for CLOSED_LOOP, POSTERIOR_CLAMP, and
COMMON_OPERAND, local same-state swaps, metrics, predictions, posteriors,
innovations, state increments, finite/normalization checks, cutoffs, q
provenance, tolerances, and three-way contrasts. It is a separate namespace;
the original M6g JSON remains byte-identical.

The smallest optional next audit is a second predeclared deterministic
received buffer for the same identities and clamp semantics. It would test
fixture dependence only, not statistical generality, and must not select
parameters or fixtures by BER. It is not run here.

## 9. Artifact integrity and verification

The M6h JSON uses schema `m6h.posterior-clamp.v1`, stores 96 regime/arm/symbol
rows plus 32 same-state intervention records, preserves shapes `(16,2)`,
`(16,)`, `(8,16)`, and uses canonical B/A/K/C ordering. Its serialized file is
428,461 bytes with SHA-256
`14bb8e891f5da49b5374804374e9fd1d28d32cbc74404e062651741708946e9f`.
The read-only M6g source remains 206,378 bytes with SHA-256
`67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75`.

Verification completed with:

- `python -m pytest -q tests/test_reconstruction_posterior_clamp_audit.py --basetemp .pytest-m6h-focused-final-temp -p no:cacheprovider` — 9 passed.
- `python -m pytest -q --basetemp .pytest-m6h-final-temp -p no:cacheprovider` — 818 passed.
- `python -m pytest -q tests/test_m5k_read_only_audit.py::test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes tests/test_m6d_source_evidence.py::test_historical_configs_and_m6b_trace_hashes_remain_unchanged --basetemp .pytest-m6h-historical-final-temp -p no:cacheprovider` — 2 passed.
- `ruff check src tests` — all checks passed.
- `ruff format --check src tests` — 135 files already formatted.

The suite consists of deterministic regression checks; no random-generation,
decoder, or BER/SER evaluation was added. `paper_exact:false`,
`receiver_enabled:false`, and SCI-02/SCI-03/SCI-METRIC-02 remain unchanged.
No new ADR is needed for this isolated evaluation-only intervention. Any
subsequent experiment requires a separate request.
