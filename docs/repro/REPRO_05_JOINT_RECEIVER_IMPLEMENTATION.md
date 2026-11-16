# REPRO-05 — joint receiver implementation

## Scope and status

REPRO-05 adds an isolated Encoder A receiver that scores all 16 trellis edges directly against the public complex `ReceiverObservation`. It does not hard-demodulate to triples before Viterbi. The implementation is a project-defined complex-baseband reconstruction; it is not claimed to be paper-exact, and it leaves `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN.

The public entry point is `run_joint_receiver(observation, receiver_config) -> JointReceiverResult`. The observation must be the exact REPRO-03 type, have complex128 samples and consistent int64 sample indices, and declare eight samples per symbol. `ChannelResult`, `EvaluationTruth`, transmitter bits, and reference phase sequences are rejected or absent from the API.

## Per-symbol calculation

The receiver reads the declared sample block `k*8 + timing_offset_samples .. (k+1)*8-1`. For each canonical Encoder A edge it obtains the coded triple from the REPRO-02 transition table, applies the versioned reconstructed ADR-002 natural-binary mapping, and forms the explicitly configured 8PSK symbol `A exp(j(phi0 + b*pi/4))`. The symbol is repeated over the selected ZOH sample block.

For the supported memoryless single-path model, the pre-update estimate `h_pre[k]` multiplies every candidate waveform. Sixteen metrics and a flat-prior soft edge-weight vector are then formed. The posterior-weighted residual mean updates only the state for symbol `k+1`. Current-symbol predictions and metrics never use the post-update estimate.

The float-metric Viterbi sums the selected branch costs across the four-state Encoder A trellis. It supports configured initial state, unknown/free final state, and explicit `zero_tail_2` constraint. The implemented decoder is full-frame traceback; its depth is `None`, and it does not claim eta=20.

## Supported channel profiles

- `identity_project_v1`: supported and independently checked.
- Explicit receiver-known constant complex gain: supported through `channel_mode=known_static_complex_gain`.
- `single_path_rician_awgn_project_v1`: the causal estimator runs from observation only; a noisy/fading run is diagnostic and carries no perfect-recovery guarantee.
- Any declared multipath profile: rejected as `MULTIPATH_JOINT_RECEIVER_PARTIAL`. Delayed multipath introduces ISI and needs memory/survivor-aware candidate history not present in this implementation.

The implementation has no equalizer or genie channel-state path. A configured known static gain is receiver information only when explicitly supplied in the receiver config.

## Result and reproducibility

`JointReceiverResult` retains sample ranges; the explicit 16-edge source/target/input/output/phase table; candidate symbols and complex predictions; the estimator value used by every candidate; metric/posterior rows; pre/post estimator state and full channel estimate; innovations; processed and unprocessed sample indices; Viterbi state metrics/survivors/path; decoded bits; observation/config hashes; mapping fingerprint; timings; and array hashes. NPZ/JSON output is isolated under `outputs/repro05/`; diagnostic SVG files are generated from actual result arrays. BER/SER is computed only by `evaluate_joint_receiver` after decoding. The CLI accepts optional `--separate-config` to run REPRO-04 on the same serialized observation and save an evaluation-only paired comparison.

The stable interface and scientific limitations are detailed in the neighboring REPRO-05 metric, recursion, posterior, multipath, integration and verification reports.
