# M5h independent planning pilot report

**Status:** completed authorized independent planning pilot; **not confirmatory performance evidence**, **not a paper-exact receiver**, and **not a physical HF Eb/N0 comparison**. All noise-axis labels below are effective discrete `gamma_b`.

## Authorization and provenance

The user explicitly authorized this bounded M5h pilot in the current Codex execution instruction. Execution scope was `m5h_pilot_only`. The proposed M5g/M5h draft files were not changed; the separate immutable run config is [approved_run_config.json](../outputs/m5h_independent_pilot/20261029T180438711965Z/approved_run_config.json). Source draft SHA-256: `1ccd5a2ac2ba397b0f1c33bcdf1480851d4a9fa8930fa4032044e92c205da2b8`; approved config SHA-256: `b072cd4f5cc7d4997df27827fe2195145f0e51bce03629a4f36428baf303fcf6`; canonical config fingerprint: `ad7ce90a96a0cf87b6d00d79afb5963c6bbf6b4d5421cc161fcf8650f8ae2dcb`. The 24-file code fingerprint is in the approved config and summary. A Git revision was unavailable because this workspace is not a Git worktree.

Runtime authorization timestamp: `2026-10-29T18:04:38Z`. Execution was guarded by the approved status/scope, explicit parameter, stratum, ADR, seed separation, and B/C parity validators before any stochastic generation or decoding.

## Frozen pilot design

Channel: reconstructed offline, L=1, real `a=0.75`, zero delay, normalized 8PSK, rectangular ZOH, 8 samples/symbol. ADR-015 circular complex AWGN variance was `sigma_squared = 4*a*a / 10^(gamma_b_eff_dB/10)`.

| Effective discrete gamma_b | sigma_squared | Runs | Role |
|---:|---:|---:|---|
| 0 dB | 2.25 | 30 | secondary descriptive |
| 5 dB | 0.7115124735378853 | 30 | primary |
| 10 dB | 0.225 | 30 | secondary descriptive |
| 15 dB | 0.07115124735378854 | 30 | secondary descriptive |

Each independent sequence had F=256 TCM symbols and 512 information bits. Sample, symbol, and estimator-time origins were all zero. B and C shared the same data, received buffer, reference bits, initial full/fluctuating IQ estimate `(0.42, 0.91)`, beta `0.7`, and time labels. B used frozen policy `alpha_prime=1`, `K_tilde=(0,0)`, `mu0=(0,0)`; C used adaptive policy `alpha_prime=0.85`, `K_tilde=(0.35,-0.2)`, `mu0=(0,0)`. No parameter tuning was performed.

## Execution and resources

Runs were processed deterministically by ascending gamma stratum (0, 5, 10, 15 dB), then ascending run index (001–030). All 120 of 120 planned runs produced valid paired B/C output; each stratum completed 30/30. Numerical failures: 0; unfinished runs: 0; receiver decode calls: 360 (the diagnostic API also performs its oracle diagnostic decode). Each run was checkpointed atomically. Output is in the separate `outputs/m5h_independent_pilot/20261029T180438711965Z/` namespace; the checkpoint/summary records are pilot-only and are not evaluation records.

Measured wall time was 251.0627 s. The single worker's RSS was sampled 1,002 times at 0.25 s intervals; sampled peak was 46,190,592 bytes (about 44.05 MiB), with zero sampling failures. This was a periodic parent-process monitor, not a hard OS RSS cap. Available system memory before execution was 5,429,579,776 bytes, measured with Windows `GlobalMemoryStatusEx`. Output size was 5,917,519 bytes, below the 100 MiB target. The run stayed within the 30-minute budget and one-process constraint. These are observed resource measurements, not extrapolated runtime estimates.

## RNG independence and resume provenance

The run used the accepted domain-separated `SeedSequence` procedure and `PCG64`. Each seed is derived from the protocol version plus `(partition code, stratum index, run index, stream code)`; partition codes distinguish pilot from future evaluation, and stream codes distinguish data, noise, and bootstrap. Pilot data/noise/bootstrap branches are separate from their evaluation counterparts. Run IDs and stratum IDs are deterministic; duplicate IDs are rejected. The audit found 120 unique data seeds and 120 unique noise seeds, with no data/noise seed collisions; bootstrap seeds are separately derived and were not used to draw data or noise. B/C consumed the same received buffer per run, and the receiver had no hidden RNG draws. The exact derivation constants and seed records are retained in the approved config, manifest, and per-run checkpoints. The separate bootstrap precision diagnostic used a pilot-bootstrap child branch and did not generate received data.

## Pilot results (descriptive only)

For each complete stratum, rates pool raw integer counts over the 30 coded-sequence clusters. Intervals use ADR-014: 2,000 same-index paired cluster resamples, two-sided 95% percentile CI, explicit bootstrap seed, and `numpy.quantile(method="linear")`. They are pilot descriptions, not confirmatory or population-level conclusions.

| gamma_b eff. | B bit errors / BER | C bit errors / BER | DeltaBER (95% paired cluster CI) | B symbol errors / SER | C symbol errors / SER | DeltaSER (95% CI) | flags |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0 dB | 3988/15360; 0.2596354 | 7262/15360; 0.4727865 | 0.2131510 [0.1915999, 0.2337272] | 3509/7680; 0.4569010 | 6111/7680; 0.7957031 | 0.3388021 [0.3096289, 0.3652376] | none |
| 5 dB (primary) | 349/15360; 0.0227214 | 5929/15360; 0.3860026 | 0.3632813 [0.3443994, 0.3809261] | 332/7680; 0.0432292 | 5463/7680; 0.7113281 | 0.6680990 [0.6394401, 0.6938835] | none |
| 10 dB | 0/15360; 0 | 5388/15360; 0.3507813 | 0.3507813 [0.3341113, 0.3668685] | 0/7680; 0 | 5187/7680; 0.6753906 | 0.6753906 [0.6455729, 0.7016927] | `rare_error_count`, `degenerate_bootstrap_distribution`, `bootstrap_interval_unreliable` |
| 15 dB | 0/15360; 0 | 5240/15360; 0.3411458 | 0.3411458 [0.3308561, 0.3521501] | 0/7680; 0 | 5024/7680; 0.6541667 | 0.6541667 [0.6384115, 0.6710970] | `rare_error_count`, `degenerate_bootstrap_distribution`, `bootstrap_interval_unreliable` |

The primary 5 dB paired run-level differences were `d_r=(C_bit_errors_r-B_bit_errors_r)/(2F)`, with 30 valid independent sequences and sample standard deviation `s_d=0.053093594133490844`. All 120 adaptive trajectories were finite, and all 120 had the finite coefficient-error-growth diagnostic flag. Per-stratum means of C maximum coefficient-error norm / maximum update-increment norm / posterior entropy were: 0 dB `1.7192 / 0.5563 / 2.1636`; 5 dB `1.6353 / 0.4150 / 2.2567`; 10 dB `1.6031 / 0.3319 / 2.2847`; 15 dB `1.5659 / 0.3012 / 2.2947`. Finite trajectories were retained with diagnostics; the growth flag is not by itself a numerical failure or a performance conclusion.

## Sample-size planning

For candidate absolute 95% DeltaBER half-width `epsilon=0.02`, the initial normal approximation gives `R_approx=ceil((1.96*s_d/epsilon)^2)=28` independent clusters per stratum, using the primary pilot's `s_d`. This is only a planning candidate: `s_d` is uncertain with 30 pilot clusters, the formula does not guarantee a percentile cluster-bootstrap CI half-width, and zero-error or degenerate samples can make naive precision estimates misleading. `R=28` is **not approved**.

A separate, deterministic precision diagnostic resampled the 30 complete primary pilot records into 2,000 pseudo-studies of 28 paired clusters. Its empirical 2.5/97.5 percentiles were `[0.3428414, 0.3825352]`, half-width `0.0198469`. This is a pilot-record bootstrap diagnostic (no new received signals), not a population CI, coverage guarantee, or approval of R. The confirmatory sample-size gate therefore remains BLOCKED pending scientific review and design approval.

## M5f boundary, limitations, and gates

M5f remains a separate historical exploratory experiment with its original config, raw records, BER/SER, bootstrap output, and warning flags intact. None of its 12 short runs entered this pilot. M5f was not treated as an independent M5g-design pilot and is excluded from future confirmatory evaluation records. M5h records are also isolated from evaluation records.

| Gate | Status | Basis |
|---|---|---|
| Approved bounded pilot execution and guard | READY / completed | explicit user authorization, separate approved run config, scope-limited guard |
| Planned independent pilot coverage | READY / completed | 120/120 valid, 30 in each stratum, no decoder failures |
| Resource and checkpoint accounting | READY / measured | one process, within observed time/RSS/output budgets, 120 atomic run records |
| Primary pilot variability estimate | READY for provisional planning | 30 complete paired clusters and finite `s_d`; not confirmatory |
| Confirmatory sample size and inference | BLOCKED | R=28 is only a candidate; precision is uncertain and requires user/design approval |
| Scientific performance or receiver claim | BLOCKED / out of scope | pilot only; reconstructed receiver, effective discrete gamma axis |

The pilot does not establish adaptive gain, general HF performance, physical Eb/N0 gain, paper-exact reconstruction, or reproduction of a 1.5 dB result. `paper_exact:false`, `receiver_enabled:false`, accepted ADRs, proposed ADR-009/011, and open SCI-02/SCI-03/SCI-METRIC-02 remain unchanged. No new ADR is required for this bounded pilot; any change to accepted science/statistical contracts requires a separate decision.

Before any confirmatory study, the user must review the pilot evidence and decide whether to approve a target precision and run-count procedure (including whether further pilot-record precision analysis is sufficient), define the treatment of missing decoder outputs for the confirmatory estimand, approve resource limits, and explicitly authorize a separately frozen confirmatory design. No next study was launched.

## Reproducible artifacts

- [Approved run configuration](../outputs/m5h_independent_pilot/20261029T180438711965Z/approved_run_config.json)
- [Execution manifest](../outputs/m5h_independent_pilot/20261029T180438711965Z/execution_manifest.json)
- [Pilot summary](../outputs/m5h_independent_pilot/20261029T180438711965Z/summary.json)
- [Precision diagnostic script](../outputs/m5h_independent_pilot/20261029T180438711965Z/precision_diagnostic.py)
- [Precision diagnostic results](../outputs/m5h_independent_pilot/20261029T180438711965Z/precision_diagnostic_5db.json)


## M5i design preparation note (pilot records unchanged)

For M5i sample-size planning, all 30 saved 5 dB checkpoint records were re-read. Their run-level differences reproduce `s_d=0.053093594133490844` exactly at stored precision and `R_approx=28`; the B/C primary raw bit error sums reproduce 349 and 5,929. This audit did not alter any pilot file, bootstrap output, warning, seed, or checkpoint. The recommended M5i candidate is R=100; see `M5_CONFIRMATORY_DESIGN_CONTRACT.md`. No confirmatory records or new BER evidence were generated by M5i.
