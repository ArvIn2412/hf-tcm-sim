# REPRO-06B — фінальний звіт

## Вердикт

- Загалом: **`REPRO_06B_MULTIPATH_PARTIAL`**.
- `STATIC_MULTIPATH_MLSE_READY` — статичні публічно задані complex gains і integer delays.
- `AUGMENTED_TRELLIS_READY` — bounded graph, у тому числі reference `D=3`.
- `MULTIPATH_ETA20_READY` — streaming finite-depth/full-frame batch modes, latency та flush.
- `ADAPTIVE_RICIAN_MULTIPATH_PARTIAL` — профіль відхиляється, survivor-specific estimator не перевірений.
- `TRUTH_ISOLATION_READY` — receiver API приймає тільки публічний observation і config.

## Реалізація

Закон каналу і transmitter timing узгоджено з REPRO-02/03. При D=3, 8 samples/symbol, розширений вузол зберігає попередню phase, оскільки чотиристановий encoder state її не визначає. Отримано 17 reachable states/68 edges. Branch cost — configurable Euclidean norm або squared Euclidean residual по всіх актуальних відліках transition, включно з tail у останньому рядку. Known static CSI надходить з явної receiver config; прихований channel truth не використовується. Generic expanded Viterbi зберігає bounded predecessor ring для eta і не змінює старі REPRO-04/05/06 engines.

Adaptive unknown Rician multipath з ISI потребує per-survivor/channel-history state або доведеного posterior-weighted causal update. Цей профіль не було реалізовано; він не маскується під single-path recursion.

## Контрольні результати

Незалежний exhaustive evaluator для F=4 перебирає 256 input sequences і повний waveform cost. Для static `[0,3]` він збігається з MLSE/Viterbi sequence та metric. Повний інтеграційний сценарій провів F=32, 256 і 20 000; останній має 40 000 information bits, 160 000 Tx samples і 160 003 Rx samples. Tail indices 160000–160002 оцінюються як частина transition 19999. Joint η=20 використав максимум 20 survivor rows.

У трьох одноразових noiseless static project fixtures BER/SER обох arms дорівнює нулю. Це не незалежна статистична evidence і не superiority claim. Модельні коефіцієнти `h0=1+0j`, `h1=0.35+0.15j` — project values, не стаття.

F=20000 одиничне вимірювання: transmitter 0.1139 s; channel 0.0288 s; joint total 1.1245 s (metric matrix 0.2193 s, Viterbi 0.8241 s); Hamming total 0.6584 s; plots 0.1648 s. Compressed outputs: observation 326,334 B, joint NPZ 1,329,660 B, Hamming NPZ 474,055 B, SVGs 4,435,200 B. Це одне runtime вимірювання, не benchmark; peak RSS не вимірювався.

## Перевірка та збереження

Focused ISI suite: **35 passed**; final full regression: **1121 passed in 70.21 s**. `ruff check src tests scripts` і `ruff format --check src tests scripts` пройшли; 238 Python files format-clean. `scripts/verify_repro06b_artifacts.py` підтвердив 76/76 bundle files, 27 SVG XML та 694/694 історичні fingerprints. Root output manifest SHA-256: `da2bf0f4ac1c065ee5e59104e5fc3eb62f9b699e28122884b96d8735819aa316`. Повний запис команд — `docs/BUILD_VERIFICATION.md`.

Поточні flags/statuses лишаються: `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN. Немає GUI, REPRO-03/04/05/06, ADR, M5–M10 або Monte Carlo змін. Не запускався REPRO-07.
