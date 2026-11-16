# REPRO-08 SNR and energy normalization

## Discrete waveform convention

REPRO-02 sends a unit-amplitude complex 8PSK symbol as a rectangular zero-order hold for `s=8` samples. One TCM trellis transition carries two information bits. For amplitude `A`, the discrete energy per information bit is

`E_b,d = sum_{i=0}^{s-1} |A exp(j phi)|^2 / 2 = s A^2 / 2`.

At `s=8, A=1`, `E_b,d=4`. This sum is a sample-domain discrete quantity. It is not a joule-valued physical energy without a sample period, impedance/power convention, pulse definition, and receiver filtering convention.

REPRO-03 complex AWGN uses `E|w[n]|^2 = sigma_c^2`, with independent real and imaginary components each of variance `sigma_c^2/2`. For an explicit dimensionless comparison only, this phase defines

`gamma_b,d[dB] = 10 log10(E_b,d / sigma_c^2)`.

This axis is called **discrete gamma_b,d**, not physical Eb/N0. The convention avoids silently treating eight repeated samples as eight independent information symbols; it explicitly accounts for their summed ZOH energy and two payload bits per TCM symbol.

The functions in `src/hf_tcm/repro/repro08_energy.py` implement these definitions and validate positive finite inputs. Independent tests check `E_b,d=4` for the base profile, the amplitude-squared relationship, inversion between variance and discrete gamma, and invalid-input rejection.

## Actual grid coordinates

| Complex sample variance | Discrete gamma_b,d (dB) | Pilot source |
|---:|---:|---|
| 0.005 | 29.0308998699 | Frozen REPRO-07 pilot and REPRO-08 first static pilot |
| 0.05 | 19.0308998699 | Frozen REPRO-07 pilot and REPRO-08 first static pilot |
| 0.2 | 13.0102999566 | Frozen REPRO-07 pilot and REPRO-08 first static pilot |
| 0.4 | 10.0000000000 | REPRO-08 static range-finding pilot |
| 0.8 | 6.9897000434 | REPRO-08 static range-finding pilot |
| 1.6 | 3.9794000867 | REPRO-08 static range-finding pilot |

All pilot plot x-axes use this declared discrete convention or label raw complex variance. They do not report Eb/N0. Fading means that instantaneous received signal power varies by sample and path; the listed coordinate is based on the unit-amplitude transmitted discrete waveform, not a per-trial received-power estimate.

## Physical limitation

The available source and REPRO-02/03 contracts do not settle physical sample period, continuous-time pulse energy, receiver matched filtering, noise spectral density, or a complete conversion from discrete complex noise variance to physical `N0`. Therefore physical SNR/Eb/N0 and energy gain in dB are **not estimable** from the current evidence. No conversion is inferred from the article's 1.5 dB claim.
