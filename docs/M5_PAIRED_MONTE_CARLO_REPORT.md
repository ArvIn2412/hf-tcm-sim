# M5f — Paired B/C Monte Carlo and cluster-bootstrap report

**Status:** isolated paired Monte Carlo and cluster-bootstrap evaluation for
`reconstructed_offline` single-path receiver, **NOT validated performance
advantage**, **NOT paper-exact receiver**, **NOT reproduction of paper
results**. This is one small diagnostic experiment. No SNR sweep, matched M2
comparison, physical HF `Eb/N0` claim, hyperparameter tuning, or statistical
power claim was made.

## Accepted policy and scope

ADR-014 was accepted by explicit user decision on 2026-10-28. The bootstrap
unit is one full independently generated TCM sequence. Each replicate samples
`R` run indices with replacement and uses those same indices for B and C,
pools raw integer counts, and calculates 95% two-sided percentile bounds from
2000 replicates. Quantiles use NumPy `quantile(method="linear")`; bootstrap
RNG is PCG64 with its own explicit seed. Exact rules and diagnostic thresholds
are in `M5_BOOTSTRAP_STATISTICAL_CONTRACT.md`.

Only the accepted narrow profile was used: `reconstructed_offline`, L=1,
positive real gain, zero delay, normalized 8PSK, rectangular ZOH, 8
samples/symbol, ADR-012 observation, ADR-005 pseudo-likelihood, ADR-013
conditional Viterbi, and ADR-015 iid circular complex sample AWGN. The result
does not measure physical HF `Eb/N0` and does not reproduce an author result.

## Fixed experiment configuration

The complete validated preset is
[`configs/m5f_paired_monte_carlo.json`](../configs/m5f_paired_monte_carlo.json).
It was fixed before the reported Monte Carlo run; parameters were not tuned on
these evaluation outcomes.

| Setting | Value |
|---|---|
| Independent clusters | 12 complete sequences |
| Symbols / information bits per run | `F=32` / 64 |
| Total observations | 384 TCM symbols / 768 information bits |
| Real channel gain | `a=0.75` |
| ADR-015 complex sample noise power | `sigma_squared=0.08` |
| Effective discrete `gamma_b` | `4a²/sigma_squared = 28.125` |
| Likelihood scale | `beta=0.7` |
| Initial fluctuating and full estimate | `(0.42,0.91)` for both; explicitly mismatched from `(0.75,0.75)` |
| B frozen policy | `alpha_prime=1`, `K_tilde=(0,0)`, `mu0=(0,0)` |
| C adaptive policy | `alpha_prime=0.85`, `K_tilde=(0.35,-0.2)`, `mu0=(0,0)` |
| Absolute sample origin / first symbol | `O=23`, `f=5` |
| Initial estimator clock | `i=41`, advanced one tick per completed symbol |
| Independent-run length / profile | One continuous 32-symbol sequence; `reconstructed_offline` |
| Data / noise / bootstrap master seeds | `2026102801` / `2026102802` / `2026102803` |
| Bootstrap replicates / confidence | `2000` / `0.95` |

`mu0_C=0` is explicit. With the common B/C starting state, zero `mu0` keeps
the initial decomposition valid while B's `(1,0,0)` policy leaves its state
unchanged. The active C correction comes from its nonzero `K_tilde`. This is a
fixed experimental choice, not a claim that nonzero `mu0` is physically
incorrect.

## Paired generation and random streams

For each run, one PCG64 `SeedSequence` child from the data master generates
`2F` information bits. A different `SeedSequence` root generates a distinct
child and derived seed for one PCG64 ADR-015 noise realization. M5e then
constructs exactly one complex received buffer for that run and applies B and
C to it. The records contain identical B/C received SHA-256 values. Bootstrap
uses its own explicit seed after all receiver runs are complete. Stream
provenance, child spawn keys, and derived seeds are stored per run.

The reference sequence and real gain remain on the evaluation side. B4d/B5b
receive no reference bits or true channel gain. B and C have identical
initial-state arrays, beta, clock and temporal labels; only their recursion
policies differ. B is checked to remain frozen. No `ChannelTruth` is stored in
receiver diagnostics or run records.

The run labels are absolute symbols `5..36`, estimator ticks `41..72`, and
sample indices `63..318` (eight samples for each symbol). B4d generates the
candidate metrics causally from the pre-observation state; the B/C cost,
posterior and decoded outputs are evaluated after their respective passes.

## Per-run raw records

Each run has 64 bits and 32 coded symbols. `B bits/symbols` and `C
bits/symbols` below are integer error counts; full seed lineage and received
hash are in [`outputs/m5f_paired_monte_carlo_records.json`](../outputs/m5f_paired_monte_carlo_records.json).

| Run | Data seed | Noise seed | B bit / symbol errors | C bit / symbol errors | `DeltaBER_run` | `DeltaSER_run` |
|---|---:|---:|---:|---:|---:|---:|
| 001 | 3151400934972509396 | 57412267287805353 | 0 / 0 | 17 / 15 | 0.265625 | 0.468750 |
| 002 | 11710574484258325196 | 9982973875407554596 | 0 / 0 | 11 / 14 | 0.171875 | 0.437500 |
| 003 | 918178872071403978 | 11371361626945531011 | 0 / 0 | 18 / 16 | 0.281250 | 0.500000 |
| 004 | 15635414766950162297 | 15422394379121379096 | 0 / 0 | 7 / 7 | 0.109375 | 0.218750 |
| 005 | 10307589230630613200 | 3520697260329845331 | 0 / 0 | 19 / 17 | 0.296875 | 0.531250 |
| 006 | 9262947081818488530 | 17345473151255503959 | 0 / 0 | 15 / 17 | 0.234375 | 0.531250 |
| 007 | 1671934042555382828 | 16065790234097232387 | 0 / 0 | 8 / 8 | 0.125000 | 0.250000 |
| 008 | 1890019548370846629 | 15437496007456531884 | 0 / 0 | 21 / 21 | 0.328125 | 0.656250 |
| 009 | 13208812607633052515 | 14103929066862804741 | 0 / 0 | 17 / 17 | 0.265625 | 0.531250 |
| 010 | 8638687047913174414 | 11203629046436758456 | 0 / 0 | 19 / 15 | 0.296875 | 0.468750 |
| 011 | 2951811929519912032 | 17316664054690926703 | 0 / 0 | 20 / 18 | 0.312500 | 0.562500 |
| 012 | 5193221701988275946 | 13919778103237697613 | 0 / 0 | 17 / 16 | 0.265625 | 0.500000 |

All B/C pairs used the same received buffer within each run. C changed the
coefficient state in all 12 runs. Its terminal full estimates varied across
runs and moved away from the mismatched initialization in some quadratures;
this configuration shows substantial adaptive state movement, not a
convergence guarantee. Every run had more observed C errors than B. This is
the outcome of this fixed diagnostic configuration and is reported without
reversing or tuning it.

## Pooled counts and estimates

| Mode | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---:|---:|---:|---:|
| B mismatched frozen | 0 / 768 | 0.000000 | 0 / 384 | 0.000000 |
| C mismatched adaptive | 189 / 768 | 0.246094 | 181 / 384 | 0.471354 |
| `Delta = C - B` | — | **+0.246094** | — | **+0.471354** |

These are pooled raw-count ratios, not mean run rates. Negative Delta would
mean fewer observed C errors; here both pooled differences are positive.

## Paired bootstrap intervals

| Metric | Point estimate | Exploratory 95% percentile interval |
|---|---:|---:|
| `BER_B` | 0.000000 | `[0.000000, 0.000000]` |
| `BER_C` | 0.246094 | `[0.207031, 0.282552]` |
| `DeltaBER` | +0.246094 | `[+0.207031, +0.282552]` |
| `SER_B` | 0.000000 | `[0.000000, 0.000000]` |
| `SER_C` | 0.471354 | `[0.406250, 0.533919]` |
| `DeltaSER` | +0.471354 | `[+0.406250, +0.533919]` |

Diagnostic flags were `too_few_independent_runs`, `rare_error_count`,
`degenerate_bootstrap_distribution`, and `bootstrap_interval_unreliable`.
There were 12 clusters, below the documented 20-run warning heuristic; B had
zero errors, making its bootstrap distribution degenerate. The zero-width B
interval is not evidence of zero true BER/SER. The Delta intervals describe
this exploratory resampling distribution only; they do not validate a
population-level advantage/disadvantage or establish adequacy of the study.

## Readiness and scientific limits

- **Paired runner and cluster-bootstrap code:** READY for reproducible
  exploratory single-profile evaluation and raw-count reporting.
- **Pairing and reproducibility:** READY; B/C hashes and initial states match,
  and identical configuration/seeds reproduce run hashes, counts, and
  bootstrap resamples in tests.
- **Population performance claim / BER/SER curves:** BLOCKED pending a
  predeclared adequately sized design, sensitivity analysis, and independent
  scientific review. The 12-run study is too small and warning-flagged.
- **Physical HF `Eb/N0`, adaptive M2 parity, general complex fading/multipath,
  and paper 1.5 dB reproduction:** BLOCKED.

ADR statuses: accepted 001/002/003/004/005/006/007/008/010/012/013/014/015;
proposed 009/011. SCI-02, SCI-03 and SCI-METRIC-02 remain open.
`paper_exact:false` and `receiver_enabled:false` remain unchanged. No new ADR
is needed.

## M5g follow-up: proposed study design

The M5f result remains unchanged: B had zero observed errors while adaptive C
had 189 bit and 181 coded-symbol errors; C was worse in all 12 observed pairs.
Those data are exploratory, warning-flagged, and are not used to retune C. The
proposed future design is recorded in
[`M5_PREREGISTERED_EXPERIMENT_DESIGN.md`](M5_PREREGISTERED_EXPERIMENT_DESIGN.md)
with a non-executable configuration draft. It defines a candidate primary
DeltaBER at 5 dB and a 0/5/10/15 dB grid; pilot and confirmatory records have
separate seed namespaces. No pilot, new Monte Carlo, or sweep was run as part
of M5g. Sample size remains BLOCKED pending pilot variability, approved
precision target, and compute budget. Nothing in this design upgrades the M5f
result into population-level evidence.
