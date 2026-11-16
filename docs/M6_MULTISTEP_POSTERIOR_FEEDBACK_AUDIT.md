# M6g — deterministic multistep posterior-feedback audit

**Classification:** deterministic multistep feedback audit of the
reconstructed_offline model. It is **not** a tuned receiver, paper-exact
receiver, performance evaluation, or proof of the cause of historical M5j
errors. No RNG, channel/noise generator, BER/SER computation, or decoder ran.
paper_exact:false and receiver_enabled:false remain unchanged.

## 1. Scope and fixed input

The question is whether alpha decay and posterior-weighted correction
interactions accumulate differently when each arm closes its own posterior
loop versus when all arms receive a frozen B innovation stream.

The 64-sample diagnostic buffer was fixed by formula before inspecting its
results:

    for n = 0,...,63:
      Re(z[n]) = (n-31)/40 + ((n mod 7)-3)/100
      Im(z[n]) = (((3*n) mod 11)-5)/30

It is an explicitly mathematical received buffer, not a claim about a
physical HF channel. SHA-256 of the complex128 byte buffer:
99df8784d417cd9d615c389d088f717f0735f4af6accb282fcff82a547629969.
It contains 64 samples, divided into eight non-overlapping 8-sample windows.
The principal run uses sample origin 0, symbol origin 0, first symbol 0, and
estimator tick 0. A deterministic clock regression uses sample origin 31,
first symbol 4, and estimator tick 7; its first window is 63–70 and its
prediction cutoff is 62.

All arms share full/fluctuating initial IQ (0.42, 0.91), mu0=(0,0),
beta=0.7, ADR-004 initial prior, ADR-002 reconstructed edge/phase order,
ADR-005 squared-residual candidate metric, ADR-012 observed-IQ convention,
and the existing transition matrix.

| Arm | alpha′ | K̃ |
|---|---:|---:|
| B, frozen | 1.00 | (0, 0) |
| A, alpha-only | 0.85 | (0, 0) |
| K, correction-only | 1.00 | (0.35, -0.2) |
| C, combined | 0.85 | (0.35, -0.2) |

These are the fixed M5j policy coefficients used as ablation values, not
optimized parameters or new author receiver modes.

## 2. Two regimes and data lineage

**CLOSED_LOOP** runs each arm through the existing eight-symbol B4d sequence
API. At each symbol the arm uses its own pre-state, metrics, posterior, and
derived posterior-weighted innovation. The B4d result supplies frozen metric
rows and the post-update state. Innovation is not exposed as a named raw
operand; the adapter independently derives it from that row's posterior,
observed-IQ mean, and 16 predictions.

**COMMON_OPERAND** first completes all four CLOSED_LOOP trajectories, then
freezes epsilon_ref[f] from B's eight own posterior-weighted innovations.
Only after this full stream exists does it replay A/K/C. Each replay uses its
own state, candidate metrics, and posterior for diagnostics, but applies the
scalar evaluation-only control

    s_next[j] = alpha′ * s[j] + K̃[j] * epsilon_ref[f][j]

to update state. A replay's own posterior and its own derived innovation do
not enter this update. The replay uses the actual production candidate-metric,
observation, first-edge posterior, and continuation posterior functions. Its
state control is an isolated counterfactual, not a production receiver mode.

The intermediate transition prior q is **not exported by B4d**. For
continuation rows it is separately derived as previous posterior times the
existing ADR-003 transition matrix and labelled derived, never as a raw B4d
field. At the first edge, the directly supplied ADR-004 prior is recorded;
there is no transition q.

## 3. First-symbol consistency and independent checks

At f=0, all arms in both regimes have identical pre-state, 16 metrics,
posterior, and own innovation. The common supplied innovation equals B's
frozen reference innovation. Both regimes satisfy the M6f one-step
factorial identity s_C−s_A−s_K+s_B = 0 within absolute tolerance 1e-12.
No invariant failure occurred.

Independent scalar-loop tests cover:

- phase-index predictions from the declared eight-phase mapping;
- ADR-005 squared residual over each actual 8-sample window;
- normalized shifted likelihood with beta 0.7;
- ADR-004 first-edge prior and a manually constructed continuation matrix;
- posterior-weighted innovation and one-step coefficient update;
- state, metric, posterior factorial contrasts;
- exact absolute sample windows, cutoffs, and estimator ticks.

The independent test oracle does not call the production function being
checked to compute its expected value. Production candidate/posterior APIs
remain the object under audit.

## 4. Per-symbol interactions

Max state interaction below is the larger of the absolute componentwise
pre-state and post-state factorial interaction at that symbol. Max feedback
contrast is the largest absolute component among CLOSED_LOOP minus
COMMON_OPERAND state-pre, state-post, metric, and posterior differences over
all four arms. The feedback column is therefore the same paired contrast in
both regime tables.

### CLOSED_LOOP

| f | Max state interaction | Max metric interaction | Max posterior interaction | Max feedback contrast |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |
| 1 | 0.0178043809 | 0.0705781077 | 0.0116804683 | 0.0122442319 |
| 2 | 0.0343506563 | 0.4801361682 | 0.0100857969 | 0.1768085162 |
| 3 | 0.0520601091 | 0.7092107114 | 0.0223554982 | 0.1895262196 |
| 4 | 0.0520601091 | 1.0191486118 | 0.0525196685 | 0.2561370827 |
| 5 | 0.0414040471 | 1.0137247164 | 0.0452131765 | 0.1720793297 |
| 6 | 0.0903523276 | 0.4189138689 | 0.0374621059 | 0.5885846814 |
| 7 | 0.1966745697 | 1.1430675018 | 0.0560063021 | 2.0061958862 |

### COMMON_OPERAND

| f | Max state interaction | Max metric interaction | Max posterior interaction | Max feedback contrast |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |
| 1 | 0.0048473975 | 0.0705781077 | 0.0116804683 | 0.0122442319 |
| 2 | 0.0123230811 | 0.2902847753 | 0.0037255906 | 0.1768085162 |
| 3 | 0.0203132346 | 0.4842347463 | 0.0190664786 | 0.1895262196 |
| 4 | 0.0293376536 | 0.7285844656 | 0.0478416577 | 0.2561370827 |
| 5 | 0.0360584923 | 0.9100102076 | 0.0428066285 | 0.1720793297 |
| 6 | 0.0370790726 | 0.8702299436 | 0.0318279496 | 0.5885846814 |
| 7 | 0.0370790726 | 0.7635125346 | 0.0185139852 | 2.0061958862 |

These are deterministic, fixture-specific algebraic contrasts; the values
are not inferential statistics.

### Frozen-B reference innovation and coefficient trajectories

The frozen reference vector, in f=0 through f=7 order, is

| f | epsilon_ref,I | epsilon_ref,Q |
|---:|---:|---:|
| 0 | 0.0000000000 | 0.1615799170 |
| 1 | 0.0072080725 | 0.1118465249 |
| 2 | -0.0015165435 | 0.0545274116 |
| 3 | 0.0087299373 | 0.0744262888 |
| 4 | -0.0052959125 | -0.0316639191 |
| 5 | 0.0022886845 | -0.1564044184 |
| 6 | 0.0018525744 | -0.1288379052 |
| 7 | -0.0030033056 | -0.0207027516 |

The first I value is numerically 1.68e-17 and displayed as zero at this
precision. The following tables list post-update fluctuating coefficients
(I,Q); full coefficients equal fluctuating plus mu0, and mu0 is zero here.

| f | B | A | K | C — CLOSED_LOOP |
|---:|---|---|---|---|
| 0 | (0.420000, 0.910000) | (0.357000, 0.773500) | (0.420000, 0.877684) | (0.357000, 0.741184) |
| 1 | (0.420000, 0.910000) | (0.303450, 0.657475) | (0.423034, 0.854602) | (0.308611, 0.619881) |
| 2 | (0.420000, 0.910000) | (0.257933, 0.558854) | (0.422591, 0.842029) | (0.262922, 0.525233) |
| 3 | (0.420000, 0.910000) | (0.219243, 0.475026) | (0.425361, 0.827240) | (0.220432, 0.444326) |
| 4 | (0.420000, 0.910000) | (0.186356, 0.403772) | (0.423811, 0.839563) | (0.189366, 0.374739) |
| 5 | (0.420000, 0.910000) | (0.158403, 0.343206) | (0.424434, 0.866921) | (0.157440, 0.292108) |
| 6 | (0.420000, 0.910000) | (0.134642, 0.291725) | (0.425197, 0.889013) | (0.137692, 0.180386) |
| 7 | (0.420000, 0.910000) | (0.114446, 0.247966) | (0.424132, 0.890892) | (0.114377, 0.032184) |

| f | B | A | K | C — COMMON_OPERAND |
|---:|---|---|---|---|
| 0 | (0.420000, 0.910000) | (0.357000, 0.773500) | (0.420000, 0.877684) | (0.357000, 0.741184) |
| 1 | (0.420000, 0.910000) | (0.303450, 0.657475) | (0.422523, 0.855315) | (0.305973, 0.607637) |
| 2 | (0.420000, 0.910000) | (0.257933, 0.558854) | (0.421992, 0.844409) | (0.259546, 0.505586) |
| 3 | (0.420000, 0.910000) | (0.219243, 0.475026) | (0.425048, 0.829524) | (0.223670, 0.414863) |
| 4 | (0.420000, 0.910000) | (0.186356, 0.403772) | (0.423194, 0.835857) | (0.188266, 0.358966) |
| 5 | (0.420000, 0.910000) | (0.158403, 0.343206) | (0.423995, 0.867138) | (0.160827, 0.336402) |
| 6 | (0.420000, 0.910000) | (0.134642, 0.291725) | (0.424643, 0.892905) | (0.137351, 0.311709) |
| 7 | (0.420000, 0.910000) | (0.114446, 0.247966) | (0.423592, 0.897046) | (0.115697, 0.269094) |

## 5. Feedback divergence and controls

At f=0, the two regimes agree for all arms. At f=1, pre-states, metrics,
and posteriors still agree because both paths applied the same first-symbol
innovation. The first closed/common post-state difference appears after the
f=1 update for K/C; its largest component is 0.0122442319. The first
metric and posterior differences between regimes appear at f=2, when those
different post-states first enter candidate prediction and continuation
posterior calculations. The largest later state-post contrast is
0.2369097951 at f=7; the largest metric contrast is 2.0061958862, and
the largest posterior contrast is 0.0409723723, also at f=7.

B is invariant between regimes: it applies the frozen B innovation in both.
A is also invariant because its K̃=(0,0) makes supplied innovation
irrelevant to its state update; identical states then produce identical
metrics and posterior histories. These controls pass for all eight symbols.
K and C differ as their own innovation stream departs from B's frozen stream.

Across the evaluated finite trajectories, every state, prediction, metric,
innovation, and posterior is finite; every posterior is normalized to
floating-point tolerance. All 64 trace rows are finite; maximum posterior
sum error is 1.11e-16. Maximum estimator-state norm is 1.0022474744,
maximum update-increment norm is 0.1801883355, maximum innovation norm is
0.6057696839, and maximum absolute coefficient is 0.91 (the initial state).
These are descriptive values, not stability thresholds. The adapter records
every row; no unfavorable finite row is excluded.

For both regimes, the first nonzero post-state factorial interaction,
metric interaction, and posterior interaction occurs at f=1; the first
nonzero pre-state interaction occurs at f=2. For the paired regime contrast,
state-post first differs at f=1, while metric and posterior first differ at
f=2. Here “nonzero” uses the declared reporting tolerance 1e-10.

## 6. Causal conclusions by level

1. **Algebra:** first-step shared operands obey the additive update
   decomposition. In later common-operand steps, factorial state interaction
   can accumulate even with a shared epsilon because the state is recursively
   multiplied by alpha while K adds a correction.
2. **Estimator state:** the two regimes have identical state through the
   first-symbol update, then K/C state paths differ when their own innovation
   replaces B's frozen innovation. This is observed on this fixed buffer.
3. **Metrics:** state divergence is consumed by the next symbol's predictions
   and changes the next 16 local metrics. Squared-residual factorial
   interactions are generally nonzero.
4. **Posterior/innovation feedback:** changed metrics yield changed
   posteriors; in CLOSED_LOOP, those posteriors and predictions determine
   subsequent innovations. COMMON_OPERAND blocks that innovation feedback
   while still reporting each replay's own posterior.
5. **Decoded path:** not tested; no decoder ran.
6. **M5j BER causation:** not established. M5j historical per-symbol traces
   remain unavailable, and this deterministic buffer is not the M5j sample.

This establishes a specific multistep dependency in the current reconstructed
implementation, not universal estimator instability, source-paper defect, or
the cause of M5j's historical BER contrast.

## 7. H1–H8 status

| Hypothesis | M6g evidence and status |
|---|---|
| H1 alpha/K fixed-policy behavior | **SUPPORTED** as deterministic local/multistep effects for these fixed policies. Their contribution to M5j BER remains unresolved. |
| H2 author quadrature convention | **UNRESOLVED**; this audit uses ADR-012. |
| H3 author innovation semantics | **UNRESOLVED**; implemented posterior-weighted innovation is observable, author operand semantics are not settled. |
| H4 author correction direction/scale | **UNRESOLVED** scientifically; the reconstructed update's arithmetic is checked. |
| H5 author edge-to-phase mapping | **UNRESOLVED**; ADR-002 remains a project reconstruction. |
| H6 update-to-later-metric dependency | **SUPPORTED** as implementation behavior; contribution to M5j errors remains unresolved. |
| H7 frame-constant/per-symbol model distinction | **UNRESOLVED** as a cause; no frame-constant alternative was tested. |
| H8 ADR-005/source-faithful likelihood distinction | **UNRESOLVED** as a cause; no source-faithful likelihood was tested. |

No scientific status or ADR was changed. SCI-02, SCI-03, and SCI-METRIC-02
remain open. Physical HF Eb/N0, paper-exact decoding, multipath, fading, and
performance claims are outside this audit.

## 8. Verification, integrity, and next study

The audit uses deterministic fixed arrays only, runs no encoder, channel/noise
generation, receiver truth/reference inputs, decoder, or BER/SER metric. It
persists all 64 rows plus the fixed-input provenance in
outputs/m6g_multistep_feedback_audit/deterministic_trace.json (206,378 bytes;
SHA-256 67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75).
This is a separate M6g namespace; no M5f/M5h/M5j/M6b output was written.
Their existing hash regressions are run during final verification.

The smallest follow-up, if separately requested, is an evaluation-only
posterior-clamp ablation: preserve each arm's state/prediction path and
compare its own posterior-weighted innovation against a fixed B posterior
weight vector on the same deterministic buffer. That would isolate the
posterior-weighting part from the frozen innovation-stream comparison. It
must not be selected by BER. It was subsequently completed as M6h; see
`M6_POSTERIOR_CLAMP_ABLATION_REPORT.md`. M6h did not modify this M6g report's
historical numeric results or trace artifact.

## M6h posterior-weight follow-up

M6h reads this M6g trace and its exact 64-sample fixture read-only. Its
posterior-clamp replay is distinct from the M6g COMMON_OPERAND regime: M6h
supplies only same-symbol B posterior weights, while retaining each other
arm's own predictions, metrics, and posterior history. B/A remain invariant;
K/C show fixture-specific differences. No decoder or BER was computed, and
M5j causal attribution remains unresolved. The M6g artifact remains byte
identical at SHA-256
`67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75`.
