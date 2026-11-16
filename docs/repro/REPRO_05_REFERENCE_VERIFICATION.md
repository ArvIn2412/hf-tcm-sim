# REPRO-05 — reference verification

## Independent tests

- Scalar complex residual fixtures independently calculate Euclidean and squared-Euclidean values.
- All 16 independent vectors in `docs/repro/REPRO_01_ENCODER_TEST_VECTORS.json` use the documented direct GF(2) substitution oracle. The test derives each project phase label from the independent output triple as `4*c2+2*c1+c0`, then checks all 8 predicted complex samples.
- Stable soft weights are tested with large beta and metric ranges; the estimator is checked against hand-calculated weighted innovation and one-step update.
- Float Viterbi is tested with an independently selected zero-cost edge path, canonical tie handling, and nonzero initial TCM state.
- Identity, known public complex gain, one-sample timing offset, exact 8-sample alignment, unused tail samples, zero-tail termination, paired REPRO-04 input hash, adaptive seeded Rician, truth rejection, multipath rejection, NPZ/JSON hashes, and real-data plots are covered.

The REPRO-05 test does not rewrite REPRO-01 vectors or the REPRO-02 encoder. It independently checks phase computation and checks the candidate ordering against the specified canonical edge identity. The sample-range contract is inclusive and `sample_indices` contains all eight samples for every processed symbol; extra tail indices are retained explicitly as unprocessed.

## Full-frame saved run

The preserved 20,000-symbol REPRO-02 reference was used with an identity channel profile. Joint and separate receiver arms used the exact same receiver-observation SHA `74697c52e4537bf899e1143f1b2c7111d0d121505566c94d6a0bb097936bd722`; both produced zero bit and symbol errors against the evaluation-only reference. This is a deterministic one-frame consistency check, not evidence of statistical superiority.

The output at `outputs/repro05/reference_n_star/joint_receiver/` has 26 NPZ arrays and 14 SVG files. All manifest/summary SHA-256 values, all plot hashes, all plot XML, and the paired REPRO-04 sub-bundle hashes were checked. Key hashes:

- Config: `522b0922a18a0c0230868d778da47a74081f71c5bf1e1b927730c915da8cb462`
- Numeric result arrays: `b4ee1d8182f06dc05d09d436ec438f7453811d535b24edd8bff236e05368cf52`
- Receiver result NPZ: `bd636e1a29a210ddda700e242aa0bb006d5fe4ea654e8e429fad23b1d0a76bea`
- Final manifest: `e8f84f6970fea42187471440dd1a56715c5a8409c763bb9ff09bd9cd76a7cbb8`

## Test and historical integrity

Focused REPRO-05: **18 passed**. Final full pytest: **1055 passed in 70.99 s**. `ruff check src tests` passed; `ruff format --check src tests` passed with 216 files. The Windows OneDrive workspace basetemp encountered the established ACL cleanup restriction; final pytest used `%TEMP%` without deleting protected directories. Historical M5-M10 recount against `tmp/m11d-integrity-before.json`: **694/694 matched**, zero changed and zero missing.

## Limits

Identity/static gain verify the selected deterministic project model. Adaptive Rician verifies finite outputs/repeatability and causal execution, not estimator accuracy or HF physical validity. Multipath is unsupported. A(2), the complex interpretation of A(1), ADR-002 author mapping, initial estimator values, flat pseudo-prior, and beta remain reconstructed/unresolved as detailed in REPRO-01. Full-frame traceback is not eta=20.
