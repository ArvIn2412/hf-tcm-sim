# REPRO-08 receiver baseline audit

## B0 audit

B0 is the unchanged REPRO-04 `SeparateReceiverConfig.article_oriented` hard 8PSK plus Hamming Viterbi receiver with finite-depth eta=20. It uses the nominal 8PSK phase reference and has no channel estimator/equalizer or delayed-path cancellation. Its hard decisions are then converted through the reconstructed inverse phase labels and decoded using integer Hamming branch costs. The receiver receives only `ReceiverObservation`.

The immutable REPRO-07 pilot (`outputs/repro07/pilot_rician_ar1_f256_v1/summary.json`) has 20 paired trials per complex sample-domain variance:

| Complex variance | Joint adaptive BER | B0 BER | B0 phase SER | B0 information-pair SER |
|---:|---:|---:|---:|---:|
| 0.005 | 0.000390625 | 0.14501953125 | 0.2896484375 | 0.254296875 |
| 0.05 | 0.0005859375 | 0.14609375 | 0.2994140625 | 0.2576171875 |
| 0.2 | 0.0017578125 | 0.1455078125 | 0.2951171875 | 0.257421875 |

For every pair, Joint and B0 have the same observation SHA. The B0 rate is nearly flat because the chosen channel mismatch dominates the added-noise variation: B0 does not track the time-varying complex gains or undo the [0,3] delayed paths. A fixed phase-rotation control independently demonstrates that the nominal hard demodulator can fail before Viterbi when its reference is rotated. Noise variance alone is therefore not an adequate explanation of the REPRO-07 error pattern.

This is not evidence of a defect in the Hamming Viterbi recurrence. The diagnostic error appears already at the hard phase decisions, and a noiseless/nominal identity control passes. The pilot does not isolate the separate contributions of fading, phase rotation, amplitude, ISI, and decision feedback. No correction was applied to B0, and REPRO-07 artifacts remain immutable.

## Three distinct arms

| ID | Actual implementation | Channel information | Interpretation |
|---|---|---|---|
| A / Joint adaptive | REPRO-06C adaptive survivor-specific Euclidean/ISI receiver, eta=20 | Public profile/prior only; hidden realized coefficients withheld | Full adaptive algorithm arm; Rician paired data currently available from REPRO-07 |
| B0 / Original Separate | REPRO-04 nominal hard demodulation + Hamming Viterbi, eta=20 | Nominal constellation only | Preserved historical baseline; no added ISI compensation |
| B1 / Channel-aware Separate | New `repro08_channel_aware_hard.py`; hard 8PSK decisions + Hamming Viterbi, eta=20 | Explicitly configured static public complex taps; causal previous-hard-symbol decision feedback | Project-defined static-channel control, not article-exact and not time-varying Rician capable |

## Controlled common-CSI pilot

The REPRO-08 static pilot compares REPRO-06B known-public-static Euclidean MLSE, B0, and B1 on the same transmitter/channel observation. The joint arm is intentionally labeled **static-known CSI control**, not the REPRO-06C adaptive arm. All three use F=256, delays `[0,3]`, taps `1+0j` and `0.5 exp(j 0.7)`, and eta=20. B1's configured taps are public receiver parameters, not EvaluationTruth. This isolates useful processing contrasts under common public static CSI but does not equate complete receiver structures.

The static pilot produced the BER/SER tables in `REPRO_08_STATISTICAL_RESULTS.md`. At higher noise, B1 improved over B0, while known-CSI Euclidean MLSE had zero observed errors in this bounded set. These are project-defined results, not a comparison of article implementations.

## B1 tests and restrictions

Independent tests cover the eight phase hypotheses under a public complex gain, two-path delay-3 end-to-end operation, invalid delays, and rejection of channel truth/full `ChannelResult` objects. The front end rejects delays at or above one symbol because its current decision-feedback contract is limited to sub-symbol sample delays. It does not estimate hidden time-varying fading and must not be used on the REPRO-07 Rician profile as a channel-aware arm.
