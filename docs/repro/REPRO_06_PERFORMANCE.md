# REPRO-06 — performance and bounded memory

Measurements in this report are single-run engineering observations, not repeated benchmarks. The workload is the existing deterministic identity-channel REPRO-05 reference metric buffer (`ReceiverObservation` SHA-256 `74697c52e4537bf899e1143f1b2c7111d0d121505566c94d6a0bb097936bd722`); no new channel realization, receiver evaluation study, or Monte Carlo is created. Integer Hamming and float Euclidean rows were measured at 32, 256, and 20,000 symbols.

| Metric rows | Symbols | Full-frame seconds | η=20 seconds | Full survivor rows | η=20 survivor rows | Full state/survivor diagnostics | η=20 compact diagnostics |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hamming integer | 32 | 0.000745 | 0.000689 | 32 | 20 | 1,312 B | 0 B |
| Hamming integer | 256 | 0.006763 | 0.005902 | 256 | 20 | 10,272 B | 0 B |
| Hamming integer | 20,000 | 0.552375 | 0.588103 | 20,000 | 20 | 800,032 B | 0 B |
| Joint float | 32 | 0.001568 | 0.001268 | 32 | 20 | 1,312 B | 0 B |
| Joint float | 256 | 0.006580 | 0.006926 | 256 | 20 | 10,272 B | 0 B |
| Joint float | 20,000 | 0.483200 | 0.569363 | 20,000 | 20 | 800,032 B | 0 B |

The ring stores at most 20 rows in finite mode (each row has four survivor edge IDs). Compact mode omits `(F+1,4)` state-metric and `(F,4)` survivor diagnostic arrays; decoded output and per-symbol records remain available. Full result arrays still scale with F. RSS was unavailable, so no process-memory claim is made. The SVG comparison plot was written in 0.00297 s (121,041 bytes), one observation only. The machine-readable measurements and plot hashes are in `outputs/repro06/performance.json` and `outputs/repro06/manifest.json`.
