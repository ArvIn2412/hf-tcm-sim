# SCIENTIFIC-EXP-03A — енергетичні конвенції

## Визначення

**[ПРОЄКТ]** Для фактичних transmitted complex samples:

`E_tx,d = Σ_n |x[n]|²`,

`E_b,d = E_tx,d / N_payload_information_bits`.

Для A амплітудної 8PSK, F symbols, 8 ZOH samples/symbol та двох information bits/symbol без pilots: `E_tx,d = 8F A²`, тому `E_b,d=4A²`. Це незалежно перераховано з NPZ samples у всіх 205 pilot records.

З pilot overhead загальна витрачена енергія ділиться на payload bits, не на pilots: `E_b,d,total/payload = 8F A²/(2F_payload)`. Для F=128, preamble=4, burst=4/32 маємо 16 pilot symbols, 112 payload symbols (224 information bits), `E_b,d=1024A²/224=4.5714286A²`. Pilot period 8 дає 64 pilot symbols, 64 payload symbols, тож `E_b,d=1024A²/128=8A²`. Це включає енергію training в system cost; окремі pilot/payload energy поля зберігаються.

Complex AWGN у pilot має `CN(0,σ_c²)`, де комплексна variance `E|w|²=σ_c²`; за circular Gaussian components окремі real/imag variances — `σ_c²/2`. Поточна пілотна статистична сітка змінює transmit amplitude за fixed `σ_c²=0.05`, channel profile та seeds domain policy. Дискретний індикатор `γ_b,d=10log10(E_b,d/σ_c²)` є безрозмірним відношенням у dB за цією project convention.

## Інтерпретаційна межа

`γ_b,d` не автоматично є фізичним `Eb/N0`. Для такої інтерпретації потрібні узгоджені часові масштаби, pulse shape і sampled energy relation, bandwidth/noise spectral density convention, receiver filtering, real signal/carrier relation та визначення кількості channel uses/payload bits разом із pilot overhead. Ці калібрувальні умови тут не доведені. Не називати sample-domain complex variance фізичним `N0`, а project gamma — фізично виміряним Eb/N0.

## Sweep і метрики

Primary 03A пілот амплітудно змінює `A←A·10^(δdB/20)` за незмінного sample-domain noise variance. AWGN direct/pilot і static/Rician pilot застосовують ту саму amplitude convention; для кожного кадру значення перевіряється з actual Tx array. Рівний scale `A` подається в обидва metric cost generators, фазова таблиця не змінюється. Noise sweep не включався до виконаних 03A range pilot.

BER — decoded payload information bit errors / payload bits. Information-pair SER — decoded pairs with at least one incorrect bit / payload pairs. FER — frames with at least one payload bit error / independent frames. Phase-symbol SER тут не є основним outcome. В усіх парних arms лічильники відтворені з одного `reference_payload_pairs` та відповідних decoded arrays; для кожного кадру перевірено `pair_errors ≤ bit_errors ≤ 2·pair_errors`.

Немає валідних Rician BER=0,05 crossings у пілотній сітці, тому Rician energy gain не обчислюється. Жоден пілотний результат не підтверджує фізичний енергетичний виграш чи статейні 1,5 dB.
