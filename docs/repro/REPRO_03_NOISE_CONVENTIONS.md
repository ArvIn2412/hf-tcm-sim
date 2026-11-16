# REPRO-03 — шумові конвенції

Підтриманий stochastic noise profile — `complex_awgn_sample_domain`:
\[
w[n]=w_I[n]+jw_Q[n],\quad w_I,w_Q\stackrel{ind}{\sim}N(0,\sigma_c^2/2),\quad E|w[n]|^2=\sigma_c^2.
\]
`noise_complex_variance` має одиницю normalized complex-envelope amplitude² per discrete sample. Відліки незалежні за часом; для нульової дисперсії генератор повертає точний нуль (config noise-free profile задає `noise_model=none`). Seed stream незалежний від fading.

Старий `channels/awgn.py` реалізує symbol-rate Eb/N0 conversion `N0=Es/(k·10^(Eb/N0/10))` із I/Q variance N0/2. Це не переноситься: REPRO-02 містить 8 повторених ZOH samples на символ і не задає matched filter, sample-rate noise bandwidth чи фізичне Eb/N0. Тому REPRO-03 не показує Eb/N0/SNR parameter і не приписує channel outputs фізичну BER-vs-Eb/N0 інтерпретацію.

Старий `channels/fluctuating_noise.py` реалізує real quadrature recurrence A(9) з coefficients A(10), `n=8` як source-derived relation, але initial state/innovations є project choices. Перетворення passband quadrature disturbance через carrier/time grid у complex baseband тут не визначене. Цей correlated mode не підключений і не називається AWGN. Новий independent complex AWGN не є заміною A(8)–A(10) і не є source-exact disturbance.

Фіксований seeded статистичний тест (N=300000, `σc²=0.4`, seed 417) отримав mean I/Q `−0.001226`, `−0.000302`, variance I/Q `0.199798`, `0.199504` при очікуванні 0.2. Автотест також перевіряє I/Q covariance та lag-1 autocovariance у межах допусків, побудованих із Gaussian sampling errors; він не створює BER/SER evidence.
