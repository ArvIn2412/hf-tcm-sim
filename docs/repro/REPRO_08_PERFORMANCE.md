# REPRO-08 performance and artifact integrity

## Measured runs

| Run | Work | Wall time | Notes |
|---|---|---:|---|
| Phase A | Eight F=64 deterministic channel controls | Stored per receiver in `outputs/repro08/phase_a_controls/phase_a_records.json` | Single-seed diagnostics, not benchmark |
| Phase B v1 | 60 F=256 pairs, three arms | 4.162 s | Static public two-path, low/moderate noise range |
| Phase B v2 | 60 F=256 pairs, three arms | 4.098 s | Static public two-path, exploratory range-finding follow-up |
| Phase B v2 adaptive arm | 60 F=256 REPRO-06C calls replaying the same 60 v2 observations | Aggregate wall time not captured by the interrupted aggregation script | 60/60 observation hashes matched; no runtime claim is made |
| Phase C | One F=20,000 Rician AR(1) pair, Joint adaptive + B0 | 147.804 s | Below explicit 300 s wall budget; resource check, not long series |

Timings are individual run measurements on the recorded environment and are not a benchmark distribution. The Phase C Joint receiver itself used 146.872 s; its paired B0 call and setup account for the remainder. It compared 40,000 bits and the common receiver-observation SHA-256 was `29bdb390f3dfa3cfa70c41efedcc6807428a8b8289fe2db02e7d2bcc4ef66c70`.

## Outputs

- `outputs/repro08/phase_a_controls/phase_a_records.json`
- `outputs/repro08/phase_b_static_public_pilot_v1/`
- `outputs/repro08/phase_b_static_public_pilot_v2/`
- `outputs/repro08/phase_c_long_frame_bounded_v1/`
- `outputs/repro08/plots/repro08_phase_b_ber.svg`
- `outputs/repro08/plots/repro08_phase_b_pair_ser.svg`
- `outputs/repro08/plots/repro08_phase_b_delta_ber.svg`
- `outputs/repro08/plots/repro08_repro07_ber_floor.svg`
- `outputs/repro08/plots/repro08_phase_a_controls.svg`
- `outputs/repro08/plots/repro08_phase_b_adaptive_vs_b1.svg`
- Three read-only selected-trial diagnostics copied from `outputs/repro07/pilot_rician_ar1_f256_v1/plots/point_02/trial_0000/`.

Pilot manifests cover stored configs, per-trial records, aggregate summaries, and computed metrics. The adaptive follow-up stores per-trial configs, seeds, observation hashes, and errors; its aggregate post-processing did not capture runtime. The phase-C record stores exact receiver/transmitter/channel config hashes, independent seeds, observation hash, error counts, and timing. Root manifest: `outputs/repro08/manifest.json`; final verification checked 23/23 payload entries.

No raw full candidate/estimator trace is stored for all Monte Carlo trials. Only selected REPRO-07 diagnostic traces remain in its original namespace. REPRO-07 output directories were read-only inputs for this milestone; REPRO-08 artifacts are isolated under `outputs/repro08/`.
