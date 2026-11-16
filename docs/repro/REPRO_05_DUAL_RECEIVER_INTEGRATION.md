# REPRO-05 — paired integration with REPRO-04

Both receiver APIs accept the same exact `ReceiverObservation` object from REPRO-03. `compare_joint_and_separate` refuses results with different semantic observation SHA-256 values and applies the same explicit reference bits/phases only after both receiver calls complete. Evaluation boundaries honor the configured two-step zero tail; reference data does not enter either decoder.

The deterministic identity fixture runs transmitter → one identity channel realization → REPRO-04 hard 8PSK/Hamming → REPRO-05 direct edge Euclidean Viterbi. Both outputs carry the same observation hash and recover the same noiseless payload. The full 20,000-symbol reference CLI also exercised both arms from the same serialized observation; both recovered all 40,000 input bits without errors. The single-frame BER/SER values are descriptive fixture checks only, not a statistical comparison. The optional `--separate-config` CLI mode saves the REPRO-04 output and a plot of both actual decoded-bit traces; it requires matching observation hashes and payload lengths.

No channel/noise realization is generated separately for either arm. No receiver is given true coefficients, noise samples, encoder states, or reference phases. The REPRO-04 implementation and historical outputs are unchanged.
