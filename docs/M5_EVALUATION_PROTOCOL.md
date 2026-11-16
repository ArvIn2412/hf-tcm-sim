# M5a — Reconstruction BER/SER evaluation protocol

**Status:** reconstruction BER/SER evaluation contract and isolated measurement
utilities, **NOT validated performance claim**, **NOT reproduction of paper
results**. This document defines post-decode measurement for the narrow
`reconstructed_offline` path; it does not run Monte Carlo batches, SNR sweeps,
confidence intervals, or receiver activation.

## 1. Scope and claims

The currently implemented measurement scope is the project reconstruction
profile: `reconstructed_offline`, L=1, real-channel experiment, zero delay,
rectangular ZOH with 8 samples/symbol, ADR-012 observation convention,
ADR-005 reconstruction pseudo-likelihood, ADR-013 conditional full Viterbi,
and one independent coded sequence per run. B5c/B5d process received samples
to decoded input bits and a selected edge path. They are not a paper-exact joint
receiver or general complex-fading/multipath receiver.

No number here or in the measurement utilities establishes the paper's claimed
1.5 dB gain. `paper_exact:false` and `receiver_enabled:false` remain in force.
ADR-009 and ADR-011 remain proposed; SCI-02, SCI-03 and SCI-METRIC-02 remain
open.

### M5e adaptive-estimator diagnostics

M5e adds paired `oracle_frozen`, `mismatched_frozen`, and
`mismatched_adaptive` diagnostics on one immutable received buffer. The
mismatched frozen/adaptive modes share the exact same initial estimator state;
only the explicitly recorded update policy differs. This is an isolated
adaptive-estimator diagnostic experiment, **NOT validated BER advantage** and
**NOT a paper-exact receiver**. Per-symbol estimates, posterior and candidate
metrics are copied from the B4d history actually used. Evaluation-only true
channel gain is never an estimator operand. M5e does not authorize large
Monte Carlo, SNR sweeps, confidence intervals, or a BER-gain claim. See
`M5_ADAPTIVE_ESTIMATOR_DIAGNOSTICS.md`.

## 2. Reference-data lifecycle

Reference information bits and any channel truth belong to the simulation and
evaluation side. A receiver run receives only its received samples and its
explicit receiver operands/state. Evaluation starts after decoding and may
compare the returned decoded bits and selected path with the separately held
reference sequence. Receiver output and diagnostics must not carry
`ChannelTruth` or reference bits.

For a noiseless control fixture, known bits and a chosen real channel coefficient
may generate the received oracle. A matching initial receiver estimate may
also be supplied explicitly to that fixture; it is oracle-derived test setup,
not a general initialization policy or a default receiver input.

## 3. Information-bit BER

For equal-length, ordered reference and decoded information-bit arrays:

```text
bit_errors = sum(reference_information_bits[k] != decoded_information_bits[k])
total_bits = number of compared information bits
BER = bit_errors / total_bits
```

For `F` rate-2/3 TCM edges, there are `F` pairs of information input bits and
therefore `total_bits = 2F` when no separately declared service or termination
bits exist. ADR-013 adds no tail bits and allows a free final trellis state.
Comparison requires exactly matching lengths, order, independent-sequence
boundaries, and information-bit semantics. A mismatch is rejected; no suffix
trimming is permitted. Compare information bits from decoder `input_bits`, not
the encoder's three-bit `output_bits`.

## 4. Coded 8PSK symbol SER

Each selected TCM edge emits one coded 8PSK symbol. Reference symbol indices
are built on the evaluation side by encoding each reference input pair from
M1 initial state `(0,0)`, then mapping the resulting `(c2,c1,c0)` output bits
through ADR-002's explicit `assumed_natural_binary` mapping. Decoded symbol
indices are obtained by mapping the `output_bits` on the selected decoded
hypothesis edges through that same mapping. Do not use hypothesis IDs as phase
indices and do not map decoded input bits directly without re-encoding.

The present mapping is bijective over all eight labels: natural-binary indices
0 through 7 correspond to the eight distinct three-bit labels. For a run of
`F` edges:

```text
symbol_errors = sum(reference_symbol_index[k] != decoded_symbol_index[k])
total_symbols = F
SER = symbol_errors / total_symbols
```

This is coded-symbol SER. Information-bit BER, coded-symbol SER, and optional
edge/path mismatch are distinct measures. Edge mismatch is not called SER.
The independent utilities count symbol-index arrays supplied by evaluation;
the mapping helpers explicitly derive those arrays from M1 reference encoding
and decoded hypothesis `output_bits`.

## 5. Run-level counts and pooled aggregation

One run is one independent coded sequence with its own signal/noise realization
and decoded result. Preserve each run's raw `(bit_errors,total_bits,
symbol_errors,total_symbols)` record and run provenance. Across runs, sum the
four primary counts and calculate pooled ratios from the totals:

```text
pooled BER = sum(run.bit_errors) / sum(run.total_bits)
pooled SER = sum(run.symbol_errors) / sum(run.total_symbols)
```

Do not substitute the unweighted mean of per-run BER/SER when run lengths
differ. Utilities are deterministic, use no RNG, and perform no hidden
normalization or length trimming.

## 6. Noise, signal energy, and SNR audit

| Quantity | Current implementation fact | Evaluation consequence |
|---|---|---|
| M1 constellation | `modulation.psk8.constellation()` is `exp(j*2*pi*m/8 + j*phase_offset)`; each 8PSK symbol has unit complex magnitude. | Symbol-rate `Es=1` before channel gain under this discrete convention. |
| M3 signal | Complex baseband; `receiver.iq.symbols_to_iq_waveform()` repeats each complex symbol exactly 8 times (rectangular ZOH), without `1/sqrt(8)` scaling. | Per-sample signal power is `|h|^2`; the discrete sum of squared sample magnitudes over one symbol is `8|h|^2`. Physical energy additionally needs a sample interval/pulse convention. |
| Rate | M1 sends two information bits for each 8PSK coded symbol. | At symbol rate and unit gain, `Eb=Es/2=1/2`; with real static gain `a`, symbol-rate `Es=|a|^2` and `Eb=|a|^2/2`. Under an unscaled 8-sample discrete sum, the corresponding sums are `8|a|^2` and `4|a|^2` per information bit. These are different energy conventions, not interchangeable SNR definitions. |
| M2 AWGN | `awgn_noise_variance(EbN0_dB, bits_per_symbol=2, energy_per_symbol=1)` returns complex `N0=Es/(k*10^(Eb/N0/10))`; `add_awgn()` gives each real/imag component variance `N0/2` on a 1-D symbol-rate sequence. | M2 has a declared symbol-rate AWGN convention, with defaults `Es=1`, `k=2`. It does not accept the B5c/B5d 8-sample observation window or a channel gain estimate. |
| M3 Rician channel | `PathSpec.average_power` is relative to `Es=1`; coefficients are complex and truth is returned separately. AWGN is a separate operation. | `average_power`, K-factor, channel realization, and noise power must be explicit; the M3 API does not define one combined Eb/N0 experiment. |
| M3 fluctuating noise | For each I/Q component, `x[i+1]=alpha*x[i]+sigma*z[i]`, `alpha=exp(-4/n)`, `sigma=sqrt(2)*sqrt(1-exp(-8/n))/n`; independent Gaussian innovations are used across quadratures/time, with default initial I=Q=0. | At `n=8`, `alpha=exp(-0.5)` and stationary per-component variance is `1/32` (complex variance `1/16`); the zero initial condition gives a transient variance. This is temporally correlated noise and is not an AWGN SNR calibration. |
| Reconstruction likelihood | ADR-005 uses explicit `beta>0` in `exp(-beta*F_rx)`. | `beta` is a project pseudo-likelihood scale, not noise variance, SNR, or a Gaussian covariance. |

The eightfold sample repetition alone does not preserve the discrete sum energy
of a symbol. An SNR comparison gate remains **BLOCKED** until a shared time/energy
normalization, channel/noise realization, covariance, and receiver observation
contract is explicitly selected. Do not transfer M2 AWGN scaling or article [A]
noise parameters to B5c/B5d by assumption.

## 7. Matched-baseline requirements

**MATCHED BASELINE — BLOCKED.** M2 hard/soft Viterbi currently accepts
symbol-rate complex observations. Its soft metric compares normalized
constellation points using complex squared Euclidean distance; its hard metric
uses demodulated labels. It has no input for the B5c/B5d 8-sample aggregate
window, its ADR-012 quadrature transform, receiver-side channel-estimate
trajectory, or ADR-005 `beta`. M2 assumes unit-energy constellation samples;
the reconstructed path uses sample-summed residual costs and potentially
explicit estimated initial coefficients. These are not presently matched
conditions.

A future matched comparison must share reference bits, M1 encoding and mapping,
the same underlying received realization, sequence length/boundaries, channel
and noise realization, termination/final-state policy, SNR/energy convention,
and an explicit CSI condition. It must mark oracle-CSI versus estimated-CSI
conditions separately. The minimum next work is a declared common waveform/noise
normalization and an adapter that presents matched observations to M2 and B5c/B5d
without discarding or silently changing the noise statistics. No such adapter
or comparison is implemented in M5a.

## 8. Randomness and paired runs

Future Monte Carlo run records should include explicit run ID; seed or
`SeedSequence` lineage; separately identified data, channel, and noise streams;
reconstruction profile; `beta`, `alpha_prime`, `K_tilde`, `mu0`; initial
estimator state; sample and symbol origins; independent-sequence length; and
receiver version/config provenance. Receiver A and receiver B must receive the
same reference bits and the exact same received sample array for a paired run.
Giving separate generators the same integer seed is not sufficient when RNG
call graphs differ. Reference data is passed only to evaluation after receiver
processing.

## 9. Statistical uncertainty

BER/SER calculated from counts are point estimates. Errors within a trellis
sequence can be dependent; the individual bit/symbol outcomes must not
automatically be treated as independent Bernoulli trials. Independent coded
sequences are the natural resampling unit. A cluster bootstrap over independent
sequence records is a proposed future method, subject to an explicit policy for
confidence level, replicate count, resampling unit, and zero-error/small-sample
reporting. M5a computes no confidence intervals. A zero observed error count is
reported as zero empirical BER/SER for the observed sample, not proof that the
underlying error probability is zero.

## 10. Reproducibility and READY/BLOCKED gates

The utility result is reproducible from exact input arrays and stores raw counts;
it uses no random source. Future experiment artifacts must retain per-run input
provenance and raw counts, not only plotted ratios.

| Gate | Status | Reason |
|---|---|---|
| Exact BER/SER counting for supplied arrays | READY | Strict validation, exact lengths, raw counts, deterministic ratios. |
| Mapping M1 reference bits and decoded path edges to coded symbol indices | READY | Uses M1 encoder/hypotheses and explicit ADR-002 mapping. |
| Pooled run aggregation | READY | Sums primary counts; unequal run lengths are handled correctly. |
| Small paired B/C cluster-bootstrap diagnostic | READY for exploratory reporting | M5f implements the accepted paired-cluster contract; intervals remain small-sample diagnostics, not validated performance evidence. |
| Physical SNR sweep / general M2 matched comparison | BLOCKED | Narrow ADR-015 oracle-CSI discrete controls are allowed; physical calibration and adaptive CSI parity are not specified. |
| Confidence intervals | READY under ADR-014 for independent-run clusters | Do not interpret small/rare/degenerate intervals as proof of an advantage or zero true BER/SER. |
| Paper 1.5 dB reproduction claim | BLOCKED | Source metric, source parameterization, baseline and experiment remain unresolved. |

### ADR-014 — accepted paired cluster-bootstrap policy

**Status: accepted by explicit user decision 2026-10-28.** Resample complete
independent coded-sequence records as clusters, preserving each run's paired
B/C integer counts. Use the same resampled run indices for both modes, pool raw
counts within each replicate, report two-sided 95% percentile intervals from
2000 replicates, and record an explicit bootstrap seed. Warn for small, rare,
all-zero, identical, imbalanced, or degenerate samples. These intervals are
exploratory diagnostics and do not automatically establish a performance gain.
The exact quantile method and warning heuristics are specified in
`M5_BOOTSTRAP_STATISTICAL_CONTRACT.md`.

## M5b smoke-run extension

The first received-to-bits smoke harness is an evaluation-side deterministic
composition. It requires a run ID, `F`, explicit reference bits, real gain,
finite complex perturbation array of shape `(8F,)` and its provenance, sample
origin, first symbol label, estimator initial time, complete validated inactive
reconstruction config, monolithic/segmented mode, explicit partition when
segmented, and initial CSI provenance. The harness generates
`M1 -> ADR-002 -> M1 8PSK -> M3 rectangular ZOH -> real gain + explicit
perturbation`, then invokes B5c or B5d and only afterward evaluates the held
reference bits/path outputs with M5a.

The report's initial estimate is explicitly oracle-initialized for a noiseless
correct-model check and is passed as fixed configured I/Q estimate. It is not
passed as channel truth and is not a general CSI initialization method. The
three sample perturbation arrays and one deterministic stress array have no
AWGN/AR(1), SNR, or covariance interpretation. No RNG, Monte Carlo, SNR sweep,
baseline comparison, CI, or performance claim was part of this M5b extension.
At that stage ADR-014 was proposed; M5f later accepted it and implemented the
paired cluster-bootstrap procedure documented below. See
`M5_SMOKE_EXPERIMENT_REPORT.md` for the historical M5b inputs and counts.

## M5c sample-energy and noise audit

The detailed source/API audit is in `M5_NOISE_BASELINE_CALIBRATION_AUDIT.md`.
M2 AWGN uses one symbol-rate complex observation and returns total complex
variance `N0=Es/(2·10^(Eb/N0/10))` at its default rate-2/3 information-bit
count; M3's waveform helper repeats each unit-magnitude symbol eight times
without scaling. Thus the same real-gain `a` has symbol-rate discrete energy
`a²` and sample-sum energy `8a²`. Physical energy needs an explicit sampled
complex-envelope convention and `Δt`.

The M3 fluctuating-noise function is an explicit AR(1) quadrature generator,
not an automatically applied AWGN channel. Its eight-sample mean variance is
conditional on explicit `n`, initial state, and innovation assumptions; ADR-012
does not claim independent noise. Pure `evaluation.signal_diagnostics`
functions measure arrays and evaluate caller-supplied covariance only; they
do not define a model or enter B5c/B5d.

ADR-015 now accepts a narrow discrete-AWGN paired control only: iid circular
complex noise per sample with explicit `sigma_squared`, one shared received
buffer, and M2 observations formed as mean-of-8 divided by explicit oracle
real gain `a`. B5 uses that buffer with oracle-initialized frozen estimates.
Only `effective discrete gamma_b=4a²/sigma_squared` is reported; physical HF
`Eb/N0` and adaptive/non-oracle matched comparisons remain **BLOCKED**.
At the M5d stage ADR-014 was still proposed; M5f later accepted and implemented
the independent-run paired cluster-bootstrap policy.

## M5d paired M2/B5 control

`evaluation.matched_m2_observation` performs the exact mean-of-eight and
explicit `/a` operation from one immutable sample buffer, with absolute
window labels. `evaluation.matched_m2_b5_experiment` generates at most one
explicit PCG64 iid circular complex AWGN realization (or accepts an explicit
noise array), forms one received buffer, and composes the existing M2 soft
Viterbi and B5c/B5d entry points. It computes BER/SER afterward in evaluation.
No M1/M2/M3/B4/B5 mathematical kernel changed. The run record stores a buffer
hash and provenance rather than reference arrays in receiver results.

For frozen correct-model coefficients, M2's normalized soft branch cost and
B5's sample-summed residual differ by a positive `8a²` factor and a
hypothesis-independent per-symbol offset. Small controls verify the identity
numerically and show matching unique-optimum paths. This is a paired control,
not a validated performance comparison. Physical calibration, adaptive or
non-oracle CSI comparison, correlated noise, SNR sweeps, Monte Carlo, and
confidence intervals and adaptive/non-oracle CSI comparisons remained blocked
at the M5d stage. M5f later accepted ADR-014 and implemented exploratory
cluster intervals; open scientific questions and `paper_exact:false`,
`receiver_enabled:false` remain unchanged.

## M5f paired adaptive B/C evaluation

The accepted ADR-014 policy is implemented in
`evaluation/paired_cluster_bootstrap.py`; the fixed exploratory study is
configured in `configs/m5f_paired_monte_carlo.json`. It uses separate data,
noise, and bootstrap seeds, 12 independent sequences of 32 symbols, one shared
received buffer per B/C pair, and M5e's existing receiver composition. See
`M5_PAIRED_MONTE_CARLO_REPORT.md` for raw per-run records, pooled point
estimates, all six intervals, and diagnostic flags. The interval excludes zero
for the observed Delta in this run, but warnings and the small sample prevent
treating it as validated evidence of a general effect.

## M5g proposed preregistered design

`M5_PREREGISTERED_EXPERIMENT_DESIGN.md` and
`configs/m5g_experiment_design_draft.json` propose, but do not authorize, a
future paired confirmatory study. The primary candidate estimand is pooled
`DeltaBER=BER_C-BER_B` at a proposed 5 dB effective discrete gamma stratum;
the grid is 0/5/10/15 dB with `a=0.75`. M5f's adaptive-worse outcome is
retained verbatim and does not tune the candidate policy. A separate
30-sequence-per-stratum F=256 pilot is proposed only for variance planning;
its runs must not enter confirmation. Final sample size remains BLOCKED until
the absolute interval half-width and compute budget are approved and pilot
variation is available. No M5g stochastic experiment or parameter search was
run. Secondary gamma, initial-mismatch, and parameter results are descriptive
only absent an approved multiplicity policy. ADR-014 remains the fixed paired
cluster-bootstrap contract; `paper_exact:false` and `receiver_enabled:false`
remain unchanged.

## M5h-prep independent pilot candidate

`M5_PILOT_PREPARATION_CONTRACT.md` defines the validated candidate protocol
and `configs/m5h_pilot_draft.json` is its explicit machine-readable draft.
The candidate remains proposed and unauthorized. The evaluation-side validator
checks all strata, ADR-015 sigma conversion, primary 5 dB role, B/C parity,
8sps origins, seed-root separation, unique run IDs, and ADR-014 settings before
the guarded runner can reach an injected per-run executor. With
`execution_authorized=false`, the runner raises before seed derivation or any
callback, so no bits, noise, or decoder are generated.

Pilot, evaluation, data, noise, and bootstrap have separate domain-separated
SeedSequence derivations. Pilot raw records are partitioned and named so they
cannot be mistaken for confirmatory records; M5f stays historical and excluded.
Numerical decoder failures remain explicit records, are not imputed or dropped,
and block pooled metrics when an output is missing. The pilot runner does not
produce pooled inference. The pilot itself, confirmatory inference, and any
resource benchmark remain BLOCKED until the candidate is approved and execution
is explicitly authorized. Candidate workload is 120 sequences, 30,720 symbols,
61,440 information bits, 245,760 received samples, and at least 240 decoder
passes; these counts imply no runtime estimate.


### M5h-run outcome

The user separately authorized a bounded `m5h_pilot_only` execution, recorded in an immutable run-specific approved config. The M5h draft remains proposed and unauthorized. The independent planning pilot completed all 120 planned runs (30 each at effective discrete gamma_b 0/5/10/15 dB), with 0 numerical failures and 360 diagnostic/receiver decode calls. Results and per-run checkpoints are documented in `M5_INDEPENDENT_PILOT_REPORT.md` and stored in the separate `outputs/m5h_independent_pilot/` namespace. Pilot records are not confirmatory evaluation records. The observed primary 5 dB run-level standard deviation supplies a provisional candidate `R_approx=28` for epsilon=0.02; sample-size approval and confirmatory inference remain BLOCKED. This pilot does not support a performance claim.


### M5i confirmatory design preparation

M5i freezes a candidate single-stratum design at 5 dB effective discrete gamma_b, F=256, and recommended R=100. Its primary contrast is pooled `DeltaBER=BER_C-BER_B`; epsilon=0.02 is a precision target only. The explicit design validator and deterministic manifest cover 100 planned evaluation IDs and reuse only the reserved M5h evaluation seed roots. They produce no bits, noise, decoder calls, or bootstrap replicates. M5i is `proposed_confirmatory`, unauthorized, and out of execution scope. Missing valid B/C output blocks full-design inference, while finite unstable runs and high BER remain included. See `M5_CONFIRMATORY_DESIGN_CONTRACT.md`; M5j requires a separate immutable authorization.

### M5j completed confirmatory evaluation

M5j used the separate immutable `m5j_confirmatory_only` approval and completed exactly 100/100 preregistered 5 dB effective discrete gamma_b runs. Counts, paired received hashes, seeds, bootstrap recomputation, resources, warnings, and limits are in `M5_CONFIRMATORY_EVALUATION_REPORT.md`. The primary pooled DeltaBER was 0.3655078125 with ADR-014 95% paired cluster-bootstrap CI [0.35548681640625, 0.37578173828125]; no confirmatory runs were added or removed. This conclusion applies only to the fixed reconstructed_offline single-path discrete-AWGN comparison, not physical HF, paper-exact reception, or general HF performance. The worker's console-print error after durable summary completion is disclosed in the report; run checkpoints and independent summary verification are intact. No subsequent experiment is automatically authorized.

### M5k post-confirmatory read-only audit

M5k independently replayed pooling and ADR-014 bootstrap statistics from the saved 100 M5j paired checkpoint counts only. It did not invoke the receiver, create bits/noise/received buffers, rerun M5h/M5j, search parameters, or change historical output bytes. The audit found 100 unique IDs and received hashes, 100 complete pairs, 0 numerical failures, 51,200 bits and 25,600 symbols per receiver, manifest-matched evaluation seeds, and raw totals B `1079/51200` bit errors and `1003/25600` symbol errors, C `19793/51200` and `17956/25600`. All six 2,000-replicate same-index cluster-bootstrap intervals replayed from saved counts under ADR-014 with seed `3940591365597190145` and `numpy.quantile(method="linear")`; the primary interval half-width `0.0101474609375` met epsilon `0.02`.

This confirms only the fixed-policy M5j contrast under the preregistered reconstructed_offline L=1 ADR-015 discrete-AWGN profile. It does not establish a cause for adaptive C's higher error rates. Checkpoints lack per-symbol pre/post estimator states, posterior vectors, innovations, and candidate metrics, so no such histories or historical branch metrics are reconstructed. The M5j post-summary worker exit code 1 was caused by printing `failure_count` instead of schema field `failure_record_count`; a synthetic regression now guards reporting and summary-consistent process status. The historical exit code and original code fingerprint remain as recorded. See `M5_POST_CONFIRMATORY_SCIENTIFIC_AUDIT.md`; new experiments and tuning remain unauthorized without a separately frozen protocol and authorization.
