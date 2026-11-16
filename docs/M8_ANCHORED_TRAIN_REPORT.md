# M8b authorized anchored TRAIN report

**Classification:** authorized exploratory anchored-adaptation TRAIN study,
**not** independently validated improvement, confirmatory performance evidence,
or a paper-exact receiver.

## Outcome

The authorized attempt is `TRAIN_INCOMPLETE_OR_BLOCKED`. The runner generated
the 40 planned TRAIN bit/noise realizations and wrote 40 checkpoints, but a
runner `KeyError: 'clock_origins'` occurred before every B4d/B5b invocation.
Consequently, there are no decoded outputs, BER/SER counts, eligible policies,
ranking, or selected policy. No zero-error or other count imputation was made.
The study cannot support an anchored-adaptation claim.

The failure is an orchestration/configuration defect, not an observed receiver
failure. The M8a draft does not contain a `clock_origins` object. The initial
approved runner indexed that absent key while preparing each policy call. The
same shared received buffer had already been generated for each run; each
buffer's SHA-256 and evaluation reference bits were checkpointed. The received
arrays themselves were not persisted. No decoder consumed them. The code was
then corrected to resolve the existing zero sample/tick origins from the
accepted M5i receiver configuration and fresh-sequence symbol origin, but this
post-attempt source change differs from the approved runtime fingerprint. The
existing approved snapshot is therefore not reusable for execution. No run was
repeated and no seed was replaced.

## Frozen design and provenance

The M8a draft remains byte-for-byte unchanged and unauthorized. Its SHA-256 is
`0740500746cfc340207d3b30a9e9cc62209e620c6a108926b1623cd7e46d960c`.
The run-specific approved TRAIN snapshot is
`configs/m8b_train_approved_run.json`, SHA-256
`a081e98bcbdf6aab94175fe410f5161e06e72d24ad99070147172088c7945e95`.
The execution-time source fingerprint digest recorded in that snapshot is
`a88db99ca90814ec610f135446a1bd03c6f5473f327c010337675a14979a9475`.
The workspace did not expose Git revision metadata; none is claimed. Output
schema is `m8b.train.v1`.

The fixed profile and eight policy definitions are copied unchanged from M8a:
six anchored policies and historical frozen B / combined C, common initial full
estimate `(0.42,0.91)`, beta `0.7`, 5 dB effective discrete gamma, and
`sigma_squared=0.7115124735378853`. This is not physical HF Eb/N0. The intended
workload was 40 sequences × 8 arms = 320 decoder passes. No receiver mathematics
was changed.

## What actually ran

| Check | Recorded result |
|---|---:|
| Planned TRAIN run IDs | 40 |
| Checkpoints written | 40 |
| Unique run IDs | 40 |
| Unique received hashes | 40 |
| Policy records | 320 (40 per candidate) |
| Decoder invocations | 0 / 320 expected |
| Valid decoded policy records | 0 |
| Failures | 40 per policy; all `KeyError: 'clock_origins'` |
| TRAIN winner | None |
| BER/SER | Unavailable; denominators are zero and pooled rates are null |
| Validation / FINAL | Not run; no such RNG streams instantiated |

| Candidate | Complete valid records | Failures | Eligible | BER / SER |
|---|---:|---:|---|---|
| `anch_a100_k025` | 0 | 40 | No | Unavailable |
| `anch_a100_k050` | 0 | 40 | No | Unavailable |
| `anch_a095_k025` | 0 | 40 | No | Unavailable |
| `anch_a095_k050` | 0 | 40 | No | Unavailable |
| `anch_a085_k025` | 0 | 40 | No | Unavailable |
| `anch_a085_k050` | 0 | 40 | No | Unavailable |
| `historical_frozen_B` | 0 | 40 | No | Unavailable |
| `historical_combined_C` | 0 | 40 | No | Unavailable |

TRAIN seed derivation used only the M8a TRAIN roots, partition code 801,
zero-based run indices 0–39, the frozen stream codes, `SeedSequence`, and
PCG64. For run 001, the data/noise child seeds were
`12240546964663076592` / `16049805712403515131`; for run 040 they were
`12590401800855788141` / `16742856063285950048`. Bootstrap and metadata child
seeds were recorded as provenance but no bootstrap or metadata generator was
instantiated. Validation and future-final seeds were not derived or used.

The requested initial-state and anchor definitions remained present in the
approved config; however, they never reached the estimator because the failure
preceded receiver calls. The output therefore does not establish that paired
received data were consumed by all arms; it only records one generated buffer
hash per sequence and the intended shared-buffer orchestration.

## Independent checkpoint audit

The checkpoint replay found 40 ordered unique IDs, 40 unique received hashes,
320 ordered policy records, exact TRAIN seed provenance, and zero decoder
invocations. Each policy has 40 explicit failure records. Every candidate is
ineligible; frozen B is also incomplete, so selection is blocked. The report
does not present missing error counts as zero.

Historical M5f, M5h, M5j, M6b, M6g, M6h, M7b, M8a draft, and its checksum
matched the approved pre-run baseline. The M7b ranking and artifacts were not
modified. The M8b output is isolated under
`outputs/m8b_train/m8_anchored_reconstructed_adaptation_v1/`.

Observed wall time was `0.1352429 s`; periodic RSS monitoring recorded
`37,306,368` bytes. These measurements cover the failed orchestration attempt,
not a completed 320-decode training study. They are not a runtime benchmark or
a hard memory limit.

## Scientific interpretation and next gate

M8b produced no policy ranking and no performance evidence. It cannot answer
whether anchored adaptation outperforms historical frozen B. The six anchored
arms remain proposed research candidates, not validated or optimized policies.
Source mapping and likelihood limitations remain unchanged;
`paper_exact:false`, `receiver_enabled:false`, and SCI-02, SCI-03, and
SCI-METRIC-02 remain open.

The corrected runner now records the resolved zero clocks in a new runtime
snapshot, but its source fingerprint differs from the failed run's approval.
The failed run records source SHA-256
`e93786aa7fb36cdbc60c9e1cfc787bfd12efb5f97518ec5b2aa276c61c706f5f` for the
M8b runner; the post-fix source SHA-256 is
`207003e3e322fc000ac4c0565ce8ed2e014d9071446087ef125c07da31322a54`, and its
overall source fingerprint digest is
`0ef2fadfae4d0e9da296b1b9f5fedca74962350b0b8f1f5e3beea00af7a4ec26`. The
existing run must not be resumed or overwritten. Any further execution
requires a separately reviewed run-specific M8b authorization/snapshot and an
explicit decision on whether these same TRAIN IDs/seeds may be replayed. M8c
VALIDATION is not available because there is no eligible TRAIN-selected
anchored policy. No next phase is launched automatically.

## Technical recovery cross-reference

The original failed attempt above remains immutable and retains its
`TRAIN_INCOMPLETE_OR_BLOCKED` status. A separately authorized same-seed
technical recovery completed under a new approved snapshot and output
namespace; see [`M8_TRAIN_RECOVERY_REPORT.md`](M8_TRAIN_RECOVERY_REPORT.md).
That recovery selected frozen B on exploratory TRAIN only. It does not
validate an adaptive improvement or alter the historical failure record.
