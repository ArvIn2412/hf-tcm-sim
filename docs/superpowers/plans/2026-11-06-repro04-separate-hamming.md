# REPRO-04 implementation plan

## Goal

Implement an isolated separate hard-8PSK-demodulation and integer-Hamming Viterbi receiver for Encoder A. The receiver consumes only REPRO-03 `ReceiverObservation`; evaluation truth remains outside the decision path. No M5–M11, REPRO-02, or REPRO-03 mathematics or artifacts are changed.

## Architecture

- Add typed receiver/front-end configuration and immutable result structures in `src/hf_tcm/repro/`.
- Hard-demodulate each explicitly configured symbol window against eight explicit 8PSK hypotheses, then invert the bijective ADR-002 reconstructed triple/phase table.
- Compute canonical Encoder A edge Hamming costs as integer distances 0–3.
- Decode with an isolated full-frame, four-state Viterbi implementation, explicit initial/final/termination constraints, and stable canonical tie-breaking.
- Keep optional BER/SER evaluation in a separate adapter. Its reference data cannot enter `run_separate_receiver`.
- Add serialization, public-observation loading, a no-surprise CLI, and read-only SVG diagnostics from actual result arrays.

## Decisions / limitations

- The phase-label table is project reconstruction ADR-002, not author-confirmed labeling.
- Receiver timing offset is explicitly configured. It is never selected from transmitter/evaluation truth.
- `expected_symbol_count` is explicit because REPRO-03 output can contain a multipath tail. Remainder samples are recorded as unprocessed; they do not form an extra symbol.
- The first declared front end is fixed nominal constellation; the second compensates only a receiver-public configured static complex gain. No hidden CSI or automatic equalizer is used.
- This milestone uses full-frame traceback; it does not claim article `eta=20`.
- The baseline does not promise reliable decisions under unknown time-varying multipath/Rician fading.

## Steps (TDD)

1. Add independent tests for config validation, all eight phase hypotheses and inverse mapping, all sixteen Hamming edges, tie behavior, initial/final-state rules, explicit sample alignment/tail handling, truth isolation, and short noiseless transmitter→channel→receiver evaluation.
2. Run focused tests to confirm the new tests fail before implementation.
3. Implement receiver config, hard demodulator, Hamming metric, full-frame Viterbi, receiver orchestration/result, and evaluation adapter.
4. Add observation/result serialization, REPRO-03 public-only input loader, CLI, and real-data SVG plot adapter. Add deterministic and Rician-multipath smoke coverage without treating it as performance evidence.
5. Run REPRO-04 tests, full pytest, Ruff check/format, reference frame processing and historical fingerprint verification.
6. Write the six requested REPRO-04 documents and update PLAN/NEXT_TASK/BUILD_VERIFICATION only with observed results.

## Verification commands

`python -m pytest -q tests/repro/test_receiver*.py --tb=short --basetemp tmp/pytest-repro04-focused -p no:cacheprovider`

`python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro04-final -p no:cacheprovider`

`ruff check src tests`

`ruff format --check src tests`

Historical M5–M10 fingerprint verifier will be discovered from the repository and run read-only.

## Completion criteria

Receiver returns actual hard symbols/triples, integer Hamming metrics, full-frame decoded bits/path metrics, and reproducible metadata from public observation only; independent fixtures pass; CLI/serialization/plots work; full regression and historical integrity checks pass. Otherwise report `REPRO_04_SEPARATE_RECEIVER_PARTIAL` with exact blockers.
