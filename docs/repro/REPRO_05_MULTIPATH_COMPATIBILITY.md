# REPRO-05 — channel compatibility

| Public observation profile | REPRO-05 behavior | Interpretation |
|---|---|---|
| `identity_project_v1` | Supported | Exact noiseless reference for the selected Encoder A / ADR-002 project map. |
| user-declared nominal single path | Supported | Receiver starts from an explicit nominal complex coefficient. |
| explicitly known static complex gain | Supported | Gain is provided in receiver config, not read from channel truth. |
| `single_path_rician_awgn_project_v1` | Runs as causal adaptive diagnostic | It does not know the actual fading history; no perfect-decoding promise. The AR(1) profile remains an engineering reconstruction, not Jakes/HF fidelity. |
| declared delayed multipath | Rejected | `MULTIPATH_JOINT_RECEIVER_PARTIAL`; the one-symbol candidate predictor omits ISI. |

REPRO-03's delayed path equation can place previous-symbol energy in the current observation. A memoryless candidate `h[k] x_e[k]` would then compare the wrong waveform. This milestone does not implement per-survivor channel-estimator banks, delayed symbol-history hypotheses, boundary-aware ISI prediction, or complexity-controlled joint channel/trellis inference. No multipath receiver result is generated or used for algorithm superiority claims.
