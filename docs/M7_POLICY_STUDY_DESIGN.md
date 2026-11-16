# M7a preregistered reconstructed estimator-policy study design

**Status:** validated proposed design only. No training search, validation,
final evaluation, stochastic sequence, receiver evaluation, or new performance
evidence was executed. This is not an optimized receiver or paper-exact
implementation. `paper_exact:false` and `receiver_enabled:false` remain.

## 1. Independent research question and M6 motivation

The independent research question is whether any policy in the fixed compact
alpha/K grid has lower pooled BER than historical frozen B on a separate
training partition, and whether a single training-selected policy preserves
its paired effect on new validation sequences. Secondary diagnostics describe
finite coefficient trajectories, post-decode estimation error, SER, and
whether observed effects align descriptively with alpha decay/correction
strength. These are questions about this project's reconstruction, not source
replication.

M6 supports examining the two update terms separately: M6e-M6f checked local
alpha/correction identities and squared-metric interactions; M6g showed
multistep state/metric/posterior dependence under closed-loop versus a frozen
innovation control; M6h isolated same-state posterior-weight changes from
prediction changes and compared a posterior-clamp trajectory. M6b's three
diagnostic traces showed finite but increased final coefficient-error norms
for C on those inputs. None identifies an optimal policy or M5j's historical
BER cause. The full evidence synthesis is `M6_MECHANISM_SYNTHESIS.md`.

## 2. Fixed scientific profile

The candidate is `reconstructed_offline`, `L=1`, real `a=0.75`, zero delay,
normalized 8PSK, rectangular ZOH at 8 samples/symbol, ADR-002 reconstructed
labeling, ADR-005 pseudo-likelihood, ADR-012 observed-IQ, ADR-013 conditional
full Viterbi, and ADR-015 independent circular complex AWGN. Effective
discrete `gamma_b=5 dB`, with

    sigma_squared = 4*a*a / 10^(gamma_b_eff_db/10)
                  = 0.7115124735378853.

This is not physical HF `Eb/N0`. Shared estimator values are initial
`full_iq=fluctuating_iq=(0.42,0.91)`, `mu0=(0,0)`, and `beta=0.7`. Every
sequence has F=256 TCM symbols and 512 information bits. Generate one
reference sequence and one channel/noise realization per sequence, then
reuse the exact same received buffer for all policies in that sequence.
Reference bits, true gain, and ChannelTruth are evaluation-side only and are
not estimator inputs.

## 3. Exact nine-policy candidate grid

`K_tilde=K_scale*(0.35,-0.2)`. Grid order is alpha-major, then ascending
K_scale:

| Candidate ID | alpha_prime | K_scale | K_tilde | Role |
|---|---:|---:|---:|---|
| `a100_k000` | 1.00 | 0.0 | (0, 0) | Historical frozen B |
| `a100_k050` | 1.00 | 0.5 | (0.175, -0.1) | New proposed policy |
| `a100_k100` | 1.00 | 1.0 | (0.35, -0.2) | New proposed policy |
| `a095_k000` | 0.95 | 0.0 | (0, 0) | New proposed policy |
| `a095_k050` | 0.95 | 0.5 | (0.175, -0.1) | New proposed policy |
| `a095_k100` | 0.95 | 1.0 | (0.35, -0.2) | New proposed policy |
| `a085_k000` | 0.85 | 0.0 | (0, 0) | New proposed policy |
| `a085_k050` | 0.85 | 0.5 | (0.175, -0.1) | New proposed policy |
| `a085_k100` | 0.85 | 1.0 | (0.35, -0.2) | Historical C |

The seven intermediate policies are not author modes or optimized settings.
The grid is frozen at these nine choices for this proposed study; no beta or
other parameter sweep is included.

## 4. Data partitions and RNG provenance

| Partition | Sequences | Policies evaluated | Use |
|---|---:|---|---|
| TRAIN | 40 new, F=256 | All nine | Selection-oriented descriptive counts only |
| VALIDATION | 40 new, F=256 | Frozen B and exactly one frozen TRAIN winner; historical C may be descriptive only | Independent paired estimate; cannot reselect |
| FINAL | 100 future, F=256 | Frozen B and selected policy; historical C optional descriptive | Not authorized; requires a separate design and run approval |

Historical M5f, M5h, M5j, M6b, M6g, and M6h samples are excluded from all
partitions. The proposed distinct root namespaces in the JSON are:

| Partition | data | noise | bootstrap/statistical | experiment metadata |
|---|---:|---:|---:|---:|
| TRAIN | 2026120101 | 2026120102 | 2026120103 | 2026120104 |
| VALIDATION | 2026120201 | 2026120202 | 2026120203 | 2026120204 |
| FINAL | 2026120301 | 2026120302 | 2026120303 | 2026120304 |

These proposed roots are all distinct and separate from audited historical
roots. Experiment metadata is a separately reserved stream namespace; the
M7a protocol does not need a stochastic metadata draw. The proposed derivation uses domain-separated NumPy
`SeedSequence(master_seed, spawn_key=(1295337521, partition_code,
zero_based_run_index, stream_code))`, then PCG64; partition codes are 701,
702, 703 and stream codes are data=11, noise=23, bootstrap=37, experiment
metadata=41.
Run IDs display one-based indices. M7a validates this plan but does not derive
child seeds, instantiate RNGs, generate bits/noise, or create observations.

Within each sequence, data/noise are generated once and the received-buffer
hash is shared by all policy records. Metadata and statistical resampling
have separate namespaces. The bootstrap stream is reserved for ADR-014
analysis, not training selection.

## 5. TRAIN selection contract

For every policy, aggregate integer bit/symbol error counts over the complete
40-run partition. Do not select using per-run averages. A candidate is
eligible only when all 40 candidate outputs and all 40 paired historical-B
outputs are valid and complete. A failure remains recorded, is not replaced
with another seed, and makes that candidate ineligible. If B has any missing
or invalid output, block the paired selection rather than pooling only
completed pairs. Continue other preregistered jobs after a failure only if a
future authorized runner's failure-continuation policy permits it. Never
impute zero errors or maximum BER. Retain finite high-BER trajectories.

Select the eligible policy with minimum pooled raw-count BER. Exact ties are
broken by: (1) lower pooled raw-count SER; (2) lower K_scale; (3) alpha_prime
closer to 1; (4) lexicographically lower candidate ID. Frozen B is eligible
and may win. No coefficient-error or validation quantity enters selection.
If no candidate is eligible, make no selection and mark the training stage
blocked. Training minimums and any intervals shown are selection-biased
descriptive statistics, not confirmatory performance estimates.

## 6. VALIDATION and future FINAL rules

After training only, freeze candidate ID and every parameter/protocol field.
VALIDATION uses its independent data/noise roots and common received samples
for B and the one selected policy. Primary contrast is pooled
`BER_selected - BER_B`; report integer counts, pooled BER/SER, paired
per-sequence records, numerical failures, and a two-sided 95% ADR-014 paired
cluster percentile interval. Resample whole sequences with same-index reuse
for both policies, pool raw counts within each replicate, use 2,000
replicates and `numpy.quantile(method="linear")`, and use the independent
validation bootstrap namespace. Missing valid output blocks full paired
inference. Validation cannot select a second candidate. A null or unfavorable
result ends this selection; any later search needs entirely new partitions.

FINAL is prospective only. Before it can run, separately approve the final
policy, sample size, primary estimand, precision target, stopping rule,
failure policy, bootstrap settings, seed roots, resource budget, and claim
language. It is not called confirmatory before that review and may not be
used for later tuning. No one-point result supports a BER curve.

## 7. Failures and coefficient diagnostics

Persist one sequence record and one policy outcome for each planned
sequence/policy pair, including status, valid raw counts when available,
received pairing provenance, and coefficient diagnostics. Non-finite states
or invalid decoder output are failures. No new-seed retries, silent row
exclusions, zero/max-error imputation, or completed-only full-design
estimand. A finite but poor trajectory remains included. If supported by the
runner, coefficient estimation error relative to true `a` is evaluation-only
after decoding and cannot be an estimator input or policy-selection criterion.

## 8. Workload and API accounting

| Partition | Independent sequences | Unique policy decoder passes (one pass per policy) | Policy-symbol passes | Received samples generated | Information bits generated | Policy records |
|---|---:|---:|---:|---:|---:|---:|
| TRAIN | 40 | 360 | 92,160 | 81,920 | 20,480 | 360 |
| VALIDATION | 40 | 80 | 20,480 | 81,920 | 20,480 | 80 |
| FINAL | 100 | 200 | 51,200 | 204,800 | 51,200 | 200 |

These counts distinguish one received realization per sequence from repeated
policy decoding over its F symbols. `run_adaptive_estimator_diagnostic`
currently calls the existing decode API once per mode and evaluates two
modes per paired call. A naive public-helper training orchestration for each
of the eight non-B candidates would therefore use 640 decoder passes, of
which 280 repeat the same B decoder outcome. The target 360 unique passes
requires an evaluation-side grid orchestrator that reuses B once per
sequence; this is a runner/workload implementation detail for a later phase,
not permission to change receiver mathematics. If that orchestration is not
implemented and independently tested, M7b must explicitly accept the 640
pass budget before execution. Validation and final with one paired call per
sequence use 80 and 200 passes respectively.

The workload table excludes the explicitly optional descriptive historical-C
arm: adding it costs 40 additional validation or 100 additional final policy
decodes, sequence-symbol passes, and policy records, while received samples
remain shared within each sequence.

Candidate execution order is single-process: partition order only after each
partition is separately authorized, ascending run index, then the listed
candidate order. Save atomic checkpoints per sequence. This is a count-based
candidate workload, not a runtime/RSS estimate; approve concrete resource
limits before any run.

## 9. Authorization and gates

The machine-readable draft is
`configs/m7a_policy_study_draft.json`, with
`design_status="proposed"`, `execution_authorized=false`, and
`execution_scope="none"`. The evaluation-only validator checks exact grid,
profile/scaling, roots, partitions, pairing, selection/failure rules,
workload arithmetic, and the unauthorized state. Its guard rejects before
accessing injected callbacks; tests spy on RNG/data/noise/decoder boundaries.

| Gate | M7a status |
|---|---|
| Scientific synthesis and fixed candidate study design | READY as proposed reconstruction research |
| Draft schema and exact design validation | READY |
| TRAIN execution | BLOCKED: no separate M7b run-specific authorization; decide/validate grid orchestration and resource budget |
| VALIDATION | BLOCKED: requires completed TRAIN, frozen winner, new partition, separate authorization |
| FINAL | BLOCKED: requires separate scientific/statistical/resource approval and run authorization |
| Source-paper fidelity / author mapping | OPEN; does not authorize source-aligned claims |

No ADR is proposed or accepted. Proposed ADR-009/011 remain proposed; SCI-02,
SCI-03, and SCI-METRIC-02 remain open. The next minimal action is review and
authorization of TRAIN only, including the explicit decoder-pass accounting;
M7a does not execute it or chain later partitions automatically.

## 10. M7b TRAIN execution record (2026-10-30)

The separately authorized M7b TRAIN partition completed 40/40 sequences with
the exact nine proposed candidates, 40 unique shared received hashes, and
360 unique decoder passes. The selection was `a100_k000` (frozen B), marked
`TRAIN_SELECTED_NOT_VALIDATED`; its pooled TRAIN BER was 478/20,480 and its
pooled TRAIN SER was 441/10,240. All candidates were eligible with zero
failures. This is selection-oriented training output only and supplies no
independent validation or confirmatory claim. The complete ranking,
fingerprints, seeds, resource observations, and integrity checks are in
[`M7_TRAIN_POLICY_SEARCH_REPORT.md`](M7_TRAIN_POLICY_SEARCH_REPORT.md).

TRAIN authorization did not authorize later partitions. Since frozen B won,
any next validation would compare B with itself under the current protocol;
M7c therefore remains blocked pending a separate decision on whether to end
the study or define and authorize a same-policy reproducibility estimand.
No automatic validation or final evaluation is permitted.

## M7c exploratory closeout

M7 is closed as
`EXPLORATORY_GRID_COMPLETED; TRAIN_WINNER_FROZEN_B;
ADAPTIVE_GAIN_NOT_ESTABLISHED; VALIDATION_NOT_EXECUTED`. A read-only replay
of all 40 M7b checkpoints independently recounted bit/symbol errors and
reproduced the full ranking: frozen B (`a100_k000`) won with 478/20,480 bit
errors and 441/10,240 symbol errors; all nine candidates had 40 valid records
and zero failures. The primary M7b artifacts still retain
`TRAIN_SELECTED_NOT_VALIDATED`; no M7b numbers or files were changed.

No validation was run because the frozen B winner would be contrasted with
the same frozen B policy. The runner-up was not promoted post hoc. Any next
study must use a new design and new independent partitions. See
[`M7_EXPLORATORY_STUDY_CLOSEOUT.md`](M7_EXPLORATORY_STUDY_CLOSEOUT.md).
