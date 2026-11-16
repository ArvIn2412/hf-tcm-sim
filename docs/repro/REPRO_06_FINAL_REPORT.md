# REPRO-06 — final report

## Verdict

`REPRO_06_FINITE_DEPTH_READY`  
`HAMMING_ETA20_READY`  
`EUCLIDEAN_ETA20_READY`  
`STREAMING_READY`  
`FRAME_FLUSH_READY`  
`MULTIPATH_JOINT_RECEIVER_PARTIAL`

## Implementation

Added shared `FiniteDepthViterbiDecoder`, `ViterbiConfig`, `DecisionRecord`, and batch `run_viterbi` in `src/hf_tcm/repro/finite_viterbi.py`. η is the count of transitions. In η=20 streaming mode the first regular decision is for symbol 0 after consuming symbol 19 (`decision_available_at=19`, delay 19 later symbols). `consume_metric_row()` emits zero or one decision; `flush()` emits only remaining decisions, reporting each actual depth. The core retains at most η survivor predecessor rows. Compact mode omits long survivor/metric diagnostic matrices.

The final unterminated endpoint is the minimum available state metric, with canonical state tie-breaking; no transmitter final state or reference bits are used. `zero_tail_2` requires a declared frame and constrains the two public tail transitions to `(0,0)`. All information pairs are emitted exactly once, including F<η and the tail for F≥η. Finite-depth local survivor edges can be drawn from overlapping paths and need not join; the result keeps these edge/state facts in decision records and separately re-encodes the emitted information pairs from the configured initial state for a valid decoded state/edge history. `final_path_metric` and `terminal_survivor_state` refer to the selected terminal survivor.

Both receiver configs preserve `full_frame` / null-depth defaults. Article-oriented config factories and the CLI `--decoder-mode finite_depth --traceback-depth 20` select the project η=20 convention. REPRO-04 Hamming decisions/metrics are unchanged. REPRO-05 metric rows, posterior and causal estimator history are unchanged by decoder mode. Receiver inputs remain `ReceiverObservation` only; no EvaluationTruth enters either arm. Full-frame legacy APIs remain in place and were compared to the shared engine.

## Actual reference run

Both finite receivers processed the existing deterministic 20,000-symbol identity observation from REPRO-05: 160,000 samples, SHA-256 `74697c52e4537bf899e1143f1b2c7111d0d121505566c94d6a0bb097936bd722`. They each decoded 40,000 payload bits with zero bit/symbol errors on this noiseless fixture. This is a single integration validation, not a statistical result.

- Both article-oriented receiver configs used `trace_output_mode=compact`; each returned a 20-row maximum survivor ring and omitted full survivor diagnostics (`(0,4)` output matrices).
- Separate Hamming output arrays SHA-256: `814ff1a084a611539e56f415a7951755ae4ab1a323bd9aa0928438b9e963674d`.
- Separate result manifest SHA-256: `f013e95469262178132d289c4201988e88a858a2fd330e39f85b39b147ae6a96`.
- Joint Euclidean result SHA-256: `99fbb0eec5b1625af00483c9dfeb86bd7f860eb4cdb5cc85b0d9ff91874fe19f`.
- Joint result manifest SHA-256: `85aa4356c60fba98d5cdc0aabc6aa7f67265f9dd86b0e5618b7fe90199327fe3`.
- Shared REPRO-06 output manifest SHA-256: `3b5119a43024e261121e8a0ae8f59b0f5e51a2b10102b0cbcbb9131efb6f8ead`; **11/11 listed output files verified**. Both CLI `--validate-only --traceback-depth 20` paths accepted the same observation/config without running a receiver.

The 256-step deterministic decoder-only comparison fixture has its first η=20 decision at symbol 0 / availability 19 and differs from full-frame on information-pair symbol 68. It is a metric-level decoder fixture, not a channel, BER, or performance study. The actual-data SVG is `outputs/repro06/full_vs_eta20_fixture/full_vs_eta20.svg` (SHA-256 `254be29eb4dfd419955f30d86f70d617f5c46b0756dee36d848112f171db6158`).

## Verification

- Focused core and both receiver suites: **63 passed**; the two additional finite zero-tail contract tests passed separately (**2 passed**).
- Full pytest: **1086 passed in 38.42 s**, using `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro06-final2 -p no:cacheprovider` (final rerun after the article-oriented compact-trace default change).
- `ruff check src tests`: PASS.
- `ruff format --check src tests`: PASS, 219 files.
- `python -m compileall -q src/hf_tcm/repro tests/repro`: PASS.
- Historical M5–M10 fingerprint comparison against `tmp/m11d-integrity-before.json`: **694/694 matched**, zero missing or changed.
- Output manifest and all listed files are SHA-256 checked; no historical output directories were written.

One-run timings, diagnostic byte counts, and bounded row counts are in `REPRO_06_PERFORMANCE.md` and `outputs/repro06/performance.json`; no RSS measurement was available. The single-path identity/static-gain and single-path Rician tests pass. Multipath joint decoding remains unsupported due to absent survivor/history-aware ISI prediction.

Source status is unchanged: `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN. η=20 is a project convention matching the requested transition-window interpretation, not proof of the exact author implementation. No Monte Carlo was run. REPRO-07 was not started.
