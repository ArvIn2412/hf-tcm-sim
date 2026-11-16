# REPRO-06B — інтеграція finite-depth Viterbi

REPRO-06B додає окремий generic expanded-graph decoder у `expanded_viterbi.py`; REPRO-06 `finite_viterbi.py`, REPRO-04 Hamming metrics і REPRO-05 single-path joint metrics лишилися без змін. `run_expanded_viterbi` приймає матрицю `F × E`; streaming `ExpandedViterbiDecoder.consume_metric_row()` приймає один вектор довжини `E`, `flush()` повертає решту рішень.

`eta` — число trellis transitions. За `eta=20` звичайне рішення для symbol 0 доступне після надходження symbol 19 (`decision_available_at=19`), traceback depth 20. Після кінця кадру best доступний terminal expanded state обирається тільки з metrics; reference final state не використовується. Tail отримує фактичну глибину `F-index`, часто меншу від 20. У контрольованому кадрі `F=32`, перше рішення має глибину 20; після `flush` усі 32 decisions присутні рівно один раз.

У receiver config підтримуються `full_frame` і `finite_depth`. Branch rows обчислюються перед передаванням decoder і не залежать від режиму. Full-frame використовує terminal survivor над повною історією; finite-depth комітить локальний survivor за ковзним вікном. Їхні шляхи можуть різнитися; це очікувана властивість і не підстава для переваги.

Survivor ring обмежений `eta` рядками по expanded target-state predecessor IDs. Пам'ять core для survivor rows — `O(eta*S)`; output decision records і batch branch matrix усе одно мають `O(F)`/`O(FE)` обсяг. Діагностичний trace окремий від компактного core.

Подвійний receiver сценарій у `outputs/repro06b/reference_static_2path/F*/` передає той самий `ReceiverObservation` обом гілкам. Hamming гілка не є ISI-aware equalizer; спільний запуск лише перевіряє спільний buffer та однакові evaluation boundaries.
