# M6b-prep — fresh-seed causal trace diagnostic protocol

**Status:** validated fresh-seed causal trace protocol, **NOT executed diagnostic experiment**, **NOT new BER evidence**, **NOT established root cause**. This is preparation only. `paper_exact:false` and `receiver_enabled:false` remain unchanged. No received samples, bits, noise, RNG streams, receiver calls, Monte Carlo, tuning, or M5j rerun were performed.

## 1. Candidate experiment and scientific intent

The candidate diagnostic is three independent fresh-seed sequences, each with
F=32 TCM symbols and 64 information bits. Every sequence is processed by
frozen B and adaptive C using the exact same received buffer. Run order is
`run-001`, `run-002`, `run-003`; the diagnostic is one process, monolithic per
sequence, with no within-sequence reset. Its purpose is to observe the already
implemented ordering

`estimator update -> next-symbol candidate metrics -> posterior -> final B5b path`.

There is no BER/SER estimand, no parameter selection, and no decision rule that
maps a trace divergence to root cause. The 3-sequence count is a compact
diagnostic workload, not a performance sample size or claim of statistical
power.

| Setting | Frozen candidate |
|---|---|
| Profile | `reconstructed_offline`, L=1, real gain a=0.75, zero delay |
| Modulation/time | normalized 8PSK, rectangular ZOH, 8 samples/symbol |
| Observation/likelihood/decoder | ADR-012 observed I/Q; ADR-005 pseudo-likelihood; ADR-013 conditional full Viterbi |
| Noise | ADR-015 independent circular complex sample AWGN |
| Effective point | `gamma_b_eff=5 dB`; `sigma_squared=4a²/10^(5/10)=0.7115124735378853`; not physical HF Eb/N0 |
| Shared B/C state | full/fluctuating I/Q `(0.42,0.91)`; beta=0.7; mu0 `(0,0)` |
| B | alpha-prime=1; K-tilde `(0,0)`; mu0 `(0,0)` |
| C | alpha-prime=0.85; K-tilde `(0.35,-0.2)`; mu0 `(0,0)` |

These are M5j's fixed historical policies, not a tuning result. They stay
unchanged in this protocol.

## 2. Draft and execution authorization gate

Machine-readable draft: `configs/m6b_trace_diagnostic_draft.json`.

It remains exactly `design_status="proposed"`,
`execution_authorized=false`, `execution_scope="none"`, and has no approval
record. `validate_m6b_trace_diagnostic_config()` checks completeness and the
fixed science/seed/clock/storage contract without deriving child seeds.
`guarded_m6b_execution()` validates first, then requires
`approved_for_m6b_trace`, `execution_authorized=true`, exact scope
`m6b_trace_diagnostic_only`, and an explicit approval record before invoking
its continuation. A malformed or proposed draft raises before that
continuation can create RNG generators, samples/noise, or call a receiver.
Preparation tests use spies and establish zero continuation calls for the
current draft. No approved config is created or accepted in M6b-prep.

## 3. Fresh RNG provenance and pairing

The planned namespace is `m6b_causal_trace_20261030_v1`, isolated from
historical M5f/M5h/M5j roots. Roots are metadata only at this stage:

| Stream | Master root | Stream code |
|---|---:|---:|
| Diagnostic data | 2026103001 | 11 |
| Diagnostic noise | 2026103002 | 23 |
| Diagnostic metadata | 2026103003 | 41 |

For zero-based run index `r=0,1,2`, future derived seed provenance uses
`SeedSequence(master_seed, spawn_key=(1295337521, 306, r, stream_code))`,
`generate_state(1,dtype=uint64)[0]`, and PCG64. Planned provenance records the
master, run index, spawn key, stream code, and bit-generator name; the child
seed is derived and recorded only after a separate run authorization. No
`SeedSequence`, `Generator`, or random values are created by protocol
validation or the blocked gate.

M5f roots 2026102801–2803, M5h roots 2026102901–2903, M5j roots
2026110101–0103, and the M5j bootstrap seed are explicitly reserved. Data,
noise, and metadata root and stream codes are distinct. At run time one
received buffer and digest are shared by B/C. Hash provenance is SHA-256 over
the exact contiguous complex128 received bytes consumed by M6a; both modes
must report the same digest. Exact seed, NumPy, Python, platform, config, and
source-file fingerprints belong in each run manifest.

## 4. Trace lineage and unavailable operands

Future trace rows are compact serialization of the actual M6a
`ReconstructionCausalTracePair`, not a replay of its estimator/posterior math.
The source-to-field mapping is:

| Persisted field | Source and interpretation |
|---|---|
| Run ID, config SHA-256, software provenance | Planned manifest plus the exact authorized runtime config/source fingerprints |
| Received SHA-256; B/C shared identity | M6a trace pair's digest, computed on the actual shared complex128 buffer |
| Absolute symbol, estimator tick, local position, segment label, window/cutoffs | M6a row's actual B4d/B4c provenance; for candidate origins all are zero, tick and symbol still remain distinct fields |
| Pre/post fluctuating/full I/Q, regular mu0 | Actual B4d state snapshots and supplied per-symbol operand |
| Observed I/Q mean, predictions, candidate costs | Actual B4c result; arrays are `(2,)`, `(16,2)`, and `(16,)` |
| Hypothesis IDs and phase indices | Actual B4c order and labels; canonical edge IDs remain separate from 8PSK phase indices |
| Edge mode and posterior provenance | Actual B4c edge mode, posterior input kind, and transition provenance; first edge uses ADR-004 prior without transition, continuation uses the previous posterior and one recorded transition |
| Posterior input and current posterior | Actual B4c inputs/outputs, each `(16,)`; posterior sum/normalization retained |
| alpha-prime, K-tilde, coefficient increments | Exact update operands and actual pre/post state differences |
| Weighted innovation | Derived from actual B4c posterior, observed mean, predictions using `sum_h p[h]*(observed-predicted[h])`; explicitly not a raw B4c field |
| Transition-predicted posterior q | `{"status":"unavailable","value":null}`; no approximation or second posterior update |
| Frozen metric matrix and final path/bits/cost | Exact B4d rows and one final B5b output; shapes `(32,16)`, `(32,)`, `(64,)` |
| Trace integrity | Schema, finite-value, clock, B/C parity, row/matrix equality, and SHA-256 checks |

The trace stores no received samples and no receiver-side reference bits. If
the evaluation harness needs reference bits for its own post-decode diagnostic,
they belong in a separate evaluation-side artifact and never enter B4d/B5b.
True gain a is confined to evaluation-side waveform generation and likewise
never enters the receiver API.

## 5. Clock and B/C comparison contract

Absolute sample, absolute symbol, estimator tick, sequence-local position, and
processing segment are separate labels. For symbol f at sample origin O,
window is `[O+8f,O+8f+7]`, prediction cutoff `O+8f-1`, and
observation/posterior cutoff `O+8f+7`. The planned run uses O=0 and starts
symbol, estimator, and local-position origins at zero; their equality in this
particular candidate does not create an implicit conversion rule.

The schema rejects skipped/duplicate symbol positions, nonmatching windows,
bad cutoffs, or a non-monolithic segment label. Runtime M6a still enforces its
actual causal contract: metrics from pre-state, update after the completed
window, post-state used next symbol only, and one B5b decode after frozen
history. No future-sample, reset, or update-before-metric path is allowed.

B/C comparisons use frozen `rtol=1e-12`, `atol=1e-14`, exact absolute labels,
shared received digest, and identical initial full/fluctuating state and beta.
They report per-symbol pre-state, posterior, metric-row, coefficient-increment,
and selected-edge differences, plus first post-state, metric, posterior, and
decoded-path divergence positions. Distinguish:

1. runtime ordering;
2. mathematical dependency;
3. observed output difference;
4. established causal root cause.

The first three never imply the fourth without additional controlled evidence.

## 6. Storage, integrity, and failures

Future namespace:
`outputs/m6b_trace_diagnostics/m6b_causal_trace_20261030_v1/<run-id>/`.
Each run has `manifest.json`, `config_fingerprint.json`, `B_trace.json`,
`C_trace.json`, `paired_comparison.json`, and `status.json`. JSON schema v1
uses sorted keys, compact separators, UTF-8, `allow_nan=false`; numeric arrays
carry explicit dtype, shape, and values. Non-finite data invalidate the trace
and produce a failure status instead of a NaN/Infinity payload. The serializer
hashes canonical payload bytes and the future writer records per-file SHA-256
in the manifest. Future writes use a same-directory temporary file, flush and
fsync, then atomic replace; an existing experiment namespace is never
overwritten. No output tree is created during M6b-prep.

Missing B or C trace blocks the paired comparison. No retries with new seeds,
silent exclusions, or replacements are allowed. A partial run receives a
failure record; historical M5 output locations are outside the write policy.

## 7. Candidate resource policy

For a separately authorized run: one process, no multiprocessing, three
sequences of 32 symbols, full per-symbol B/C trace, deterministic run order,
and one atomic checkpoint per run (six B5b passes total). This is a candidate
workload only. Runtime and RAM are not estimated; resource limits must be set
at authorization. No benchmark was run.

## 8. Scientific boundaries and gates at M6b-prep close

The gates below record the preparation state. The later authorized execution
and updated gate status are documented under “M6b-run authorized execution
addendum” at the end of this protocol.

The profile remains reconstructed and offline, with ADR-005 pseudo-likelihood,
ADR-012 observed-IQ convention, ADR-013 conditional full Viterbi, and ADR-015
independent circular complex sample AWGN at one effective discrete point. It
does not calibrate physical radio energy, validate the source-paper receiver,
or generalize to HF, multipath, fading, or correlated noise. SCI-02, SCI-03,
and SCI-METRIC-02 remain open; ADR-009/011 remain proposed. No ADR is changed.

| Gate | Status |
|---|---|
| Complete draft, fixed parameters, run IDs, clock and output namespace | **READY** |
| Fresh data/noise/metadata namespace separation | **READY — provenance only; no streams created** |
| Trace schema and synthetic serialization round-trip | **READY** |
| Authorization guard blocks proposed draft before continuation | **READY** |
| Execution authorization | **BLOCKED — draft proposed/false/none** |
| New received data, trace rows, or diagnostic evidence | **NOT RUN** |
| H1–H8 root-cause determination | **BLOCKED / unresolved** |

The next minimal step is separate explicit authorization of a frozen run
config, including resource limits and an approved-config fingerprint. Only then
could M6b-run execute the three planned sequences. Do not launch that run as
part of preparation.

## Verification evidence

The focused protocol suite passed 12 synthetic tests. The full repository suite
passed 760 tests in 5.63s, including the M5f/M5h/M5j baseline-byte integrity
check. `ruff check src tests` passed; `ruff format --check src tests` reported
124 files already formatted. Tests did not launch M6b: its guard spy remained
uncalled for proposed/invalid configs, and the protocol module contains no
receiver import or RNG/data/noise generation path. No M6b output directory or
received data was created.

Final verification supersedes the earlier timing paragraph: after all protocol,
provenance, and immutability assertions were in place, 12 focused tests passed
in 0.48s and the full suite passed 760 tests in 6.83s on a fresh basetemp.
Both requested Ruff commands passed; 124 files were already formatted.

## M6b-run authorized execution addendum (2026-10-30)

The separate approved snapshot at `configs/m6b_trace_diagnostic_approved_run.json` was authorized by the user instruction for M6b-run only. It exactly preserved the frozen M6b-prep science, policies, clocks, seeds, and schema; only authorization fields and the explicitly requested resource limits changed. Draft and approved config fingerprints, runtime code fingerprints, RNG provenance, and the execution manifest are in `outputs/m6b_trace_diagnostics/m6b_causal_trace_20261030_v1/`.

Exactly run-001 through run-003 completed. Each run generated one reference bit vector, one ADR-015 AWGN realization, and one received buffer shared by B/C; 192 total per-symbol rows were serialized. B5b ran once per mode after each frozen 32x16 metric matrix. No BER-based selection, Monte Carlo, tuning, or further run occurred. See `M6_FRESH_TRACE_DIAGNOSTIC_REPORT.md` for run-level hashes, divergence labels, error counts, coefficient diagnostics, and limitations.

Measured wall time was 0.6959 s. Periodic RSS sampling failed at `GetProcessMemoryInfo` (error 6), so RSS is unavailable and the 512 MiB budget is not verified. M5f/M5h/M5j hashes passed the pre-run and post-run integrity checks. H6 is supported as an implementation dependency in these traces; contribution to decoded errors remains unestablished. H1-H5 remain unresolved; H7/H8 remain model distinctions whose causal contributions are unresolved. M5j historical per-symbol trace remains unavailable; no M5j conclusion is changed. The result is diagnostic only, not performance evidence or an established root cause.
