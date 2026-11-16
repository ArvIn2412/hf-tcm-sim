# M9b fixed-policy evaluation report

**Status:** `M9_EVALUATION_COMPLETE_VERIFIED`  
**Classification:** prospective fixed-policy comparison motivated by the
post-hoc M8 runner-up; not M8 validation, not tuning, not paper-exact, and not
physical HF-channel evaluation.

## 1. Question and provenance

M9 estimates the paired raw-count contrast
`DeltaBER = BER(anch_a085_k025) - BER(historical_frozen_B)` on the fixed
constant-gain `reconstructed_offline` profile. `anch_a085_k025` was identified
as runner-up after observing the M8 eight-policy TRAIN grid. It was fixed for
M9 before M9 observations, so M9 is a prospective fixed-policy study, but it
was not preregistered before M8 and is not independent validation of the M8
grid or its winner. No candidate selection or tuning occurred in M9.

## 2. Frozen authorization and runtime provenance

The M9a draft remains byte-for-byte unchanged and unauthorized
(`proposed / false / none`), SHA-256
`a6be31a2225aeaee48fffec5ff6f868866773a1087978a561e4cadea78e1d5ac`.
M9b used the separate approved snapshot
[`m9b_evaluation_approved_run.json`](../configs/m9b_evaluation_approved_run.json),
with SHA-256
`72dcc41f8cfc20028a1c2ea0ea15d0edc3fc6d941a322a3622e58ae1b099cad4` and a
matching `.sha256` sidecar. Its scope is `m9b_evaluation_only`; provenance is
the explicit user authorization in the M9b instruction. The runtime source
fingerprint is
`93530a40e4c95d24324150da37c423dfbbfc4945ddf4a9e80b0b154d987f04c1`.
The full file manifest is frozen in the approved snapshot and copied into the
output manifest. Environment: Python 3.13.13, NumPy 2.3.3, Windows 11
10.0.26300-SP0. Git revision was unavailable because this workspace is not a
Git worktree.

The exact two policies, their fixed order, receiver configuration, clock
origins, 100 run IDs, complete child-seed manifest, failure contract, output
schema, and resource limits are recorded in the approved snapshot. M9a's
scientific fields match the approved snapshot; only approval/runtime metadata
and output execution details were added.

## 3. Scientific profile and policies

Both policies used `reconstructed_offline`, L=1, real gain `a=0.75`, zero
delay, normalized 8PSK, rectangular ZOH at 8 samples/symbol, ADR-002 mapping,
ADR-005 pseudo-likelihood, ADR-012 observed IQ, ADR-013 conditional full
Viterbi, and independent circular complex AWGN under ADR-015. Effective
discrete `gamma_b=5 dB`, `sigma_squared=0.7115124735378853`, F=256 symbols,
512 information bits, `beta=0.7`, and initial full estimate `(0.42, 0.91)`.
This gamma is not physical HF Eb/N0.

| Policy | alpha_prime | K_tilde | mu0 | initial fluctuating IQ | initial full IQ |
|---|---:|---|---|---|---|
| `historical_frozen_B` | 1.00 | (0, 0) | (0, 0) | (0.42, 0.91) | (0.42, 0.91) |
| `anch_a085_k025` | 0.85 | (0.0875, -0.05) | (0.42, 0.91) | (0, 0) | (0.42, 0.91) |

No true gain, reference bits, channel truth, or correct path was passed into
receiver APIs. These were used only on the simulation/evaluation side after
receiver output.

## 4. Preflight and execution

Before M9 data/noise stream initialization, a real deterministic B4d/B5b
integration smoke ran both policies on an existing four-symbol, 32-sample
fixture. It passed direct-API equivalence, matching initial predictions and
metric row, canonical 16-edge order, 8-sample clock windows, zero sample,
symbol, and estimator-tick origins, valid metric/posterior shapes, finite
outputs, and one decoder invocation per policy. The smoke used no M9 samples
or RNG and is counted separately from the 200 experimental calls. The clock
origins were resolved from the accepted M5i receiver configuration and B4d
new-sequence contract; no `clock_origins` field or fallback was assumed from
M9a.

The evaluation completed all 100 planned runs in ascending index order:
`m9_fixed_anchored_vs_frozen_v1:evaluation:run-001` through `run-100`, with
zero-based indices 0–99. For each run, one information-bit vector, encoder
output, waveform, AWGN realization, and immutable received buffer were
shared by B and anchored policy. There are 100 distinct received SHA-256
hashes, 200 policy records, exactly 200 experimental decoder invocations, and
no failures. The run-by-run hashes and derived seeds are in the approved
config's `run_manifest` and individual checkpoints under
[`outputs/m9b_fixed_policy_evaluation/m9_fixed_anchored_vs_frozen_v1`](../outputs/m9b_fixed_policy_evaluation/m9_fixed_anchored_vs_frozen_v1/manifest.json).

Seed derivation followed M9a exactly: `SeedSequence(master_seed,
spawn_key=(1295337521, 901, run_index, stream_code))`, deriving a uint64 child
seed then initializing PCG64 for data/noise. Roots/codes were data
2027020101/11, noise 2027020102/23, bootstrap 2027020103/37, and metadata
2027020104/41. The first and last data/noise spawn keys are respectively
`(1295337521,901,0,11)` / `(1295337521,901,0,23)` and
`(1295337521,901,99,11)` / `(1295337521,901,99,23)`. The bootstrap child seed
was `13306766977441767340` from `(1295337521,901,0,37)`. Metadata seeds were
recorded for provenance; no metadata RNG was initialized. No M5–M8 or
validation/final roots were used.

## 5. Raw results and primary/secondary estimands

Independent checkpoint recount recomputed errors from saved reference and
decoded arrays, and verified decoded bits/symbols against the saved canonical
path. The denominators are 51,200 bits and 25,600 coded symbols per policy.

| Policy | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---:|---:|---:|---:|
| `historical_frozen_B` | 1,130 / 51,200 | 0.0220703125 | 1,050 / 25,600 | 0.041015625 |
| `anch_a085_k025` | 1,072 / 51,200 | 0.0209375 | 1,001 / 25,600 | 0.0391015625 |

Primary pooled raw-count contrast:

```text
DeltaBER = (1072 - 1130) / 51200 = -0.0011328125
```

The point estimate is lower for anchored on this fixed comparison. The
secondary contrast is:

```text
DeltaSER = (1001 - 1050) / 25600 = -0.0019140625
```

### Paired cluster bootstrap

The ADR-014 analysis resampled the same 100 complete sequence indices for
both policies, pooled integer errors per replicate, and used 2,000 replicates,
95% percentile intervals, and `numpy.quantile(method="linear")`. The separate
bootstrap stream used PCG64 with root 2027020103, spawn key
`(1295337521, 901, 0, 37)`, and derived seed `13306766977441767340`. No
receiver/data/noise stream was used for bootstrap.

| Estimand | Point estimate | 95% paired cluster-bootstrap CI |
|---|---:|---:|
| DeltaBER | -0.0011328125 | [-0.00322265625, 0.00068359375] |
| DeltaSER | -0.0019140625 | [-0.0053125, 0.0011328125] |

Both intervals include zero. Under the predefined interval this comparison's
direction is unresolved. Inclusion of zero does not establish equivalence,
noninferiority, or absence of an effect. The independent scalar-loop
bootstrap reproduced the resample-index SHA-256
`7641f1bb485013c17921b70d529f1eafc50baa20899ee442924da20c5a29d321` and both
intervals.

## 6. Numerical and coefficient diagnostics

All 200 outputs had finite final coefficient states and candidate metrics;
all final posterior vectors were normalized within the runner's `1e-12`
tolerance. B's final full-state norm was 1.0022474744293446 in all runs.
Anchored final full-state norms ranged from 0.9475843463504642 to
1.0706814530838624, with mean 1.005645041051456. The evaluation-only
two-coordinate final coefficient-error norm (relative to the simulation
gain value in the diagnostic code) ranged from 0.27227950202512397 to
0.4942828183260273 for anchored, mean 0.36231311907631003; B's value was
0.366742416417845 in all runs. These coefficient diagnostics are secondary,
model-specific summaries and did not determine policy or inference.
Per-symbol coefficient trajectories are unavailable from the conditional
decode result. Numerical failure count: 0.

## 7. Independent verification and integrity

Read-only verification from the 100 saved checkpoints confirmed 100 unique
run IDs, 100 unique received hashes, 2 records per run, exact policy
definitions/order, paired received hashes, 200 experimental decoder calls,
raw error recounts, denominators, counts, both pooled estimands, and zero
failures. The independently recalculated bootstrap bounds matched the saved
ADR-014 result. The output integrity manifest matched every output file
except itself. Historical hashes were identical before and after execution
for M5f, M5h, M5j, M6b, M6g, M6h, M7b, the original and recovered M8 artifacts,
and the M9a draft.

Resources: one process, 102.5633079999825 seconds for experimental
generation/decoding, 0.21279959997627884 seconds for bootstrap, 100/100 runs,
200 experimental decoder calls, and 50,085,888 bytes maximum periodically
observed RSS. RSS is monitoring, not a hard OS limit. The 900-second wall
budget was not reached.

## 8. Interpretation and limitations

This is independent evidence for one fixed pair under this reconstructed
constant-gain profile, not validation of the M8 search and not a comparison
against every possible adaptive policy. The anchored point estimates were
lower, while both paired intervals include zero; the prespecified CI does
not resolve a direction. No equivalence/noninferiority margin was specified,
so neither is claimed. The post-hoc M8 selection history remains material:
M9 was motivated by M8's runner-up, although the policy was fixed before
these M9 samples.

The result does not imply physical HF performance, a gain in physical dB,
paper-exact behavior, universal estimator stability, or a cause of historical
M5j errors. Source mapping and source equation semantics remain unresolved;
`paper_exact:false`, `receiver_enabled:false`, accepted ADRs and open
SCI-02/SCI-03/SCI-METRIC-02 are unchanged. No other experiment, partition,
or RNG namespace was used. Any further study requires a separate scientific
decision, explicit design, and authorization.

## 9. Verification commands

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp tmp/pytest-m9b-final-temp -p no:cacheprovider` | PASS — 897 passed in 11.31s |
| `ruff check src tests` | PASS — All checks passed |
| `ruff format --check src tests` | PASS — 149 files already formatted |

