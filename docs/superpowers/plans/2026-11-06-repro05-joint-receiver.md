# REPRO-05 execution plan

## Scope

Implement the approved REPRO-05 design in a new `hf_tcm.repro` joint-receiver namespace. Leave REPRO-04 and all older mathematics/artifacts unchanged. No Monte Carlo or REPRO-06.

## Steps — tests first

1. Add independent tests for Euclidean and squared-Euclidean scalar metrics; 16-edge prediction references; soft posterior normalization/extremes; hand-computed adaptive recursion; causality; float-metric Viterbi/ties/termination; truth isolation; multipath rejection; same-observation REPRO-04/05 identity integration; serialization and plots.
2. Run the new tests and confirm expected RED failures before implementation.
3. Implement strict joint config, candidate predictor, separate metric kernels, stable soft posterior, causal complex single-path estimator, and float-cost trellis Viterbi.
4. Add exact-type `ReceiverObservation` validation, memoryless-profile guard, immutable result arrays, evaluation-only BER/SER adapter, NPZ/JSON I/O, CLI and actual-data SVG diagnostics.
5. Run deterministic short fixture, F=32, F=256 and reference F=20000; record per-stage runtime/storage, without interpreting them as a benchmark.
6. Run full pytest, Ruff check/format, historical 694-item SHA recount, manifest/SVG verification. No Node/Edge unless GUI is changed.
7. Write the eight requested REPRO-05 documents and update PLAN/NEXT_TASK/BUILD_VERIFICATION with observed results.

## Key invariants

- Candidate predictions use `estimator_state_pre[k]`; current posterior update affects only symbol k+1.
- Branch costs are unweighted raw distances (selected profile); posterior and Viterbi cost transforms are separately serialized.
- Candidate dimension/order equals the canonical REPRO Encoder A edge table (16 rows).
- Receiver gets exact `ReceiverObservation` and never `ChannelResult`/`EvaluationTruth`.
- Multipath public profiles fail explicitly; no symbol-local approximation is labelled valid joint inference.
- Full-frame traceback is not eta=20.

## Verification commands

`python -m pytest -q tests/repro/test_joint_receiver.py --tb=short --basetemp tmp/repro05-focused -p no:cacheprovider`

`python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro05-final -p no:cacheprovider`

`ruff check src tests`

`ruff format --check src tests`

## Completion condition

Declare `REPRO_05_JOINT_RECEIVER_READY` only when all tests, reference processing, manifest verification, and historical recount pass for the explicitly limited memoryless/single-path profile. Otherwise report `PARTIAL` and exact unsupported behavior.
