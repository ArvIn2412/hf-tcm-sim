# REPRO-08 design: article crosswalk and bounded receiver comparison

## Intent and goal

Audit the available 2026 paper against the implemented experiment chain, explain the REPRO-07 B0 error floor using controlled channel cases, define a discrete energy/noise scale without pretending it is physical Eb/N0, and run a bounded, reproducible multi-arm experiment. Preserve the original REPRO-07 records and all REPRO-02..06C mathematics.

## Decisions and approaches

1. **Keep only B0 and compare all cases.** This reproduces the historical comparison exactly but leaves its known channel/ISI mismatch confounded. It is retained as the historical arm, not chosen as the only scientific baseline.
2. **Use a public-static-CSI hard detector as B1.** A separate decision-feedback detector predicts the delayed sample contributions from previously detected phase symbols, uses only explicit receiver configuration, hard-decides the current 8PSK phase, then passes inverse labels through the existing Hamming Viterbi. This is the selected controlled baseline for static channels because it adds no EvaluationTruth and permits independent waveform tests. It is not claimed to reproduce the paper receiver.
3. **Use an unvalidated blind adaptive B1.** This could cover unknown Rician fading, but without a known pilot protocol it would add a new estimator and identifiability assumptions. It is deferred; B1 is rejected for hidden time-varying channels in this milestone.

## Signal and statistical conventions

Keep source amplitude A=1, 8 complex samples per TCM transition, and finite-depth eta=20. Define discrete sample energy per information bit as `E_b,d = sum_i |x_k[i]|^2 / 2 = 8 A^2 / 2 = 4` for the current ZOH profile. For circular complex noise with `E|w|^2 = sigma_c^2`, define dimensionless `gamma_b,dB = 10 log10(E_b,d / sigma_c^2)`. Do not call this physical Eb/N0: sample period, receiver bandwidth, and matched-filter convention are unspecified. Generate independent bit/fading/noise streams by trial and use common observations across all arms within a trial.

## Source interpretation

Use `references/source_paper_2026.docx` as the latest local article artifact only with an explicit version caveat; the source register says its exact v7 status is unconfirmed and a different v3 manuscript exists. Visually checked pages 4-7 and distinguish source-supported formula structure from reconstructed project choices. The paper's `p*_n` is described as channel error frequency, not established as decoded payload BER. Preserve `paper_exact:false`.

## Non-goals

No changes to old receivers or historical results; no tuning to the paper's 1.5 dB claim; no genie-aided equalization; no hidden-state disclosure to a receiver; no claim of physical HF propagation; no REPRO-09.

## Remaining implementation choices

Implement the static public-tap B1 under a new isolated REPRO-08 module, test it against hand-computed complex samples and the existing hard-demod/Hamming stages, then reuse the existing transmitter, channel, joint receiver, separate receiver, and paired bootstrap rather than copying them. Run Phase A controls first. Only profiles that pass Phase A enter the bounded statistical pilot. Save all new outputs below `outputs/repro08/` with config, per-trial seeds/hashes, aggregate counts, CIs, completeness state, and measured SVGs. A one-pair F=20,000 or resource-capped attempt is not confirmatory evidence.
