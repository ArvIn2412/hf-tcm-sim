# Mathematical model: implementation contract

Цей файл — короткий операційний довідник. Повний обсяг вимог у `TECHNICAL_SPECIFICATION.md`, розділи 3–9.

## 1. Кодер

**[СТАТТЯ]** `G(x) = [[1,0,0], [0,1+x²,x]]`, `R=2/3`; схема на с. 6.  
**[ПРОЄКТ, потребує SCI-02]** `c2[k]=u0[k]`, `c1[k]=u1[k] XOR u1[k-2]`, `c0[k]=u1[k-1]`; стан `(u1[k-1],u1[k-2])`; 4 стани, 4 дозволені входи на стан.

Визначити: порядок бітів, initial_state, zero-tail/tail-biting/unterminated, frame alignment.

## 2. 8PSK

> **Correction note — M11d, 2026-11-02:** the historical sentence below in this section is imprecise when it calls `π/4` the absolute `φ0`. The original [A], p. 5, defines `Δφ=π/4` as a phase increment in the phase-index expression; that alone does not set an absolute initial phase `φ0=π/4`. The old wording is retained for audit traceability. The implementation's absolute orientation and edge-to-phase mapping remain the ADR-002 project reconstruction. See `M11D_SOURCE_FIDELITY_AUDIT.md`.

**[ПРОЄКТ]** `S[m]=exp(j*(2πm/8+φ0))`. Стаття згадує `φ0=π/4` (с.5). `labeling` має бути явною бієкцією `{0,1}³ ↔ {0,…,7}`. До SCI-02 заборонено називати обране маркування авторським.

## 3. AWGN і нормалізація

**[ПРОЄКТ]** `Es=1`, `k_info=2 info bits/symbol` (за відсутності overhead), `γb=10^(EbN0_dB/10)`, `N0=Es/(k_info*γb)`, `n=sqrt(N0/2)*(ZI+j ZQ)`, `ZI,ZQ~N(0,1)`.

**[ПРОЄКТ — M2 baseline]** `numpy.random.Generator` передається явно до AWGN-функції. Перша BER/SER метрика використовує незавершений кадр: початковий стан `(0,0)`, кінцевий стан Вітербі вільний; автоматичні tail-біти не додаються. `SER` тут означає помилки жорсткого рішення 8PSK до декодування, а `BER` — помилки відновлених інформаційних бітів. Обидва лічильники зберігають чисельник і знаменник.

При termination/padding потрібно звітувати, чи застосовано номінальний `k_info=2`, чи фактичний `effective_info_bits_per_symbol`; **заборонено непомітно перемикатися між визначеннями**.

## 4. Багатопроменевість

**[ПРОЄКТ, концептуально відповідає суперпозиції зі статті]** `y[t] = Σ_l h[l,t] x[t−τ_l] + n[t]`. Кількість шляхів, масштаб, затримки та Rician K — сценарій. Стаття не дає повного набору конкретних чисел (SCI-04). Спрощений AR/корельований Gaussian fading — тільки з позначкою `approximate`.

**[ПРОЄКТ — approximate, не paper-exact]** M3 задає кожний шлях окремо: цілочисельна затримка у відліках, середня потужність, Rician K-фактор і фаза LOS. Статичний режим використовує сталий коефіцієнт у кадрі. `approximate_ar1` генерує нормований комплексний Gaussian diffuse-компонент з `g[t]=ρg[t−1]+sqrt(1−ρ²)w[t]`, де `ρ∈[0,1)` заданий користувачем; LOS-компонент сталий. Затримані хвости виходу доповнюються нулями. Це параметризований навчальний канал, а не реалізація невідомої рекурсії зі статті.

**[ПРОЄКТ — approximate, SCI-07]** I/Q waveform helper розгортає кожен символ у 8 однакових відліків (zero-order hold / прямокутний імпульс) і повертає окремі I та Q масиви. Фільтрація, синхронізація, дробові затримки та форма імпульсу статті не моделюються.

## 5. Декодування

**A: hard** `Hamming(hard_label(y[k]), branch_output_label)`.  
**B: soft** `abs(y[k] - expected_constellation_point(branch))**2`.  
**C: adaptive [СТАТТЯ як ідея]** мінімізує накопичений squared-Euclidean residual за формулою (2): квадрат різниці між спостереженими та прогнозованими I/Q компонентами сумується за вікном `η` і променями. Це не тотожне одній M2 branch cost. Точні прогнози/індекси та адаптивна реалізація залежать від SCI-02…04; див. ADR-001.

M2 реалізує лише A/B baseline: hard Hamming і soft squared-Euclidean branch costs на спільній чотиристанній решітці. Це не реалізує adaptive decoder C.

## 6. BER і SER

`BER = bit_errors/info_bits_checked`. Вирівнювання input/output і виключення завершальних бітів виконуються до ділення. `SER` має вказувати тип символу та його знаменник. При 0 помилках виводити `0/N` і, за потреби, upper confidence bound.

## 7. Відтворення результату 1,5 дБ

Стаття повідомляє +1,5 дБ, але не задає повного протоколу. Наш результат — емпірична різниця потрібного Eb/N0 при однаковому BER із відомим baseline, статистикою та інтерполяцією; **1,5 дБ не використовується як примусова ціль**.
