# REPRO-07 paired randomization

`derive_trial_seeds(root, experiment_id, point_index, trial_index)` hashes the tuple plus a stream label using SHA-256 and takes the first 64 bits. Separate labels derive the input-bit, channel-fading, and additive-noise seeds. The channel module further splits its fading seed per path using its established REPRO-03 generator contract.

Within a trial, one REPRO-02 `TransmitterResult` and one REPRO-03 `ChannelResult` are generated. Only `ChannelResult.receiver_observation` is supplied to either receiver. The trial is rejected if the two receiver observation hashes differ from the generated observation hash. `EvaluationTruth` remains in the runner and is consulted only after receiver execution for reference counting/selected diagnostics.

Different trial IDs and noise grid point IDs derive distinct bit/fading/noise streams. A repeated config and trial ID reproduces the same values. The committed record stores the three derived seeds, config hashes, transmitter/reference hashes, observation hashes, and result-record SHA-256.
