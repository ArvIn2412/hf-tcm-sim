# M5c Noise and Energy Calibration Design

**Intent:** Audit the actual M1/M2/M3 and reconstructed receiver conventions, then make the energy/covariance arithmetic reproducible without selecting a future SNR model.

**Goals:** Document symbol-rate, discrete sample-sum, and conditional physical-energy meanings; derive M2 AWGN and M3 AR(1) noise statistics; assess common-observation and CSI parity; propose but do not accept ADR-015; keep all SNR and matched-baseline gates blocked.

**Non-goals:** No stochastic channel changes, SNR sweep, Monte Carlo, baseline comparison, confidence interval, receiver activation, or performance claim. `paper_exact:false`, `receiver_enabled:false`, ADR-014 proposed, and open SCI questions remain unchanged.

**Approaches:** (1) Documentation-only audit is lowest risk but leaves the deterministic identities unexercised. (2) Add small pure sample-domain diagnostics for finite complex energy, fixed-size ZOH block energy, sample means/power, and covariance-derived mean variance. The second is selected because the request explicitly lists deterministic tests and it introduces no physical normalization or noise assumption.

**Implementation call:** Diagnostics return measured/discrete quantities only. Physical energy is a separate calculation requiring an explicit positive sample interval. AR(1) covariance is derived only for the explicit recurrence/initial-state/innovation assumptions; the code does not claim independent AWGN. Tests use supplied arrays and covariance matrices, never random draws.

**Files:** Add `src/hf_tcm/evaluation/signal_diagnostics.py`, its focused test, and `docs/M5_NOISE_BASELINE_CALIBRATION_AUDIT.md`; update the listed M5/M4 decision, verification, and planning documents. Do not modify M1-M3 or receiver kernels.
