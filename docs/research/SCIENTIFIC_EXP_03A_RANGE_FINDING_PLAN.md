# SCIENTIFIC-EXP-03A — зафіксований bounded range-finding план

**Статус:** план зафіксовано до запуску; це підготовча, не confirmatory серія.

## Мета й межі

Перевірити працездатність спільного pilot frontend / clean-tail combiner і приблизно локалізувати BER-області для майбутньої сітки SCIENTIFIC-EXP-03B. Не оцінювати остаточний енергетичний виграш і не переносити ці кадри до confirmatory вибірки.

## Незмінні параметри пілота

| Параметр | Значення |
|---|---:|
| Кадр | `F=128` елементів сигналу |
| Енергетичні відступи | `[-15, -12, -9, -6, -3] dB` від базового `A=1` при фіксованій комплексній дисперсії `σ²_c=0.05` |
| Незалежні кадри на рівень | 5 |
| Ціль для range finding | BER `0.05` (лише навігаційна мітка) |
| Seed derivation | `SeedSequence([root_seed, 0x03A, point_index, trial_index])`, три uint64 для джерела, fading, noise |
| Pilot схема у pilot режимах | 4 preamble symbols; burst довжини 4 кожні 32 елементи; payload/pilot inputs однакові для A-E та A-H |
| Декодер | спільний Encoder A, `η=20`, однаковий constrained traceback |
| Ліміт runner | максимум 120 s на серію; checkpoint після кожного кадру |
| Bootstrap | 500 paired cluster draws; описово, без confirmatory інтерпретації |

## Серії й seed domains

| ID | Канал | Frontend | Root seed |
|---|---|---|---:|
| `exp03a-pilot-awgn-direct-v1` | unit-gain AWGN | пряме усереднення 8 samples, без equalizer та pilot | 831031 |
| `exp03a-pilot-awgn-pilot-v1` | той самий unit-gain AWGN profile | pilot estimate / clean-tail combiner | 831032 |
| `exp03a-pilot-static-d3-v1` | taps `1+0j`, `0.3−0.2j`, delays `[0,3]` | pilot estimate / clean-tail combiner | 831033 |
| `exp03a-pilot-rician-ar1-v1` | powers `[1,0.25]`, K `[4,1]`, LOS phases `[0,0.7]`, delays `[0,3]`, `ρ=0.98` per sample | pilot estimate / clean-tail combiner | 831034 |

Rician очікувана сума потужностей taps дорівнює `1.25`; це явно заданий профіль, не приховано перенормований до одиниці. Потужності шляхів незалежно нормуються чинним генератором до заданих середніх потужностей.

## Правило інтерпретації

Пілот використовується лише для перевірки меж діапазону, причинності, residual ISI/noise та часу. Сітка 03B після пілота може бути заморожена окремим протоколом із новим seed domain. Жодні пілотні trials не входять до оцінки 03B. Не виконувати екстраполяцію; відсутність перетину означає, що пілот не локалізував ціль.

## Межа запуску

Скрипт `scripts/run_scientific_exp03a_range_pilot.py` містить саме цей fixed design і передає runner лише `phase="range_finding"`. Confirmatory phase відхиляється типом конфігурації runner. Основну статистичну серію автоматично не запускати.
