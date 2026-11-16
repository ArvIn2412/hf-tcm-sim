# REPRO-05 — final report

## Implemented result

The REPRO-05 joint receiver is an isolated Encoder A path. It accepts only the exact REPRO-03 `ReceiverObservation`, scores 16 edge predictions directly against each received 8-sample symbol, forms Euclidean or squared-Euclidean branch metrics, calculates stable flat-prior edge pseudo-weights, causally updates a complex single-path estimate, and runs four-state full-frame float-metric Viterbi. It does not perform hard 8PSK-to-coded-bit demodulation before Viterbi.

The API is `run_joint_receiver(observation, JointReceiverConfig) -> JointReceiverResult`. The result includes observation/config SHA-256, encoder/mapping identifiers and mapping-table fingerprint, edge/source/target/input/output/phase descriptions, candidate symbols and waveforms, the exact estimator value used by every candidate, metric/posterior rows, estimator pre/post states and innovations, exact inclusive sample ranges, all processed/unprocessed sample indices, Viterbi metrics/survivors/path, decoded bits, and timing/hash metadata. NPZ/JSON output and plots are isolated under `outputs/repro05/`. The CLI accepts `--config`, `--input`, `--output`, `--validate-only`, `--print-summary`, optional evaluation `--reference`, and optional paired REPRO-04 `--separate-config`.

## Source and mathematics

The available S1 source is `references/source_paper_2026.docx`, SHA-256 `a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8`. The REPRO-01 equation register is the reviewed basis for A(1), A(2), and A(5). A(2) does not resolve residual square/norm semantics. The squared residual is the project default from REPRO-01, not an author-confirmed transcription. A(1)'s complex-baseband posterior-weighted residual update is `adaptive_project_v1`, a causal project reconstruction. A(5) is structurally consistent under the project's complex convention, not established as an exact full predictor. ADR-002 remains a reconstructed edge-to-phase mapping.

The estimator consumes only the received samples and declared receiver configuration. For each symbol, the pre-update estimate forms all predictions; metrics and normalized pseudo-weights are computed; a weighted residual mean then updates the state for the next symbol. Pseudo-weights are not HMM state marginals. The Viterbi operates directly on raw selected-profile branch metrics, uses canonical deterministic ties, and is full-frame. `decoder_depth=null`; eta=20 is not claimed.

Identity and explicitly receiver-known static complex gain are supported. A seeded single-path Rician profile runs without hidden truth and exercises the adaptive recursion, but does not establish estimator accuracy or physical HF correspondence. Delayed multipath is rejected as `MULTIPATH_JOINT_RECEIVER_PARTIAL`, since a symbol-local predictor omits ISI and no survivor/history-aware predictor is implemented.

## Reference and paired run

The existing 20,000-symbol REPRO-02 reference was run through an identity REPRO-03 channel; it was not regenerated or modified. Receiver observation SHA-256: `74697c52e4537bf899e1143f1b2c7111d0d121505566c94d6a0bb097936bd722`. Receiver config SHA-256: `522b0922a18a0c0230868d778da47a74081f71c5bf1e1b927730c915da8cb462`. Result-array SHA-256: `b4ee1d8182f06dc05d09d436ec438f7453811d535b24edd8bff236e05368cf52`. NPZ SHA-256: `bd636e1a29a210ddda700e242aa0bb006d5fe4ea654e8e429fad23b1d0a76bea`. Final manifest SHA-256: `e8f84f6970fea42187471440dd1a56715c5a8409c763bb9ff09bd9cd76a7cbb8`.

The run decoded 40,000 information bits and 20,000 phase symbols with zero errors on this noiseless identity fixture. The optional REPRO-04 paired arm used the same observation SHA and evaluation boundaries, and also had zero errors. These are deterministic one-frame checks, not statistical evidence. The result includes 26 arrays: candidate predictions `(20000,16,8)`, candidate estimator values `(20000,16)`, metrics and pseudo-weights `(20000,16)`, plus 160,000 exact sample indices. Fourteen SVGs were hash-verified and parsed from actual result arrays, including received/candidate constellations, metrics, posterior weights, estimates, innovation, Viterbi metrics/path, sample window, evaluation errors, and joint/separate bit paths.

One-machine, one-run timing (not a benchmark): receiver 1.621 s total; candidate generation 0.038 s; metric calculation 0.535 s; posterior/estimator 0.760 s; Viterbi 0.178 s; all plot output 3.995 s. Numeric arrays occupy 55,360,482 bytes; final receiver output tree is 18,113,934 bytes. The F=256 identity test and F=32 seeded single-path adaptive Rician test passed.

## Verification and frozen data

- Focused REPRO-05 tests: **18 passed**.
- Final full suite: **1055 passed in 70.99 s** using Windows user-temp basetemp because workspace/OneDrive pytest cleanup is ACL-blocked.
- `ruff check src tests`: PASS.
- `ruff format --check src tests`: PASS, 216 files formatted.
- Output array, NPZ, JSON manifest, nested REPRO-04 bundle, and 14 SVG hashes: PASS.
- Historical M5-M10 fingerprint recount: **694/694 matched**, zero changed/missing.

`paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN remain. No Monte Carlo, BER-vs-SNR curve, GUI change, REPRO-04 mathematics change, REPRO-06, or historical artifact modification occurred.

## REPRO-06 handoff

REPRO-06 may separately define and test eta=20 traceback/decision semantics, including tail and boundary rules. It must not conflate a visualization window with decoder depth. A future multipath receiver requires an explicit survivor/history-aware ISI predictor and complexity tests. Source-exact claims still require resolution of A(2), A(1) operands/initial values, phase labeling, and source-v7 channel/SNR conventions. REPRO-06 was not started.
