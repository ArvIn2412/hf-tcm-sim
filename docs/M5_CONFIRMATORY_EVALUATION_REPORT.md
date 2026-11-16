# M5j independent confirmatory evaluation report

**Confirmatory evaluation of a fixed reconstructed_offline L=1 discrete-AWGN receiver comparison, NOT a paper-exact joint receiver, NOT a physical HF Eb/N0 comparison, and NOT a reproduction of paper results.** This report covers only the separately authorized M5j experiment. M5f remains historical exploratory and M5h remains an independent planning pilot; neither was pooled into M5j.

## Frozen design and authorization

Approved immutable run config: `configs/m5j_confirmatory_approved_run.json`; SHA-256 `8a9cb4c2d42a0b7014a40d5b83b9da13e7d1a65fe2fa3a68e1d90d5a53607840`. It records explicit user authorization through this M5j instruction, `design_status=approved_confirmatory`, `execution_authorized=true`, and `execution_scope=m5j_confirmatory_only`. The M5i draft and manifest remain unchanged. An earlier preflight snapshot, `configs/m5j_confirmatory_approved_run_preflight_superseded.json`, was not executed; it was superseded before the first run following a preflight code correction.

Frozen design/manifest fingerprints: `6e42b5003e3804c89266cd78dcf3702d9d8159ed4ed46b81acf962bbff4db1e4` and `6b63e12f6463680af603944a43e576afa15e08b1b84155273fbbbc42c4fb5b15`. The approved code fingerprint for the M5j runner is `ebb588d63c73e80372b568ef8ea10df95882fba3f8f13d4da6fcd0e9e6f2e930`; runtime was Python 3.13.13, NumPy 2.3.3, PCG64. Git revision was unavailable because the workspace is not a Git worktree.

The sole primary condition was 5 dB effective discrete gamma_b, a=0.75, ADR-015 sigma_squared=0.7115124735378853, R=100 independent sequences, F=256 symbols, 512 information bits and 2048 complex received samples per sequence. Noise was independent circular complex AWGN, sqrt(sigma_squared/2)*(X+jY), generated once per run and shared by B/C. Waveform was normalized 8PSK rectangular ZOH at 8 samples/symbol. Sample, symbol and estimator origins were all zero.

B was frozen: alpha_prime=1, K_tilde=(0,0), mu0=(0,0). C was adaptive: alpha_prime=0.85, K_tilde=(0.35,-0.2), mu0=(0,0). Both used initial full/fluctuating I/Q estimate (0.42,0.91), beta=0.7, the same reference bits, received buffer, initial state, trellis, termination behavior and time labels. Only estimator update policy differed. There was no tuning or outcome-dependent stopping.

## Execution and provenance

All planned IDs run-001 through run-100 completed in deterministic manifest order. There were 100 valid paired outputs, zero numerical failures and zero not-completed IDs. Output records are isolated under `outputs/m5j_confirmatory/20261029T-run/`. Independent verification found 100 unique IDs and received hashes, same received hash for B/C within each run, seeds matching the frozen evaluation manifest, 51,200 information bits and 25,600 coded symbols per receiver. Each mode decoded 25,600 symbols. The actual diagnostic API also ran its evaluation-only oracle control, so there were 300 decoder passes total.

Only evaluation roots were used: data 2026110101, noise 2026110102, bootstrap 2026110103. Seed derivation was `SeedSequence(master, spawn_key=(1295337521,211,1,zero_based_run_index,stream_code))`, stream codes data=11, noise=23, bootstrap=37. Derived streams used PCG64; bootstrap seed was 3940591365597190145. No M5h pilot namespace or M5f record was used. Checkpoints contain seeds, counts, hashes, status and compact diagnostics, not reference bits, received arrays or ChannelTruth.

`independent_verification.json` independently re-sums checkpoint counts and reruns ADR-014 on the saved counts. Its B/C totals, six intervals, warning flags, ID set, per-run received hashes and seed provenance match the saved execution summary.

## Results

| Measure | Frozen B | Adaptive C | C - B |
|---|---:|---:|---:|
| Information bit errors / bits | 1,079 / 51,200 | 19,793 / 51,200 | - |
| Pooled BER | 0.02107421875 | 0.38658203125 | **0.3655078125** |
| Coded-symbol errors / symbols | 1,003 / 25,600 | 17,956 / 25,600 | - |
| Pooled SER | 0.0391796875 | 0.70140625 | **0.6622265625** |

Primary estimand was pooled DeltaBER=BER_C-BER_B at 5 dB effective discrete gamma_b. DeltaSER was secondary. Point estimates use pooled integer counts, not mean run rates.

## ADR-014 paired cluster bootstrap

The analysis used 100 independent sequence clusters, 2,000 same-index paired B/C resamples, 95% two-sided percentile intervals, pooled integer counts per replicate, NumPy `quantile(method="linear")`, and the explicit independent bootstrap seed above.

| Metric | 95% percentile CI |
|---|---:|
| BER_B | [0.017265625, 0.02498193359375] |
| BER_C | [0.37710888671875, 0.395900390625] |
| DeltaBER | [0.35548681640625, 0.37578173828125] |
| SER_B | [0.032734375, 0.045705078125] |
| SER_C | [0.6882421875, 0.7135244140625] |
| DeltaSER | [0.6474599609375, 0.6771494140625] |

Primary CI half-width was 0.0101474609375; the candidate epsilon=0.02 precision target was met. The target did not control stopping or R. Bootstrap warnings were empty. An interval excluding zero does not establish equivalence, generality or receiver performance beyond this profile.

## Numerical and coefficient diagnostics

All decoder outputs were valid. All 100 adaptive coefficient trajectories were finite and retained. Across 25,600 adaptive full-I/Q increments, increment-norm minimum/median/maximum were 0.0011519989 / 0.1733958345 / 0.5307475518. Final full-I estimate component means were (0.0002324491,-0.0047189956); component ranges were [-0.6369456371,0.5482927199] and [-0.4153344494,0.4730906790]. Final coefficient-error diagnostic mean/median/maximum were 1.0933055 / 1.1073315 / 1.6477646. These are descriptive evaluation-side diagnostics only; they did not affect updates, tuning, exclusions or the primary estimand.

## Resources, wrapper note and scientific interpretation

Available system memory before approval was 5,494,489,088 bytes. Parent monitoring sampled the worker every 0.25 s: wall time 149.5761 s, 597 RSS samples, observed peak 47,329,280 bytes. RSS is periodic monitoring, not a hard OS cap. Neither the 900 s nor 1.5 GiB limit was reached.

The worker persisted all 100 checkpoints and its complete summary, then its console-print path raised `KeyError`: it requested `failure_count` while the saved summary schema uses `failure_record_count`. Worker exit code was 1 after the completed result had been durably written. The parent retained it and independently verified checkpoints and bootstrap. No run was retried or regenerated. This post-completion reporting defect did not change evaluation outputs or inference.

Under this one preregistered 5 dB reconstructed_offline L=1 ADR-015 discrete-AWGN profile, C had higher BER and SER than frozen B. This is limited to this specified comparison. It is not physical HF Eb/N0 gain, paper-exact reception, reproduction of 1.5 dB, general HF-channel performance, proof of optimality or a universal adaptive effect. No additional gamma points were run.

| Gate | Status |
|---|---|
| Frozen profile, authorization and 100 planned IDs | READY |
| Completeness and paired provenance | READY, 100/100, zero numerical failures |
| Primary inference under frozen policy | READY for this fixed profile |
| epsilon=0.02 precision target | MET; not a run-extension rule |
| Generalization, physical-HF or paper-exact claim | BLOCKED / out of scope |
| Additional experiment, tuning, sweep or M5k | NOT AUTHORIZED by this run |

M5f/M5h historical outputs and M5i draft design/manifest remain unchanged. `paper_exact:false`, `receiver_enabled:false`, ADR statuses and open SCI questions remain unchanged. No new ADR is required. The next step is scientific review of this fixed-profile result and its assumptions; no study launches automatically.

## Verification

`python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` passed: 721 passed in 3.89s. `ruff check src tests` passed: all checks passed. `ruff format --check src tests` passed: 119 files already formatted. Tests generated no stochastic received data. Existing M5i preservation tests verified historical M5h artifact hashes and all 120 checkpoint hashes.

## M5k post-confirmatory audit addendum (2026-10-30)

M5k independently re-read the 100 M5j checkpoints and replayed integer-count pooling and the ADR-014 bootstrap. It created no receiver observations and changed no M5f/M5h/M5j historical output bytes. The raw-count totals, all six bootstrap intervals, IDs, evaluation seed provenance, paired received hashes, denominators, and zero numerical failures agree with `summary.json` and `independent_verification.json`. The only audit discrepancy is binary float representation: count-derived `DeltaBER=0.3655078125` is stored by subtraction as `0.36550781250000003`; this is immaterial (~3e-17), not a count or inference discrepancy. Full details and M5j integrity digests are in [`M5_POST_CONFIRMATORY_SCIENTIFIC_AUDIT.md`](M5_POST_CONFIRMATORY_SCIENTIFIC_AUDIT.md).

The historical M5j worker exit code remains 1: after it had written the complete summary and all checkpoints, the final console path indexed nonexistent `failure_count`; the actual schema field was `failure_record_count`. M5k fixed only this reporting path and made the worker's exit status follow summary counts and run-record status. A synthetic-summary regression passed; historical M5j files and the original approved runtime fingerprint were not rewritten. Future runtime code fingerprints therefore differ from M5j's recorded fingerprint. No receiver mathematics, scientific configuration, checkpoint schema, or bootstrap behavior changed.

The confirmatory conclusion remains limited to the predefined B/C policies under the fixed ADR-015 `L=1` discrete-AWGN profile. Adaptive C had higher pooled BER (`DeltaBER=+0.3655078125`, 95% paired cluster-bootstrap CI `[0.35548681640625, 0.37578173828125]`) and higher secondary SER (`DeltaSER=+0.6622265625`, CI `[0.6474599609375, 0.6771494140625]`). The primary half-width was `0.0101474609375`, meeting `epsilon=0.02`. This is not a universal adaptive claim, paper-method failure, physical HF `Eb/N0` result, or general multipath result. Estimator mechanism attribution remains blocked because M5j did not preserve per-symbol pre/post states, innovations, posterior vectors, or candidate-metric histories.
