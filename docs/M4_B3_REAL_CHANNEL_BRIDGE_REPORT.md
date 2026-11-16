# M4.7m/B3c-3 — controlled L=1 real-channel I/Q bridge

## Scope and source version

This is a deterministic synthetic control experiment for `L=1`, zero delay, no noise and a static real channel multiplier `h=a`. It is not a general Rician/Rayleigh model or a receiver implementation. As the user noted, the v7 DOCX is not in the workspace; this report does **not** claim v7-specific verification. The [A](5) expression used here is the available equation/scan already recorded in `M4_B3_BASEBAND_COMPATIBILITY_REPORT.md`.

## Algebra

M3's normalized 8PSK baseband point is

\[
x_b=e^{j b\pi/4}=\cos(b\pi/4)+j\sin(b\pi/4).
\]

The controlled real single-path fixture has `z_b=a x_b`, with explicit real `a`, no delay and no noise. M3 `split_iq()` gives `I=Re(z_b)=a cos(bπ/4)` and `Q=Im(z_b)=a sin(bπ/4)`. [A](5) gives

\[
U_1=-\mu_1\sin(b\pi/4),\qquad U_2=\mu_2\cos(b\pi/4).
\]

For the specified special case `\mu_1=\mu_2=a`,

\[
(U_1,U_2)=(-a\sin(b\pi/4),a\cos(b\pi/4))=(-\operatorname{Im}z_b,\operatorname{Re}z_b).
\]

This is an exact +90° coordinate rotation under this real-channel, equal-coefficient control. It does not divide by `h`: the test-only bridge receives only `received` samples and applies `(-Im,Re)`. The fixture knows `a` to construct and independently check its expected samples, but `a`, `ChannelTruth` and `b` are not inputs to the bridge. The actual forward API is also checked using explicit `(a,a)` coefficients and all eight assumed-natural-binary phase labels.

## Independent test results for every phase

`tests/test_m3_real_channel_iq_bridge.py` builds symbols with M3's `constellation()`, expands them with the actual 8-sample `symbols_to_iq_waveform()` helper, applies the controlled scalar `a` in the synthetic fixture, then uses M3 `split_iq()` and the actual aggregate forward function. The independently calculated [A](5) values are the expected values below. Each value is constant across all eight sample positions of its rectangular symbol block.

| `b` | `x_b=(cos,sin)` | `z_b` for `a=0.75` | bridge = [A](5) = forward `(0.75,0.75)` | `z_b` for `a=2` | bridge = [A](5) = forward `(2,2)` |
|---:|---:|---:|---:|---:|---:|
| 0 | `(1,0)` | `0.75+j0` | `(0, 0.75)` | `2+j0` | `(0, 2)` |
| 1 | `(0.707107,0.707107)` | `0.530330+j0.530330` | `(-0.530330, 0.530330)` | `1.414214+j1.414214` | `(-1.414214, 1.414214)` |
| 2 | `(0,1)` | `0+j0.75` | `(-0.75, 0)` | `0+j2` | `(-2, 0)` |
| 3 | `(-0.707107,0.707107)` | `-0.530330+j0.530330` | `(-0.530330, -0.530330)` | `-1.414214+j1.414214` | `(-1.414214, -1.414214)` |
| 4 | `(-1,0)` | `-0.75+j0` | `(0, -0.75)` | `-2+j0` | `(0, -2)` |
| 5 | `(-0.707107,-0.707107)` | `-0.530330-j0.530330` | `(0.530330, -0.530330)` | `-1.414214-j1.414214` | `(1.414214, -1.414214)` |
| 6 | `(0,-1)` | `0-j0.75` | `(0.75, 0)` | `0-j2` | `(2, 0)` |
| 7 | `(0.707107,-0.707107)` | `0.530330-j0.530330` | `(0.530330, 0.530330)` | `1.414214-j1.414214` | `(1.414214, 1.414214)` |

Thus the noiseless **controlled experiment is READY** and passes both real gains for all eight phases. No production observed-IQ adapter or receiver integration was added.

## Complex-channel counterexamples

For a complex `h=u+jv`, `z_b=h e^{jθ}` gives

\[
(-\operatorname{Im}z_b,\operatorname{Re}z_b)
=(-u\sin θ-v\cos θ,\;u\cos θ-v\sin θ).
\]

The `v` terms are absent from the equal-coefficient [A](5) pair `(-a sin θ,a cos θ)`. For a concrete `b=0` counterexample, compare the raw bridge with the illustrative equal coefficients `\mu_1=\mu_2=|h|`:

| Test control `h` | `z_0=h` | `(-Im z_0, Re z_0)` | [A](5) at `b=0`, `μ₁=μ₂=|h|` |
|---:|---:|---:|---:|
| `1+j` | `1+j` | `(-1,1)` | `(0,√2)` |
| `2−0.5j` | `2−0.5j` | `(0.5,2)` | `(0,√4.25)` |

The identity therefore does not extend to a general complex path coefficient. This comparison does not prescribe how [A](5)'s separate coefficient pair should be inferred from a complex M3 channel coefficient.

## Narrow proposed ADR-012 wording — not accepted

> **ADR-012 — L=1 noiseless real-channel I/Q convention.** For a controlled `reconstructed_offline` experiment with exactly one path, zero delay, no noise, a static real channel multiplier `h=a`, and equal explicit coefficients `mu1=mu2=a`, define the per-sample bridge `observed_iq[n]=(-Im(received[n]), Re(received[n]))`. This is a change of I/Q coordinate convention (+90° rotation); it does not divide by, estimate, or otherwise use true `h` inside the observed-IQ operation. The simulation fixture may know `a` to build/test received samples, while the estimated receiver receives only received samples and its own explicit estimates; it must not receive `h`, `ChannelTruth`, `.truth`, or transmitted `b`. This rule is restricted to real `h`; complex-channel cases require a separately specified model and are not covered. The rule does not define how eight samples are reduced to one recursion operand, noise covariance, posterior/likelihood, or multipath behavior; ADR-011 remains proposed.

ADR-012 remains **proposed**. The current test verifies its per-sample transform in the stated noiseless fixture; it does not accept the ADR.

## Proposed temporal convention and unresolved sample reducer

Under accepted ADR-008, the project rectangular profile labels one symbol with eight consecutive samples. A proposed causal rule is: update the estimator once only after all eight sample positions for the current symbol have arrived; do not access any sample from the next symbol; use the post-update snapshot only for a subsequent prediction. This is **not accepted** and does not set whether estimator `time_index` equals symbol index or another counter.

In the exact fixture above, all eight positions contain the same noiseless held value, so a selected sample or their arithmetic mean gives the same test result. That coincidence does not choose an observation operator for a noisy or non-rectangular stream. The current APIs do not decide whether one step's `observed_iq (2,)` should come from a selected position, an eight-sample mean, a matched/integrated value, or another explicit operator. Do not choose one automatically. No future-symbol samples may be used; the snapshot becomes available only after the current block has been received and updated, and can be used starting at the next prediction cutoff.

## Noise and readiness

The rotation is deterministic and requires no noise covariance to calculate. Noise covariance remains an open parameter for any likelihood/posterior or statistical evaluation; do not transfer M3's `N0/2` component normalization to [A] without evidence.

- **Narrow L=1 real-channel experiment — READY as a deterministic test convention.** Two nonzero real `a` values, eight phases, and the aggregate forward output agree.
- **Production L=1 observed-IQ adapter — BLOCKED pending ADR-012 acceptance and a rule selecting/reducing the eight observations for each estimator step.** The test helper is not production receiver code.
- **General complex-fading receiver — BLOCKED.** The rotation identity fails for nonzero `Im(h)`; the conversion/equalization model, coefficient relation, noise covariance and timebase would need new specification. ADR-011 remains proposed for multipath.

No production source kernel, `paper_recursion.py`, `paper_metric.py`, receiver dispatch, `paper_exact:false`, `receiver_enabled:false` or SCI-METRIC-02 status was changed. The requested v7 DOCX is still absent from this workspace, so this report does not claim v7 verification.

## M4.7n/B3c-4 disposition

The user accepted ADR-012 on 2026-10-28 with an explicit extension to this report's earlier experiment: exactly eight transformed samples are arithmetically averaged per symbol, one update occurs after sample `O+8f+7`, and the resulting snapshot is eligible only for symbol `f+1` or later. The real-channel condition is a reconstruction-profile constraint, not an input to the observed-IQ adapter. The adapter receives aggregate complex samples only. It does not normalize by `h` and does not treat the mean as an independent AWGN observation. Noise covariance/correlation remains open. This approval does not verify the absent v7 DOCX.
