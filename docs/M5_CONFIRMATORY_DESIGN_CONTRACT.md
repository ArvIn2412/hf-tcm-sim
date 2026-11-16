# M5i confirmatory design preparation contract

**Result:** pilot-informed confirmatory design preparation, **NOT executed confirmatory evaluation**, **NOT new performance evidence**. The current configuration is a draft and cannot execute. M5j requires a separately reviewed, immutable, run-specific authorization.

## Evidence phases and separation

1. **M5f:** historical exploratory paired experiment. Preserve its configuration, raw records, summaries, bootstrap output, warnings, and seeds. It was not used to tune M5i.
2. **M5g:** proposed confirmatory-design proposal; it was not itself executed as a confirmatory study.
3. **M5h:** completed independent planning pilot. Its raw records, checkpoint files, summary, bootstrap intervals, diagnostics, warning flags, seeds, and approved pilot config are unchanged and remain outside confirmatory records.
4. **M5i:** this pilot-informed design preparation and a planned-ID/evaluation-seed manifest. Seed derivation is deterministic metadata work; M5i generated no bits, received signals, noise, decoder output, or bootstrap records.
5. **M5j:** future independently seeded confirmatory evaluation, only after the user reviews and separately authorizes an immutable run-specific configuration. No M5h permission or pilot stream can authorize M5j.

The M5g and M5h draft configs remain `proposed` with `execution_authorized=false`; the approved M5h config is preserved as a historical pilot authorization scoped to `m5h_pilot_only`. The M5i draft is `design_status="proposed_confirmatory"`, `execution_authorized=false`, and `execution_scope="none"`.

## Scientific scope and frozen configuration

The estimand concerns only the difference between the specified frozen B and adaptive C reconstructed receivers under the fixed ADR-015 single-path discrete-AWGN profile. It does not test a paper-exact joint receiver or physical HF performance. All noise labels mean **effective discrete `gamma_b`**, never physical HF Eb/N0.

| Field | Frozen M5i candidate |
|---|---|
| Profile | `reconstructed_offline`; L=1; real gain `a=0.75`; zero delay |
| Waveform / modulation | normalized 8PSK; rectangular ZOH; 8 samples/symbol |
| Primary condition | effective discrete `gamma_b=5 dB` only |
| Noise variance | ADR-015 `4*a*a / 10^(gamma_b_eff_dB/10)` = `0.7115124735378853` |
| Sequence size | F=256 TCM symbols = 512 information bits |
| Independent sequences | R=100, each is one complete coded TCM sequence |
| Workload | 25,600 TCM symbols; 51,200 bits; 204,800 received complex samples; at least 200 B/C decoder passes |
| Origins | absolute sample=0; symbol=0; estimator time=0 |
| Shared B/C state | full_iq and fluctuating_iq `(0.42,0.91)`; beta=0.7; mu0 `(0,0)` |
| Frozen B | alpha_prime=1; K_tilde `(0,0)`; mu0 `(0,0)` |
| Adaptive C | alpha_prime=0.85; K_tilde `(0.35,-0.2)`; mu0 `(0,0)` |

Every pair has identical reference input bits, noisy received samples, initial estimator state, beta, origins, trellis, and termination rules. Only the estimator update policy differs. The complete explicit reconstruction profile is embedded in `configs/m5i_confirmatory_design_draft.json`; there are no implicit runtime defaults. Parameter values are frozen and are not selected or tuned from M5f/M5h outcomes.

The only primary estimand is pooled `DeltaBER = BER_C - BER_B` at 5 dB. `DeltaSER`, BER_B, BER_C, SER_B, SER_C, raw counts, denominators, failure counts, and coefficient trajectory diagnostics are secondary reports. The 0/10/15 dB results remain historical M5h pilot diagnostics; M5j must not automatically execute these strata or claim simultaneous four-point inference. One primary point does not establish general adaptive advantage or disadvantage.

## Pilot-informed sample-size recommendation

The 30 saved primary M5h checkpoints independently reproduce `s_d=0.053093594133490844` for `d_r=(C_bit_errors_r-B_bit_errors_r)/(2F)` and `R_approx=28` under the normal approximation with candidate `epsilon=0.02`. The raw records also reproduce 349 B and 5,929 C bit errors at 5 dB. The machine-readable pilot summary, 120-checkpoint inventory, approved config, execution manifest, and precision diagnostic hashes are recorded in the M5i draft.

Recommend R=100 paired independent sequences: it is an operationally conservative increase over the pilot approximation of 28, leaves margin for uncertainty in pilot `s_d`, and fits the completed pilot's observed workload as a planning budget. M5h took 251.0627 seconds for 120 F=256 sequences across four strata; simple proportional workload reference for 100 such sequences is about 209.22 seconds. This is not a runtime guarantee: hardware, code path, and per-run decode work may differ. The proposed 900-second M5j wall budget is bounded and exceeds the observed pilot duration; no benchmark was run in M5i.

The target 95% primary DeltaBER CI half-width `epsilon=0.02` is a precision target, not an early-stopping rule. R=100 is not a guarantee that the percentile cluster-bootstrap CI will meet that precision. If the observed interval is wider, do not extend R automatically; do not change R after inspecting errors, DeltaBER, or intervals.

## ADR-014 bootstrap contract

For complete valid M5j runs, use the accepted ADR-014 API and policy: one complete coded sequence per independent cluster; same-index paired B/C resampling; 2,000 replicates; two-sided 95% percentile bounds; NumPy `quantile(method="linear")`; pooled raw integer error counts; an explicit evaluation bootstrap seed. Report intervals for BER_B, BER_C, DeltaBER, SER_B, SER_C, and DeltaSER, plus existing diagnostic warnings. Preserve warnings for too few, rare-error, all-zero, or degenerate samples. A CI `[0,0]` is not proof of true zero BER; a CI containing zero is not evidence of receiver equivalence. Secondary or diagnostic intervals do not imply simultaneous coverage.

No new bootstrap is performed in M5i. The static manifest contains one future evaluation bootstrap seed, but no resamples or result records.

## Planned IDs and RNG provenance

The planned manifest is `configs/m5i_confirmatory_run_manifest_draft.json`. It lists 100 deterministic unique IDs, `M5j-confirmatory-paired-ber:evaluation:gamma-5dB:run-001` through `...run-100`. The primary stratum keeps stratum index 1 from the canonical M5h 0/5/10/15 dB grid, even though M5j has one executed primary condition. Run indices in seed keys are zero-based.

Only the reserved **evaluation** master roots from the M5h protocol are used: data `2026110101`, noise `2026110102`, bootstrap `2026110103`. Pilot roots are not used. Each derived 64-bit seed is generated as `SeedSequence(master_seed, spawn_key=(0x4D354831, 211, 1, run_index, stream_code)).generate_state(1, dtype=uint64)[0]`; stream codes are data=11, noise=23, bootstrap=37. Data/noise children are unique within the 100 planned runs and across namespaces, bootstrap is independent, and an audit found no overlap with any stored M5h pilot seed. Generators for future data/noise would use NumPy PCG64. The manifest records Python and NumPy versions and source-file SHA-256 fingerprints; the workspace has no Git revision available.

The manifest is deterministic and contains IDs, roots, spawn keys, derived seeds, stratum, F, sigma, and code/runtime provenance only. It contains no generated bitstream, received buffer, noise sample, reference bits, error counts, or bootstrap replicates. A future M5j run-specific config must pin the manifest, complete config fingerprint, and code fingerprint; resume under a changed fingerprint is forbidden.

## Failure policy and fixed stopping

If a planned run lacks valid B or C output, preserve a failure record with its planned ID, seeds, and available diagnostics. Do not impute zero or maximum errors, silently exclude the ID, retry with a new seed, or change receiver parameters. Primary full-design inference is BLOCKED; the run count is NOT ACHIEVED. Completed-only pooled summaries may appear only as descriptive estimates explicitly labeled with the missing-output count. No automatic worst/best-case sensitivity bounds are substituted for the estimand.

Finite but unstable trajectories with valid decoded output remain included with diagnostics. High BER runs remain included with all observed errors. After a technical interruption, resume only unfinished planned IDs with the original seeds and exact matching config, manifest, and code fingerprints. Checkpoint each completed run atomically and reject duplicates. Fixed stopping is completion of all 100 planned IDs or a documented technical interruption. A wall/RSS budget interruption must stop before the next independent run, retain completed atomic checkpoints, and mark the design incomplete. There is no result-dependent early stopping, no stopping on DeltaBER sign/CI, and no automatic run-count increase.

## Future M5j laptop budget and authorization

Candidate future budget: one process, one worker, no multiprocessing, at most 900 seconds wall time, and 1.5 GiB RSS budget if reliably monitorable. If monitoring is sampled polling, report that it is not a hard OS memory cap. Checkpoint after every full paired run using atomic writes; verify the manifest and code/config fingerprint before run and resume; reject duplicate IDs. No runtime benchmark was run for M5i.

`execution_authorized=false` implies no data generation, no noise generation, and no decoder execution. The M5i guard rejects before callback access. M5j requires a new immutable run-specific config approved explicitly by the user, with a separate authorization status/scope and fresh code/config fingerprint. Never reuse the M5h `m5h_pilot_only` authorization and do not enable the receiver CLI.

## Scientific claim limits and readiness

If separately authorized and completed, M5j can estimate only the performance difference between these specified frozen and adaptive reconstructed receivers under this fixed ADR-015 single-path discrete-AWGN profile. It cannot establish a paper-exact joint receiver, general HF channel evaluation, complex fading, multipath, correlated AR(1), physical Eb/N0 gain, optimality, universal adaptation benefit, or reproduction of a 1.5 dB result. Even if the DeltaBER CI excludes zero, interpret it only within this frozen profile and alongside assumptions, failures, and bootstrap warnings. Preserve `paper_exact:false`, `receiver_enabled:false`, proposed ADR-009/011, and open SCI-02/SCI-03/SCI-METRIC-02.

| Gate | Status |
|---|---|
| M5h pilot inputs and exact primary variability | READY | 30 raw primary checkpoints verified against saved summary; `s_d` and R approximation reproduced |
| Frozen M5i parameters and workload | READY | explicit schema, ADR-015 sigma check, fixed paired B/C policies |
| Evaluation-only ID/seed manifest | READY for planning | 100 IDs and seed provenance deterministic; no stochastic streams consumed |
| Failure/stopping/bootstrap contracts | READY as design rules | fixed policy validated; no confirmatory records produced |
| M5j execution authorization | BLOCKED | user must review and issue separate run-specific approval |
| Confirmatory CI precision | BLOCKED pending observed M5j data | epsilon is only a target; R=100 does not guarantee interval width |
| Performance or generalization claim | BLOCKED / out of scope | reconstructed offline single profile only |

No new ADR is required: this design applies accepted ADR-012/013/014/015 without changing their contracts. Any future change to accepted scientific or statistical assumptions needs a separate review.


## Prepared artifacts and fingerprints

- Draft config: `configs/m5i_confirmatory_design_draft.json`; canonical design fingerprint `6e42b5003e3804c89266cd78dcf3702d9d8159ed4ed46b81acf962bbff4db1e4` (file SHA-256 `bb402f26d0f3f6fde0e8d4b473273f6075e4b19585af7ae13de8e8ba98cca218`).
- Planned run manifest: `configs/m5i_confirmatory_run_manifest_draft.json`; file SHA-256 `6b63e12f6463680af603944a43e576afa15e08b1b84155273fbbbc42c4fb5b15`; contains 100 IDs and metadata-only seeds. Its independent evaluation bootstrap seed is `3940591365597190145`.
- The static manifest records code fingerprints for the M5i validator and the M5h protocol/runner plus the actual paired-run, adaptive-diagnostic, metric, reconstruction-config, and receiver-forward modules. Workspace revision metadata is unavailable because this directory is not a Git worktree.

## M5j authorized execution outcome

The separately authorized M5j run completed all 100 frozen primary-stratum IDs with no numerical failures. See `M5_CONFIRMATORY_EVALUATION_REPORT.md` and `outputs/m5j_confirmatory/20261029T-run/`. The run-specific approval is `configs/m5j_confirmatory_approved_run.json`; M5i draft and manifest remain proposed metadata and unchanged. Pooled results were BER_B=0.02107421875, BER_C=0.38658203125, DeltaBER=0.3655078125, SER_B=0.0391796875, SER_C=0.70140625, DeltaSER=0.6622265625. DeltaBER's ADR-014 95% interval was [0.35548681640625, 0.37578173828125], half-width=0.0101474609375; epsilon=0.02 was met. This supports only the preregistered fixed reconstructed_offline L=1 ADR-015 discrete-AWGN comparison. It does not support physical HF Eb/N0, paper-exact, or general receiver claims. No further experiment is authorized by M5j.

All 100 per-run checkpoints and the complete summary are persisted and independently re-aggregated. The worker had a post-summary console `KeyError` (wrong count-field key), exit code 1 after it had written the completed result; parent monitoring and independent checkpoint/bootstrap verification confirmed the saved 100-run result. This reporting defect is documented and did not cause a rerun or affect outputs. Periodic RSS monitoring observed a 47,329,280-byte peak over 597 samples; it is not a hard OS cap. No new ADR is required.
