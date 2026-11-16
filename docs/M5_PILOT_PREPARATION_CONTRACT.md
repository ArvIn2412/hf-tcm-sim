# M5h-prep — independent pilot preparation contract

**Result:** validated pilot execution preparation, **NOT executed pilot**,
**NOT new BER evidence**, **NOT performance claim**. This document and
`configs/m5h_pilot_draft.json` define a candidate protocol only.

## Scope and scientific boundary

The candidate uses `reconstructed_offline`, L=1, real positive gain, zero
delay, normalized 8PSK, rectangular ZOH at 8 samples/symbol, ADR-012 observed
IQ, ADR-013 conditional full Viterbi, and ADR-015 independent circular
complex sample AWGN. Every noise-axis label is **effective discrete
`gamma_b`**, not physical HF `Eb/N0`.

Accepted ADRs remain 001/002/003/004/005/006/007/008/010/012/013/014/015;
ADR-009 and ADR-011 remain proposed. SCI-02, SCI-03, and SCI-METRIC-02 remain
open. `paper_exact:false` and `receiver_enabled:false` remain. No mathematical
kernel, M1–M3, B4/B5 behavior, or M5f artifact is changed.

M5f remains a historical exploratory experiment. Its configuration, raw run
records, BER/SER, bootstrap output, and warning flags are preserved as-is. M5f
is neither an independent M5g/M5h pilot nor input to future confirmatory
records.

## Candidate design — not approved

| Setting | Candidate value |
|---|---:|
| Real gain `a` | 0.75 |
| Effective discrete `gamma_b` grid | 0, 5, 10, 15 dB |
| Primary stratum | 5 dB |
| Symbols per sequence `F` | 256 |
| Independent sequences per stratum | 30 |
| Total independent sequences | 120 |
| B policy | alpha_prime=1; K_tilde=(0,0); mu0=(0,0) |
| C policy | alpha_prime=0.85; K_tilde=(0.35,-0.2); mu0=(0,0) |
| Shared B/C initial full and fluctuating estimate | (0.42,0.91) |
| Shared beta | 0.7 |
| Sample/symbol/estimator origins | 0 / 0 / 0 |
| Candidate absolute 95% DeltaBER CI half-width | 0.02; requires approval |
| Confirmatory run count | unset; BLOCKED |

For each stratum, `gamma_b_eff_linear=10^(gamma_b_eff_dB/10)` and
`sigma_squared=4*a*a/gamma_b_eff_linear`, per ADR-015:

| effective discrete gamma_b (dB) | linear | sigma_squared |
|---:|---:|---:|
| 0 | 1.0000000000 | 2.2500000000 |
| 5 | 3.1622776602 | 0.7115124735 |
| 10 | 10.0000000000 | 0.2250000000 |
| 15 | 31.6227766017 | 0.0711512474 |

The candidate fixes project settings for a proposed comparison; they are not
article-derived recursion settings or validated as useful/optimal. B and C
must use identical bits, received samples, gain/noise realization, origins,
initial estimate, beta, and termination. Only the registered update policy
differs. Reference bits and ChannelTruth remain evaluation-side only.

## Configuration validation and execution gate

`configs/m5h_pilot_draft.json` is a standalone explicit candidate, including
the full inactive receiver profile. The evaluation-side
`m5h_pilot_protocol.py` validator rejects missing fields, unsupported
scientific status, invalid strata or ADR-015 calibration, non-8sps timebase,
incomplete B/C parity, conflicting seed namespaces, duplicate run IDs,
inconsistent profile settings, or any bootstrap contract that differs from
ADR-014. It does not fill missing values with defaults.

The guarded `run_m5h_pilot` checks, before deriving per-run provenance or
calling its injected run executor:

1. configuration is validated;
2. `execution_authorized is True`;
3. `design_status == "approved"`;
4. an explicit run executor is supplied.

The checked-in JSON remains `design_status="proposed"` and
`execution_authorized=false`. Tests use spies to verify zero callback/decoder
calls when either gate fails. M5h-prep does not change the authorization
field. There is no CLI/default path that silently converts this draft into an
executable config.

The current M5e/M5f APIs were audited directly. The paired Monte Carlo config
requires an explicit embedded reconstruction profile, one `sigma_squared`
per run batch, shared B/C state, and separate data/noise roots; its runner
derives child streams internally and then invokes the adaptive diagnostic
composition. The adaptive diagnostic API accepts explicit reference bits,
gain, sigma/noise, origins, receiver config, and B/C recursion operands. The
ADR-014 bootstrap API requires paired raw count records, replicate count,
confidence level, and seed. The M5h schema is evaluation-side and keeps the
per-stratum noise variance and independent pilot/evaluation namespaces
explicit; no M1–M3/B4/B5 API or mathematical kernel was altered.

## RNG provenance and independence

The candidate declares six distinct master roots:

| Partition | Data | Noise | Bootstrap |
|---|---:|---:|---:|
| Pilot | 2026102901 | 2026102902 | 2026102903 |
| Evaluation | 2026110101 | 2026110102 | 2026110103 |

For each data/noise stream, derive a child as follows:

```text
spawn_key = (
    0x4D354831,                  # protocol version M5H1
    101 if pilot else 211,       # partition domain
    stratum_index,               # 0..3, fixed grid order
    run_index,                   # zero-based within stratum
    11 for data or 23 for noise,
)
child = numpy.random.SeedSequence(master_root, spawn_key=spawn_key)
seed = int(child.generate_state(1, dtype=numpy.uint64)[0])
generator = numpy.random.Generator(numpy.random.PCG64(seed))
```

The bootstrap child uses its own bootstrap master root, the same protocol and
partition/stratum coordinates, run index zero, and stream code 37. It is
recorded per stratum and consumed only after raw records exist. It cannot
advance either signal/data or noise generator. Each raw run record must retain
partition, stratum ID, unique run ID, master roots, spawn keys, derived seeds,
bit generator, F, sigma, and all three origins. Run IDs include study,
partition, gamma, and one-based run number. Duplicate IDs and derived data/noise
seed collisions are rejected. Pilot and evaluation roots and partition domain
codes are distinct, and the same run identifier cannot occur across the two
partitions. Distinct seeds alone are not treated as proof that two algorithms
are independent; stream identity, derivation lineage, and separation of
implementation responsibilities must also be recorded and reviewed.

## Failure handling

| Class | Required handling |
|---|---|
| A. Invalid experimental configuration | Reject before data/noise generation or decoder invocation. |
| B. Numerical decoder failure | Keep a failure record with run/stratum IDs, exception class/detail, and last available diagnostics. Never impute zero errors, silently remove the run, or compute pooled metrics as if all runs completed. Mark pooled inference BLOCKED if receiver output is missing. |
| C. Finite but unstable coefficient trajectory | Retain the numerically valid run and counts; attach the predeclared trajectory diagnostics. No automatic exclusion. |
| D. Valid decoded sequence with high BER | Retain all observed errors and denominators without exception. |

The evaluation-side wrapper preserves callback exceptions as failure records;
any failure blocks pooled metrics. A policy for including/excluding a numerical
failure in a confirmatory estimand cannot be inferred from ADR-014 and needs
researcher/user review. Therefore the confirmatory gate stays **BLOCKED** until
that interpretation is fixed before a confirmatory run.

## Statistical contract and sample-size planning

Keep ADR-014 unchanged: independent cluster is one coded sequence; use the
same-index paired B/C resamples; pool raw integer counts; use 2000 bootstrap
replicates, an explicit bootstrap seed, a two-sided 95% percentile interval,
and `numpy.quantile(method="linear")`. Preserve all warning flags. Primary is
pooled `DeltaBER = BER_C - BER_B` at 5 dB. DeltaSER and other strata are
secondary descriptive results. Pointwise intervals do not provide simultaneous
coverage; no multiplicity correction is added. Pilot estimates are not
population-level effects and never enter confirmatory records.

After a separately authorized pilot, at the primary stratum compute paired
run-level differences
`d_r=(bit_errors_C_r-bit_errors_B_r)/(2F)`, and their pilot standard deviation
`s_d`. For an approved absolute half-width `epsilon`, an initial approximation
is:

```text
R_approx = ceil((1.96*s_d/epsilon)^2)
```

This is a normal approximation, not a guarantee of the requested half-width
for the percentile cluster-bootstrap interval. With only 30 pilot sequences,
`s_d` is itself uncertain. Zero errors, all-identical paired differences, or
other degenerate samples can make the approximation misleading; do not insert
an unapproved variance floor or tune from pilot/evaluation effects. If approved,
a later planning step may resample only the pilot records to simulate bootstrap
interval widths. That is distinct from generating new received signals. Do not
declare a confirmatory `R` until the pilot is reviewed, the target precision
and resource budget are approved, and the precision check is acceptable.

## Workload and resource measurement

The candidate pilot workload is:

| Quantity | Count |
|---|---:|
| Independent sequences | 4 strata * 30 = 120 |
| TCM symbols | 120 * 256 = 30,720 |
| Information bits | 2 * 30,720 = 61,440 |
| Received samples | 8 * 30,720 = 245,760 |
| Minimum B/C decoder passes | 2 * 120 = 240 |

These are operation counts, not a runtime or memory estimate. After explicit
authorization, measure only the smallest approved unit using the exact
environment; record repeated wall-clock measurements and peak process memory,
then project the full workload with uncertainty. Do not launch a benchmark that
silently expands into a Monte Carlo batch. No benchmark ran in M5h-prep.

## Readiness gates and required decisions

| Gate | M5h-prep status |
|---|---|
| Candidate config parsing/round-trip and explicitness | READY; tests pass |
| ADR-015 variance conversion and 5 dB primary stratum | READY; machine-checked |
| B/C candidate policy parity and 8sps origins | READY; machine-checked |
| Pilot/evaluation/data/noise/bootstrap stream derivation | READY as a deterministic protocol; no streams used for data generation |
| Execution guard with zero-call spy | READY; both authorization and status gates tested |
| Actual pilot execution | BLOCKED; `execution_authorized=false` |
| Candidate parameters/design approval | BLOCKED; still proposed |
| Confirmatory R / inference | BLOCKED; pilot, precision target, resource budget, and failure interpretation unresolved |
| Multiplicity policy for inferential secondary results | BLOCKED unless separately approved |
| Physical HF Eb/N0, paper-exact result, receiver activation | BLOCKED/out of scope |

Before a future M5h-run, approve or revise: the 0/5/10/15 dB effective
discrete gamma grid and 5 dB primary contrast; `a=0.75`; fixed B/C policies,
initial state and beta; F=256; 30 pilot runs per stratum; origins; the 0.02
candidate absolute DeltaBER half-width or a replacement; the compute/memory
budget and bounded measurement method; and how numerical failures block or
otherwise affect the pilot estimand. Then explicitly authorize the separate
pilot. No new ADR is needed to apply already accepted ADR-014/015; request a
new ADR only if the scientific model or accepted statistical contract changes.
