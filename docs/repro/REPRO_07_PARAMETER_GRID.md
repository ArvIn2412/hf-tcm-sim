# REPRO-07 parameter grid

| Setting | Pilot value | Meaning / status |
|---|---:|---|
| Frame length | 256 TCM transitions | Project-defined bounded pilot; 512 information bits |
| Noise variance | 0.005, 0.05, 0.2 | `E[|w[n]|^2]`, complex sample-domain variance per sample |
| Path delays | 0, 3 samples | REPRO-03 integer-delay model |
| Path average powers | 1.0, 0.25 | Explicit project profile |
| Rician K | 4.0, 1.0 | Explicit project profile |
| LOS phases | 0.0, 0.7 rad | Explicit project profile |
| AR(1) correlation | 0.98 per sample | Explicit project profile; not Jakes/Doppler validation |
| Trials / point | 20 | Independent channel/noise/bit streams per point |
| Decoder | finite-depth | eta=20 trellis transitions |
| Bootstrap | 5,000 replicates, 95% | Paired trial-cluster, ratio-of-sums |
| Bit seed root | 2026110907 | Domain-separated SHA-256 seed plan |

No Eb/N0 conversion is performed. The grid's independent streams differ across noise points; no shared-noise scaling dependence is introduced between grid points. The long-frame resource config is one F=20,000 pair at variance 0.05, eta=20, with a 240-second wall budget and 2 GB disk cap. It is a bounded check, not a long-frame Monte Carlo series.
