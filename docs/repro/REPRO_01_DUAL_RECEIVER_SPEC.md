# REPRO-01 — dual receiver contracts

## Common input
One immutable trial bundle contains source bits, encoder outputs, mapping profile, transmitted samples, one channel/noise realization and one received IQ array. A and B receive identical bytes and public configuration. ChannelTruth is an isolated evaluation sidecar and is not available to either receiver.

## A — joint demodulation and decoding
For each candidate trellis edge, predict I/Q from the declared mapping and estimated channel; update estimates using a recurrence family related to A(1); compute candidate branch cost; accumulate costs under trellis constraints; traceback and return bits, path, candidate metrics, posterior and estimator traces.

Recommended project profile is squared Euclidean residual, sum((I-Ihat)^2+(Q-Qhat)^2). This is a reconstructed project choice, not an established author A(2). Initial estimator state, gains, prior, normalization, sample alignment and tie rules are explicit config fields. η=20 is proposed as 20 branch intervals; the literal inclusive range r-η…r gives η+1 indices and must remain a separate sensitivity profile. The existing full-frame Viterbi is not a depth-20 receiver.

## B — separate hard demodulation and Hamming Viterbi
Use the same received samples; hard-decision the nearest 8PSK point in a declared reference frame; inverse-map to a coded triple; compute Hamming branch distance 0…3 against each encoder edge; run trellis Viterbi and traceback. Phase/carrier synchronization, inverse author labeling, ties and termination are not fully sourced. Do not use true fading phase as an oracle; define a non-oracle synchronizer or constrain the channel profile.

## Pairing and tests
Generate transmit, channel and noise once. Verify received SHA-256 before each receiver. Save separate outputs, error masks, BER/SER, paths and latency. Test identical input hash, no truth access, deterministic ties and common denominators. One frame is not statistical evidence.
