# REPRO-06C final report

## Реалізація

Створено строгі configs без truth-полів, sample-level complex Kalman/RLS primitives, delayed ZOH regressors, per-augmented-node survivor adaptive receiver, NPZ/JSON persistence, CLI, actual-data SVG plots і paired F=32 runner. API приймає тільки точний тип `ReceiverObservation`. REPRO-06B static-known receiver та всі попередні математичні модулі лишилися окремими.

## Перевірені факти на цьому звіті

- 17 вузлів / 68 ребер для delay `[0,3]`; η=20 має звичайне рішення при k=19 та зберігає повний decoded output через frame flush.
- 14 нових targeted tests пройшли наявний набір config/estimator/receiver fixtures.
- F=32 paired suite: identity 0/64 BER errors обом arms; known-static 06B 0/64 і Hamming 0/64; unknown-static 0/64 для конкретного явно заданого nominal prior; slow-Rician і Rician-AR(1)+AWGN adaptive 0/64. Значення окремих кадрів не є статистичними доказами.
- Same observation SHA перевірено для обох receiver arms; static-known path користується незміненим 06B API.
- Створено п'ять SVG з реальних observation/result arrays на кожен adaptive сценарій.

## Статуси до завершення перевірок

## Фінальна перевірка

- F=20,000 run на REPRO-03 Rician AR(1) `ReceiverObservation` завершено: 160,000 transmit samples, 160,003 receive samples, 40,000 decoded information bits, 17 states/68 edges, η=20, максимальний survivor ring 20. Runtime 152.96 s; NPZ 28,031,692 bytes; result SHA-256 `e651e1f636717c985b45d38be8f3f4a206026dd235919bca90820afcd46985ac`; NPZ SHA-256 `2f06ba4ee9cb887440a75ff47a75c541047a54f9d66e93eeca1f3ded699ea3ef`.
- F=256 seeded Rician AR(1)+AWGN run завершено; adaptive arm мав 6/512 evaluation-only bit errors (0.01171875), Hamming arm — BER 0.19140625 і SER 0.3203125. Це один кадр, не підтвердження переваги.
- F=32 paired identity, known-static (існуючий 06B), unknown-static, slow Rician і Rician AR(1)+AWGN fixtures завершено. Для adaptive arms у цих конкретних fixtures bit errors: 0/64; для Hamming відповідно 0/64, 0/64 для known-static 06B pair, 0/64, 4/64 і 8/64. Observation SHA збігається всередині кожної пари.
- Targeted suite: 14 passed. Final full suite: 1135 passed (35.70 s). Ruff `check src tests scripts/run_repro06c_paired_checks.py scripts/run_repro06c_reference_frame.py` та відповідний `format --check` пройшли. Output manifest перевірено для F=20,000, F=256 та чотирьох F=32 adaptive scenarios. Усі 72 REPRO-06C SVG пройшли XML parse. Historical verifier: 694/694 fingerprints, 76/76 REPRO-06B root files, 27 REPRO-06B SVG valid.
- Незалежні тести підтверджують ручний комплексний Kalman update, sample-rate AR(1), rank-deficient stability, D=3 regressor, causal pre-update metric, незалежні filter states, survivor selection за frozen metric rows, ETA latency/flush та paired observation hashes.

### Перевірка після оновлення evaluation summary

- Повторний запуск `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro06c-final4 -p no:cacheprovider` завершився результатом **1135 passed in 34.49 s**.
- Повторні `ruff check src tests scripts/run_repro06c_paired_checks.py scripts/run_repro06c_reference_frame.py` і відповідний `ruff format --check` пройшли. Усі 6 REPRO-06C output manifests повторно перевірено SHA-256; усі 72 SVG прочитано як XML.
- `ruff check .` не є чистим через ACL-denied traversal та 27 наявних lint findings у generated `docs/figures/generate_thesis_figures.py`. `ruff format --check .` завершується помилкою traversal `Expected a ruff source file`. Нові й підтримувані source/test/script шляхи проходять scoped checks; generated thesis figure script не змінювався.

Фінальний висновок: `REPRO_06C_ADAPTIVE_MULTIPATH_READY` у межах survivor-specific approximation. Профіль невідомого time-varying Rician і slow Rician пройшов deterministic integration та reference-size stability run; це не означає global ML optimum або statistical superiority. `UNKNOWN_STATIC_MULTIPATH_READY`, `SLOW_FADING_MULTIPATH_READY`, `ADAPTIVE_RICIAN_MULTIPATH_READY`, `PSP_CAUSALITY_READY`, `MULTIPATH_ETA20_READY`, `TRUTH_ISOLATION_READY`. `paper_exact:false`, `receiver_enabled:false`; REPRO-07 не запускали.
