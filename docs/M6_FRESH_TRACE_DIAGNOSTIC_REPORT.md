# M6b — authorized fresh-seed causal trace diagnostics

**Status:** authorized fresh-seed causal trace diagnostics, **NOT new performance evidence**, **NOT established scientific root cause**, **NOT paper-exact receiver**. Exactly the three preregistered diagnostic sequences were run. No Monte Carlo, tuning, sweep, M5j/M5h rerun, or further stage was executed. `paper_exact:false` and `receiver_enabled:false` remain unchanged.

## 1. Approved configuration and provenance

The immutable M6b-prep draft remains `design_status="proposed"`,
`execution_authorized=false`, `execution_scope="none"`.
The separate [approved run snapshot](../configs/m6b_trace_diagnostic_approved_run.json)
uses `design_status="approved_diagnostic"`,
`execution_authorized=true`, `execution_scope="m6b_trace_only"`, and records
the explicit authorization in this M6b-run instruction. After normalizing only
authorization fields and the separately approved resource limits, the approved
snapshot exactly matches the frozen draft.

| Fingerprint | SHA-256 |
|---|---|
| Frozen draft config | `218881f447919b27c4b598269e6d9c9184187ee51cb353d3a3acacfe2a2dc844` |
| Approved run config | `700f4af81b5dc92ae4b1a685d93d25cfcdf85b344e458fa538b690a452f119ee` |
| Runtime source tree | `1f2d4ef93ff5e1f1b097765014d8602448f42e392a073e66b5a86640afb950cc` |

The runtime fingerprint is the SHA-256 of the canonical sorted per-file SHA-256
map for all `src/hf_tcm/**/*.py` files. The full map is in the output
`config_fingerprint.json`. Git revision is unavailable because this workspace
has no `.git` metadata. Runtime: Python 3.13.13, NumPy 2.3.3, Windows 11.

## 2. Execution completeness and fresh RNG provenance

All three planned IDs completed, in order, with no numerical/decoder failure:

| Run ID | run_index | Data seed | Noise seed | Metadata seed | Received SHA-256 |
|---|---:|---:|---:|---:|---|
| `m6b_causal_trace_20261030_v1:run-001` | 0 | 8602586874629705848 | 16460929233105184742 | 310251496497998953 | `6a2b6a1918f50e9182b0b6bc1a02e12c654062c03af4ac25f078e81b116317aa` |
| `m6b_causal_trace_20261030_v1:run-002` | 1 | 10224026525733600054 | 8299842525227244502 | 6795341926385133457 | `63ab81cd2bc2d12b01d984ea10a29e467658f81bc334600973f8606940c8589c` |
| `m6b_causal_trace_20261030_v1:run-003` | 2 | 16641262219135861494 | 12682989721120017232 | 15242363563098841395 | `80ebcfa784c5c7f5c80ab2d3b21f29fa90399d4db7d9a887f386d56ad7f647fa` |

For each run the recorded derivation is
`SeedSequence(master_seed, spawn_key=(1295337521,306,run_index,stream_code)).generate_state(1,dtype=uint64)[0]`, then PCG64. Roots were data `2026103001`, noise `2026103002`, metadata `2026103003`; stream codes were 11/23/41. The reference bits were generated once, the existing evaluation AWGN API was called once, and one received buffer was passed to B and C. The paired received hashes match in every run. No historical M5 namespace was used.

The fixed profile was reconstructed offline, L=1, real `a=0.75`, zero delay,
normalized 8PSK, rectangular ZOH 8 sps, ADR-012, ADR-005, ADR-013, and ADR-015
at effective discrete `gamma_b=5 dB` (`sigma_squared=0.7115124735378853`). This
is not physical HF Eb/N0. B and C used the exact authorized fixed policies and
identical initial state, beta, mu0, clocks, and received input.

## 3. Trace availability, clocks, and causal validation

The output namespace is
`outputs/m6b_trace_diagnostics/m6b_causal_trace_20261030_v1/`. Each completed
run has 32 B rows and 32 C rows: **192 symbol rows total**. Each frozen metric
history is exactly `(32,16)`; decoded path is `(32,)`; decoded information bits
are `(64,)`. Per-symbol candidate and posterior rows are `(16,)`, predicted I/Q
is `(16,2)`, and the observed I/Q operand is `(2,)`.

The trace values are copied from actual M6a B4d/B4c histories. The recorded
causality checks passed in all runs: windows `[8f,8f+7]`, prediction cutoff
`8f-1`, observation cutoff `8f+7`, one first-edge ADR-004 prior without
transition, 31 continuation rows, canonical IDs 0–15, one monolithic segment,
post-state handoff to the next pre-state, frozen B state invariance, exact
row-to-frozen-matrix equality, normalized finite posteriors, and one final B5b
decode per mode. This validates implementation ordering and trace integrity;
it does not establish source-model correctness.

`transition_predicted_posterior_q` is recorded as unavailable for every row.
The weighted innovation is marked derived and independently replayed with a
scalar sum from the recorded posterior, observed mean, and predicted I/Q; it is
not represented as a raw B4c field. Reference bits and true gain are absent
from receiver inputs and receiver traces. BER/SER and coefficient error are
evaluation-side only. No received arrays were persisted.

## 4. Paired divergence and evaluation-only counts

Floating comparisons used `rtol=1e-12`, `atol=1e-14`. Absolute and
sequence-local positions are equal because both origins are zero.

| Run | First post-state divergence | First pre-state divergence | First metric divergence | First posterior divergence | First decoded-path divergence | Different decoded edges | B bit / symbol errors | C bit / symbol errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| run-001 | 0 | 1 | 1 | 1 | 17 | 15 | 0/64, 0/32 | 16/64, 14/32 |
| run-002 | 0 | 1 | 1 | 1 | 11 | 16 | 0/64, 0/32 | 16/64, 15/32 |
| run-003 | 0 | 1 | 1 | 1 | 10 | 21 | 0/64, 0/32 | 26/64, 21/32 |

These are per-sequence descriptive diagnostic counts, not a pooled estimator,
performance sample, or comparison with uncertainty. In each run C's first
post-update state differs at symbol 0, while its first pre-state, metric, and
posterior divergence occurs at symbol 1. This matches the implemented
`post-state(f) -> pre-state(f+1) -> next metric` dependency. The later path
divergences are observed outputs, not proof that the update caused the errors.
The complete 32-edge B/C decoded paths and 64 information-bit vectors are
retained in each run's `B_trace.json` and `C_trace.json`; the divergence lists
are in `paired_comparison.json`. Evaluation-only raw errors and rates are in
`evaluation_only.json`.

## 5. Coefficient diagnostics

Coefficient error is evaluated after decoding against the reconstructed
quadrature target `(a,a)` used by the existing diagnostic convention. It never
enters recursion.

| Run | Mode | Initial error norm | Final error norm | Largest absolute coefficient | Largest update norm | Finite | Max posterior-sum error |
|---|---|---:|---:|---:|---:|---|---:|
| run-001 | B | 0.366742 | 0.366742 | 0.910000 | 0 | yes | 1.11e-16 |
| run-001 | C | 0.366742 | 1.493646 | 0.808973 | 0.317404 | yes | 1.11e-16 |
| run-002 | B | 0.366742 | 0.366742 | 0.910000 | 0 | yes | 2.22e-16 |
| run-002 | C | 0.366742 | 0.771920 | 0.786627 | 0.378647 | yes | 2.22e-16 |
| run-003 | B | 0.366742 | 0.366742 | 0.910000 | 0 | yes | 1.11e-16 |
| run-003 | C | 0.366742 | 1.431735 | 0.795126 | 0.331659 | yes | 1.11e-16 |

All 32 per-symbol error norms and update norms are retained in each
`evaluation_only.json`. No “large increment” threshold was preregistered, so
that field is null rather than selected post hoc. C's estimated coefficient
error increased from its initial value by the final symbol in all three runs;
this observation alone does not establish instability or explain the decoded
errors.

Example C row values (I/Q order), showing the recorded operands and actual
increment without causal overinterpretation:

| Run / symbol | Derived innovation | Fluctuating increment | Pre full I/Q | Post full I/Q |
|---|---|---|---|---|
| run-001 / 0 | `(0.271859,-0.177363)` | `(0.032151,-0.101027)` | `(0.42,0.91)` | `(0.452151,0.808973)` |
| run-002 / 0 | `(-0.229525,-0.065637)` | `(-0.143334,-0.123373)` | `(0.42,0.91)` | `(0.276666,0.786627)` |
| run-003 / 0 | `(0.098561,-0.108128)` | `(-0.028504,-0.114874)` | `(0.42,0.91)` | `(0.391496,0.795126)` |

## 6. H1–H8 evidence and status

| Hypothesis | M6b observable and independent check | Limitation / status | Minimal next independent test |
|---|---|---|---|
| H1: fixed `alpha_prime/K_tilde` behavior | C updated on all 32 symbols; final coefficient error exceeded initial in all 3 runs; update norms remain finite. | No alternative policy, stability criterion, or source-derived optimum was tested. **UNRESOLVED** as a cause. | Hand-derived component update on several fixed residual vectors using only the frozen coefficients; no BER ranking. |
| H2: ADR-012 observed I/Q vs [A](5) | Actual 8-sample mean, predicted I/Q, and metric rows are traceable; clock checks passed. | No independent source-convention mapping was performed. **UNRESOLVED**. | One literal complex window mapped by hand through ADR-012 and an independently transcribed [A](5) convention. |
| H3: innovation meaning in [A](1) | Derived innovation agrees with the scalar replay; M6a manual [A](1) oracle and current state handoffs agree. | This verifies project algebra, not paper notation or intent. **UNRESOLVED**. | Independent source transcription of indices/signs, then a one-step hand oracle with explicit operands. |
| H4: correction direction/scale/sign | Nonzero signed increments match fixed `K_tilde` and recorded derived innovations; all trajectories finite. | No author-intended correction convention is established. **UNRESOLVED**. | Hand-calculated positive/negative I/Q residual cases and componentwise comparison. |
| H5: posterior weighting / 16 hypotheses | Actual posterior inputs/results, predictions, canonical edge IDs and distinct phase indices are stored; sums normalize. | No source correspondence or counterfactual operand comparison. **UNRESOLVED**. | Independently enumerate 16 edges and verify posterior-weighted operand and edge-to-phase mapping against a source-derived convention. |
| H6: update affects later metrics | In all runs post-state differs at symbol 0; pre-state/metrics/posterior first diverge at symbol 1. | This supports the code dependency; the contribution to decoded errors is not isolated. **SUPPORTED implementation dependency; M5j/M6b error attribution UNRESOLVED**. | A separately frozen no-update or delayed-update ablation on the same future authorized input, with no parameter selection; requires its own approval. |
| H7: frame-constant forward vs per-symbol adaptive model | M6b traces exhibit per-symbol adaptive states. | No frame-constant control was run; the model-timebase distinction is documented, contribution untested. **SUPPORTED as a model distinction; contribution UNRESOLVED**. | Hand-specified frame-constant and per-symbol schedules on identical deterministic symbols; decide source timing first. |
| H8: ADR-005 pseudo-likelihood vs source-faithful likelihood | All captured metrics/posteriors use the declared ADR-005 reconstruction. | No source-faithful likelihood was implemented or compared. **SUPPORTED as a declared distinction; contribution UNRESOLVED**. | Resolve SCI-METRIC-02 from source, then compare an independent literal likelihood oracle on hand-set rows. |

No mechanism is established as the cause of M5j or these three diagnostic
outcomes. M5j historical per-symbol state and metric history remains
**HISTORY UNAVAILABLE** and has not been reconstructed.

## 7. Output integrity, resources, and historical protection

All three runs completed and each run directory has an atomic checkpoint,
canonical trace-pair round-trip, separate B/C traces, evaluation-only counts,
comparison, status, and file hashes. The root `integrity.json` covers 25
pre-integrity output files; its tree digest is
`19b58bd057ffc1c8b725b225f4698a26b120c88dec6950fbaecd058c206a9ba3`.

Measured wall-clock time from execution start through final summary was
`0.6959 s`, below the five-minute budget. Windows working-set sampling was
attempted every 0.2 s but `GetProcessMemoryInfo` failed with error 6 before a
sample could be recorded. **RSS is unavailable and the 512 MiB budget cannot be
verified**; no memory estimate is substituted. This is a monitoring limitation,
not a run failure. One process was used; no multiprocessing.

The historical integrity test passed before and after execution. M5f records,
M5h output tree, and M5j output tree retain their M6a/M5k baseline digests;
no M5f/M5h/M5j output was written or modified. The new output tree is isolated
under M6b only.

## 8. Scientific limits and gates

This remains a three-sequence reconstructed diagnostic at one effective
discrete gamma point, one L=1 real gain, independent sample-level AWGN,
ADR-005 pseudo-likelihood, ADR-012 observed-IQ, ADR-013 conditional full
Viterbi, fixed mismatched initial estimate and fixed update coefficients. It
does not calibrate physical radio energy, generalize to HF/multipath/complex
fading/correlated noise, reproduce a source-paper joint receiver, or establish
performance. No tuning or evaluation adaptation was done. SCI-02, SCI-03, and
SCI-METRIC-02 remain open; ADR-009/011 remain proposed. No ADR is changed.

| Gate | Status |
|---|---|
| Exact approved config and seed separation | **READY / verified** |
| Three planned paired runs and 192 rows | **READY / complete** |
| Causal trace/schema/frozen-metric integrity | **READY / passed** |
| Numerical failures | **None** |
| Wall-clock budget | **READY / 0.6959 s** |
| RSS budget | **UNVERIFIED / monitor unavailable** |
| H1–H5 root-cause attribution | **BLOCKED / unresolved** |
| H6 implementation dependency | **SUPPORTED; error contribution unresolved** |
| Source fidelity / general performance claims | **BLOCKED / unresolved and out of scope** |

The next minimal independent task is a hand-transcribed source-convention
control for one symbol: compare ADR-012 observed-IQ reduction and [A](5)
predictions componentwise, then check one [A](1) update from explicit operands.
That test needs source equation transcription and must not run a new signal
experiment. Do not launch it automatically.
