# M7b authorized TRAIN policy search report

**Status:** `TRAIN_SELECTED_NOT_VALIDATED`. This is exploratory TRAIN policy
selection for the reconstructed receiver, not independent validation,
confirmatory performance evidence, or a source-faithful receiver. No
VALIDATION or FINAL partition was executed. `paper_exact:false` and
`receiver_enabled:false` remain.

## 1. Approved TRAIN-only protocol and provenance

The execution used a separate run-specific authorization created from the
unchanged M7a draft. The authorization provenance is the explicit user
authorization in the M7b instruction. Its scope is exactly
`approved_training / m7b_train_only`; the draft remains
`proposed / false / none`.

| Artifact | SHA-256 / status |
|---|---|
| M7a draft | `6b5cffdd9c4f47241bf7d54ff5d58c93d65bc2759a35557e07e3a1f38dae841f` |
| Approved TRAIN config | `7b29eaed0166765193b3f8bc16eae760826e1469a97025577573730113c87595` |
| Runtime source fingerprint digest | `b125014fb5e61bccf66162beaf41214d591369563f0bedcdaa784e700b40c909` |
| Git revision | unavailable; workspace is not a Git worktree |
| Output integrity manifest | `84586641089bafd686a9f9f29a13c09ac1ab38017a85d92d4ed0ddfb13e8b80c` |

The approved configuration freezes the 24-file runtime fingerprint, Python
and NumPy versions, the M7a profile, policy order, selection and failure
rules, seed manifest, resource limits, and historical artifact baselines.
The runtime fingerprint still matches the sources after execution.

## 2. Scientific profile and candidates

This was the fixed `reconstructed_offline` profile: L=1, real gain 0.75, zero
delay, normalized 8PSK, rectangular ZOH at 8 samples/symbol, ADR-002
reconstructed labeling, ADR-005 pseudo-likelihood, ADR-012 observed I/Q,
ADR-013 conditional full Viterbi, and independent circular complex AWGN
under ADR-015. The effective discrete `gamma_b` was 5 dB with
`sigma_squared=0.7115124735378853`; this is not physical HF `Eb/N0`.
Sequences had F=256 and 512 information bits. All policies shared
`initial full_iq=(0.42,0.91)`, `mu0=(0,0)`, `beta=0.7`, clocks, input bits,
and the same received array within a run.

The exact alpha-major, K-scale-minor nine-policy grid was fixed before the
TRAIN draws:

| Candidate | alpha_prime | K_tilde | Role |
|---|---:|---:|---|
| `a100_k000` | 1.00 | (0, 0) | frozen B |
| `a100_k050` | 1.00 | (0.175, -0.1) | proposed policy |
| `a100_k100` | 1.00 | (0.35, -0.2) | proposed policy |
| `a095_k000` | 0.95 | (0, 0) | proposed policy |
| `a095_k050` | 0.95 | (0.175, -0.1) | proposed policy |
| `a095_k100` | 0.95 | (0.35, -0.2) | proposed policy |
| `a085_k000` | 0.85 | (0, 0) | proposed policy |
| `a085_k050` | 0.85 | (0.175, -0.1) | proposed policy |
| `a085_k100` | 0.85 | (0.35, -0.2) | historical C |

No parameters were changed after observing results. The seven intermediate
settings are experimental policies, not author modes or an optimal policy.

## 3. TRAIN seeds, pairing, and execution completeness

The 40 run IDs are
`m7_reconstructed_estimator_policy_study_v1:train:run-001` through
`...:run-040`, processed in ascending order. The exact per-run data, noise,
and metadata seeds, master roots, spawn keys, and PCG64 provenance are in
the approved config and output manifest. TRAIN roots were data=2026120101,
noise=2026120102, and experiment metadata=2026120104. The M7a-reserved
bootstrap root 2026120103 was unused. The derivation was the exact M7a
`SeedSequence(master, spawn_key=(1295337521,701,zero_based_run_index,stream_code))`
rule. Metadata seeds were recorded but no metadata RNG was instantiated.
No validation or final child seeds were derived or used.

Each run generated one information sequence and one ADR-015 noise
realization, formed one received array, and passed that same immutable buffer
to each policy. The 40 received SHA-256 values are unique; each is recorded
once at the run level and repeated in all nine policy records. The direct
orchestrator called the existing B4d/B5b path once per candidate and did not
re-decode B for paired comparisons.

| Quantity | Observed |
|---|---:|
| Independent TRAIN sequences | 40 / 40 |
| Unique received hashes | 40 |
| Policy records | 360 / 360 |
| Decoder invocations | 360 / 360 |
| Policy-symbol passes | 92,160 |
| Received complex samples | 81,920 |
| Information bits | 20,480 |
| Candidate numerical/decoder failures | 0 |

The pre-run B/C equivalence regression used an existing deterministic small
fixture and compared paths, raw counts, metrics, posterior, states,
coefficient diagnostics, and clock provenance with the established paired
diagnostic API. It also spied on nine decoder invocations and confirmed all
B4d calls received the identical array without reference-bit, gain, or
`ChannelTruth` operands.

## 4. TRAIN raw-count ranking and selection

The independent verifier read all sequence checkpoints, checked the planned
run IDs and seed provenance, confirmed nine ordered policy rows per run,
recomputed coded symbols and decoded paths from saved evaluation-side data,
recounted integer errors from decoded outputs, and pooled raw counts. Every
candidate had 40 valid records and denominators of 20,480 bits and 10,240
coded symbols. Ranking applies the frozen BER, SER, K-scale, alpha-distance,
and candidate-ID rule; no tie-break was needed because pooled BER values
differed.

| Rank | Candidate | Bit errors / bits | Pooled BER | Symbol errors / symbols | Pooled SER | Failures | Eligible |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `a100_k000` | 478 / 20,480 | 0.023339843750 | 441 / 10,240 | 0.043066406250 | 0 | yes |
| 2 | `a095_k000` | 1,903 / 20,480 | 0.092919921875 | 1,559 / 10,240 | 0.152246093750 | 0 | yes |
| 3 | `a100_k050` | 3,050 / 20,480 | 0.148925781250 | 2,333 / 10,240 | 0.227832031250 | 0 | yes |
| 4 | `a100_k100` | 4,831 / 20,480 | 0.235888671875 | 3,835 / 10,240 | 0.374511718750 | 0 | yes |
| 5 | `a085_k000` | 4,871 / 20,480 | 0.237841796875 | 4,006 / 10,240 | 0.391210937500 | 0 | yes |
| 6 | `a095_k100` | 7,357 / 20,480 | 0.359228515625 | 6,799 / 10,240 | 0.663964843750 | 0 | yes |
| 7 | `a095_k050` | 7,575 / 20,480 | 0.369873046875 | 6,791 / 10,240 | 0.663183593750 | 0 | yes |
| 8 | `a085_k100` | 8,093 / 20,480 | 0.395166015625 | 7,339 / 10,240 | 0.716699218750 | 0 | yes |
| 9 | `a085_k050` | 8,545 / 20,480 | 0.417236328125 | 7,502 / 10,240 | 0.732617187500 | 0 | yes |

The TRAIN-selected policy is `a100_k000` (frozen B), with
`alpha_prime=1.0`, `K_tilde=(0,0)`. Its immutable record is marked
`TRAIN_SELECTED_NOT_VALIDATED`. The training minimum is selection-biased and
descriptive only. It does not show superiority on independent data and does
not establish an adaptive performance claim.

## 5. Failures, resources, and artifact verification

There were zero candidate failures. No output was imputed or excluded; all
finite outputs were retained. The single process completed in 174.07 seconds
within the 900-second budget. Periodic Windows RSS monitoring observed a
peak working set of 43,401,216 bytes (about 41.4 MiB), below the 1.5 GiB
monitoring budget. This is a periodic observation, not a hard OS memory
limit. No multiprocessing was used.

The independent checkpoint replay found 40 ordered unique run IDs, 40 unique
received hashes, 360 policy records, 360 decoder calls, 40 complete paired
sequence checkpoints, exact expected denominators, and the same ranking and
winner as the runner summary. The output integrity manifest matches all 46
listed files. A separate descriptive paired comparison was then derived
read-only from saved checkpoints; it invoked neither receiver nor RNG and did
not affect selection. See
[`paired_comparison_summary.json`](../outputs/m7b_train/m7_reconstructed_estimator_policy_study_v1/paired_comparison_summary.json).

The paired bit-error differences below are candidate minus frozen B across
the 40 matched runs. Run tallies are descriptive and are not significance
tests.

| Candidate | Delta bit errors | Delta symbol errors | Runs higher / equal / lower BER than B |
|---|---:|---:|---:|
| `a100_k000` | 0 | 0 | 0 / 40 / 0 |
| `a100_k050` | 2,572 | 1,892 | 22 / 4 / 14 |
| `a100_k100` | 4,353 | 3,394 | 35 / 1 / 4 |
| `a095_k000` | 1,425 | 1,118 | 39 / 0 / 1 |
| `a095_k050` | 7,097 | 6,350 | 40 / 0 / 0 |
| `a095_k100` | 6,879 | 6,358 | 40 / 0 / 0 |
| `a085_k000` | 4,393 | 3,565 | 40 / 0 / 0 |
| `a085_k050` | 8,067 | 7,061 | 40 / 0 / 0 |
| `a085_k100` | 7,615 | 6,898 | 40 / 0 / 0 |

The paired-summary SHA-256 is
`347ee6e32d7f480b91b64b41e68747848e85685583184ce2445769946c0ea842`.

Historical hashes before and after TRAIN matched exactly:

| Historical artifact | Files | SHA-256 |
|---|---:|---|
| M5f | 1 | `98801572202a6c6c21199ef94257a9e1d9e99bb5d38273cf07b66f041b511d1a` |
| M5h | 128 | `5689921ddf901790322a124abc52e0cbb34642385e6ef1ce5054a8b8e5f3cf2c` |
| M5j | 102 | `b12c3171ab13d69895d89e00eb3113c7122a7e6756461761769dd4337454233b` |
| M6b | 26 | `5cf8e11aa2f3e5e9d357344828afa1c7ebae8bf0a17040dee67e32f3de81ad5b` |
| M6g | 1 | `76301b6965f77ac70302c4879158b77f9a9fc55e0cfdccf9725034279c25f1d2` |
| M6h | 1 | `baca1959562833d004bd3f3cb6cca718f54ec3f7a583b7b1f0954515643ee069` |

## 6. Verification and scientific limits

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_m7b_train_runner.py -p no:tmpdir -p no:cacheprovider` | PASS — 5 passed in 1.89s |
| `python -m pytest -q --basetemp .pytest-m7b-final-temp -p no:cacheprovider` | PASS — 846 passed in 9.39s |
| `ruff check src tests` | PASS — All checks passed |
| `ruff format --check src tests` | PASS — 139 files already formatted |

This is one fixed effective discrete gamma point, L=1 real gain, independent
sample-level ADR-015 AWGN, ADR-005 pseudo-likelihood, ADR-013 conditional
Viterbi, mismatched fixed initialization, and a specific finite alpha/K grid.
It has no physical radio-energy calibration, AR(1), multipath, or complex
fading. Source mapping/quadrature/innovation questions remain unresolved.
Training search does not change M5j's historical result, answer the M5j
causal question, identify an optimal policy, validate the selected policy,
or support source-paper or general HF claims. Receiver mathematics,
accepted ADRs, and open SCI questions were not changed. No new ADR was needed.

## 7. Next authorization gate

M7c is not authorized. Because frozen B won, the proposed validation pair
would compare B against itself unless the study objective and estimand are
reconsidered. The next decision must explicitly choose whether to stop the
policy study or authorize a separate same-policy reproducibility exercise
with a clearly stated non-superiority estimand. Any VALIDATION needs a new
authorization and must not reselect from these TRAIN results; FINAL remains
separately blocked.

Machine-readable checkpoints and provenance are in
[`outputs/m7b_train/m7_reconstructed_estimator_policy_study_v1/manifest.json`](../outputs/m7b_train/m7_reconstructed_estimator_policy_study_v1/manifest.json),
with exact seeds in its `run_manifest` and `approved_config_snapshot.json`.
