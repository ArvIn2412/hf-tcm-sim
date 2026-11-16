# REPRO-03 — перевірка Rician coefficients

Існуючий `src/hf_tcm/channels/rician.py` реалізує:
`sqrt(P)(sqrt(K/(K+1))*exp(jφ)+sqrt(1/(K+1))*g)`. Його `g` має unit complex power; у AR(1) режимі перше значення теж stationary `CN(0,1)`, а не zero-start transient. Реалізація позначає AR(1) як approximate. REPRO-03 тонкий wrapper `rician_fading.py` додає per-path PCG64 seed і названі source/project statuses без зміни старого helper.

Перевірено окремо: static history є сталою; той самий seed відтворює всі coefficients; різний seed змінює realization; при `P=0.75`, `K=3`, `ρ=0.72`, `φ=0.4`, seed `20261106`, N=250000 отримано `E|h|²=0.751774`, diffuse power `0.187925` (очікування `0.1875`), lag-1 correlation `0.720323 + 0.001519j` (цільове `0.72`). Ці значення підтверджують вибрану статистичну параметризацію на цьому тестовому потоці, не фізичну HF fidelity. K є ratio `P_LOS/P_diffuse`, не power-in-dB input.

Ні AR(1), ні K-факторний Rician distribution самі по собі не доводять HF channel fidelity. У джерельному реєстрі fading law/параметри неповні; точні Doppler, frequency selectivity, Doppler spectrum, path delays і time scale не відновлені. Rician profiles тут — параметризоване дослідницьке наближення.
