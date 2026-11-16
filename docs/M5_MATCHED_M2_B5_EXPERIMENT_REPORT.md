# M5d — paired discrete-AWGN M2/B5 control

**Result:** isolated matched discrete-AWGN paired M2/B5 control experiment,
**NOT validated performance advantage**, **NOT physical HF Eb/N0 calibration**,
**NOT reproduction of paper results**.

This report applies the user-approved narrow ADR-015 profile. It is a small
integration and metric-consistency check. It contains no SNR sweep, Monte
Carlo batch, confidence interval, matched performance claim, or dB-gain claim.

## Accepted profile and equations

ADR-015 is accepted only for `reconstructed_offline`, L=1, positive real gain
`a`, zero delay, normalized 8PSK, rectangular ZOH with eight samples/symbol,
and independent circular complex sample noise. The evaluation layer generates
one sample-noise realization and constructs one immutable `received` buffer;
M2 and B5 consume that same received value.

For a transmitted normalized symbol `s_f`,

```text
clean[f,k] = a*s_f
received[f,k] = clean[f,k] + n[f,k]
n[f,k] = sqrt(sigma_squared/2) * (X[f,k] + jY[f,k])
```

`X` and `Y` are independent standard-normal draws. Thus each real component
has variance `sigma_squared/2`, and complex sample power is
`E|n|²=sigma_squared`. This is an evaluation-only discrete noise convention;
it is not [A](9)-(10), M3 AR(1), or a physical HF channel model.

With two information bits per symbol, this profile labels only
`effective discrete gamma_b = 4*a²/sigma_squared` (optionally
`10 log10(gamma_b)` as `effective discrete gamma_b_dB`). The symbol-rate
signal energy is `a²`, the per-information-bit symbol-rate energy is `a²/2`,
and the independent eight-sample mean noise power is `sigma_squared/8` before
equalization. After M2's explicit division by `a`, its observation noise
power is `sigma_squared/(8a²)`. None of these labels asserts physical Eb/N0.
ADR-005 `beta` remains a pseudo-likelihood scale, not noise precision.

## Receiver composition and information boundary

Evaluation encodes explicit reference information bits with M1 from `(0,0)`,
maps output triples through ADR-002, modulates with the existing M1 mapper, and
uses the M3 rectangular ZOH helper. The evaluation-only control multiplies by
explicit `a`, then either adds one explicit complex noise array or generates
one PCG64 stream from an explicit seed and stream ID. It never generates
separate M2 and B5 noise.

M2 receives `mean(received[f,0:8])/a` as its symbol-rate complex observations
and calls the existing soft `decode_viterbi()` with initial `(0,0)`, free final
state, no tails, phase offset zero, and the M1 baseline mapping. It accepts
external observations, so no M2 AWGN generator is called. B5 receives the same
eight raw samples per symbol, the validated explicit initial estimator state
`full_iq=fluctuating_iq=(a,a)`, and explicit frozen recursion operands
`alpha_prime=1`, `K_tilde=0`, `mu0=0`. Both use oracle-derived information in
this **oracle-CSI matched control**. This is not estimated-CSI parity or an
operational initialization policy.

Reference bits and reference coded symbols are confined to the evaluation
setup and post-decode measurement. Receiver calls receive neither reference
bits nor true phase, channel truth, or a true path. Result records retain the
received SHA-256, dimensions, parameters, time labels, decoder outputs, and
counts rather than embedding reference bits or the full received buffer.

## M2/B5 metric relationship

For each candidate symbol `s_h` under frozen correct coefficient `a`, the B5
sample-summed residual satisfies

```text
F_B5[f,h] = sum_k |received[f,k] - a*s_h|²
           = sum_k |received[f,k] - mean_f|²
             + 8*a²*|mean_f/a - s_h|².
```

M2 soft branch costs are `|mean_f/a-s_h|²`. For each symbol, B5 therefore
equals `8a²` times the M2 branch cost plus a candidate-independent offset.
This preserves each row's minimizing labels and, because the scale is positive
and the offset is common to all candidates in a row, preserves complete path
ordering in the tested fixed-estimate setup. It does not make the raw path
costs equal and is not a joint channel/trellis optimization. The implementation
reports the maximum absolute error against this identity and row minimizer
agreement.

### Tie behavior

M2's current loop walks `build_trellis()` order and replaces a survivor only
on strict `<`; a tied incoming edge therefore leaves the first canonical
branch. Its unconstrained final state is selected by `min((metric,state))`,
so equal final metrics use tuple state order. B5's accepted ADR-013 rules use
minimum canonical hypothesis ID for survivor ties and minimum canonical M1
state index for final ties. Current canonical ordering agrees on the all-zero
one-symbol fixture, but these are separately implemented policies and exact
ties are not used as evidence of general path equivalence.

## Control records

The short seeded controls use the test reference rule
`bit[j]=(3*j + floor(j/2) + 1) mod 2`, sample origin `O=23`, first absolute
symbol `f=5`, initial estimator time `41`, beta `0.7`, and PCG64. Noise stream
IDs are shown as `<run-id>/noise`.

| Run ID | F | a | sigma² | effective discrete gamma_b | Seed | M2 bit/symbol errors | B5 bit/symbol errors | Branch/path agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `seed-075-F2` | 2 | 0.75 | 0.02 | 112.5 | 13 | 0/4, 0/2 | 0/4, 0/2 | same path `(2,1)` |
| `seed-2-F4` | 4 | 2.0 | 0.1 | 160 | 27 | 0/8, 0/4 | 0/8, 0/4 | same path `(2,1,10,5)` |
| `seed-075-F4` | 4 | 0.75 | 0.05 | 45 | 55 | 0/8, 0/4 | 0/8, 0/4 | same path `(2,1,10,5)` |

These are three reproducible paired controls, not a statistical sample.

Zero-noise oracle controls were also run for `a=0.75` and `a=2.0`, with
`F=1,2,4`; all had zero bit and coded-symbol errors for both receivers.
`sigma_squared` and `gamma_b` are deliberately absent for these all-zero noise
fixtures.

Three deterministic F=2 perturbation controls at `a=0.75` each add
`0.035+0.012j` to one sample (offsets 0, 5, and 15). M2 and B5 each had 0/4
bit errors and 0/2 symbol errors in these cases. They are literal perturbations,
not AWGN samples or SNR points. The shared-buffer hash, deterministic rerun
tests, and exact same-input comparison verify pairing. For the tested noisy
arrays, the B5/M2 branch identity maximum absolute residual was about
`7.11e-15` (floating-point arithmetic).

## Status and gates

| Item | Status | Limit |
|---|---|---|
| M2 observation adapter | READY | Mean of exactly 8 explicit samples, then `/a`; no noise generation. |
| Paired M2/B5 discrete-AWGN controls | READY | Narrow oracle-CSI, frozen-estimator profile only. |
| Candidate branch metric identity | READY for frozen control | Positive scale and row-wise constant offset verified numerically. |
| General or adaptive M2/B5 CSI comparison | BLOCKED | M2 has no estimator trajectory input; this experiment uses oracle CSI on both sides through different interfaces. |
| Physical HF Eb/N0 | BLOCKED | Discrete convention has no physical sample interval/amplitude calibration. |
| BER-vs-SNR, Monte Carlo, confidence intervals | BLOCKED / not run | ADR-014 remains proposed; no statistical policy is accepted. |
| General complex fading, correlated noise, multipath | BLOCKED | Outside ADR-015's accepted profile. |
| Paper performance or 1.5 dB replication | BLOCKED | This is not the paper's algorithm or calibrated experiment. |

Accepted ADRs are 001/002/003/004/005/006/007/008/010/012/013/015. Proposed
ADRs are 009/011/014. SCI-02, SCI-03, and SCI-METRIC-02 remain open;
`paper_exact:false` and `receiver_enabled:false` are unchanged. No new ADR was
needed.

## M5e adaptive diagnostic follow-up

M5e uses the same narrow received-generation and B5 contracts, but its primary
comparison is B (mismatched frozen) versus C (same mismatched initial state,
explicit adaptive recursion). A (oracle frozen) is a separate control. M2 is
not used as a CSI-matched comparator for B/C. The exact recursion operands,
per-symbol B4d diagnostics, and small paired results are recorded in
`M5_ADAPTIVE_ESTIMATOR_DIAGNOSTICS.md`; the controls demonstrate that active
updates can change estimates, posterior and metrics, and can worsen decoded
output in a fixture. They establish no BER advantage or statistical effect.
