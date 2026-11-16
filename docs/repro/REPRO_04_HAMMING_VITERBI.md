# REPRO-04 — метрика Хемінга та декодер Вітербі

## Branch metric

Для кожної hard трійки `r[k,j]` та кожного канонічного Encoder A edge `e` із вихідною трійкою `c[e,j]` обчислюється

`d_H(e,k)=Σ(j=0..2) 1[r[k,j] ≠ c[e,j]]`.

Результат — ціле число `0,1,2,3`. Матриця має форму `(F,16)`, dtype `int8`. Жодна евклідова відстань не входить у branch cost: Euclidean distance використана лише на попередній hard 8PSK стадії.

## Повнокадровий Viterbi

Становий порядок узято без змін із REPRO-02: `00,10,01,11`; edge order — `state_order_00_10_01_11_input_binary_00_01_10_11_v1`. На початку метрика заданого initial state дорівнює 0, решти станів — недосяжності. Для кожного кроку до метрики попереднього стану додається integer Hamming branch cost. Survivor edge зберігається для кожного часу і destination state.

Однакові costs розв'язуються стабільно: canonical edge iteration, оновлення лише при строгому покращенні; фінальний state при вільному завершенні — перший мінімум у `STATE_ORDER`. Так true final state не використовується. При `termination_policy="zero_tail_2"` останні два input pairs примусово `(0,0)`, а фінальний стан — `00`. При `none` кінцевий стан вільний.

Traceback охоплює весь кадр. Вихід містить повний шлях і повні decoded pairs; `decoded_information_bits` виключає лише явно задані 2 termination pairs, а `decoded_frame_information_bits` їх зберігає. Це не реалізація чи твердження про `η=20`.

## Незалежні fixtures

Тести звіряють output triples усіх canonical edges із незалежним попарним порівнянням, усі Hamming distances — із незалежним скалярним сумуванням, deterministic equal-cost path, nonzero initial state і zero-tail constraints. Ідентичний noiseless channel дає точне відновлення payload. Один приклад не є оцінкою статистичної переваги.

