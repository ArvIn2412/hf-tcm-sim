# M8 exploratory anchored-study closeout

**Classification:** M8 exploratory closeout; no M8 validation and no new
performance evidence. This is not a paper-exact receiver.

## Read-only recovery verification

The original failed M8b attempt remains immutable: 40 generated received
realizations, 320 failed policy records, zero decoder calls, and
`KeyError('clock_origins')`. The separate technical recovery replayed the same
40 IDs and seeds; its saved received hashes match the original attempt, with
40 complete sequences, 320 valid records, 320 decoder invocations, and zero
failures. All 320 records also report finite final states and metric rows and
normalized final posteriors. The recovery `integrity_manifest.json` was independently checked
against every listed output file before and after this closeout. The original
recovery status remains `TRAIN_SELECTED_NOT_VALIDATED`.

Raw checkpoint records reproduce the ranking. Frozen B recorded 413/20,480
bit errors and 371/10,240 symbol errors. `anch_a085_k025` recorded 429/20,480
and 385/10,240; historical combined C recorded 7,804/20,480 and 7,074/10,240.
Frozen B is the unchanged TRAIN winner. The exact closeout verdict is
`M8_EXPLORATORY_GRID_COMPLETED; TRAIN_WINNER_FROZEN_B;
ANCHORED_GAIN_NOT_ESTABLISHED; ORIGINAL_VALIDATION_NOT_EXECUTED`.

Independent pooling of all 320 complete checkpoint records gives:

| Rank | Policy | Bit errors / bits (BER) | Symbol errors / symbols (SER) |
|---:|---|---:|---:|
| 1 | `historical_frozen_B` | 413 / 20,480 (0.020166015625) | 371 / 10,240 (0.03623046875) |
| 2 | `anch_a085_k025` | 429 / 20,480 (0.020947265625) | 385 / 10,240 (0.03759765625) |
| 3 | `anch_a095_k025` | 490 / 20,480 (0.02392578125) | 440 / 10,240 (0.04296875) |
| 4 | `anch_a085_k050` | 528 / 20,480 (0.02578125) | 463 / 10,240 (0.04521484375) |
| 5 | `anch_a095_k050` | 924 / 20,480 (0.0451171875) | 786 / 10,240 (0.0767578125) |
| 6 | `anch_a100_k025` | 1,501 / 20,480 (0.073291015625) | 1,204 / 10,240 (0.117578125) |
| 7 | `anch_a100_k050` | 3,000 / 20,480 (0.146484375) | 2,324 / 10,240 (0.226953125) |
| 8 | `historical_combined_C` | 7,804 / 20,480 (0.3810546875) | 7,074 / 10,240 (0.6908203125) |

Original M8 validation was not run because the selected policy was frozen B,
which would produce a B-versus-B contrast. The post-hoc runner-up was not
promoted into M8 validation. This result is limited to the predefined eight
policies and the saved M8 TRAIN partition; it does not show that anchored
adaptation generally fails.

## Read-only paired runner-up contrast

The 40 paired sequence clusters were extracted from the recovery checkpoints.
For each run, the same received hash, complete finite records, and raw counts
were checked. With `d = anchored - B`, the per-run bit differences are:

```text
0, 0, 0, 12, 0, 0, 0, 0, 0, -1, 0, 0, 0, 2, -6, 6, -5, 0, -15, 0,
0, 0, 0, 0, 6, 0, 0, -3, 9, -5, 0, 11, 5, 0, 0, 0, 0, 0, 0, 0
```

The symbol differences are:

```text
0, 0, 0, 9, 0, 0, 0, 0, 0, -1, 0, 0, 0, 2, -6, 8, -5, 0, -14, 0,
0, 0, 0, 0, 4, 0, 0, -3, 9, -3, 0, 9, 5, 0, 0, 0, 0, 0, 0, 0
```

| Contrast | Negative / zero / positive runs | Range | Sample SD | Pooled difference |
|---|---:|---:|---:|---:|
| Bit errors | 6 / 27 / 7 | -15 to 12 | 4.4190728811 | +16 / 20,480 = +0.00078125 BER |
| Symbol errors | 6 / 27 / 7 | -14 to 9 | 3.9971143437 | +14 / 10,240 = +0.0013671875 SER |

The independent statistical cluster is the complete coded sequence. The
8,192 information bits across the 40 sequences are not treated as independent
clusters.

An ADR-014 paired cluster bootstrap was computed from those saved raw counts:
2,000 whole-run paired resamples, 95% percentile intervals, NumPy
`quantile(method="linear")`, PCG64, analysis-only seed `2026103009`. No
receiver RNG, data/noise generation, or decoder was used. The exploratory
intervals are DeltaBER `[-0.002197265625, 0.003369140625]` and DeltaSER
`[-0.00390625, 0.00595703125]`. The runner-up was selected after inspecting
the eight M8 arms, so these are **post-selection exploratory summaries**,
not independent confirmatory intervals. They do not establish equivalence or
noninferiority and do not alter the M8 selection rule.

Machine-readable per-run differences and bootstrap provenance are in
[`paired_runnerup_audit.json`](../outputs/m8c_closeout/paired_runnerup_audit.json).
No historical M8 checkpoint or summary was modified.

## Closeout and next study

M8 is closed as an exploratory grid. The prospective M9a design fixes
`anch_a085_k025` before any M9 observation and compares it with frozen B on a
new, independent constant-gain partition. M9 is a subsequent fixed-policy
study motivated by a post-hoc M8 runner-up; it was not preregistered before
M8. M8 validation is not being retroactively performed. M9 remains
unauthorized, and no M9 streams or observations were created.

`paper_exact:false`, `receiver_enabled:false`, the accepted/proposed ADR lists,
and open SCI-02/SCI-03/SCI-METRIC-02 statuses remain unchanged.
