# REPRO-04 — evaluation-only контракт

`run_separate_receiver` повертає рішення без reference bits/symbols. Окремий `evaluate_separate_receiver(result, reference_information_bits, reference_phase_indices)` після декодування порівнює результат із truth, який передає зовнішній evaluator.

- BER: бітові помилки серед payload information bits.
- SER: відмінність між hard phase decision і reference phase index для payload символів. Це зафіксоване project definition, не source-confirmed стаття.
- Для `zero_tail_2` останні два symbol/четири information tail bits виключаються зі знаменників; рішення та path для хвоста залишаються доступні у receiver result.
- Якщо reference length не відповідає payload довжині, evaluator завершується помилкою, а не обрізає мовчки.
- Позиції помилок повертаються окремо.

Один кадр дає лише описові BER/SER числа, а не статистичний доказ. У receiver CLI reference дані не завантажуються; evaluation є окремим API та окремою командою `python -m hf_tcm.repro.receiver_evaluation_cli`. Вона читає вже збережений receiver output і окремий JSON reference, не повторно запускає рішення, а зберігає `evaluation.json` з reference/output hashes. Evaluation object зберігає reference phase indices лише для окремих evaluation-графіків.

