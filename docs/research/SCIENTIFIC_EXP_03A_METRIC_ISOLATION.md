# SCIENTIFIC-EXP-03A — ізоляція метрик

## Дизайн

У metric contrast обидві arms отримують один і той самий вектор рівняних комплексних спостережень `z[k]`, однакову інформаційну/пілотну послідовність, Encoder A transitions, initial state, відомі pilot edge constraints і η=20 finite-depth Viterbi. Фіксований порядок edge hypotheses походить із `transition_table()`; phase index формується з трійки `4*c2 + 2*c1 + c0`. Окремий тест порівнює всі 16 відповідностей.

Для кожного переходу `e` евклідова вартість є

`m_E(k,e) = |z[k] - A exp(j(2πq(e)/8 + φ₀))|²`.

Hamming arm спершу формує один candidate-independent hard phase:

`q̂[k] = argmin_q |z[k] - A exp(j(2πq/8 + φ₀))|²`,

потім застосовує канонічний inverse label `b̂[k]=label(q̂[k])` і

`m_H(k,e)=d_H(b̂[k], c(e))`.

Рівність за відстанню вирішується фіксованим правилом: найменший phase index. Кожний Hamming branch рядок залежить від `z[k]` та еталонного edge label, а не від власного candidate slicing; тож він не є штучно нульовим для кожного edge. Encoder/phase mapping, Euclidean scalar calculations, Hamming distances, tie rule, Viterbi trace parity та noiseless controls закріплено незалежними тестами.

Термін «єдина відмінність — метрика» тут має операційне значення: після спільного frontend змінюється тільки правило формування branch cost, де hard slicing є необхідною частиною визначення Hamming metric. Це не означає, що Euclidean і Hamming costs є лінійно взаємозамінними або що вони мають однакову статистичну правдоподібність.

## AWGN baseline

У direct-control AWGN режимі застосовується однакове усереднення восьми ZOH samples на символ без equalizer і pilot. За незалежного `w[n]~CN(0,σc²)`, ідеального unit gain та одного символу на восьми samples, усереднений noise має `CN(0,σc²/8)`. Це найчистіший контроль впливу soft complex distance проти жорсткого phase label; він не має pilot estimate reuse.

## Спільний equalizer і його межі

Нехай `y[n]=Σ_l h_l[n]x[n-d_l]+w[n]`, `x[n]` — 8-sample ZOH, а `D=max_l d_l<8` — ціле. Для sample indices `8k+D … 8k+7` кожен delayed argument `n-d_l` належить відрізку `[8k,8k+7]`. Отже всі delayed paths у clean-tail window несуть той самий `x_k`; попередній символ відсутній. Pilot estimates оцінюють composite gain, а спільний coherent combiner повертає один `z[k]` для обох decoder arms. Доказ і кодовий контракт обмежені саме цими умовами.

Це усуває детерміновану міжсимвольну інтерференцію в обраних відліках, але має ціну: для `D=3` зберігається 5 із 8 samples/символ; абсолютна та відносна шумова статистика змінюється; приймач відкидає решту samples. Це не еквівалентно повному оптимальному ISI decoder.

## Масштаб і статистична надійність

Квадратична Euclidean row має одиниці амплітуди², Hamming row — цілі 0…3. Додатне множення всіх Euclidean costs на одну константу не змінює argmin path за незмінних constraints, але не робить cost співмірним із Hamming. Евклідова метрика використовує відстань/величину залишку; Hamming втрачає її після slicing і зберігає лише labels. Амплітуда `A` входить у сузір'я обох arms однаково. Якщо неправильно підставити різний масштаб або різний phase mapping, це вже буде не контроль метрик; hashes і fixtures перевіряють спільні frontend output та config.

Для білого AWGN з відомою сталою дисперсією squared Euclidean likelihood ranking природний. Після pilot-based equalization effective residual містить channel-estimation error; при reuse однієї noisy estimate він може бути correlated між symbols, а Rician coefficient може змінитися в межах clean window. Тому невиважений Euclidean branch cost тут — зафіксований проектний decoder metric, але не доведений ML metric для реального Rician residual. Hamming, відповідно, не враховує відстань до найближчої фази та різницю надійності відліків. Ці властивості треба включити в тлумачення порівняння, а не приховувати normalizing weights.

EvaluationTruth використовується лише post-decode, для RMSE/ISI/noise diagnostics. Oracle-CSI frontend має окрему назву/режим і не включається до практичного gain. Порівняння повних Joint/B0/B1 алгоритмів є окремим contrast B і не є метрик-ізоляційним результатом.

## Статистичний результат пілоту

Кожна точка мала лише 5 незалежних кадрів, F=128. 205 парних кадрів використано лише для пошуку діапазону й перевірки infra. Нульові BER точки та `PARTIAL`/`NOT_ESTIMABLE` bootstrap outcomes не є оцінкою фінального gain. Rician period 32 не перетнув 0,05 ні для A-E, ні для A-H; period 8 A-E перебував нижче 0,05 у всіх виміряних точках, A-H — вище. Жоден Rician gain не оцінюється.

Повні рядки, counts, decoded bits і hashes: `outputs/scientific-exp03a/metric-studies/exp03a-*/trials/`; незалежний validator: `outputs/scientific-exp03a/validation/independent_pilot_recount.json`.
