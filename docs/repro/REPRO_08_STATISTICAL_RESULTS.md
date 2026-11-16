# REPRO-08 statistical results

## Frozen REPRO-07 Rician pilot

These counts are read from the immutable REPRO-07 aggregate, not rerun. There are 20 paired F=256 trials and 10,240 compared information bits per receiver/point. `DeltaBER = BER_joint - BER_B0`; negative favors Joint in this specific complete-algorithm comparison.

| Complex variance | Joint errors / bits; BER (95% trial bootstrap CI) | B0 errors / bits; BER (95% CI) | DeltaBER (95% paired cluster CI) | Pair SER Joint / B0 |
|---:|---|---|---|---|
| 0.005 | 4/10240; 0.000390625 [0, 0.001171875] | 1485/10240; 0.14501953125 [0.13017578125, 0.15927734375] | -0.14462890625 [-0.15869140625, -0.13007568359] | 0.0005859375 / 0.254296875 |
| 0.05 | 6/10240; 0.0005859375 [0, 0.00146484375] | 1496/10240; 0.14609375 [0.12665771484, 0.1662109375] | -0.1455078125 [-0.165234375, -0.12626953125] | 0.0009765625 / 0.2576171875 |
| 0.2 | 18/10240; 0.0017578125 [0.000390625, 0.00341796875] | 1490/10240; 0.1455078125 [0.1306640625, 0.16015625] | -0.14375 [-0.1583984375, -0.12900390625] | 0.002734375 / 0.257421875 |

These CIs come from REPRO-07's paired trial-cluster bootstrap (5,000 replicates). They quantify uncertainty for that pilot only. The roughly invariant B0 BER and high phase error rate indicate a receiver/channel compatibility problem in B0 under that channel configuration, rather than a clean AWGN sensitivity curve.

## REPRO-08 static public two-path pilot v2

F=256; 20 independent paired trials per point; 10,240 information bits and 5,120 information pairs per arm/point. Channel taps were fixed public values `h0=1`, `h1=0.5 exp(j0.7)`, delays `[0,3]`. All three arms used the same observations. Joint here is REPRO-06B **known-static CSI Euclidean MLSE**, not adaptive REPRO-06C.

| Variance | Discrete gamma_b,d (dB) | Arm | Bit errors / bits; BER | Information-pair errors / pairs; pair SER | Phase-symbol SER |
|---:|---:|---|---:|---:|---:|
| 0.4 | 10.0000 | Joint static-known | 0/10240; 0 | 0/5120; 0 | 0 |
| 0.4 | 10.0000 | B0 | 184/10240; 0.01796875 | 169/5120; 0.0330078125 | 0.0783203125 |
| 0.4 | 10.0000 | B1 | 4/10240; 0.000390625 | 4/5120; 0.00078125 | 0.0017578125 |
| 0.8 | 6.9897 | Joint static-known | 0/10240; 0 | 0/5120; 0 | 0 |
| 0.8 | 6.9897 | B0 | 481/10240; 0.04697265625 | 436/5120; 0.08515625 | 0.13359375 |
| 0.8 | 6.9897 | B1 | 58/10240; 0.0056640625 | 55/5120; 0.0107421875 | 0.0279296875 |
| 1.6 | 3.9794 | Joint static-known | 0/10240; 0 | 0/5120; 0 | 0 |
| 1.6 | 3.9794 | B0 | 1226/10240; 0.1197265625 | 1109/5120; 0.2166015625 | 0.2296875 |
| 1.6 | 3.9794 | B1 | 493/10240; 0.04814453125 | 457/5120; 0.0892578125 | 0.1298828125 |

The paired trial-cluster bootstrap for `Joint static-known - B1` gave DeltaBER and 95% intervals: at variance 0.4, -0.000390625 [-0.00078125, -0.00009765625]; at 0.8, -0.0056640625 [-0.0078125, -0.0037109375]; at 1.6, -0.04814453125 [-0.058203125, -0.03915771484]. Zero observed errors for the known-CSI arm do not imply a true zero BER; ordinary percentile bootstrap degenerates at zero and is not a rare-event confidence bound.

### Adaptive A versus B1 follow-up on the same observations

The identical 60 v2 observations were replayed through REPRO-06C with `unknown_static` PSP and a public prior mean equal to the explicitly configured static tap values (`prior_variance=0.25` per path), then paired against the already stored B1 decisions. SHA-256 matched for **60/60** re-created observations. This is an exploratory follow-up because the extra arm was added after the range-finding set was fixed; it is not the article's unknown Rician fading result. The profile uses public static gains, not EvaluationTruth.

| Variance | A: REPRO-06C adaptive public prior | B1: public static hard | DeltaBER A-B1 (95% paired trial bootstrap CI) |
|---:|---:|---:|---:|
| 0.4 | 0/10240 = 0 | 4/10240 = 0.000390625 | -0.000390625 [-0.00078125, -0.00009765625] |
| 0.8 | 0/10240 = 0 | 58/10240 = 0.0056640625 | -0.0056640625 [-0.0078125, -0.0037109375] |
| 1.6 | 0/10240 = 0 | 493/10240 = 0.04814453125 | -0.04814453125 [-0.0583984375, -0.03916015625] |

The adaptive arm used the public tap means as its initialization. This supports an algorithm comparison for the declared static channel with common observation and public channel values, but the zero-error arm's bootstrap interval degenerates and this small pilot is not a rare-event upper bound or article reproduction. Its receiver runtime was not successfully captured by the post-processing runner; do not use this follow-up as performance evidence.

Information-pair SER is one if either payload bit in the pair is wrong. Phase-symbol SER is separately computed by comparing phase indices; it is not interchangeable with either information BER or information-pair SER.

## Completeness

No REPRO-08 Rician paired data were pooled with the static CSI arm. Phase C has only one completed long-frame pair. The measured points form discrete pilot observations; no smooth fitted curve or article-level inferential claim is made.
