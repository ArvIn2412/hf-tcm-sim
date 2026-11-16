# REPRO-07 final report: paired experiment

## Verdict

**REPRO_07_PAIRED_EXPERIMENT_READY** for the paired runner, bounded pilot statistics, resume, and measured plots. This does not mean article-exact reproduction, physical Eb/N0 normalization, or general receiver superiority.

## Implementation

Added `src/hf_tcm/repro/paired_experiment.py`, `paired_experiment_plots.py`, `paired_experiment_cli.py`, and `energy_gain.py`. The API provides `ExperimentConfig`, `run_paired_trial`, `run_paired_experiment`, domain-separated seeds, ratio-of-sums aggregation, paired cluster bootstrap, hash-verified resume, atomic trial records, failure exclusion, and resource limits.

Each paired trial creates one REPRO-02 transmitter result and one REPRO-03 observation, then supplies the same receiver-facing observation to both receivers. `EvaluationTruth` is only used after both receiver calls. Outputs are under `outputs/repro07/`. The known-public static multipath control uses REPRO-06B and is recorded distinctly from the main REPRO-06C adaptive receiver. Other implemented controls include identity, static single path, Rician single path, unknown/static multipath, slow fading, and Rician AR(1).

The CLI is `python -m hf_tcm.repro.paired_experiment_cli --config <json>` with `--validate-only`, `--output`, and `--print-summary`. Plots are SVGs built from measured records. The energy-gain helper refuses to interpret sample-domain noise as physical SNR.

## Pilot results

`pilot_rician_ar1_f256_v1` completed 60/60 paired trials: 20 independent trials at each complex sample-domain noise variance 0.005, 0.05, and 0.2. Each frame had F=256 transitions and 512 information bits; both arms compared 10,240 bits per point. Both receivers used finite-depth Viterbi eta=20. The channel used delays [0,3], path powers [1,0.25], K [4,1], LOS phases [0,0.7] rad, and sample-level AR(1) rho=0.98.

Joint/Separate BER values were 0.000390625/0.14501953125, 0.0005859375/0.14609375, and 0.0017578125/0.1455078125. DeltaBER (Joint minus Separate) was -0.14462890625, -0.1455078125, and -0.14375. The 95% paired cluster bootstrap intervals were [-0.15869140625,-0.13007568359375], [-0.165234375,-0.12626953125], and [-0.1583984375,-0.12900390625]. Exact BER/SER counts and intervals are in `REPRO_07_BER_SER_RESULTS.md` and `outputs/repro07/pilot_rician_ar1_f256_v1/summary.json`.

This compares two complete receiver algorithms: adaptive ISI-aware joint channel processing versus hard demodulation and Hamming decoding without a multipath equalizer. It does not isolate the effect of Euclidean versus Hamming metrics. The measured differences apply only to this project-defined profile; they do not establish paper-exact or universal superiority.

Deterministic F=32 identity and public known-static multipath smoke cases recovered the payload without errors in both arms. These are integration controls, not statistical evidence.

## Long-frame resource check

One paired F=20,000 trial completed at variance 0.05. Joint had 16/40,000 bit errors (BER 0.0004); Separate had 6,019/40,000 (BER 0.150475); DeltaBER was -0.150075. Pair-SER was 12/20,000 versus 5,300/20,000. One independent pair cannot support a confidence interval or statistical conclusion. Measured receiver times were about 238.66 s Joint and 0.649 s Separate; this is one timing observation, not a benchmark. No long-frame multi-trial sweep was run.

## Reproducibility and verification

Bits, fading, and noise use separately domain-derived seeds keyed by experiment, grid point, and trial. Both receiver arms share one observation per trial. Resume was exercised on the pilot and long-frame check; valid records were verified and skipped without duplicate aggregation.

REPRO-07 targeted tests: **18 passed**. Full regression:
`python -m pytest -q --tb=short --maxfail=1 --basetemp %TEMP%\\hf-tcm-repro07-full-final -p no:cacheprovider`
— **1153 passed**. Scoped `ruff check` passed; scoped `ruff format --check` passed (7 files already formatted). `python scripts/verify_repro06b_artifacts.py` verified 76/76 historical bundle files and **694/694 M5-M10 fingerprints**.

`verify_experiment` passed all four REPRO-07 output roots. Their manifest SHA-256 values and parsed SVG counts:

| Output directory | Manifest SHA-256 | SVG files |
|---|---|---:|
| `pilot_rician_ar1_f256_v1` | `31d2527a3aba2f957adc7fbc3d1338385fc33ba148e5beffeac2e482497bcc45` | 15 |
| `long_frame_single_pair_resource_check_v1` | `a07036363d10c2282f501961a868f68594ce0ce4fe02aa358a4470c6e7352f18` | 6 |
| `smoke_identity_f32_v1` | `9ad058b53b8cddd372b14fa9fb471a6fa0100b0091f705a96340c373a8c3a273` | 9 |
| `smoke_known_static_multipath_f32_v1` | `f2dc1d7496a362c659074d321e8cdc831da627777c1381fab372a152a82cc416` | 8 |

All 60 pilot records have identical observation hashes for the paired record, Joint, and Separate arms. Median per-trial receiver times (seconds, not benchmark) across the three points were Joint/Separate: 7.277/0.0243, 5.305/0.0182, and 2.398/0.0111.

Root-wide `ruff check .` did not pass: traversal encountered ACL-denied paths and found 27 existing lint findings in generated `docs/figures/generate_thesis_figures.py`. Root-wide `ruff format --check .` failed during traversal with `Expected a ruff source file`. These unrelated generated artifacts were not changed. Scoped checks for the REPRO-07 Python files passed.

No REPRO-02 through REPRO-06C receiver/transmitter/channel mathematics, M5-M10 outputs, GUI, or accepted ADRs were changed. `paper_exact:false`, `receiver_enabled:false`, and existing open source-fidelity statuses remain unchanged. No GUI QA was needed. The only Monte Carlo series run here was the explicitly requested bounded 60-pair pilot.

## Subsystem statuses

- `PAIRED_OBSERVATIONS_VERIFIED`
- `MONTE_CARLO_RUNNER_READY`
- `BER_SER_STATISTICS_READY`
- `PAIRED_CONFIDENCE_INTERVALS_READY`
- `CHECKPOINT_RESUME_READY`
- `BER_SER_PLOTS_READY`
- `LONG_FRAME_RESEARCH_PRESET_READY` for a validated config and one bounded resource-check pair; a long-frame multi-trial study was not run.

## Limitations and next phase

The pilot is custom and project-defined. Its horizontal axis is complex sample-domain noise variance, not Eb/N0. It does not establish metric-only causality, equivalence, noninferiority, or universal superiority. No energy gain is reported; the helper only accepts physically defined measured SNR curves with a bracketed target BER.

The `article_oriented` validation mode enforces the verified 8-sample and eta=20 conventions and refuses an unspecified article channel profile. The available article-oriented identity control is an engineering control, not a noisy article reproduction. Missing source-defined noise/SNR values are not filled with invented defaults.

REPRO-08 should separately define and approve the physical SNR/Eb/N0 convention, confirmatory design, stopping/precision rules, and long-run resource budget. REPRO-08 was not started.
