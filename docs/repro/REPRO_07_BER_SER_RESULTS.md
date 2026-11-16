# REPRO-07 measured BER/SER results

The main series is `outputs/repro07/pilot_rician_ar1_f256_v1/summary.json`.
Each point contains 20 independent paired trials, F=256 TCM transitions,
512 information bits per frame, and 10,240 compared bits per receiver.
The two receiver arms have matching denominators. `DeltaBER = BER_joint - BER_separate`.

| Complex noise variance per sample | Joint errors / bits | Joint BER (95% cluster CI) | Separate errors / bits | Separate BER (95% cluster CI) | DeltaBER (95% paired CI) | Pair-SER Joint / Separate | Delta pair-SER |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.005 | 4 / 10240 | 0.000390625 [0, 0.001171875] | 1485 / 10240 | 0.14501953125 [0.13017578125, 0.15927734375] | -0.14462890625 [-0.15869140625, -0.13007568359375] | 3/5120; 1302/5120 | -0.2537109375 |
| 0.05 | 6 / 10240 | 0.0005859375 [0, 0.00146484375] | 1496 / 10240 | 0.14609375 [0.12665771484375, 0.1662109375] | -0.1455078125 [-0.165234375, -0.12626953125] | 5/5120; 1319/5120 | -0.256640625 |
| 0.2 | 18 / 10240 | 0.0017578125 [0.000390625, 0.00341796875] | 1490 / 10240 | 0.1455078125 [0.1306640625, 0.16015625] | -0.14375 [-0.1583984375, -0.12900390625] | 14/5120; 1318/5120 | -0.2546875 |

Pair-SER counts an information-pair symbol as an error if either bit is wrong.
The separately recorded 8PSK phase-symbol SER is not interchangeable with it.
Measured phase-SER counts (Joint / Separate) were 4/5120 vs 1483/5120,
9/5120 vs 1533/5120, and 20/5120 vs 1511/5120 at the three noise points.

Intervals use 5,000 paired cluster-bootstrap replicates per point, resampling
independent trial IDs and recomputing ratio-of-sums. This compares two complete
receivers: adaptive ISI-aware joint processing versus hard demodulation and
Hamming decoding without a multipath equalizer. It does not isolate Euclidean
versus Hamming metric effects and does not establish universal or paper-exact
superiority.

The horizontal variable is complex sample-domain noise variance
`E[|w[n]|^2]`. It is not Eb/N0, physical SNR, or energy gain. No energy-gain
claim is made. Measured plots are listed in the output `summary.json`: BER,
pair-SER, DeltaBER with CI, paired error differences, cumulative errors,
runtime, plus selected-trial signal, error-position, and estimator views.

## Long-frame resource check

`outputs/repro07/long_frame_single_pair_resource_check_v1/summary.json` records
one F=20,000 pair at variance 0.05. Joint had 16/40,000 bit errors (BER 0.0004);
Separate had 6,019/40,000 (BER 0.150475); DeltaBER was -0.150075. Pair-SER was
12/20,000 versus 5,300/20,000. With only one independent pair, no confidence
interval or statistical conclusion is available. Measured receiver times
were about 238.66 s Joint and 0.649 s Separate.
