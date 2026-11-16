# M9a fixed-policy comparison design

**Status:** proposed and unauthorized. Classification: M8 exploratory
closeout and M9 independent fixed-policy study design; not M8 validation, not
new performance evidence, and not a paper-exact receiver.

## Research question and provenance

M8's eight-arm TRAIN grid selected historical frozen B. `anch_a085_k025` was
the runner-up and was identified after the M8 policies had been observed.
M9 therefore asks a new prospective question: on fresh independent
constant-gain reconstructed-offline samples, what is the paired BER difference
between frozen B and that one fixed anchored policy? The candidate is frozen
before any M9 data are generated. M9 was not preregistered before M8; M8's
post-selection interval is not independent validation, and M5j is not
validation for M9.

Primary estimand:

```text
DeltaBER = BER(anch_a085_k025) - BER(historical_frozen_B)
```

Positive values mean the anchored policy has higher BER. Secondary estimand
is pooled raw-count DeltaSER. Coefficient-error trajectories are descriptive
evaluation-only diagnostics. Numerical failures are reported separately and
block full-design inference. No equivalence, noninferiority, or improvement is
presumed.

## Fixed policies and profile

| Policy | alpha_prime | K_tilde | mu0 | Initial fluctuating IQ | Initial full IQ |
|---|---:|---|---|---|---|
| `historical_frozen_B` | 1.00 | (0, 0) | (0, 0) | (0.42, 0.91) | (0.42, 0.91) |
| `anch_a085_k025` | 0.85 | (0.0875, -0.05) | (0.42, 0.91) | (0, 0) | (0.42, 0.91) |

Both use beta 0.7. No additional candidate or replacement is allowed. The
profile is `reconstructed_offline`, L=1, real gain 0.75, zero delay,
normalized 8PSK, rectangular ZOH, 8 samples/symbol, ADR-002 mapping, ADR-005
pseudo-likelihood, ADR-012 observed IQ, ADR-013 conditional full Viterbi, and
ADR-015 independent circular complex AWGN. Effective discrete gamma-b is
5 dB and `sigma_squared = 0.7115124735378853`; this is not physical HF Eb/N0.
True gain and reference bits stay in simulation/evaluation and are never
passed to the receiver.

## Prospective partition and RNG plan

The proposed evaluation partition has 100 new independent sequences of F=256
symbols and 512 information bits each. Both policies receive the same
received buffer within a run. The order is ascending zero-based run index
0..99, with IDs `m9_fixed_anchored_vs_frozen_v1:evaluation:run-001` through
`run-100`.

| Namespace | Master root | Stream code |
|---|---:|---:|
| Data | 2027020101 | 11 |
| Noise | 2027020102 | 23 |
| Bootstrap | 2027020103 | 37 |
| Metadata | 2027020104 | 41 |

Proposed derivation is domain-separated
`SeedSequence(master_seed, spawn_key=(1295337521, 901, run_index,
stream_code))`, with PCG64 initialized from a generated uint64 child seed in a
future separately approved execution. Bootstrap uses the bootstrap root with
partition 901, run index 0, and stream code 37. M9a records roots and spawn
rules only; it does not derive child seeds or initialize M9 RNGs. These roots
are distinct from M5-M8 data/noise/bootstrap namespaces, including M8
validation roots. No data, noise, or bootstrap stream is created in M9a.

## Estimation and failure contract

Primary and secondary estimates pool raw integer error counts. ADR-014
intervals use 2,000 paired resamples of whole independent sequence clusters,
95% percentile bounds, and `numpy.quantile(method="linear")`. Individual bits
are not treated as independent clusters. A future numerical/decoder failure
is recorded and blocks a full-design inference; incomplete sequences are
reported without replacement seeds. Valid zero counts remain zero. There is
no data-dependent stopping, missing-output imputation, or policy fallback.
The observed M8 contrast does not define an equivalence/noninferiority margin;
any such margin would require separate justification before independent
observations.

## M6 mechanism boundary

H1/H5/H6 describe reconstructed-model policy and feedback sensitivities, not
an optimal policy or a cause of M5j errors. H2 (author quadrature), H3 (author
innovation semantics), and H4 (author correction convention) remain source
unresolved. H7 (frame-constant versus symbol-adaptive model) and H8 (ADR-005
versus a source-faithful likelihood) remain model distinctions whose
contribution to performance is unresolved. M9 does not resolve any of these
source questions; SCI-02, SCI-03, and SCI-METRIC-02 remain OPEN.

## Workload, guards, and limitations

Candidate workload: 100 sequences, 2 fixed policies, 200 paired policy
records and decoder passes, 51,200 information bits per policy, 25,600 coded
symbols per policy, and 204,800 unique received samples. Proposed execution is
single-process with one atomic checkpoint per sequence, 900 seconds wall
clock and periodic 1.5 GiB RSS monitoring. These are proposed limits, not
measurements or a guaranteed runtime. They must be frozen again in a
run-specific approved config.

The draft
[`m9a_fixed_policy_study_draft.json`](../configs/m9a_fixed_policy_study_draft.json)
is validated by an evaluation-side design validator. Its authorization guard
blocks before RNG, data/noise, or decoder callbacks. It remains
`proposed / false / none`; no approved run config is created. M9 results, if
separately authorized and executed, would estimate only this fixed contrast
under the constant-gain reconstruction. They would not establish physical HF
performance or source-faithful behavior. `paper_exact:false` and
`receiver_enabled:false` remain.

The variable-channel question is separate and described in
[`M9_VARIABLE_CHANNEL_RESEARCH_NOTE.md`](M9_VARIABLE_CHANNEL_RESEARCH_NOTE.md).

## M9b separately authorized evaluation (2026-10-30)

The M9a draft above remains `proposed / false / none`. A separate
M9b-only authorization froze an approved snapshot with draft SHA-256
`a6be31a2225aeaee48fffec5ff6f868866773a1087978a561e4cadea78e1d5ac`, approved
config SHA-256 `72dcc41f8cfc20028a1c2ea0ea15d0edc3fc6d941a322a3622e58ae1b099cad4`,
and runtime source fingerprint
`93530a40e4c95d24324150da37c423dfbbfc4945ddf4a9e80b0b154d987f04c1`. The
real deterministic receiver smoke passed before evaluation stream
initialization. All 100 planned paired runs completed with 200 policy records,
200 experimental decoder calls, 100 unique received hashes, and no failures.

Raw counts were B 1,130/51,200 bits and 1,050/25,600 symbols, anchored
1,072/51,200 bits and 1,001/25,600 symbols. `DeltaBER=-0.0011328125` with a
95% paired cluster-bootstrap CI `[-0.00322265625, 0.00068359375]`;
`DeltaSER=-0.0019140625` with CI `[-0.0053125, 0.0011328125]`. Both intervals
include zero; this does not establish equivalence or noninferiority. The
anchor was a post-hoc M8 runner-up, so this is not validation of the M8 grid.
Full results and limitations are in
[`M9_FIXED_POLICY_EVALUATION_REPORT.md`](M9_FIXED_POLICY_EVALUATION_REPORT.md).
No validation, final, variable-channel, or other experiment was run, and no
receiver mathematics changed.
