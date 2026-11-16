# M4.7l/B3c-2 — M3 baseband and reconstruction forward compatibility

## Scope and source availability

This audit compares the M3 normalized complex 8PSK/baseband convention, the visible [A](3)–(6) scan, and the existing project `iq_prediction.py` / `reconstruction_forward.py` APIs. The requested file `Яковів_Гриненко_2026_в7 27-10-26.docx` is **not present** in the workspace. `references/` contains `source_paper_2026.docx`, the earlier v3 file, and page scans `key_pages/page-4.png`–`page-7.png`; `references/README.md` identifies `source_paper_2026.docx` as the provided original, but does not identify it as v7. Therefore the equations below were visually checked against the available page-5 scan and local source, **not independently verified against v7**. No claim is made that the missing version has identical formula presentation.

## Equations and APIs compared

M3 modulation uses unit-radius symbols

\[
x_b=e^{j b\pi/4}=\cos(b\pi/4)+j\sin(b\pi/4),\qquad b=0,\ldots,7.
\]

`symbols_to_iq_waveform()` repeats each complex symbol for the configured number of samples (8 in the exercised project profile). M3 `apply_multipath()` returns complex samples of the form `z[n]=h[n] x[n-d]` summed over paths; for the tested one-path static case with zero delay, `h` is constant over the vector. The channel API returns `truth` separately, but the fixture and comparisons below do not read it. M3's `split_iq()` is exactly `(Re(z), Im(z))`; it does not downconvert or equalize.

The available [A](3) scan gives a real passband signal `S(t_i)=A(t_i)cos(ω₀t_i+b(t_i)Δφ+ψ(t_i))`. [A](4) expresses its received signal as a sum of `U_{s,1}^{(l)} sin(ω₀t_i) + U_{s,2}^{(l)} cos(ω₀t_i)` plus disturbance. [A](5), with `Δφ=π/4`, gives

\[
U_{s,1}^{(l)}=-\mu_{1,i}^{(l)}\sin(b_i^{(l)}\pi/4),\qquad
U_{s,2}^{(l)}=\mu_{2,i}^{(l)}\cos(b_i^{(l)}\pi/4).
\]

The current `iq_quadratures_from_index()` implements these two signed expressions. `predict_reconstructed_aggregate_iq()` passes the explicit estimated coefficient pair `(mu1,mu2)` to that algebra, repeats each pair over 8 samples, shifts it by the supplied integer sample delay, applies zero-padding/cropping, then sums paths. For `L=1`, its returned aggregate is the one predicted pair repeated across the symbol's 8 sample labels.

## Independent controlled comparison

Added `tests/test_m3_baseband_reconstruction_compatibility.py`. The fixture uses all eight unit-radius M3 symbols, 8-sample rectangular hold, one static path, zero delay and no AWGN. A known static test channel coefficient is reconstructed from the explicit channel configuration and seeded control RNG; `ChannelOutput.truth` is never used as an estimated-receiver input. Two nonzero [A](5) coefficient pairs are tested: `(1.7, 0.6)` and `(0.45, 2.3)`. For each pair, the test compares all 8 complex received symbols and their Re/Im values, an independently written [A](5) calculation, `iq_quadratures_from_index()`, and all 8 samples/symbol from the actual aggregate forward API.

For the reproducible test channel coefficient `h=1.4807522638 + j·0.1548823991`, the raw complex baseband symbol is `z_b=h x_b`. The table shows the raw M3 sample and Re/Im, its unit-symbol value after division by this explicit **test-only control** `h`, and the per-symbol value returned by [A](5) and the forward API. The final column gives the forward result for the second coefficient pair. Each forward pair is repeated over 8 samples.

| `b` | M3 `z_b` | `(Re z_b, Im z_b)` | `z_b/h` `(I,Q)` | [A](5) / forward `(1.7,0.6)` | [A](5) / forward `(0.45,2.3)` |
|---:|---:|---:|---:|---:|---:|
| 0 | `1.480752+j0.154882` | `(1.480752, 0.154882)` | `(1, 0)` | `(0, 0.6)` | `(0, 2.3)` |
| 1 | `0.937532+j1.156568` | `(0.937532, 1.156568)` | `(0.707107, 0.707107)` | `(-1.202082, 0.424264)` | `(-0.318198, 1.626346)` |
| 2 | `-0.154882+j1.480752` | `(-0.154882, 1.480752)` | `(0, 1)` | `(-1.7, 0)` | `(-0.45, 0)` |
| 3 | `-1.156568+j0.937532` | `(-1.156568, 0.937532)` | `(-0.707107, 0.707107)` | `(-1.202082, -0.424264)` | `(-0.318198, -1.626346)` |
| 4 | `-1.480752-j0.154882` | `(-1.480752, -0.154882)` | `(-1, 0)` | `(0, -0.6)` | `(0, -2.3)` |
| 5 | `-0.937532-j1.156568` | `(-0.937532, -1.156568)` | `(-0.707107, -0.707107)` | `(1.202082, -0.424264)` | `(0.318198, -1.626346)` |
| 6 | `0.154882-j1.480752` | `(0.154882, -1.480752)` | `(0, -1)` | `(1.7, 0)` | `(0.45, 0)` |
| 7 | `1.156568-j0.937532` | `(1.156568, -0.937532)` | `(0.707107, -0.707107)` | `(1.202082, 0.424264)` | `(0.318198, 1.626346)` |

The direct M3 `(Re,Im)` pair is **not** the [A](5) pair: phase order/sign differs, and its unit-radius amplitude is not the independent `(mu1,mu2)` scaling. With identity channel normalization `h=1`, the exact controlled conversion is

\[
(U_{s,1},U_{s,2})=(-\mu_1\,\mathrm{Im}(z),\;\mu_2\,\mathrm{Re}(z)).
\]

For a nonzero static complex path coefficient `h=a+jb`, first remove its phase/gain using an explicit receiver-side estimate `\hat h` (the fixture uses known `h` only as an oracle), then apply the above conversion. With exact test `h`, the equivalent real matrix from raw `(I,Q)` is

\[
\begin{bmatrix}U_{s,1}\\U_{s,2}\end{bmatrix}
=\frac{1}{|h|^2}
\begin{bmatrix}\mu_1 b&-\mu_1 a\\\mu_2 a&\mu_2 b\end{bmatrix}
\begin{bmatrix}I\\Q\end{bmatrix}.
\]

Thus there is a coefficient-dependent fixed conversion in this controlled synthetic case, not direct equality and not a universal scale-only correction. For `mu1=mu2=1` and `h=1`, it reduces to a +90° rotation `(-Q,I)`; unequal coefficients add separate quadrature scaling. The tests establish this algebraic relation and forward agreement, **not** an implementable receiver bridge: production code has no authorized `\hat h` estimation/demodulation rule, and the test deliberately does not expose its control `h` to estimated-receiver code.

## Amplitude versus noise

The deterministic phase-to-quadrature calculation requires no noise model. A noisy input can still be transformed deterministically once its extraction operator is specified. Noise distribution and covariance are needed to interpret extraction uncertainty, form likelihood/posterior weights, and conduct statistical/performance studies; they are not needed to evaluate [A](5) or the zero-noise mapping above. M3 complex AWGN uses variance `N0` with `N0/2` in each real component. That normalization is not automatically [A](4)'s `ξ(t_i)` covariance, nor the fading-noise normalization in [A](9)–(10). Do not infer one from the other.

## Minimum clock contract and causal proposal

Current APIs define three different labels:

- **Absolute sample index:** `reconstruction_alignment.py` labels samples by explicit integer segment/frame origins; M3's returned vector by itself has only buffer offsets. For 8-sample hold, symbol `s` starts at `symbol_origin_sample+8s`, occupies the next eight labels, and integer delay shifts labels forward before zero-padding/cropping.
- **Symbol index:** the integer `s` in the explicit project mapping above. The code does not infer it from an arbitrary received sample vector.
- **Estimator `time_index`:** the state/sequence API requires consecutive integer labels `i→i+1`, but does not identify `i` as a sample or symbol. [A](1)'s discrete `i+1` and [A](3)–(6)'s `t_i` do not specify sampling rate, samples per symbol, or update cadence. Consequently sample-level versus symbol-level update is **unresolved by the source/API**.

**Draft project timing assumption, not accepted:** choose one estimator update per symbol. Assign update `k` to an explicitly declared symbol label `s_k`; collect that symbol's full 8-sample block after applying the declared delay/alignment and extraction rule; make its observation available only after the final block sample `n_0+8s_k+7` is received. Only then may state `k→k+1` be updated. Its new snapshot may be used for predictions whose declared cutoff begins after that availability point. Under the current forward API, one coefficient pair remains fixed for each supplied frame, so a snapshot cannot silently vary inside that frame. The exact relation among `k`, `s_k`, absolute sample origin and frame boundaries remains a user decision.

The current M3 API returns a completed sample vector; it has no per-sample arrival event or latency contract. In a causal streaming convention, `received[n]` would become available only after that absolute sample is acquired. Under the draft symbol-block proposal, `observed_iq[s]` and its state update are unavailable until sample `n_0+8s+7` has arrived (plus any explicitly chosen processing latency). That availability rule is proposed for a future contract; it is not provided by `apply_multipath()` or the batch forward API.

No `received[n]`, posterior, prediction or coefficient snapshot available after a prediction cutoff may be used for that earlier prediction/state. `reconstructed_offline` does not authorize lookahead. A noncausal offline smoothing regime would need its own explicit data window, output labels and provenance decision.

## Proposed ADR-012 wording (not accepted)

> **ADR-012 — L=1 aggregate-baseband to observed-I/Q bridge and causal clock.** For `reconstructed_offline` and exactly one path, define the receiver-side transformation from complex M3 aggregate samples to `observed_iq (2,)` for one estimator update. Specify an absolute sample origin and sample window; symbol origin and the use (or rejection) of the 8-sample rectangular block; integer delay/zero-padding treatment; the receiver-side complex gain/phase estimate or other demodulator state and its provenance; the exact real-valued transformation into [A](4)/(5) quadrature order/sign/scale; the relation of that transformation and `(mu1,mu2)` to [A](6); whether estimator ticks are sample- or symbol-level and the mapping to `sample_index`/`symbol_index`; when the final input sample, posterior and predictions become available; the causal cutoff and which subsequent frame may use the resulting full-estimate snapshot; and the noise source, per-quadrature covariance and normalization for likelihood/statistical use. No operation may inspect `ChannelTruth`, `.truth`, generator state or hidden channel coefficients. This one-path decision does not accept or define multipath pseudo-observations; ADR-011 remains proposed.

The zero-noise conversion tested above is a candidate algebraic fixture, not an automatic choice for ADR-012. A decision must also resolve how `\hat h` or its equivalent is obtained without truth leakage. ADR-012 remains **proposed**.

## Readiness

- **L=1 observed-IQ bridge — BLOCKED.** A reproducible controlled conversion exists for synthetic samples with a supplied static test coefficient, but the production receiver has no permitted gain/phase estimate, extraction window, scale or noise provenance.
- **Causal integration — BLOCKED.** Sample, symbol and estimator clock mapping/update cadence are undecided; availability cutoffs and frame-snapshot selection are not wired. The symbol-level rule above is only a proposal.
- The full-IQ snapshot adapter remains an immutable copy with an estimator label only. The forward model, `paper_recursion.py`, `paper_metric.py`, `receiver_enabled:false`, `paper_exact:false`, and SCI-METRIC-02 are unchanged. ADR-001/002/006/007/008/010 remain accepted; ADR-003/004/005/009/011 remain proposed; ADR-012 remains proposed.
