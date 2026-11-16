# REPRO-01 — parameter register

SOURCE_DOCUMENTED means explicit in available article S1; SOURCE_UNRESOLVED means no exact value; PROJECT_RECONSTRUCTION is not an author value.

| NAME_IN_ARTICLE | SYMBOL | VALUE | UNIT | PAGE | FULLY_DEFINED | DEFAULT_FOR_REPRO | EDIT | VALIDATION | STATUS |
|---|---|---|---|---:|---|---|---|---|---|
| Signal elements | N | 20000 | elements; precise meaning unclear | 6 | No | record 20000, define mapping | Yes | positive; denominator explicit | PARTIAL |
| Samples/element | n | 8 | samples | 6 | value yes; time grid no | 8 | extension only | positive integer | SOURCE_DOCUMENTED |
| Decoder depth | eta | 20 | intervals/elements | 6 | endpoint ambiguous | 20 transitions proposed | Yes in extension | convention named | PARTIAL |
| Code rate | R | 2/3 | info/coded bits | 5-6 | structural | 2/3 | No | 2 in, 3 out | SOURCE_DOCUMENTED |
| Modulation | — | 8PSK | points | 5 | labeling partial | 8PSK | No in article profile | mapping ID required | PARTIAL |
| Phase increment | Delta phi | pi/4 | rad | 5 | as increment | pi/4 | No | exact | SOURCE_DOCUMENTED |
| Error target | p* | 5e-2 | ratio | 6 | event/denominator partial | record only; never force | target only | event tagged | PARTIAL |
| Rays | L | unspecified | count | 5-6 | No | required field | Yes | integer >0 | UNRESOLVED |
| Delays | tau_l | unspecified | time/samples | 5 | No | named profile required | Yes | conversion declared | UNRESOLVED |
| Fading | mu_s, mu_c | Rayleigh mentioned | amplitude | 5-6 | No | explicit reconstruction | Yes | law/covariance/normalization | PARTIAL |
| Disturbance | xi_s, xi_c | zero-mean Gaussian | amplitude | 6 | No | explicit innovation law | Yes | variance/init/correlation | PARTIAL |
| alpha_fp, sigma_fp | A(10) | exp(-4/n), sqrt(2/n^2*(1-exp(-8/n))) | dimensionless | 6 | formula yes, innovations no | formula with n=8 | n extension | n>0 | PARTIAL |
| Estimator alpha', K-tilde, mu0 | symbols | unspecified | model-dependent | 4 | No | required fields | Yes | finite, units declared | UNRESOLVED |
| RNG/seeds | — | unspecified | — | — | No | deterministic labeled streams | Yes | persist algorithm/version | UNRESOLVED |
| SNR/Eb/N0 | — | convention unspecified | dB | — | No | no article default | extension | power reference declared | UNRESOLVED |
| Trials/stopping | — | unclear | trials | 6-7 | No | predeclared fixed count | Yes | no outcome-driven stop | UNRESOLVED |

## USER_EXTENSION_PARAMETERS
Bit distribution, trial count, RNG, SNR grid, ray powers/K/LOS phase, correlation, noise initialization/covariance, phase synchronization, time grid/carrier removal, termination, metric, mapping, eta endpoints, CI and gain interpolation. Each needs provenance, units, validation and a versioned profile.

Proposed project baseline: Encoder A, R=2/3, n=8, Delta phi=pi/4, N=20000 explicitly defined symbol intervals, initial state 00, no tail padding, ADR-002 marked reconstructed, p*=0.05 as target only, eta=20 transitions. Missing values remain required config fields, never invented author values. Do not import S4 n=4, gamma^2=1, epsilon=0.001 or L=1:2.
