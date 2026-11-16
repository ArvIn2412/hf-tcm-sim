# REPRO-01 — controlled experiment plan

No Monte Carlo or new BER/SER is run in this phase.

For each paired trial: generate one information frame; encode/map/modulate once; generate one channel realization and one noise buffer; freeze and hash the received samples; run A and B against identical bytes; separately compute bit errors/information-bit denominator and symbol errors/transmitted-symbol denominator. Truth is evaluator-only. Persist config, source/software IDs, RNG seeds, hashes, arrays/checkpoint policy and outputs.

Future Monte Carlo uses a fixed named SNR grid, same bits/channel/noise within each pair, independent seeds between trials, predeclared count or stopping rule, and checkpoints. Do not stop on a desired gain. p*=0.05 is a target only, not a forced result. Predeclare interval methods: e.g. Wilson per receiver and a paired method or cluster bootstrap over independent frames for A-B differences. Record resampling unit, seed and replicate count.

Define energy gain as G_dB = SNR_B(p*) - SNR_A(p*), positive when A needs less SNR. Both curves must bracket target and interpolation is fixed before analysis; otherwise report non-estimable. S1 does not fully define SNR/Eb/N0 normalization, so the gain is project-defined until Es/Eb, code rate, sample normalization, noise variance and pre/post-channel reference are fixed. Never force 1.5 dB. Store REPRO runs outside M5-M10.
