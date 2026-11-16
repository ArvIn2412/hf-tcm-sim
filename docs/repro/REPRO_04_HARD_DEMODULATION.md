# REPRO-04 — жорстка демодуляція 8PSK

Для кожного символу `k` receiver бере явно визначену множину відліків `J_k` і для кожної гіпотези `b∈{0,…,7}` обчислює

`D[k,b] = Σ(i∈J_k) |y[i] − g A exp(j(φ₀ + bπ/4))|²`.

Тут `y[i]` — комплексний прийнятий baseband відлік; `A>0` — amplitude normalization; `φ₀` — явно заданий фазовий reference; `g=1` у `fixed_nominal`, або заданий приймачу сталий комплексний gain у `known_static_complex_gain`. Вибирається `argmin_b`; при точній рівності `numpy.argmin` повертає найменший фазовий індекс. Це лише nearest-constellation hard classification. Воно не є joint demodulation/decoding і не використовує trellis constraints.

Обчислення використовує тотожність суми квадратів відстаней до сталої гіпотези, але зберігає всі вісім `D[k,b]` для діагностики. Числова точність — `float64` для відстаней, `complex128` для received data. Відкидання незначного від'ємного round-off відбувається через нижню межу нуль.

## Від фаз до кодових бітів

Для зафіксованого профілю ADR-002 `b = 4c₂ + 2c₁ + c₀`, тому inverse table: `(c₂,c₁,c₀)=((b>>2)&1,(b>>1)&1,b&1)`. Усі вісім phase indices дають різні трійки; вони також покривають множину вихідних трійок Encoder A. Це bijection для профілю `adr002_assumed_natural_binary_c2_c1_c0_v1`, але не підтвердження авторського фазового маркування.

`Δφ=π/4` — phase increment. Абсолютний `φ₀` окремий параметр; його не прирівняно до `π/4`. У REPRO-03 reference run значення `φ₀=0` узято з transmitter config як public experiment setup, а не виведено з прихованого стану каналу.

## Дані та перевірки

`HardDemodulation` містить hard phase indices, decoded triples, матрицю відстаней форми `(F,8)`, constellation hypotheses і середні sample values для зручного огляду. Незалежні тести перевіряють усі 8 точок, inverse label bijection, статичний відомий gain та noiseless identity. Невідомий фазовий зсув або часово-змінне завмирання не оцінюються цим блоком.

