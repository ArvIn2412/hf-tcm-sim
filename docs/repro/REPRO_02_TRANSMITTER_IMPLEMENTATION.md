# REPRO-02 — реалізація передавального тракту

## Межі етапу

Реалізовано окремий namespace `hf_tcm.repro`. Він формує інформаційні біти, кодує їх Encoder A зі швидкістю 2/3, застосовує реконструйований профіль маркування ADR-002, модулює 8PSK та утворює прямокутні ZOH-відліки. Жоден канал, приймач, демодулятор, декодер, BER/SER оцінювач або Monte Carlo не запускається.

`paper_exact:false` та `receiver_enabled:false` залишаються у runtime-результаті й manifest.

## API та конфігурація

- `TransmitterConfig` (`config.py`) — незмінна конфігурація зі строгим JSON schema `repro02-transmitter-v1`.
- `generate_information_bits(config)` — режими `manual`, `pattern`, `seeded_random`; seeded режим явно використовує локальний NumPy `PCG64`, не глобальний RNG.
- `encode(input_pairs, initial_state, termination_policy)` — Encoder A, пари бітів у порядку `(u0,u1)`.
- `build_edge_mapping(encoder_result)` — таблиця ADR-002 з окремим `mapping_id` та SHA-256.
- `modulate(phase_indices, amplitude, phase_offset_rad, phase_increment_rad)` — комплексні 8PSK символи.
- `rectangular_zoh(symbols, samples_per_symbol=8)` — рівно 8 комплексних відліків на символ.
- `run_transmitter(config)` — наскрізний API, повертає `TransmitterResult` з input/coded bits, парами, станами, edge IDs, фазами, символами, I/Q, енергіями, sample indices, termination та provenance.

Інформаційні біти мають dtype `int8`, shape `(2F,)`; пари `(F,2)`; кодові трійки `(F+T,3)`, де `T` — лише явно задані termination steps; символи `(F+T,)`; відліки `(8(F+T),)` complex128. Індекси символу/локального відліку/абсолютного відліку збережені окремими масивами.

Конфігурація вимагає явного `frame_symbols`, initial state, termination policy, амплітуди та φ₀. Вхідні біти не обрізаються і не доповнюються непомітно. Підтримана termination policy `zero_tail_2` додає рівно дві нульові інформаційні пари й фіксує їх окремо від payload.

## Відтворюваність і CLI

Запуск без параметрів показує довідку і не виконує кадр. CLI приймає `--config`, `--output`, `--validate-only`, `--print-summary`; записи обмежені `outputs/repro02/`. Артефакти включають вхідну конфігурацію, `arrays.npz` без pickle, mapping table, summary, manifest із dtype/shape/SHA-256 кожного масиву, середовищем і RNG metadata.

Приклад:

```powershell
python -m hf_tcm.repro.transmitter --config configs/repro02/deterministic_example.json --output outputs/repro02/example --print-summary
```

Два виконання `n_star_transmitter_only.json` дали ті самі хеші масивів і summary-значення. Час та вимірювання пам'яті не є науковою оцінкою продуктивності; `performance.json` є лише одиничним transmitter-only спостереженням.

## Наукові межі

Авторський файл `references/source_paper_2026.docx` має SHA-256 `a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8`; його редакція не підтверджена як запитана v7. Точна supervisor v7 редакція відсутня. `Δφ=π/4` використовується як приріст. `φ₀=0`, амплітуда 1 та profile mapping є явними параметрами проєктної реконструкції, а не підтвердженими авторськими значеннями.

REPRO-01 machine vectors, що передували цьому етапу, містили рядки, несумісні з описаними там recurrence equations. Незалежна перевірка в REPRO-02 виявила це; 16 векторів і відповідна таблиця виправлені за формулами `c2=u0`, `c1=u1 XOR p2`, `c0=p1`, `next=(u1,p1)`. Виправлення не змінює джерело або старий production код; воно документоване як корекція помилкових тестових даних REPRO-01.
