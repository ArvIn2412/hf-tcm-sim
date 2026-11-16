# M5f — Paired cluster-bootstrap contract

**Status:** ADR-014 accepted for exploratory paired evaluation. The interval
method does not by itself establish a validated performance advantage.

## Estimand and independent unit

One cluster is one complete, independent, terminated-by-observation TCM
sequence of `F` symbols; ADR-013 uses initial trellis state `(0,0)`, free final
state, and no tail bits. Bits and symbols inside a cluster are not resampled
independently. For each independent run, B and C have identical information
bits, one common immutable received buffer, channel/noise realization, sample,
symbol and estimator clocks, beta, and initial estimator state. Only their
explicit coefficient update policies differ.

For integer run counts, pooled point estimates are:

```text
BER_B = sum(B_bit_errors) / sum(total_bits)
BER_C = sum(C_bit_errors) / sum(total_bits)
SER_B = sum(B_symbol_errors) / sum(total_symbols)
SER_C = sum(C_symbol_errors) / sum(total_symbols)
DeltaBER = BER_C - BER_B
DeltaSER = SER_C - SER_B
```

Each bootstrap replicate samples `R` run indices with replacement from
`0..R-1`, then applies that same ordered index vector to both B and C. It sums
the selected raw integer counts before computing ratios. The replicate table
columns are fixed as `ber_b, ber_c, delta_ber, ser_b, ser_c, delta_ser`.

## Percentile interval and reproducibility

The policy uses a two-sided 95% percentile interval with 2000 replicates for
the accepted preset; the general function requires the replicate count,
confidence level and nonnegative bootstrap seed explicitly. NumPy `PCG64`
generates the resample indices. Bounds use `numpy.quantile` with
`method="linear"` at `(1-confidence_level)/2` and its complement. The ordered
run IDs, resample-index matrix, seed, bit generator, quantile method, and
read-only replicate estimates are retained in the result.

Data and noise use separate `SeedSequence` roots and separate per-run child
streams; the bootstrap seed is a third independent explicit input. Data and
noise child spawn keys and derived seeds are recorded per run. B and C do not
draw randomness: M5e creates one received realization and passes it through
both modes. Bootstrap draws occur only after the run records exist.

## Diagnostic warning heuristics

These thresholds are warning heuristics, not adequacy criteria or hypothesis
tests:

| Flag | Trigger |
|---|---|
| `too_few_independent_runs` | Fewer than 20 independent sequence clusters. |
| `all_zero_errors` | All B and C bit and symbol error counts are zero. |
| `all_runs_identical` | Every run has the same denominators and B/C error-count tuple. |
| `rare_error_count` | Any pooled B/C bit or symbol error count is below 20. |
| `strong_cluster_imbalance` | Largest per-run bit denominator exceeds twice the median. |
| `degenerate_bootstrap_distribution` | At least one reported metric has no bootstrap variation. |
| `bootstrap_interval_unreliable` | Any small, rare, imbalanced, or degenerate condition above is present. |

The accepted M5f run has only 12 clusters, so it necessarily emits the
small-run warning. A degenerate `[0,0]` interval for a receiver with zero
observed errors is not evidence that its true error probability is zero. A
Delta interval excluding zero in a small exploratory sample is also not, by
itself, a validated or general performance claim. Errors may be dependent
within one sequence; the procedure assumes independence across independently
seeded sequences.

## Input and mutation rules

Each run ID must be unique, B/C denominators must match, counts must be valid
M5a `ErrorCounts`, and at least one run is required. Bootstrap replicate count
is a positive integer; confidence level lies strictly in `(0,1)`; seed is a
nonnegative integer. Input records and explicit resample indices are not
mutated. Empty, duplicate, non-integer, negative, or out-of-range indices are
rejected.

The implementation returns pooled integer counts and rates separately from
the six percentile intervals. It does not compute p-values, adjust for
hyperparameter tuning, estimate physical `Eb/N0`, or decide whether a sample is
large enough for scientific inference. ADR-014 does not authorize tuning,
SNR sweeps, or paper-performance claims.

## M5g preregistration use

The proposed design keeps this accepted resampling procedure fixed at 2000
replicates, explicit bootstrap seed, paired run indices, pooled raw counts,
two-sided 95% percentile bounds, and `numpy.quantile(method="linear")`.
M5g proposes a separate pilot to estimate between-sequence paired variation;
pilot clusters are never pooled with confirmatory clusters. The actual
confirmatory run count is BLOCKED until a practical DeltaBER interval
half-width and compute budget are approved and pilot variation is available.
The M5f 12-cluster interval remains exploratory and is not a sample-size
justification. Preserve all implementation warnings, including
`all_runs_identical` and `strong_cluster_imbalance` when they occur.

## M5h-prep pilot and sample-size boundary

The machine-readable M5h candidate and execution guard are specified in
`M5_PILOT_PREPARATION_CONTRACT.md`. ADR-014 remains unchanged: one coded
sequence per cluster, same-index paired B/C resampling, pooled raw counts,
2000 replicates, explicit bootstrap seed, two-sided 95% percentile interval,
and NumPy `method="linear"`. The 5 dB pooled DeltaBER is the only proposed
primary contrast; other gamma intervals are pointwise descriptive and do not
provide simultaneous coverage.

After a separately approved pilot, an initial planning approximation may use
`d_r=(bit_errors_C_r-bit_errors_B_r)/(2F)` and
`R_approx=ceil((1.96*s_d/epsilon)^2)`. This normal approximation does not
guarantee the percentile cluster-bootstrap interval half-width. Pilot `s_d`
from 30 clusters is uncertain, and zero-error or degenerate records may make
it misleading. Do not approve an evaluation run count from this formula alone;
pilot records remain outside confirmatory aggregates. Numerical failures are
retained and block pooled metrics if a receiver output is missing, pending a
preapproved interpretation policy.


### M5h independent pilot results

The separately authorized M5h planning pilot completed with 30 independent paired sequence clusters in each of four effective discrete gamma_b strata. Per-stratum pooled counts and ADR-014 intervals are in `M5_INDEPENDENT_PILOT_REPORT.md`; the machine-readable records are isolated under `outputs/m5h_independent_pilot/`. The primary 5 dB pilot had 30 valid clusters and no warning flags. The 10 and 15 dB pilot intervals carry `rare_error_count`, `degenerate_bootstrap_distribution`, and `bootstrap_interval_unreliable`; both B policies had zero errors there. These are pointwise pilot diagnostics only. No multiplicity correction was added.

The primary pilot's `s_d=0.053093594133490844` yields candidate `R_approx=28` for epsilon=0.02 using the preregistered normal approximation. A 2,000 pseudo-study resampling diagnostic of pilot records gave empirical half-width 0.0198469 at R=28, but this neither guarantees the future percentile CI width nor approves the run count. Confirmatory sample-size and inferential gates remain BLOCKED. Pilot records must never be pooled with confirmatory records.


### M5i planned confirmatory use

M5i retains ADR-014 unchanged for its sole future primary condition: 100 independent complete-sequence clusters at 5 dB effective discrete gamma_b, 2,000 same-index paired B/C resamples, 95% two-sided percentile intervals using NumPy `method="linear"`, pooled integer counts, and one explicit evaluation bootstrap seed. The six reported metrics are BER_B, BER_C, DeltaBER, SER_B, SER_C, and DeltaSER. Warning flags remain visible; `[0,0]` is not proof of zero BER and an interval containing zero is not evidence of equivalence. No bootstrap was run on new data in M5i; its planned manifest includes only seed provenance.

### M5j observed primary bootstrap

The completed M5j dataset used 100 independent sequence clusters, 2,000 same-index paired B/C resamples, NumPy `quantile(method="linear")`, and explicit evaluation bootstrap seed `3940591365597190145`. The six intervals are recorded in `M5_CONFIRMATORY_EVALUATION_REPORT.md`; the DeltaBER interval was [0.35548681640625, 0.37578173828125] (half-width 0.0101474609375). An independent recomputation from the saved run checkpoints matched all six intervals and the warning flags. Epsilon=0.02 was met; it was not used as a stopping or run-extension condition. Results remain specific to the frozen 5 dB effective discrete gamma_b reconstructed_offline profile. Existing warning and zero-interval interpretations remain in force.
