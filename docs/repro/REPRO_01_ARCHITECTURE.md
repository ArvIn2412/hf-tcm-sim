# REPRO-01 — isolated research architecture

Create src/hf_tcm/repro/; leave M5-M11 code and outputs untouched.

| Component | Responsibility |
|---|---|
| source_spec.py | source IDs, equation/page citations, statuses |
| config.py | frozen strict experiment schema |
| encoder.py, mapping.py, modulation.py | Encoder A, mapping profile, complex envelope |
| channel/ | source-derived and reconstructed models kept separate |
| receivers/joint_euclidean.py | prediction, estimator/posterior, cost, traceback |
| receivers/separate_hamming.py | hard decision, inverse label, Hamming Viterbi |
| bundle.py | immutable shared TX/channel/RX buffers and hashes; truth sidecar |
| experiment.py | paired orchestration in new output namespace |
| statistics.py | counts, BER/SER, paired difference, CI and gain |
| manifest.py | config/source/software/RNG/artifact hashes |
| plots/ | read-only plots with units and provenance |
| studio_adapter.py | optional future GUI integration |
| tests/repro/ | independent oracle, schema, pairing, leakage, determinism |

Each config field has value, unit, provenance, validation and status. Source-exact mode rejects unknown values; project mode requires named reconstruction IDs. Include source hashes, bit/seed, encoder ordering, start/end, mapping/phase, samples per symbol, waveform, channel/noise, SNR, estimator, metric, eta endpoint, traceback, receivers, trials/stopping, CI and RNG version.

Reject unknown keys, NaN/inf, malformed shapes, grouping/length mismatch and incompatible receiver profiles. No silent padding/clipping/defaults. For F steps and n samples/symbol: bits (2F), triples (F,3), states F+1, edges F, symbols F, Tx samples F*n, received samples F*n plus declared tail, A costs (F,16), decoded bits (2F). Tag units. Complex baseband is not RF voltage. ReceiverInput has only samples/public config; ChannelTruth is evaluator-only. Enforce common buffer hash and immutable manifests; no run writes into historical directories.
