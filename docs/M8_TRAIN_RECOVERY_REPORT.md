# M8b controlled TRAIN recovery report

**Classification:** controlled M8b TRAIN recovery attempt, exploratory policy
selection only; not independent validation, not confirmatory performance
evidence, and not a paper-exact receiver.

## Recovery basis and original failure

The original M8b attempt remains immutable at
`outputs/m8b_train/m8_anchored_reconstructed_adaptation_v1/`. It contains 40
ordered TRAIN IDs, 40 received hashes, 320 explicit `KeyError('clock_origins')`
policy failures, zero decoder calls, no eligible candidates, and no winner.
Its approved config SHA-256 is
`a081e98bcbdf6aab94175fe410f5161e06e72d24ad99070147172088c7945e95`; its
runtime fingerprint is
`a88db99ca90814ec610f135446a1bd03c6f5473f327c010337675a14979a9475` and the
original approved runner hash is
`e93786aa7fb36cdbc60c9e1cfc787bfd12efb5f97518ec5b2aa276c61c706f5f`.
The old failure occurred before any decode and therefore yielded no policy
performance observations. This explicit recovery replays the same partition;
it is not a new independent sample.

The old runner attempted to read `clock_origins` directly from M8a draft JSON,
which intentionally contains no such field. The corrected adapter resolves
sample origin 0 and estimator tick 0 from the accepted M5i reconstruction
configuration (`timebase.symbol_origin_sample` and
`estimator.initial_time_index`). B4d's new-independent-sequence contract sets
the sequence symbol origin to 0 and requires the first symbol index to equal
that origin. These values are checked and passed explicitly; no fallback is
used. B4d timing provenance verifies prediction cutoff `8f-1`, observation
cutoff `8f+7`, and samples `8f..8f+7` for each symbol. The clock fix changes
orchestration provenance only, not estimator, metric, posterior, or decoder
semantics.

## Frozen recovery approval and preflight

The M8a draft remains byte-identical and unauthorized (`proposed / false /
none`), SHA-256
`0740500746cfc340207d3b30a9e9cc62209e620c6a108926b1623cd7e46d960c`.
The new recovery approval is
`configs/m8b_train_recovery_approved_run.json`, scoped only to
`m8b_train_recovery_only`; SHA-256
`045e20a914a4a43fa428387a4b0ba1c80a6199ae17370d67c90508c364393657`.
Runtime fingerprint SHA-256 is
`d7113a162a0fcb86979662809421ba995bb95013b61346613332d60c6af4fd54`;
recovery runner source SHA-256 is
`e38b4409f099c4daa4b5c95e74cda11dc15ccaff87909939d790fb8a7d0440cd`.
The current M8b runner source hash was checked as
`207003e3e322fc000ac4c0565ce8ed2e014d9071446087ef125c07da31322a54`.
Git revision is unavailable in this workspace.

Before TRAIN, deterministic tests reproduced the old missing-key failure,
verified the exact clock origins and invocation contract, and exercised the
real conditional B4d/B5b path for all eight policies on a separate 4-symbol,
32-sample deterministic fixture. All outputs had valid 8-bit/4-symbol shapes,
finite `(4,16)` metrics, correct clocks and canonical edge order, the expected
per-policy `mu0` and initial state, and no reference-bit or channel-truth
receiver arguments. One decoder call was observed per invocation. Direct calls
to the existing conditional API matched the adapter's decoded paths, bits,
metrics, and final state for an anchored arm and frozen B. No TRAIN input or
RNG was used by the smoke test.

## Same-seed replay and integrity gates

The recovery used the exact M8a TRAIN roots, partition code 801, PCG64,
zero-based run indices 0–39, stream codes data 11, noise 23, bootstrap 37,
metadata 41, and the original 40 IDs
`m8_anchored_reconstructed_adaptation_v1:train:run-001` through `run-040`.
Data/noise seeds and the original per-run received SHA-256 were read from the
preserved approval/checkpoints. Reference bits were regenerated once per run
and checked against the original failed checkpoint. The one reconstructed
received buffer was hashed using the original canonical complex128 byte rule.
All 40 hashes matched exactly before any decoder was called. No seed was
replaced; validation/final streams were not derived or used.

The scientific profile was unchanged: reconstructed offline, L=1, real gain
0.75, zero delay, normalized 8PSK, rectangular ZOH at 8 samples/symbol,
ADR-002/005/012/013/015, effective discrete gamma-b 5 dB, variance
`0.7115124735378853`, F=256, beta 0.7, and the frozen eight M8a policies with
their exact anchor/initial-state definitions. The effective gamma is not
physical HF Eb/N0. True gain and reference bits were used only in simulation
and post-decode evaluation.

## Completion, counts, and ranking

All 40 sequences completed with 8 policy records each: 320 records, 320
actual conditional decoder invocations, 40 unique received hashes, zero
decoder/numerical failures, and no missing outputs. Each candidate has 20,480
information bits and 10,240 coded symbols. Raw counts were independently
recomputed from saved reference bits/symbols and decoded path outputs.

| Rank | Candidate | Bit errors / bits | Pooled BER | Symbol errors / symbols | Pooled SER | Eligible |
|---:|---|---:|---:|---:|---:|:---:|
| 1 | `historical_frozen_B` | 413 / 20,480 | 0.020166015625 | 371 / 10,240 | 0.03623046875 | Yes |
| 2 | `anch_a085_k025` | 429 / 20,480 | 0.020947265625 | 385 / 10,240 | 0.03759765625 | Yes |
| 3 | `anch_a095_k025` | 490 / 20,480 | 0.02392578125 | 440 / 10,240 | 0.04296875 | Yes |
| 4 | `anch_a085_k050` | 528 / 20,480 | 0.02578125 | 463 / 10,240 | 0.04521484375 | Yes |
| 5 | `anch_a095_k050` | 924 / 20,480 | 0.0451171875 | 786 / 10,240 | 0.0767578125 | Yes |
| 6 | `anch_a100_k025` | 1,501 / 20,480 | 0.073291015625 | 1,204 / 10,240 | 0.117578125 | Yes |
| 7 | `anch_a100_k050` | 3,000 / 20,480 | 0.146484375 | 2,324 / 10,240 | 0.226953125 | Yes |
| 8 | `historical_combined_C` | 7,804 / 20,480 | 0.3810546875 | 7,074 / 10,240 | 0.6908203125 | Yes |

The exact M8a ranking rule selected `historical_frozen_B`; no tie-break was
needed. Status is `TRAIN_SELECTED_NOT_VALIDATED`. This is exploratory selection
on the fixed TRAIN partition only. It does not establish independent adaptive
improvement, confirmatory superiority, physical-channel performance, or a
cause of historical M5j errors.

## Independent verification, resources, and preservation

Checkpoint verification found 40 exact run IDs, 40 matching received hashes,
eight ordered candidate records per sequence, exact candidate parameters,
seed provenance, decoded-path validity, bit/symbol denominators, 320 recorded
and observed decoder calls, and the ranking above. Recovery output integrity
hashes verify. Historical M5f/M5h/M5j/M6b/M6g/M6h/M7b, M8a draft/sidecar,
original M8b approval/sidecar, and original failed M8b output matched their
pre-run baselines.

The one-process run took 159.352 seconds. Periodic RSS monitoring observed a
peak of 44,167,168 bytes; this is not a hard OS memory limit. The 15-minute
time and 1.5-GiB monitoring budgets were not reached. Receiver mathematics,
ADR status, and open SCI questions did not change. `paper_exact:false` and
`receiver_enabled:false` remain in force.

## Next gate

M8c is not launched. The TRAIN winner is historical frozen B, so the proposed
anchored-versus-B validation has no adaptive candidate to validate. Do not
promote the runner-up. A next study requires a separately decided estimand,
fresh independent partition design, and explicit authorization; any claim
remains limited to reconstructed offline assumptions.

Read-only follow-up: the M8 exploratory closeout independently extracted the
40 paired `historical_frozen_B` / `anch_a085_k025` raw-count contrasts without
changing this report's recovery findings or any checkpoint. See
[`M8_EXPLORATORY_ANCHORED_CLOSEOUT.md`](M8_EXPLORATORY_ANCHORED_CLOSEOUT.md).
