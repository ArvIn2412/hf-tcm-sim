# REPRO-04 — фінальний звіт

## Статус

`REPRO_04_SEPARATE_RECEIVER_READY` для визначеного REPRO-04 project profile: Encoder A, явні nominal/public static gain front ends, 8-sample symbol windows, hard 8PSK і full-frame Hamming Viterbi. Це не підтвердження точності відтворення авторської receiver або адаптивного каналу.

## Додано

- `receiver_config.py`: versioned config, front-end modes, strict constraints.
- `hard_8psk_demodulator.py`: 8-hypothesis squared-Euclidean hard classifier та ADR-002 inverse.
- `hamming_metric.py`, `hamming_viterbi.py`: canonical integer costs і 4-state full-frame traceback.
- `separate_receiver.py`, `receiver_evaluation.py`: receiver result/API та ізольований evaluation contract.
- `receiver_io.py`, `receiver_cli.py`, `receiver_evaluation_cli.py`, `receiver_plot_adapter.py`: receiver-only NPZ/JSON, public-observation loader, окремий evaluation CLI і SVG diagnostics.
- `configs/repro04/reference_n_star_receiver.json`; незалежні REPRO-04 тести.

## Фінальна перевірка

- `python -m pytest -q tests/repro/test_separate_receiver.py --tb=short --basetemp tmp/repro04-focused-evalcli -p no:cacheprovider` — 16 passed.
- `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro04-final-release -p no:cacheprovider` — 1037 passed.
- `ruff check src tests` — PASS; `ruff format --check src tests` — PASS, 205 files.
- CLI reference run обробив рівно 20,000 символів, 160,000 sample indices; три tail samples не утворили символ.
- Manifest перевірив 13 файлів/артефактів без SHA mismatches; усі 10 SVG розібрано як XML.
- Read-only historical recount проти `tmp/m11d-integrity-before.json`: 694/694 matched, 0 missing/changed.
- Reference result NPZ SHA-256: `8682e31a56c60d11c7c9e9b9530392ba5af59cf55a076f901ce245ef64e283aa`; output-array SHA-256: `683052c7d5ee6bd4ed8eaa63f62395e6a706ece57ef93716c22d490eb8f789ad`.
- Latest single-run timing from `outputs/repro04/reference_n_star/performance.json`: receiver 0.1991 s (demodulation 0.0044 s, Hamming 0.0052 s, Viterbi 0.1623 s), plot generation 0.0299 s. Arrays 4,240,058 bytes; NPZ 1,572,548 bytes. Peak RSS unavailable; this is not a benchmark.
- Node/Edge checks не запускали: JavaScript/GUI не змінювався.

## Обмеження

Mapping ADR-002 reconstructed; `φ₀` має задаватися явно. Фіксований nominal receiver не оцінює фазу/амплітуду невідомого каналу. Відомий static gain допустимий лише як receiver-public config. Немає equalizer для time-varying Rician multipath. Візуальний/повний кадр — не `η=20`. Evaluation BER/SER не виконується всередині receiver. `paper_exact:false`, `receiver_enabled:false`, SCI-02/03/METRIC-02 OPEN.

## Перехід до REPRO-05

REPRO-05 може спожити той самий `ReceiverObservation` hash і побудувати окрему joint-demodulation/decoding гілку. До paired comparison потрібно зафіксувати receiver-visible phase/timing/channel assumptions, однакову mapping/profile та однакові sample indices. Не передавати `EvaluationTruth` жодному receiver; не трактувати одиничний fixture як доказ переваги.

