# Demo Defense Checklist

## Before the defense

- [ ] Start from the repository root with `python -m hf_tcm.demo_studio` or double-click `start_demo.cmd` (optional: `start_demo.cmd -Port 8766`).
- [ ] Confirm the browser URL uses `127.0.0.1` or `localhost`.
- [ ] Open “Захист магістерської · F=32” and press “Запустити демонстрацію”.
- [ ] Confirm 32 symbols, 256 samples, two receiver arms, no RNG, and the deterministic/not-scientific-evidence label.
- [ ] Confirm both arms show one shared received SHA-256 and exact policy values.
- [ ] Keep `paper_exact:false` and `receiver_enabled:false` visible while explaining the reconstruction.

## Demonstration path

- [ ] Inspect bits, TCM encoder, four canonical states, and all 16 edge rows.
- [ ] Click an edge in the table and on the graph; confirm synchronized highlighting and distinct hypothesis, decoded, and reference columns.
- [ ] Visit symbol indices 0, 1, 15, 16, 30, and 31. Confirm eight samples, indices, 16 predictions/metrics/posteriors, estimator pre/post states, decoded position, and error flags update together.
- [ ] On symbol 31, explain that no next-symbol prediction is defined.
- [ ] Explain estimator causality in order: pre-state, current predictions, current metrics, posterior, innovation, post-state, then next-symbol prediction.
- [ ] Search the Inspector for `alpha_prime`, `k_tilde`, `mu0`, `beta`, or a runtime state. Read-only fields are table entries, not sliders.
- [ ] After the run, search the Inspector for `runtime.F`, `runtime.samples_per_symbol`, `runtime.encoder_state_before`, `runtime.transition_edge`, `runtime.phase_index`, `runtime.candidate_metrics`, `runtime.posterior_weights`, `runtime.estimator_pre_state`, `runtime.estimator_post_state`, `runtime.viterbi_decision`, `runtime.BER`, `runtime.SER`, `noise.sigma_squared`, `profile.gamma_b_eff_db`, `historical.M9b.delta_ber_ci`, and `historical.M10b.primary_delta_ber_ci`.
- [ ] Confirm the selected-symbol Inspector values change when the symbol slider moves and stop at f=31.
- [ ] Present M9 and M10 values with their intervals and explicitly say both intervals include zero.
- [ ] Explain M5j aggregate-only trace availability and that M7b TRAIN ranking is not independent validation.
- [ ] Use Previous, Next, Reset, Return, and Inspector controls in presentation mode.
- [ ] Follow the revised sequence: architecture, bits, four states, sixteen transitions, edge selection, 8PSK, waveform, channel, received samples, predictions, metrics, posterior, estimator, Viterbi, decoded sequence, BER/SER, M9/M10, limitations.

## Close

- [ ] State that ADR-002/ADR-005 are project reconstructions and SCI-02, SCI-03, and SCI-METRIC-02 remain open.
- [ ] Do not claim an author-confirmed HMM, forward-backward, Baum-Welch, or statistically significant improvement.
- [ ] Remind the audience that stage 28 paired inference requires archived independent studies.
