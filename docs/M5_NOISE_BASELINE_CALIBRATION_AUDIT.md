# M5c — sample-energy/noise calibration audit and matched-baseline contract

**Status:** sample-energy/noise calibration audit and matched-baseline readiness
contract, **NOT validated performance comparison**, **NOT reproduction of paper
results**. No SNR sweep, Monte Carlo batch, BER curve, confidence interval, or
baseline comparison was run.

## 1. Scope and source/API audit

The assessed profile is `reconstructed_offline`, L=1, real channel coefficient,
zero delay, rectangular ZOH at 8 samples/symbol, ADR-012 observation mapping,
and ADR-013 conditional Viterbi. The M5b smoke harness composes M1 encoding and
ADR-002 mapping, M1 8PSK, the M3 `symbols_to_iq_waveform()` helper, explicit real
gain and explicit perturbation, B5c/B5d, and M5a counting. Reference bits stay
in the evaluation layer. It does not invoke a noise generator.

Relevant implementation sources:

- M1: `modulation/psk8.py`, `modulation/labeling.py`, `coding/encoder.py`.
- M2: `channels/awgn.py`, `decoding/branch_metrics.py`, `decoding/viterbi.py`.
- M3: `receiver/iq.py`, `channels/rician.py`, `channels/multipath.py`,
  `channels/fluctuating_noise.py`.
- Reconstruction: `receiver/reconstruction_observation.py`,
  `receiver/reconstruction_conditional_decode.py`,
  `receiver/reconstruction_segmented_decode.py`,
  `evaluation/reconstruction_smoke_experiment.py`.

`reconstruction_config.py` carries `sample_rate_hz` and `symbol_rate_hz` and
checks `sample_rate_hz = 8 * symbol_rate_hz`; `symbols_to_iq_waveform()` itself
only repeats samples and has no sample interval or physical-unit conversion.
The current M5b smoke report lists `O=23`, `f=5`, and the tested configuration,
but these are timing/test values, not energy calibration.

## 2. Constellation and three energy conventions

M1 returns `s_m = exp(j 2πm/8)` for `m=0,…,7` at zero phase offset. Thus
`|s_m|=1` exactly in the mathematical model. ADR-002 maps M1 output bits to the
phase index; it does not scale the constellation. A real static gain `a`
produces `r=a s`, and the M3 waveform helper repeats each complex value exactly
8 times with no `1/sqrt(8)` factor.

Let `a` be dimensionless gain and let complex sample amplitude be measured in
amplitude units `A`. For rate 2/3 TCM there are two information bits per one
8PSK symbol.

| Convention | Per-symbol energy | Per-information-bit energy | Units / limitation |
|---|---:|---:|---|
| Symbol-rate discrete sample | `|a s|² = a²` | `a²/2` | `A²` per one complex symbol sample; M2 AWGN's `energy_per_symbol` convention. |
| Eight-sample discrete sum | `Σ[k=0..7] |a s|² = 8a²` | `4a²` | `A²·sample` per symbol / `A²·sample` per information bit; M3 ZOH array sum, no `Δt`. |
| Sampled complex-envelope physical integral | `Δt Σ|a s|² = 8Δt a²` | `4Δt a²` | `A²·s` per symbol / bit. If amplitude is normalized as `√W`, this is joules. Requires a chosen complex-envelope energy convention and `Δt=1/Fs`. |

For `a=0.75`, the three symbol values are `0.5625 A²`, `4.5 A²·sample`,
and `4.5 Δt A²·s`. For `a=2`, they are `4 A²`, `32 A²·sample`, and
`32 Δt A²·s`. Dividing by two gives the corresponding bit energies. If
`Fs=8Rs`, the last symbol integral simplifies to `a²/Rs`; this does not make
the M2 symbol-rate `a²` and M3 sample sum `8a²` interchangeable. The code
does not state a unit-energy pulse integral or a physical conversion between
the complex baseband envelope and passband power.

## 3. M2 AWGN convention

`awgn_noise_variance(EbN0_dB, bits_per_symbol=k, energy_per_symbol=Es)` uses

```text
γb = 10^(EbN0_dB/10)
N0 = Es / (k γb)
Eb = Es/k
```

At the defaults `k=2`, `Es=1`, the function returns `N0=1/(2γb)`. `add_awgn()`
adds circular complex noise to a one-dimensional symbol-rate array, with
`Var(Re n)=Var(Im n)=N0/2` and `E|n|²=N0`. `soft_branch_cost()` is the unweighted
complex squared distance `|y-s|²` to unit-energy 8PSK points; M2 does not take
CSI or noise variance in `decode_viterbi()`. The hard metric uses nearest
8PSK labels/Hamming distance. If the signal has gain `a≠1`, callers must decide
whether `Es=a²`, whether observations are equalized by `a`, or whether the
branch constellation is scaled; the current decoder API does none of these
automatically.

The M2 AWGN utility is not called by `apply_multipath()`. M3 channel
coefficients and AWGN are separate operations. `PathSpec.average_power` is
relative to `Es=1`, but M3 does not specify a combined `Eb/N0` convention.

## 4. Hypothetical independent 8-sample noise

This is a mathematical alternative only, **not** the current M3 noise model.
If eight complex samples have zero mean, equal complex variance `σ²`, and are
independent, then for their arithmetic mean

```text
n̄ = (1/8) Σk n[k]
E|n̄|² = σ²/8.
```

For a general explicitly supplied covariance matrix `C[k,l] =
E[(n[k]-E n[k]) conj(n[l]-E n[l])]`,

```text
E|n̄-E n̄|² = (1/64) Σk Σl C[k,l] = 1ᴴ C 1 / 64.
```

M3 does not automatically generate this independent per-sample AWGN or apply it
to the smoke waveform. ADR-012's mean-of-eight is a deterministic observation
operator; it does not assert that its output is an independent AWGN sample.

## 5. M3 fluctuating-noise AR(1) audit

`fluctuating_noise_coefficients(n)` implements

```text
α = exp(-4/n)
σ = √2 √(1-exp(-8/n)) / n
x[i+1] = α x[i] + σ z[i]
```

The I and Q recursions use separate standard-normal innovations; the API default
is deterministic `I[0]=Q[0]=0`, while the article equations do not specify that
initial value. `n` is an explicit input (“samples in one signal element”); the
API does not bind it automatically to ADR-012's 8 samples/symbol. The generator
is reproducible given the caller's NumPy `Generator`, but independent runs are
not guaranteed unless callers supply independent streams.

For fixed deterministic initial value and independent unit-variance
innovations, the per-quadrature mean is `E[x[k]]=α^k x[0]` and

```text
Var(x[k]) = σ² Σ[r=0..k-1] α^(2r)
Cov(x[k],x[l]) = α^|k-l| Var(x[min(k,l)]).
```

If initialized from the stationary distribution, the limiting variance is
`σ²/(1-α²)` and covariance is that variance times `α^|k-l|`; that is not the
API's default initialization. With explicit `n=8`,
`α=e^-1/2≈0.60653066`, `σ²=(1-e^-1)/32≈0.01975377`, and stationary
per-quadrature variance is `1/32`; stationary complex variance is `1/16`.
With the default zero start, a symbol window `x[0..7]` has transient
per-quadrature mean variance

```text
Var(mean(x[0..7])) = (σ²/64) Σ[m=0..6] ((1-α^(m+1))/(1-α))²
                    ≈ 0.009153939894,
```

so the I/Q complex mean variance is approximately `0.018307879788`. With a
stationary initial state it would instead be approximately `0.024386737724`.
These conditional values apply only when `n=8` is explicitly selected and the
noise generator's outputs are the eight samples being averaged. The M5b smoke
harness does not call this generator. It is temporally correlated, not AWGN,
and its scale is not automatically an M2 `Eb/N0` variance. The current code
provides enough to derive covariance under the stated innovation and initial
conditions; it does not provide a common M3-received-to-M2 SNR calibration.

## 6. Observation reduction and CSI parity

B5c/B5d retains the original complex `(8F,)` received buffer. For each symbol,
ADR-012 maps each sample `z` to `(-Im z, Re z)` and separately uses the mean of
the eight transformed I/Q rows for the estimator recursion. B4b candidate
metrics use the sum of squared residuals over all eight rows, not the squared
residual of their mean.

M2 `decode_viterbi()` accepts one complex observation per symbol and compares
it with unit-magnitude complex constellation points. A possible adapter from
the same received block is
`y_symbol[f]=mean(received[8f:8f+8])`; for constant ZOH samples this preserves
the signal mean, but its noise covariance depends on the eight-sample
covariance. It also remains raw complex `(Re,Im)` while ADR-012 expresses
quadratures as `(-Im,Re)`, a fixed 90-degree coordinate rotation. This is
convertible, but no conversion/CSI policy is accepted for M2.

For real `a>0`, raw mean is `a s + n̄`; M2 expects `s`. Hard demodulation is
unchanged by a positive noiseless scale but assumes phase alignment. Soft
metrics see a gain mismatch unless observations are divided by `a` or branch
points are scaled. M2 has no CSI argument or equalizer; B5 receives explicit
initial coefficient estimates and may update them. A divide-by-`a` adapter
would be oracle CSI and would scale the noise covariance by `1/a²`. No such
adapter is implemented. Beta in ADR-005 only scales project pseudo-likelihood
`exp(-beta F_rx)`; it is not a physical noise variance.

## 7. Fair-baseline readiness matrix

| Comparison | Same samples/reference/trellis? | CSI parity | Energy/noise parity | Status |
|---|---|---|---|---|
| B5 oracle-initialized estimate vs M2 oracle CSI | Same reference and exact received buffer; M2 uses the accepted mean-of-8 then `/a` adapter. | Both receive oracle-derived channel information through different explicit interfaces; this is labelled oracle-CSI matched control. | Accepted discrete iid sample-AWGN and effective `gamma_b` convention. | **READY only for the narrow M5d control**; not estimated-CSI or operational parity. |
| B5 non-oracle explicit initial estimate vs M2 with corresponding CSI | Same reference and received samples are possible; observation mapping remains needed. | No M2 estimated-CSI input or estimator policy exists. | Same calibration gap. | **BLOCKED**. |
| Adaptive B5 estimate vs fixed-CSI or estimated-CSI M2 | Same signal can be replayed, but the decoders consume different representations. | Time-varying B5 estimates versus absent/fixed M2 CSI are unequal information unless explicitly designed. | Same calibration gap, plus B5's sample-summed objective versus M2's symbol-rate metric. | **BLOCKED** as fair comparison; can only be reported as separately labelled operating conditions after policy approval. |

All future comparisons must hold fixed the same information bits, M1 encoder,
ADR-002 mapping, received realization, sequence length and boundary policy.
M2 currently has default initial `(0,0)`, free final state and no tail bits,
which can match ADR-013's trellis boundary policy, but its observation/CSI and
noise models still do not match B5.

## 8. ADR-015 — accepted narrow discrete control profile

**User decision, 2026-10-28:** accept only the following reconstructed offline
control scope: `L=1`, real gain `a>0`, zero delay, normalized 8PSK, rectangular
ZOH at eight samples/symbol, iid circular complex AWGN with explicit sample
power `sigma_squared>0`, `Var(Re n)=Var(Im n)=sigma_squared/2`, and independent
sample positions. Generate noise exactly once in evaluation and share one
received buffer.

The M2 adapter takes the arithmetic mean of the same eight received samples
and explicitly divides by oracle `a`. B5 retains the eight raw samples and
uses explicit oracle-initialized `full_iq=fluctuating_iq=(a,a)` with a frozen
estimator. This is labelled **oracle-CSI matched control**, not estimated-CSI
parity. The effective discrete convention is
`gamma_b_eff=4a²/sigma_squared`; after mean and equalization the complex noise
power is `sigma_squared/(8a²)`. Report `effective discrete gamma_b` or its dB
form only. This does not assign a physical sample interval or claim physical
HF `Eb/N0`; it is not the article's noise model and does not make ADR-005
`beta` a noise precision.

Accepted ADR-015 does not define correlated noise, general complex fading,
adaptive B5 CSI comparison, physical energy calibration, BER/SNR sweeps,
confidence intervals, or paper performance. Those remain separate blocked
questions; ADR-014 is still proposed.

## 9. M5c deterministic diagnostics

`evaluation.signal_diagnostics` exposes measured sample-domain quantities:
complex sample energy, explicit equal-block discrete energies, deterministic
sample mean, component mean-square powers, and covariance-derived complex
mean power `1ᴴC1/N²`. The covariance is an explicit caller operand. These
helpers do not generate noise, impose a distribution, attach physical units,
or feed the receiver. Input arrays are not mutated.

## 10. READY/BLOCKED gates and next decisions

| Gate | Status | Reason |
|---|---|---|
| M1 8PSK normalization and 8-sample ZOH sample-sum arithmetic | **READY** | Unit-magnitude symbols and unscaled repetition are explicit in code. |
| M2 symbol-rate AWGN formula | **READY** | N0 and I/Q component variances are explicit in `channels/awgn.py`. |
| Conditional AR(1) covariance for explicit `n`, innovation and initial-state assumptions | **READY** | Algebra follows the implemented recursion; `n=8` is not auto-bound to ADR-012. |
| M3 independent per-sample AWGN assertion | **BLOCKED / unsupported** | M3 does not attach the M2 AWGN utility to its generated samples; current smoke perturbations are deterministic. |
| Physical Es/Eb label for current waveform | **BLOCKED** | No accepted amplitude/complex-envelope energy normalization is coupled to the sample interval. |
| Narrow discrete AWGN paired M2/B5 control | **READY** | Accepted ADR-015 specifies iid sample noise, shared buffer, mean-of-8 `/a`, and oracle-CSI frozen-B5 control. |
| Physical SNR-calibrated BER/SER | **BLOCKED** | No physical sample interval/amplitude calibration; accepted label is only effective discrete `gamma_b`. |
| General/adaptive matched M2 comparison | **BLOCKED** | M2 has no estimated channel trajectory interface; only the oracle-CSI control is scoped. |
| ADR-014 uncertainty intervals | **BLOCKED** | ADR-014 remains proposed; no bootstrap policy or interval run. |
| Paper 1.5 dB reproduction | **BLOCKED** | This audit neither closes source uncertainties nor reproduces the article experiment. |

ADR-015's narrow discrete control choices are accepted; physical SNR and
adaptive/fair-baseline extensions remain blocked. ADR-014 needs a separate
explicit acceptance before confidence intervals. Accepted ADRs are
001/002/003/004/005/006/007/008/010/012/013/015; proposed ADRs are 009/011/014.
SCI-02, SCI-03 and SCI-METRIC-02 remain open. `paper_exact:false`,
`receiver_enabled:false`.
