# REPRO-04 — реалізація роздільного приймача

## Статус і межі

REPRO-04 додає окремий тракт `hard 8PSK → hard coded triples → integer Hamming → full-frame Viterbi` для Encoder A. Код розміщений у `src/hf_tcm/repro/`; історичний receiver та M5–M11 не змінювалися. Вхід приймача — тільки точний тип REPRO-03 `ReceiverObservation`. `ChannelResult`, `EvaluationTruth` і їхні підкласи не приймаються.

Це project-defined, відтворюваний receiver, а не точна авторська реалізація. Збережено `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN. Mapping ADR-002 має статус `PROJECT_RECONSTRUCTION_ADR002`. Виконується full-frame traceback; `eta=20` не заявляється.

## API

```python
run_separate_receiver(
    observation: ReceiverObservation,
    receiver_config: SeparateReceiverConfig,
) -> SeparateReceiverResult
```

`SeparateReceiverConfig` фіксує очікувану кількість символів, initial state, termination, зсув вибору відліків, front end, ідентифікатори Encoder A/mapping і tie policy. `ReceiverFrontEndConfig` підтримує `fixed_nominal` та `known_static_complex_gain`. Другий режим використовує лише комплексний коефіцієнт, прямо заданий у конфігурації приймача. Автоматичного оцінювання чи вирівнювання невідомого каналу немає.

`SeparateReceiverResult` зберігає hash вхідного observation, точні індекси й діапазони відліків, hard phase decisions, трійки, матрицю branch costs, накопичені метрики станів, survivor edges, декодований шлях, payload біти та повну послідовність із termination symbols. Arrays незмінні. `receiver_io.py` зберігає лише цей результат; observation loader читає тільки `receiver_observation.npz/json` і не відкриває `evaluation_truth.npz`.

## Часове вирівнювання

Один TCM-крок відповідає восьми відлікам REPRO-02. `expected_symbol_count=F` має бути явно заданий. Для символу `k` зсув `q∈[0,7]` означає використання sample indices `8k+q … 8k+7`. Вибір не оптимізується за переданими бітами чи channel truth. Усі інші відліки записуються як `unprocessed_sample_indices`: зокрема, три відліки хвоста після кадру не утворюють символ `F`.

## Обмеження каналу

Fixed nominal constellation працює без інформації про fading. `known_static_complex_gain` коректний тільки тоді, коли цей gain відомий receiver за конфігурацією експерименту. Невідомий time-varying Rician/multipath канал не компенсується, тож hard decisions і BER можуть погіршитися. Receiver не має доступу до coefficient histories, доданого шуму, per-path contributions або transmitter reference.

## Запуск

```powershell
python -m hf_tcm.repro.receiver_cli --config configs/repro04/reference_n_star_receiver.json --input outputs/repro03/reference_n_star --output outputs/repro04/reference_n_star --print-summary
```

Без `--config` та `--input` CLI лише показує довідку. `--validate-only` перевіряє schema/hash без декодування. NPZ містить numeric arrays; JSON summary та manifest містять config і SHA-256. SVG графіки будуються з receiver observation/result.

BER/SER перераховується окремою evaluation командою, яка читає лише збережений receiver result і наданий reference JSON:

```powershell
python -m hf_tcm.repro.receiver_evaluation_cli --receiver-output outputs/repro04/reference_n_star --reference path/to/evaluation_reference.json --output outputs/repro04/evaluation --print-summary
```

Reference JSON schema: `{"information_bits": [0,1,...], "phase_indices": [0,1,...]}`. Evaluation command не повторно запускає receiver.

