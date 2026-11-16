# REPRO-08 experiment protocol

## Source alignment and design freeze

The exact requested article v7 and Chapter 4 DOC are absent; see `REPRO_08_ARTICLE_CROSSWALK.md`. The available current article copy and related v3 manuscript were inspected separately. REPRO-08 results are labeled project-defined and do not assert paper-exactness.

The experiment uses real REPRO-02/03 transmitter and channel functions and the existing REPRO-04/06B/06C receiver implementations, plus the additional explicitly named B1 front end. Each paired trial creates one transmitter output and one channel realization/`ReceiverObservation`; all arms in that trial receive the same observation hash. Evaluation truth is used only after decoding to count errors.

## Phase A controls

Ten fixed F=64 deterministic controls were stored in `outputs/repro08/phase_a_controls/phase_a_records.json`: identity/no-noise, AWGN-only at variances 0.005/0.05/0.2, static gain, a 0.9 rad phase rotation, known/unknown static two-path, slow fading, and Rician AR(1) multipath. They are diagnostic single-seed cases, not statistical evidence. The nominal B0 works on identity/AWGN, but static phase rotation gives phase-decision failure. No Phase A control supplies hidden truth to a receiver.

## Phase B pilots

Two frozen output sets:

1. `outputs/repro08/phase_b_static_public_pilot_v1/`: F=256, 20 independent trials at each variance 0.005/0.05/0.2, static taps at delays `[0,3]`; common observation for static-known Euclidean MLSE, B0, and B1. This initial range yielded sparse errors.
2. `outputs/repro08/phase_b_static_public_pilot_v2/`: F=256, 20 independent trials per point, same static channel and three receiver arms, with complex sample variances 0.4/0.8/1.6. The follow-up is explicitly an exploratory range-finding pilot motivated by sparse errors in v1, not a confirmatory evaluation set.

The independent unit is a trial/channel/noise realization. Point estimates pool counts over all bits; paired DeltaBER uncertainty resamples whole trials (cluster bootstrap, 5,000 resamples, fixed seed). With only 20 clusters per point these intervals are pilot uncertainty summaries, not high-precision confirmatory intervals.

The frozen REPRO-07 pilot is separately retained as a historical Joint-adaptive vs B0 Rician comparison at F=256, 20 trials per variance 0.005/0.05/0.2. It is not rewritten or pooled with the static B1 pilot.

## Phase C bounded long-frame check

`outputs/repro08/phase_c_long_frame_bounded_v1/` contains one completed paired F=20,000 Rician AR(1) trial at variance 0.05 and eta=20. It used REPRO-07 Joint adaptive vs B0, finished in 147.804 s under a 300 s one-pair budget, and compared 40,000 information bits. This is a resource/alignment check only: one realization cannot support a long-frame statistical conclusion, and B1 is not supported for hidden time-varying fading.

## Completeness and inference

The static pilot batches completed 60/60 pairs each, with identical observation hashes across their receiver arms. The 60-trial REPRO-07 pilot remains complete. Phase C is one of one planned resource-check pairs, not a multi-realization research series. No full confirmatory article grid was run. No tuning used evaluation bits; the v2 grid is marked exploratory because it followed a prior range-finding batch.
