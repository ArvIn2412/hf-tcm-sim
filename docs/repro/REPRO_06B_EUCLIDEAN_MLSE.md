# REPRO-06B — Euclidean MLSE зі статично відомим CSI

## Predictor і гілкова вартість

Для кожного expanded transition `e`, його фазової історії та символу `k` predictor обчислює всі передбачені відліки:

\[
\widehat y_e[n]=\sum_\ell h_\ell x_e[n-d_\ell],
\qquad
J_e(k)=\sum_{n\in W_k}|y[n]-\widehat y_e[n]|^2.
\]

`h_l` і цілочисельні `d_l` є явними receiver-public параметрами. Відкладені компоненти беруться з фази в augmented-node history. Відсутні початкові й післякадрові відліки дорівнюють нулю. Поточна reference configuration використовує `h0=1+0j`, `h1=0.35+0.15j`, `d=[0,3]`, zero noise; ці значення позначені як інженерний project profile, не як дані статті.

Підтримуються `squared_euclidean = sum(|r|^2)` та `euclidean = sqrt(sum(|r|^2))`, вибір явно збережено в receiver config. Viterbi додає вибрану branch cost. Корінь метрики не можна загалом винести крізь шляхову суму; тому Euclidean та squared-Euclidean профілі не оголошуються еквівалентними.

Статичне передобчислення phase/history waveform templates не змінює operands; batch metric matrix звірено з незалежним перехідним evaluator, а короткий кадр — з прямим exhaustive перебором усіх інформаційних пар.

## Режими та межі

Підтримано лише `known_public_static` CSI. Немає hard demodulation перед Viterbi. `EvaluationTruth` і `ChannelResult` відхиляються API; приймач приймає рівно `ReceiverObservation` та config. Single-path REPRO-05 код не змінений.

Невідомий часово-змінний multipath/Rician estimator не реалізовано. Звичайний Rician channel output не можна подавати цьому статичному профілю як коректно узгоджений receiver model. Необхідне survivor-specific або інше memory-aware причинне оцінювання.

`paper_exact:false`; mapping лишається проєктною реконструкцією ADR-002.
