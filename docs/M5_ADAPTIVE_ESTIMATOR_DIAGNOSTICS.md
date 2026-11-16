# M5e — Adaptive estimator diagnostic controls

**Status:** isolated adaptive-estimator diagnostic experiment, **NOT validated
BER advantage**, **NOT paper-exact receiver**. `paper_exact:false` and
`receiver_enabled:false` remain unchanged. This is a small deterministic
evaluation composition, not Monte Carlo or a performance study.

## Scope and decisions

The experiment uses only the accepted narrow profile: `reconstructed_offline`,
L=1 real constant gain `a>0`, zero delay, normalized 8PSK, rectangular ZOH at
8 samples/symbol, ADR-012 observed I/Q, ADR-005 reconstruction pseudo-likelihood,
ADR-013 conditional full Viterbi, and (for seeded noisy cases) ADR-015 iid
circular complex sample AWGN. At the M5e stage ADR-009/011/014 were proposed;
M5f later accepted ADR-014. SCI-02, SCI-03, and SCI-METRIC-02 remain open. No
new ADR is needed for these diagnostic controls.

Historical M5e ADR statuses were accepted 001/002/003/004/005/006/007/008/
010/012/013/015 and proposed 009/011/014. Current M5f status: ADR-014 is
accepted; only 009/011 remain proposed.

Three modes consume one immutable `received` buffer per run:

| Mode | Initial estimate | Recursion operands | Meaning |
|---|---|---|---|
| A `oracle_frozen` | `(a,a)` for both fluctuating and full estimates | `alpha_prime=1`, `K_tilde=0`, `mu0=0` | Oracle-initialized frozen control |
| B `mismatched_frozen` | Explicit caller pair different from `(a,a)`; fluctuating and full components equal for this zero-`mu0` frozen policy | `1,0,0` | Mismatched frozen control |
| C `mismatched_adaptive` | Exact same immutable state as B | Explicit `alpha_prime`, `K_tilde`, `mu0` scalar/per-symbol schedule | Adaptive recursion diagnostic |

The result records the actual initial state and every recursion operand. If
`mu0` is nonzero, initial fluctuating and full estimates remain separate; the
state is not collapsed. A post-step state is checked against
`full_iq = fluctuating_iq + mu0` for that step. The chosen recursion parameters
are experimental settings, not a convergence guarantee and are not tuned
against reference bits or BER.

The two active parameter profiles are sensitivity probes: profile 1 uses
smaller estimate retention (`alpha_prime=0.85`) with a larger signed correction
gain; profile 2 uses higher retention (`0.95`) with lower positive correction
gains. Both are explicit stable finite operands for exercising the kernel, not
source-derived settings or tuned recommendations. They are not asserted to be
stable for arbitrary signals or sequences.

## Paired data lifecycle and causality

Reference bits are encoded on the evaluation side through M1 and ADR-002. The
evaluation composition creates the clean control waveform, adds exactly one
explicit complex noise array or one seeded ADR-015 AWGN realization, freezes
the resulting received buffer, and calls B4d separately for A, B, and C. The
receiver calls receive the samples, explicit estimator state, posterior
configuration, and recursion operands; they do not receive `a`, reference
bits, transmitted phase indices, or `ChannelTruth`. The true `a` is used only
for evaluation waveform setup, A's explicitly labelled oracle initialization,
and post-run coefficient-error diagnostics.

For symbol `f`, the pre-observation state predicts using samples only through
`O+8f-1`; the metric, posterior and update become available after sample
`O+8f+7`. Thus the post-state for `f` can affect candidate costs only from
`f+1` onward. Per-symbol diagnostics copy B4d's actual candidate metrics and
posterior; historical metrics are never recomputed from a final estimate. B5b
is run once over each mode's frozen metric matrix. Monolithic and segmented
B4d processing are both available; segmentation does not reset state or
posterior.

Diagnostics include absolute sample/symbol/estimator labels, cutoffs,
pre/post fluctuating and full estimates, coefficient increments, posterior,
candidate costs, coefficient-error norm (evaluation only), selected path,
decoded bits, and raw BER/SER counts. Arrays and state are immutable or copied
into immutable result records. The received SHA-256 identifies paired sample
identity without storing duplicate received buffers in each mode.

## Recursion being diagnosed

The existing [A](1) implementation is called unchanged. In the repository's
quadrature notation, for prior fluctuating estimate `mu_tilde_i`, posterior
weights `p_h`, observed vector `Y`, predictions `Uhat_h`, and explicit
parameters, the update is:

`mu_tilde_(i+1) = alpha_prime * mu_tilde_i + K_tilde * sum_h p_h * (Y-Uhat_h)`

and `mu_star_(i+1) = mu_tilde_(i+1) + mu0`.

This statement describes the implemented kernel operands and decomposition;
it does not equate `mu0` with either estimate and makes no claim of stability,
convergence, or performance improvement.

## Diagnostic controls

The test/control fixtures use `a=0.75` and `a=2.0`, `F=2,4,8`, nonzero sample
origin 23, first absolute symbol 5, and estimator time origin 41. The standard
mismatched initial state is `fluctuating_iq=full_iq=(0.42,0.91)`. A second
explicit mismatch `(0.31,0.83)` is also validated. One active profile uses
`alpha_prime=0.85`, `K_tilde=(0.35,-0.2)`, `mu0=(0,0)`; a second uses
`alpha_prime=0.95`, `K_tilde=(0.08,0.04)`. These are diagnostics only, not
recommended operating values.

The deterministic control run below uses explicit reference fixtures and
zero perturbation. It is a compact integration check rather than a statistical
sample:

| `a` | `F` | Mode | Bit errors / total | BER | Symbol errors / total | SER | Final full-estimate displacement |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0.75 | 2 | A | 0/4 | 0 | 0/2 | 0 | 0 |
| 0.75 | 2 | B | 0/4 | 0 | 0/2 | 0 | 0 |
| 0.75 | 2 | C | 0/4 | 0 | 0/2 | 0 | 0.3753 |
| 2.0 | 4 | A | 0/8 | 0 | 0/4 | 0 | 0 |
| 2.0 | 4 | B | 0/8 | 0 | 0/4 | 0 | 0 |
| 2.0 | 4 | C | 2/8 | 0.25 | 2/4 | 0.5 | 0.5031 |

The adaptive posterior and candidate costs changed after the first update in
the paired cases; the estimator update did not guarantee lower BER. In the
`a=2,F=4` control, C was worse than B. This is recorded as a diagnostic
counterexample to any claim that an active correction necessarily improves
decoded output.

Three small seeded ADR-015 runs use `sigma_squared=0.02`, stream ID
`m5e-diagnostic-awgn`, explicit independent seeds, and the same mismatched
initial state and paired samples for A/B/C:

| Run | `a` | `F` | Seed | effective discrete `gamma_b` | A/B/C bit errors | A/B/C symbol errors |
|---|---:|---:|---:|---:|---|---|
| `seed-701` | 0.75 | 4 | 701 | 112.5 | 0/8, 0/8, 0/8 | 0/4, 0/4, 0/4 |
| `seed-702` | 2.0 | 8 | 702 | 800 | 0/16, 0/16, 0/16 | 0/8, 0/8, 0/8 |
| `seed-703` | 0.75 | 8 | 703 | 112.5 | 0/16, 0/16, 0/16 | 0/8, 0/8, 0/8 |

The adaptive full-estimate displacements for these runs were respectively
0.5199, 0.8707, and 0.3080 in the implemented two-quadrature coefficient
norm. Posterior and later candidate metrics differed from B in each run.
These few selected control outcomes do not estimate an error probability.

Seeded ADR-015 controls are supported with an explicit seed, stream ID and
`sigma_squared`; the resulting `effective discrete gamma_b=4a^2/sigma_squared`
is a sample-domain label only. Explicit deterministic perturbation arrays are
not labelled AWGN and do not receive a gamma value unless the caller explicitly
provides an ADR-015 variance contract. No SNR sweep, BER curve, confidence
interval, or Monte Carlo claim is made.

## Gates and interpretation

- **Paired A/B/C diagnostics:** READY for isolated controls; all three modes
  use the same received hash and B/C share the same initial state.
- **Adaptive execution and causality:** READY for the explicit B4d sequence
  composition, including hand-checked [A](1) updates and copied per-symbol
  history.
- **Monolithic/segmented equivalence:** READY for identical inputs in the
  tested narrow profile; this does not establish frame-constant forward-model
  compatibility.
- **Adaptive BER advantage:** BLOCKED / not established. A few selected runs
  are not a statistical comparison.
- **At the M5e stage, paired Monte Carlo and uncertainty were BLOCKED** pending
  policy; M5f later accepted ADR-014 and ran the small exploratory paired study.
  The M5e controls themselves remain diagnostics, not a statistical sample.
- **Adaptive CSI parity with M2 or general channels:** BLOCKED; M2 oracle-CSI
  controls are not an estimated-CSI matched baseline for B/C.
- **Paper result reproduction:** BLOCKED; this harness does not validate the
  paper's metric ambiguity, full channel model, or reported 1.5 dB result.

## M5f follow-up

ADR-014 was later accepted and a separate 12-cluster paired B/C study was run;
see `M5_PAIRED_MONTE_CARLO_REPORT.md`. Its fixed configuration produced
zero observed errors for frozen B and larger error counts for adaptive C.
That follow-up does not convert the M5e diagnostic controls into an evidence
of general performance and does not justify parameter tuning from either
small dataset.

## M5g design boundary

The proposed primary adaptive policy remains the historical M5f setting
`alpha_prime=0.85`, `K_tilde=(0.35,-0.2)`, `beta=0.7`, with the same initial
mismatch as B. M5f observed C worse in all pairs; do not select replacement
parameters from those outcomes. Candidate one-factor sensitivity levels and
initial mismatch scenarios are documented as exploratory only in
`M5_PREREGISTERED_EXPERIMENT_DESIGN.md`; they require separate approval and
have no confirmatory status. Coefficient-error growth is logged as an
evaluation-only diagnostic, never used to feed back or exclude a numerically
valid BER/SER run.

## M6a — causal B4d trace adapter

`evaluation/reconstruction_causal_trace.py` adds a paired B/C trace over a
caller-provided deterministic received buffer. It copies the actual B4d/B4c
per-symbol candidate row, posterior, pre/post state, clocks/cutoffs, update
coefficients and increments, and then decodes the frozen metric matrix once
with B5b. It does not accept reference bits or true gain, generate observations,
or change receiver mathematics. Read-only innovation is derived from the exact
B4c posterior/observed-mean/predicted-IQ operands; intermediate transition
prediction `q` is unavailable and is not recomputed.

The deterministic six-symbol fixture first diverges in post-update state at
symbol 5 and in candidate metric at symbol 6. This verifies the implementation
dependency of future rows on earlier updates, not a cause of M5j bit errors.
M5j historical per-symbol trace remains unavailable. Full schema, field
availability, H1–H8 interpretation, and gates are in
`M6_CAUSAL_ESTIMATOR_TRACE_CONTRACT.md`.
