# REPRO-08 energy-gain analysis

## Determination

**ENERGY_GAIN_NOT_ESTIMABLE.** The current model supports a dimensionless discrete `gamma_b,d` derived from ZOH sample energy per payload bit divided by complex sample-noise variance. It does not define physical sample period, matched-filter convention, continuous-time pulse energy, or physical noise spectral density. Therefore a physical SNR/Eb/N0 difference in dB cannot be claimed.

In addition, the relevant curves do not have a common methodologically matched channel/receiver pair across the whole operating range. REPRO-07 compares Joint adaptive with original B0 on time-varying Rician multipath; the REPRO-08 B1 pilot is restricted to public static CSI and its Joint arm is known-static MLSE. These are distinct questions.

## Target BER

No target BER is declared as matching article `p*_n=5e-2`: the article calls that value a channel error frequency, and its event/denominator are unresolved. Selecting a decoded-payload target after inspecting the curves would also be post hoc. The source's 1.5 dB is retained only as a historical claim, not used as a target or fitted value.

## Estimation rule and uncertainty

The repository helper `estimate_energy_gain_db` accepts only a physically defined SNR axis and refuses sample-domain proxies. If a future experiment prespecifies a target and measures both curves bracketing it, the configured method is linear interpolation of adjacent measured BER points without extrapolation. A future gain CI must resample paired trial clusters and re-compute both crossings on every resample; resamples without both valid crossings must be reported, not silently discarded. REPRO-08 does not produce a numerical energy-gain estimate.
