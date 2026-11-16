# REPRO-07 experiment protocol

## Scope

REPRO-07 calls the frozen REPRO-02 transmitter, REPRO-03 channel, REPRO-06C adaptive multipath receiver, and REPRO-04 separate Hamming receiver. A trial constructs exactly one transmitter result and one channel realization. Both receivers receive the same `ReceiverObservation`; reference bits and channel truth are used only by the evaluation code after both decoders return.

The primary contrast is between **two complete receiver algorithms**, not an isolated Euclidean-versus-Hamming metric experiment. The adaptive joint arm estimates a time-varying multipath channel and handles ISI; the separate arm uses hard 8PSK decisions and has no multipath equalizer. The result must not be interpreted as the causal effect of branch metric alone.

## Pilot definition

- 256 TCM transitions per frame; 512 information bits; no encoder termination symbols.
- Encoder A, reconstructed ADR-002 mapping, 8 complex samples/symbol.
- 17-node / 68-edge augmented trellis for sample delays `[0, 3]`.
- Two-path Rician AR(1), powers `[1.0, 0.25]`, K factors `[4.0, 1.0]`, LOS phases `[0.0, 0.7]` rad, sample-level correlation `rho=0.98`.
- Complex sample-domain noise variances `[0.005, 0.05, 0.2]`; these are not Eb/N0 or physical SNR values.
- 20 independent paired trials per point, 60 paired trials total; both receivers use finite-depth Viterbi `eta=20`.
- Seed root `2026110907`; stream seeds are SHA-256 domain-separated by experiment ID, grid point, trial ID, and stream (`bits`, `fading`, `noise`).
- Pilot is exploratory and fixed before any pilot results were inspected.

## Article-oriented status

Verified article-oriented conventions include the 8-sample representation and the project eta=20 transition-depth contract. The full source-defined channel/noise law and physical SNR normalization are not sufficiently established by the project source register. Accordingly, this executable pilot is a custom project-defined sample-domain experiment, not an article-exact reproduction. The identity profile is an engineering control only.

## Evaluation boundaries

All frames use the same 512 payload information bits in both arms. BER counts decoded information-bit errors over the exact payload length. Pair-symbol SER counts information pairs with either bit wrong. 8PSK phase-symbol SER is recorded separately; coded-bit errors are not called information BER. Channel tail samples are scored under the existing REPRO-06C frame policy and do not create another information symbol.
