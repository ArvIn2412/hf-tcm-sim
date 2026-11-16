# REPRO-06 — independent reference tests

The core tests include an exhaustive small-frame path oracle independent of production Viterbi; row-by-row streaming versus batch agreement; integer and floating costs; all-zero canonical ties; nonzero initial state; frame lengths below/equal/above η; η=1/2/20; declared zero-tail termination; unknown final state; one-row/short frames; large nearly equal floats; exact first-decision timing; complete unique output indices; bounded survivor row count; and a deterministic fixture where short-depth and full-frame decisions differ.

Receiver tests compare REPRO-04/05 finite identity runs, verify the first η=20 availability index, verify metric-row invariance across joint decoder modes, and exercise known static gain and single-path noisy/Rician observations without asserting perfect recovery under noise. Both finite receiver arms are given the same `ReceiverObservation` hash. Channel truth remains rejected by the receiver API.

Full-frame compatibility is checked against the pre-existing REPRO-04 integer and REPRO-05 floating decoders on deterministic rows. Plot and NPZ checks use actual decoded/decision arrays. None of these fixtures is a BER/SNR study.
