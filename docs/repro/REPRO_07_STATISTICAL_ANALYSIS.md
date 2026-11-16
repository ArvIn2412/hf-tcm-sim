# REPRO-07 statistical analysis

## Estimands

For arm `r`, aggregate BER is `sum(bit_errors_r) / sum(compared_information_bits_r)`. Aggregate pair-SER uses the analogous sum of information-pair errors over compared pairs. The primary paired contrast is `Delta_BER = BER_joint - BER_separate`; a negative value means fewer errors for the joint arm in this experiment. Phase-symbol SER is reported separately from information-pair SER.

## Uncertainty

The resampling unit is an independent paired trial/channel realization, not an individual bit. Each bootstrap replicate samples trial IDs with replacement and recomputes both BER ratios from pooled error and denominator sums; its difference is the replicate DeltaBER. The same procedure is used for BER arm intervals and pair-SER intervals. The configured pilot uses 5,000 replicates and 95% percentile intervals with a fixed, per-grid-point bootstrap seed.

Failed trials are not silently treated as zero errors. Only hash-verified completed pairs enter an aggregate. Fewer than two completed independent pairs produce no interval and an exploratory status. Unequal frame lengths are supported by ratio-of-sums weighting, but both arms in any individual pair must have identical compared payload denominators.

An interval that includes zero is not evidence of equivalence/noninferiority. A result from the present pilot applies only to the specified full algorithms and project channel profile; it does not isolate metric choice or establish source-exact performance.
