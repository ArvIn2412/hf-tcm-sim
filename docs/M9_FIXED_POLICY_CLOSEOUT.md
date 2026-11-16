# M9b fixed-policy evaluation closeout

**Status:** `M9_EVALUATION_COMPLETE_VERIFIED`  
**Classification:** independent evaluation of one fixed pair on the
reconstructed constant-gain profile; not M8 validation, not physical HF
channel evidence, and not a paper-exact reconstruction.

## Independent recount

The saved M9b checkpoints contain 100 unique run IDs, 100 distinct paired
received hashes, two valid policy records per run, 200 experimental decoder
calls, and zero failures. Raw checkpoint recount agrees with the saved
independent verification and output integrity manifest.

| Policy | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---:|---:|---:|---:|
| `historical_frozen_B` | 1,130 / 51,200 | 0.0220703125 | 1,050 / 25,600 | 0.041015625 |
| `anch_a085_k025` | 1,072 / 51,200 | 0.0209375 | 1,001 / 25,600 | 0.0391015625 |

The paired pooled contrasts are `DeltaBER=-0.0011328125` and
`DeltaSER=-0.0019140625`.

| Contrast | 95% paired cluster-bootstrap CI |
|---|---:|
| DeltaBER | [-0.00322265625, 0.00068359375] |
| DeltaSER | [-0.0053125, 0.0011328125] |

The intervals use ADR-014: 2,000 resamples of the same 100 full-sequence
indices for both policies, raw-count pooling, 95% percentile intervals, and
`numpy.quantile(method="linear")`. An independent scalar bootstrap reproduced
the saved index fingerprint and bounds.

The anchored policy has a lower point estimate on this fixed comparison, but
both intervals include zero. Superiority is not established. Equivalence and
noninferiority are not established. The policy was selected as M8's runner-up
after the M8 grid was observed, then fixed before M9 observations; M9 is
independent evidence for this particular pair, not validation of the M8 grid.

No M10 samples or random streams were generated during M10a. M9 outputs and
the approved protocol remain unchanged. Historical M5f/M5h/M5j/M6b/M6g/M6h
hashes match their recorded baselines.
